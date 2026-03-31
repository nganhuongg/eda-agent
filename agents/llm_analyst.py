from __future__ import annotations

import logging
import os
import warnings
from pathlib import Path
from typing import List

import openai
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / ".env.local")
from pydantic import ValidationError
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from agents.schemas import AnalystDecision
from state.runtime_state import AgentState

_VALID_TOOLS = [
    "analyze_distribution",
    "detect_outliers",
    "analyze_missing_pattern",
    "analyze_correlation",
]

_SYSTEM_PROMPT = (
    "You are a data analyst. For the given column signals, return ONLY a JSON object "
    "matching this exact schema:\n"
    "{\n"
    '  "column": "<string: column name>",\n'
    '  "hypothesis": "<string: testable prediction about risk or opportunity>",\n'
    '  "recommended_tools": ["<one or more of: analyze_distribution, detect_outliers, '
    "analyze_missing_pattern, analyze_correlation>\"],\n"
    '  "business_label": "<one of: risk, opportunity, anomaly, trend>",\n'
    '  "narrative": "<string: plain business language, no statistical jargon>",\n'
    '  "claims": [{"field": "<signal_field_name>", "value": <numeric_value>}]\n'
    "}\n"
    "Do not include any text before or after the JSON object.\n"
    "narrative must use plain language a non-technical stakeholder can understand — "
    "no terms like kurtosis, p-value, adfuller, skewness, or standard deviation.\n"
    "claims[] must reference only the signal field names listed under 'Signals' — "
    "never include temporal context fields in claims[].\n"
    "When a 'Temporal context' block is present, incorporate period comparisons naturally "
    "into the narrative (e.g. 'July was up 3% vs June', 'the column is trending upward').\n"
    "If rejected_claims are provided, address each one in the revised hypothesis and claims."
)


def build_analyst_context(state: AgentState, column: str) -> dict:
    """Return a signal-only context dict with no DataFrame references.

    Enforces the df boundary (D-09, D-10, D-11):
    - Numeric columns: missing_ratio, skewness, outlier_ratio, variance
    - Categorical columns: entropy, dominant_ratio, unique_count, missing_ratio
    - Temporal signals if present: trend_direction, trend_confidence,
      mom_delta, yoy_delta, forecast_values
    - Also includes: risk_score, analyzed_columns, column, column_type

    This function must never access df, call .values, .to_dict(), or any
    DataFrame method. AgentState TypedDict structurally cannot hold a df key.
    """
    col_signals = state["signals"].get(column, {})
    col_type = state["dataset_metadata"].get(column, {}).get("type", "unknown")

    if col_type == "numeric":
        extracted = {
            k: col_signals.get(k)
            for k in ("missing_ratio", "skewness", "outlier_ratio", "variance")
        }
    else:
        extracted = {
            k: col_signals.get(k)
            for k in ("entropy", "dominant_ratio", "unique_count", "missing_ratio")
        }

    # Temporal context (optional) — stored separately so the LLM uses these
    # in narrative prose but does NOT cite them in claims[].
    # The Critic validates claims against state["signals"], not temporal_signals,
    # so any temporal field in claims[] would always be rejected.
    temporal_context = {}
    col_temporal = (
        state.get("temporal_signals", {})
        .get("columns", {})
        .get(column, {})
    )
    if col_temporal:
        trend = col_temporal.get("trend", {})
        if trend.get("direction"):
            temporal_context["trend_direction"] = trend["direction"]
        if trend.get("confidence"):
            temporal_context["trend_confidence"] = trend["confidence"]

        period_deltas = col_temporal.get("period_deltas", {})
        mom = period_deltas.get("mom_pct_change", {})
        if mom:
            last_date = list(mom.keys())[-1]
            last_val = list(mom.values())[-1]
            # Format as human-readable so the LLM can write "July +3% vs June"
            temporal_context["mom_delta"] = f"{last_val * 100:+.2f}% ({last_date})"
        yoy = period_deltas.get("yoy_pct_change", {})
        if yoy:
            last_date = list(yoy.keys())[-1]
            last_val = list(yoy.values())[-1]
            temporal_context["yoy_delta"] = f"{last_val * 100:+.2f}% ({last_date})"

        forecast_block = col_temporal.get("forecast", {})
        if forecast_block.get("forecast"):
            temporal_context["forecast_values"] = forecast_block["forecast"]

    return {
        "column": column,
        "column_type": col_type,
        "signals": extracted,
        "temporal_context": temporal_context,
        "risk_score": state["risk_scores"].get(column, 0.0),
        "analyzed_columns": list(state.get("analyzed_columns", set())),
    }


def _get_client() -> OpenAI | None:
    """Return OpenAI client pointed at MiniMax, or None if key missing (D-06)."""
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        return None
    return OpenAI(
        api_key=api_key,
        base_url="https://api.minimax.io/v1",
        max_retries=0,  # tenacity owns the 3-retry budget (D-08); disable SDK retries
    )


@retry(
    wait=wait_random_exponential(min=1, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(openai.RateLimitError),
    reraise=False,
)
def _call_minimax(client: OpenAI, messages: list) -> str | None:
    """Call MiniMax API and return raw JSON string.

    Uses reasoning_split=True so that <think>...</think> content is separated
    into reasoning_details and content holds only the JSON output.
    """
    response = client.chat.completions.create(
        model=os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7"),
        messages=messages,
        response_format={"type": "json_object"},
        extra_body={"reasoning_split": True},
    )
    return response.choices[0].message.content


def _build_messages(context: dict, rejected_claims: List[str]) -> list:
    """Build the messages list for the MiniMax API call."""
    user_content = (
        f"Column: {context['column']}\n"
        f"Type: {context['column_type']}\n"
        f"Risk score: {context['risk_score']}\n"
        f"Already-analyzed columns: {context['analyzed_columns']}\n"
        f"Signals:\n"
        + "\n".join(f"  {k}: {v}" for k, v in context["signals"].items() if v is not None)
    )
    # Temporal context rendered as a separate block — LLM uses these in narrative
    # prose but must NOT include them in claims[] (Critic cannot validate them).
    temporal = context.get("temporal_context", {})
    if temporal:
        user_content += "\n\nTemporal context (use in narrative only — do NOT add to claims[]):\n"
        user_content += "\n".join(f"  {k}: {v}" for k, v in temporal.items())
    if rejected_claims:
        user_content += (
            "\n\nPreviously rejected claims: "
            + str(rejected_claims)
            + "\nAddress each rejected claim in your revised response."
        )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _infer_label_from_signals(signals: dict) -> str:
    """Infer business_label from signal values for deterministic fallback."""
    if signals.get("outlier_ratio", 0.0) > 0.1 or signals.get("missing_ratio", 0.0) > 0.1:
        return "risk"
    if signals.get("skewness", 0.0) > 1.5:
        return "opportunity"
    if signals.get("variance", 0.0) > 500.0:
        return "anomaly"
    return "trend"


def _deterministic_fallback(state: AgentState, column: str) -> AnalystDecision:
    """D-07: wrap deterministic pipeline output into AnalystDecision shape."""
    from insight.insight_generator import generate_insight_for_column  # noqa: PLC0415

    column_type = state["dataset_metadata"].get(column, {}).get("type", "numeric")
    signals = state["signals"].get(column, {})
    analysis_results = state["analysis_results"].get(column, {})

    insight = generate_insight_for_column(column, column_type, signals, analysis_results)

    logging.warning("LLM Analyst fell back to deterministic mode for column '%s'", column)

    return AnalystDecision(
        column=column,
        hypothesis=f"Deterministic fallback — column '{column}' flagged by risk planner",
        recommended_tools=["analyze_distribution"],
        business_label=_infer_label_from_signals(signals),
        narrative=str(
            insight.get("summary", f"Column '{column}' shows notable statistical characteristics.")
        ),
        claims=[],  # Always empty — avoids Critic rejections (Pitfall 4)
    )


def analyze_column(
    state: AgentState,
    column: str,
    rejected_claims: List[str] | None = None,
) -> AnalystDecision:
    """Public entry point. Phase 5 wraps with functools.partial for run_loop.

    Signature: analyze_column(state, column, rejected_claims=[])
    Phase 5 usage: run_loop(partial(analyze_column, state, column), critic_fn)
    """
    rejected_claims = rejected_claims or []
    client = _get_client()
    if client is None:
        return _deterministic_fallback(state, column)

    context = build_analyst_context(state, column)
    messages = _build_messages(context, rejected_claims)

    raw_json = None
    try:
        raw_json = _call_minimax(client, messages)
    except openai.APIError:
        pass  # Network, auth, timeout — immediate fallback without retry
    except RetryError:
        pass  # tenacity exhausted all 3 RateLimitError attempts (D-08) — fall back

    if raw_json is not None:
        # Strip markdown code fences if model wrapped JSON in ```json ... ```
        stripped = raw_json.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("\n", 1)[-1]  # remove first line (```json or ```)
            stripped = stripped.rsplit("```", 1)[0].strip()  # remove trailing ```
        try:
            return AnalystDecision.model_validate_json(stripped)
        except (ValidationError, ValueError):
            warnings.warn(
                f"AnalystDecision parse failure for '{column}': {str(raw_json)[:200]}"
            )

    return _deterministic_fallback(state, column)

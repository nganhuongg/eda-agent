from __future__ import annotations

import logging
import os
import warnings
from typing import List

import openai
from openai import OpenAI
from pydantic import ValidationError
from tenacity import (
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
    "claims[] must reference only the signal field names provided in the context.\n"
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

    # Temporal signals (optional — D-09)
    temporal = state.get("temporal_signals", {}).get(column, {})
    for k in ("trend_direction", "trend_confidence", "mom_delta", "yoy_delta", "forecast_values"):
        if k in temporal:
            extracted[k] = temporal[k]

    return {
        "column": column,
        "column_type": col_type,
        "signals": extracted,
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
    """Call MiniMax API and return raw JSON string."""
    response = client.chat.completions.create(
        model="MiniMax-M2.7",
        messages=messages,
        response_format={"type": "json_object"},
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

    if raw_json is not None:
        try:
            return AnalystDecision.model_validate_json(raw_json)
        except (ValidationError, ValueError):
            warnings.warn(
                f"AnalystDecision parse failure for '{column}': {str(raw_json)[:200]}"
            )

    return _deterministic_fallback(state, column)

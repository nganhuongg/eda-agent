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
    """Call MiniMax API and return raw JSON string. Raises NotImplementedError until Plan 04-02."""
    raise NotImplementedError


def _build_messages(context: dict, rejected_claims: List[str]) -> list:
    """Build the messages list for the MiniMax API call."""
    raise NotImplementedError


def _deterministic_fallback(state: AgentState, column: str) -> AnalystDecision:
    """D-07: wrap deterministic pipeline output into AnalystDecision shape."""
    raise NotImplementedError


def analyze_column(
    state: AgentState,
    column: str,
    rejected_claims: List[str] | None = None,
) -> AnalystDecision:
    """Public entry point. Phase 5 wraps with functools.partial for run_loop.

    Signature: analyze_column(state, column, rejected_claims=[])
    Phase 5 usage: run_loop(partial(analyze_column, state, column), critic_fn)
    """
    raise NotImplementedError

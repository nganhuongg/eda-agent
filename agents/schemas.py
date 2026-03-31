from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel


class AnalystDecision(BaseModel):
    """Structured result returned by the LLM Analyst for a single column.

    column: Target column name.
    hypothesis: Testable prediction formed before analysis tools run (ANLST-02).
    recommended_tools: Subset of ACTION_TO_TOOL keys to invoke (ANLST-03).
        Valid values: analyze_distribution, detect_outliers,
                      analyze_missing_pattern, analyze_correlation
    business_label: One of risk/opportunity/anomaly/trend (ANLST-04).
    narrative: Plain business language — no statistical jargon (ANLST-05).
    claims: List of {"field": <signal_field_name>, "value": <numeric>} dicts
            that the Critic validates against signals (D-01).
            Fallback path always uses claims=[] to avoid Critic rejections.
    """

    column: str
    hypothesis: str
    recommended_tools: List[str]
    business_label: Literal["risk", "opportunity", "anomaly", "trend"]
    narrative: str
    claims: List[dict]

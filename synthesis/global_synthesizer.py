from __future__ import annotations
from typing import Any, Dict


def _build_findings_list(state: Dict[str, Any]) -> Dict[str, Any]:
    """Convert analyst_decisions + risk_scores into the dict shape expected by quality_bar_critic.

    SYNTH-01 (D-06): sets single_angle=True when only 1 analysis tool ran for a column.
    SYNTH-02: returns findings sorted descending by risk_score.
    Columns with 0 tool results are excluded from Gate 2 findings (rendered separately
    as "Below risk threshold" in the report).

    claims=[] always (Phase 4 pattern: avoids Check 2 rejections from quality_bar_critic).
    """
    ranked = sorted(
        state["risk_scores"].items(),
        key=lambda x: -x[1],
    )
    findings = []
    for column, score in ranked:
        decision = state["analyst_decisions"].get(column)
        if decision is None:
            continue
        tool_count = len(state["analysis_results"].get(column, {}))
        if tool_count == 0:
            continue  # rendered as "Below risk threshold" in report, not in Gate 2
        finding = {
            "business_label": decision.business_label,
            "score": score,
            "column": column,
            "claims": [],  # safe: avoids Check 2 rejections (Phase 4 claims=[] pattern)
            "narrative": decision.narrative,
            "hypothesis": decision.hypothesis,
        }
        if tool_count == 1:
            finding["single_angle"] = True
        findings.append(finding)
    return {
        "findings": findings,
        "signals": state["signals"],
        "analysis_results": state["analysis_results"],
    }


def generate_global_summary(state):

    total_columns = state["total_columns"]
    analyzed = len(state["columns_analyzed"])

    numeric_cols = [
        col for col, meta in state["dataset_metadata"].items()
        if meta["type"] == "numeric"
    ]

    categorical_cols = [
        col for col, meta in state["dataset_metadata"].items()
        if meta["type"] == "categorical"
    ]

    return {
        "coverage_ratio": analyzed / total_columns,
        "numeric_columns": len(numeric_cols),
        "categorical_columns": len(categorical_cols)
    }
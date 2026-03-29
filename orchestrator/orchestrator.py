from __future__ import annotations

import logging
from functools import partial
from typing import Any, Dict

import pandas as pd

from agents.llm_analyst import analyze_column
from agents.schemas import AnalystDecision, CriticVerdict
from execution.analysis_tools import (
    analyze_correlation,
    analyze_distribution,
    analyze_missing_pattern,
    detect_outliers,
)
from insight.critic import validate_finding
from orchestrator.ralph_loop import run_loop
from planning.risk_planner import compute_risk_scores, risk_driven_planner
from profiling.signal_extractor import extract_signals
from state.runtime_state import AgentState


ACTION_TO_TOOL = {
    "analyze_distribution": analyze_distribution,
    "detect_outliers": detect_outliers,
    "analyze_missing_pattern": analyze_missing_pattern,
    "analyze_correlation": analyze_correlation,
}


def _record_action(
    state: Dict[str, Any],
    step: int,
    phase: str,
    plan: Dict[str, Any] | None,
    status: str,
    details: Dict[str, Any] | None = None,
) -> None:
    entry = {
        "step": step,
        "phase": phase,
        "status": status,
        "details": details or {},
    }
    if plan:
        entry.update(
            {
                "column": plan.get("column"),
                "action": plan.get("action"),
                "source": plan.get("source"),
                "reason": plan.get("reason"),
                "priority": float(plan.get("priority", 0.0)),
            }
        )
    state["action_history"].append(entry)


def _make_gate1_critic(state: AgentState, column: str):
    """Return a critic_fn closure wrapping validate_finding for run_loop Gate 1 (D-05)."""
    def critic_fn(decision: AnalystDecision) -> CriticVerdict:
        finding = {"column": decision.column, "claims": decision.claims}
        return validate_finding(finding, state["signals"], state["analysis_results"])
    return critic_fn


def _run_tools_for_column(
    state: Dict[str, Any],
    df: pd.DataFrame,
    column: str,
    column_type: str,
    step: int,
) -> None:
    """Run analysis tools for a column, populating state['analysis_results'][column] (D-02).

    df is passed here and NOWHERE else in the new loop. This is the structural df boundary.
    Numeric: analyze_distribution + detect_outliers.
    Categorical / all: analyze_missing_pattern + detect_outliers.
    """
    state["analysis_results"].setdefault(column, {})

    if column_type == "numeric":
        state["analysis_results"][column]["analyze_distribution"] = analyze_distribution(
            df, column, column_type
        )
        state["analysis_results"][column]["detect_outliers"] = detect_outliers(df, column)
    else:
        state["analysis_results"][column]["analyze_missing_pattern"] = analyze_missing_pattern(
            df, column
        )
        state["analysis_results"][column]["detect_outliers"] = detect_outliers(df, column)

    _record_action(state, step, "tools_run", {"column": column}, "completed",
                   {"tools_run": list(state["analysis_results"][column].keys())})


def run_agent(state: Dict[str, Any], df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
    """Run Analyst+Critic investigation loop per column (D-08: signature unchanged).

    Column-based outer loop (D-01): for each high-risk unanalyzed column,
    run tools first (D-02), then run_loop Gate 1 (D-05).
    Stores AnalystDecision in state['analyst_decisions'] (D-03).
    Bridges state['insights'] for backward compat with report generator (D-04).
    Logs exhaustion warning if Gate 1 does not approve (D-06).
    Returns dict matching D-09 shape.
    """
    max_columns = int(config.get("MAX_COLUMNS", len(df.columns)))

    for _col_idx in range(max_columns):
        # Refresh signals and risk scores each iteration
        state["signals"] = extract_signals(df, state["dataset_metadata"])
        state["risk_scores"] = compute_risk_scores(state["dataset_metadata"], state["signals"])

        plan = risk_driven_planner(state)
        if plan is None:
            return {
                "status": "SUCCESS",
                "reason": "NO_PENDING_INVESTIGATIONS",
                "columns_analyzed": len(state["analyzed_columns"]),
                "total_columns": len(state["dataset_metadata"]),
            }

        column = plan["column"]
        column_type = state["dataset_metadata"][column]["type"]

        # Tools-first: populate analysis_results before LLM sees signals (D-02)
        # df boundary enforced here — df never passed beyond this function
        _run_tools_for_column(state, df, column, column_type, _col_idx)

        # Gate 1: Analyst+Critic via run_loop (D-05)
        generator_fn = partial(analyze_column, state, column)
        critic_fn = _make_gate1_critic(state, column)
        decision: AnalystDecision = run_loop(generator_fn, critic_fn, max_iter=5)

        _record_action(state, _col_idx, "analyst_loop", plan, "completed",
                       {"column": column})

        # Exhaustion check: warn if best attempt not approved (D-06)
        final_verdict = critic_fn(decision)
        if not final_verdict.approved:
            logging.warning(
                "Gate 1 exhausted for column '%s' after 5 iterations — using best attempt",
                column,
            )

        _record_action(state, _col_idx, "gate1_result", plan, "completed",
                       {"approved": final_verdict.approved, "column": column})

        # Store AnalystDecision (D-03)
        state["analyst_decisions"][column] = decision

        # Bridge state['insights'] for backward compat (D-04)
        state["insights"][column] = {
            "summary": decision.narrative,
            "category": decision.business_label,
            "column": decision.column,
            "hypothesis": decision.hypothesis,
            "recommended_tools": decision.recommended_tools,
        }

        # Mark column as analyzed
        state["analyzed_columns"].add(column)

    return {
        "status": "PARTIAL",
        "reason": "MAX_COLUMNS_REACHED",
        "columns_analyzed": len(state["analyzed_columns"]),
        "total_columns": len(state["dataset_metadata"]),
    }

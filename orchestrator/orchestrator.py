from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from execution.analysis_tools import (
    analyze_correlation,
    analyze_distribution,
    analyze_missing_pattern,
    detect_outliers,
)
from insight.critic import suggest_investigations
from insight.insight_generator import generate_insight_for_column
from planning.risk_planner import compute_risk_scores, risk_driven_planner
from profiling.signal_extractor import extract_signals


ACTION_TO_TOOL = {
    "analyze_distribution": analyze_distribution,
    "detect_outliers": detect_outliers,
    "analyze_missing_pattern": analyze_missing_pattern,
    "analyze_correlation": analyze_correlation,
}


def _queue_action(state: Dict[str, Any], proposed_action: Dict[str, Any]) -> None:
    proposed_key = (proposed_action.get("column"), proposed_action.get("action"))

    for action in state["investigation_queue"]:
        existing_key = (action.get("column"), action.get("action"))
        if existing_key == proposed_key:
            return

    for entry in state["action_history"]:
        history_key = (entry.get("column"), entry.get("action"))
        if history_key == proposed_key and entry.get("status") == "completed":
            return

    state["investigation_queue"].append(proposed_action)


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


def run_agent(state: Dict[str, Any], df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
    max_steps = int(config.get("MAX_STEPS", max(1, len(df.columns) * 4)))

    for step in range(1, max_steps + 1):
        state["signals"] = extract_signals(df, state["dataset_metadata"])
        _record_action(state, step, "observe", None, "completed", {"signals_refreshed": True})

        state["risk_scores"] = compute_risk_scores(state["dataset_metadata"], state["signals"])
        _record_action(state, step, "assess", None, "completed", {"risk_scores_refreshed": True})

        plan = risk_driven_planner(state)
        if plan is None:
            return {
                "status": "SUCCESS",
                "reason": "NO_PENDING_INVESTIGATIONS",
                "steps": step - 1,
                "columns_analyzed": len(state["analyzed_columns"]),
                "total_columns": len(state["dataset_metadata"]),
            }

        _record_action(state, step, "plan", plan, "completed")

        column = plan["column"]
        action_name = plan["action"]
        column_type = state["dataset_metadata"][column]["type"]
        action_result = ACTION_TO_TOOL[action_name](df, column, column_type) if action_name == "analyze_distribution" else ACTION_TO_TOOL[action_name](df, column)

        state["analysis_results"].setdefault(column, {})
        state["analysis_results"][column][action_name] = action_result
        _record_action(state, step, "act", plan, "completed", action_result)

        insight = generate_insight_for_column(
            column=column,
            column_type=column_type,
            signals=state["signals"][column],
            analysis_results=state["analysis_results"][column],
        )
        state["insights"][column] = insight
        _record_action(state, step, "evaluate", plan, "completed", insight)

        for suggestion in suggest_investigations(
            column=column,
            column_type=column_type,
            signals=state["signals"][column],
            insight=insight,
            analysis_results=state["analysis_results"][column],
        ):
            _queue_action(state, suggestion)

        if action_name == "analyze_distribution":
            state["analyzed_columns"].add(column)

        _record_action(
            state,
            step,
            "update_state",
            plan,
            "completed",
            {"queued_actions": len(state["investigation_queue"])},
        )

    return {
        "status": "PARTIAL",
        "reason": "MAX_STEPS_REACHED",
        "steps": max_steps,
        "columns_analyzed": len(state["analyzed_columns"]),
        "total_columns": len(state["dataset_metadata"]),
    }

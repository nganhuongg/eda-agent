from __future__ import annotations

from typing import Any, Dict, List


def compute_risk_scores(
    dataset_metadata: Dict[str, Dict[str, Any]],
    signals: Dict[str, Dict[str, Any]],
) -> Dict[str, float]:
    numeric_variances = [
        float(column_signals.get("variance", 0.0))
        for column, column_signals in signals.items()
        if dataset_metadata[column]["type"] == "numeric"
    ]
    max_variance = max(numeric_variances, default=0.0)

    risk_scores: Dict[str, float] = {}

    for column, meta in dataset_metadata.items():
        column_signals = signals[column]
        missing_component = float(column_signals.get("missing_ratio", 0.0))
        skew_component = min(abs(float(column_signals.get("skewness", 0.0))) / 3.0, 1.0)
        outlier_component = min(float(column_signals.get("outlier_ratio", 0.0)) * 3.0, 1.0)

        if meta["type"] == "numeric" and max_variance > 0:
            variance_component = min(float(column_signals.get("variance", 0.0)) / max_variance, 1.0)
        else:
            variance_component = 0.0

        score = (
            0.35 * missing_component
            + 0.25 * skew_component
            + 0.20 * variance_component
            + 0.20 * outlier_component
        )
        risk_scores[column] = round(score, 4)

    return risk_scores


def risk_driven_planner(state: Dict[str, Any]) -> Dict[str, Any] | None:
    queued_actions: List[Dict[str, Any]] = []
    seen_keys = {
        (entry.get("column"), entry.get("action"))
        for entry in state["action_history"]
        if entry.get("status") == "completed"
    }

    for action in state["investigation_queue"]:
        action_key = (action.get("column"), action.get("action"))
        if action_key not in seen_keys:
            queued_actions.append(action)

    if queued_actions:
        queued_actions.sort(key=lambda item: (-float(item.get("priority", 0.0)), item.get("column", "")))
        selected = queued_actions[0]
        state["investigation_queue"] = [item for item in state["investigation_queue"] if item is not selected]
        return selected

    unexplored_columns = [
        column
        for column in state["dataset_metadata"]
        if column not in state["analyzed_columns"]
    ]

    if not unexplored_columns:
        return None

    selected_column = max(
        unexplored_columns,
        key=lambda column: (float(state["risk_scores"].get(column, 0.0)), column),
    )

    return {
        "column": selected_column,
        "action": "analyze_distribution",
        "priority": float(state["risk_scores"].get(selected_column, 0.0)),
        "reason": "Highest-risk unexplored column",
        "source": "risk_planner",
    }

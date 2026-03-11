from __future__ import annotations

import os
from typing import Any, Dict


def _format_number(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def generate_report(state: Dict[str, Any], summary: Dict[str, Any]) -> str:
    lines = ["# Dataset Technical Audit Report", ""]

    lines.extend(
        [
            "## 1. Overview",
            f"- Status: {summary['status']}",
            f"- Reason: {summary['reason']}",
            f"- Steps Executed: {summary['steps']}",
            f"- Columns Analyzed: {summary['columns_analyzed']}/{summary['total_columns']}",
            "",
        ]
    )

    lines.append("## 2. Risk Ranking of Columns")
    ranked_columns = sorted(state["risk_scores"].items(), key=lambda item: (-item[1], item[0]))
    for column, score in ranked_columns:
        lines.append(f"- {column}: {_format_number(score)}")
    lines.append("")

    lines.append("## 3. Signal Summary")
    for column, signals in state["signals"].items():
        metrics = ", ".join(f"{key}={_format_number(value)}" for key, value in signals.items())
        lines.append(f"- {column}: {metrics}")
    lines.append("")

    lines.append("## 4. Investigation History")
    for entry in state["action_history"]:
        if entry.get("phase") not in {"plan", "act", "evaluate", "update_state"}:
            continue

        details = entry.get("details", {})
        lines.append(
            f"- Step {entry['step']} | {entry['phase']} | {entry.get('column', '-')}"
            f" | {entry.get('action', '-')}"
            f" | source={entry.get('source', '-')}"
            f" | reason={entry.get('reason', '-')}"
            f" | status={entry.get('status', '-')}"
        )
        if details:
            detail_text = ", ".join(f"{key}={_format_number(value)}" for key, value in details.items())
            lines.append(f"  details: {detail_text}")
    lines.append("")

    lines.append("## 5. Analysis Results")
    for column, actions in state["analysis_results"].items():
        lines.append(f"### {column}")
        for action, result in actions.items():
            metrics = ", ".join(f"{key}={_format_number(value)}" for key, value in result.items())
            lines.append(f"- {action}: {metrics}")
        lines.append("")

    lines.append("## 6. Anomaly Findings")
    findings_written = False
    for column, insight in state["insights"].items():
        for finding in insight.get("anomaly_findings", []):
            lines.append(f"- {column}: {finding}")
            findings_written = True
    if not findings_written:
        lines.append("- No major anomalies were flagged by the rule-based insight layer.")
    lines.append("")

    lines.append("## 7. Visualizations")
    visualizations = state.get("visualizations", {})
    if visualizations:
        for name, path in visualizations.items():
            lines.append(f"- {name}: {path}")
    else:
        lines.append("- No visualizations were triggered by the current insight set.")
    lines.append("")

    report_text = "\n".join(lines)
    os.makedirs("outputs", exist_ok=True)

    path = "outputs/report.md"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(report_text)

    return path

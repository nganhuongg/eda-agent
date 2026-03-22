import os
from typing import Any, Dict, List

import httpx
from openai import OpenAI


def _format_number(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _build_llm_input_summary(state: Dict[str, Any], summary: Dict[str, Any]) -> str:
    lines: List[str] = [
        "# Compact Deterministic Audit Summary",
        "",
        "## Overview",
        f"- Status: {summary['status']}",
        f"- Reason: {summary['reason']}",
        f"- Steps Executed: {summary['steps']}",
        f"- Columns Analyzed: {summary['columns_analyzed']}/{summary['total_columns']}",
        "",
        "## Top Risk Columns",
    ]

    ranked_columns = sorted(
        state["risk_scores"].items(),
        key=lambda item: (-item[1], item[0]),
    )[:8]
    for column, score in ranked_columns:
        lines.append(f"- {column}: {_format_number(score)}")

    lines.extend(["", "## Key Investigation Summary"])
    investigation_lines = 0
    for entry in state["action_history"]:
        if entry.get("phase") != "act":
            continue

        column = entry.get("column", "-")
        action = entry.get("action", "-")
        details = entry.get("details", {})
        brief_details = ", ".join(
            f"{key}={_format_number(value)}"
            for key, value in list(details.items())[:4]
        )
        lines.append(f"- Step {entry['step']} | {column} | {action} | {brief_details}")
        investigation_lines += 1
        if investigation_lines >= 10:
            break

    lines.extend(["", "## Anomaly Findings"])
    finding_count = 0
    for column, insight in state["insights"].items():
        for finding in insight.get("anomaly_findings", []):
            lines.append(f"- {column}: {finding}")
            finding_count += 1
            if finding_count >= 12:
                break
        if finding_count >= 12:
            break
    if finding_count == 0:
        lines.append("- No major anomalies were flagged by the rule-based insight layer.")

    lines.extend(["", "## Visualization Summary"])
    visualizations = state.get("visualizations", {})
    if visualizations:
        for name, path in list(visualizations.items())[:12]:
            lines.append(f"- {name}: {path}")
    else:
        lines.append("- No visualizations were triggered by the current insight set.")

    lines.extend(["", "## Insight Snapshot"])
    for column, insight in list(state["insights"].items())[:8]:
        concise_insight = ", ".join(
            f"{key}={value}"
            for key, value in insight.items()
            if key not in {"anomaly_findings", "recommended_visualizations"}
        )
        lines.append(f"- {column}: {concise_insight}")

    return "\n".join(lines)


def generate_llm_report(state: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, str]:
    api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        return {
            "status": "missing_key",
            "path": "",
            "error": "GROQ_API_KEY is not set.",
        }

    base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    try:
        with httpx.Client(timeout=10.0) as client:
            health_response = client.get(base_url.replace("/openai/v1", ""))
            health_response.raise_for_status()
    except Exception as exc:
        return {
            "status": "request_failed",
            "api_key": api_key[:4] + "..." if api_key else "None",
            "path": "",
            "error": f"Cannot reach Groq API at {base_url}. {type(exc).__name__}: {exc}",
        }

    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )

    deterministic_report = _build_llm_input_summary(state, summary)

    prompt = f"""
You are a senior data auditor producing narrative only.

Rewrite the following compact deterministic technical audit into a professional report.

Rules:
- Do NOT invent, recalculate, round differently, or modify any statistic.
- Do NOT add new numeric claims.
- Do NOT omit the major risk rankings, investigation history, anomaly findings, or visualizations contained in the summary.
- Preserve every numeric value exactly as provided.
- Improve only wording, structure, and readability.

Compact Deterministic Report:
----------------------------
{deterministic_report}
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You write precise, technical data audit reports."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        llm_text = response.choices[0].message.content
        if not llm_text:
            return {
                "status": "request_failed",
                "path": "",
                "error": "LLM response was empty.",
            }
    except Exception as exc:
        return {
            "status": "request_failed",
            "path": "",
            "error": f"Groq request failed for model '{model}' at {base_url}. {type(exc).__name__}: {exc}",
        }

    output_path = "outputs/report_llm.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(llm_text)

    return {
        "status": "generated",
        "path": output_path,
        "error": "",
    }

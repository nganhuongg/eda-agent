# report/llm_report_writer.py

import os
from typing import Any, Dict

from openai import OpenAI


def generate_llm_report(state: Dict[str, Any], summary: Dict[str, Any]) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return ""

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )

    deterministic_report = open("outputs/report.md", "r", encoding="utf-8").read()

    prompt = f"""
You are a senior data auditor producing narrative only.

Rewrite the following deterministic technical audit into a professional report.

Rules:
- Do NOT invent, recalculate, round differently, or modify any statistic.
- Do NOT add new numeric claims.
- Do NOT omit risk rankings, investigation history, anomaly findings, or visualizations.
- Preserve every numeric value exactly as provided.
- Improve only wording, structure, and readability.

Deterministic Report:
----------------------
{deterministic_report}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You write precise, technical data audit reports."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        llm_text = response.choices[0].message.content
    except Exception:
        return ""

    output_path = "outputs/report_llm.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(llm_text)

    return output_path

import os
from typing import Any, Dict

import httpx
from openai import OpenAI


def generate_llm_report(state: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, str]:
    api_key = os.getenv("GROQ_API_KEY")
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
            "path": "",
            "error": f"Cannot reach Groq API at {base_url}. {type(exc).__name__}: {exc}",
        }

    client = OpenAI(
        api_key=api_key,
        base_url=base_url
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

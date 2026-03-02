# report/llm_report_writer.py

from typing import Dict, Any
import os
from openai import OpenAI


def generate_llm_report(state: Dict[str, Any], summary: Dict[str, Any]) -> str:

    # Groq-compatible OpenAI client
    client = OpenAI(
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1"
    )

    deterministic_report = open("outputs/report.md", "r", encoding="utf-8").read()

    prompt = f"""
You are a senior data auditor.

Rewrite the following deterministic technical audit into a professional,
well-structured technical report.

Rules:
- Do NOT invent statistics.
- Do NOT change numerical values.
- Base everything strictly on provided content.
- Improve clarity and technical tone.

Deterministic Report:
----------------------
{deterministic_report}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You write precise, technical data audit reports."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
    )

    llm_text = response.choices[0].message.content

    output_path = "outputs/report_llm.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(llm_text)

    return output_path
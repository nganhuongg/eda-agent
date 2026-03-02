# report/report_generator.py

from typing import Dict, Any


def generate_report(state: Dict[str, Any], summary: Dict[str, Any]) -> str:

    lines = []

    lines.append("# Dataset Technical Audit Report\n")

    # -----------------------------
    # 1. Overview
    # -----------------------------
    lines.append("## 1. Dataset Overview\n")
    lines.append(f"- Coverage Ratio: {summary['coverage_ratio']:.2f}")
    lines.append(f"- Columns Analyzed: {summary['columns_analyzed']}/{summary['total_columns']}")
    lines.append("")

    # -----------------------------
    # 2. Data Quality Summary
    # -----------------------------
    lines.append("## 2. Data Quality Summary\n")

    high_missing_columns = []

    for column, insight in state["insights"].items():
        if insight.get("data_quality_flag") == "high_missing":
            high_missing_columns.append(column)

    if high_missing_columns:
        lines.append("- Columns with high missing values:")
        for col in high_missing_columns:
            lines.append(f"  - {col}")
    else:
        lines.append("- No columns with high missing values detected.")

    lines.append("")

    # -----------------------------
    # 3. Numeric Feature Analysis
    # -----------------------------
    lines.append("## 3. Numeric Feature Analysis\n")

    for column, meta in state["dataset_metadata"].items():

        if meta["type"] != "numeric":
            continue

        insight = state["insights"].get(column, {})

        lines.append(f"### {column}")
        lines.append(f"- Variance Level: {insight.get('variance_level')}")
        lines.append(f"- Skewness Direction: {insight.get('skewness_direction')}")
        lines.append(f"- Data Quality: {insight.get('data_quality_flag')}")
        lines.append("")

    # -----------------------------
    # 4. Categorical Feature Analysis
    # -----------------------------
    lines.append("## 4. Categorical Feature Analysis\n")

    for column, meta in state["dataset_metadata"].items():

        if meta["type"] != "categorical":
            continue

        insight = state["insights"].get(column, {})

        lines.append(f"### {column}")
        lines.append(f"- Balance Level: {insight.get('balance_level')}")
        lines.append(f"- Cardinality Level: {insight.get('cardinality_level')}")
        lines.append("")

    # -----------------------------
    # 5. Visual Assets
    # -----------------------------
    lines.append("## 5. Generated Visualizations\n")

    for name, path in state.get("visualizations", {}).items():
        lines.append(f"- {name}: {path}")

    report_text = "\n".join(lines)

    # Save report
    import os
    os.makedirs("outputs", exist_ok=True)

    path = "outputs/report.md"

    with open(path, "w", encoding="utf-8") as f:
        f.write(report_text)

    return path
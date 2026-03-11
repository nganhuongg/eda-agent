from __future__ import annotations

from config import CONFIG
from orchestrator.orchestrator import run_agent
from profiling.profiler import profile_dataset
from report.llm_report_writer import generate_llm_report
from report.report_generator import generate_report
from state.runtime_state import initialize_state
from visualization.plot_generator import generate_insight_driven_plots


if __name__ == "__main__":
    file_path = "data/sample.csv"

    state = initialize_state()
    df, metadata, total_columns = profile_dataset(file_path)
    state["dataset_metadata"] = metadata
    state["total_columns"] = total_columns

    result = run_agent(state=state, df=df, config=CONFIG)
    state["visualizations"] = generate_insight_driven_plots(state, df)

    print("\n=== RUN SUMMARY ===")
    print(result)

    print("\n=== RISK SCORES ===")
    print(state["risk_scores"])

    print("\n=== ANALYSIS RESULTS ===")
    print(state["analysis_results"])

    print("\n=== INSIGHTS ===")
    print(state["insights"])

    print("\n=== VISUALIZATIONS ===")
    print(state["visualizations"])

    report_path = generate_report(state, result)
    print("\n=== REPORT GENERATED ===")
    print(report_path)

    llm_report_result = generate_llm_report(state, result)
    if llm_report_result["status"] == "generated":
        print("\n=== LLM REPORT GENERATED ===")
        print(llm_report_result["path"])
    else:
        print("\n=== LLM REPORT SKIPPED ===")
        print(llm_report_result["error"])

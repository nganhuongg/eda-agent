# main.py

from orchestrator.orchestrator import run_agent
from planning.coverage_planner import coverage_planner
from execution.stat_executor import stat_executor
from profiling.profiler import profile_dataset
from config import CONFIG
from synthesis.global_synthesizer import generate_global_summary
from insight.insight_generator import generate_insights
from visualization.plot_generator import generate_all_plots
from report.report_generator import generate_report
from report.llm_report_writer import generate_llm_report

def initialize_state():

    # temporary empty metadata (will be replaced by profiler)
    state = {
        "dataset_metadata": {},
        "total_columns": 0,
        "columns_analyzed": set(),
        "last_rejection_reason": None,
        "retry_count": 0,

        "current_plan": {},
        "plan_history": [],
        "execution_results": {},
        "insights": {},
        "evaluation": {},
        "score_history": [],
        "logs": []
    }

    return state


if __name__ == "__main__":

    config = {
        "MAX_RETRY": 5
    }

    file_path = "data/sample.csv"   # <-- put your CSV file here

    state = initialize_state()

    df, metadata, total_columns = profile_dataset(file_path)

    state["dataset_metadata"] = metadata
    state["total_columns"] = total_columns

    result = run_agent(
        state=state,
        planner=coverage_planner,
        executor=stat_executor,
        config=CONFIG,
        df=df
    )

    generate_insights(state)
    

    state["visualizations"] = generate_all_plots(state, df)

    print("\n=== RUN SUMMARY ===")
    print(result)

    print("\n=== EXECUTION RESULTS ===")
    print(state["execution_results"])

    if result["coverage_ratio"] >= CONFIG["SYNTHESIS_THRESHOLD"]:
        summary = generate_global_summary(state)
        print("\n=== GLOBAL SUMMARY ===")
        print(summary)
    
    print("\n=== STRUCTURED INSIGHTS ===")
    print(state["insights"])

    print("\n=== GENERATED PLOTS ===")
    print(state["visualizations"])

    report_path = generate_report(state, result)

    print("\n=== REPORT GENERATED ===")
    print(report_path)

    llm_report_path = generate_llm_report(state, result)

    print("\n=== LLM REPORT GENERATED ===")
    print(llm_report_path)
"""
EDA Agent — Streamlit UI

Upload a CSV file and run the risk-driven analysis engine.
Results include risk scores, insights, anomaly findings, and visualizations.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env.local")

from config import CONFIG
from orchestrator.orchestrator import run_agent
from profiling.profiler import profile_dataset
from report.llm_report_writer import generate_llm_report
from report.report_generator import generate_report
from state.runtime_state import initialize_state
from visualization.plot_generator import generate_insight_driven_plots


st.set_page_config(
    page_title="EDA Agent",
    page_icon="🔍",
    layout="wide",
)

st.title("Risk-Driven EDA Agent")
st.caption(
    "Upload a CSV file. The agent investigates it column by column, "
    "prioritizing the highest-risk signals, and delivers ranked insights."
)

uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])

run_button = st.button("Run Analysis", disabled=uploaded_file is None)

if run_button and uploaded_file is not None:
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        with st.status("Running analysis...", expanded=True) as status:
            st.write("Profiling dataset...")
            state = initialize_state()
            df, metadata, total_columns = profile_dataset(tmp_path)
            state["dataset_metadata"] = metadata
            state["total_columns"] = total_columns

            st.write(f"Dataset: {total_columns} columns, {len(df)} rows")

            st.write("Investigating columns by risk...")
            result = run_agent(state=state, df=df, config=CONFIG)

            st.write("Generating visualizations...")
            os.makedirs("outputs/plots", exist_ok=True)
            state["visualizations"] = generate_insight_driven_plots(state, df)

            st.write("Writing report...")
            report_path = generate_report(state, result)

            llm_result = generate_llm_report(state, result)

            status.update(label="Analysis complete", state="complete")

        # --- Results ---

        col1, col2, col3 = st.columns(3)
        col1.metric("Columns analyzed", result.get("columns_analyzed", 0))
        col2.metric("Steps executed", result.get("steps", 0))
        col3.metric("Status", result.get("status", "—"))

        st.divider()

        # Risk scores
        st.subheader("Risk Rankings")
        risk_scores = state.get("risk_scores", {})
        if risk_scores:
            sorted_risks = sorted(risk_scores.items(), key=lambda x: -x[1])
            cols = st.columns(min(4, len(sorted_risks)))
            for i, (col_name, score) in enumerate(sorted_risks[:8]):
                cols[i % 4].metric(col_name, f"{score:.4f}")

        st.divider()

        # Insights + anomalies
        st.subheader("Insights & Anomaly Findings")
        insights = state.get("insights", {})
        if insights:
            for col_name, insight in insights.items():
                anomalies = insight.get("anomaly_findings", [])
                if anomalies:
                    with st.expander(f"**{col_name}** — {len(anomalies)} finding(s)"):
                        for finding in anomalies:
                            st.write(f"- {finding}")
        else:
            st.info("No anomaly findings recorded.")

        st.divider()

        # Visualizations
        plots = state.get("visualizations", {})
        if plots:
            st.subheader("Visualizations")
            plot_items = list(plots.items())
            for i in range(0, len(plot_items), 2):
                cols = st.columns(2)
                for j, (name, path) in enumerate(plot_items[i:i+2]):
                    if Path(path).exists():
                        cols[j].image(path, caption=name, use_container_width=True)

        st.divider()

        # Reports
        st.subheader("Reports")
        report_col1, report_col2 = st.columns(2)

        with report_col1:
            if Path(report_path).exists():
                report_text = Path(report_path).read_text(encoding="utf-8")
                st.download_button(
                    "Download Deterministic Report",
                    data=report_text,
                    file_name="report.md",
                    mime="text/markdown",
                )
                with st.expander("Preview report"):
                    st.markdown(report_text)

        with report_col2:
            if llm_result.get("status") == "generated":
                llm_text = Path(llm_result["path"]).read_text(encoding="utf-8")
                st.download_button(
                    "Download AI Narrative Report",
                    data=llm_text,
                    file_name="report_llm.md",
                    mime="text/markdown",
                )
                with st.expander("Preview AI narrative"):
                    st.markdown(llm_text)
            else:
                st.info(f"AI report skipped: {llm_result.get('error', 'No API key')}")

    finally:
        os.unlink(tmp_path)

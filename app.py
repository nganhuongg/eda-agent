"""
EDA Agent — Streamlit UI

Upload a CSV file and run the risk-driven analysis engine.
Results include risk scores, insights, anomaly findings, and visualizations.
"""

from __future__ import annotations

import re
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
from profiling.temporal_profiler import profile_temporal
from visualization.plot_generator import generate_insight_driven_plots


# ── Visual helpers ────────────────────────────────────────────────────────────

def _render_report_with_images(
    report_text: str,
    visualizations: dict,
    known_columns: list,
) -> None:
    """Render a markdown report with matching images injected after each section.

    Works for both the deterministic report and the LLM narrative report.

    How it works:
    1. Build a lookup: column_name → [(viz_key, file_path)], matching viz filenames
       as column-name prefixes (e.g. "salary_distribution" → column "salary").
    2. Strip any ![](path) markdown image syntax from the text — Streamlit can't
       render local file paths via markdown, so we replace them with st.image() calls.
    3. Split on ## headings so each chunk is one report section.
    4. After rendering each chunk, inject that column's images below it.
    5. Dataset-level plots (e.g. missing heatmap) appear once at the end.
    """
    # Step 1 — map each visualization to its column (longest prefix match wins).
    column_to_images: dict[str, list] = {}
    for viz_key, path in visualizations.items():
        matched_col = None
        for col in known_columns:
            if viz_key == col or viz_key.startswith(col + "_"):
                if matched_col is None or len(col) > len(matched_col):
                    matched_col = col
        if matched_col:
            column_to_images.setdefault(matched_col, []).append((viz_key, path))
        else:
            column_to_images.setdefault("_dataset_", []).append((viz_key, path))

    # Step 2 — split on ## headings (lookahead keeps the heading in each chunk).
    sections = re.split(r"(?=^## )", report_text, flags=re.MULTILINE)

    already_shown: set[str] = set()

    # Step 3 & 4 — render each section, inject matching images below it.
    for section in sections:
        if not section.strip():
            continue

        # Strip markdown image syntax before rendering — broken local paths
        # would show as a missing-image icon; we handle display via st.image() instead.
        clean_section = re.sub(r"!\[.*?\]\(.*?\)", "", section)
        st.markdown(clean_section)

        section_lower = section.lower()
        for col, imgs in column_to_images.items():
            if col == "_dataset_":
                continue
            if col.lower() in section_lower and col not in already_shown:
                already_shown.add(col)
                existing = [(n, p) for n, p in imgs if Path(p).exists()]
                if existing:
                    img_cols = st.columns(min(2, len(existing)))
                    for i, (name, path) in enumerate(existing):
                        img_cols[i % 2].image(
                            path,
                            caption=name.replace("_", " "),
                            use_container_width=True,
                        )

    # Step 5 — dataset-level plots (e.g. missing heatmap) once at the end.
    for name, path in column_to_images.get("_dataset_", []):
        if Path(path).exists():
            st.image(path, caption="Missing Value Heatmap", use_container_width=True)


def risk_color(score: float) -> str:
    """Return a hex color based on risk score: red = high, amber = medium, green = low."""
    if score > 0.7:
        return "#ef4444"
    if score > 0.4:
        return "#f59e0b"
    return "#10b981"


def risk_label(score: float) -> str:
    """Return a human-readable risk tier label."""
    if score > 0.7:
        return "HIGH"
    if score > 0.4:
        return "MEDIUM"
    return "LOW"


# ── Global CSS ────────────────────────────────────────────────────────────────
# Injected once at page load. Streamlit renders raw HTML/CSS via st.markdown.

CUSTOM_CSS = """
<style>
/* Tighten top padding so the hero header feels intentional */
.main .block-container {
    padding-top: 1.5rem;
}

/* Metric cards — lift them off the page with a subtle shadow */
[data-testid="metric-container"] {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

/* Primary action button (Run Analysis) */
.stButton > button {
    background-color: #2563eb;
    color: white;
    border-radius: 8px;
    border: none;
    font-weight: 600;
    font-size: 1rem;
    padding: 0.55rem 1.5rem;
    transition: background 0.15s ease;
}
.stButton > button:hover { background-color: #1d4ed8; }
.stButton > button:disabled {
    background-color: #cbd5e1;
    color: #94a3b8;
}

/* Download buttons — secondary blue style */
.stDownloadButton > button {
    background-color: #eff6ff;
    color: #1d4ed8;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    font-weight: 500;
}
.stDownloadButton > button:hover {
    background-color: #dbeafe;
}

/* Tab bar — bolder active tab */
.stTabs [data-baseweb="tab"] {
    font-size: 0.95rem;
    font-weight: 500;
}

/* Rounded corners on info/warning callouts */
.stAlert { border-radius: 8px; }
</style>
"""


# ── Page setup ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="EDA Agent",
    page_icon="🔍",
    layout="wide",
)

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ── Hero header ───────────────────────────────────────────────────────────────
# Centered title + subtitle gives the page a landing-page feel instead of
# the default left-aligned Streamlit title.

st.markdown("""
<div style="text-align:center; padding: 1.5rem 0 1rem;">
    <h1 style="font-size:2.4rem; font-weight:700; color:#1e293b; margin-bottom:0.4rem;">
        Risk-Driven EDA Agent
    </h1>
    <p style="color:#64748b; font-size:1.05rem; max-width:600px; margin:0 auto;">
        Upload a CSV file. The agent investigates it column by column,
        prioritizing the highest-risk signals, and delivers ranked insights.
    </p>
</div>
""", unsafe_allow_html=True)

st.write("")  # small spacer


# ── Upload card ───────────────────────────────────────────────────────────────
# st.container(border=True) draws a rounded card outline around the upload area.

with st.container(border=True):
    uploaded_file = st.file_uploader(
        "Upload a CSV file",
        type=["csv"],
        help="The agent will profile every column and rank them by anomaly risk.",
    )
    run_button = st.button(
        "Run Analysis",
        disabled=uploaded_file is None,
        use_container_width=True,
    )


# ── Analysis ──────────────────────────────────────────────────────────────────

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
            state["temporal_signals"] = profile_temporal(df, metadata)

            st.write(f"Dataset: {total_columns} columns, {len(df)} rows")

            st.write("Investigating columns by risk...")
            result = run_agent(state=state, df=df, config=CONFIG)

            st.write("Generating visualizations...")
            state["visualizations"] = generate_insight_driven_plots(state, df)

            st.write("Writing report...")
            report_path = generate_report(state, result)
            llm_result = generate_llm_report(state, result)

            status.update(label="Analysis complete", state="complete")

        # ── Summary bar ───────────────────────────────────────────────────────

        st.subheader("Summary")
        col1, col2, col3 = st.columns(3)
        col1.metric("Columns analyzed", result.get("columns_analyzed", 0))
        col2.metric("Steps executed", result.get("steps", 0))
        col3.metric("Status", result.get("status", "—"))

        st.divider()

        # ── Risk rankings ─────────────────────────────────────────────────────
        # Each column gets a color-coded card: red > 0.7, amber > 0.4, green otherwise.
        # Using raw HTML here because Streamlit's st.metric doesn't support custom colors.

        st.subheader("Risk Rankings")
        risk_scores = state.get("risk_scores", {})
        if risk_scores:
            sorted_risks = sorted(risk_scores.items(), key=lambda x: -x[1])
            cols = st.columns(min(4, len(sorted_risks)))
            for i, (col_name, score) in enumerate(sorted_risks[:8]):
                color = risk_color(score)
                label = risk_label(score)
                cols[i % 4].markdown(f"""
<div style="background:#f8fafc; border-left:4px solid {color}; border-radius:8px;
            padding:0.8rem 1rem; margin-bottom:0.5rem;">
    <div style="font-size:0.75rem; color:#64748b; font-weight:600;
                text-transform:uppercase; letter-spacing:0.05em;">{col_name}</div>
    <div style="font-size:1.6rem; font-weight:700; color:{color}; line-height:1.2;">{score:.4f}</div>
    <div style="font-size:0.72rem; font-weight:600; color:{color};">{label}</div>
</div>""", unsafe_allow_html=True)
        else:
            st.info("No risk scores recorded.")

        st.divider()

        # ── Reports ───────────────────────────────────────────────────────────

        st.subheader("Reports")
        tab1, tab2 = st.tabs(["Deterministic Report", "AI Narrative Report"])

        with tab1:
            if Path(report_path).exists():
                report_text = Path(report_path).read_text(encoding="utf-8")
                st.download_button(
                    "Download Deterministic Report",
                    data=report_text,
                    file_name="report.md",
                    mime="text/markdown",
                )
                _render_report_with_images(
                    report_text=report_text,
                    visualizations=state.get("visualizations", {}),
                    known_columns=list(state.get("risk_scores", {}).keys()),
                )

        with tab2:
            if llm_result.get("status") == "generated":
                llm_text = Path(llm_result["path"]).read_text(encoding="utf-8")
                st.download_button(
                    "Download AI Narrative Report",
                    data=llm_text,
                    file_name="report_llm.md",
                    mime="text/markdown",
                )
                _render_report_with_images(
                    report_text=llm_text,
                    visualizations=state.get("visualizations", {}),
                    known_columns=list(state.get("risk_scores", {}).keys()),
                )
            else:
                st.info(f"AI report skipped: {llm_result.get('error', 'No API key')}")

        

    finally:
        Path(tmp_path).unlink()

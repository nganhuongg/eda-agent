from __future__ import annotations

# orchestrator/orchestrator.py
#
# This is the brain of the agent — the file that connects every other module
# together and runs the main investigation loop.
#
# High-level flow:
#   for each column (highest-risk first):
#       1. Run deterministic analysis tools on the real data
#       2. Ask the LLM to interpret the signals (Gate 1 loop)
#       3. The Critic checks every numeric claim the LLM made
#       4. If claims are wrong, tell the LLM what failed and try again (up to 5x)
#       5. Store the result and move to the next column

import logging
from functools import partial
from typing import Any, Dict

import pandas as pd

from agents.llm_analyst import analyze_column
from agents.schemas import AnalystDecision
from execution.analysis_tools import (
    analyze_correlation,
    analyze_distribution,
    analyze_missing_pattern,
    detect_outliers,
)
from insight.critic import CriticVerdict, validate_finding
from orchestrator.ralph_loop import run_loop
from planning.risk_planner import compute_risk_scores, risk_driven_planner
from profiling.signal_extractor import extract_signals
from state.runtime_state import AgentState


# Maps the string names the LLM uses in recommended_tools to the actual Python
# functions. This lets the LLM say "analyze_distribution" in its JSON response
# and the orchestrator knows which function to call.
ACTION_TO_TOOL = {
    "analyze_distribution": analyze_distribution,
    "detect_outliers": detect_outliers,
    "analyze_missing_pattern": analyze_missing_pattern,
    "analyze_correlation": analyze_correlation,
}


def _record_action(
    state: Dict[str, Any],
    step: int,
    phase: str,
    plan: Dict[str, Any] | None,
    status: str,
    details: Dict[str, Any] | None = None,
) -> None:
    """Append one entry to state['action_history'] — the agent's audit trail.

    Every meaningful action the agent takes (running a tool, completing a loop,
    recording a verdict) gets logged here. This is how you can trace what the
    agent did, in order, after the run completes.

    'phase' describes what kind of step this is (e.g. 'tools_run', 'gate1_result').
    'details' holds any extra data worth recording for that step.
    """
    entry = {
        "step": step,
        "phase": phase,
        "status": status,
        "details": details or {},
    }
    if plan:
        # Copy the plan's key fields directly into the log entry so each record
        # is self-contained — no need to cross-reference the plan dict later.
        entry.update(
            {
                "column": plan.get("column"),
                "action": plan.get("action"),
                "source": plan.get("source"),
                "reason": plan.get("reason"),
                "priority": float(plan.get("priority", 0.0)),
            }
        )
    state["action_history"].append(entry)


def _make_gate1_critic(state: AgentState, column: str):
    """Build the critic function used inside Gate 1 (the per-column Ralph Loop).

    run_loop() expects a critic_fn with the signature: fn(result) -> CriticVerdict.
    But validate_finding() needs signals and analysis_results too.

    This function returns a closure — a small function that already has 'state'
    and 'column' baked in, so run_loop can call it with just the LLM decision.

    Think of a closure like a pre-filled form: the blanks for state and column
    are already filled in; the caller only needs to supply the decision.
    """
    def critic_fn(decision: AnalystDecision) -> CriticVerdict:
        # Extract only what the Critic needs: the column name and the list of
        # numeric claims the LLM made. The Critic checks each claim against
        # the pre-computed signals and analysis_results.
        finding = {"column": decision.column, "claims": decision.claims}
        return validate_finding(finding, state["signals"], state["analysis_results"])
    return critic_fn


def _run_tools_for_column(
    state: Dict[str, Any],
    df: pd.DataFrame,
    column: str,
    column_type: str,
    step: int,
) -> None:
    """Run deterministic analysis tools on the real DataFrame for one column.

    IMPORTANT: df (the actual data) is used HERE and NOWHERE else in the agent.
    This is a deliberate architectural boundary. By confining all raw data access
    to this one function, we guarantee the LLM never sees individual row values —
    only the computed summaries this function stores in state['analysis_results'].

    Why run tools before the LLM?
    The LLM needs something concrete to reason about. We compute first, then ask
    the LLM to interpret the results. This is the 'deterministic first, AI second'
    principle that runs through the whole system.

    Tool selection by column type:
    - Numeric columns get distribution stats + outlier detection.
    - Categorical/other columns get missing pattern analysis + outlier detection.
    """
    state["analysis_results"].setdefault(column, {})

    if column_type == "numeric":
        state["analysis_results"][column]["analyze_distribution"] = analyze_distribution(
            df, column, column_type
        )
        state["analysis_results"][column]["detect_outliers"] = detect_outliers(df, column)
    else:
        state["analysis_results"][column]["analyze_missing_pattern"] = analyze_missing_pattern(
            df, column
        )
        state["analysis_results"][column]["detect_outliers"] = detect_outliers(df, column)

    _record_action(state, step, "tools_run", {"column": column}, "completed",
                   {"tools_run": list(state["analysis_results"][column].keys())})


def run_agent(state: Dict[str, Any], df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full agent investigation loop and return a summary dict.

    This is the main entry point called by main.py. It loops over columns,
    from highest-risk to lowest, and for each column:
      - Runs deterministic tools to produce signals and analysis results
      - Runs Gate 1: LLM generates an insight, Critic validates it
      - Stores the final AnalystDecision in state for the report to use

    Args:
        state:  The shared AgentState dict. All modules read and write to this.
        df:     The loaded DataFrame. Only used inside _run_tools_for_column.
        config: Settings dict. Must contain MAX_COLUMNS (or falls back to all columns).

    Returns a dict with:
        status:           'SUCCESS' (all columns done) or 'PARTIAL' (hit MAX_COLUMNS)
        reason:           Why we stopped
        columns_analyzed: How many columns were completed
        total_columns:    Total columns in the dataset
    """
    # MAX_COLUMNS caps how many columns the agent will investigate in one run.
    # This prevents infinite loops on wide datasets and controls API cost.
    max_columns = int(config.get("MAX_COLUMNS", len(df.columns)))

    for _col_idx in range(max_columns):

        # --- Step 1: Refresh signals and risk scores ---
        # Risk scores are relative (they depend on max variance across all columns).
        # As columns get analyzed and state changes, a full refresh ensures the
        # planner always works from accurate, up-to-date priorities.
        state["signals"] = extract_signals(df, state["dataset_metadata"])
        state["risk_scores"] = compute_risk_scores(state["dataset_metadata"], state["signals"])

        # --- Step 2: Ask the planner which column to investigate next ---
        # risk_driven_planner looks at risk_scores and analyzed_columns and returns
        # the highest-risk column not yet analyzed. Returns None when all done.
        plan = risk_driven_planner(state)
        if plan is None:
            # All columns have been analyzed — clean exit.
            return {
                "status": "SUCCESS",
                "reason": "NO_PENDING_INVESTIGATIONS",
                "columns_analyzed": len(state["analyzed_columns"]),
                "total_columns": len(state["dataset_metadata"]),
            }

        column = plan["column"]
        column_type = state["dataset_metadata"][column]["type"]

        # --- Step 3: Run deterministic tools on the real data ---
        # df is passed here and NOWHERE else. See _run_tools_for_column docstring.
        _run_tools_for_column(state, df, column, column_type, _col_idx)

        # --- Step 4: Gate 1 — LLM + Critic loop ---
        #
        # partial() pre-fills the first two arguments of analyze_column (state, column)
        # so run_loop can call it as generator_fn(rejected_claims) without needing
        # to know about state or column.
        #
        # run_loop will:
        #   - Call generator_fn(rejected_claims) to get an AnalystDecision from the LLM
        #   - Call critic_fn(decision) to validate the LLM's numeric claims
        #   - If approved: return the decision immediately
        #   - If rejected: pass the rejected claim names back to the LLM and retry
        #   - After 5 failed attempts: return the best available decision anyway
        generator_fn = partial(analyze_column, state, column)
        critic_fn = _make_gate1_critic(state, column)
        decision: AnalystDecision = run_loop(generator_fn, critic_fn, max_iter=5)

        _record_action(state, _col_idx, "analyst_loop", plan, "completed",
                       {"column": column})

        # --- Step 5: Log a warning if Gate 1 never achieved approval ---
        # We check the final verdict one more time here (outside the loop) so we
        # can warn in the logs. The decision still gets stored — we never discard
        # the result, even if the Critic never fully approved it.
        final_verdict = critic_fn(decision)
        if not final_verdict.approved:
            logging.warning(
                "Gate 1 exhausted for column '%s' after 5 iterations — using best attempt",
                column,
            )

        _record_action(state, _col_idx, "gate1_result", plan, "completed",
                       {"approved": final_verdict.approved, "column": column})

        # --- Step 6: Store the result ---
        # state['analyst_decisions'] is the primary store — used by the synthesizer
        # and report generator to build the final ranked findings.
        state["analyst_decisions"][column] = decision

        # state['insights'] is a simpler copy of the same data in a flat dict format.
        # The report generator was written expecting this shape, so we maintain it
        # here for compatibility rather than rewriting the report generator.
        state["insights"][column] = {
            "summary": decision.narrative,
            "category": decision.business_label,
            "column": decision.column,
            "hypothesis": decision.hypothesis,
            "recommended_tools": decision.recommended_tools,
        }

        # Mark column as done so the planner skips it next iteration.
        state["analyzed_columns"].add(column)

    # We reached max_columns without finishing all columns.
    # This is expected on large datasets — not an error.
    return {
        "status": "PARTIAL",
        "reason": "MAX_COLUMNS_REACHED",
        "columns_analyzed": len(state["analyzed_columns"]),
        "total_columns": len(state["dataset_metadata"]),
    }

from __future__ import annotations

import pytest


# ── Lazy import helpers ────────────────────────────────────────────────────────

def _get_run_agent():
    from orchestrator.orchestrator import run_agent  # noqa: PLC0415
    return run_agent


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_minimal_state():
    from state.runtime_state import initialize_state  # noqa: PLC0415
    import pandas as pd
    state = initialize_state()
    state["dataset_metadata"] = {
        "revenue": {"type": "numeric"},
        "category": {"type": "categorical"},
    }
    state["signals"] = {
        "revenue": {"missing_ratio": 0.0, "skewness": 0.5, "outlier_ratio": 0.05, "variance": 100.0},
        "category": {"entropy": 1.2, "dominant_ratio": 0.6, "unique_count": 3, "missing_ratio": 0.0},
    }
    state["risk_scores"] = {"revenue": 0.9, "category": 0.3}
    state["analysis_results"] = {}
    return state


def _make_minimal_df():
    import pandas as pd  # noqa: PLC0415
    return pd.DataFrame({"revenue": [100, 200, 300], "category": ["A", "B", "A"]})


def _make_config():
    return {"MAX_COLUMNS": 2}


# ── D-07: df boundary smoke test ──────────────────────────────────────────────

def test_run_agent_df_boundary():
    """No agent module receives a pd.DataFrame (D-07, Phase 5 success criterion 2)."""
    raise NotImplementedError("RED — implement in Plan 05-02")


# ── D-06: Exhaustion logging ──────────────────────────────────────────────────

def test_run_agent_exhaustion_logging():
    """Gate 1 exhaustion triggers logging.warning with column name (D-06)."""
    raise NotImplementedError("RED — implement in Plan 05-02")


# ── Integration smoke test ────────────────────────────────────────────────────

def test_run_agent_integration_smoke():
    """run_agent populates state['analyst_decisions'] and state['insights'] (D-03, D-04)."""
    raise NotImplementedError("RED — implement in Plan 05-02")

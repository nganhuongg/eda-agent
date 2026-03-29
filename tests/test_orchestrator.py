from __future__ import annotations

import logging
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
from agents.schemas import AnalystDecision, CriticVerdict


# ── Lazy import helpers ────────────────────────────────────────────────────────

def _get_run_agent():
    from orchestrator.orchestrator import run_agent  # noqa: PLC0415
    return run_agent


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_minimal_state():
    from state.runtime_state import initialize_state  # noqa: PLC0415
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
    run_agent = _get_run_agent()
    state = _make_minimal_state()
    df = _make_minimal_df()
    config = _make_config()

    df_leak_detected = []

    def spy_analyze_column(s, col, rejected_claims=None):
        # Inspect all arguments for DataFrame — should never find one
        for arg in [s, col, rejected_claims]:
            if isinstance(arg, pd.DataFrame):
                df_leak_detected.append(f"arg: {type(arg)}")
        return AnalystDecision(
            column=col,
            hypothesis="test",
            recommended_tools=["analyze_distribution"],
            business_label="risk",
            narrative="test narrative",
            claims=[],
        )

    # Stub to return exactly one column plan then None (single column pass)
    plan_calls = [0]
    def stub_planner(st):
        if plan_calls[0] == 0:
            plan_calls[0] += 1
            return {"column": "revenue", "action": "analyze_distribution",
                    "source": "test", "reason": "high risk", "priority": 0.9}
        return None

    with patch("orchestrator.orchestrator.analyze_column", side_effect=spy_analyze_column), \
         patch("orchestrator.orchestrator.risk_driven_planner", side_effect=stub_planner), \
         patch("orchestrator.orchestrator.extract_signals", return_value=state["signals"]), \
         patch("orchestrator.orchestrator.compute_risk_scores", return_value=state["risk_scores"]), \
         patch("orchestrator.orchestrator._run_tools_for_column"):
        run_agent(state, df, config)

    assert plan_calls[0] >= 1, "analyze_column was never called — test is vacuous"
    assert df_leak_detected == [], f"DataFrame leaked into analyze_column: {df_leak_detected}"


# ── D-06: Exhaustion logging ──────────────────────────────────────────────────

def test_run_agent_exhaustion_logging():
    """Gate 1 exhaustion triggers logging.warning with column name (D-06)."""
    run_agent = _get_run_agent()
    state = _make_minimal_state()
    df = _make_minimal_df()
    config = _make_config()

    exhausted_decision = AnalystDecision(
        column="revenue",
        hypothesis="test",
        recommended_tools=["analyze_distribution"],
        business_label="risk",
        narrative="test narrative",
        claims=[{"field": "nonexistent_field", "value": 999.0}],  # will not approve
    )

    plan_calls = [0]
    def stub_planner(st):
        if plan_calls[0] == 0:
            plan_calls[0] += 1
            return {"column": "revenue", "action": "analyze_distribution",
                    "source": "test", "reason": "high risk", "priority": 0.9}
        return None

    with patch("orchestrator.orchestrator.run_loop", return_value=exhausted_decision), \
         patch("orchestrator.orchestrator.risk_driven_planner", side_effect=stub_planner), \
         patch("orchestrator.orchestrator.extract_signals", return_value=state["signals"]), \
         patch("orchestrator.orchestrator.compute_risk_scores", return_value=state["risk_scores"]), \
         patch("orchestrator.orchestrator._run_tools_for_column"), \
         patch("orchestrator.orchestrator.logging") as mock_log:
        run_agent(state, df, config)

    # Assert logging.warning was called with the exhaustion message
    warning_calls = mock_log.warning.call_args_list
    assert any(
        "Gate 1 exhausted" in str(call) and "revenue" in str(call)
        for call in warning_calls
    ), f"Expected 'Gate 1 exhausted' warning for 'revenue', got: {warning_calls}"


# ── Integration smoke test ────────────────────────────────────────────────────

def test_run_agent_integration_smoke():
    """run_agent populates state['analyst_decisions'] and state['insights'] (D-03, D-04)."""
    run_agent = _get_run_agent()
    state = _make_minimal_state()
    df = _make_minimal_df()
    config = _make_config()

    approved_decision = AnalystDecision(
        column="revenue",
        hypothesis="Revenue shows high outlier ratio — risk of data quality issues",
        recommended_tools=["analyze_distribution", "detect_outliers"],
        business_label="risk",
        narrative="Revenue column has significant outliers that may indicate data entry errors.",
        claims=[],
    )

    plan_calls = [0]
    def stub_planner(st):
        if plan_calls[0] == 0:
            plan_calls[0] += 1
            return {"column": "revenue", "action": "analyze_distribution",
                    "source": "test", "reason": "high risk", "priority": 0.9}
        return None

    with patch("orchestrator.orchestrator.run_loop", return_value=approved_decision), \
         patch("orchestrator.orchestrator.risk_driven_planner", side_effect=stub_planner), \
         patch("orchestrator.orchestrator.extract_signals", return_value=state["signals"]), \
         patch("orchestrator.orchestrator.compute_risk_scores", return_value=state["risk_scores"]), \
         patch("orchestrator.orchestrator._run_tools_for_column"):
        result = run_agent(state, df, config)

    # D-03: AnalystDecision stored
    assert "revenue" in state["analyst_decisions"], "analyst_decisions missing 'revenue'"
    assert isinstance(state["analyst_decisions"]["revenue"], AnalystDecision)

    # D-04: state['insights'] populated with backward-compat shape
    assert "revenue" in state["insights"], "insights missing 'revenue'"
    insight = state["insights"]["revenue"]
    for key in ("summary", "category", "column", "hypothesis", "recommended_tools"):
        assert key in insight, f"insights['revenue'] missing key '{key}'"

    # D-09: return dict shape
    assert result["columns_analyzed"] >= 1
    assert "total_columns" in result
    assert result["status"] in ("SUCCESS", "PARTIAL")

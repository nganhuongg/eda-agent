from __future__ import annotations

from state.runtime_state import initialize_state


def test_temporal_signals_field():
    state = initialize_state()
    assert "temporal_signals" in state
    assert state["temporal_signals"] == {}


def test_v2_fields_unbroken():
    state = initialize_state()
    assert "signals" in state
    assert "risk_scores" in state
    assert "dataset_metadata" in state
    assert "analysis_results" in state
    assert "insights" in state

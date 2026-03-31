from __future__ import annotations
import pytest
from agents.schemas import AnalystDecision
from state.runtime_state import initialize_state
from unittest.mock import patch, MagicMock


def _get_build_findings_list():
    from synthesis.global_synthesizer import _build_findings_list
    return _build_findings_list


def _get_generate_report():
    from report.report_generator import generate_report
    return generate_report


def _make_minimal_state():
    state = initialize_state()
    state["risk_scores"] = {"revenue": 0.9, "category": 0.3}
    state["analyst_decisions"] = {
        "revenue": AnalystDecision(
            column="revenue", hypothesis="Revenue has outliers",
            recommended_tools=["analyze_distribution", "detect_outliers"],
            business_label="risk",
            narrative="Revenue shows right-skewed outliers above 95th percentile.",
            claims=[],
        )
    }
    state["analysis_results"] = {
        "revenue": {"analyze_distribution": {}, "detect_outliers": {}}
    }
    state["signals"] = {"revenue": {"mean": 50.0, "std": 10.0}}
    state["temporal_signals"] = {}
    state["visualizations"] = {}
    state["dataset_metadata"] = {
        "revenue": {"type": "numeric"}, "category": {"type": "categorical"}
    }
    state["total_columns"] = 2
    return state


_SUMMARY = {"status": "DONE", "reason": "complete", "steps": 5,
            "columns_analyzed": 1, "total_columns": 2}


def test_findings_list_ranked():
    """_build_findings_list returns findings sorted descending by risk_score (SYNTH-02, RPT-01)."""
    _build_findings_list = _get_build_findings_list()
    state = _make_minimal_state()
    result = _build_findings_list(state)
    assert "findings" in result
    assert len(result["findings"]) == 1
    assert result["findings"][0]["column"] == "revenue"
    assert result["findings"][0]["score"] == 0.9


def test_single_angle_note():
    """Column with 1 tool result gets single_angle=True flag (SYNTH-01)."""
    _build_findings_list = _get_build_findings_list()
    state = _make_minimal_state()
    state["analysis_results"] = {"revenue": {"analyze_distribution": {}}}  # 1 tool only
    result = _build_findings_list(state)
    assert result["findings"][0].get("single_angle") is True


def test_below_threshold_note():
    """Column with 0 tool results is excluded from Gate 2 findings (SYNTH-01, D-06)."""
    _build_findings_list = _get_build_findings_list()
    state = _make_minimal_state()
    state["analysis_results"] = {"revenue": {}}  # 0 tools
    result = _build_findings_list(state)
    columns_in_findings = [f["column"] for f in result["findings"]]
    assert "revenue" not in columns_in_findings


def test_gate2_called():
    """generate_report calls run_loop with quality_bar_critic as critic_fn (SYNTH-02, D-08)."""
    generate_report = _get_generate_report()
    state = _make_minimal_state()
    from orchestrator.ralph_loop import quality_bar_critic
    with patch("report.report_generator.run_loop") as mock_run_loop:
        mock_run_loop.return_value = {"findings": [], "signals": {}, "analysis_results": {}}
        generate_report(state, _SUMMARY)
        assert mock_run_loop.called
        call_kwargs = mock_run_loop.call_args
        # critic_fn must be quality_bar_critic
        assert call_kwargs[1].get("critic_fn") is quality_bar_critic or \
               (len(call_kwargs[0]) >= 2 and call_kwargs[0][1] is quality_bar_critic)

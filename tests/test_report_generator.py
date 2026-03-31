from __future__ import annotations
import os
import pytest
from agents.schemas import AnalystDecision
from state.runtime_state import initialize_state
from unittest.mock import patch


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
        ),
        "category": AnalystDecision(
            column="category", hypothesis="Category skew",
            recommended_tools=["analyze_distribution"],
            business_label="opportunity",
            narrative="Category distribution shows opportunity.",
            claims=[],
        ),
    }
    state["analysis_results"] = {
        "revenue": {"analyze_distribution": {}, "detect_outliers": {}},
        "category": {"analyze_distribution": {}},
    }
    state["signals"] = {"revenue": {"mean": 50.0}, "category": {"cardinality": 5}}
    state["temporal_signals"] = {}
    state["visualizations"] = {}
    state["dataset_metadata"] = {
        "revenue": {"type": "numeric"}, "category": {"type": "categorical"}
    }
    state["total_columns"] = 2
    return state


_SUMMARY = {"status": "DONE", "reason": "complete", "steps": 5,
            "columns_analyzed": 2, "total_columns": 2}


def test_ranked_order_in_report(tmp_path, monkeypatch):
    """Report lists revenue (score 0.9) before category (score 0.3) (RPT-01)."""
    generate_report = _get_generate_report()
    monkeypatch.chdir(tmp_path)
    state = _make_minimal_state()
    path = generate_report(state, _SUMMARY)
    text = open(path, encoding="utf-8").read()
    assert text.index("revenue") < text.index("category")


def test_business_label_present(tmp_path, monkeypatch):
    """Every analyzed column section shows its business_label (RPT-02)."""
    generate_report = _get_generate_report()
    monkeypatch.chdir(tmp_path)
    state = _make_minimal_state()
    path = generate_report(state, _SUMMARY)
    text = open(path, encoding="utf-8").read()
    assert "**Business label:** risk" in text
    assert "**Business label:** opportunity" in text


def test_temporal_section_present(tmp_path, monkeypatch):
    """Temporal section appears when temporal_signals is non-empty (RPT-03)."""
    generate_report = _get_generate_report()
    monkeypatch.chdir(tmp_path)
    state = _make_minimal_state()
    state["temporal_signals"] = {"revenue": {"direction": "up", "confidence": 0.87}}
    path = generate_report(state, _SUMMARY)
    text = open(path, encoding="utf-8").read()
    assert "## Temporal Analysis" in text


def test_no_temporal_section(tmp_path, monkeypatch):
    """No Temporal Analysis section when temporal_signals is empty (RPT-03 negative)."""
    generate_report = _get_generate_report()
    monkeypatch.chdir(tmp_path)
    state = _make_minimal_state()
    state["temporal_signals"] = {}
    path = generate_report(state, _SUMMARY)
    text = open(path, encoding="utf-8").read()
    assert "## Temporal Analysis" not in text


def test_output_file_written(tmp_path, monkeypatch):
    """generate_report writes outputs/report.md and returns that path (RPT-04)."""
    generate_report = _get_generate_report()
    monkeypatch.chdir(tmp_path)
    state = _make_minimal_state()
    path = generate_report(state, _SUMMARY)
    assert path == "outputs/report.md"
    assert os.path.isfile(path)

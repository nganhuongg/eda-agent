from __future__ import annotations

import pytest
import openai
from unittest.mock import patch, MagicMock

_SENTINEL = "SHOULD_NOT_APPEAR_IN_CONTEXT"

_VALID_TOOLS = {
    "analyze_distribution",
    "detect_outliers",
    "analyze_missing_pattern",
    "analyze_correlation",
}


def _get_analyze_column():
    from agents.llm_analyst import analyze_column
    return analyze_column


def _get_build_analyst_context():
    from agents.llm_analyst import build_analyst_context
    return build_analyst_context


def _make_minimal_state():
    from state.runtime_state import initialize_state
    state = initialize_state()
    state["signals"] = {
        "revenue": {
            "missing_ratio": 0.05,
            "skewness": 2.3,
            "outlier_ratio": 0.08,
            "variance": 150.0,
        }
    }
    state["dataset_metadata"] = {"revenue": {"type": "numeric"}}
    state["risk_scores"] = {"revenue": 0.42}
    state["analyzed_columns"] = set()
    return state


# ── ANLST-01: analyze_column returns AnalystDecision ─────────────────────────

def test_analyze_column_returns_analyst_decision(monkeypatch):
    """analyze_column returns AnalystDecision instance (ANLST-01)."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    analyze_column = _get_analyze_column()
    result = analyze_column(_make_minimal_state(), "revenue", rejected_claims=[])
    from agents.schemas import AnalystDecision
    assert isinstance(result, AnalystDecision)
    assert result.column == "revenue"


# ── ANLST-02: hypothesis is non-empty ─────────────────────────────────────────

def test_analyst_decision_hypothesis_non_empty(monkeypatch):
    """hypothesis is a non-empty string (ANLST-02)."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    analyze_column = _get_analyze_column()
    result = analyze_column(_make_minimal_state(), "revenue", rejected_claims=[])
    assert isinstance(result.hypothesis, str)
    assert len(result.hypothesis) > 0


# ── ANLST-03: recommended_tools values are valid ──────────────────────────────

def test_recommended_tools_valid(monkeypatch):
    """recommended_tools contains only valid ACTION_TO_TOOL keys (ANLST-03)."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    analyze_column = _get_analyze_column()
    result = analyze_column(_make_minimal_state(), "revenue", rejected_claims=[])
    assert len(result.recommended_tools) > 0
    assert all(t in _VALID_TOOLS for t in result.recommended_tools)


# ── ANLST-04: business_label is valid ─────────────────────────────────────────

def test_business_label_valid(monkeypatch):
    """business_label is one of the four allowed values (ANLST-04)."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    analyze_column = _get_analyze_column()
    result = analyze_column(_make_minimal_state(), "revenue", rejected_claims=[])
    assert result.business_label in {"risk", "opportunity", "anomaly", "trend"}


# ── ANLST-05: narrative is non-empty ──────────────────────────────────────────

def test_narrative_non_empty(monkeypatch):
    """narrative is a non-empty plain-text string (ANLST-05)."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    analyze_column = _get_analyze_column()
    result = analyze_column(_make_minimal_state(), "revenue", rejected_claims=[])
    assert isinstance(result.narrative, str)
    assert len(result.narrative) > 0


# ── ANLST-06 / D-10: build_analyst_context contains no df reference ───────────

def test_build_analyst_context_contains_no_df_reference():
    import json
    build_analyst_context = _get_build_analyst_context()
    state = _make_minimal_state()
    ctx = build_analyst_context(state, "revenue")
    ctx_str = json.dumps(ctx, default=str)
    assert _SENTINEL not in ctx_str
    assert "DataFrame" not in ctx_str
    assert isinstance(ctx["signals"]["missing_ratio"], float)
    assert isinstance(ctx["signals"]["skewness"], float)


# ── D-09: build_analyst_context extracts correct numeric fields ───────────────

def test_build_analyst_context_fields_numeric():
    build_analyst_context = _get_build_analyst_context()
    state = _make_minimal_state()
    ctx = build_analyst_context(state, "revenue")
    assert ctx["column"] == "revenue"
    assert ctx["column_type"] == "numeric"
    assert "missing_ratio" in ctx["signals"]
    assert "skewness" in ctx["signals"]
    assert "outlier_ratio" in ctx["signals"]
    assert "variance" in ctx["signals"]
    assert ctx["risk_score"] == 0.42
    assert isinstance(ctx["analyzed_columns"], list)


# ── D-04: malformed JSON triggers fallback ────────────────────────────────────

def test_malformed_json_triggers_fallback(monkeypatch):
    """Malformed JSON response triggers fallback, not exception (D-04)."""
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    analyze_column = _get_analyze_column()
    with patch("agents.llm_analyst._call_minimax", return_value='{"invalid": true}'):
        result = analyze_column(_make_minimal_state(), "revenue")
    from agents.schemas import AnalystDecision
    assert isinstance(result, AnalystDecision)
    assert result.claims == []


# ── D-06: missing API key triggers fallback immediately ───────────────────────

def test_missing_api_key_triggers_fallback(monkeypatch):
    """Missing MINIMAX_API_KEY triggers deterministic fallback (D-06)."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    analyze_column = _get_analyze_column()
    result = analyze_column(_make_minimal_state(), "revenue", rejected_claims=[])
    from agents.schemas import AnalystDecision
    assert isinstance(result, AnalystDecision)
    assert result.column == "revenue"
    assert result.claims == []


# ── D-07: fallback returns valid AnalystDecision with claims=[] ───────────────

def test_fallback_returns_analyst_decision(monkeypatch):
    """Deterministic fallback returns valid AnalystDecision with claims=[] (D-07)."""
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    analyze_column = _get_analyze_column()
    result = analyze_column(_make_minimal_state(), "revenue", rejected_claims=[])
    from agents.schemas import AnalystDecision
    assert isinstance(result, AnalystDecision)
    assert len(result.hypothesis) > 0
    assert result.claims == []
    assert result.business_label in {"risk", "opportunity", "anomaly", "trend"}


# ── D-08: RateLimitError retries 3 times then falls back ──────────────────────

def test_rate_limit_retries_then_fallback(monkeypatch):
    """RateLimitError triggers 3 retry attempts then deterministic fallback (D-08)."""
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    analyze_column = _get_analyze_column()
    call_count = {"n": 0}

    def mock_create(**kwargs):
        call_count["n"] += 1
        raise openai.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body={},
        )

    with patch("agents.llm_analyst.OpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create.side_effect = mock_create
        result = analyze_column(_make_minimal_state(), "revenue")

    assert call_count["n"] == 3
    from agents.schemas import AnalystDecision
    assert isinstance(result, AnalystDecision)
    assert result.claims == []


# ── CRIT-04 regression: AnalystDecision survives JSON round-trip ──────────────

def test_analyst_decision_json_roundtrip():
    from agents.schemas import AnalystDecision
    decision = AnalystDecision(
        column="revenue",
        hypothesis="Revenue distribution is right-skewed due to outliers",
        recommended_tools=["analyze_distribution", "detect_outliers"],
        business_label="risk",
        narrative="Revenue shows concentrated risk from extreme values",
        claims=[{"field": "skewness", "value": 2.3}],
    )
    restored = AnalystDecision.model_validate_json(decision.model_dump_json())
    assert restored == decision

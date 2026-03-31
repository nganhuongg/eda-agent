from __future__ import annotations

import importlib
import os
import pytest
from insight.critic import CriticVerdict


# ── Shared fixtures ────────────────────────────────────────────────────────────

def _make_signals() -> dict:
    return {
        "revenue": {
            "skewness": 2.3,
            "missing_ratio": 0.12,
        }
    }


def _make_analysis_results() -> dict:
    return {
        "revenue": {
            "outlier_count": 5,
        }
    }


def _make_finding(claims: list, column: str = "revenue") -> dict:
    return {
        "column": column,
        "claims": claims,
        "narrative": "Test narrative.",
        "business_label": "risk",
    }


def _get_validate_finding():
    """Lazy import so collection succeeds in RED state (ImportError raised at call time)."""
    from insight.critic import validate_finding  # noqa: PLC0415
    return validate_finding


# ── CRIT-01: Claim matches signal or analysis_results → approved ───────────────

def test_approved_when_claim_matches_signal():
    validate_finding = _get_validate_finding()
    finding = _make_finding([{"field": "skewness", "value": 2.3}])
    verdict = validate_finding(finding, _make_signals(), _make_analysis_results())
    assert verdict.approved is True
    assert verdict.rejected_claims == []


def test_approved_when_claim_matches_analysis_results():
    validate_finding = _get_validate_finding()
    finding = _make_finding([{"field": "outlier_count", "value": 5.0}])
    verdict = validate_finding(finding, _make_signals(), _make_analysis_results())
    assert verdict.approved is True
    assert verdict.rejected_claims == []


# ── CRIT-02: No match or out-of-tolerance → rejected ──────────────────────────

def test_rejected_when_field_not_found():
    validate_finding = _get_validate_finding()
    finding = _make_finding([{"field": "nonexistent_field", "value": 1.0}])
    verdict = validate_finding(finding, _make_signals(), _make_analysis_results())
    assert verdict.approved is False
    assert "nonexistent_field" in verdict.rejected_claims


def test_rejected_when_value_out_of_tolerance():
    validate_finding = _get_validate_finding()
    # skewness=9.9 is far outside 1% of 2.3
    finding = _make_finding([{"field": "skewness", "value": 9.9}])
    verdict = validate_finding(finding, _make_signals(), _make_analysis_results())
    assert verdict.approved is False
    assert "skewness" in verdict.rejected_claims


# ── CRIT-03: Returns CriticVerdict with both fields ───────────────────────────

def test_verdict_has_approved_and_rejected_claims():
    validate_finding = _get_validate_finding()
    finding = _make_finding([{"field": "skewness", "value": 2.3}])
    verdict = validate_finding(finding, _make_signals(), _make_analysis_results())
    assert isinstance(verdict, CriticVerdict)
    assert isinstance(verdict.approved, bool)
    assert isinstance(verdict.rejected_claims, list)


# ── CRIT-04: JSON round-trip + zero API calls ──────────────────────────────────

def test_critic_verdict_json_roundtrip_approved():
    v = CriticVerdict(approved=True, rejected_claims=[])
    restored = CriticVerdict.model_validate_json(v.model_dump_json())
    assert restored == v
    assert restored.approved is True
    assert restored.rejected_claims == []


def test_critic_verdict_json_roundtrip_rejected():
    v = CriticVerdict(approved=False, rejected_claims=["skewness", "missing_ratio"])
    restored = CriticVerdict.model_validate_json(v.model_dump_json())
    assert restored == v
    assert restored.approved is False
    assert restored.rejected_claims == ["skewness", "missing_ratio"]


def test_no_api_call_without_groq_key():
    saved = os.environ.pop("GROQ_API_KEY", None)
    try:
        import insight.critic as critic_mod
        importlib.reload(critic_mod)
        verdict = critic_mod.validate_finding(
            _make_finding([{"field": "skewness", "value": 2.3}]),
            _make_signals(),
            _make_analysis_results(),
        )
        assert verdict.approved is True
    finally:
        if saved is not None:
            os.environ["GROQ_API_KEY"] = saved


# ── CRIT-05: rejected_claims list contains specific field names ────────────────

def test_rejected_claims_list_contains_field_names():
    validate_finding = _get_validate_finding()
    # Two bad claims → both field names should appear in rejected_claims
    finding = _make_finding([
        {"field": "skewness", "value": 9.9},
        {"field": "missing_ratio", "value": 0.99},
    ])
    verdict = validate_finding(finding, _make_signals(), _make_analysis_results())
    assert verdict.approved is False
    assert "skewness" in verdict.rejected_claims
    assert "missing_ratio" in verdict.rejected_claims


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_empty_claims_returns_approved():
    validate_finding = _get_validate_finding()
    finding = _make_finding([])
    verdict = validate_finding(finding, _make_signals(), _make_analysis_results())
    assert verdict.approved is True
    assert verdict.rejected_claims == []


def test_none_signal_value_rejects_claim():
    validate_finding = _get_validate_finding()
    signals = {"revenue": {"skewness": None}}
    finding = _make_finding([{"field": "skewness", "value": 2.3}])
    verdict = validate_finding(finding, signals, _make_analysis_results())
    assert verdict.approved is False
    assert "skewness" in verdict.rejected_claims


def test_partial_rejection():
    validate_finding = _get_validate_finding()
    # skewness=2.3 passes, missing_ratio=0.99 fails (signal has 0.12)
    finding = _make_finding([
        {"field": "skewness", "value": 2.3},
        {"field": "missing_ratio", "value": 0.99},
    ])
    verdict = validate_finding(finding, _make_signals(), _make_analysis_results())
    assert verdict.approved is False
    assert verdict.rejected_claims == ["missing_ratio"]


def test_column_not_in_signals_rejects_all():
    validate_finding = _get_validate_finding()
    # signals has no entry for column "units"
    finding = _make_finding([
        {"field": "skewness", "value": 2.3},
        {"field": "missing_ratio", "value": 0.12},
    ], column="units")
    verdict = validate_finding(finding, _make_signals(), _make_analysis_results())
    assert verdict.approved is False
    assert "skewness" in verdict.rejected_claims
    assert "missing_ratio" in verdict.rejected_claims

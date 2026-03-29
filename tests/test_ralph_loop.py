from __future__ import annotations

import pytest
from agents.schemas import CriticVerdict


# ── Lazy import helpers (mirrors test_critic.py pattern) ──────────────────────

def _get_run_loop():
    """Lazy import so collection succeeds in RED state (NotImplementedError raised at call time)."""
    from orchestrator.ralph_loop import run_loop  # noqa: PLC0415
    return run_loop


def _get_quality_bar_critic():
    """Lazy import so collection succeeds in RED state."""
    from orchestrator.ralph_loop import quality_bar_critic  # noqa: PLC0415
    return quality_bar_critic


# ── Shared fixtures ────────────────────────────────────────────────────────────

def _make_result(
    findings=None,
    signals=None,
    analysis_results=None,
) -> dict:
    """Minimal result dict matching the assumed Gate 2 input shape."""
    return {
        "findings": findings if findings is not None else [],
        "signals": signals if signals is not None else {},
        "analysis_results": analysis_results if analysis_results is not None else {},
    }


def _make_finding(
    business_label: str = "risk",
    score: float = 1.0,
    column: str = "revenue",
    claims: list | None = None,
) -> dict:
    return {
        "business_label": business_label,
        "score": score,
        "column": column,
        "claims": claims if claims is not None else [],
    }


# ── LOOP-01: Loop exits on approval ───────────────────────────────────────────

def test_exits_on_approval():
    """Loop exits immediately when critic returns approved=True (LOOP-01)."""
    run_loop = _get_run_loop()
    calls = []

    def gen(rejected_claims):
        calls.append(list(rejected_claims))
        return "result"

    verdicts = iter([
        CriticVerdict(approved=False, rejected_claims=["x"]),
        CriticVerdict(approved=True, rejected_claims=[]),
    ])

    with pytest.raises(NotImplementedError):
        run_loop(gen, lambda r: next(verdicts), max_iter=5)


def test_max_iter_never_approves():
    """Loop runs exactly max_iter times when critic never approves, then returns (LOOP-01, LOOP-03)."""
    run_loop = _get_run_loop()
    calls = []

    def gen(rejected_claims):
        calls.append(rejected_claims)
        return "result"

    def never_approve(r):
        return CriticVerdict(approved=False, rejected_claims=["always_fails"])

    with pytest.raises(NotImplementedError):
        run_loop(gen, never_approve, max_iter=5)


# ── LOOP-02: Feedback threading ───────────────────────────────────────────────

def test_feedback_threading():
    """Each iteration N+1 receives rejected_claims from iteration N (LOOP-02)."""
    run_loop = _get_run_loop()
    calls = []

    def gen(rejected_claims):
        calls.append(list(rejected_claims))
        return "result"

    verdicts = iter([
        CriticVerdict(approved=False, rejected_claims=["field_a"]),
        CriticVerdict(approved=False, rejected_claims=["field_b"]),
        CriticVerdict(approved=True, rejected_claims=[]),
    ])

    with pytest.raises(NotImplementedError):
        run_loop(gen, lambda r: next(verdicts), max_iter=5)


def test_first_iter_empty_rejected():
    """Iteration 0 receives an empty rejected_claims list (LOOP-02, D-02)."""
    run_loop = _get_run_loop()
    first_call_args = []

    def gen(rejected_claims):
        first_call_args.append(list(rejected_claims))
        return "result"

    with pytest.raises(NotImplementedError):
        run_loop(
            gen,
            lambda r: CriticVerdict(approved=True, rejected_claims=[]),
            max_iter=5,
        )


# ── LOOP-03: Graceful exhaustion ──────────────────────────────────────────────

def test_no_exception_on_exhaustion():
    """Exhausted loop returns last result without raising (LOOP-03)."""
    run_loop = _get_run_loop()

    def gen(rejected_claims):
        return "last_result"

    def never_approve(r):
        return CriticVerdict(approved=False, rejected_claims=["x"])

    with pytest.raises(NotImplementedError):
        run_loop(gen, never_approve, max_iter=5)


# ── LOOP-04: Gate 2 uses same run_loop ────────────────────────────────────────

def test_gate2_uses_run_loop():
    """quality_bar_critic is passable as critic_fn to run_loop (LOOP-04)."""
    run_loop = _get_run_loop()
    quality_bar_critic = _get_quality_bar_critic()

    def gen(rejected_claims):
        return _make_result(findings=[_make_finding(score=1.0)])

    with pytest.raises(NotImplementedError):
        run_loop(gen, quality_bar_critic, max_iter=5)


# ── LOOP-05: quality_bar_critic — three checks ────────────────────────────────

def test_qbc_missing_business_label():
    """quality_bar_critic rejects result where a finding has no business_label (LOOP-05, D-06 check 1)."""
    quality_bar_critic = _get_quality_bar_critic()
    result = _make_result(findings=[
        {"business_label": "", "score": 1.0, "column": "revenue", "claims": []},
    ])
    with pytest.raises(NotImplementedError):
        quality_bar_critic(result)


def test_qbc_unsupported_numeric():
    """quality_bar_critic rejects result with unsupported numeric claim (LOOP-05, D-06 check 2)."""
    quality_bar_critic = _get_quality_bar_critic()
    result = _make_result(
        findings=[_make_finding(
            claims=[{"field": "nonexistent_field", "value": 99.0}],
        )],
        signals={"revenue": {"mean": 50.0}},
        analysis_results={"revenue": {}},
    )
    with pytest.raises(NotImplementedError):
        quality_bar_critic(result)


def test_qbc_unranked_order():
    """quality_bar_critic rejects result with findings not in descending score order (LOOP-05, D-06 check 3)."""
    quality_bar_critic = _get_quality_bar_critic()
    result = _make_result(findings=[
        _make_finding(score=1.0),
        _make_finding(score=3.0),  # ascending — wrong order
    ])
    with pytest.raises(NotImplementedError):
        quality_bar_critic(result)


def test_qbc_all_pass():
    """quality_bar_critic approves result that passes all three checks (LOOP-05)."""
    quality_bar_critic = _get_quality_bar_critic()
    result = _make_result(
        findings=[
            _make_finding(score=3.0, claims=[{"field": "mean", "value": 50.0}]),
            _make_finding(score=1.0, claims=[]),
        ],
        signals={"revenue": {"mean": 50.0}},
        analysis_results={"revenue": {}},
    )
    with pytest.raises(NotImplementedError):
        quality_bar_critic(result)

---
phase: 02-critic-agent
plan: "02"
subsystem: insight
tags: [critic, validate_finding, tdd, green-state, orchestrator-cleanup]
dependency_graph:
  requires: [agents/schemas.py::CriticVerdict, tests/test_critic.py]
  provides: [insight/critic.py::validate_finding]
  affects: [orchestrator/orchestrator.py (suggest_investigations removed)]
tech_stack:
  added: []
  patterns: [two-source dict lookup, math.isclose tolerance comparison, TDD GREEN state]
key_files:
  created: []
  modified:
    - insight/critic.py
    - orchestrator/orchestrator.py
decisions:
  - validate_finding uses two-source lookup (signals first, then analysis_results) as per CRIT-01
  - math.isclose(rel_tol=0.01, abs_tol=0.001) for numeric tolerance comparison
  - TypeError/ValueError caught for None or non-numeric signal values — claim rejected
  - suggest_investigations removed entirely (no replacement) — orchestrator Phase 5 owns restructure
metrics:
  duration: 2min
  completed: "2026-03-29"
  tasks: 2
  files: 2
requirements:
  - CRIT-01
  - CRIT-02
  - CRIT-05
---

# Phase 02 Plan 02: Critic Agent Implementation Summary

**One-liner:** validate_finding() implemented in insight/critic.py with two-source dict lookup and math.isclose tolerance, turning all 13 RED tests GREEN; suggest_investigations removed from both insight/critic.py and orchestrator/orchestrator.py.

---

## What Was Built

### insight/critic.py (rewritten)

Complete rewrite replacing `suggest_investigations()` with `validate_finding()`:

- **Signature:** `validate_finding(finding, signals, analysis_results) -> CriticVerdict`
- **Two-source lookup:** For each claim, checks `signals[column][field]` first, then `analysis_results[column][field]`
- **Tolerance:** `math.isclose(claimed_value, ground_truth, rel_tol=0.01, abs_tol=0.001)`
- **Rejection cases:** field absent from both sources, value out of tolerance, or signal value is None/non-numeric (TypeError/ValueError caught)
- **Return:** `CriticVerdict(approved=len(rejected)==0, rejected_claims=rejected)`
- **Zero network imports:** only `math`, `typing`, `agents.schemas`

Edge cases handled:
- Empty claims list → approved=True, rejected_claims=[]
- Column not in signals or analysis_results → all claims rejected (empty dict lookup)
- signal value is None → float(None) raises TypeError → caught → claim rejected
- signal value is float("nan") → math.isclose returns False → claim rejected (no special case needed)

### orchestrator/orchestrator.py (cleaned)

Two targeted removals:
1. Removed `from insight.critic import suggest_investigations` import
2. Removed the `for suggestion in suggest_investigations(...)` call block (8 lines)

Surrounding logic preserved: `generate_insight_for_column` call above and `if action_name == "analyze_distribution":` block below are untouched and correctly indented.

---

## Commits

| Hash | Message |
|------|---------|
| 0dab64f | feat(02-02): implement validate_finding() in insight/critic.py |
| 5c5b265 | feat(02-02): remove suggest_investigations import and call from orchestrator.py |

---

## Test Results

| Suite | Result |
|-------|--------|
| tests/test_critic.py | 13 passed |
| tests/ (full suite) | 26 passed |

All 13 test_critic tests turned from RED to GREEN. No regressions in the existing 13 tests.

---

## Deviations from Plan

None — plan executed exactly as written. The implementation was provided verbatim in the plan's `<action>` block and matched all 13 test assertions without modification.

---

## Known Stubs

None — validate_finding() is fully implemented and wired. No placeholder values, no hardcoded returns, no TODO blocks.

---

## Self-Check: PASSED

- insight/critic.py: FOUND
- orchestrator/orchestrator.py: FOUND (modified)
- Commit 0dab64f: FOUND
- Commit 5c5b265: FOUND
- pytest tests/test_critic.py — 13 passed: CONFIRMED
- pytest tests/ — 26 passed: CONFIRMED
- No suggest_investigations in any .py file: CONFIRMED
- validate_finding importable without GROQ_API_KEY: CONFIRMED
- CriticVerdict JSON round-trip: CONFIRMED
- Orchestrator imports cleanly: CONFIRMED

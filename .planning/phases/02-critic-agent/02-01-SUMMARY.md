---
phase: 02-critic-agent
plan: "01"
subsystem: agents
tags: [critic, pydantic, tdd, red-state, schema]
dependency_graph:
  requires: []
  provides: [agents/schemas.py::CriticVerdict, tests/test_critic.py]
  affects: [insight/critic.py (Plan 02 will implement validate_finding)]
tech_stack:
  added: [pydantic v2 BaseModel, agents/ package]
  patterns: [TDD RED state, lazy import for collection compatibility]
key_files:
  created:
    - agents/__init__.py
    - agents/schemas.py
    - tests/test_critic.py
  modified: []
decisions:
  - CriticVerdict placed in agents/schemas.py per CONTEXT.md Decision 4
  - Lazy import (_get_validate_finding helper) used so pytest can collect 13 tests while validate_finding is absent
  - Two fields only (approved: bool, rejected_claims: List[str]) — no validators, no network imports
metrics:
  duration: 2min
  completed: "2026-03-29"
  tasks: 2
  files: 3
requirements:
  - CRIT-03
  - CRIT-04
---

# Phase 02 Plan 01: Critic Agent Schema + RED Test Suite Summary

**One-liner:** CriticVerdict Pydantic v2 BaseModel with approved/rejected_claims fields and 13-test RED suite covering CRIT-01 through CRIT-05 plus 4 edge cases.

---

## What Was Built

### agents/__init__.py
Package marker for the new `agents/` module. Required for `from agents.schemas import CriticVerdict` to resolve.

### agents/schemas.py
`CriticVerdict` Pydantic v2 `BaseModel` with exactly two fields:
- `approved: bool` — True only when all claims validated within tolerance
- `rejected_claims: List[str]` — field names that failed; threaded to Analyst in next Ralph Loop iteration

No network imports. No validators. `model_validate_json()` round-trip verified for both approved and rejected instances.

### tests/test_critic.py
13 test functions in RED state:

| Group | Tests | Status |
|-------|-------|--------|
| CRIT-01 | test_approved_when_claim_matches_signal, test_approved_when_claim_matches_analysis_results | FAIL (ImportError) |
| CRIT-02 | test_rejected_when_field_not_found, test_rejected_when_value_out_of_tolerance | FAIL (ImportError) |
| CRIT-03 | test_verdict_has_approved_and_rejected_claims | FAIL (ImportError) |
| CRIT-04 | test_critic_verdict_json_roundtrip_approved, test_critic_verdict_json_roundtrip_rejected | **PASS** |
| CRIT-04 | test_no_api_call_without_groq_key | FAIL (AttributeError — validate_finding not on module) |
| CRIT-05 | test_rejected_claims_list_contains_field_names | FAIL (ImportError) |
| Edge | test_empty_claims_returns_approved, test_none_signal_value_rejects_claim, test_partial_rejection, test_column_not_in_signals_rejects_all | FAIL (ImportError) |

---

## Commits

| Hash | Message |
|------|---------|
| b5ec004 | feat(02-01): create agents/ package with CriticVerdict Pydantic v2 schema |
| 6372c7f | test(02-01): add RED test suite for Critic agent (13 tests, all validate_finding fail) |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Lazy import pattern for pytest collection compatibility**
- **Found during:** Task 2
- **Issue:** Plan showed `from insight.critic import validate_finding` at module level, which would cause ImportError during pytest collection (not just during test execution), preventing the "collects 13 tests" acceptance criterion from being met.
- **Fix:** Added `_get_validate_finding()` helper that performs the import lazily inside each test function. This allows pytest to collect all 13 tests while they still fail with ImportError at execution time (RED state). The two CriticVerdict round-trip tests pass as specified.
- **Files modified:** tests/test_critic.py
- **Commit:** 6372c7f

---

## Known Stubs

None — no stubs in this plan. `CriticVerdict` is fully implemented. Test assertions are complete (no pass/... bodies). The `validate_finding` function does not exist yet by design — Plan 02 implements it.

---

## Self-Check: PASSED

- agents/__init__.py: FOUND
- agents/schemas.py: FOUND
- tests/test_critic.py: FOUND
- Commit b5ec004: FOUND
- Commit 6372c7f: FOUND
- pytest collects 13 tests: CONFIRMED
- CriticVerdict round-trip PASS: CONFIRMED
- No groq/openai/httpx in agents/: CONFIRMED

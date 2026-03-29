---
phase: 03-ralph-loop-utility
plan: 01
subsystem: testing
tags: [tdd, pytest, ralph-loop, orchestrator, critic-verdict]

# Dependency graph
requires:
  - phase: 02-critic-agent
    provides: "CriticVerdict schema in agents/schemas.py (approved: bool, rejected_claims: List[str])"
provides:
  - "orchestrator/ralph_loop.py shell with run_loop and quality_bar_critic signatures"
  - "tests/test_ralph_loop.py with 10 named RED-state stubs covering LOOP-01 through LOOP-05"
  - "Wave 0 TDD scaffold: pytest collects all 10 stubs; all pass by catching NotImplementedError"
affects: [03-02-implementation, orchestrator, testing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy import helper pattern (mirrors test_critic.py): _get_run_loop() and _get_quality_bar_critic() import inside function body with noqa: PLC0415"
    - "RED state contract: wrap call in pytest.raises(NotImplementedError) instead of pytest.mark.skip"
    - "Namespace package: orchestrator/ has no __init__.py but is importable as namespace package"

key-files:
  created:
    - orchestrator/ralph_loop.py
    - tests/test_ralph_loop.py
  modified: []

key-decisions:
  - "pytest.raises(NotImplementedError) as RED state contract: ensures stubs are wired (imports succeed) while marking intent to fail"
  - "Lazy import helpers for both run_loop and quality_bar_critic: collection succeeds in RED state because ImportError is deferred to call time"

patterns-established:
  - "RED state stub pattern: shell raises NotImplementedError; tests wrap in pytest.raises(NotImplementedError) so 10 passed confirms correct wiring"
  - "Wave 0 before Wave 1: importable stubs must exist before implementation begins to enable continuous pytest feedback"

requirements-completed: [LOOP-01, LOOP-02, LOOP-03, LOOP-04, LOOP-05]

# Metrics
duration: 3min
completed: 2026-03-29
---

# Phase 3 Plan 01: Ralph Loop TDD Scaffold Summary

**10-test RED-state scaffold for ralph loop: importable orchestrator/ralph_loop.py shell + pytest stubs for LOOP-01 through LOOP-05 behaviors, all collecting and passing in RED state**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-29T15:24:45Z
- **Completed:** 2026-03-29T15:27:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `orchestrator/ralph_loop.py` as a namespace-package-importable shell exporting `run_loop` and `quality_bar_critic` with correct type signatures; both raise `NotImplementedError`
- Created `tests/test_ralph_loop.py` with exactly 10 named test stubs using lazy import pattern (mirrors test_critic.py), all wrapping calls in `pytest.raises(NotImplementedError)` — RED state confirmed
- All 10 stubs pass (`10 passed`) and existing 15 tests in test_critic.py + test_state_schema.py remain GREEN — zero regression

## Task Commits

Each task was committed atomically:

1. **Task 1: Create orchestrator/ralph_loop.py shell** - `046ca13` (feat)
2. **Task 2: Create tests/test_ralph_loop.py with 10 RED stubs** - `53a6d42` (test)

## Files Created/Modified

- `orchestrator/ralph_loop.py` - Shell implementation file with run_loop and quality_bar_critic signatures; both raise NotImplementedError; imports only from agents.schemas
- `tests/test_ralph_loop.py` - 10 RED-state test stubs covering LOOP-01 (approval exit), LOOP-02 (feedback threading), LOOP-03 (graceful exhaustion), LOOP-04 (gate2 uses run_loop), LOOP-05 (quality_bar_critic three checks)

## Decisions Made

- Used `pytest.raises(NotImplementedError)` as the RED state contract instead of `pytest.mark.skip` — this ensures imports are wired and pytest can confirm the shell behaves predictably before Wave 1 replaces the raises
- Lazy import helpers `_get_run_loop()` and `_get_quality_bar_critic()` used for both functions to mirror the established pattern from test_critic.py, ensuring collection never fails even if import paths change

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 0 scaffold complete: Plan 02 executor can immediately implement `run_loop` and `quality_bar_critic` against the 10 named, known-failing tests
- Both function signatures are locked in ralph_loop.py — Plan 02 replaces the `raise NotImplementedError` bodies only
- Existing test suite (critic + state schema) remains GREEN — no regressions introduced

---
*Phase: 03-ralph-loop-utility*
*Completed: 2026-03-29*

## Self-Check: PASSED

- FOUND: orchestrator/ralph_loop.py
- FOUND: tests/test_ralph_loop.py
- FOUND: .planning/phases/03-ralph-loop-utility/03-01-SUMMARY.md
- FOUND: commit 046ca13 (Task 1)
- FOUND: commit 53a6d42 (Task 2)

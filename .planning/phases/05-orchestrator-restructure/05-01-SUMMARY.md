---
phase: 05-orchestrator-restructure
plan: 01
subsystem: orchestrator
tags: [tdd, orchestrator, run_agent, column-loop, gate1, analyst-decisions, df-boundary]
dependency_graph:
  requires: [04-02]
  provides: [orchestrator-column-loop, gate1-critic, analyst-decisions-state-key]
  affects: [orchestrator/orchestrator.py, state/runtime_state.py, tests/test_orchestrator.py]
tech_stack:
  added: [functools.partial]
  patterns: [column-based loop, tools-first execution, _make_gate1_critic closure, run_loop Gate 1]
key_files:
  created: [tests/test_orchestrator.py]
  modified: [state/runtime_state.py, orchestrator/orchestrator.py]
decisions:
  - "Column-based outer loop replaces step-based loop — one iteration per high-risk unanalyzed column"
  - "_run_tools_for_column() is the single df boundary point — df never passed to analyze_column or run_loop"
  - "_make_gate1_critic() wraps validate_finding as a CriticVerdict closure, threaded to run_loop"
  - "analyst_decisions added as Dict[str, Any] in TypedDict to avoid circular import from agents/"
  - "Three RED stubs raise NotImplementedError directly (not wrapped in pytest.raises) — collection succeeds, runtime fails"
metrics:
  duration: 2min
  completed_date: "2026-03-29"
  tasks: 3
  files: 3
---

# Phase 05 Plan 01: Orchestrator Restructure — TDD Foundation + Column Loop Summary

**One-liner:** Column-based run_agent() with tools-first execution, _make_gate1_critic() Gate 1 closure, and analyst_decisions state key; three RED stubs wired for Plan 05-02 GREEN pass.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create test_orchestrator.py — three RED stubs | 3df967f | tests/test_orchestrator.py |
| 2 | Extend AgentState with analyst_decisions key | 13557ce | state/runtime_state.py |
| 3 | Rewrite run_agent() — column loop + tools-first + Gate 1 | 0286ac5 | orchestrator/orchestrator.py |

---

## What Was Built

### Task 1: RED Test Stubs

`tests/test_orchestrator.py` — 3 tests collected, 3 FAILED (NotImplementedError), no ImportError. Uses lazy import helpers (`_get_run_agent()`) mirroring `test_ralph_loop.py` pattern. Fixture helpers `_make_minimal_state()`, `_make_minimal_df()`, `_make_config()` stubbed for Plan 05-02 GREEN implementation.

### Task 2: AgentState Extension

`state/runtime_state.py` — Added `analyst_decisions: Dict[str, Any]` to `AgentState` TypedDict (after `insights`) and `"analyst_decisions": {}` to `initialize_state()` return dict. Uses `Dict[str, Any]` to avoid circular import from `agents/` package. All 2 prior state schema tests remain GREEN.

### Task 3: Orchestrator Rewrite

`orchestrator/orchestrator.py` — Full rewrite of `run_agent()`:

- **Column-based outer loop (D-01):** `for _col_idx in range(max_columns)` replaces step-based loop
- **Tools-first (D-02):** `_run_tools_for_column()` called before `analyze_column` — df boundary enforced structurally
- **Gate 1 (D-05):** `run_loop(partial(analyze_column, state, column), critic_fn, max_iter=5)`
- **_make_gate1_critic (D-05):** Closure wrapping `validate_finding` returning `CriticVerdict`
- **analyst_decisions (D-03):** `state["analyst_decisions"][column] = decision`
- **insights bridge (D-04):** `state["insights"][column]` populated with 5 required keys
- **Exhaustion warning (D-06):** `logging.warning("Gate 1 exhausted for column '%s'...")`
- **Removed:** `_queue_action()`, `generate_insight_for_column` import

All 48 prior tests (phases 1-4) remain GREEN.

---

## Verification Results

1. `pytest tests/test_orchestrator.py -v` — 3 FAILED (NotImplementedError RED stubs, all collected)
2. `pytest tests/ --ignore=tests/test_orchestrator.py -q` — 48 passed, 0 failures
3. `python -c "from state.runtime_state import initialize_state; s = initialize_state(); assert 'analyst_decisions' in s"` — exits 0
4. `python -c "from orchestrator.orchestrator import run_agent, _make_gate1_critic"` — exits 0
5. `grep -c "generate_insight_for_column" orchestrator/orchestrator.py` — returns 0

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Column-based outer loop replaces step-based loop | D-01 requirement; one iteration per high-risk unanalyzed column |
| _run_tools_for_column() is the single df boundary point | D-07 structural enforcement; df never passed to analyze_column, run_loop, or validate_finding |
| _make_gate1_critic() wraps validate_finding as CriticVerdict closure | D-05 requirement; run_loop needs critic_fn: Callable[[Any], CriticVerdict] |
| analyst_decisions typed as Dict[str, Any] | Avoids circular import from agents/ package; AnalystDecision lives in agents/schemas.py |
| RED stubs raise NotImplementedError directly | Consistent with Phase 03/04 pattern; collection succeeds, test bodies fail predictably |

---

## Known Stubs

None — all implemented behavior is wired to real logic. The RED stubs in `tests/test_orchestrator.py` are intentional and tracked: they exist to be implemented GREEN in Plan 05-02.

---

## Self-Check: PASSED

- [x] tests/test_orchestrator.py exists
- [x] state/runtime_state.py modified (analyst_decisions in TypedDict + initialize_state)
- [x] orchestrator/orchestrator.py rewritten (column loop, _make_gate1_critic, run_loop wired)
- [x] Commit 3df967f exists (test stubs)
- [x] Commit 13557ce exists (state extension)
- [x] Commit 0286ac5 exists (orchestrator rewrite)

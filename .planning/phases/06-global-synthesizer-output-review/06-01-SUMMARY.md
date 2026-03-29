---
phase: "06-global-synthesizer-output-review"
plan: "01"
subsystem: "synthesis"
tags: ["tdd", "synthesizer", "global_synthesizer", "test-stubs", "red-green"]
dependency_graph:
  requires:
    - "05-02: orchestrator.orchestrator with analyst_decisions, run_loop, quality_bar_critic"
    - "03-02: ralph_loop.py run_loop and quality_bar_critic implemented"
    - "04-01: agents/schemas.py AnalystDecision model"
    - "01-01: state/runtime_state.py initialize_state with temporal_signals"
  provides:
    - "_build_findings_list() in synthesis/global_synthesizer.py"
    - "tests/test_synthesizer.py with 4 tests (3 GREEN, test_gate2_called RED)"
    - "tests/test_report_generator.py with 5 tests (3 GREEN, 2 RED pending Plan 02)"
  affects:
    - "synthesis/global_synthesizer.py"
    - "report/report_generator.py (Plan 02 scope)"
tech_stack:
  added: []
  patterns:
    - "Lazy import helpers for _build_findings_list (mirrors test_ralph_loop.py pattern)"
    - "claims=[] pattern to avoid quality_bar_critic Check 2 rejections"
    - "sort(risk_scores.items(), key=lambda x: -x[1]) for descending risk ranking"
key_files:
  created:
    - "tests/test_synthesizer.py"
    - "tests/test_report_generator.py"
  modified:
    - "synthesis/global_synthesizer.py"
decisions:
  - "synthesis/global_synthesizer.py ignores gitignore in worktree — force-added with git add -f because synthesis/ is in .gitignore on both branches but the file is tracked in main"
  - "_build_findings_list returns findings dict compatible with quality_bar_critic shape (findings, signals, analysis_results)"
  - "tool_count == 0 columns excluded from findings list entirely, not just flagged"
  - "test_gate2_called intentionally stays RED until Plan 02 rewrites report_generator.py"
metrics:
  duration: "3min 18sec"
  completed_date: "2026-03-29"
  tasks_completed: 2
  files_changed: 3
---

# Phase 06 Plan 01: RED-state TDD Tests + _build_findings_list Implementation Summary

**One-liner:** RED-state test stubs for synthesizer and report generator, plus `_build_findings_list()` implementation using descending risk-score ranking, single-angle flag, and below-threshold exclusion.

---

## What Was Built

**Task 1 (RED stubs):** Created `tests/test_synthesizer.py` and `tests/test_report_generator.py` with the exact test function names required by the plan and validation strategy. All tests use lazy import helpers so pytest collection succeeds in RED state without collection-level ImportError.

**Task 2 (GREEN implementation):** Extended `synthesis/global_synthesizer.py` with `_build_findings_list(state)` below the existing `generate_global_summary()`. The function:
- Ranks columns by `risk_scores` descending (SYNTH-02)
- Skips columns with no `AnalystDecision` (not investigated)
- Excludes columns with 0 tool results from Gate 2 findings (SYNTH-01, D-06)
- Sets `single_angle=True` when exactly 1 tool result exists (SYNTH-01)
- Uses `claims=[]` to avoid quality_bar_critic Check 2 rejections (Phase 4 pattern)
- Returns `{findings, signals, analysis_results}` dict matching `quality_bar_critic` input shape

---

## Test Results

| Test | Status | Reason |
|------|--------|--------|
| test_findings_list_ranked | GREEN | _build_findings_list sorts revenue (0.9) before category |
| test_single_angle_note | GREEN | single_angle=True set when tool_count == 1 |
| test_below_threshold_note | GREEN | revenue excluded when analysis_results["revenue"] == {} |
| test_gate2_called | RED (expected) | Needs Plan 02's run_loop integration in generate_report |
| test_ranked_order_in_report | GREEN | Current generate_report already ranks by risk_score |
| test_business_label_present | RED (expected) | Needs Plan 02's new generate_report format |
| test_temporal_section_present | RED (expected) | Needs Plan 02's temporal section rendering |
| test_no_temporal_section | GREEN | Current generate_report has no temporal section |
| test_output_file_written | GREEN | Current generate_report writes outputs/report.md |

**Full suite:** 57 passed, 3 failed (all expected RED for Plan 02 scope). 0 regressions.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] synthesis/ is in .gitignore in both branches**

- **Found during:** Task 2 commit
- **Issue:** The worktree branch (.gitignore from old commit 93b6318) listed `synthesis/` as deprecated. After merging main, the file existed but was untracked and ignored.
- **Fix:** Used `git add -f synthesis/global_synthesizer.py` to force-track the file in the worktree branch. This matches the main branch where the file was already tracked before the gitignore entry was added.
- **Files modified:** synthesis/global_synthesizer.py (force-tracked)
- **Commit:** 6da4722

---

## Known Stubs

None. All stubs in test files are intentional RED-state tests documented as Plan 02 scope. The `_build_findings_list()` implementation is complete with no stubs.

---

## Self-Check: PASSED

| Item | Status |
|------|--------|
| tests/test_synthesizer.py exists | FOUND |
| tests/test_report_generator.py exists | FOUND |
| synthesis/global_synthesizer.py exists | FOUND |
| Commit e2d8fc4 (Task 1) exists | FOUND |
| Commit 6da4722 (Task 2) exists | FOUND |
| def _build_findings_list in global_synthesizer.py | FOUND |
| single_angle=True in global_synthesizer.py | FOUND |

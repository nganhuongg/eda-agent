---
phase: 3
slug: ralph-loop-utility
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 |
| **Config file** | `pytest.ini` (project root) — `testpaths = tests` |
| **Quick run command** | `py -m pytest tests/test_ralph_loop.py -q` |
| **Full suite command** | `py -m pytest tests/ -q --ignore=tests/test_temporal_profiler.py` |
| **Estimated runtime** | ~3 seconds |

Note: `tests/test_temporal_profiler.py` has a known collection error — excluded from full suite until resolved separately.

---

## Sampling Rate

- **After every task commit:** Run `py -m pytest tests/test_ralph_loop.py -q`
- **After every plan wave:** Run `py -m pytest tests/ -q --ignore=tests/test_temporal_profiler.py`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~3 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 0 | LOOP-01..05 | unit (stub) | `py -m pytest tests/test_ralph_loop.py -q` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | LOOP-01 | unit | `py -m pytest tests/test_ralph_loop.py::test_exits_on_approval -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | LOOP-01 | unit | `py -m pytest tests/test_ralph_loop.py::test_max_iter_never_approves -x` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 1 | LOOP-02 | unit | `py -m pytest tests/test_ralph_loop.py::test_feedback_threading -x` | ❌ W0 | ⬜ pending |
| 03-02-04 | 02 | 1 | LOOP-02 | unit | `py -m pytest tests/test_ralph_loop.py::test_first_iter_empty_rejected -x` | ❌ W0 | ⬜ pending |
| 03-02-05 | 02 | 1 | LOOP-03 | unit | `py -m pytest tests/test_ralph_loop.py::test_no_exception_on_exhaustion -x` | ❌ W0 | ⬜ pending |
| 03-02-06 | 02 | 1 | LOOP-04 | unit | `py -m pytest tests/test_ralph_loop.py::test_gate2_uses_run_loop -x` | ❌ W0 | ⬜ pending |
| 03-02-07 | 02 | 1 | LOOP-05 | unit | `py -m pytest tests/test_ralph_loop.py::test_qbc_missing_business_label -x` | ❌ W0 | ⬜ pending |
| 03-02-08 | 02 | 1 | LOOP-05 | unit | `py -m pytest tests/test_ralph_loop.py::test_qbc_unsupported_numeric -x` | ❌ W0 | ⬜ pending |
| 03-02-09 | 02 | 1 | LOOP-05 | unit | `py -m pytest tests/test_ralph_loop.py::test_qbc_unranked_order -x` | ❌ W0 | ⬜ pending |
| 03-02-10 | 02 | 1 | LOOP-05 | unit | `py -m pytest tests/test_ralph_loop.py::test_qbc_all_pass -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ralph_loop.py` — 10 stubs for LOOP-01 through LOOP-05 (all marked `pytest.mark.skip` or `raise NotImplementedError`)
- [ ] No new framework install required — pytest already available

*All stubs must be importable (no SyntaxError) before Wave 1 begins.*

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

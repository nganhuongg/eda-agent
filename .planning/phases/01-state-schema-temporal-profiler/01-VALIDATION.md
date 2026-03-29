---
phase: 1
slug: state-schema-temporal-profiler
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` (Wave 0 creates) |
| **Quick run command** | `.venv/Scripts/pytest tests/test_temporal_profiler.py -q` |
| **Full suite command** | `.venv/Scripts/pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/Scripts/pytest tests/test_temporal_profiler.py -q`
- **After every plan wave:** Run `.venv/Scripts/pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | infra | setup | `.venv/Scripts/pytest --version` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | TEMP-01 | unit | `.venv/Scripts/pytest tests/test_temporal_profiler.py::test_date_column_detected -q` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | TEMP-01 | unit | `.venv/Scripts/pytest tests/test_temporal_profiler.py::test_no_date_column_skips -q` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 2 | TEMP-02 | unit | `.venv/Scripts/pytest tests/test_temporal_profiler.py::test_trend_direction_up -q` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 2 | TEMP-02 | unit | `.venv/Scripts/pytest tests/test_temporal_profiler.py::test_trend_direction_confidence -q` | ❌ W0 | ⬜ pending |
| 1-01-06 | 01 | 2 | TEMP-03 | unit | `.venv/Scripts/pytest tests/test_temporal_profiler.py::test_mom_yoy_deltas -q` | ❌ W0 | ⬜ pending |
| 1-01-07 | 01 | 2 | TEMP-04 | unit | `.venv/Scripts/pytest tests/test_temporal_profiler.py::test_forecast_with_sufficient_data -q` | ❌ W0 | ⬜ pending |
| 1-01-08 | 01 | 2 | TEMP-04 | unit | `.venv/Scripts/pytest tests/test_temporal_profiler.py::test_forecast_gated_insufficient_data -q` | ❌ W0 | ⬜ pending |
| 1-01-09 | 01 | 2 | TEMP-05 | unit | `.venv/Scripts/pytest tests/test_temporal_profiler.py::test_no_date_message_in_state -q` | ❌ W0 | ⬜ pending |
| 1-01-10 | 01 | 2 | TEMP-06 | unit | `.venv/Scripts/pytest tests/test_temporal_profiler.py::test_gap_detection -q` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | TEMP-01 | unit | `.venv/Scripts/pytest tests/test_state_schema.py::test_temporal_signals_field -q` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | TEMP-01 | unit | `.venv/Scripts/pytest tests/test_state_schema.py::test_v2_fields_unbroken -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — make tests a package
- [ ] `pytest.ini` — pytest config pointing at `tests/`
- [ ] `tests/test_temporal_profiler.py` — stubs for TEMP-01 through TEMP-06 (11 test functions)
- [ ] `tests/test_state_schema.py` — stubs for AgentState extension (2 test functions)
- [ ] `.venv/Scripts/pip install pytest statsmodels scipy` — missing runtime dependencies

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `outputs/report.md` still generated after Phase 1 | TEMP-01 (v2 contract) | Requires running full agent on real CSV | Run `python main.py`, confirm `outputs/report.md` exists and is non-empty |
| Trend section absent when no date column | TEMP-05 | Requires real CSV without date col | Run with `data/sample.csv` if it has no date col, read report and confirm skip message |

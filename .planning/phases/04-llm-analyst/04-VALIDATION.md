---
phase: 4
slug: llm-analyst
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (confirmed installed) |
| **Config file** | None — uses default pytest discovery |
| **Quick run command** | `pytest tests/test_llm_analyst.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds (all mocked — no real API calls) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_llm_analyst.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 0 | ANLST-01..06 | stub | `pytest tests/test_llm_analyst.py -x` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 1 | ANLST-01 | unit | `pytest tests/test_llm_analyst.py::test_analyze_column_returns_analyst_decision -x` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 1 | ANLST-02 | unit | `pytest tests/test_llm_analyst.py::test_analyst_decision_hypothesis_non_empty -x` | ❌ W0 | ⬜ pending |
| 4-01-04 | 01 | 1 | ANLST-03 | unit | `pytest tests/test_llm_analyst.py::test_recommended_tools_valid -x` | ❌ W0 | ⬜ pending |
| 4-01-05 | 01 | 1 | ANLST-04 | unit | `pytest tests/test_llm_analyst.py::test_business_label_valid -x` | ❌ W0 | ⬜ pending |
| 4-01-06 | 01 | 1 | ANLST-05 | unit | `pytest tests/test_llm_analyst.py::test_narrative_non_empty -x` | ❌ W0 | ⬜ pending |
| 4-01-07 | 01 | 1 | ANLST-06 | unit (sentinel-df) | `pytest tests/test_llm_analyst.py::test_build_analyst_context_contains_no_df_reference -x` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 1 | D-04 | unit | `pytest tests/test_llm_analyst.py::test_malformed_json_triggers_fallback -x` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 1 | D-06 | unit | `pytest tests/test_llm_analyst.py::test_missing_api_key_triggers_fallback -x` | ❌ W0 | ⬜ pending |
| 4-02-03 | 02 | 1 | D-07 | unit | `pytest tests/test_llm_analyst.py::test_fallback_returns_analyst_decision -x` | ❌ W0 | ⬜ pending |
| 4-02-04 | 02 | 1 | D-08 | unit (mock 429) | `pytest tests/test_llm_analyst.py::test_rate_limit_retries_then_fallback -x` | ❌ W0 | ⬜ pending |
| 4-02-05 | 02 | 1 | CRIT-04 reg | unit | `pytest tests/test_llm_analyst.py::test_analyst_decision_json_roundtrip -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_llm_analyst.py` — stubs for ANLST-01..06, D-04, D-06, D-07, D-08, CRIT-04 regression
- [ ] No new conftest.py needed — minimal_state fixture defined inline or reuse initialize_state()
- [ ] No new framework install needed — pytest already present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Plain business language, no statistical jargon in narrative | ANLST-05 | Jargon detection is subjective | Inspect `narrative` field in a real run against a sales CSV — confirm no raw stat terms like "kurtosis", "p-value", "adfuller" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

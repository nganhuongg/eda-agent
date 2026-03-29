---
phase: 06
slug: global-synthesizer-output-review
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini |
| **Quick run command** | `python -m pytest tests/test_synthesizer.py tests/test_report_generator.py -q` |
| **Full suite command** | `python -m pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_synthesizer.py tests/test_report_generator.py -q`
- **After every plan wave:** Run `python -m pytest tests/ -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | SYNTH-01, SYNTH-02 | unit (RED) | `python -m pytest tests/test_synthesizer.py -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 0 | RPT-01, RPT-02 | unit (RED) | `python -m pytest tests/test_report_generator.py -q` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | SYNTH-01, SYNTH-02 | unit (GREEN) | `python -m pytest tests/test_synthesizer.py -q` | ✅ W0 | ⬜ pending |
| 06-01-04 | 01 | 1 | RPT-01, RPT-02, RPT-03 | unit (GREEN) | `python -m pytest tests/test_report_generator.py -q` | ✅ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | LOOP-04, LOOP-05 | unit (GREEN) | `python -m pytest tests/test_report_generator.py -k gate2 -q` | ✅ W0 | ⬜ pending |
| 06-02-02 | 02 | 2 | RPT-04, RPT-05 | integration | `python -m pytest tests/ -q --tb=short` | ✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_synthesizer.py` — stubs for SYNTH-01, SYNTH-02
- [ ] `tests/test_report_generator.py` — stubs for RPT-01, RPT-02, RPT-03, RPT-04, RPT-05

*Existing infrastructure (pytest.ini, conftest.py) covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Inline visualizations render in Markdown viewer | RPT-01, RPT-02 | Requires visual inspection of rendered .md | Open outputs/report.md in a Markdown viewer; verify plots appear inline within their section |
| LLM narrative generation end-to-end | RPT-05 | Requires live MINIMAX_API_KEY | Set MINIMAX_API_KEY in .env.local; run python main.py; verify outputs/report_llm.md generated |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

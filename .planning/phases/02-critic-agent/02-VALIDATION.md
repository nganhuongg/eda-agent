---
phase: 02
slug: critic-agent
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pytest.ini exists, installed) |
| **Config file** | `pytest.ini` |
| **Quick run command** | `.venv/Scripts/pytest tests/test_critic.py -q --tb=short` |
| **Full suite command** | `.venv/Scripts/pytest tests/ -q --tb=short` |
| **Estimated runtime** | ~8 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/Scripts/pytest tests/test_critic.py -q --tb=short`
- **After every plan wave:** Run `.venv/Scripts/pytest tests/ -q --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~8 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | CRIT-03, CRIT-04 | stub | `.venv/Scripts/pytest tests/test_critic.py -q` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | CRIT-04 | unit | `.venv/Scripts/pytest tests/test_critic.py::test_critic_verdict_schema -q` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | CRIT-01 | unit | `.venv/Scripts/pytest tests/test_critic.py::test_approved_when_claim_matches -q` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 1 | CRIT-02 | unit | `.venv/Scripts/pytest tests/test_critic.py::test_rejected_when_no_match -q` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 1 | CRIT-05 | unit | `.venv/Scripts/pytest tests/test_critic.py::test_rejected_claims_list -q` | ❌ W0 | ⬜ pending |
| 02-01-06 | 01 | 1 | CRIT-03 | unit | `.venv/Scripts/pytest tests/test_critic.py::test_no_api_calls -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_critic.py` — stubs for CRIT-01 through CRIT-05
- [ ] `agents/__init__.py` — empty module marker (prerequisite for CriticVerdict import)
- [ ] `agents/schemas.py` — CriticVerdict skeleton (import must not error)

*Existing pytest infrastructure (pytest.ini, tests/__init__.py) already in place from Phase 01.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | — | — | — |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

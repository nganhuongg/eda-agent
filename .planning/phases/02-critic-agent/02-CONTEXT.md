---
phase: 02-critic-agent
created: 2026-03-29
status: ready
---

# Phase 02: Critic Agent — Context

## Domain

Build a fully deterministic Critic agent that validates structured LLM findings against computed signals and returns a `CriticVerdict` Pydantic BaseModel. Zero API calls. Replaces the existing `suggest_investigations()` function in `insight/critic.py`.

---

## Decisions

### 1. Claim structure — Option A: Structured finding dict

The LLM outputs structured findings — not free-text narratives. Each finding is a dict with explicit fields the Critic can validate directly via dict lookup.

**Finding shape (per column):**
```python
{
  "column": "revenue",
  "claims": [
    {"field": "skewness", "value": 2.3},
    {"field": "missing_ratio", "value": 0.12}
  ],
  "narrative": "Revenue is highly skewed...",
  "business_label": "risk"  # risk | opportunity | anomaly | trend
}
```

**Critic validates:** `signals[column][field]` or `analysis_results[column][field]` against `claim["value"]` using `math.isclose`. No regex. No text parsing.

**CriticVerdict shape:**
```python
class CriticVerdict(BaseModel):
    approved: bool
    rejected_claims: List[str]  # field names that failed validation
```

One `CriticVerdict` per finding. The `rejected_claims` list identifies which specific fields failed — this list is threaded forward to the Analyst in the next Ralph Loop iteration (CRIT-05).

### 2. Numeric tolerance — `math.isclose(rel_tol=0.01, abs_tol=0.001)`

Relative 1% tolerance with an absolute floor of 0.001 for near-zero values. Implementation:
```python
import math
math.isclose(claim_value, signal_value, rel_tol=0.01, abs_tol=0.001)
```

This handles mixed scales (ratios near 0–1 and large dollar amounts) without false rejections from floating-point rounding.

### 3. Legacy `suggest_investigations()` — DELETE in Phase 2

`insight/critic.py` currently contains `suggest_investigations()` — a deterministic function that recommends next analysis actions based on signal flags. This function is replaced by the LLM Analyst (Phase 4).

**Action:** Delete `suggest_investigations()` entirely in Phase 2. The file becomes the `CriticVerdict` validator only. No legacy preservation — Phase 4 owns investigation strategy.

### 4. Module placement (Claude's Discretion — confirmed)

- `CriticVerdict` BaseModel → `agents/schemas.py` (new package, as noted in STATE.md)
- Critic validation logic → `insight/critic.py` (extended in place, old function deleted)
- `agents/__init__.py` created as empty module marker

### 5. Inherited decisions (locked from prior phases / STATE.md)

- **Zero API calls** — Critic must pass with `GROQ_API_KEY` unset. No network calls of any kind.
- **Dict comparison only** — "LLM-vs-LLM rephrases claims, not grounds them; dict comparison is the only grounding strategy" (STATE.md Active Decision)
- **Pydantic BaseModel for CriticVerdict** — `model_validate_json()` round-trip must pass (CRIT-04 success criterion)
- **Breaking change to `insight/critic.py`** — planned and expected; no backwards compat required

---

## Canonical Refs

- `.planning/ROADMAP.md` — Phase 2 goal and success criteria (CRIT-01 through CRIT-05)
- `.planning/REQUIREMENTS.md` — CRIT-01, CRIT-02, CRIT-03, CRIT-04, CRIT-05
- `.planning/STATE.md` — Active decisions: Deterministic Critic strategy, breaking change note
- `insight/critic.py` — File to be extended; `suggest_investigations()` to be deleted
- `state/runtime_state.py` — `AgentState` TypedDict; Critic reads `signals` and `analysis_results` keys
- `agents/` — New directory to create; `schemas.py` holds `CriticVerdict` and future agent schemas

---

## Out of Scope (this phase)

- LLM Analyst — Phase 4
- Ralph Loop iteration logic — Phase 3
- Wiring Critic into the orchestrator — Phase 5
- Global synthesizer — Phase 6
- Any API call, retry logic, or Groq integration

---

## Deferred Ideas

None surfaced during discussion.

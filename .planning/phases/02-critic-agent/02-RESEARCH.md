# Phase 02: Critic Agent - Research

**Researched:** 2026-03-28
**Domain:** Pydantic v2 BaseModel, deterministic claim validation, Python stdlib `math.isclose`
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **Claim structure — Option A: Structured finding dict**
   Each finding is a dict with explicit `claims` list. Each claim has `{"field": str, "value": float}`.
   Critic validates via `signals[column][field]` or `analysis_results[column][field]` dict lookup.
   No regex. No text parsing.

2. **Numeric tolerance — `math.isclose(rel_tol=0.01, abs_tol=0.001)`**
   Relative 1% tolerance with absolute floor 0.001 for near-zero values.

3. **Legacy `suggest_investigations()` — DELETE in Phase 2**
   The function is removed entirely. No backwards compat. Phase 4 owns investigation strategy.

4. **Module placement (confirmed)**
   - `CriticVerdict` BaseModel → `agents/schemas.py` (new package)
   - Critic validation logic → `insight/critic.py` (extended in place, old function deleted)
   - `agents/__init__.py` created as empty module marker

5. **Inherited: Zero API calls**
   Critic must pass with `GROQ_API_KEY` unset. No network calls of any kind.

6. **Inherited: Dict comparison only**
   "LLM-vs-LLM rephrases claims, not grounds them; dict comparison is the only grounding strategy" (STATE.md Active Decision).

7. **Inherited: Pydantic BaseModel for CriticVerdict**
   `model_validate_json()` round-trip must pass (CRIT-04 success criterion).

8. **Breaking change to `insight/critic.py` is expected** — no backwards compat required.

### Claude's Discretion

None surfaced — all structural decisions are locked.

### Deferred Ideas (OUT OF SCOPE)

- LLM Analyst (Phase 4)
- Ralph Loop iteration logic (Phase 3)
- Wiring Critic into the orchestrator (Phase 5)
- Global synthesizer (Phase 6)
- Any API call, retry logic, or Groq integration
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CRIT-01 | Critic agent validates every LLM claim against deterministic signals before the finding is accepted | Dict lookup pattern with `math.isclose`; two-source lookup (signals + analysis_results) |
| CRIT-02 | Critic agent rejects any claim that cannot be traced to a value in `signals` or `analysis_results` | Key-miss branch: claim field not present in either source dict → rejected_claims append |
| CRIT-03 | Critic agent returns a structured `CriticVerdict` with approved flag and list of rejected claims | Pydantic v2 BaseModel with `approved: bool` and `rejected_claims: List[str]` |
| CRIT-04 | Critic agent is fully deterministic — no LLM call, no API dependency | Pure Python: `math.isclose`, dict access, Pydantic v2 — no network I/O |
| CRIT-05 | Rejected findings carry the Critic's `rejected_claims` list so the Analyst can address specific failures in next prompt | `CriticVerdict.rejected_claims` is the list the caller threads forward — no extra field needed |
</phase_requirements>

---

## Summary

Phase 2 is a small, well-scoped implementation task. The domain is Pydantic v2 BaseModel definition and Python stdlib dict/numeric validation — no new dependencies, no network I/O, no ambiguous design choices.

The existing `insight/critic.py` contains a single function (`suggest_investigations()`) that is being deleted outright. The file becomes the home for a new public function — call it `validate_finding()` or `critique_finding()` — that accepts a finding dict and a slice of `AgentState` signals, runs claim-by-claim dict lookup + `math.isclose`, and returns a `CriticVerdict` Pydantic model.

The new `agents/` package (directory + `__init__.py` + `schemas.py`) must be created before any imports from `insight/critic.py` can reference `CriticVerdict`. The `AgentState` in `state/runtime_state.py` is already stable from Phase 1; the Critic reads `state["signals"][column]` and `state["analysis_results"][column]` — both are `Dict[str, Any]` keyed by field name.

**Primary recommendation:** Create `agents/schemas.py` with `CriticVerdict`, rewrite `insight/critic.py` as a pure validation module with zero imports beyond stdlib and `agents.schemas`, and test every success criterion directly with pytest fixtures that inject synthetic signal dicts.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.12.5 (in requirements.txt) | `CriticVerdict` BaseModel, `model_validate_json()` | Already project dependency; v2 API is confirmed stable |
| math (stdlib) | Python 3 stdlib | `math.isclose()` for numeric tolerance | No import cost, exact semantics locked by decision |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing (stdlib) | Python 3 stdlib | `List`, `Dict`, `Any`, `Optional` type annotations | All type hints in `schemas.py` and `critic.py` |
| pytest | Already in dev environment | Unit tests for Critic | Existing `pytest.ini` targets `tests/` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `math.isclose` | `numpy.isclose` | numpy is available, but math.isclose is stdlib, zero-dependency, and the tolerance params are identical — math wins |
| Pydantic BaseModel | dataclass + `__post_init__` | Pydantic is already a project dep and CRIT-04 explicitly requires `model_validate_json()` |

**Installation:** No new packages needed. Pydantic 2.12.5 already in requirements.txt.

---

## Architecture Patterns

### Recommended Project Structure After Phase 2

```
agents/
├── __init__.py          # empty module marker
└── schemas.py           # CriticVerdict (and future agent schemas)

insight/
└── critic.py            # validate_finding() — replaces suggest_investigations()

tests/
├── test_state_schema.py      # existing (Phase 1)
├── test_temporal_profiler.py # existing (Phase 1)
└── test_critic.py            # new (Phase 2)
```

### Pattern 1: CriticVerdict Pydantic v2 BaseModel

**What:** A minimal Pydantic v2 model with two fields. It must survive `model_validate_json()` round-trip.
**When to use:** Constructed and returned by `validate_finding()` in every code path.

```python
# agents/schemas.py
from __future__ import annotations

from typing import List

from pydantic import BaseModel


class CriticVerdict(BaseModel):
    approved: bool
    rejected_claims: List[str]  # field names that failed validation
```

Round-trip verification:
```python
verdict = CriticVerdict(approved=True, rejected_claims=[])
assert CriticVerdict.model_validate_json(verdict.model_dump_json()) == verdict
```

Confidence: HIGH — verified against Pydantic v2 docs. `model_validate_json()` and `model_dump_json()` are the canonical v2 round-trip methods.

### Pattern 2: Claim Validation — Two-Source Dict Lookup

**What:** For each claim in a finding, look up the field value in `signals[column]` first, then `analysis_results[column]`. If neither has the key, the claim is rejected. If found, compare numerically with `math.isclose`.
**When to use:** The core loop inside `validate_finding()`.

```python
# insight/critic.py
from __future__ import annotations

import math
from typing import Any, Dict, List

from agents.schemas import CriticVerdict


def validate_finding(
    finding: Dict[str, Any],
    signals: Dict[str, Any],
    analysis_results: Dict[str, Any],
) -> CriticVerdict:
    """Validate a structured finding dict against computed signal values."""
    column: str = finding["column"]
    claims: List[Dict[str, Any]] = finding.get("claims", [])

    col_signals = signals.get(column, {})
    col_results = analysis_results.get(column, {})

    rejected: List[str] = []

    for claim in claims:
        field: str = claim["field"]
        claimed_value: float = float(claim["value"])

        # Two-source lookup: signals first, then analysis_results
        if field in col_signals:
            ground_truth = float(col_signals[field])
        elif field in col_results:
            ground_truth = float(col_results[field])
        else:
            # Field not found in either source — reject
            rejected.append(field)
            continue

        if not math.isclose(claimed_value, ground_truth, rel_tol=0.01, abs_tol=0.001):
            rejected.append(field)

    return CriticVerdict(
        approved=len(rejected) == 0,
        rejected_claims=rejected,
    )
```

### Pattern 3: Finding Dict Shape (consumed, not produced, by Phase 2)

The Critic reads findings but does not produce them. The finding shape (locked in CONTEXT.md Decision 1):

```python
{
    "column": "revenue",
    "claims": [
        {"field": "skewness", "value": 2.3},
        {"field": "missing_ratio", "value": 0.12}
    ],
    "narrative": "Revenue is highly skewed...",
    "business_label": "risk"
}
```

The Critic only reads `finding["column"]` and `finding["claims"]`. The `narrative` and `business_label` fields are passed through to the caller untouched — the Critic does not mutate the finding dict.

### Anti-Patterns to Avoid

- **Mutating the finding dict inside the Critic:** The Critic is a pure validator — it returns a verdict; it does not modify the finding or attach fields to it. Attachment of `rejected_claims` to findings is the orchestrator's responsibility (Phase 5).
- **Using `float(x) == float(y)` for numeric comparison:** Always use `math.isclose` with the locked tolerance. Direct equality fails on float rounding even for identical computations.
- **Catching `KeyError` to handle missing fields:** Use `.get()` with a default empty dict for the column lookup. Never let a missing column crash the Critic — return `approved=False` with all claims rejected instead.
- **Using `isinstance(value, (int, float))` as a guard without handling `None`:** Signal dicts may contain `None` for columns with all-missing values. Cast with `float()` inside a try/except `(TypeError, ValueError)` and reject the claim if the cast fails.
- **Importing `groq`, `openai`, or `httpx` anywhere in `insight/critic.py` or `agents/schemas.py`:** Violates CRIT-04. These modules must remain importable with `GROQ_API_KEY` unset.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured output validation | Custom dict-schema checker | Pydantic `BaseModel` | `model_validate_json()` is CRIT-04; Pydantic handles type coercion, serialization, and error messages |
| JSON round-trip testing | Manual `json.dumps` + `json.loads` + compare | `model_validate_json(verdict.model_dump_json())` | Pydantic v2 canonical round-trip is one method call each way |
| Numeric tolerance | Custom epsilon comparison | `math.isclose(rel_tol=0.01, abs_tol=0.001)` | Handles mixed scales (ratios near 0 and large dollar amounts) without custom logic |

**Key insight:** The entire Critic implementation is ~30 lines of pure Python. The complexity budget should go into thorough tests, not implementation. Every edge case (missing column, None value, non-numeric field, empty claims list) must be tested — not defended against with elaborate runtime logic.

---

## Existing Code Analysis: `insight/critic.py`

The current file contains one function: `suggest_investigations()`. It is:
- 62 lines
- Imports: `from __future__ import annotations`, `typing` only — no third-party deps
- Returns: `List[Dict[str, Any]]` — a list of suggested next-analysis action dicts
- Read access: `signals` dict and `analysis_results` dict (same sources the new Critic uses)

**Deletion plan:** The entire function body and its docstring are removed. The file docstring and `from __future__ import annotations` line remain. The new `validate_finding()` function and its imports replace the deleted content. No other file in the codebase imports `suggest_investigations()` — confirm with a grep before deletion.

The imports change from:
```python
from typing import Any, Dict, List
```
to:
```python
import math
from typing import Any, Dict, List
from agents.schemas import CriticVerdict
```

---

## Common Pitfalls

### Pitfall 1: `float()` cast on None values in signal dicts

**What goes wrong:** Signal dicts store computed statistics. If a column has all-null values, `signals[column]["skewness"]` may be `None` or `float("nan")`. Calling `float(None)` raises `TypeError`. Calling `math.isclose(nan, ...)` returns `False` but silently, which is misleading.

**Why it happens:** The profiler uses pandas which returns `NaN` for statistics on empty series; those propagate into the signal dict.

**How to avoid:** Wrap the `float()` cast in try/except `(TypeError, ValueError)`. If the cast fails, treat the signal value as "unavailable" and reject the claim.

**Warning signs:** `TypeError: float() argument must be a string or a real number, not 'NoneType'` in test output.

### Pitfall 2: Empty claims list — should return `approved=True`

**What goes wrong:** A finding with `"claims": []` (no numeric claims) could return `approved=False` if the logic defaults to False without running the loop.

**Why it happens:** The verdict is only `approved=True` when `rejected` is empty after the loop. An empty claims list means the loop never runs and `rejected` stays `[]` — so `approved=True`. This is correct behavior, but it needs an explicit test to confirm no off-by-one error exists.

**How to avoid:** Write a test case with `claims=[]` asserting `approved=True`. The current loop structure handles this correctly as long as `approved = len(rejected) == 0`.

### Pitfall 3: `agents/` directory not on Python path

**What goes wrong:** `from agents.schemas import CriticVerdict` fails with `ModuleNotFoundError` when running pytest from the project root if `agents/` is not recognized as a package.

**Why it happens:** `agents/` is a new directory. Without `agents/__init__.py`, Python does not treat it as a package. Additionally, `pytest.ini` must be in the root for sys.path resolution to work correctly.

**How to avoid:** Create `agents/__init__.py` (empty) as part of Wave 0 (directory + package scaffold). The existing `pytest.ini` at the project root already configures `testpaths = tests` — imports from `agents/` will resolve as long as pytest is run from the project root.

**Warning signs:** `ModuleNotFoundError: No module named 'agents'` on first test run.

### Pitfall 4: `analysis_results[column]` is a flat dict, not always nested

**What goes wrong:** Assuming `analysis_results[column]["skewness"]` is always a direct float. In practice, some analysis tools return nested dicts (e.g., `analysis_results["revenue"]["outlier_stats"]["z_score_count"]`). Flat field name lookup fails silently on nested structures.

**Why it happens:** The `analysis_results` dict is populated by multiple tool functions with inconsistent depth.

**How to avoid:** In Phase 2, the Critic does only flat key lookup (`col_results.get(field)`). If the field is nested, the lookup returns `None` and the claim is rejected. Document this behavior explicitly — the Analyst (Phase 4) is responsible for forming claims against keys that actually exist at the top level of the results dict.

**Warning signs:** Claims that should match are rejected; inspection shows the value is nested one level deeper.

### Pitfall 5: `suggest_investigations()` is imported elsewhere

**What goes wrong:** Deleting `suggest_investigations()` breaks an import in another module, causing runtime `ImportError`.

**Why it happens:** The function was the original Critic API and may be referenced in the orchestrator or main entry point.

**How to avoid:** Grep for `suggest_investigations` across the entire codebase before deleting. If found, the import must be removed or redirected as part of the same plan task — not left for Phase 5.

---

## Code Examples

### `CriticVerdict` model_validate_json round-trip (CRIT-04)

```python
# Verified pattern — Pydantic v2 canonical round-trip
from agents.schemas import CriticVerdict

verdict = CriticVerdict(approved=False, rejected_claims=["skewness", "missing_ratio"])
serialized = verdict.model_dump_json()                          # '{"approved":false,"rejected_claims":["skewness","missing_ratio"]}'
restored = CriticVerdict.model_validate_json(serialized)
assert restored == verdict                                      # True
assert restored.approved is False
assert restored.rejected_claims == ["skewness", "missing_ratio"]
```

Confidence: HIGH — Pydantic v2 `model_dump_json()` / `model_validate_json()` are the documented canonical methods for JSON round-trip since v2.0.

### `math.isclose` boundary behavior

```python
import math

# Values within 1% relative tolerance — PASS
assert math.isclose(2.3, 2.3 * 1.009, rel_tol=0.01, abs_tol=0.001) is True

# Values outside 1% relative tolerance — FAIL
assert math.isclose(2.3, 2.3 * 1.02, rel_tol=0.01, abs_tol=0.001) is False

# Near-zero values — abs_tol=0.001 floor prevents false rejection
assert math.isclose(0.0, 0.0005, rel_tol=0.01, abs_tol=0.001) is True

# None value — must be caught before calling isclose
try:
    float(None)
except TypeError:
    # claim is rejected — None cannot be compared numerically
    pass
```

### Test fixture pattern (matches existing project test style)

```python
# tests/test_critic.py — follows pattern established in test_temporal_profiler.py
from __future__ import annotations

import pytest
from agents.schemas import CriticVerdict
from insight.critic import validate_finding


def _make_signals() -> dict:
    return {
        "revenue": {
            "skewness": 2.3,
            "missing_ratio": 0.12,
        }
    }


def _make_analysis_results() -> dict:
    return {
        "revenue": {
            "outlier_count": 5,
        }
    }


def test_approved_when_claim_matches_signal():
    finding = {
        "column": "revenue",
        "claims": [{"field": "skewness", "value": 2.3}],
        "narrative": "...",
        "business_label": "risk",
    }
    verdict = validate_finding(finding, _make_signals(), _make_analysis_results())
    assert verdict.approved is True
    assert verdict.rejected_claims == []


def test_rejected_when_claim_value_out_of_tolerance():
    finding = {
        "column": "revenue",
        "claims": [{"field": "skewness", "value": 9.9}],  # wrong value
        "narrative": "...",
        "business_label": "risk",
    }
    verdict = validate_finding(finding, _make_signals(), _make_analysis_results())
    assert verdict.approved is False
    assert "skewness" in verdict.rejected_claims


def test_rejected_when_field_not_in_signals_or_results():
    finding = {
        "column": "revenue",
        "claims": [{"field": "nonexistent_field", "value": 1.0}],
        "narrative": "...",
        "business_label": "risk",
    }
    verdict = validate_finding(finding, _make_signals(), _make_analysis_results())
    assert verdict.approved is False
    assert "nonexistent_field" in verdict.rejected_claims
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `model_validate` + `model_dump` (Pydantic v1 `.dict()`, `.parse_raw()`) | `model_validate_json()` + `model_dump_json()` (Pydantic v2) | Pydantic v2.0 (mid-2023) | Breaking change from v1; `.parse_raw()` is removed in v2 |
| `from pydantic import validator` | `from pydantic import field_validator` (v2) | Pydantic v2.0 | `@validator` decorator removed; use `@field_validator` in v2 |

**Deprecated/outdated:**
- `CriticVerdict.parse_raw(json_str)`: Pydantic v1 method — removed in v2. Use `CriticVerdict.model_validate_json(json_str)`.
- `verdict.dict()`: Pydantic v1 — use `verdict.model_dump()` in v2.
- `suggest_investigations()`: Deleted in this phase — no replacement in Phase 2 scope.

---

## Open Questions

1. **Does `suggest_investigations()` appear anywhere outside `insight/critic.py`?**
   - What we know: The function signature is only defined in `insight/critic.py`. A grep is required before deletion.
   - What's unclear: Whether the orchestrator (`orchestrator/`) or `main.py` calls it.
   - Recommendation: Wave 0 task — grep for `suggest_investigations` across the repo. If found, add a removal sub-task to the same plan.

2. **Should `validate_finding()` gracefully handle non-numeric claim values (e.g., `"value": "high"`)?**
   - What we know: CONTEXT.md Decision 1 shows all example claim values as floats. The locked decision says "numeric claims."
   - What's unclear: Whether the Analyst will ever emit a non-numeric claim value (e.g., a count or a string label).
   - Recommendation: Treat non-numeric `float()` cast failures as rejected claims. Document this behavior in the function docstring. Do not add special-case logic.

3. **Should `analysis_results[column]` lookup be a flat key lookup only, or should there be a depth-2 search?**
   - What we know: CONTEXT.md says "dict lookup" — implying flat.
   - What's unclear: Phase 4 Analyst may emit claims against nested keys.
   - Recommendation: Flat lookup only in Phase 2. Document the constraint. Phase 4 research will determine the correct claim structure for nested results.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | Yes | (project environment) | — |
| pydantic | `agents/schemas.py` CriticVerdict | Yes | 2.12.5 | — |
| math (stdlib) | `insight/critic.py` isclose | Yes | stdlib | — |
| pytest | `tests/test_critic.py` | Yes | in dev env (pytest.ini present) | — |
| GROQ_API_KEY | Critic module | Not required | — | Unset is the test condition |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None. All dependencies are satisfied.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (pytest.ini at project root) |
| Config file | `D:/Test/eda_agent/pytest.ini` — `testpaths = tests` |
| Quick run command | `pytest tests/test_critic.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CRIT-01 | Claim matching a signal value within tolerance → approved=True | unit | `pytest tests/test_critic.py::test_approved_when_claim_matches_signal -x` | No — Wave 0 |
| CRIT-01 | Claim sourced from analysis_results (not signals) → approved=True | unit | `pytest tests/test_critic.py::test_approved_when_claim_matches_analysis_results -x` | No — Wave 0 |
| CRIT-02 | Claim with field not in signals or analysis_results → approved=False, field in rejected_claims | unit | `pytest tests/test_critic.py::test_rejected_when_field_not_found -x` | No — Wave 0 |
| CRIT-02 | Claim with value outside tolerance → approved=False, field in rejected_claims | unit | `pytest tests/test_critic.py::test_rejected_when_value_out_of_tolerance -x` | No — Wave 0 |
| CRIT-03 | CriticVerdict is returned with both fields present | unit | `pytest tests/test_critic.py::test_verdict_has_approved_and_rejected_claims -x` | No — Wave 0 |
| CRIT-04 | `model_validate_json()` round-trip on approved verdict | unit | `pytest tests/test_critic.py::test_critic_verdict_json_roundtrip_approved -x` | No — Wave 0 |
| CRIT-04 | `model_validate_json()` round-trip on rejected verdict | unit | `pytest tests/test_critic.py::test_critic_verdict_json_roundtrip_rejected -x` | No — Wave 0 |
| CRIT-04 | Import `insight.critic` with GROQ_API_KEY unset — no ImportError or network call | unit | `pytest tests/test_critic.py::test_no_api_call_without_groq_key -x` | No — Wave 0 |
| CRIT-05 | rejected_claims list on a rejected verdict is non-empty and contains the failing field names | unit | `pytest tests/test_critic.py::test_rejected_claims_list_contains_field_names -x` | No — Wave 0 |

**Additional edge case tests (not mapped to a requirement ID but needed for correctness):**

| Behavior | Test Type | Note |
|----------|-----------|------|
| Empty claims list → approved=True | unit | Pitfall 2 |
| None value in signal dict → rejected | unit | Pitfall 1 |
| Multiple claims, one fails → approved=False, one field in rejected_claims | unit | Partial rejection |
| Multiple claims, all pass → approved=True, rejected_claims=[] | unit | Full approval |
| Column not in signals dict at all → all claims rejected | unit | Column-missing case |

### Sampling Rate

- **Per task commit:** `pytest tests/test_critic.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green (`pytest tests/ -x`) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_critic.py` — covers all CRIT-01 through CRIT-05 cases plus edge cases
- [ ] `agents/__init__.py` — empty file; required for `from agents.schemas import CriticVerdict` to resolve
- [ ] `agents/schemas.py` — `CriticVerdict` BaseModel definition

*(Framework install: not needed — pytest is already present per existing test infrastructure)*

---

## Sources

### Primary (HIGH confidence)

- Pydantic v2 official docs (`model_validate_json`, `model_dump_json`, `BaseModel`) — verified against pydantic==2.12.5 in requirements.txt
- Python docs: `math.isclose` — stdlib, unchanged since Python 3.5, behavior verified with local execution
- `state/runtime_state.py` — read directly; `AgentState.signals` and `AgentState.analysis_results` are `Dict[str, Dict[str, Any]]`
- `insight/critic.py` — read directly; `suggest_investigations()` is the sole function; no other imports
- `requirements.txt` — pydantic==2.12.5, no groq package present (confirms zero-API constraint is structurally enforced)
- `pytest.ini` — `testpaths = tests`; existing test pattern confirmed from `test_temporal_profiler.py`

### Secondary (MEDIUM confidence)

- `math.isclose(1.01, 1.0, rel_tol=0.01, abs_tol=0.001)` returns `True` — verified with local Python execution

### Tertiary (LOW confidence)

None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pydantic version read from requirements.txt; math from stdlib
- Architecture: HIGH — finding shape and CriticVerdict shape are locked in CONTEXT.md with explicit Python code
- Pitfalls: HIGH — derived from direct code inspection of `insight/critic.py` and `state/runtime_state.py`; edge cases are well-known Pydantic/float behaviors

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (Pydantic v2 API is stable; no fast-moving ecosystem changes)

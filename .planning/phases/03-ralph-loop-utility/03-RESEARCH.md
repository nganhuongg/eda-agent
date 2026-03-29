# Phase 3: Ralph Loop Utility — Research

**Researched:** 2026-03-29
**Domain:** Pure Python iterative refinement loop with callable injection, feedback threading, and bounded iteration
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** One generic function: `run_loop(generator_fn, critic_fn, max_iter=5)`. Gate 1 and Gate 2 are not separate functions — they pass different `critic_fn` callables to the same loop.
- **D-02:** Generator callable signature: `generator_fn(rejected_claims: List[str]) -> Any`. On iteration 0, an empty list is passed. On each subsequent iteration, the `rejected_claims` from the previous `CriticVerdict` are passed directly.
- **D-03:** `rejected_claims` from the previous `CriticVerdict` is passed to the next generator call as a flat `List[str]`. No accumulated history dict — only the most recent rejection set is forwarded.
- **D-04:** When the loop exits after `max_iter` iterations without approval, the result from the final iteration is returned. No tracking of "fewest rejected claims" across iterations.
- **D-05:** The Gate 2 quality bar checker is a function `quality_bar_critic(result) -> CriticVerdict` that lives in `orchestrator/ralph_loop.py`. It is the `critic_fn` argument passed to `run_loop()` for Gate 2. No separate `report/quality_checker.py` module.
- **D-06:** Three quality bar checks (LOOP-05):
  1. All findings have a `business_label` field present (non-empty)
  2. No unsupported numeric claims — all numeric claims in findings have a source in `signals` or `analysis_results`
  3. Findings are in ranked/sorted order (descending by a priority or score field)
- **Hard max 5 iterations** — `for i in range(5)`, never `while not approved:`
- **`CriticVerdict` shape is locked** — `approved: bool`, `rejected_claims: List[str]` (Phase 02)
- **`validate_finding()` in `insight/critic.py`** — this is the Gate 1 critic function; `run_loop()` receives it as `critic_fn`
- **File placement** — `orchestrator/ralph_loop.py` (new file in existing `orchestrator/` package)

### Claude's Discretion

None stated in CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)

None surfaced during discussion.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LOOP-01 | Investigation loop runs until Critic approves the insight batch or max iterations (5) reached | `run_loop()` with `for i in range(5)` pattern; exit on `verdict.approved` |
| LOOP-02 | Each loop iteration passes prior rejection feedback to the Analyst for the next attempt | `rejected_claims` threaded as function argument each iteration; empty list on iter 0 |
| LOOP-03 | Loop exits gracefully after max iterations with best available result, never blocking run completion | Return `last_result` after `range(max_iter)` exhaustion; no exception path |
| LOOP-04 | Output review loop runs after global synthesis until report quality bar is met or max iterations reached | Gate 2 passes `quality_bar_critic` as `critic_fn` to the same `run_loop()` |
| LOOP-05 | Quality bar checks: all findings have business labels, no unsupported numeric claims, ranked order present | `quality_bar_critic()` implements three deterministic checks; returns `CriticVerdict` |
</phase_requirements>

---

## Summary

Phase 3 delivers `orchestrator/ralph_loop.py` — a single-file Python module containing two public functions: `run_loop()` (the generic bounded loop) and `quality_bar_critic()` (the Gate 2 critic callable). The implementation is pure Python with no new dependencies; it composes directly with `CriticVerdict` from `agents/schemas.py` and the established callable-injection pattern already present in `orchestrator/orchestrator.py`.

The technical scope is narrow and well-specified: a for-loop over `range(max_iter)` that calls `generator_fn(rejected_claims)`, evaluates the result with `critic_fn`, breaks on approval, and returns the final result unconditionally. No accumulation, no history, no exception paths. `quality_bar_critic()` mirrors the deterministic style of `validate_finding()` — three sequential dict-inspection checks, each contributing field names to a `rejected_claims` list, finally constructing a `CriticVerdict`.

The test strategy follows the existing `test_critic.py` spy/mock pattern exactly: pass a mock `generator_fn` (a Python callable that records its call arguments) and a mock `critic_fn` (a callable that returns a pre-scripted sequence of verdicts). All LOOP-01 through LOOP-05 behaviors are verifiable purely through argument inspection and return-value assertions — no filesystem, no network, no LLM.

**Primary recommendation:** Implement `run_loop()` and `quality_bar_critic()` in a single file (`orchestrator/ralph_loop.py`), test with spy callables following `test_critic.py` patterns, and verify the three quality bar checks are deterministic and self-contained.

---

## Standard Stack

### Core (no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pydantic` | 2.12.5 (pinned in requirements.txt) | `CriticVerdict` model validation | Already locked; `CriticVerdict` imported from `agents/schemas.py` |
| `typing` | stdlib | `List`, `Any`, `Callable` type hints | Consistent with existing module style (`from __future__ import annotations`) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | 8.4.2 | Test framework | All new tests in `tests/test_ralph_loop.py` |

**No new packages required.** `orchestrator/ralph_loop.py` has zero imports beyond stdlib `typing` and the project-internal `agents.schemas.CriticVerdict`.

**Version verification:** All versions confirmed via `requirements.txt` and `pip show` — no registry lookup needed (no new packages).

---

## Architecture Patterns

### File Structure (new file only)

```
orchestrator/
├── orchestrator.py     # existing — do not modify in this phase
└── ralph_loop.py       # NEW — all Phase 3 deliverables live here

tests/
├── test_critic.py      # existing — reference for test patterns
└── test_ralph_loop.py  # NEW — LOOP-01 through LOOP-05 tests
```

No `__init__.py` is needed. The `orchestrator/` directory is already a namespace package — `import orchestrator.ralph_loop` resolves without one (confirmed: `import orchestrator.orchestrator` works today without `__init__.py`).

### Pattern 1: Bounded Loop with Callable Injection

The established pattern in `orchestrator/orchestrator.py` is `for step in range(1, max_steps + 1)`. Phase 3 applies the same discipline:

```python
# Source: orchestrator/orchestrator.py lines 74-129 (established pattern)
def run_loop(
    generator_fn: Callable[[List[str]], Any],
    critic_fn: Callable[[Any], CriticVerdict],
    max_iter: int = 5,
) -> Any:
    """Iterative refinement loop. Always exits within max_iter. Never raises."""
    rejected_claims: List[str] = []
    last_result: Any = None

    for _i in range(max_iter):
        last_result = generator_fn(rejected_claims)
        verdict: CriticVerdict = critic_fn(last_result)
        if verdict.approved:
            return last_result
        rejected_claims = verdict.rejected_claims

    return last_result
```

Key properties of this implementation:
- `range(max_iter)` is a hard ceiling — no while loop, satisfies Active Risk mitigation
- `last_result` is always defined after iter 0 — safe return after exhaustion (LOOP-03)
- On iter 0, `rejected_claims = []` — satisfies D-02 (empty list on first call)
- On iter N+1, `rejected_claims = verdict.rejected_claims` — satisfies D-03 (most recent only)
- Early return on approval — satisfies LOOP-01 (exits immediately on first approval)

### Pattern 2: Deterministic Quality Bar Critic (Gate 2)

Follows the same structure as `validate_finding()` in `insight/critic.py`: sequential checks, flat list accumulation, construct `CriticVerdict` at end. No LLM calls, no I/O.

```python
# Source: insight/critic.py lines 36-63 (structural model)
def quality_bar_critic(result: Any) -> CriticVerdict:
    """Gate 2 critic. Three deterministic quality checks. No API calls."""
    rejected: List[str] = []

    # Check 1 (LOOP-05): All findings have business_label (non-empty)
    findings = result.get("findings", []) if isinstance(result, dict) else []
    for i, f in enumerate(findings):
        if not f.get("business_label"):
            rejected.append(f"findings[{i}].business_label")

    # Check 2 (LOOP-05): No unsupported numeric claims
    signals = result.get("signals", {}) if isinstance(result, dict) else {}
    analysis_results = result.get("analysis_results", {}) if isinstance(result, dict) else {}
    for i, f in enumerate(findings):
        for claim in f.get("claims", []):
            field = claim.get("field", "")
            col = f.get("column", "")
            in_signals = field in signals.get(col, {})
            in_analysis = field in analysis_results.get(col, {})
            if not (in_signals or in_analysis):
                rejected.append(f"findings[{i}].claims.{field}")

    # Check 3 (LOOP-05): Findings in ranked/sorted order (descending by score/priority)
    scores = [f.get("score", f.get("priority", None)) for f in findings]
    numeric_scores = [s for s in scores if s is not None]
    if len(numeric_scores) > 1:
        if numeric_scores != sorted(numeric_scores, reverse=True):
            rejected.append("findings_order")

    return CriticVerdict(approved=len(rejected) == 0, rejected_claims=rejected)
```

**Note for planner:** The exact field names used by Gate 2 (`findings`, `claims`, `score`, `priority`) depend on the output schema produced by Phase 6's Global Synthesizer — which does not yet exist. The planner should stub these field names consistently with what Phase 6 will produce, or use a minimal agreed-upon contract. The three checks themselves (business label, numeric grounding, ranked order) are locked by D-06 and LOOP-05.

### Pattern 3: Spy/Mock Testing (from test_critic.py)

Phase 2 tests use lazy import and helper builder functions. Phase 3 tests use Python `unittest.mock.Mock` or simple counter callables to spy on `generator_fn` call arguments:

```python
# Mirrors test_critic.py structure — spy callable pattern
def test_loop_exits_on_approval():
    call_log = []

    def mock_generator(rejected_claims):
        call_log.append(rejected_claims)
        return {"findings": []}

    call_count = 0
    def mock_critic(result):
        nonlocal call_count
        call_count += 1
        return CriticVerdict(approved=(call_count >= 2), rejected_claims=["x"])

    result = run_loop(mock_generator, mock_critic, max_iter=5)
    assert call_count == 2   # exits immediately after first approval
    assert call_log[1] == ["x"]  # feedback threaded correctly
```

### Anti-Patterns to Avoid

- **`while not approved:`** — prohibited by Active Risk mitigation. The loop body must be `for i in range(max_iter)`. Any `while` loop is a defect.
- **`raise` on max-iter exhaustion** — LOOP-03 requires graceful return, never an exception. No `raise RuntimeError("max iterations exceeded")`.
- **Accumulating all prior `rejected_claims` into a growing list** — D-03 specifies only the most-recent rejection set is forwarded. `rejected_claims = verdict.rejected_claims` (replace, not extend).
- **Importing `validate_finding` directly inside `ralph_loop.py`** — the loop is generic; Gate 1's critic is passed in by the caller. Direct import couples the loop to Gate 1 and breaks the callable-injection design.
- **Initialising `last_result = None` and returning `None` path** — impossible if `range(max_iter)` has at least 1 iteration and `generator_fn` always returns something, but `max_iter=0` would return `None`. Guard against `max_iter < 1` or document the contract.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Callable type annotation | Custom Protocol or ABC | `Callable[[List[str]], Any]` from `typing` | stdlib covers it; no new import needed |
| Spy/mock for callable arguments | Hand-rolled recorder class | `unittest.mock.Mock` with `call_args_list` | Already in stdlib; test_critic.py pattern is simpler lambda/closure |
| JSON round-trip testing of CriticVerdict | Custom serializer | `CriticVerdict.model_validate_json(v.model_dump_json())` | Established in test_critic.py lines 93-99 |

**Key insight:** This phase adds zero new dependencies. The loop itself is 10-15 lines of pure Python. Complexity lives only in `quality_bar_critic()`, which is also pure dict inspection.

---

## Common Pitfalls

### Pitfall 1: Off-By-One on Iteration Count

**What goes wrong:** Test asserts "Critic never approves → loop runs exactly 5 times." If the loop is `for i in range(1, max_iter + 1)` (the orchestrator.py style) rather than `for i in range(max_iter)` (0-indexed), a test checking `call_count == 5` will still pass, but mixing styles causes confusion.

**Why it happens:** `orchestrator.py` uses `range(1, max_steps + 1)` so `step` is human-readable (1-indexed). The ralph loop has no use for the index variable — `for _i in range(max_iter)` is idiomatic and unambiguous.

**How to avoid:** Use `for _i in range(max_iter)` (underscore signals unused variable). Test with `max_iter=5` and a critic that never approves; assert `generator_fn` was called exactly 5 times.

**Warning signs:** `range(1, 6)` in the loop body, or a test that passes with `max_iter=5` but `call_count == 4`.

### Pitfall 2: Returning `None` When Generator Raises

**What goes wrong:** If `generator_fn` raises an exception on any iteration, `last_result` may be `None` and the except clause silently swallows the error.

**Why it happens:** Defensive `try/except` around the generator call is tempting but hides bugs.

**How to avoid:** Do NOT wrap the generator call in try/except. LOOP-03 says "never raises" — that guarantee is provided by the `for` loop terminating naturally, not by exception suppression. Let generator exceptions propagate; Phase 4 will handle retry at the Analyst level.

**Warning signs:** Any `try/except` block inside `run_loop()`.

### Pitfall 3: Gate 2 Check 2 Field Path Mismatch

**What goes wrong:** `quality_bar_critic()` looks up numeric claims using a field path (e.g., `result["findings"][i]["claims"]`) that doesn't match the actual output schema the Global Synthesizer will produce in Phase 6.

**Why it happens:** Phase 6's output schema doesn't exist yet. Assumptions made now may be wrong.

**How to avoid:** In Phase 3, test `quality_bar_critic()` against a minimal synthetic dict (not Phase 6's actual output). Use explicit, minimal keys. Document the assumed schema shape in a comment in `ralph_loop.py`. Phase 6 will adapt or the quality bar critic will be updated.

**Warning signs:** Tests that construct deeply nested result dicts to exercise quality_bar_critic — these may silently pass in Phase 3 but fail in Phase 6 if the key names drift.

### Pitfall 4: `orchestrator/` Package Without `__init__.py`

**What goes wrong:** Adding `from orchestrator.ralph_loop import run_loop` in another module fails with `ModuleNotFoundError` if the import path isn't resolved.

**Why it happens:** The directory is a namespace package (no `__init__.py`). This works for `import orchestrator.ralph_loop` but may not work in all Python configurations.

**How to avoid:** Verify the import works in the test environment using `py -c "import orchestrator.ralph_loop"` immediately after file creation. Confirmed today: `import orchestrator.orchestrator` works without `__init__.py` (namespace package resolution active). The same will work for `ralph_loop`.

**Warning signs:** `ModuleNotFoundError: No module named 'orchestrator'` in tests.

---

## Code Examples

### Minimal `run_loop()` Implementation

```python
# Source: Derived from orchestrator/orchestrator.py pattern (lines 74, established)
from __future__ import annotations

from typing import Any, Callable, List

from agents.schemas import CriticVerdict


def run_loop(
    generator_fn: Callable[[List[str]], Any],
    critic_fn: Callable[[Any], CriticVerdict],
    max_iter: int = 5,
) -> Any:
    rejected_claims: List[str] = []
    last_result: Any = None

    for _i in range(max_iter):
        last_result = generator_fn(rejected_claims)
        verdict: CriticVerdict = critic_fn(last_result)
        if verdict.approved:
            return last_result
        rejected_claims = verdict.rejected_claims

    return last_result
```

### Test Spy Pattern (from test_critic.py, adapted for run_loop)

```python
# Source: tests/test_critic.py — lazy import + helper function pattern
from agents.schemas import CriticVerdict


def _get_run_loop():
    from orchestrator.ralph_loop import run_loop  # noqa: PLC0415
    return run_loop


def test_exits_on_approval():
    run_loop = _get_run_loop()
    calls = []

    def gen(rejected_claims):
        calls.append(list(rejected_claims))
        return "result"

    verdicts = [
        CriticVerdict(approved=False, rejected_claims=["x"]),
        CriticVerdict(approved=True, rejected_claims=[]),
    ]
    verdict_iter = iter(verdicts)

    result = run_loop(gen, lambda r: next(verdict_iter), max_iter=5)
    assert result == "result"
    assert len(calls) == 2
    assert calls[0] == []       # iter 0: empty list
    assert calls[1] == ["x"]   # iter 1: prior rejected_claims
```

### `CriticVerdict` Usage (confirmed from agents/schemas.py)

```python
# Source: agents/schemas.py — exact field names
from agents.schemas import CriticVerdict

verdict = CriticVerdict(approved=True, rejected_claims=[])
# verdict.approved   → bool
# verdict.rejected_claims → List[str]
```

---

## Runtime State Inventory

This is a greenfield-within-existing-project phase — new file, no renames, no migrations.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — loop is stateless | None |
| Live service config | None | None |
| OS-registered state | None | None |
| Secrets/env vars | None — no API calls in this module | None |
| Build artifacts | None | None |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (py launcher) | All code | Yes | 3.x (via `py` launcher) | None needed |
| pytest | Test suite | Yes | 8.4.2 | None needed |
| pydantic | CriticVerdict | Yes | 2.12.5 | None — pinned in requirements.txt |

**Run command confirmed:** `py -m pytest tests/test_ralph_loop.py -q`

**Note on python executable:** The system has two Python installs. The MSYS2 `python` does not have the project's packages. Always use `py -m pytest` (Windows py launcher), not `python -m pytest`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 |
| Config file | `pytest.ini` (project root) — `testpaths = tests` |
| Quick run command | `py -m pytest tests/test_ralph_loop.py -q` |
| Full suite command | `py -m pytest tests/ -q --ignore=tests/test_temporal_profiler.py` |

Note: `tests/test_temporal_profiler.py` currently has a collection error (confirmed). Run critic + state schema + ralph_loop tests; temporal profiler tests are excluded until that issue is resolved separately.

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LOOP-01 | Loop exits immediately when critic returns `approved=True` | unit | `py -m pytest tests/test_ralph_loop.py::test_exits_on_approval -x` | No — Wave 0 |
| LOOP-01 | Loop runs all 5 iterations when critic never approves | unit | `py -m pytest tests/test_ralph_loop.py::test_max_iter_never_approves -x` | No — Wave 0 |
| LOOP-02 | Iteration N+1 receives `rejected_claims` from iteration N's verdict | unit | `py -m pytest tests/test_ralph_loop.py::test_feedback_threading -x` | No — Wave 0 |
| LOOP-02 | Iteration 0 receives empty `rejected_claims` list | unit | `py -m pytest tests/test_ralph_loop.py::test_first_iter_empty_rejected -x` | No — Wave 0 |
| LOOP-03 | Exhausted loop returns last result, never raises | unit | `py -m pytest tests/test_ralph_loop.py::test_no_exception_on_exhaustion -x` | No — Wave 0 |
| LOOP-04 | Gate 2: `quality_bar_critic` passed as `critic_fn` to same `run_loop` | unit | `py -m pytest tests/test_ralph_loop.py::test_gate2_uses_run_loop -x` | No — Wave 0 |
| LOOP-05 | `quality_bar_critic` rejects result missing business_label | unit | `py -m pytest tests/test_ralph_loop.py::test_qbc_missing_business_label -x` | No — Wave 0 |
| LOOP-05 | `quality_bar_critic` rejects result with unsupported numeric claim | unit | `py -m pytest tests/test_ralph_loop.py::test_qbc_unsupported_numeric -x` | No — Wave 0 |
| LOOP-05 | `quality_bar_critic` rejects result with findings out of ranked order | unit | `py -m pytest tests/test_ralph_loop.py::test_qbc_unranked_order -x` | No — Wave 0 |
| LOOP-05 | `quality_bar_critic` approves result passing all three checks | unit | `py -m pytest tests/test_ralph_loop.py::test_qbc_all_pass -x` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `py -m pytest tests/test_ralph_loop.py -q`
- **Per wave merge:** `py -m pytest tests/test_ralph_loop.py tests/test_critic.py tests/test_state_schema.py -q`
- **Phase gate:** Full passing suite (excluding temporal profiler collection error) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_ralph_loop.py` — covers LOOP-01 through LOOP-05 (all 10 tests above)
- [ ] `orchestrator/ralph_loop.py` — implementation file (empty shell needed for RED state)

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `while not approved:` loop | `for i in range(N):` bounded loop | Active design constraint from STATE.md | Eliminates infinite loop risk |
| Separate Gate 1 / Gate 2 loop functions | Single `run_loop()` with injected `critic_fn` | D-01 decision | Less duplication, easier testing |
| History accumulation (all prior rejections) | Most-recent-only `rejected_claims` | D-03 decision | Simpler to test, matches LOOP-02 semantics |

---

## Open Questions

1. **Gate 2 `quality_bar_critic()` input schema**
   - What we know: Result is whatever Phase 6's Global Synthesizer returns; must have `findings` list; each finding has `business_label`, `claims`, and some score/priority field
   - What's unclear: Exact field names (`score` vs `priority` vs `risk_score`), exact claims structure, whether `signals`/`analysis_results` are nested inside the result or accessed separately
   - Recommendation: In Phase 3, define `quality_bar_critic()` against a minimal assumed schema (documented in a comment), tested with synthetic dicts. Phase 6 updates the critic to match actual output — this is acceptable coupling because D-05 explicitly places quality_bar_critic in Phase 3's file, and Phase 6 will touch it.

2. **`max_iter` default value exposure**
   - What we know: Default is 5 per D-01; `range(5)` is the hard ceiling per STATE.md
   - What's unclear: Whether callers (Phase 5, Phase 6) override `max_iter` or always use the default
   - Recommendation: Default `max_iter=5` is correct. Do not make it a constant (no `MAX_ITER = 5` module-level var unless callers need to import it). Callers that need to test with fewer iterations will pass it explicitly.

---

## Project Constraints (from CLAUDE.md)

No `CLAUDE.md` found in project root. No project-specific coding constraints beyond those documented in STATE.md and CONTEXT.md.

**Constraints from STATE.md Active Risks (treated as directives):**

- Ralph Loop MUST use `for i in range(5)`, never `while not approved:` — unbounded loop is an active risk
- `df` (DataFrame) MUST NOT reach any agent module — `ralph_loop.py` must not accept or pass DataFrames
- Phase 5 (Orchestrator Restructure) has highest regression risk — Phase 3 tests must not modify `orchestrator.py`

---

## Sources

### Primary (HIGH confidence)

- `orchestrator/orchestrator.py` — established `for step in range(N)` pattern, `ACTION_TO_TOOL` callable injection (project source, inspected directly)
- `agents/schemas.py` — `CriticVerdict(approved: bool, rejected_claims: List[str])` confirmed field names (project source, inspected directly)
- `insight/critic.py` — deterministic check structure, two-source lookup pattern (project source, inspected directly)
- `tests/test_critic.py` — lazy import pattern, helper builder functions, spy callable idiom (project source, inspected directly)
- `pytest.ini` — `testpaths = tests`, `py -m pytest` confirmed working (environment verified directly)
- `requirements.txt` — all package versions verified (no new dependencies needed)
- `.planning/phases/03-ralph-loop-utility/03-CONTEXT.md` — all locked decisions (canonical upstream input)
- `.planning/STATE.md` — Active Risks section, `for i in range(5)` mandate (project decision log)

### Secondary (MEDIUM confidence)

None — all findings derive from direct project source inspection. No external sources required for this phase.

### Tertiary (LOW confidence)

None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; all libraries confirmed present in requirements.txt and verified in environment
- Architecture: HIGH — `run_loop()` structure derived directly from established orchestrator pattern; `quality_bar_critic()` structure derived directly from `validate_finding()` pattern
- Pitfalls: HIGH — off-by-one, exception suppression, field name drift are well-understood risks for this pattern; confirmed against project source
- Test mapping: HIGH — test names and commands derived from requirement semantics; pattern confirmed from test_critic.py

**Research date:** 2026-03-29
**Valid until:** 2026-04-29 (stable internal domain — no external API dependencies, no fast-moving ecosystem)

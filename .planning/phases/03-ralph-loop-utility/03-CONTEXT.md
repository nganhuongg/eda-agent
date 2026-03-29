---
phase: 03-ralph-loop-utility
created: 2026-03-29
status: ready
---

# Phase 03: Ralph Loop Utility — Context

## Domain

Build a shared iterative refinement utility (`orchestrator/ralph_loop.py`) that gates generation on Critic approval, threads `rejected_claims` feedback forward each iteration, and always exits within the iteration cap (5). Two gate variants are delivered in this phase: Gate 1 (investigation checkpoint) and Gate 2 (output review checkpoint with quality bar rules).

---

## Implementation Decisions

### Loop Interface — Single generic `run_loop()`

**D-01:** One generic function: `run_loop(generator_fn, critic_fn, max_iter=5)`. Gate 1 and Gate 2 are not separate functions — they pass different `critic_fn` callables to the same loop.

Rationale: LOOP-01 through LOOP-03 describe identical mechanics for both gates. Duplicating the loop logic in two functions creates a maintenance risk. The two gates differ only in what "Critic" means — that difference belongs in the caller, not in the loop.

**D-02:** Generator callable signature: `generator_fn(rejected_claims: List[str]) -> Any`. On iteration 0, an empty list is passed. On each subsequent iteration, the `rejected_claims` from the previous `CriticVerdict` are passed directly.

### Feedback Threading — Flat list as argument

**D-03:** `rejected_claims` from the previous `CriticVerdict` is passed to the next generator call as a flat `List[str]`. No accumulated history dict — only the most recent rejection set is forwarded.

Rationale: LOOP-02 specifies "prior rejection feedback," singular. The LLM Analyst needs to know what failed in the last attempt, not all prior history. Simpler to test — inspect the args to the generator callable at iteration N+1.

### Best-Attempt Selection — Last attempt

**D-04:** When the loop exits after `max_iter` iterations without approval, the result from the final iteration is returned. No tracking of "fewest rejected claims" across iterations.

Rationale: Each iteration incorporates the previous rejection feedback, so the last attempt is the most-informed one. LOOP-03 requires the loop never raises and always returns — "last attempt" is always well-defined with no bookkeeping overhead.

### Gate 2 Quality Checker — Inline in `ralph_loop.py`

**D-05:** The Gate 2 quality bar checker is a function `quality_bar_critic(result) -> CriticVerdict` that lives in `orchestrator/ralph_loop.py`. It is the `critic_fn` argument passed to `run_loop()` for Gate 2. No separate `report/quality_checker.py` module.

**D-06:** The three quality bar checks (per LOOP-05):
1. All findings have a `business_label` field present (non-empty)
2. No unsupported numeric claims — all numeric claims in findings have a source in `signals` or `analysis_results`
3. Findings are in ranked/sorted order (descending by a priority or score field)

Rationale: The quality checker is the Gate 2 critic — it belongs with the loop. Extracting it to a separate module would fragment Phase 3's scope with no decoupling benefit. Phase 6 can extract it if the logic grows.

### Inherited Decisions (locked from prior phases)

- **Hard max 5 iterations** — `for i in range(5)`, never `while not approved:` (Active Risk mitigation from STATE.md)
- **`CriticVerdict` shape is locked** — `approved: bool`, `rejected_claims: List[str]` (Phase 02)
- **`validate_finding()` in `insight/critic.py`** — this is the Gate 1 critic function; `run_loop()` receives it as `critic_fn`
- **File placement** — `orchestrator/ralph_loop.py` (noted in STATE.md Technical Notes)

---

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/ROADMAP.md` — Phase 3 goal and success criteria (LOOP-01 through LOOP-05)
- `.planning/REQUIREMENTS.md` — LOOP-01, LOOP-02, LOOP-03, LOOP-04, LOOP-05

### Existing Agent Contracts
- `agents/schemas.py` — `CriticVerdict(BaseModel)` with `approved: bool` and `rejected_claims: List[str]`
- `insight/critic.py` — `validate_finding(finding, signals, analysis_results) -> CriticVerdict` — this is Gate 1's `critic_fn`

### State & Orchestrator Patterns
- `state/runtime_state.py` — `AgentState` TypedDict; loop result integrates into state
- `orchestrator/orchestrator.py` — `run_agent()` shows the established `for step in range(1, max_steps + 1)` pattern and action recording style
- `.planning/STATE.md` — Active Risks section: "Unbounded Ralph Loop" mitigation rule

### Existing Tests (patterns to follow)
- `tests/test_critic.py` — Phase 2 test structure; mock patterns for testing deterministic agents

---

## Existing Code Insights

### Reusable Assets
- `CriticVerdict` (`agents/schemas.py`): ready to use as loop's exit condition carrier — `verdict.approved` gates the loop, `verdict.rejected_claims` is threaded to the next generator call
- `validate_finding()` (`insight/critic.py`): the concrete Gate 1 critic function — `run_loop()` receives it as a callable, never imports it directly inside the loop body

### Established Patterns
- Bounded iteration: `orchestrator.py` uses `for step in range(1, max_steps + 1)` — same pattern applies to `run_loop()`
- Callable injection: `ACTION_TO_TOOL` dict in `orchestrator.py` — the same dispatch-via-callable pattern applies to critic_fn and generator_fn
- Test spy pattern (from Phase 2 test_critic.py): mock callables that record call arguments — used to verify feedback threading in loop tests

### Integration Points
- `orchestrator/ralph_loop.py` is a new file in the existing `orchestrator/` package — no `__init__.py` changes needed (package already exists)
- Phase 5 (Orchestrator Restructure) will call `run_loop()` with the real LLM Analyst as generator_fn — Phase 3 tests use mocked generator callables only

---

## Specific Ideas

No specific UI/UX references. The loop is a pure Python utility — correctness and testability are the only aesthetic concerns.

---

## Deferred Ideas

None surfaced during discussion.

---

*Phase: 03-ralph-loop-utility*
*Context gathered: 2026-03-29*

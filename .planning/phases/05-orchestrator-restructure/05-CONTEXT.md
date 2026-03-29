---
phase: 05-orchestrator-restructure
created: 2026-03-29
status: ready
---

# Phase 05: Orchestrator Restructure — Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewire `orchestrator/orchestrator.py` so `run_agent()` routes each high-risk column through an Analyst+Critic investigation loop (Ralph Loop Gate 1) instead of calling `generate_insight_for_column()` directly. The df boundary is enforced structurally: `df` reaches only analysis tools, never agent modules.

Phase 5 also extends `AgentState` with an `analyst_decisions` key to store `AnalystDecision` objects, while keeping `state["insights"]` populated for backward compatibility with the v2 report generator.

This phase covers no exclusive requirements — it is the integration phase that wires Phases 2, 3, and 4 together and enables RPT-04 (v2 output contract).

</domain>

<decisions>
## Implementation Decisions

### D-01: Column-Based Outer Loop (replaces step-based)

Replace the current `for step in range(max_steps)` loop with a column-based loop:

```python
for _col_idx in range(max_columns):
    # 1. Refresh signals + risk scores
    state["signals"] = extract_signals(df, state["dataset_metadata"])
    state["risk_scores"] = compute_risk_scores(state["dataset_metadata"], state["signals"])

    # 2. Pick next high-risk unanalyzed column
    plan = risk_driven_planner(state)
    if plan is None:
        break  # No more columns to investigate
    column = plan["column"]

    # 3. Run analysis tools to populate analysis_results (tools-first)
    # 4. Run Analyst+Critic via run_loop (Gate 1)
    # 5. Store findings, mark column analyzed
```

`max_columns` = `config.get("MAX_COLUMNS", len(df.columns))` — reasonable upper bound, same spirit as old `max_steps`.

`risk_driven_planner(state)` is still used for column selection — it returns the highest-risk unanalyzed column. The `plan["action"]` field is ignored in Phase 5 (tools are now run deterministically by column type).

### D-02: Tools-First Execution

For each column, run analysis tools BEFORE the Analyst+Critic loop. This populates `state["analysis_results"][column]` so the Critic can validate AnalystDecision claims against both signals AND tool outputs.

**Tools to run per column type (Claude's discretion on exact tool set):**
- Numeric: `analyze_distribution` + `detect_outliers` (minimum; `analyze_missing_pattern` optional)
- Categorical: `analyze_missing_pattern` (minimum; others optional)
- All: at Claude's discretion — run at least 2 tools per column for multi-angle coverage (SYNTH-01 groundwork)

df is passed to tools here and **nowhere else** in the new loop. This is the structural df boundary.

### D-03: `analyst_decisions` — New AgentState Key

Add `analyst_decisions: Dict[str, AnalystDecision]` to `AgentState` TypedDict in `state/runtime_state.py`:

```python
class AgentState(TypedDict):
    # ... existing keys unchanged ...
    analyst_decisions: Dict[str, Any]  # AnalystDecision objects keyed by column
```

Use `Dict[str, Any]` to avoid circular imports (AnalystDecision lives in `agents/`).

`initialize_state()` adds `"analyst_decisions": {}`.

### D-04: Backward-Compatible `state["insights"]` Population

After `run_loop()` returns an `AnalystDecision`, populate `state["insights"][column]` in a format compatible with the existing report generator:

```python
state["analyst_decisions"][column] = decision
state["insights"][column] = {
    "summary": decision.narrative,
    "category": decision.business_label,
    "column": decision.column,
    "hypothesis": decision.hypothesis,
    "recommended_tools": decision.recommended_tools,
}
```

This preserves `state["insights"]` for `report/report_generator.py`, `visualization/plot_generator.py`, and `main.py` — all v2 output contract consumers. Phase 6 will replace this bridge with the full synthesizer.

### D-05: Gate 1 critic_fn — `validate_finding` Wrapper

Wrap `insight.critic.validate_finding()` as the `critic_fn` argument to `run_loop()`. The wrapper converts `AnalystDecision` → dict format expected by `validate_finding`:

```python
from functools import partial
from insight.critic import validate_finding

def _make_gate1_critic(state: AgentState, column: str):
    def critic_fn(decision: AnalystDecision) -> CriticVerdict:
        finding = {"column": decision.column, "claims": decision.claims}
        return validate_finding(finding, state["signals"], state["analysis_results"])
    return critic_fn
```

Then in the loop:
```python
generator_fn = partial(analyze_column, state, column)
critic_fn = _make_gate1_critic(state, column)
decision = run_loop(generator_fn, critic_fn, max_iter=5)
```

### D-06: Exhaustion Logging

When `run_loop()` returns without Critic approval (exhausted 5 iterations), log a warning:

```python
# After run_loop returns:
verdict = _make_gate1_critic(state, column)(decision)
if not verdict.approved:
    logging.warning(
        "Gate 1 exhausted for column '%s' after 5 iterations — using best attempt", column
    )
```

Run continues to next column unconditionally (ROADMAP success criterion 3).

### D-07: df Boundary Smoke Test

Add a test `tests/test_orchestrator.py` (or extend existing test infrastructure) with a sentinel-df smoke test:

```python
def test_run_agent_df_boundary():
    """No agent module should receive a DataFrame. If df leaks, AnalystDecision import will fail."""
    # Create a state with sentinel signals
    # Monkeypatch analyze_column to assert its arguments contain no DataFrame
    # Run run_agent with a minimal 2-column CSV
    # Assert analyze_column was called and no pd.DataFrame appeared in its args
```

This satisfies ROADMAP success criterion 2.

### D-08: `run_agent` Signature Unchanged

`run_agent(state, df, config)` keeps the same signature. `main.py` requires no changes. The v2 call chain is preserved end-to-end.

### D-09: Return Value Shape

Return dict shape is preserved:
```python
return {
    "status": "SUCCESS" | "PARTIAL",
    "reason": "NO_PENDING_INVESTIGATIONS" | "MAX_COLUMNS_REACHED",
    "columns_analyzed": len(state["analyzed_columns"]),
    "total_columns": len(state["dataset_metadata"]),
}
```

### Inherited Decisions (locked from prior phases)

- **df boundary non-negotiable** — df never passed to llm_analyst, critic_agent, or insight_generator
- **`run_loop(generator_fn, critic_fn, max_iter=5)`** — Phase 3 interface; do not modify
- **`analyze_column(state, column, rejected_claims=[])`** — Phase 4 interface; use with `functools.partial`
- **`validate_finding(finding, signals, analysis_results)`** — Phase 2 interface
- **Hard max 5 iterations** — Phase 3 architecture
- **`CriticVerdict` shape locked** — Phase 2

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/ROADMAP.md` — Phase 5 goal and success criteria
- `.planning/REQUIREMENTS.md` — Integration phase; no exclusive requirements; enables RPT-04

### Existing Implementation (read before modifying)
- `orchestrator/orchestrator.py` — Current `run_agent()` and `ACTION_TO_TOOL` dict
- `orchestrator/ralph_loop.py` — `run_loop(generator_fn, critic_fn, max_iter)` interface
- `agents/llm_analyst.py` — `analyze_column(state, column, rejected_claims=[])` + `build_analyst_context()`
- `agents/schemas.py` — `AnalystDecision` and `CriticVerdict` schemas
- `insight/critic.py` — `validate_finding(finding, signals, analysis_results)` interface
- `state/runtime_state.py` — `AgentState` TypedDict + `initialize_state()`

### Consumers of state["insights"] (backward compat targets)
- `report/report_generator.py` — reads `state["insights"]` for report output
- `visualization/plot_generator.py` — reads `state["insights"]` for plot generation
- `main.py` — calls `run_agent()`, prints `state["insights"]`

### Project Constraints
- `.planning/STATE.md` — Active Risks: df boundary, unbounded loops; Active Decisions: raw openai SDK, deterministic Critic

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `orchestrator/orchestrator.py` → `ACTION_TO_TOOL` dict: 4 tool functions, still needed for tools-first execution
- `orchestrator/orchestrator.py` → `_record_action()`: keep for action history tracing
- `orchestrator/ralph_loop.py` → `run_loop()`: drop-in for Gate 1 — no changes needed
- `planning/risk_planner.py` → `risk_driven_planner(state)`: column selector — still used, `plan["action"]` ignored
- `agents/llm_analyst.py` → `analyze_column()`: the generator_fn for run_loop

### Established Patterns
- `functools.partial(analyze_column, state, column)` as `generator_fn` — documented in Phase 4 module docstring
- `for _i in range(max_iter)` not `while` — Phase 3 constraint on all loops
- Lazy imports for cross-package calls where circular import risk exists

### Integration Points
- `state/runtime_state.py` — add `analyst_decisions` key to TypedDict + initialize_state()
- `orchestrator/orchestrator.py` — rewire `run_agent()` loop body
- `tests/test_orchestrator.py` — new test file for df boundary smoke test + exhaustion behavior

### What NOT to change
- `run_loop()`, `quality_bar_critic()` — Phase 3, do not modify
- `validate_finding()` — Phase 2, do not modify
- `analyze_column()`, `build_analyst_context()` — Phase 4, do not modify
- `main.py` — signature unchanged
- `report/report_generator.py` — Phase 5 must stay compatible
- `AgentState` existing keys — add only; do not rename or remove

</code_context>

<specifics>
## Specific Ideas

- Phase 5 `run_agent()` is the last thing that touches `df` before the LLM layer. Once tools have run and `analysis_results` is populated, `df` is never needed again until `generate_insight_driven_plots()` in main.py (which is called after `run_agent` returns).
- The sentinel-df smoke test can be lightweight: monkeypatch `analyze_column` to inspect its kwargs, assert no pd.DataFrame appears.
- `_record_action()` can be kept for action history but adapted to log the new phases: "tools_run", "analyst_loop", "gate1_result".

</specifics>

<deferred>
## Deferred Ideas

None surfaced during discussion.

</deferred>

---

*Phase: 05-orchestrator-restructure*
*Context gathered: 2026-03-29*

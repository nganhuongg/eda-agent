# Phase 6: Global Synthesizer + Output Review — Research

**Researched:** 2026-03-29
**Domain:** Report generation, synthesis pipeline, Gate 2 Ralph Loop integration
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: Ranking Strategy — Pure Risk Score**
Rank all columns by `state["risk_scores"]` descending. Highest risk score = top of report.
No analyst-confidence weighting, no label-based grouping. The risk score is already
deterministic and computed by `risk_planner.py` — no new ranking logic needed.

**D-02: Unanalyzed Columns — Include with Note**
All columns appear in the report, ranked by risk score:
- Analyzed columns (have an `AnalystDecision`) → full structured paragraph
- Unanalyzed columns (below risk threshold or not reached) → brief note:
  `"Below risk threshold — not investigated"`

**D-03: Report Replacement Strategy — Replace generate_report()**
Phase 6 rewrites `report/report_generator.py`'s `generate_report()` function in-place
to produce the new ranked findings format. `main.py` requires no wiring changes — it
still calls `generate_report(state, result)`. No duplicate report files, no parallel paths.

**D-04: Report Section Structure**
```
# Risk-Driven EDA Report

## Executive Summary
- Coverage (columns analyzed / total)
- Run status and reason
- Date of analysis

## Ranked Findings
[For each column, ranked by risk_score descending:]

### [LABEL] Column: {column_name} (risk score: {score:.3f})
**Business label:** risk / opportunity / anomaly / trend
**Hypothesis:** {analyst_decision.hypothesis}
**Key signals:** {top 3-4 signal values}
**Finding:** {analyst_decision.narrative — one paragraph}

{Inline visualizations for this column, if any:}
![{Caption describing what the figure shows}](outputs/plots/{column}_{plot_type}.png)

---
[Columns without AnalystDecision:]
### Column: {column_name} (risk score: {score:.3f})
Below risk threshold — not investigated.

---

## Temporal Analysis
[Only if date column detected (state["temporal_signals"] is populated):]
- Trend directions per numeric column (up/down/flat + confidence)
- MoM and YoY deltas
- Forecasts (or explicit data-quality note if gated)

{Inline temporal visualizations, if any:}
![{Caption}](outputs/plots/{temporal_plot}.png)
```

Technical v2 sections (Signal Summary, Investigation History, Analysis Results) are
**removed** from the deterministic report. They will still be available via
`_build_llm_input_summary()` in `llm_report_writer.py` for LLM context.

**D-05: Inline Visualizations — Relative Markdown Path**
Visualizations are embedded inline within the section they belong to.
Format: `![{Caption text describing figure meaning}](outputs/plots/{filename}.png)`
Standard Markdown relative path — no base64 encoding.
Caption must describe what the figure shows (not just the filename).
`generate_insight_driven_plots()` is still called from `main.py` before `generate_report()`
— Phase 6 does not change plot generation, only where plots appear in the report.

**D-06: Multi-Angle Verification — Synthesizer Checks, No Re-investigation**
The synthesizer checks `len(state["analysis_results"].get(column, {}))`:
- If >= 2 tool results: full finding rendered normally
- If 1 tool result: finding rendered with inline note:
  `"⚠ Single analytical angle — distribution analysis only"`
- If 0 tool results: column listed as "Below risk threshold"
No re-running of tools from the synthesizer. The synthesizer never receives a DataFrame.

**D-07: Gate 2 generator_fn — Deterministic Re-sort**
`generator_fn` for Gate 2 = a function that takes the current `state` and produces a
findings list (list of dicts with `business_label`, `narrative`, `claims`) from
`state["analyst_decisions"]`. `quality_bar_critic()` checks this list against the three
quality bar rules. If it fails, the generator re-sorts or re-formats to satisfy the checks.
The LLM narrative (`generate_llm_report`) runs AFTER Gate 2 passes — it receives the
deterministic report as input, not the other way around.

**D-08: Gate 2 Integration Point**
Gate 2 runs inside the report writer, before writing to disk:
```python
# In generate_report():
from orchestrator.ralph_loop import run_loop, quality_bar_critic

findings_list = _build_findings_list(state)  # from analyst_decisions, ranked
reviewed_findings = run_loop(
    generator_fn=lambda: findings_list,
    critic_fn=quality_bar_critic,
    max_iter=5,
)
# Then render reviewed_findings to Markdown
```
Report is always written to disk regardless of Gate 2 outcome (LOOP-03 constraint).

### Inherited Decisions (locked from prior phases)

- **df boundary** — synthesizer and report writer never receive a DataFrame
- **`run_loop(generator_fn, critic_fn, max_iter=5)`** — Phase 3 interface; do not modify
- **`quality_bar_critic()`** — Phase 3 Gate 2 critic; do not modify
- **v2 output contract** — `outputs/report.md` + `outputs/plots/` always produced
- **MiniMax API** — `report/llm_report_writer.py` already uses OpenAI-compatible client
- **Hard max 5 iterations** — Phase 3 architecture, applies to Gate 2

### Claude's Discretion

None specified in CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)

None surfaced during discussion.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SYNTH-01 | Agent investigates each high-risk column from at least two analytical angles before synthesizing findings | Multi-angle check via `len(state["analysis_results"].get(column, {})) >= 2`; single-angle note exact string defined in D-06 |
| SYNTH-02 | Global synthesizer combines per-column findings into a unified ranked report before output review loop | `_build_findings_list()` helper reads `analyst_decisions` + `risk_scores`; Gate 2 via `run_loop()` with `quality_bar_critic` |
| RPT-01 | Final report ranks all findings by importance (highest-risk first) | `sorted(state["risk_scores"].items(), key=lambda x: -x[1])` — already used in existing `report_generator.py` |
| RPT-02 | Each finding includes a business label (risk / opportunity / anomaly / trend) | `AnalystDecision.business_label` Literal type already enforces valid values; rendered in report heading |
| RPT-03 | Report includes temporal section with trends, comparisons, forecasts when date column detected | Conditional on `state["temporal_signals"]` non-empty; data already in state from Phase 1 |
| RPT-04 | Report preserves v2 output format: `outputs/report.md` + `outputs/plots/` | Already complete; `generate_report()` writes to same path, `os.makedirs("outputs", exist_ok=True)` pattern established |
| RPT-05 | Optional LLM narrative `outputs/report_llm.md` generated via Groq when API key set | `generate_llm_report()` in `llm_report_writer.py` already guards on `MINIMAX_API_KEY`; preserve unchanged |
</phase_requirements>

---

## Summary

Phase 6 is the final delivery phase of the EDA agent v3 project. Its work is tightly scoped:
rewrite `report/report_generator.py`'s `generate_report()` function and extend
`synthesis/global_synthesizer.py` to produce a ranked, business-labelled report that passes
Gate 2 (the output review Ralph Loop). All dependencies are already implemented and tested
from prior phases (51 tests passing).

The key architectural constraint is that `generate_report()` must adapt its output dict shape
to match the `quality_bar_critic` contract from Phase 3: a dict with `"findings"`, `"signals"`,
and `"analysis_results"` keys, where each finding has `business_label`, `score`, `column`, and
`claims`. The Gate 2 `generator_fn` is a deterministic re-sort, not an LLM call — it resolves
any ordering or labelling violations by re-sorting the findings list.

The LLM narrative path (`generate_llm_report`) is entirely preserved. It already reads
`state["insights"]` (populated by Phase 5's backward-compat bridge), so no changes to
`llm_report_writer.py` are required. The only change to main.py call ordering is none — the
existing sequence `run_agent() → generate_insight_driven_plots() → generate_report() →
generate_llm_report()` is maintained exactly.

**Primary recommendation:** Write `_build_findings_list(state)` as the core helper — it
bridges `state["analyst_decisions"]` + `state["risk_scores"]` + `state["analysis_results"]` +
`state["signals"]` into the `quality_bar_critic` dict shape, then pass it through `run_loop()`
before rendering to Markdown.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.x | String formatting, os.makedirs, datetime | No new deps needed |
| pydantic | already installed | AnalystDecision schema already in use | Validated at Phase 4 |
| openai (SDK) | already installed | LLM report writer MiniMax client | Established in Phase 4 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | already installed | Test framework — 51 tests currently passing | All test files |
| unittest.mock | stdlib | Patching for Gate 2 tests | Stub `run_loop`, `quality_bar_critic` |

**No new dependencies required for Phase 6.** All libraries are already installed.

### Installation
```bash
# No new installs needed — existing requirements satisfied
```

---

## Architecture Patterns

### Recommended File Structure Changes
```
report/
├── report_generator.py      # REWRITE generate_report() in-place; add _build_findings_list()
synthesis/
├── global_synthesizer.py    # EXTEND generate_global_summary() — add ranked findings output
tests/
├── test_report_generator.py # NEW — covers SYNTH-01, SYNTH-02, RPT-01, RPT-02, RPT-03
```

### Pattern 1: _build_findings_list() — Bridge to quality_bar_critic Shape

**What:** Converts `state["analyst_decisions"]` (Dict[str, AnalystDecision]) into the list-of-dicts
shape that `quality_bar_critic` expects.

**When to use:** Called inside `generate_report()` before `run_loop()`.

**quality_bar_critic expected shape (from Phase 3 source):**
```python
# Source: orchestrator/ralph_loop.py lines 53-57
result = {
    "findings": [
        {
            "business_label": str,   # Check 1: must be truthy
            "score": float,          # Check 3: must be descending
            "column": str,
            "claims": [{"field": str, "value": Any}],  # Check 2: field must exist in signals/analysis_results
        }
    ],
    "signals": {col: {field: value}},           # passed through for Check 2
    "analysis_results": {col: {field: value}},  # passed through for Check 2
}
```

**Critical detail — claims must only reference existing fields:** The claims list in each
finding must contain only `{"field": ..., "value": ...}` dicts where `field` exists in
`state["signals"][column]` or `state["analysis_results"][column]`. The safest strategy is to
use `claims=[]` for all findings in `_build_findings_list()` (same strategy as the
deterministic fallback in Phase 4, per `claims=[] always in deterministic fallback` decision).
This guarantees Check 2 always passes. Check 1 is guaranteed by `AnalystDecision.business_label`
Literal type validation. Check 3 is guaranteed by sorting findings descending by risk score.

```python
# Pattern for _build_findings_list
def _build_findings_list(state):
    ranked = sorted(
        state["risk_scores"].items(),
        key=lambda x: -x[1]
    )
    findings = []
    for column, score in ranked:
        decision = state["analyst_decisions"].get(column)
        if decision is None:
            continue  # unanalyzed columns rendered separately, not in Gate 2 findings
        findings.append({
            "business_label": decision.business_label,
            "score": score,
            "column": column,
            "claims": [],  # safe: avoids Check 2 rejections
            "narrative": decision.narrative,
            "hypothesis": decision.hypothesis,
        })
    return {
        "findings": findings,
        "signals": state["signals"],
        "analysis_results": state["analysis_results"],
    }
```

### Pattern 2: Gate 2 Integration in generate_report()

**What:** Run `run_loop()` with deterministic generator and `quality_bar_critic` before rendering.

**Critical detail — run_loop signature:** The existing `run_loop(generator_fn, critic_fn, max_iter=5)`
passes `rejected_claims: List[str]` to `generator_fn` on each call. The `generator_fn` must accept
this argument even if it ignores it for the deterministic case:

```python
# Source: orchestrator/ralph_loop.py lines 8-38
# generator_fn signature: Callable[[List[str]], Any]
# NOT: Callable[[], Any]

# Correct pattern for Gate 2 generator_fn:
findings_data = _build_findings_list(state)
reviewed = run_loop(
    generator_fn=lambda rejected_claims: _build_findings_list(state),
    critic_fn=quality_bar_critic,
    max_iter=5,
)
```

**Note on D-08 code snippet in CONTEXT.md:** The snippet shows `generator_fn=lambda: findings_list`
(no argument) but `run_loop` always calls `generator_fn(rejected_claims)`. The lambda must accept
one positional argument. Use `lambda rejected_claims: _build_findings_list(state)` or
`lambda _: findings_data`.

### Pattern 3: Multi-Angle Check (SYNTH-01)

**What:** Before rendering a column's finding, check how many tools ran.

```python
tool_count = len(state["analysis_results"].get(column, {}))
if tool_count >= 2:
    # render full finding — no note
elif tool_count == 1:
    # render finding + exact string: "⚠ Single analytical angle — distribution analysis only"
else:
    # render: "Below risk threshold — not investigated"
```

**Exact string required by CONTEXT.md D-06 and specifics section:**
`"⚠ Single analytical angle — distribution analysis only"`

### Pattern 4: Temporal Section Rendering (RPT-03)

**What:** Conditional section in report, rendered only when `state["temporal_signals"]` is non-empty.

**What temporal_signals contains (from Phase 1):**
`state["temporal_signals"]` is a dict populated by `profile_temporal()`. When a date column is
present it contains trend directions, MoM/YoY deltas, forecasts (or data-quality gating notes),
and gap detection flags. When no date column is found, it is either empty or contains only the
skip-reason key.

```python
# Check from Phase 1 contract
if state.get("temporal_signals"):
    # Render temporal section
    # Include trend directions, MoM/YoY from temporal_signals values
```

### Pattern 5: Inline Visualization Matching

**What:** Find plots for a column from `state["visualizations"]` and embed them inline.

`state["visualizations"]` is a `Dict[str, str]` where keys follow the pattern
`{column}_{plot_type}` (e.g., `"revenue_distribution"`, `"revenue_boxplot"`) and values are
file paths like `"outputs/plots/revenue_distribution.png"`.

```python
# Find all plots for a column
column_plots = {
    key: path
    for key, path in state.get("visualizations", {}).items()
    if key.startswith(f"{column}_")
}
# Embed inline in Markdown
for key, path in column_plots.items():
    plot_type = key[len(column)+1:]  # e.g., "distribution"
    lines.append(f"![{column} {plot_type} plot]({path})")
```

### Anti-Patterns to Avoid

- **Passing a lambda with no args to run_loop:** `run_loop` always calls `generator_fn(rejected_claims)`.
  A zero-arg lambda will raise `TypeError`. Use `lambda _: ...` or `lambda rejected_claims: ...`.
- **Including numeric claims in `_build_findings_list`:** Any claim field not present in
  `state["signals"]` or `state["analysis_results"]` causes Check 2 rejection. Use `claims=[]`.
- **Blocking run on Gate 2 failure:** LOOP-03 guarantees the report is always written to disk.
  Do not gate file writing on `verdict.approved`.
- **Passing df to synthesizer or report generator:** The df boundary is structural — confirmed
  by Phase 5's sentinel-df smoke test. The report generator must never receive a DataFrame.
- **Modifying ralph_loop.py or quality_bar_critic:** These are Phase 3 completed code; do not touch.
- **Modifying llm_report_writer.py:** It already works; Phase 6 only ensures it is called after
  Gate 2 with the same `(state, result)` signature.
- **Modifying main.py call order:** The existing sequence is the correct wiring.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Iterative quality-gate loop | Custom while loop | `run_loop()` from `orchestrator/ralph_loop.py` | Phase 3 already built and tested; hard max_iter enforced |
| Quality bar validation | Custom checks | `quality_bar_critic()` from `orchestrator/ralph_loop.py` | Phase 3 already tested three checks; field names are contractual |
| LLM narrative generation | New LLM call | `generate_llm_report()` from `report/llm_report_writer.py` | Already uses OpenAI-compatible client with MiniMax key guard |
| Number formatting | Custom formatter | `_format_number()` in existing `report_generator.py` | Already handles float/non-float uniformly |
| Risk score computation | Re-compute | `state["risk_scores"]` (already computed by orchestrator) | Recomputing risks inconsistency |

**Key insight:** Phase 6 is almost entirely assembly — the hard infrastructure is done. The only
novel code is the report rendering logic and `_build_findings_list()` bridge helper.

---

## Common Pitfalls

### Pitfall 1: run_loop generator_fn Signature Mismatch

**What goes wrong:** `TypeError: <lambda>() takes 0 positional arguments but 1 was given`
at runtime when Gate 2 generator is called.

**Why it happens:** `run_loop` always calls `generator_fn(rejected_claims)` — see line 31 of
`ralph_loop.py`: `last_result = generator_fn(rejected_claims)`. D-08 in CONTEXT.md shows a
zero-arg lambda which is incorrect.

**How to avoid:** Always write `lambda rejected_claims: ...` or `lambda _: ...`.

**Warning signs:** Test passes in isolation (direct call) but fails inside `run_loop`.

### Pitfall 2: quality_bar_critic Claims Check Rejections

**What goes wrong:** Gate 2 never approves after 5 iterations; report written but quality bar
always failing Check 2.

**Why it happens:** Claims contain field names from AnalystDecision that don't exist in
`state["signals"][column]` or `state["analysis_results"][column]`.

**How to avoid:** Use `claims=[]` in `_build_findings_list()`. This is the established pattern
from Phase 4's deterministic fallback (see STATE.md: "claims=[] always in deterministic fallback").

**Warning signs:** `quality_bar_critic` returns `approved=False` with `rejected_claims`
containing `findings[N].claims.{field_name}` entries.

### Pitfall 3: Unanalyzed Columns in Gate 2 Findings List

**What goes wrong:** Gate 2 findings list includes columns that have no `AnalystDecision`,
causing `business_label` to be empty/None → Check 1 fails.

**Why it happens:** Iterating over all `risk_scores` rather than only `analyst_decisions`.

**How to avoid:** `_build_findings_list` skips columns not in `state["analyst_decisions"]`.
Unanalyzed columns are rendered separately in the Markdown (not part of Gate 2 findings).

**Warning signs:** `quality_bar_critic` returns `findings[N].business_label` in rejected_claims.

### Pitfall 4: Temporal Section Renders When temporal_signals is Empty Dict

**What goes wrong:** Report shows an empty "Temporal Analysis" section on datasets with no date
column, producing confusing output.

**Why it happens:** Checking `if "temporal_signals" in state:` rather than
`if state.get("temporal_signals"):`.

**How to avoid:** Use truthiness check `if state.get("temporal_signals"):` — an empty dict is falsy.

**Warning signs:** Report has empty `## Temporal Analysis` section for non-temporal CSVs.

### Pitfall 5: Visualization Path Mismatch

**What goes wrong:** Inline visualization links are broken (404 in Markdown viewer).

**Why it happens:** `state["visualizations"]` values are relative paths like
`"outputs/plots/revenue_distribution.png"` but the report is read from the project root.
The existing `report_generator.py` already uses this pattern (lines 78-80) and it works.

**How to avoid:** Use visualization paths exactly as stored in `state["visualizations"]` — do not
modify or re-derive them.

**Warning signs:** Markdown shows `![caption]()` with broken image links.

### Pitfall 6: Token Budget on Wide CSVs

**What goes wrong:** `_build_llm_input_summary()` builds a prompt with all columns' action history
and insights; on 100+ column CSVs this can exceed LLM context limits.

**Why it happens:** STATE.md active risks: "Token budget for wide CSVs (100+ columns)".

**How to avoid:** `_build_llm_input_summary()` already caps top risk columns at 8 and investigation
lines at 10 — this is Phase 4's existing code. Phase 6 does not need to add further capping unless
a specific wide-CSV test case is required. Document this as a known risk.

**Warning signs:** MiniMax API returns 400/context-length error on datasets with many columns.

---

## Code Examples

### Example 1: _build_findings_list() — Correct Shape for quality_bar_critic

```python
# Verified against orchestrator/ralph_loop.py quality_bar_critic expected shape (lines 53-87)
def _build_findings_list(state):
    ranked = sorted(
        state["risk_scores"].items(),
        key=lambda x: -x[1],
    )
    findings = []
    for column, score in ranked:
        decision = state["analyst_decisions"].get(column)
        if decision is None:
            continue
        findings.append({
            "business_label": decision.business_label,
            "score": score,
            "column": column,
            "claims": [],  # Safe: avoids Check 2 rejections
        })
    return {
        "findings": findings,
        "signals": state["signals"],
        "analysis_results": state["analysis_results"],
    }
```

### Example 2: Gate 2 run_loop Call — Correct Lambda Signature

```python
# Source: orchestrator/ralph_loop.py line 31 — generator_fn called as generator_fn(rejected_claims)
from orchestrator.ralph_loop import run_loop, quality_bar_critic

findings_data = _build_findings_list(state)
reviewed = run_loop(
    generator_fn=lambda rejected_claims: _build_findings_list(state),
    critic_fn=quality_bar_critic,
    max_iter=5,
)
# reviewed is the findings dict (last approved or last attempt after 5 iter)
```

### Example 3: Multi-Angle Note (SYNTH-01 exact string)

```python
# Source: CONTEXT.md D-06 and specifics section
tool_count = len(state["analysis_results"].get(column, {}))
if tool_count == 1:
    lines.append("> ⚠ Single analytical angle — distribution analysis only")
```

### Example 4: Column Section Header (D-04 format)

```python
# Source: CONTEXT.md D-04 report structure
label = decision.business_label.upper()
score = state["risk_scores"][column]
lines.append(f"### [{label}] Column: {column} (risk score: {score:.3f})")
lines.append(f"**Business label:** {decision.business_label}")
lines.append(f"**Hypothesis:** {decision.hypothesis}")
```

### Example 5: Executive Summary Section

```python
# Source: CONTEXT.md D-04 + orchestrator/orchestrator.py return dict shape (D-09)
import datetime
analyzed = summary.get("columns_analyzed", 0)
total = summary.get("total_columns", state["total_columns"])
lines.extend([
    "## Executive Summary",
    f"- **Coverage:** {analyzed}/{total} columns analyzed",
    f"- **Run status:** {summary.get('status', 'UNKNOWN')}",
    f"- **Reason:** {summary.get('reason', '')}",
    f"- **Date:** {datetime.date.today().isoformat()}",
    "",
])
```

### Example 6: Existing Test Pattern for report_generator Tests

```python
# Pattern: mirrors test_orchestrator.py fixture approach
def _make_minimal_state():
    from state.runtime_state import initialize_state
    state = initialize_state()
    state["risk_scores"] = {"revenue": 0.9, "category": 0.3}
    state["analyst_decisions"] = {
        "revenue": AnalystDecision(
            column="revenue", hypothesis="test", recommended_tools=[],
            business_label="risk", narrative="Revenue has outliers.", claims=[],
        )
    }
    state["analysis_results"] = {
        "revenue": {"analyze_distribution": {}, "detect_outliers": {}}
    }
    state["signals"] = {"revenue": {"mean": 50.0}}
    state["temporal_signals"] = {}
    state["visualizations"] = {}
    state["dataset_metadata"] = {
        "revenue": {"type": "numeric"}, "category": {"type": "categorical"}
    }
    return state
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Technical audit sections (Signal Summary, Investigation History, Analysis Results) in report | Removed from deterministic report; available via `_build_llm_input_summary()` only | Phase 6 | Report is now business-facing; technical detail still available for LLM |
| `generate_global_summary()` returns coverage ratio only | Extended to produce ranked findings list | Phase 6 | SYNTH-02 fulfilled |
| Visualizations listed as bullet points at end of report | Inline within column section immediately after finding | Phase 6 | D-05 fulfilled |

---

## Open Questions

1. **generate_global_summary() scope**
   - What we know: CONTEXT.md says "extend or replace" this function; it currently only computes coverage ratio
   - What's unclear: Whether SYNTH-02 is satisfied by extending `generate_global_summary()` to return findings, or whether `_build_findings_list()` inside `generate_report()` is sufficient
   - Recommendation: Keep `generate_global_summary()` as a coverage-only summary helper (preserve its existing callers if any); implement `_build_findings_list()` as a private helper in `report_generator.py`. The CONTEXT.md D-03 says "Phase 6 rewrites `generate_report()` in-place" — this is the primary target.

2. **state["columns_analyzed"] vs state["analyzed_columns"]**
   - What we know: `AgentState` TypedDict has `analyzed_columns: Set[str]` (runtime_state.py line 36). The `result` dict from `run_agent()` has `"columns_analyzed": len(state["analyzed_columns"])` (integer count).
   - What's unclear: Executive Summary coverage line uses `summary["columns_analyzed"]` (integer from result) vs `len(state["analyzed_columns"])` (set). Both give same value; use `summary["columns_analyzed"]` to match the existing `_build_llm_input_summary()` pattern.
   - Recommendation: Use `summary.get("columns_analyzed", 0)` and `summary.get("total_columns", state["total_columns"])` matching existing LLM report writer pattern.

---

## Environment Availability

All dependencies are pre-existing and verified by the 51-test suite passing.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pytest | Test suite | Yes | Installed | — |
| pydantic | AnalystDecision schema | Yes | Installed | — |
| openai SDK | llm_report_writer.py | Yes | Installed | — |
| python-dotenv | llm_report_writer.py | Yes | Installed | — |
| MiniMax API key | RPT-05 (LLM report) | Optional | — | Run exits cleanly with "missing_key" status |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | none — pytest discovers tests/ automatically |
| Quick run command | `python -m pytest tests/test_report_generator.py -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SYNTH-01 | Column with 1 tool result gets single-angle note; column with 2+ gets full finding | unit | `pytest tests/test_report_generator.py::test_single_angle_note -x` | Wave 0 |
| SYNTH-01 | Column with 0 tool results shows "Below risk threshold" text | unit | `pytest tests/test_report_generator.py::test_below_threshold_note -x` | Wave 0 |
| SYNTH-02 | _build_findings_list returns findings sorted descending by risk_score | unit | `pytest tests/test_report_generator.py::test_findings_list_ranked -x` | Wave 0 |
| SYNTH-02 | generate_report calls run_loop with quality_bar_critic | unit | `pytest tests/test_report_generator.py::test_gate2_called -x` | Wave 0 |
| RPT-01 | Report Ranked Findings section lists columns highest risk first | unit | `pytest tests/test_report_generator.py::test_ranked_order_in_report -x` | Wave 0 |
| RPT-02 | Every analyzed column section shows business_label | unit | `pytest tests/test_report_generator.py::test_business_label_present -x` | Wave 0 |
| RPT-03 | Temporal section present when temporal_signals non-empty | unit | `pytest tests/test_report_generator.py::test_temporal_section_present -x` | Wave 0 |
| RPT-03 | No temporal section when temporal_signals empty | unit | `pytest tests/test_report_generator.py::test_no_temporal_section -x` | Wave 0 |
| RPT-04 | generate_report writes outputs/report.md | unit | `pytest tests/test_report_generator.py::test_output_file_written -x` | Wave 0 |
| RPT-05 | generate_llm_report returns missing_key when MINIMAX_API_KEY unset | unit (existing) | `pytest tests/ -k "llm" -x` | Verify existing coverage |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_report_generator.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green (51 + new tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_report_generator.py` — covers SYNTH-01, SYNTH-02, RPT-01, RPT-02, RPT-03, RPT-04

*(No framework install needed — pytest already installed and 51 tests passing)*

---

## Sources

### Primary (HIGH confidence)
- `orchestrator/ralph_loop.py` — `run_loop()` and `quality_bar_critic()` implementation read directly; confirmed function signatures and expected dict shape
- `state/runtime_state.py` — `AgentState` TypedDict read directly; confirmed all fields Phase 6 reads
- `report/report_generator.py` — current `generate_report()` read directly; confirmed rewrite target
- `report/llm_report_writer.py` — current `generate_llm_report()` read directly; confirmed preserve-as-is
- `agents/schemas.py` — `AnalystDecision` schema read directly; confirmed `business_label` Literal type
- `orchestrator/orchestrator.py` — `run_agent()` return dict shape (D-09) confirmed
- `.planning/phases/06-global-synthesizer-output-review/06-CONTEXT.md` — all decisions read verbatim
- `.planning/REQUIREMENTS.md` — requirement texts read directly
- `tests/test_ralph_loop.py` — Phase 3 test patterns read; confirmed `_make_result` / `_make_finding` fixture shapes

### Secondary (MEDIUM confidence)
- `visualization/plot_generator.py` — `generate_insight_driven_plots()` return dict pattern confirmed (`{column}_{type}` key convention)
- `main.py` — call order confirmed; no wiring changes needed

### Tertiary (LOW confidence)
- None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all libraries verified by existing test suite
- Architecture: HIGH — all function signatures read from source; quality_bar_critic contract verified from Phase 3 code
- Pitfalls: HIGH — all identified from direct code reading (run_loop signature, claims shape, empty dict check)
- Test map: HIGH — test names and commands derived from requirement IDs and established project patterns

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable internal codebase — no external API changes expected)

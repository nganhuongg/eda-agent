# Phase 06: Global Synthesizer + Output Review — Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Take `state["analyst_decisions"]` (per-column findings from Phase 5) and produce a
ranked, labelled, Critic-reviewed report on disk. Three sub-components:

1. **Global Synthesizer** — combines per-column `AnalystDecision` objects into a ranked
   findings list using existing `state["risk_scores"]`
2. **Gate 2 Review Loop** — runs `quality_bar_critic()` via `run_loop()` until the report
   meets all three quality bar checks or 5 iterations are exhausted
3. **Report Writer** — replaces `generate_report()` with a new business-facing structured
   report in v2-compatible output format (`outputs/report.md`) with inline visualizations

Phase 6 also preserves the optional LLM narrative path (`outputs/report_llm.md`) via the
existing `report/llm_report_writer.py` which already uses MiniMax.

</domain>

<decisions>
## Implementation Decisions

### D-01: Ranking Strategy — Pure Risk Score

Rank all columns by `state["risk_scores"]` descending. Highest risk score = top of report.
No analyst-confidence weighting, no label-based grouping. The risk score is already
deterministic and computed by `risk_planner.py` — no new ranking logic needed.

### D-02: Unanalyzed Columns — Include with Note

All columns appear in the report, ranked by risk score:
- Analyzed columns (have an `AnalystDecision`) → full structured paragraph
- Unanalyzed columns (below risk threshold or not reached) → brief note:
  `"Below risk threshold — not investigated"`

Full coverage is visible; nothing silently dropped.

### D-03: Report Replacement Strategy — Replace generate_report()

Phase 6 rewrites `report/report_generator.py`'s `generate_report()` function in-place
to produce the new ranked findings format. `main.py` requires no wiring changes — it
still calls `generate_report(state, result)`. No duplicate report files, no parallel paths.

### D-04: Report Section Structure

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

### D-05: Inline Visualizations — Relative Markdown Path

Visualizations are embedded inline within the section they belong to:
- Findings for column `revenue` include its plots (distribution, trend, etc.) immediately
  after that column's paragraph
- Temporal section includes temporal plots inline

Format: `![{Caption text describing figure meaning}](outputs/plots/{filename}.png)`

Standard Markdown relative path — no base64 encoding. The caption must describe what
the figure shows (not just the filename), e.g.:
- `![Revenue distribution showing right-skewed outliers above 95th percentile](outputs/plots/revenue_distribution.png)`
- `![Monthly revenue trend — upward slope with 0.87 confidence](outputs/plots/revenue_trend.png)`

`generate_insight_driven_plots()` is still called from `main.py` before `generate_report()`
— Phase 6 does not change plot generation, only where plots appear in the report.

### D-06: Multi-Angle Verification — Synthesizer Checks, No Re-investigation

The synthesizer (or report generator) checks `len(state["analysis_results"].get(column, {}))`:
- If ≥ 2 tool results: full finding rendered normally
- If 1 tool result: finding rendered with inline note:
  `"⚠ Single analytical angle — distribution analysis only"`
- If 0 tool results: column listed as "Below risk threshold"

No re-running of tools from the synthesizer. The synthesizer never receives a DataFrame
(df boundary preserved from Phase 5).

### D-07: Gate 2 generator_fn — Deterministic Re-sort

The Gate 2 output review loop iterates a deterministic report builder, not an LLM call.

`generator_fn` for Gate 2 = a function that takes the current `state` and produces a
findings list (list of dicts with `business_label`, `narrative`, `claims`) from
`state["analyst_decisions"]`. `quality_bar_critic()` checks this list against the three
quality bar rules. If it fails, the generator re-sorts or re-formats to satisfy the checks.

The LLM narrative (`generate_llm_report`) runs AFTER Gate 2 passes — it receives the
deterministic report as input, not the other way around.

### D-08: Gate 2 Integration Point

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/ROADMAP.md` — Phase 6 goal and success criteria (SYNTH-01, SYNTH-02, RPT-01 through RPT-05)
- `.planning/REQUIREMENTS.md` — All Phase 6 requirements with traceability

### Synthesis and Report Layer
- `synthesis/global_synthesizer.py` — Current stub (coverage ratio only); Phase 6 rewrites this
- `report/report_generator.py` — Current v2 generate_report(); Phase 6 replaces this
- `report/llm_report_writer.py` — LLM narrative writer (MiniMax); preserve and call AFTER Gate 2

### Gate 2 (already implemented — read, do not modify)
- `orchestrator/ralph_loop.py` — `run_loop()` interface + `quality_bar_critic()` implementation

### State Consumers (Phase 5 outputs that Phase 6 reads)
- `state/runtime_state.py` — `AgentState` TypedDict; Phase 6 reads `analyst_decisions`, `risk_scores`, `analysis_results`, `temporal_signals`, `insights`
- `orchestrator/orchestrator.py` — `run_agent()` return dict shape (status, reason, columns_analyzed, total_columns)

### Main Pipeline (wiring reference — no changes needed)
- `main.py` — Calls order: `run_agent()` → `generate_insight_driven_plots()` → `generate_report()` → `generate_llm_report()`
- `visualization/plot_generator.py` — `generate_insight_driven_plots(state, df)` return dict of column → plot path

### Project Constraints
- `.planning/STATE.md` — Active risks and decisions from prior phases

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `orchestrator/ralph_loop.py` → `run_loop()` + `quality_bar_critic()`: drop-in for Gate 2 — no changes needed
- `report/llm_report_writer.py` → `_build_llm_input_summary()`: compact deterministic summary for LLM input — still useful
- `report/report_generator.py` → `_format_number()` helper: keep for signal rendering
- `visualization/plot_generator.py` → returns `{column: plot_path}` dict stored in `state["visualizations"]`: use to embed inline plots

### Established Patterns
- `state["analyst_decisions"]` is `Dict[str, AnalystDecision]` keyed by column name
- `state["risk_scores"]` is `Dict[str, float]` keyed by column name — use for ranking
- `state["analysis_results"]` is `Dict[str, Dict[str, Any]]` — outer key=column, inner key=tool name
- `state["temporal_signals"]` populated by `profile_temporal()` — check for presence before rendering temporal section
- `state["visualizations"]` populated by `generate_insight_driven_plots()` — dict of name → path

### Integration Points
- `report/report_generator.py` → `generate_report(state, summary)` — rewrite this function
- `synthesis/global_synthesizer.py` → `generate_global_summary()` — extend or replace with ranking logic
- `main.py` → no changes required (wiring preserved)

### What NOT to change
- `orchestrator/ralph_loop.py` — Phase 3, do not modify
- `visualization/plot_generator.py` — plot generation unchanged; Phase 6 only changes where plots appear in the report
- `main.py` — preserve call order and signatures
- `report/llm_report_writer.py` — preserve; Phase 6 calls it after Gate 2

</code_context>

<specifics>
## Specific Ideas

- Inline visualizations in report: plots go immediately after the finding paragraph for their
  column, not batched at the end. Caption must describe figure meaning (not just filename).
- Temporal section only renders if `state["temporal_signals"]` is non-empty (already the
  Phase 1 contract — no date column = empty temporal_signals).
- The `_build_llm_input_summary()` in `llm_report_writer.py` reads `state["insights"]`
  for anomaly findings and action history. Phase 6 should ensure `state["insights"]` is
  still populated (Phase 5 backward-compat bridge already does this) so the LLM narrative
  path remains functional without changes.
- SYNTH-01 verification note in report: `"⚠ Single analytical angle — distribution analysis only"`
  is the exact string to use when a column has only 1 tool result.

</specifics>

<deferred>
## Deferred Ideas

None surfaced during discussion.

</deferred>

---

*Phase: 06-global-synthesizer-output-review*
*Context gathered: 2026-03-29*

# Reflection Log

---

## 2026-03-30 - Embed visualizations in LLM narrative report

**What was done:**
Added `_append_visualizations()` to `report/llm_report_writer.py`. After the LLM writes its narrative, this function appends a `## Visualizations` section with `![...](...)` image links grouped by column. The missing heatmap (whole-dataset) appears first, then per-column plots under individual column headings.

**Why append at the end instead of injecting mid-text:**
The LLM writes free-form prose - it may rename sections, reorder paragraphs, or use different column names. Searching the text for the right insertion point would break on any of these variations. Appending a dedicated section is simpler, always works, and keeps the LLM's prose untouched.

**What this demonstrates (post-processing pattern):**
When an LLM produces free-form output that you need to augment with structured data, the safest strategy is to append the structured data *after* the LLM text rather than trying to parse and splice into it. This is a common pattern in agentic systems: let the LLM do language work, then layer deterministic structure on top.

**What to look at:**
Compare `report_generator.py` lines 67-76 (inline chart injection, possible because the code controls the structure) with `_append_visualizations()` (appended section, necessary because the LLM controls the structure). Same data, different insertion strategy - the difference is who owns the document layout.

---

## 2026-03-30 - Move CriticVerdict to insight/critic.py

**What was done:**
`CriticVerdict` was defined in `agents/schemas.py` alongside `AnalystDecision`. It was moved into `insight/critic.py`, which is where it logically belongs. All 5 importing files were updated accordingly.

**Why this approach:**
`CriticVerdict` is the Critic's own output type - it describes the verdict a critic produces. Having it live in `agents/` created a backwards dependency: `insight/` had to import from `agents/` to get a type that belongs to the insight layer. The fix is to own your output types where they are produced.

**What this demonstrates (dependency direction):**
In a layered system, types should be defined in the layer that produces them, not in a shared bag. `AnalystDecision` stays in `agents/schemas.py` because the Analyst produces it. `CriticVerdict` now lives in `insight/critic.py` because the Critic produces it. This is the "own your outputs" principle.

**What to look at:**
Compare the import lines in `orchestrator/orchestrator.py` before and after: previously both types came from one place. Now `AnalystDecision` comes from `agents/` and `CriticVerdict` comes from `insight/` - each from the layer that produces it. The orchestrator's import block now reads like a map of which layers it depends on.

---

## 2026-03-30 - Fix temporal signals + signal-driven visualizations

### What was done
Three files were changed to fix two independent bugs and add visualizations to the report.

**Bug 1 - temporal signals never reached the LLM**

`profile_temporal()` returns this shape:
```python
{"status": "ok", "date_column": "date", "gap_flags": {...},
 "columns": {"revenue": {"trend": {...}, "period_deltas": {...}, "forecast": {...}}}}
```

But `build_analyst_context()` was doing:
```python
state["temporal_signals"].get(column, {})   # looks for "revenue" at top level
```
That always returned `{}` because column data is nested under `"columns"`.

Fix: navigate the correct path `.get("columns", {}).get(column, {})` and flatten
the nested keys (trend.direction -> trend_direction, etc.) into a human-readable
`temporal_context` dict.

**Why temporal context is a separate dict from signals**

The Critic validates every field the LLM puts in `claims[]` by looking it up in
`state["signals"]`. Temporal data lives in `state["temporal_signals"]`, not
`state["signals"]`. If the LLM cited `mom_delta` in `claims[]`, the Critic would
reject it every time - so the loop would spin 5 times and still fail.

Solution: pass temporal data in a separate `temporal_context` key, render it as
a distinct "Temporal context (use in narrative only - do NOT add to claims[])"
block in the prompt, and tell the LLM in the system prompt to use it only in
the narrative. The Critic is never involved.

**Bug 2 - no plots were ever generated**

`generate_insight_driven_plots()` read `insight["recommended_visualizations"]`.
But the orchestrator's insights bridge never sets that key:
```python
state["insights"][column] = {
    "summary": ..., "category": ..., "hypothesis": ..., "recommended_tools": ...
    # no "recommended_visualizations" key!
}
```
So `requested` was always an empty set and no plots were triggered.

Fix: rewrite `generate_insight_driven_plots()` to iterate over `state["signals"]`
directly and trigger each plot type from named threshold constants:
- `MISSING_RATIO_THRESHOLD = 0.05` -> whole-dataset missing heatmap (once)
- `SKEWNESS_THRESHOLD = 1.0` -> distribution plot for that numeric column
- `OUTLIER_RATIO_THRESHOLD = 0.10` -> boxplot for that numeric column
- `DOMINANT_RATIO_THRESHOLD = 0.5` -> bar plot for that categorical column

**Report: missing heatmap added at top**

A new `## Data Quality` section was added to `report_generator.py` immediately
after the Executive Summary. It embeds the missing heatmap if one was generated.
Per-column plots (distribution, boxplot, bar) already embedded in `## Ranked
Findings` by the existing `_build_ranked_section()` loop - that code was fine,
it just never had any plots to embed because of Bug 2.

### Pattern demonstrated
**Separation of trust boundaries**: the Critic is deterministic Python math.
Temporal signals are pre-formatted strings ("July +3.00%"), not raw floats -
so they can never be cleanly compared with `math.isclose`. Keeping them out of
`claims[]` entirely is the correct architectural decision, not a workaround.

### What to look at
- `agents/llm_analyst.py` -> `build_analyst_context()`: how the temporal dict
  is built, and why it goes into `temporal_context` not `signals`
- `agents/llm_analyst.py` -> `_build_messages()`: how the two blocks render
  differently in the prompt the LLM actually sees
- `visualization/plot_generator.py`: threshold constants at the top - this is
  the "named constants, no magic numbers" principle from the global rules
- `report/report_generator.py` -> `generate_report()`: the Data Quality section
  and how the missing heatmap path flows from `state["visualizations"]`

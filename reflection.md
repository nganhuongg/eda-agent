# Reflection Log

---

## 2026-04-02 - Add trend line graphs for temporal columns

**What was done:** Two gaps fixed. (1) Added `plot_trend_line()` to `plot_generator.py` — draws the column values over time as a line chart with a red dashed OLS trend line overlaid. (2) Added temporal plot generation at the end of `generate_insight_driven_plots()` — it reads `state["temporal_signals"]` and plots any column whose trend direction is "up" or "down". (3) Added `profile_temporal(df, metadata)` call in `app.py` so `state["temporal_signals"]` is actually populated when using the web UI (it was only called in `main.py` before).

**Why this approach:** `numpy.polyfit(x, y, deg=1)` fits a degree-1 polynomial (i.e. a straight line) through the data — `deg=1` means one slope + one intercept. The result is the OLS trend line. We only plot "up" or "down" trends and skip "flat" because a flat trend line adds no visual information.

**What concept this demonstrates:** The gap between `main.py` (the CLI entrypoint) and `app.py` (the web entrypoint) — both need to call the same pipeline steps. Missing a step in one but not the other is a common source of bugs when refactoring CLI tools into web apps.

**What to look at:** `plot_trend_line()` in `plot_generator.py` — notice how `(date_series - date_series.min()).dt.days` converts dates to plain integers (days since start) so `polyfit` can work with them numerically. Also look at the temporal loop at the end of `generate_insight_driven_plots` — the `direction in ("up", "down")` guard is the trigger condition.

---

## 2026-04-02 - Inline images in LLM narrative report

**What was done:** Added `_render_llm_report_with_images()` in `app.py`. It replaces the bare `st.markdown(llm_text)` call in the AI Narrative tab. The function splits the report on `##` headings, renders each section, then injects matching visualization images immediately below any section that mentions the column name.

**Why this approach:** `st.markdown()` can render markdown text but cannot display local file images embedded in it — Streamlit serves images via `st.image()`, not via `![](path)` syntax. So images must be injected as explicit `st.image()` calls. Splitting by `##` headers and matching column names in text is a good-enough heuristic: the LLM report always names the column it is discussing.

**What concept this demonstrates:** The separation of *data* (the report text file) from *display* (how Streamlit renders it). The report is stored as plain markdown; the rendering layer enriches it with images at display time. Also: `re.split(r"(?=^## )", ...)` uses a *lookahead* — it splits at positions before `##` without consuming the heading itself.

**What to look at:** The `_render_llm_report_with_images()` function in `app.py` — especially steps 1 (building `column_to_images`), 3 (matching column names in section text), and 4 (dataset-level fallback). Also note the `already_shown` set — it prevents the same column's image appearing twice if the column is mentioned in multiple sections.

---

## 2026-04-02 - Fix report paragraph formatting and broken image paths

**What was done:** Two bugs fixed. (1) In `report_generator.py`, added blank lines (`""`) between each finding field so Markdown renders them as separate paragraphs instead of one run-on line. (2) In `plot_generator.py`, replaced all relative `"outputs/plots/..."` paths with absolute paths built from `Path(__file__).parent.parent`, anchoring them to the project root.

**Why this approach:** Markdown treats consecutive lines with a single `\n` as the same paragraph — you need a blank line (`\n\n`) to start a new paragraph. The relative path bug happened because Streamlit's CWD depends on where the terminal was when you ran it, not where `app.py` lives. `__file__` always points to the source file itself, so `Path(__file__).parent.parent` is a reliable anchor for project-root paths.

**What concept this demonstrates:** The difference between relative paths (fragile — depend on CWD) and absolute paths (stable — anchored to a known location). `Path(__file__).parent` is the standard Python pattern for "a path relative to this source file." Also: Markdown's paragraph rules — blank lines are structural, not cosmetic.

**What to look at:** `plot_generator.py` line 16 — `PLOTS_DIR = Path(__file__).parent.parent / "outputs" / "plots"`. The `.parent.parent` goes up: first from `visualization/` to the project root, then builds the path down to `outputs/plots/`.

---

## 2026-04-02 - UI/UX polish pass on Streamlit app

**What was done:** Added a global CSS block, a centered hero header, a bordered upload card, color-coded risk score cards (red/amber/green), styled anomaly callout boxes, and emoji icons on section headers.

**Why this approach:** Streamlit's default style is functional but plain. CSS injection via `st.markdown("<style>...</style>", unsafe_allow_html=True)` is the standard way to override it — Streamlit renders the HTML directly. Custom HTML cards (via `st.markdown(..., unsafe_allow_html=True)`) were used for risk scores because `st.metric()` doesn't support custom colors.

**What concept this demonstrates:** The separation between *structure* (what data to show) and *presentation* (how to style it). The analysis logic didn't change at all — only the rendering layer did. Also shows progressive enhancement: the app still works if CSS is blocked.

**What to look at:** The `risk_color()` and `risk_label()` helper functions show how to extract a repeated decision (what color = what risk level) into one named place instead of repeating it in every card. The CSS block at the top shows how to use CSS selectors like `[data-testid="metric-container"]` to target Streamlit's internal elements.

---

## 2026-04-02 - Inline report display in Streamlit UI

**What was done:** Replaced `st.expander("Preview report")` / `st.expander("Preview AI narrative")` with direct `st.markdown()` calls. Also switched from a two-column layout to `st.tabs()` so each report has its own full-width tab. Download buttons are kept at the top of each tab as a secondary option.

**Why this approach:** Expanders hide content by default — users had to click to see the report. Rendering inline means results are visible immediately. Tabs were chosen over columns because report text is long; columns would have made each one very narrow and hard to read.

**What concept this demonstrates:** The difference between progressive disclosure (expanders, good for optional detail) vs. primary display (inline rendering, good for the main result). Use expanders when content is supplementary; render inline when it is the point.

**What to look at:** In `app.py` around line 121 — notice how `st.tabs()` creates named sections without hiding content, and how `st.markdown()` renders the `.md` file with headers, bullets, and formatting intact.

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

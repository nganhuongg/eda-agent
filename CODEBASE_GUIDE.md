# Codebase Reading Guide

This guide walks you through every file in the project in the order that makes
the most sense for a learner. For each file you will find: what it does, which
functions to focus on, and what concept it demonstrates.

> **Tip:** Keep this file open alongside your code editor.
> Read the section here first, then open the file and follow along.

---

## Where to start — the two entry points

There are only two ways to run this agent:

| File | How to run | What it does |
|------|-----------|-------------|
| `main.py` | `python main.py` | CLI — runs the full pipeline and prints results |
| `app.py` | `streamlit run app.py` | Web UI — upload a CSV in a browser |

**Start with `main.py`.** It is only 51 lines and calls every major module in
order. Reading it gives you the skeleton of the whole system before you read
any of the detail.

---

## Reading order

```
1. main.py                        <- the skeleton
2. state/runtime_state.py         <- the shared memory
3. config.py                      <- settings
4. profiling/profiler.py          <- load the CSV
5. profiling/signal_extractor.py  <- compute statistics
6. profiling/temporal_profiler.py <- time-series analysis
7. planning/risk_planner.py       <- decide column order
8. execution/analysis_tools.py    <- run tools on real data
9. agents/schemas.py              <- data shapes (Pydantic)
10. agents/llm_analyst.py         <- LLM reasoning
11. insight/critic.py             <- validate LLM claims
12. orchestrator/ralph_loop.py    <- the retry loop
13. orchestrator/orchestrator.py  <- the main agent loop
14. synthesis/global_synthesizer.py <- assemble findings
15. visualization/plot_generator.py <- generate charts
16. report/report_generator.py    <- write report.md
17. report/llm_report_writer.py   <- write report_llm.md
```

---

## 1. `main.py` — The skeleton

**What it does:** Calls every module in sequence. Nothing clever happens here —
it just wires everything together.

**Read this function:** The `if __name__ == "__main__":` block (the entire file).

**What to notice:**
```python
state = initialize_state()                          # create shared memory
df, metadata, total_columns = profile_dataset(...)  # load CSV
state["temporal_signals"] = profile_temporal(...)   # time-series
result = run_agent(state, df, config)               # main loop
state["visualizations"] = generate_insight_driven_plots(...)
report_path = generate_report(state, result)        # write report.md
llm_report_result = generate_llm_report(...)        # write report_llm.md
```

This is the full data flow in 8 lines. Every other file in the project fills
in one of these steps.

**Key concept:** The `state` dict is passed to almost every function. It is the
agent's shared memory — the one object that carries all information from one
step to the next.

---

## 2. `state/runtime_state.py` — The shared memory

**What it does:** Defines `AgentState` — a typed dictionary that every module
reads from and writes to.

**Read these two things:**
- The `AgentState` TypedDict class — every key is a different kind of data
- The `initialize_state()` function — sets all keys to their empty starting values

**What to notice:**
```python
class AgentState(TypedDict):
    dataset_metadata:  Dict   # column names, types, row counts
    signals:           Dict   # computed stats per column (mean, skew, etc.)
    risk_scores:       Dict   # priority score per column
    analysis_results:  Dict   # output of the 4 analysis tools
    insights:          Dict   # flat summary for backward compatibility
    analyst_decisions: Dict   # the LLM's structured output per column
    analyzed_columns:  Set    # which columns are finished
    temporal_signals:  Dict   # time-series analysis results
    visualizations:    Dict   # file paths to generated PNG charts
    action_history:    List   # audit trail of every step taken
    total_columns:     int
```

**Key concept:** Instead of passing data directly between functions, every
module reads from and writes to this one dict. This is how the agent
"remembers" what it did in previous iterations of the loop.

---

## 3. `config.py` — Settings

**What it does:** One small dict with one key.

```python
CONFIG = {
    "MAX_STEPS": 50   # safety cap — agent stops after this many loop iterations
}
```

Short file, read it in 10 seconds. The cap prevents the agent from running
forever on a wide dataset.

---

## 4. `profiling/profiler.py` — Load the CSV

**What it does:** Reads the CSV file and figures out basic facts about each column.

**Read this function:** `profile_dataset(file_path)`

**What it returns:**
```python
df        # the actual DataFrame — used only in orchestrator later
metadata  # e.g. {"revenue": {"type": "numeric", "dtype": "float64", "non_null_count": 98}}
total_columns  # integer count
```

**Key concept:** Type detection. The profiler decides whether each column is
`numeric`, `categorical`, or `datetime`. This classification affects every
downstream step — which tools run, which plots are generated, how the LLM
describes the column.

---

## 5. `profiling/signal_extractor.py` — Compute statistics

**What it does:** For every column, computes a small dictionary of statistics
from the real data. These statistics (called *signals*) are what the LLM
will later receive instead of raw rows.

**Read this function:** `extract_signals(df, metadata)`

**What signals look like for a numeric column:**
```python
{
    "revenue": {
        "mean":          9844.56,
        "std":           2341.10,
        "variance":      5480749.21,
        "skewness":      0.45,
        "missing_ratio": 0.014,
        "outlier_ratio": 0.08,
    }
}
```

**What signals look like for a categorical column:**
```python
{
    "region": {
        "unique_count":   4,
        "dominant_ratio": 0.42,
        "entropy":        1.32,
        "missing_ratio":  0.03,
    }
}
```

**Key concept:** The LLM never sees individual row values. It only ever sees
this small statistics dict. This is the privacy and hallucination control
mechanism — the LLM can only cite numbers it was explicitly given.

---

## 6. `profiling/temporal_profiler.py` — Time-series analysis

**What it does:** If the dataset has a date column, runs time-series analysis
on every numeric column.

**Read this function:** `profile_temporal(df, metadata)`

**What it computes:**
```python
{
    "status": "ok",
    "date_column": "date",
    "columns": {
        "revenue": {
            "trend":         {"direction": "up", "confidence": "HIGH"},
            "period_deltas": {"mom_pct_change": {...}, "yoy_pct_change": {...}},
            "forecast":      {"forecast": [10200.5, 10350.2, 10500.1]}
        }
    }
}
```

**What to notice:** The forecast has two gates before it runs:
1. Minimum 12 data points (otherwise "insufficient data")
2. ADF stationarity test (p < 0.05 required)

If either gate fails, the forecast is skipped. This is the "check assumptions
before doing work" pattern — better to return no forecast than a wrong one.

**Key concept:** Why is temporal data kept separate from signals?
Because the Critic validates LLM claims against `state["signals"]`. Temporal
fields live in `state["temporal_signals"]`. If they were mixed together, the
Critic would reject every temporal claim the LLM made. Keeping them separate
lets the LLM use temporal context in its narrative without the Critic trying
to validate it.

---

## 7. `planning/risk_planner.py` — Decide column order

**What it does:** Scores every column by how problematic it is, then returns
the highest-risk unanalyzed column.

**Read these two functions:**
- `compute_risk_scores(metadata, signals)` — produces a score (0.0–1.0) per column
- `risk_driven_planner(state)` — returns the next column to investigate, or None

**The risk score formula:**
```
score = 0.35 × missing_ratio
      + 0.25 × (abs(skewness) / 3.0)
      + 0.20 × (variance / max_variance)
      + 0.20 × (outlier_ratio * 3.0)
```
All terms are capped at 1.0. Higher score = investigate first.

**What `risk_driven_planner` returns:**
```python
{
    "column":   "revenue",
    "action":   "investigate",
    "priority": 0.73,
    "source":   "risk_planner",
    "reason":   "highest risk score among unanalyzed columns"
}
```
Or `None` if all columns are already analyzed — which is the signal for the
main loop to stop.

**Key concept:** The planner is pure Python — no LLM involved. This is
deliberate. If the LLM decided column order, a failed or hallucinated LLM
response would break the investigation plan before any analysis even began.

---

## 8. `execution/analysis_tools.py` — Run tools on real data

**What it does:** Provides 4 functions that run on the actual DataFrame and
return structured results.

**Read all four functions:**

| Function | What it computes |
|----------|-----------------|
| `analyze_distribution(df, col, col_type)` | min, max, median, Q1, Q3, top values |
| `detect_outliers(df, col)` | IQR bounds, outlier count and ratio |
| `analyze_missing_pattern(df, col)` | missing count, co-missing columns |
| `analyze_correlation(df, col)` | top 5 correlated columns by magnitude |

**Key concept:** This is the ONLY place in the entire codebase where `df`
(the real data) is used. The orchestrator passes `df` to
`_run_tools_for_column()`, which calls these functions and stores the results
in `state["analysis_results"]`. After that, `df` never appears again.

This is a *data boundary* — a deliberate architectural rule that makes it
impossible for raw data to accidentally reach the LLM.

---

## 9. `agents/schemas.py` — Data shapes (Pydantic models)

**What it does:** Defines the exact structure the LLM must return.

**Read both classes:**

`AnalystDecision` — what the LLM returns for each column:
```python
class AnalystDecision(BaseModel):
    column:            str         # which column was analyzed
    hypothesis:        str         # the LLM's prediction before seeing tool results
    recommended_tools: List[str]   # which analysis tools to run
    business_label:    Literal["risk", "opportunity", "anomaly", "trend"]
    narrative:         str         # plain-English explanation
    claims:            List[dict]  # EVERY numeric value the LLM cited
                                   # e.g. [{"field": "skewness", "value": 0.45}]
```

`CriticVerdict` is in `insight/critic.py` (see step 11).

**Key concept:** The `claims` list is the hallucination control mechanism.
The LLM is required to explicitly list every number it cites. If it mentions
a value in the narrative but does not list it in `claims`, the Critic cannot
check it — so the prompt instructs the LLM to be exhaustive. If it invents a
number (e.g. claims `skewness=0.45` when the real value is `2.3`), the Critic
catches it here.

Using Pydantic means if the LLM returns malformed JSON, `AnalystDecision.parse()`
raises a validation error and the code falls back to the deterministic path
rather than crashing.

---

## 10. `agents/llm_analyst.py` — LLM reasoning

**What it does:** Calls the MiniMax API and returns an `AnalystDecision`.

**Read these two functions:**
- `build_analyst_context(state, column)` — builds the dict of signals the LLM receives
- `analyze_column(state, column, rejected_claims)` — makes the API call

**What the LLM receives (the context dict):**
```python
{
    "column": "revenue",
    "column_type": "numeric",
    "signals": {
        "mean": 9844.56,
        "skewness": 0.45,
        ...
    },
    "risk_score": 0.73,
    "analysis_results": { ... },   # output of the 4 tools
    "temporal_context": { ... },   # trend, MoM, YoY — in a SEPARATE key
    "rejected_claims": ["outlier_ratio"]  # feedback from previous iteration
}
```

**What to notice about `rejected_claims`:**
On the first call this is an empty list. If the Critic rejected some claims,
those field names are passed back here on the next attempt. The prompt tells
the LLM: "you previously got these wrong — correct them."

**What to notice about `_deterministic_fallback()`:**
If the API call fails (network error, missing key, bad JSON), this function
returns an `AnalystDecision` built from pure Python rules — no LLM involved.
The agent always produces output, even when the AI component is unavailable.

---

## 11. `insight/critic.py` — Validate LLM claims

**What it does:** Checks every numeric claim in the LLM's output against the
pre-computed ground truth. Returns a `CriticVerdict`.

**Read these two things:**
- `CriticVerdict` class — the Critic's output (approved: bool, rejected_claims: list)
- `validate_finding(finding, signals, analysis_results)` — the validation logic

**How the check works:**
```python
for claim in finding["claims"]:
    field = claim["field"]          # e.g. "skewness"
    claimed_value = claim["value"]  # e.g. 0.45

    ground_truth = signals[column].get(field)   # look up the real value

    if math.isclose(claimed_value, ground_truth, rel_tol=0.01, abs_tol=0.001):
        pass    # approved
    else:
        rejected.append(field)      # rejected
```

**Why `math.isclose()` instead of `==`?**
Floating point numbers are imprecise. `0.08` might be stored as `0.07999999...`.
Exact equality would fail on a correct value. `math.isclose` with 1% relative
tolerance handles this correctly.

**Key concept:** The Critic makes zero API calls. It is pure Python math. This
is the most important design decision in the file — if you used an LLM to
verify another LLM, you would get agreement, not verification. Python math is
deterministic and always correct.

---

## 12. `orchestrator/ralph_loop.py` — The retry loop

**What it does:** Runs a generate → evaluate → feedback loop up to `max_iter`
times, exiting as soon as the Critic approves.

**Read these two functions:**
- `run_loop(generator_fn, critic_fn, max_iter)` — the generic loop
- `quality_bar_critic(result)` — the Gate 2 critic (report-level check)

**The loop in plain English:**
```
rejected_claims = []

repeat up to 5 times:
    result  = generator_fn(rejected_claims)   <- ask the LLM (or regenerate)
    verdict = critic_fn(result)               <- check the result

    if verdict.approved:
        return result                         <- done early

    rejected_claims = verdict.rejected_claims <- tell LLM what failed

return result  <- return best attempt after 5 tries
```

**Three rules to remember:**
1. **Exit immediately on approval** — do not run all 5 iterations if the first
   attempt passes. Efficiency matters when each call costs API credits.
2. **Replace, do not extend, the rejected list** — each iteration only passes
   the *current* rejections. If iteration 2 fixed skewness but broke outlier,
   you only tell the LLM about outlier, not skewness again.
3. **Never crash** — after 5 failures, return the best available result. A
   warning in the logs is better than a crashed report.

**Where `run_loop` is used:**
- **Gate 1** (inside `orchestrator.py`): per-column LLM+Critic loop
- **Gate 2** (inside `report_generator.py`): full report quality check

---

## 13. `orchestrator/orchestrator.py` — The main agent loop

**What it does:** This is where all the above modules connect together and
execute in order for each column.

**Read this function:** `run_agent(state, df, config)`

**The loop per column:**
```
Step 1: Refresh signals + risk scores from current state
Step 2: Ask risk_planner: which column next? (None = all done, exit)
Step 3: Run analysis tools on df  <- df used HERE ONLY
Step 4: Gate 1 (run_loop x5):
           LLM generates AnalystDecision
           Critic validates claims
           If rejected: LLM gets feedback, tries again
Step 5: Log a warning if Gate 1 never approved
Step 6: Store AnalystDecision, update state['insights'], mark column done
Repeat from Step 1
```

**What to notice about `partial()`:**

```python
generator_fn = partial(analyze_column, state, column)
```

`partial()` creates a new function with some arguments pre-filled. Here,
`analyze_column` normally takes `(state, column, rejected_claims)`. After
`partial`, `generator_fn` only needs `(rejected_claims)` — state and column
are already baked in. This is required because `run_loop` calls the generator
with only one argument.

**What to notice about the two return shapes:**
```python
# Clean finish — all columns analyzed
return {"status": "SUCCESS", "reason": "NO_PENDING_INVESTIGATIONS", ...}

# Hit the cap — not all columns done
return {"status": "PARTIAL", "reason": "MAX_COLUMNS_REACHED", ...}
```
Both are valid outcomes. PARTIAL just means the dataset had more columns than
MAX_COLUMNS allowed. The report still gets written.

---

## 14. `synthesis/global_synthesizer.py` — Assemble findings

**What it does:** Takes all the individual `AnalystDecision` objects from
`state["analyst_decisions"]` and assembles them into one ranked findings list.

**Read these two functions:**
- `_build_findings_list(state)` — sorts findings by risk score, adds metadata
- `generate_global_summary(state)` — wraps the findings list with a status dict

**What it returns:**
```python
{
    "findings": [
        {
            "column":         "revenue",
            "risk_score":     0.73,
            "business_label": "risk",
            "hypothesis":     "...",
            "narrative":      "...",
            "claims":         [...],
            "single_angle":   False   # True if only one tool was used
        },
        ...  # sorted by risk_score descending
    ],
    "single_angle": False   # True if ALL findings share the same business_label
}
```

**Key concept:** The `single_angle` flag warns the reader if every column was
labeled the same way (e.g. all "risk"). That would suggest the analysis found
only one angle on the data — a signal that something might be off.

---

## 15. `visualization/plot_generator.py` — Generate charts

**What it does:** Iterates over `state["signals"]` and triggers a plot for
each column where a signal crosses its threshold.

**Read this function:** `generate_insight_driven_plots(state, df)`

**The threshold constants at the top of the file:**
```python
MISSING_RATIO_THRESHOLD  = 0.05   # any column above this -> missing heatmap
SKEWNESS_THRESHOLD       = 1.0    # abs(skewness) above this -> distribution plot
OUTLIER_RATIO_THRESHOLD  = 0.10   # outlier_ratio above this -> boxplot
DOMINANT_RATIO_THRESHOLD = 0.50   # categorical dominant -> bar chart
```

**Why named constants instead of raw numbers?**
If you write `if signals["skewness"] > 1.0`, the `1.0` has no name — future
readers don't know why that number was chosen. Named constants make intent
clear and allow you to change the value in one place.

**What it returns:** A dict mapping plot names to file paths:
```python
{
    "missing_heatmap":         "outputs/plots/missing_heatmap.png",
    "revenue_distribution":    "outputs/plots/revenue_distribution.png",
    "revenue_boxplot":         "outputs/plots/revenue_boxplot.png",
}
```
This dict is stored in `state["visualizations"]` and used by the report generator.

---

## 16. `report/report_generator.py` — Write report.md

**What it does:** Converts the assembled findings into a markdown file at
`outputs/report.md`. Runs Gate 2 (quality bar check) before writing.

**Read these three functions:**
- `generate_report(state, summary)` — main entry point
- `_build_ranked_section(state, reviewed)` — renders the ## Ranked Findings section
- `_build_temporal_section(state)` — renders the ## Temporal Analysis section

**Gate 2 — what it checks:**
```python
reviewed = run_loop(
    generator_fn=lambda rejected_claims: _build_findings_list(state),
    critic_fn=quality_bar_critic,
    max_iter=5,
)
```
`quality_bar_critic` (in `ralph_loop.py`) checks:
1. Every finding has a `business_label`
2. Every numeric claim is traceable to signals
3. Findings are sorted descending by risk score

**Key concept:** Plots are embedded inline — immediately after each column's
finding paragraph. The path came from `state["visualizations"]` earlier:
```python
![revenue distribution](outputs/plots/revenue_distribution.png)
```

---

## 17. `report/llm_report_writer.py` — Write report_llm.md

**What it does:** Sends the deterministic report summary to MiniMax and asks
it to rewrite the content as a narrative business report. Saves to
`outputs/report_llm.md`.

**Read these two functions:**
- `_build_llm_input_summary(state, summary)` — builds the compact text the LLM receives
- `generate_llm_report(state, summary)` — makes the API call and writes the file

**What to notice:**
```python
# Strip <think>...</think> reasoning blocks that reasoning models leak
llm_text = re.sub(r"<think>.*?</think>\s*", "", llm_text, flags=re.DOTALL)

# Strip any Chinese characters that MiniMax may insert mid-sentence
llm_text = re.sub(r"[\u4e00-\u9fff\u3400-\u4dbf]+", "", llm_text)
```
These two post-processing lines exist because MiniMax is a reasoning model
that sometimes leaks its chain of thought and occasionally writes Chinese
characters inside English text. Both are stripped before writing to disk.

**Key concept:** Two reports exist for two audiences:
- `report.md` — trustworthy, every number came from deterministic code
- `report_llm.md` — readable, written in plain business language by the LLM

If a stakeholder questions a number, point them to `report.md`.
If they want a quick read, give them `report_llm.md`.

---

## Test files — `tests/`

Each test file covers one module. The naming is direct:

| Test file | What it tests |
|-----------|--------------|
| `test_state_schema.py` | AgentState initialization |
| `test_critic.py` | validate_finding() claim validation |
| `test_ralph_loop.py` | run_loop() iteration + quality_bar_critic() |
| `test_temporal_profiler.py` | profile_temporal() time-series analysis |
| `test_llm_analyst.py` | analyze_column() + build_analyst_context() |
| `test_orchestrator.py` | run_agent() main loop |
| `test_synthesizer.py` | global synthesis |
| `test_report_generator.py` | report writing |

Run all tests:
```bash
python -m pytest tests/ -v
```

Run one file:
```bash
python -m pytest tests/test_critic.py -v
```

---

## The full data flow in one picture

```
data/sample.csv
    |
    v
profiler.py          -> df, state["dataset_metadata"]
signal_extractor.py  -> state["signals"]
temporal_profiler.py -> state["temporal_signals"]
risk_planner.py      -> state["risk_scores"]
    |
    v
MAIN LOOP (orchestrator.py) — once per column, highest risk first
    |
    +-> analysis_tools.py   -> state["analysis_results"][col]   (df used HERE ONLY)
    |
    +-> GATE 1 (run_loop x5)
    |       |
    |       +-> llm_analyst.py    -> AnalystDecision (hypothesis, claims, narrative)
    |       +-> critic.py         -> CriticVerdict   (approved? rejected_claims?)
    |       +-> if rejected: feed back rejected_claims to LLM, retry
    |
    +-> state["analyst_decisions"][col] = decision
    +-> state["analyzed_columns"].add(col)
    |
    v
global_synthesizer.py -> ranked findings list
plot_generator.py     -> state["visualizations"]
    |
    v
GATE 2 (run_loop x5)
    +-> quality_bar_critic: check labels, grounding, sort order
    |
    v
report_generator.py   -> outputs/report.md
llm_report_writer.py  -> outputs/report_llm.md
```

---

## Key terms glossary

| Term | Meaning |
|------|---------|
| **Signal** | A pre-computed statistic (mean, skewness, etc.) derived from the data before any LLM call |
| **AgentState** | The shared dict that every module reads from and writes to |
| **Gate 1** | The per-column LLM+Critic loop (up to 5 iterations) |
| **Gate 2** | The full-report quality bar check (up to 5 iterations) |
| **Ralph Loop** | The generic generate-evaluate-feedback loop used in both gates |
| **Claim** | A specific numeric value the LLM asserts, listed explicitly so the Critic can check it |
| **CriticVerdict** | The Critic's output: approved (bool) + list of rejected field names |
| **AnalystDecision** | The LLM's output: hypothesis, label, narrative, claims |
| **Deterministic fallback** | Pure Python path used when the LLM API is unavailable |
| **df boundary** | The rule that `df` (raw data) is only used inside `_run_tools_for_column` |
| **Temporal signals** | Time-series analysis (trend, MoM, YoY, forecast) stored separately from signals |
| **Risk score** | A weighted (0.0-1.0) score per column: missing + skewness + variance + outliers |

# Learning: AI Agentic System Design

A walkthrough of the design decisions behind this project.

---

## Chapter 1: The Core Problem This System Solves

Before looking at any code, understand the problem.

You have a CSV file with business data. You want an AI to analyze it and tell you what's wrong, what's interesting, and what to watch. Simple enough — why not just send the CSV to ChatGPT?

**Three problems with that:**

1. **Privacy.** Business data is confidential. Sending it to an external API is a data breach risk.
2. **Hallucination.** LLMs invent numbers. If you ask "what's the average revenue?", it might say 45,000 — but the real answer is 9,800. You'd never know.
3. **No accountability.** If the AI just gives you a paragraph of text, how do you know which numbers to trust?

This project solves all three with architecture — not prompting tricks. The design itself makes hallucination structurally impossible.

---

## Chapter 2: The Fundamental Design Choice — Signals, Not Raw Data

This is the most important decision in the entire system. Everything else flows from it.

```
┌─────────────────────────────────────────────────────────┐
│ WRONG way: send raw data to LLM                         │
│                                                         │
│  CSV → LLM → "revenue has mean of 45,000"  ← invented  │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ THIS system: compute first, send only numbers           │
│                                                         │
│  CSV → Python computes: mean=9,844, skewness=0.45      │
│      → LLM receives: {"mean": 9844, "skewness": 0.45}  │
│      → LLM says: "mean is 9,844"   ← grounded in fact  │
└─────────────────────────────────────────────────────────┘
```

The LLM never sees row values. It only sees a small dictionary of pre-computed statistics. This is called **signals-only context**.

**Why this works as hallucination control:** The LLM can only cite numbers it was given. If it makes up a number that wasn't in the dict, the Critic catches it. You'll see how below.

---

## Chapter 3: The Shared State — The System's Memory

**File:** `state/runtime_state.py`

Every part of the system reads and writes to one shared dictionary called `AgentState`. Think of it as a whiteboard everyone in the room can see and write on.

```python
# Simplified view of what's in AgentState
state = {
    "dataset_metadata":   {},   # column names, types, row counts
    "signals":            {},   # computed stats per column
    "risk_scores":        {},   # priority score per column
    "analysis_results":   {},   # tool outputs per column
    "insights":           {},   # findings per column
    "analyst_decisions":  {},   # LLM decisions per column
    "analyzed_columns":   set(),# which columns are done
    "temporal_signals":   {},   # time-series analysis
    "visualizations":     {},   # generated plot paths
    "total_columns":      0,
    "action_history":     [],
}
```

**Why one shared dict instead of passing data between functions?**

Because this is an **agent loop** — it runs repeatedly, and each iteration needs to know what all previous iterations discovered. If you passed data directly between functions, the loop couldn't "remember" what it did two iterations ago. The shared state is the agent's memory.

**Why not a database or file?** Speed. The whole analysis runs in-process. A database would be overkill for a single run. The state is only needed for the lifetime of one analysis session.

---

## Chapter 4: The Pipeline Layers (Top to Bottom)

The system has 6 distinct layers. Each layer does one job and hands off to the next.

```
Layer 1: PROFILING      — understand the raw data
Layer 2: PLANNING       — decide what to investigate
Layer 3: EXECUTION      — run deterministic analysis tools
Layer 4: AGENTS         — LLM reasons about the signals
Layer 5: CRITIC         — verify LLM claims against ground truth
Layer 6: REPORT         — assemble and write output
```

### Layer 1: Profiling (`profiling/`)

**Three files, three jobs:**

**`profiler.py`** — loads the CSV and figures out basic facts:
- How many rows and columns?
- What type is each column? (numeric, categorical, datetime)
- How many non-null values?

This populates `state["dataset_metadata"]`.

**`signal_extractor.py`** — for each column, computes statistical signals:
```
Numeric columns:     mean, std, variance, skewness, missing_ratio, outlier_ratio
Categorical columns: unique_count, dominant_ratio, entropy, missing_ratio
```

These go into `state["signals"]`. These are the numbers that will be given to the LLM later, and that the Critic will check against.

**`temporal_profiler.py`** — if a date column is found, runs time-series analysis:
- Trend direction (up/down/flat) using linear regression
- Month-over-month % change
- Year-over-year % change
- 3-month forecast using Holt-Winters smoothing

**Why separate these three instead of one big profiler?**

Because they have different failure modes. `profiler.py` can fail if the file doesn't exist. `signal_extractor.py` can fail if a column is all-null. `temporal_profiler.py` might find no date column and skip entirely. Separating them means a failure in one doesn't crash the others, and each is independently testable.

**Why does the forecast have a stationarity gate (ADF test)?**

Holt-Winters assumes the data has a stable mean and variance over time. If that assumption is violated (non-stationary data), the forecast is meaningless — it might project a fake trend. The ADF test checks this mathematically. If the test fails, the forecast is skipped rather than producing garbage output.

This is a pattern you'll see throughout this system: **check assumptions before doing work, and fail gracefully rather than producing wrong output.**

---

### Layer 2: Planning (`planning/risk_planner.py`)

After profiling, the system needs to decide: **which column should we investigate first?**

The risk score formula:
```
score = 0.35 × missing_ratio
      + 0.25 × (|skewness| / 3.0)
      + 0.20 × (variance / max_variance)
      + 0.20 × (outlier_ratio × 3.0)
```

All terms capped at 1.0. Higher score = more problematic = investigate first.

**Why these weights?**

- **Missing data (35%)** gets the highest weight because it's the most concrete data quality problem. A column that's 40% missing cannot be relied upon.
- **Skewness (25%)** matters because highly skewed distributions mislead averages. If revenue is skewed by a few huge deals, the mean doesn't represent a typical transaction.
- **Variance (20%)** flags instability. A column that swings wildly is worth investigating.
- **Outliers (20%)** flag anomalies, but get less weight than missing because outliers can be legitimate (a big sale is real data, not a quality problem).

**Why not just investigate all columns?**

For a 100-column dataset, investigating everything at equal depth wastes time and produces noise. The report becomes too long to act on. Risk-driven investigation means: focus depth where it matters most.

**Why not let the LLM decide column order?**

The risk planner is deterministic. It runs before any LLM call. If the LLM decided column order, you'd need an LLM call just to figure out where to start — and if that call fails or hallucinates, the whole plan breaks. Deterministic planning as a first step keeps the system stable.

---

### Layer 3: Execution (`execution/analysis_tools.py`)

Four tools that run against the actual DataFrame:

| Tool | What it computes |
|------|-----------------|
| `analyze_distribution` | min, max, median, Q1, Q3, top values |
| `detect_outliers` | IQR-based bounds, outlier count and ratio |
| `analyze_missing_pattern` | missing count, co-missing columns |
| `analyze_correlation` | top 5 correlated columns by magnitude |

**Critical rule:** These tools are the **only place in the entire system that touches `df`** (the actual DataFrame). This is enforced by `orchestrator.py` — `df` is passed only to `_run_tools_for_column()` and nowhere else.

**Why this boundary?**

If any other function could access `df`, a bug could accidentally send raw row values to the LLM. By making `_run_tools_for_column()` the single access point, you have one place to audit for data leakage.

Think of it like a server that handles credit card numbers. You don't scatter card-handling code everywhere — you isolate it in one module so you know exactly where sensitive data flows.

Results go into `state["analysis_results"][column]`. The LLM later receives only summaries; the Critic checks claims against these results.

---

### Layer 4: The LLM Analyst (`agents/llm_analyst.py`)

This is where AI enters the loop. The Analyst receives:

```python
context = {
    "column": "revenue",
    "column_type": "numeric",
    "signals": {
        "mean": 9844.56,
        "skewness": 0.45,
        "outlier_ratio": 0.08,
        "missing_ratio": 0.014,
    },
    "risk_score": 0.38,
    "analyzed_columns": ["date", "region"],  # what's already been done
}
```

And it must return a structured JSON:

```json
{
  "column": "revenue",
  "hypothesis": "Moderate skewness with 8% outliers — likely a few high-value deals skewing the distribution",
  "recommended_tools": ["analyze_distribution", "detect_outliers"],
  "business_label": "anomaly",
  "narrative": "Revenue shows a moderate right skew...",
  "claims": [
    {"field": "skewness", "value": 0.45},
    {"field": "outlier_ratio", "value": 0.08}
  ]
}
```

**Notice the `claims` array.** This is the hallucination control mechanism. The LLM is required to explicitly list every numeric claim it makes, with the exact field name and value. This makes the Critic's job straightforward.

**Why `response_format: json_object`?**

Because if the LLM returns free-form text, parsing is fragile. JSON forces a structure you can validate with Pydantic. If the LLM returns malformed JSON, Pydantic validation fails, and the system falls back to `_deterministic_fallback()` rather than crashing.

**Why have a `_deterministic_fallback()`?**

Because the MiniMax API might be down, rate-limited, or the key might not be configured. A robust system must not crash when an external dependency fails. The fallback uses `insight_generator.py` — a rule-based system that generates findings without any LLM call. The report still gets written; it just uses simpler language.

---

### Layer 5: The Critic (`insight/critic.py`)

The Critic is the **trust boundary** of the entire system. It is the answer to the question: *"How do we know the LLM didn't make up those numbers?"*

```python
def validate_finding(finding, signals, analysis_results) -> CriticVerdict:
    for claim in finding["claims"]:
        field = claim["field"]      # e.g. "outlier_ratio"
        value = claim["value"]      # e.g. 0.08

        # Look up the ground truth
        ground_truth = signals[column].get(field)
        if ground_truth is None:
            ground_truth = analysis_results[column].get(field)

        # Mathematical comparison
        if math.isclose(value, ground_truth, rel_tol=0.01, abs_tol=0.001):
            # APPROVED
        else:
            rejected.append(field)  # REJECTED

    return CriticVerdict(approved=len(rejected)==0, rejected_claims=rejected)
```

**Why `math.isclose()` instead of exact equality?**

Floating point numbers are imprecise. `0.08` might be stored as `0.07999999999`. Exact equality would fail. `math.isclose` with 1% relative tolerance handles this correctly.

**Why zero API calls in the Critic?**

This is the most important design decision in the entire file. If you used an LLM to evaluate another LLM's claims, you'd get:

```
LLM Analyst says: "outlier_ratio is 0.45"
LLM Critic says:  "yes, that sounds right"
```

That's not validation — that's agreement. The Critic would just rephrase what the Analyst said. Grounding requires comparison against actual computed numbers, and that's a simple Python operation.

**The rule: trust boundaries must be deterministic.** The LLM is probabilistic (it might be wrong). Python math is deterministic (it is always right). The Critic is Python math.

---

### Layer 6: The Orchestrator — Where Everything Connects

**File:** `orchestrator/orchestrator.py`

This is the main loop. It's where all the layers above get called in the right order.

```
run_agent() loop:
│
├── Step 1: refresh signals + risk scores from current state
│
├── Step 2: ask risk_planner "which column next?"
│           → if None: we're done, return
│
├── Step 3: _run_tools_for_column()   ← df used HERE ONLY
│           → state["analysis_results"][column] populated
│
├── Step 4: Gate 1 (Ralph Loop)
│           → generate: analyze_column() → LLM Analyst call
│           → evaluate: critic validates claims
│           → if rejected: analyst gets rejected_claims, tries again
│           → exits when approved or after 5 iterations
│
├── Step 5: store AnalystDecision in state["analyst_decisions"]
│
├── Step 6: mark column as analyzed
│
└── repeat from Step 1
```

**Why refresh signals at the start of each iteration (Step 1)?**

Because the risk scores are relative — they depend on max variance across all columns. As columns get analyzed and the state updates, a full refresh ensures the priority queue is always accurate.

**Why does the orchestrator hold `df` and nobody else?**

Single access point for sensitive data. Everywhere else, only state dicts travel.

---

## Chapter 5: The Ralph Loop — Self-Correction

**File:** `orchestrator/ralph_loop.py`

This is the mechanism that makes the system self-correcting. It's used in two places (more on that below).

```python
def run_loop(generator_fn, critic_fn, max_iter=5):
    rejected_claims = []    # starts empty

    for i in range(max_iter):
        result = generator_fn(rejected_claims)   # generate (or regenerate)
        verdict = critic_fn(result)              # evaluate

        if verdict.approved:
            return result                        # exit immediately on success

        rejected_claims = verdict.rejected_claims  # thread feedback

    return result  # best attempt after max iterations
```

**The loop has three critical rules:**

**Rule 1 — Exit on approval immediately.**
Don't run all 5 iterations just because you can. If the first attempt is approved, you're done. Efficiency matters.

**Rule 2 — Replace, don't extend the rejected list.**
Each iteration, `rejected_claims` is replaced with the *current* list of rejections, not appended to. Why? Because if iteration 2 fixed the skewness claim but introduced a new outlier claim, you don't want the prompt to still mention the old skewness rejection. You only tell the LLM about *current* problems.

**Rule 3 — Never crash at max iterations.**
After 5 failed attempts, return the best available result and log a warning. The run must complete. A warning in the log is better than a crashed report.

**Why 5 iterations as the cap?**

It's a balance. Too few (1-2) and the LLM doesn't get enough chances to correct itself. Too many (10+) and you're burning API credits on diminishing returns. 5 is a common choice in agentic systems for this type of correction loop.

---

## Chapter 6: Two Gates — Where the Ralph Loop Is Used

The Ralph Loop runs at **two checkpoints**, solving two different failure modes.

```
Gate 1: per-column investigation         Gate 2: full report quality
─────────────────────────────            ──────────────────────────
After: LLM generates a finding          After: all columns analyzed
Goal:  each finding is factually         Goal:  the assembled report
       grounded                                 meets quality bar

Critic:  insight/critic.py               Critic: quality_bar_critic()
         (validates numeric claims)              (3 checks below)
```

**Gate 2 checks (in `quality_bar_critic()`):**

1. Every finding has a `business_label` (risk/opportunity/anomaly/trend). If a finding has no label, it's not actionable.
2. Every numeric claim is traceable to signals or analysis results. (Same check as Gate 1, but at the report level.)
3. Findings are ranked descending by risk score. Most important first.

**Why two gates instead of one?**

Gate 1 catches errors at the individual finding level — a wrong number in one column's analysis.

Gate 2 catches errors at the assembly level — the synthesizer might forget to include a label, or rank findings incorrectly. These are different failure modes that happen at different stages. One gate can't catch both.

Think of it like manufacturing quality control: you inspect each component (Gate 1), then inspect the assembled product (Gate 2).

---

## Chapter 7: Synthesis and Report

**`synthesis/global_synthesizer.py`** — takes all per-column `analyst_decisions` and assembles a ranked list:
- Sort findings by risk score (descending)
- Flag if all findings have the same `business_label` (single-angle warning — you might be missing diversity in your analysis)

**`report/report_generator.py`** — converts the ranked findings into a markdown file. Runs Gate 2 before writing. Always writes something — even if Gate 2 never achieves approval, the best available result gets written.

**`report/llm_report_writer.py`** — optional. Takes the deterministic report and asks MiniMax to rewrite it in narrative business language. The output is `report_llm.md`. This is the *only* place the LLM is used for pure language work rather than reasoning.

**Why keep these two reports separate?**

`report.md` is trustworthy — every number came from deterministic computation. `report_llm.md` is readable — written in plain business language. If a stakeholder questions a number, you point them to `report.md`. If they want a quick read, you give them `report_llm.md`. Different audiences, different needs.

---

## Chapter 8: The Full Picture — How It All Fits

```
CSV file
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ PROFILING (deterministic, no LLM)                           │
│  profiler.py → dataset_metadata                             │
│  signal_extractor.py → signals (mean, skew, outlier...)     │
│  temporal_profiler.py → temporal_signals (trend, MoM, forecast)│
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼ (all goes into AgentState)
┌─────────────────────────────────────────────────────────────┐
│ ORCHESTRATOR LOOP (runs once per column)                    │
│                                                             │
│  risk_planner → which column?                               │
│       │                                                     │
│       ▼                                                     │
│  analysis_tools → run on df (ONLY place df is used)        │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────── GATE 1 (Ralph Loop × 5) ───────────────┐ │
│  │  LLM Analyst (signals only context) → AnalystDecision  │ │
│  │       │                                                 │ │
│  │       ▼                                                 │ │
│  │  Critic (Python math, zero API calls)                  │ │
│  │       │                                                 │ │
│  │  approved? → exit loop    rejected? → feed back        │ │
│  └─────────────────────────────────────────────────────────┘ │
│       │                                                     │
│  store decision, mark column done, loop to next column      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ SYNTHESIS + GATE 2 (Ralph Loop × 5)                         │
│  global_synthesizer → ranked findings                       │
│  quality_bar_critic → check labels, grounding, ranking      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ OUTPUT                                                      │
│  plot_generator.py → insight-triggered visualizations       │
│  report_generator.py → outputs/report.md (deterministic)    │
│  llm_report_writer.py → outputs/report_llm.md (optional)    │
└─────────────────────────────────────────────────────────────┘
```

---

## Chapter 9: Why This Architecture — The Principles Behind the Design

Now that you've seen all the parts, here are the design principles that explain *why* it was built this way:

**1. Deterministic first, AI second.**
All computation happens before any LLM call. The LLM interprets facts it was given, not facts it invented.

**2. Trust boundaries must be non-LLM.**
Every component that makes a trust decision (the Critic, the quality bar) is pure Python. Never use an LLM to verify another LLM.

**3. Fail gracefully, never crash.**
Every LLM call has a deterministic fallback. Every loop has a hard cap. The report always gets written.

**4. Isolate sensitive data.**
`df` is held in one place. Everything else works with summaries. This is "data confinement" — a security principle applied to privacy.

**5. Self-correction through feedback loops.**
The Ralph Loop threads rejection feedback into the next generation call. The LLM is explicitly told what it got wrong, not just asked to "try again."

**6. One job per module.**
`signal_extractor.py` extracts signals and nothing else. `critic.py` validates and nothing else. This makes each component independently testable and replaceable.

---

## Chapter 10: How Temporal Signals Reach the LLM and Report

`learning.md` Chapter 4 explained *what* `temporal_profiler.py` computes. This chapter explains the full path those numbers travel — and an important architectural trap that had to be solved.

### The shape of temporal_signals in state

`main.py` stores the profiler output directly:

```python
state["temporal_signals"] = profile_temporal(df, metadata)
```

The shape is nested:
```python
{
    "status": "ok",
    "date_column": "date",
    "gap_flags": {...},
    "columns": {
        "revenue": {
            "trend":          {"direction": "up", "confidence": "HIGH", ...},
            "period_deltas":  {"mom_pct_change": {"2023-07-31": 0.03, ...}, ...},
            "forecast":       {"forecast": [10200.5, 10350.2, 10500.1], ...},
        }
    }
}
```

Column data sits under the `"columns"` key — **not** at the top level of the dict.

### The bug: one level too shallow

The original `build_analyst_context()` did:

```python
temporal = state["temporal_signals"].get(column, {})
```

`state["temporal_signals"].get("revenue")` returns `None` because `"revenue"` is not a top-level key — it is nested under `"columns"`. The result was always `{}`. The LLM never saw any temporal data.

The fix navigates the correct path:

```python
col_temporal = (
    state.get("temporal_signals", {})
    .get("columns", {})    # ← the missing level
    .get(column, {})
)
```

### Why temporal context is a separate dict — not mixed into signals

Once we can read the temporal data, the next question is: where do we put it so the LLM can use it?

The obvious answer would be: add it to the `signals` dict alongside `skewness` and `missing_ratio`. **This would break the Critic.**

Here is why:

```
Critic rule: every field the LLM puts in claims[] is looked up in
             state["signals"][column].  If it is not there, the claim is rejected.

Temporal data lives in state["temporal_signals"], not state["signals"].

Result: if the LLM wrote {"field": "mom_delta", "value": 0.03} in claims[],
        the Critic would reject it on every iteration — all 5 Ralph Loop
        attempts would fail — and the best the system could do is fall back
        to the deterministic path.
```

The solution is to pass temporal data in a **completely separate key** (`temporal_context`) and label it explicitly in the prompt:

```
Temporal context (use in narrative only — do NOT add to claims[]):
  trend_direction: up
  trend_confidence: HIGH
  mom_delta: +3.00% (2023-07-31)
  yoy_delta: +15.20% (2023-07-31)
  forecast_values: [10200.5, 10350.2, 10500.1]
```

The LLM reads this block and writes narrative like:
> "Revenue is trending upward with high confidence. The most recent month showed a +3% gain vs the prior month."

The Critic is never asked to validate anything from this block — so the Ralph Loop runs cleanly.

**Design principle reinforced:** Trust boundaries must be deterministic. The Critic checks claims against `state["signals"]`. Anything outside that dict must stay outside `claims[]`. Architecture enforces the rule; prompting alone is not enough.

### Two paths for temporal data in the final report

```
Temporal profiler output
  │
  ├── Path A: per-column LLM narrative (report.md § Ranked Findings)
  │     build_analyst_context() → temporal_context dict
  │     → LLM uses it in narrative prose for that column's finding
  │     → "July was up +3% vs June"
  │
  └── Path B: dedicated section (report.md § Temporal Analysis)
        _build_temporal_section() reads state["temporal_signals"]["columns"]
        → pure deterministic Python, no LLM
        → renders trend direction, MoM %, YoY %, forecast for every column
```

Path A gives readable business language inside each column's finding.
Path B gives the raw numbers in a structured reference section.

---

## Chapter 11: Signal-Driven Visualizations

### Why no plots were appearing

`generate_insight_driven_plots()` was supposed to trigger plots based on what analysis found, but it read from a key that was never populated:

```python
# Old code — always produced an empty set
requested = set(insight.get("recommended_visualizations", []))
```

The orchestrator's insights bridge stored `summary`, `category`, `hypothesis`, and `recommended_tools` — but never `recommended_visualizations`. So `requested` was always `set()`, and no condition ever triggered.

### The fix: drive off signals, not insight metadata

Instead of asking "what did the insight layer recommend?", the new code asks "what do the signal values say?":

```python
# visualization/plot_generator.py

MISSING_RATIO_THRESHOLD = 0.05    # any column above this → whole-dataset heatmap
SKEWNESS_THRESHOLD      = 1.0     # abs(skewness) above this → distribution plot
OUTLIER_RATIO_THRESHOLD = 0.10    # outlier_ratio above this → boxplot
DOMINANT_RATIO_THRESHOLD= 0.50    # categorical dominant_ratio → bar plot

for column, signals in state["signals"].items():
    if signals["missing_ratio"] > MISSING_RATIO_THRESHOLD:
        → plot_missing_heatmap()          # once per dataset
    if abs(signals["skewness"]) > SKEWNESS_THRESHOLD:
        → plot_numeric_distribution()     # per column
    if signals["outlier_ratio"] > OUTLIER_RATIO_THRESHOLD:
        → plot_boxplot()                  # per column
    if signals["dominant_ratio"] > DOMINANT_RATIO_THRESHOLD:
        → plot_categorical_distribution() # per column
```

**Why named constants instead of raw numbers?**

If you write `if signals["skewness"] > 1.0`, future-you (or a teammate) has no idea why 1.0. If you write `if abs(signals["skewness"]) > SKEWNESS_THRESHOLD`, the name tells you the intent. You also only change the value in one place instead of hunting through the function.

### Where each plot appears in the report

```
report.md structure:

  # Risk-Driven EDA Report

  ## Executive Summary
  ...

  ## Data Quality             ← NEW: appears only when missing_heatmap was generated
  ![Missing Value Heatmap]    ← whole-dataset view of missing cells

  ## Ranked Findings
    ### [RISK] Column: revenue
    **Finding:** Revenue is trending up...
    ![revenue distribution]   ← embedded immediately after the finding paragraph
    ![revenue boxplot]        ← same column, next plot
    ---
    ### Column: region
    ![region category_distribution]
    ---

  ## Temporal Analysis
  *Date column: date*
  **revenue:** trend up (confidence: HIGH)
    - Latest MoM: +3.00%
    - Latest YoY: +15.20%
    - Forecast: [10200.5, 10350.2, 10500.1]
```

The missing heatmap appears first because data quality is the foundation — a reader should know how complete the dataset is before interpreting any finding. Per-column plots are embedded immediately after each finding so the reader sees the chart alongside the explanation, not somewhere else in the document.

---

## Key Takeaways for Agentic System Design

If you're building your own agentic AI systems, these three patterns from this project are the most transferable:

**1. Signals-only context**
Never give an LLM more data than it needs to reason about. Always pre-compute what it will cite. This controls both privacy and hallucination in one move.

**2. Deterministic critic**
Use Python logic — not another LLM — as your verification layer. A trust boundary must be deterministic. An LLM evaluating another LLM only agrees, it doesn't verify.

**3. Feedback-threaded loops**
When a generation fails, tell the model *specifically* what was wrong. Replace the error list each iteration (don't accumulate). Cap iterations and always return something — agents that can crash or run forever are not production-ready.

These three patterns appear in production agentic systems at much larger scale. This project is a clean, minimal implementation of all three.

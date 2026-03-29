# Complete AI Agentic Pipeline — EDA Agent v3

This document explains every phase, every step, and the reasoning behind each decision in the v3 pipeline. It is written for someone learning how AI agentic systems are designed and built.

---

## What Makes This an AI Agent

Before the phases: a plain script runs a fixed sequence of steps. An AI agent runs a **loop** where each iteration can take a different path depending on what it observed in the previous one.

The core loop is:

```
Observe → Reason → Decide → Act → Evaluate → Observe again
```

The key difference from a script: **the agent's decisions change what happens next**. A script always does step 3 after step 2. An agent might do step 3, or step 7, or loop back to step 1 — depending on what the data said.

In v3, the agent:
- **Observes** a column's computed signals (missingness, skewness, outlier ratio)
- **Reasons** about what those signals mean (LLM Analyst forms a hypothesis)
- **Decides** which analysis tools to run based on that hypothesis
- **Acts** by running those tools deterministically
- **Evaluates** whether the findings are trustworthy (Critic agent checks every claim)
- **Loops** until the Critic approves, then moves to the next column

That loop, repeated with self-correction, is what makes this a genuine AI agent rather than a smarter script.

---

## The Full Pipeline: Six Phases

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
  State        Critic      Ralph       LLM         Orchestrator  Report
  Schema +     Agent       Loop        Analyst     Restructure   + Output
  Temporal                 Utility                               Review
  Profiler
```

Each phase builds on the one before it. You cannot run Phase 4 (LLM Analyst) without Phase 3 (the loop that controls it). You cannot run Phase 3 without Phase 2 (the Critic that the loop depends on). This dependency chain is intentional — it lets you test each component in isolation before connecting them.

---

## Phase 1: State Schema + Temporal Profiler

**Goal:** The pipeline has a stable, extended state schema and can extract temporal signals from any CSV — or skip gracefully when no date column is found.

**Why this is first:** Everything else in the pipeline reads from `AgentState`. If the state schema changes after later phases are built, you break everything downstream. Locking the schema first means all other phases build against a stable contract.

---

### What is AgentState?

`AgentState` is a Python TypedDict — a dictionary with named, typed fields. It is the **single shared memory** of the entire agent. Every module reads from it or writes to it. No module passes data to another module directly — they all read and write state.

```
             ┌──────────────┐
   CSV ──►   │  AgentState  │  ◄──── every module reads/writes here
             └──────────────┘
```

**Why a shared state dict instead of direct function calls?**
Because the agent loop can run for many iterations. If module A called module B directly, you'd have to redesign the call graph every time a new phase was added. With shared state, any module can read what any other module wrote, in any order, without knowing who wrote it.

---

### Step 1.1 — Install Missing Dependencies (Wave 0)

**What happens:**
- Install `statsmodels>=0.14.0` — the library that computes trend slopes and forecasts
- Install `scipy>=1.13.0` — statistical testing utilities
- Install `pytest` — the test runner
- Create `tests/` directory with empty `__init__.py`
- Create `pytest.ini` pointing pytest at the `tests/` folder
- Write test stubs for all 13 tests (11 temporal, 2 schema) — these fail intentionally at first

**Why do this before writing any code?**
This is Test-Driven Development (TDD). You write the tests first, watch them fail, then write code until they pass. The benefit: the tests define exactly what the code must do before you write a single line of implementation. If you write code first, tests tend to be written to match what the code already does — which defeats the purpose of testing.

**Why a Wave 0 specifically?**
Wave 0 is setup work that must complete before any implementation tasks. If you tried to run tests while statsmodels isn't installed, every test crashes with an ImportError — you can't tell which tests pass and which fail. Wave 0 makes the test environment reliable first.

**What the test stubs look like:**
```python
def test_date_column_detected():
    df = pd.DataFrame({"date": ["2023-01-01", "2023-02-01"], "sales": [10, 20]})
    result = profile_temporal(df, metadata)
    assert result["status"] == "ok"
    assert result["date_column"] == "date"
```
This test will fail immediately (module doesn't exist yet). After Step 1.2, it will pass.

---

### Step 1.2 — Build `temporal_profiler.py` (Wave 1)

**What happens:** Create `profiling/temporal_profiler.py` with one public function: `profile_temporal(df, metadata) -> dict`.

Internally, the function calls five helpers in sequence:

#### Helper 1: `_detect_date_column(df)`

**What it does:** Scans every column. For each non-numeric column, tries `pd.to_datetime(col, errors='coerce')`. If more than 80% of values parse successfully, that column is the date column.

**Why 80% and not 100%?** Real business data has dirty rows — nulls, typos, incomplete entries. Requiring 100% would cause the agent to miss date columns in imperfect datasets. 80% is a pragmatic threshold: enough to be confident it's a date column, tolerant enough for real-world data.

**Why skip numeric columns?** A column of Unix timestamps (e.g., `1672531200`) is technically parseable as a date, but you'd never want the agent to treat an integer ID or price column as time data. Skipping numeric types prevents this misidentification.

#### Helper 2: `_compute_trend(series)`

**What it does:** Fits an OLS (Ordinary Least Squares) regression line to the column values over time. If the slope is significantly positive (p < 0.05), direction is "up". If significantly negative, "down". Otherwise "flat".

**Why OLS for trend detection?**
OLS is the simplest linear regression. It answers: "if I draw the best straight line through this data, does it go up or down?" It also gives you a p-value — the probability that the slope you see happened by chance. If p < 0.05, there's less than 5% chance the trend is random noise.

**Why p-value thresholds for confidence?**
- p < 0.01 → HIGH confidence (less than 1% chance it's noise)
- p < 0.05 → MEDIUM confidence
- p >= 0.05 → LOW / flat (the line isn't statistically meaningful)

This prevents the agent from reporting "sales are trending up!" when the data is actually just random variation.

#### Helper 3: `_compute_period_deltas(series)`

**What it does:** Resamples the series to monthly frequency, then computes:
- Month-over-month (MoM): `pct_change()` — what changed vs last month
- Year-over-year (YoY): `pct_change(periods=12)` — what changed vs the same month last year

**Critical detail:** Uses `resample("ME")` not `resample("M")`.

**Why does this matter?** Pandas 2.x deprecated the old aliases `"M"` and `"Y"`. Using `"M"` still works but raises a FutureWarning and will break in a future version. Using `"ME"` (month-end) is the correct 2025 API. Research caught this before it became a bug in production.

**Why YoY only when >= 13 months?** `pct_change(periods=12)` compares month N to month N-12. If you have only 12 months of data, the first 12 comparisons are all NaN (no prior year to compare to). The result would be an empty dict — misleading rather than useful. The code handles this explicitly.

#### Helper 4: `_compute_forecast(series)` — with ADF gate

**What it does:** Attempts a 3-month Holt-Winters forecast. But first, two gates:

```
Gate 1: n >= 12?  ──NO──► return None + "Insufficient data for forecast range"
             │
            YES
             ▼
Gate 2: adfuller(p) < 0.05?  ──NO──► return None + note
             │
            YES
             ▼
      Run ExponentialSmoothing → return [f1, f2, f3]
```

**Why the n >= 12 gate?**
Holt-Winters uses historical patterns to project forward. With fewer than 12 data points, there isn't enough history to detect a meaningful pattern. The model would fit noise, not signal, and produce unreliable forecasts.

**Why the ADF test?**
ADF (Augmented Dickey-Fuller) tests for stationarity. A stationary series has a stable mean and variance over time — it doesn't drift or wander. Holt-Winters assumes some stability in the pattern. If the series is non-stationary (it's a random walk), the forecast is mathematically unreliable.

`adfuller(series.values, autolag="AIC")` returns a p-value. If p < 0.05, reject the null hypothesis that the series has a unit root (i.e., it IS stationary enough to forecast).

**Why Holt-Winters (ExponentialSmoothing) and not something more complex?**
Holt-Winters handles trend well with `trend="add"`. It's well-understood, available in statsmodels, requires no training data split, and works on short series. More complex models (ARIMA, Prophet) have more failure modes and require more data.

#### Helper 5: `_detect_gaps(index)`

**What it does:** Computes time differences between consecutive timestamps. Calculates the median interval. Any gap larger than 2× the median is flagged as irregular.

**Why 2× median?** If your data is monthly and one gap is 3 months, something happened — data wasn't collected, a month was skipped. The threshold of 2× catches genuine anomalies without flagging normal variation in irregular datasets (e.g., weekly data where some weeks have slightly more days).

**Why flag gaps at all?** Period comparisons and forecasts become unreliable when there are gaps. The gap flag lets the report warn the reader: "MoM comparisons may be unreliable — irregular intervals detected." Without this, the agent would silently produce misleading comparisons.

---

### Step 1.3 — Extend AgentState (Wave 2, Plan 02)

**What happens:** Two targeted edits to `state/runtime_state.py`:

1. Add `temporal_signals: Dict[str, Any]` to the `AgentState` TypedDict
2. Add `"temporal_signals": {}` to `initialize_state()` return dict

**Why only two lines?** The philosophy of this codebase is minimal, targeted changes. The AgentState already works for v2. Adding one field is the smallest possible change that achieves the goal. Rewiring everything would introduce new bugs.

**Why `{}` as the default?** If the dataset has no date column, `profile_temporal` returns a skip dict. The orchestrator stores that skip dict in `state["temporal_signals"]`. Downstream modules (LLM Analyst, report generator) check `state["temporal_signals"].get("status")` to decide whether temporal analysis happened. An empty `{}` means "not yet populated" — which is different from "ran but found nothing."

---

### Step 1.4 — Wire into `main.py` (Wave 2, Plan 02)

**What happens:** Two targeted edits to `main.py`:

1. Add `from profiling.temporal_profiler import profile_temporal` to imports
2. Add `state["temporal_signals"] = profile_temporal(df, metadata)` after `profile_dataset`

**Why must this come after `profile_dataset` and before `run_agent`?**
`profile_temporal` needs the DataFrame (`df`) and column metadata (`metadata`) — both produced by `profile_dataset`. The orchestrator loop (inside `run_agent`) needs temporal signals available in state from the first iteration. If you called `profile_temporal` after `run_agent`, the agent would run the entire investigation without temporal context.

```python
# Order matters:
df, metadata, total_columns = profile_dataset(file_path)  # ← produces df, metadata
state["dataset_metadata"] = metadata
state["total_columns"] = total_columns
state["temporal_signals"] = profile_temporal(df, metadata)  # ← uses df, metadata; fills state
result = run_agent(state=state, df=df, config=CONFIG)         # ← reads state["temporal_signals"]
```

---

### Phase 1 Success Criteria (How We Know It Works)

| Test | What it verifies |
|------|-----------------|
| `test_date_column_detected` | Date detection returns status="ok" with correct column name |
| `test_no_date_column_skips` | Returns the exact skip message string |
| `test_trend_direction_up` | OLS slope correctly classified as "up" |
| `test_trend_direction_confidence` | p-value correctly maps to confidence level |
| `test_mom_yoy_deltas` | Both delta keys present in output |
| `test_forecast_with_sufficient_data` | Forecast key present when n >= 12 |
| `test_forecast_gated_insufficient_data` | Forecast is None + "Insufficient" in note when n < 12 |
| `test_no_date_message_in_state` | Exact string match on skip message |
| `test_gap_detection` | Flags irregular=True with 5x-median gap |
| `test_gap_detection_regular` | Returns irregular=False on evenly spaced data |
| `test_skip_reason_key` | Returns "status" key, not "skip_reason" |
| `test_temporal_signals_field` | `initialize_state()["temporal_signals"] == {}` |
| `test_v2_fields_unbroken` | All 10 original keys still present after extension |

---

## Phase 2: Critic Agent

**Goal:** A fully deterministic Critic agent exists that validates LLM claims against computed signals and returns a structured `CriticVerdict` — with no API calls.

**Why build this before the LLM Analyst?**
The Critic is the trust mechanism. You should build and test the trust mechanism before building the thing it's supposed to trust. If you built the Analyst first, you'd have no way to verify its output during development. Building the Critic first means: by the time the Analyst exists, you already have a working quality gate.

---

### Step 2.1 — Define the `CriticVerdict` Schema

**What happens:** Create a Pydantic BaseModel:

```python
class CriticVerdict(BaseModel):
    approved: bool
    rejected_claims: list[str]  # empty if approved
    reason: str
```

**Why Pydantic?**
Pydantic validates the shape of data at runtime. If the Critic produces output that doesn't match this schema (e.g., a missing field, a wrong type), `model_validate()` raises an error immediately. This prevents silent corruption — the worst kind of bug in an agent pipeline where data flows through many stages.

**Why a structured schema instead of a plain dict?**
Because the Ralph Loop (Phase 3) will read `verdict.approved` and `verdict.rejected_claims` programmatically. A structured object with typed fields is safer than `verdict["approved"]` — it fails loudly at the wrong key, not silently.

---

### Step 2.2 — Implement Deterministic Claim Validation

**What happens:** Create `agents/critic_agent.py`. The Critic receives two things:
1. An Analyst finding (a string claim, e.g., "sales has high outlier rate")
2. The signal dict for that column (e.g., `{"outlier_ratio": 0.003, "skewness": 0.4}`)

It then checks: does any numeric claim in the finding correspond to a value in the signal dict?

**Why no LLM call in the Critic?**
This is the most important design decision in the whole system.

If you use an LLM to evaluate another LLM's output, you haven't grounded anything. The evaluating LLM might agree with the claim even when it's wrong — because LLMs tend to be agreeable, and because the evaluating LLM doesn't have access to the actual computed data either.

Grounding means: compare the claim against a number that came from actual computation. That comparison is pure Python logic — no probability, no generation, no hallucination risk. The Critic is the one component in the system that is 100% deterministic and 100% trustworthy.

**What "matching a claim" looks like:**
```
Claim: "outlier_ratio is high (0.42)"
Signal: {"outlier_ratio": 0.003}
Decision: REJECT — claim says 0.42, signal says 0.003
```

```
Claim: "missing_ratio is 12%"
Signal: {"missing_ratio": 0.118}
Decision: APPROVE — 0.118 ≈ 12%, within tolerance
```

---

### Step 2.3 — Write Tests for the Critic

Every Critic behavior is tested before the Critic is used:

| Test | What it proves |
|------|---------------|
| matching claim → approved=True | Happy path works |
| unmatched claim → approved=False | Rejection works |
| zero API calls (no GROQ key) | Critic is truly deterministic |
| `CriticVerdict` validates via Pydantic | Schema contract holds |
| rejected_claims carries the offending claim | Feedback is specific enough for Analyst to act on |

---

## Phase 3: Ralph Loop Utility

**Goal:** A shared iterative refinement utility that gates generation on Critic approval, threads feedback forward each iteration, and always exits within the iteration cap.

**Why a shared utility?**
The loop runs at two points: after each insight is generated (Gate 1) and after the full report is synthesized (Gate 2). If you wrote the loop inline at both places, you'd have duplicate logic that could drift out of sync. A shared utility means both gates use identical behavior.

---

### Step 3.1 — The Loop Structure

**What happens:** Create `orchestrator/ralph_loop.py`:

```python
def ralph_loop(generate_fn, critic_fn, context, max_iterations=5):
    for i in range(max_iterations):
        result = generate_fn(context)
        verdict = critic_fn(result, context)
        if verdict.approved:
            return result
        context["feedback"] = verdict.rejected_claims  # ← thread feedback forward
    return result  # best attempt after cap
```

**Why `for i in range(max_iterations)` and not `while not approved`?**
`while not approved` has no exit condition if the Critic consistently rejects. If the Analyst keeps generating the same wrong output, the loop runs forever. `for i in range(5)` provides a hard ceiling. The agent always terminates — a fundamental requirement for any production system.

**Why return the last attempt instead of failing?**
The agent's job is to produce a report, even when some findings are imperfect. Raising an exception after 5 failed iterations would crash the entire run. Returning the best available result (with a logged warning) means the report gets written with an honest note: "This finding could not be fully verified."

---

### Step 3.2 — Feedback Threading (The Critical Detail)

**What happens:** After each rejection, the rejected claims are added to `context["feedback"]` before the next call to `generate_fn`.

**Why this is essential:**
Without feedback threading, the loop runs identically every iteration. The Analyst has no way to know what was wrong. It would generate the same output, the Critic would reject it for the same reasons, and you'd hit the iteration cap every time.

With feedback threading:
```
Iteration 1: "sales outlier rate is extreme (0.82)"
Critic: REJECT — outlier_ratio signal is 0.003

Iteration 2 (with feedback):
  Context includes: rejected_claims = ["outlier_ratio claimed as 0.82 but signal is 0.003"]
  Analyst sees this and generates: "sales shows low outlier rate (0.003) but high skewness (2.4)"
Critic: APPROVE
```

The loop learns within a single run. That is a core property of agentic systems: **self-correction within the same execution.**

---

### Step 3.3 — Gate 2 Quality Bar

**What happens:** A variant of the loop that checks three conditions instead of claim-level grounding:

1. Every finding has a business label (risk / opportunity / anomaly / trend)
2. No finding contains an unsupported numeric claim
3. Findings are in ranked order (highest risk first)

**Why different criteria for Gate 2?**
Gate 1 checks individual claims. Gate 2 checks the assembled report as a whole. You can have individually valid findings that are assembled incorrectly (wrong order, missing labels, inconsistent taxonomy). Gate 2 catches those synthesis errors that Gate 1 can't see.

---

## Phase 4: LLM Analyst

**Goal:** The LLM Analyst can receive signal context, form a testable hypothesis, recommend analysis tools, and return a validated `AnalystDecision` — without ever receiving a DataFrame.

**Why build this fourth?**
The Analyst needs:
- State schema (Phase 1) to know what signals look like
- Critic (Phase 2) to validate its output
- Ralph Loop (Phase 3) to provide the iteration gate around it

Building it fourth means all of its dependencies are already tested and working. You're not building on assumptions; you're building on proven foundations.

---

### Step 4.1 — The `AnalystDecision` Schema

**What happens:** Define the output contract for the LLM Analyst:

```python
class AnalystDecision(BaseModel):
    column: str
    hypothesis: str
    recommended_tools: list[str]
    reasoning: str
    business_label: str  # "risk" | "opportunity" | "anomaly" | "trend"
```

**Why define the output schema before writing the prompt?**
The schema IS the prompt's contract. When the LLM generates JSON, Pydantic parses and validates it. If the LLM omits `business_label` or puts a wrong type, the validation fails immediately — before the output reaches any downstream code. This is called "structured output" and it's the primary hallucination prevention technique.

---

### Step 4.2 — The Context Builder (Privacy Boundary)

**What happens:** Create `build_analyst_context(state, column)` that produces:

```python
{
    "column": "sales",
    "signals": {
        "outlier_ratio": 0.18,
        "skewness": 2.4,
        "missing_ratio": 0.03,
        "mean": 1204.5,
        "std": 843.2
    },
    "temporal": {
        "direction": "up",
        "confidence": "HIGH",
        "mom_pct_change": {"2024-12": 0.14},
        "forecast": [1350.2, 1410.8, 1465.3]
    },
    "prior_findings": [...],
    "feedback": []  # populated by Ralph Loop on retry
}
```

**What is NOT in this context:**
- Raw CSV rows
- Actual column values
- Column names that might reveal PII
- DataFrame references

**Why is this the privacy boundary?**
The LLM (running via Groq/MiniMax API) processes this dict and sends it over the network. If raw CSV data were in the dict, your confidential business data would leave the machine. By building a context that contains only computed signals — numbers derived from the data — you get AI analysis without data exposure.

**Why this also prevents hallucination:**
The LLM can only make claims about what's in the context. It can't invent `outlier_ratio: 0.82` if the context shows `outlier_ratio: 0.18`. The Critic then verifies that every claim in the Analyst's response matches the context values. The privacy boundary and the hallucination control are the same architectural decision.

---

### Step 4.3 — Groq/MiniMax Retry Wrapper

**What happens:** Wrap every API call in retry logic with exponential backoff:

```
Attempt 1 → wait 1s if 429
Attempt 2 → wait 2s if 429
Attempt 3 → wait 4s if 429
After 3 attempts → fall back to deterministic output, log warning
```

**Why not just crash on 429?**
Rate limit errors are transient — the API is fine, the client is just sending too fast. Retrying with backoff handles transient errors automatically. A crash would abort the entire analysis run, losing all work done so far.

**Why fall back to deterministic output instead of failing hard?**
The v2 deterministic pipeline can still produce a valid report without LLM intelligence. If the API is down, you get a deterministic report instead of nothing. The agent degrades gracefully rather than failing catastrophically.

---

## Phase 5: Orchestrator Restructure

**Goal:** The orchestrator runs the full Analyst+Critic investigation loop (Ralph Loop Gate 1) for each column, enforces the df boundary structurally, and produces a complete per-column findings set.

**Why is this the highest-risk phase?**
The orchestrator is the central coordination point. Changing it touches the flow that all other modules depend on. Phases 1-4 can be built and tested in isolation; Phase 5 wires them all together. The risk: a change to the orchestrator can break v2 behavior that was working fine.

---

### Step 5.1 — The df Boundary Enforcement

**What happens:** The orchestrator holds the DataFrame. A sentinel test verifies that no agent module receives it:

```python
# Sentinel test: replace df with an object that raises on any attribute access
class SentinelDF:
    def __getattr__(self, name):
        raise AssertionError(f"df accessed in agent module via .{name}")

# Run the analysis with sentinel
result = run_agent(state=state, df=SentinelDF(), config=CONFIG)
# If any agent module touches df, this raises immediately
```

**Why a sentinel instead of code review?**
Code review catches the mistakes you look for. A sentinel catches the mistakes you didn't look for. It's a runtime enforcement of an architectural rule — and it will keep catching violations as new code is added in the future.

---

### Step 5.2 — Rewiring the Main Loop

**What the v2 orchestrator loop does:**
```
for each column (by risk score):
    run analysis tools
    generate insights
    critic decides follow-up
```

**What the v3 orchestrator loop does:**
```
for each column (by risk score):
    build analyst context (signals only, no df)
    ralph_loop(
        generate_fn = llm_analyst.generate,
        critic_fn = critic_agent.validate,
        context = analyst_context
    )  ← Gate 1: loops until approved or 5 iterations
    store approved finding in state
```

**Why keep the same outer loop structure?**
The outer loop (column-by-column in risk order) is proven and correct. Rewiring is about what happens inside each iteration, not the loop structure itself. Preserve what works; replace only what needs to change.

---

## Phase 6: Global Synthesizer + Output Review

**Goal:** All per-column findings are synthesized into a single ranked report, reviewed through Ralph Loop Gate 2, and written to disk in v2-compatible output format with optional AI narrative.

**Why a global synthesizer?**
After Phase 5, you have a set of per-column findings — each individually Critic-approved. But the report needs to be a coherent whole: ranked by importance, consistent labels, no contradictions between columns. The synthesizer takes many independent findings and produces one unified document.

---

### Step 6.1 — Multi-Angle Analysis

**What happens:** Before synthesizing, each high-risk column must have been investigated from at least two analytical angles:

- Distribution analysis (shape, skewness, outliers)
- Trend analysis (direction, confidence, forecasts)
- Missing pattern analysis (are nulls random or systematic?)
- Correlation analysis (does this column correlate with others?)

**Why multiple angles?**
A single analysis can be misleading. A column might look fine from a distribution perspective but show a concerning trend when viewed over time. The agent investigates the same column from multiple perspectives before drawing a conclusion — the same way a good analyst would.

---

### Step 6.2 — Ralph Loop Gate 2 (Output Review)

**What happens:** The synthesized report runs through the second Ralph Loop checkpoint:

```
Synthesizer generates ranked report
   ↓
Gate 2 Critic checks:
  1. Every finding has a business label? (risk/opportunity/anomaly/trend)
  2. No finding contains an unsupported numeric claim?
  3. Findings are ranked highest-risk first?
   ↓
If all pass → write report to disk
If any fail → send back to synthesizer with feedback (max 5 iterations)
```

**Why validate the assembled report separately from individual findings?**
Individual findings can be locally correct but globally inconsistent. Example:
- Finding A: "revenue is at risk (HIGH)"
- Finding B: "revenue is an opportunity (LOW)"
These are individually valid but contradict each other. Gate 2 catches synthesis-level errors that Gate 1 can't see because Gate 1 only saw one finding at a time.

---

### Step 6.3 — v2 Output Format Preservation

**What happens:** The final report is written to `outputs/report.md` in the same format v2 produces. If a Groq/MiniMax API key is set, an additional AI narrative version is written to `outputs/report_llm.md`.

**Why preserve the v2 format?**
Users who built workflows around v2's output format should not have to change their downstream processes when upgrading to v3. This is the principle of backward compatibility: new capabilities should not break existing usage.

---

## The Complete Data Flow

```
CSV file (stays in orchestrator — never leaves)
     │
     ▼
profile_dataset() ──────────────────────────► dataset_metadata
     │                                         total_columns
     │
     ▼
profile_temporal() ─────────────────────────► temporal_signals
     │                                         (trend, MoM/YoY, forecast, gaps)
     │
     ▼
extract_signals() ──────────────────────────► signals
     │                                         (outlier_ratio, skewness, entropy...)
     │
     ▼
risk_planner() ─────────────────────────────► risk_scores
     │                                         investigation_queue
     │
┌────▼──────────────────────────────────┐
│  AGENT LOOP (per column, risk order)  │
│                                       │
│  build_analyst_context()              │
│    ↓ (signal dict, NO raw df)         │
│  ┌─────────────────────────────────┐  │
│  │  RALPH LOOP — Gate 1            │  │
│  │  llm_analyst.generate()         │  │
│  │    ↓ AnalystDecision (Pydantic) │  │
│  │  critic_agent.validate()        │  │
│  │    ↓ CriticVerdict              │  │
│  │  approved? → exit loop          │  │
│  │  rejected? → add feedback →     │  │
│  │             retry (max 5)       │  │
│  └─────────────────────────────────┘  │
│    ↓ approved finding                 │
│  analysis_tools.run()                 │
│    ↓ deterministic results            │
│  insight_generator.generate()         │
│    ↓ categorical insights             │
│  state.insights[column] = finding     │
└───────────────────────────────────────┘
     │
     ▼
global_synthesizer()
     │
     ▼
┌─────────────────────────────────────────────┐
│  RALPH LOOP — Gate 2 (output review)        │
│  Checks: labels, grounding, ranking          │
│  Feedback → synthesizer → retry (max 5)     │
└─────────────────────────────────────────────┘
     │
     ▼
report_generator() ─────────────────────────► outputs/report.md
     │                                         outputs/plots/
     ▼
llm_report_writer() ────────────────────────► outputs/report_llm.md
(optional, API key required)                   (AI narrative version)
```

---

## Why This Architecture Works

**Deterministic foundation, AI on top:**
All numbers come from deterministic code. The AI interprets those numbers. This means the report is reproducible (same CSV → same signals → Critic can verify), while the interpretation is human-readable (AI explains what the numbers mean for the business).

**Privacy by architecture, not by policy:**
The DataFrame boundary is enforced by design (sentinel test, not developer discipline). Data never reaches the API call site. Confidential data stays local by structural necessity, not by hoping developers remember the rule.

**Graceful degradation:**
Every failure mode has a non-crash path:
- No date column → skip with message, not crash
- Forecast data insufficient → return None + note, not crash
- LLM API down → fall back to deterministic, not crash
- Critic never approves → return best attempt, not crash

This makes the agent reliable enough to run unattended on business datasets, where someone will notice if it crashes but won't notice if it quietly degrades.

**Testable at every layer:**
Phase 1 is tested by 13 unit tests. Phase 2 (Critic) is tested with zero API calls. Phase 3 (Ralph Loop) is tested with mock functions. Phase 4 (LLM Analyst) can be tested with a fake context. The pipeline can be verified incrementally, not just end-to-end.

---

*Document reflects v3 design as of 2026-03-28. Update after each phase completes.*

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

### Step 2.1 — Delete the legacy `suggest_investigations()` function

**What happens:** The existing `insight/critic.py` contains `suggest_investigations()` — a deterministic function that recommended next analysis actions based on signal flags. This is deleted entirely.

**Why now?** In v3, the LLM Analyst (Phase 4) takes over investigation strategy. Keeping the old function alongside the new Critic logic would create confusion about what the Critic's job is. Clean break — `insight/critic.py` becomes the claim validator only. The orchestrator's import and call site are also removed in the same wave.

---

### Step 2.2 — Define the `CriticVerdict` Schema

**What happens:** Create `agents/schemas.py` (new `agents/` package) with a Pydantic BaseModel:

```python
class CriticVerdict(BaseModel):
    approved: bool
    rejected_claims: list[str]  # field names that failed — empty if approved
```

**Why Pydantic?**
Pydantic validates the shape of data at runtime. If the Critic produces output that doesn't match this schema (e.g., a missing field, a wrong type), `model_validate_json()` raises an error immediately. This prevents silent corruption — the worst kind of bug in an agent pipeline where data flows through many stages.

**Why a structured schema instead of a plain dict?**
Because the Ralph Loop (Phase 3) will read `verdict.approved` and `verdict.rejected_claims` programmatically. A structured object with typed fields is safer than `verdict["approved"]` — it fails loudly at the wrong key, not silently.

**Why `agents/schemas.py` and not inside `insight/critic.py`?**
`CriticVerdict` is a shared contract — the LLM Analyst (Phase 4) and Ralph Loop (Phase 3) both need to import it. Putting it in a dedicated `agents/schemas.py` gives both future modules a clean import path with no circular dependency risk.

---

### Step 2.3 — Implement Deterministic Claim Validation

**What happens:** Rewrite `insight/critic.py` with one public function: `validate_finding(finding, state)`.

The Critic receives a **structured finding dict** — not free text. The LLM Analyst outputs explicit field names and values:

```python
finding = {
    "column": "revenue",
    "claims": [
        {"field": "skewness", "value": 2.3},
        {"field": "missing_ratio", "value": 0.12}
    ],
    "narrative": "Revenue is highly skewed...",
    "business_label": "risk"
}
```

For each claim, the Critic looks up the field in `state["signals"][column]` or `state["analysis_results"][column]` and compares with `math.isclose`:

```python
math.isclose(claim["value"], signal_value, rel_tol=0.01, abs_tol=0.001)
```

**Why structured claims instead of parsing text?**
If the LLM outputs free text ("revenue is highly skewed at 2.3"), the Critic would need to regex-extract `2.3` and guess which signal field it refers to. That's fragile and re-introduces non-determinism. By requiring the LLM to output structured `{"field": "skewness", "value": 2.3}`, the validation becomes a pure dict lookup — no parsing, no ambiguity.

**Why `math.isclose` with `rel_tol=0.01, abs_tol=0.001`?**
Floating point means exact equality fails even for correct claims. `rel_tol=0.01` allows 1% relative error, which handles large-magnitude values (e.g., revenue figures). `abs_tol=0.001` provides a floor so near-zero values don't cause division instability. Python's `math.isclose` handles both cases in one call.

**Why no LLM call in the Critic?**
This is the most important design decision in the whole system.

If you use an LLM to evaluate another LLM's output, you haven't grounded anything. The evaluating LLM might agree with the claim even when it's wrong — because LLMs tend to be agreeable, and because the evaluating LLM doesn't have access to the actual computed data either.

Grounding means: compare the claim against a number that came from actual computation. That comparison is pure Python logic — no probability, no generation, no hallucination risk. The Critic is the one component in the system that is 100% deterministic and 100% trustworthy.

**What validation looks like:**
```
Claim: {"field": "outlier_ratio", "value": 0.42}
Signal: state["signals"]["revenue"]["outlier_ratio"] = 0.003
Decision: REJECT — math.isclose(0.42, 0.003) is False → add "outlier_ratio" to rejected_claims
```

```
Claim: {"field": "missing_ratio", "value": 0.12}
Signal: state["signals"]["revenue"]["missing_ratio"] = 0.118
Decision: APPROVE — math.isclose(0.12, 0.118, rel_tol=0.01) is True
```

**Edge cases handled:**
- `state["signals"][column]` missing → reject all claims cleanly (no KeyError crash)
- Signal value is `None` or `NaN` → `float()` cast fails → claim rejected (no crash)
- Empty `claims` list → `approved=True, rejected_claims=[]` (nothing to reject)

---

### Step 2.4 — Write Tests for the Critic (TDD)

Tests are written in RED state (Wave 1) before the implementation exists (Wave 2). All 13 tests cover CRIT-01 through CRIT-05 plus edge cases:

| Test | Requirement | What it proves |
|------|-------------|---------------|
| `test_approved_when_claim_matches` | CRIT-01 | Matching claim within tolerance → `approved=True` |
| `test_rejected_when_no_match` | CRIT-02 | Claim absent from signals → `approved=False` |
| `test_rejected_when_out_of_tolerance` | CRIT-02 | Claim present but value too different → `approved=False` |
| `test_critic_verdict_schema` | CRIT-03, CRIT-04 | `CriticVerdict` has correct fields and types |
| `test_model_validate_json_roundtrip` | CRIT-04 | Survives `model_validate_json()` round-trip |
| `test_no_api_call_without_groq_key` | CRIT-03 | Passes with `GROQ_API_KEY` unset |
| `test_rejected_claims_list` | CRIT-05 | `rejected_claims` contains the specific field name |
| `test_missing_column_in_signals` | edge case | No crash when column not in signals |
| `test_none_signal_value` | edge case | No crash when signal value is `None` |
| `test_empty_claims_list` | edge case | Empty claims → `approved=True` |
| `test_analysis_results_lookup` | CRIT-01 | Falls back to `analysis_results` when not in `signals` |
| `test_multiple_claims_partial_rejection` | CRIT-02, CRIT-05 | One bad claim rejects the finding; good claim not in list |
| `test_tolerance_boundary` | CRIT-01 | Claim at exactly 1% tolerance → approved |

---

## Phase 3: Ralph Loop Utility

**Goal:** A shared iterative refinement utility that gates generation on Critic approval, threads feedback forward each iteration, and always exits within the iteration cap.

**Why a shared utility?**
The loop runs at two points: after each insight is generated (Gate 1) and after the full report is synthesized (Gate 2). If you wrote the loop inline at both places, you'd have duplicate logic that could drift out of sync. A shared utility means both gates use identical behavior.

---

### Step 3.1 — The Loop Structure

**What happens:** Create `orchestrator/ralph_loop.py` with one public loop function:

```python
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
        rejected_claims = verdict.rejected_claims  # replace, not extend

    return last_result  # best attempt after cap
```

**Why `for _i in range(max_iter)` and not `while not approved`?**
`while not approved` has no exit condition if the Critic consistently rejects. If the Analyst keeps generating the same wrong output, the loop runs forever. `for _i in range(5)` provides a hard ceiling. The agent always terminates — a fundamental requirement for any production system.

**Why return the last attempt instead of failing?**
The agent's job is to produce a report, even when some findings are imperfect. Raising an exception after 5 failed iterations would crash the entire run. Returning the last result means the report gets written — the final attempt is also the most-informed one, since it had the benefit of all prior rejection feedback applied to it.

**Why is Gate 1 and Gate 2 the same function?**
The two gates differ only in what "Critic" means. The loop mechanics (iterate, thread feedback, exit at cap) are identical. By accepting `critic_fn` as a callable argument, `run_loop()` is reusable at both checkpoints without any branching inside the loop. This follows the same callable-injection pattern already used by `ACTION_TO_TOOL` in the orchestrator.

---

### Step 3.2 — Feedback Threading (The Critical Detail)

**What happens:** After each rejection, `verdict.rejected_claims` replaces `rejected_claims` before the next call to `generator_fn`. On iteration 0, an empty list is passed.

**Why pass `rejected_claims` as an argument instead of via a shared dict?**
The Analyst needs to know what failed in the last attempt — not a full history of all prior rejections. A flat `List[str]` passed as an argument is simpler, testable by inspecting call arguments, and keeps the prompt lean. Accumulating history would bloat the Analyst's context over multiple iterations with no benefit.

**Why replace, not extend (`rejected_claims = verdict.rejected_claims`, not `.extend()`)?**
Each Analyst rewrite addresses the prior iteration's failures. The new rejection set reflects the current state — a previous failure that was fixed should no longer appear. Accumulating all rejections would confuse the Analyst with stale issues it already corrected.

With feedback threading:
```
Iteration 0: generator called with []
  Analyst: "sales outlier rate is extreme (0.82)"
  Critic: REJECT — outlier_ratio signal is 0.003
  rejected_claims → ["outlier_ratio"]

Iteration 1: generator called with ["outlier_ratio"]
  Analyst: "sales shows low outlier rate (0.003) but high skewness (2.4)"
  Critic: APPROVE → loop exits
```

The loop learns within a single run. That is a core property of agentic systems: **self-correction within the same execution.**

---

### Step 3.3 — Gate 2 Quality Bar

**What happens:** `orchestrator/ralph_loop.py` also exports `quality_bar_critic(result) -> CriticVerdict` — a deterministic function that checks three conditions on the assembled report, then is passed as `critic_fn` to `run_loop()` for Gate 2:

```python
def quality_bar_critic(result: Any) -> CriticVerdict:
    rejected: List[str] = []

    findings = result.get("findings", [])
    signals = result.get("signals", {})
    analysis_results = result.get("analysis_results", {})

    # Check 1: all findings have business_label (non-empty)
    for i, f in enumerate(findings):
        if not f.get("business_label"):
            rejected.append(f"findings[{i}].business_label")

    # Check 2: no unsupported numeric claims
    for i, f in enumerate(findings):
        col = f.get("column", "")
        for claim in f.get("claims", []):
            field = claim.get("field", "")
            if field and field not in signals.get(col, {}) and field not in analysis_results.get(col, {}):
                rejected.append(f"findings[{i}].claims.{field}")

    # Check 3: findings in descending order by score
    scores = [f.get("score", f.get("priority")) for f in findings]
    numeric = [s for s in scores if s is not None]
    if numeric != sorted(numeric, reverse=True):
        rejected.append("findings_order")

    return CriticVerdict(approved=len(rejected) == 0, rejected_claims=rejected)
```

**Why different criteria for Gate 2 than Gate 1?**
Gate 1 (`validate_finding`) checks individual numeric claims against computed signals. Gate 2 checks the assembled report as a whole. You can have individually valid findings that are assembled incorrectly: wrong order, missing labels, or a claim that was valid at column-level but references a signal that doesn't exist in the global result dict. Gate 2 catches synthesis-level errors that Gate 1 can't see because Gate 1 only saw one finding at a time.

**Why keep `quality_bar_critic` in the same file as `run_loop`?**
It is the Gate 2 critic — it belongs with the loop that uses it. Separating it into a different module would fragment Phase 3's scope with no decoupling benefit. Phase 6 (Global Synthesizer + Output Review) can extract it if the logic grows significantly.

---

### Phase 3 Tests (TDD)

Two-wave structure: Wave 0 builds the test scaffold (RED state), Wave 1 implements to GREEN.

**Wave 0 — TDD scaffold (Plan 03-01):**

Creates `orchestrator/ralph_loop.py` as an importable shell (both functions raise `NotImplementedError`) and `tests/test_ralph_loop.py` with 10 named stubs. All stubs wrap calls in `pytest.raises(NotImplementedError)` — this is the RED state contract, not `pytest.mark.skip`. Pytest collects all 10 without error.

**Wave 1 — Implementation (Plan 03-02):**

Replaces the `NotImplementedError` bodies with working implementations until all 10 tests pass GREEN:

| Test | Requirement | What it proves |
|------|-------------|---------------|
| `test_exits_on_approval` | LOOP-01 | Loop exits after 2 calls when critic approves on iter 2 |
| `test_max_iter_never_approves` | LOOP-01, LOOP-03 | Generator called exactly 5 times; no exception raised |
| `test_feedback_threading` | LOOP-02 | `calls[1] == ["field_a"]`, `calls[2] == ["field_b"]` (most recent only) |
| `test_first_iter_empty_rejected` | LOOP-02 | `calls[0] == []` — iter 0 always receives empty list |
| `test_no_exception_on_exhaustion` | LOOP-03 | Exhausted loop returns last result; no exception raised |
| `test_gate2_uses_run_loop` | LOOP-04 | `quality_bar_critic` passes as `critic_fn` without any import changes |
| `test_qbc_missing_business_label` | LOOP-05 | Finding with `business_label=""` → `approved=False` |
| `test_qbc_unsupported_numeric` | LOOP-05 | Claim field absent from signals/analysis_results → `approved=False` |
| `test_qbc_unranked_order` | LOOP-05 | Findings with scores `[1.0, 3.0]` (ascending) → `approved=False` |
| `test_qbc_all_pass` | LOOP-05 | Labels present, claims supported, scores `[3.0, 1.0]` → `approved=True` |

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

### Step 4.1 — The `AnalystDecision` Schema (Single LLM Call)

**What happens:** Add `AnalystDecision` to `agents/schemas.py` alongside `CriticVerdict`:

```python
class AnalystDecision(BaseModel):
    column: str
    hypothesis: str
    recommended_tools: List[str]   # drawn from ACTION_TO_TOOL keys
    business_label: Literal["risk", "opportunity", "anomaly", "trend"]
    narrative: str                 # plain business language, no statistical jargon
    claims: List[dict]             # [{"field": "skewness", "value": 2.3}, ...]
```

**Why a single LLM call that returns both strategy AND the finding label?**

There are two possible architectures here:

**Option A (single call):** One LLM call per column. The Analyst looks at the signals and returns everything in one shot: which column to investigate, a hypothesis, which tools to run, a business label, a narrative, and the claims the Critic will validate.

**Option B (two calls):** A first call returns an `InvestigationDecision` (column + hypothesis + tools). After the tools run, a second call returns a `FindingDecision` (label + narrative + claims) using the richer post-tool `analysis_results`.

**Why single call is the right choice for this agent:**

The signals available at Phase 4 are already rich enough to make accurate business label determinations without running tools first. Consider what the Analyst actually sees:

```
revenue:
  missing_ratio: 0.12     ← 12% of values are missing
  skewness: 2.3           ← heavily right-skewed
  outlier_ratio: 0.08     ← 8% of rows are statistical outliers
  variance: 94820.0       ← extreme spread
  temporal:
    trend_direction: up
    trend_confidence: HIGH
    mom_delta: +0.14      ← +14% month-over-month
```

A business analyst looking at those numbers would immediately say "this is a risk — high skew and 12% missing values in a revenue column is a data quality problem." The LLM can make that same judgment without needing to run `analyze_distribution` first. The signal extraction pipeline (Phase 1) does the hard measurement work; the LLM does the business interpretation.

The `claims[]` array is the key insight: claims reference signal fields (`{"field": "skewness", "value": 2.3}`), and the Critic already validates against both `signals` and `analysis_results` (Phase 2 decision). So the Analyst can make grounded, Critic-validatable claims without post-tool data.

**What single call gives you:**
- Half the API calls (important when analyzing 10–20 columns in one run)
- A cleaner Phase 4 scope — the module works completely in isolation without needing to run tools
- Simpler test setup — all tests pass mock signal dicts, no tool execution needed
- The Phase 5 (Orchestrator Restructure) wiring is also simpler — one call per column, not two

**Why define the output schema before writing the prompt?**
The schema IS the prompt's contract. When the LLM generates JSON, Pydantic parses and validates it via `model_validate_json()`. If the LLM omits `business_label` or puts the wrong type, validation fails immediately — before the output touches any downstream code. This is structured output, and it's the primary hallucination-prevention technique at the API boundary.

**Why `Literal["risk", "opportunity", "anomaly", "trend"]` and not `str`?**
A plain `str` field would let the LLM invent labels like "concern" or "problem". `Literal[...]` constrains the output to exactly four options at the Pydantic validation layer — before the Critic ever sees it. The Critic validates numeric claims; Pydantic validates structural claims. Both are deterministic.

**Why `claims: List[dict]` included in the same decision?**
The `claims[]` array is what the Critic validates. Putting it in `AnalystDecision` rather than a separate schema means the Analyst is responsible for producing checkable evidence alongside its interpretation. You cannot separate "what the Analyst claims" from "what the Critic checks" — they are the same data.

---

### Step 4.2 — The Context Builder: `build_analyst_context()` (Privacy Boundary)

**What happens:** Create `build_analyst_context(state, column)` in `agents/llm_analyst.py`. This function is the only entry point from `AgentState` to the LLM — it extracts diagnostic fields and returns a clean dict with no DataFrame, no raw values, no PII.

**Key fields extracted per column:**

```python
{
    "column": "revenue",
    "risk_score": 0.74,
    "signals": {
        # numeric columns
        "missing_ratio": 0.12,
        "skewness": 2.3,
        "outlier_ratio": 0.08,
        "variance": 94820.0,
        # categorical columns
        "entropy": 1.4,
        "dominant_ratio": 0.83,
        "unique_count": 4,
    },
    "temporal": {
        "trend_direction": "up",
        "trend_confidence": "HIGH",
        "mom_delta": 0.14,
        "yoy_delta": 0.32,
        "forecast": [1350.2, 1410.8, 1465.3],
    },
    "already_analyzed": ["customer_id", "region"],  # avoid re-recommending
    "rejected_claims": [],  # populated by Ralph Loop on retry
}
```

**What is NOT in this context:**
- Raw CSV rows or any individual cell value
- The DataFrame object itself
- Column names that could reveal PII (only the target column name is passed)
- Any reference to `df` whatsoever

**Why key fields only, not the full signals dict?**

The `signals` dict can be large on wide CSVs. A dataset with 50 columns would produce a signals dict with hundreds of entries across all columns. Passing the full dict to the LLM on every call would:

1. Bloat the prompt with data the LLM doesn't need (it's analyzing *one* column per call)
2. Increase token usage and API cost on every analysis
3. Risk hitting context window limits on smaller models

The key fields (`missing_ratio`, `skewness`, `outlier_ratio`, `variance` for numeric; `entropy`, `dominant_ratio`, `unique_count` for categorical; temporal signals when present) are the ones that actually drive business-relevant insight. The full signals dict contains many intermediate computation artifacts that don't translate to business meaning. By selecting only the diagnostic fields, the prompt stays lean and model-agnostic — it works regardless of whether MiniMax gives you 32k or 1M context tokens.

**Why is this the privacy boundary?**
The LLM calls the MiniMax API over the network. Whatever is in the prompt leaves the machine. By building a context that contains only derived statistics — numbers computed FROM the data but not the data itself — you get AI analysis without exposing the actual business records. The privacy boundary and the hallucination control are the same architectural decision: if the LLM can only see computed signals, it can only make claims about computed signals, and the Critic can verify every one of them.

**Why a dedicated `build_analyst_context()` function rather than building the dict inline?**
Because Phase 5 will call it inside a loop, and Phase 6's global synthesizer will need a variant of it. A named function with a clear signature is testable in isolation — specifically, the success criteria require a sentinel-DataFrame test that confirms no raw values escape through this function. You can't write that test for inline dict construction.

---

### Step 4.3 — LLM Provider: MiniMax via Raw OpenAI SDK

**What happens:** The Analyst calls MiniMax using the `openai` Python SDK with a `base_url` override:

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["MINIMAX_API_KEY"],
    base_url="<MiniMax endpoint — discovered by researcher>",
)
```

**Why MiniMax instead of Groq?**

Groq's free tier has very tight token limits — too small for running analysis across multiple columns in a single session. MiniMax provides significantly more budget (two accounts at $30 each), which is practical for development, testing, and running real analysis pipelines during Phase 5 and 6 integration.

**Why the raw `openai` SDK instead of a dedicated MiniMax SDK or LangChain?**

Almost every modern LLM provider offers an OpenAI-compatible REST API. This means the same SDK — just change `base_url` and `api_key`. The decision to use the raw SDK (locked in STATE.md from the Groq era) was precisely to avoid dependency on any single provider. Switching from Groq to MiniMax requires changing two environment variables and one string constant — no new packages, no refactoring.

LangChain adds an abstraction layer that hides what's actually happening in the API call. When something goes wrong (wrong JSON format, unexpected response structure), LangChain's error messages are harder to interpret than the raw SDK's. For a system where structured output validation is critical, you want to be close to the raw response.

**Why `MINIMAX_API_KEY` as the environment variable?**
If the key is unset, the Analyst immediately falls back to the deterministic pipeline — same behavior as an API failure. This means the agent runs correctly in CI, development environments without credentials, and any machine where the API key isn't configured. You get a valid (deterministic) report in all cases.

---

### Step 4.4 — API Failure Fallback: Deterministic Pipeline

**What happens:** The API call is wrapped in retry logic. After 3 attempts with exponential backoff (1s → 2s → 4s), the Analyst falls back to the existing deterministic pipeline:

```
Attempt 1 → MiniMax API call
  └─ 429 / timeout → wait 1s
Attempt 2 → MiniMax API call
  └─ 429 / timeout → wait 2s
Attempt 3 → MiniMax API call
  └─ failure → FALLBACK

Fallback:
  column = risk_driven_planner(state)          ← existing Phase 2 planner
  finding = generate_insight_for_column(...)   ← existing Phase 1 insight generator
  return AnalystDecision(                      ← same return type, consistent interface
      column=column,
      hypothesis="deterministic fallback",
      recommended_tools=[plan["action"]],
      business_label="risk",
      narrative=str(finding),
      claims=[],
  )
```

**Why fall back to the deterministic pipeline instead of raising an exception?**

This is a fundamental choice about what kind of system you're building. Two philosophies:

**Fail fast:** Any unexpected condition raises an error. The run aborts. The user sees exactly what went wrong. This is good for development but terrible for production — a single API hiccup wipes out a full analysis run.

**Degrade gracefully:** Unexpected conditions trigger a lesser-quality fallback that still produces a result. The run completes. The user gets output. A warning log explains what fell back.

This agent processes confidential business data. Users run it to get insights before a meeting or decision. If the analysis aborts 80% of the way through because MiniMax returned a 429, the user is left with nothing. The deterministic pipeline exists, it works, and it produces valid (if less insightful) output. Using it as a fallback means the agent always delivers something useful.

**Why return the same `AnalystDecision` type from the fallback?**
The caller (Phase 5 orchestrator) should not need to know whether the result came from MiniMax or the fallback. If the fallback returned a different type, every call site would need an `isinstance` check. A consistent return type keeps the orchestrator loop simple and makes the fallback invisible to downstream code.

**Why `risk_driven_planner` + `generate_insight_for_column` as the fallback sources?**
These are the exact functions the v2 agent used for column selection and insight generation. They've been tested, they handle all column types, and they produce output the Critic can validate. Reusing them for the fallback means zero new code in the fallback path — and the fallback has the same test coverage as the functions themselves.

---

### Phase 4 Tests (TDD)

Phase 4 follows the same Wave 0 (RED scaffold) → Wave 1 (GREEN implementation) structure as Phases 2 and 3:

**Wave 0 — TDD scaffold:** Create `agents/llm_analyst.py` as an importable shell with `NotImplementedError` stubs. Create `tests/test_llm_analyst.py` with named test stubs covering ANLST-01 through ANLST-06. All stubs wrap calls in `pytest.raises(NotImplementedError)`.

**Wave 1 — Implementation:** Replace stubs with working code until all tests pass GREEN.

Key tests:

| Test | Requirement | What it proves |
|------|-------------|---------------|
| `test_analyst_decision_schema` | ANLST-01/02/03/04/05 | `AnalystDecision` has all required fields with correct types |
| `test_model_validate_json_roundtrip` | success criteria | Survives `model_validate_json()` round-trip |
| `test_recommended_tools_valid` | ANLST-03 | All tools in `recommended_tools` are in `ACTION_TO_TOOL` keys |
| `test_business_label_constrained` | ANLST-04 | `business_label` is one of the four literals |
| `test_build_analyst_context_no_df` | ANLST-06 | Sentinel-DataFrame test — no raw value escapes |
| `test_build_analyst_context_key_fields` | ANLST-06 | Output contains diagnostic fields, not raw data |
| `test_fallback_on_api_failure` | success criteria | Returns `AnalystDecision` even when API call raises |
| `test_narrative_no_jargon` | ANLST-05 | Narrative field populated (content checked in integration) |
| `test_rejected_claims_in_context` | ANLST-02 | `rejected_claims` from Critic present in context on retry |
| `test_no_minimax_key_uses_fallback` | ANLST-06 | Unset `MINIMAX_API_KEY` triggers deterministic fallback |

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

*Document reflects v3 design as of 2026-03-29. Updated after Phase 03 (Ralph Loop Utility) planning.*

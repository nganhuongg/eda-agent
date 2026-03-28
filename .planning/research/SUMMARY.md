# Research Summary — EDA Agent v3

*Synthesized: 2026-03-28*

---

## Executive Summary

EDA Agent v3 extends a proven deterministic v2 pipeline by adding a two-agent AI layer — an LLM Analyst that drives investigation strategy and a deterministic Critic that blocks hallucinated claims — without replacing any existing components. The central architectural insight is that confidentiality and hallucination control are solved by the same constraint: the LLM never receives a DataFrame, only a pre-serialized dict of computed signals. This single rule is the load-bearing design decision for the entire v3 system.

The recommended build approach is conservative and dependency-aware: extend v2 rather than rewrite it, keep the raw `openai` SDK rather than adding LangChain, use `statsmodels` for time-series rather than Prophet (which reliably fails on Windows 11), and make the Critic a pure Python dict comparison with zero API calls. The Ralph Loop iterative refinement pattern gates quality at two checkpoints — after insight generation and after report synthesis — with a hard cap of 5 iterations to prevent runaway loops.

The biggest risks are implementation-level rather than conceptual: allowing `df` to reach agent modules by convention drift, building an LLM-based Critic instead of a deterministic one, accepting unvalidated LLM JSON without Pydantic parsing, and forecasting on sparse time-series without data-quality gates. All of these have clear prevention strategies documented in PITFALLS.md and are phase-specific — meaning they can be caught early if the build follows the dependency-ordered phase structure derived from ARCHITECTURE.md.

---

## Recommended Stack

| Component | Decision | Rationale |
|-----------|----------|-----------|
| LLM client | `openai==2.24.0` (already installed) | Already pointed at Groq's OpenAI-compatible API; zero new dependencies |
| Schema validation | `pydantic==2.12.5` (already installed) | `model_validate_json()` on `AnalystDecision` and `CriticVerdict` provides automatic hallucination rejection |
| LLM framework | None — raw SDK only | LangChain adds 50+ transitive dependencies for features this project does not use |
| Time-series | `statsmodels>=0.14.0` (add) | OLS slope for trend, `ExponentialSmoothing` for forecast, `adfuller` as quality gate |
| Statistical tests | `scipy>=1.13.0` (verify/add) | Mann-Kendall trend test via `scipy.stats.kendalltau` |
| Time-series alternative | Prophet — rejected | Requires compiled C++/Stan backend; routinely fails on Windows 11 without build tools |
| Critic implementation | Pure Python dict comparison | LLM-vs-LLM does not ground claims — it rephrases them; deterministic comparison is the only grounding strategy |

**New dependencies to add:** `statsmodels>=0.14.0`. Verify `scipy` is present; add if not.

**Confidence: HIGH** — confirmed against existing codebase and well-documented Windows build issues with Prophet.

---

## Table Stakes Features

Features that must ship in v3 — users of an AI-powered EDA tool require all of these.

| Feature | Source | Complexity |
|---------|--------|-----------|
| LLM Analyst drives column selection and hypothesis formation | New (core v3) | High |
| Critic agent rejects hallucinated claims and forces rewrite | New (core v3) | High |
| Ralph Loop at investigation checkpoint (Gate 1) | New | High |
| Ralph Loop at output review checkpoint (Gate 2) | New | High |
| Natural-language summaries with business labels (risk/opportunity/anomaly) | New | Low |
| Ranked insight output — most important finding first | New | Low |
| Grounded claims — every LLM statement cites a signal | New (Critic enforcement) | Medium |
| Time-series trend direction (up/down/flat + confidence) | New | Medium |
| Period comparison (MoM, YoY) when date column present | New | Medium |
| Graceful temporal fallback with explicit messaging | New | Low |
| Forecasting with uncertainty ranges (1-3 months) | New, data-quality gated | High |
| Privacy constraint: LLM receives signals only, never raw rows | Architectural, must be preserved | Medium |
| Single-run completion without human intervention | Preserved from v2 | Low |
| Deterministic numeric results | Preserved from v2 | Low |

**Deliberately deferred to v2+:** Interactive Q&A, web UI/dashboard, streaming data, multiple forecast model selection, prescriptive business decisions.

---

## Architecture Blueprint

### Core Constraint (Non-Negotiable)

`df: pd.DataFrame` is held exclusively by `orchestrator.py`. Every agent module receives `state: AgentState` only. This is enforced by convention and code review — not by Python's type system — so it must be a team-level rule, not assumed.

### Component Map

```
orchestrator.py  (holds df exclusively)
│
├── profiling/
│   ├── signal_extractor.py      (existing — add temporal signals)
│   └── temporal_profiler.py     (NEW — date detection, OLS slope, MoM/YoY, adfuller gate)
│
├── planning/
│   └── risk_planner.py          (existing — extend to feed LLM Analyst context)
│
├── agents/                      (NEW directory)
│   ├── llm_analyst.py           (NEW — returns AnalystDecision BaseModel)
│   ├── critic_agent.py          (NEW — deterministic dict comparison, returns CriticVerdict BaseModel)
│   └── schemas.py               (NEW — AnalystDecision + CriticVerdict Pydantic schemas)
│
├── orchestrator/
│   └── ralph_loop.py            (NEW — shared loop utility, max_iterations=5)
│
├── execution/
│   └── analysis_tools.py        (existing — add trend/forecast/comparison tools)
│
├── insight/
│   ├── insight_generator.py     (existing — feeds into Ralph Loop Gate 1)
│   └── critic.py                (existing — extend into CriticVerdict-returning module)
│
├── report/
│   ├── report_generator.py      (existing — extend for ranked insights format)
│   ├── global_synthesizer.py    (NEW — multi-angle synthesis, feeds Gate 2)
│   └── llm_report_writer.py     (existing — preserve, minor extensions)
│
└── state/
    └── runtime_state.py         (existing — extend AgentState schema)
```

### Data Flow Summary

```
CSV → signal_extractor + temporal_profiler → signal dicts
    → risk_planner → ranked columns + context
    → llm_analyst (signals only, no df) → AnalystDecision
    → analysis_tools (deterministic) → analysis_results
    → insight_generator → insights
    → [RALPH LOOP GATE 1: critic_agent validates each insight]
    → global_synthesizer → ranked report draft
    → [RALPH LOOP GATE 2: critic_agent validates full report]
    → report_generator → outputs/report.md + plots
    → llm_report_writer → outputs/report_llm.md (optional)
```

### Pydantic Schemas (Critical)

```python
class AnalystDecision(BaseModel):
    column: str
    hypothesis: str
    recommended_tools: list[str]
    reasoning: str
    business_label: str  # "risk" | "opportunity" | "anomaly" | "trend"

class CriticVerdict(BaseModel):
    approved: bool
    rejected_claims: list[str]
    reason: str
```

All LLM JSON responses must pass `model_validate_json()` — validation failure is treated as rejection, not a parse error to recover from.

### Key Pattern: Ralph Loop

```python
def ralph_loop(generate_fn, critic_fn, context, max_iterations=5):
    for i in range(max_iterations):
        result = generate_fn(context)
        verdict = critic_fn(result, context)
        if verdict.approved:
            return result
        context["feedback"] = verdict.rejected_claims  # MUST pass feedback forward
    return result  # return best attempt, never block report generation
```

**Confidence: HIGH** — derived from direct v2 source analysis.

---

## Top Pitfalls to Avoid

### 1. LLM-Based Critic (Critical)
**Risk:** A Critic that calls an LLM to evaluate Analyst output rephrases claims rather than grounding them.
**Prevention:** `critic_agent.py` makes zero API calls. Implement as pure Python dict comparison: for each numeric claim in `AnalystDecision.reasoning`, verify it matches a value in `signals` or `analysis_results` within tolerance. No match = reject.
**Phase:** Phase 2

### 2. Unbounded Ralph Loop (Critical)
**Risk:** `while not approved:` with no exit condition causes infinite loops on persistently failing inputs.
**Prevention:** Always `for i in range(max_iterations)` with `max_iterations=5`. After max iterations, return best attempt with `final_attempt: true` flag and log a warning. Never block report generation on loop failure.
**Phase:** Phase 3

### 3. Feedback Not Passed to Next Loop Iteration (Critical)
**Risk:** Each Analyst call receives the same context regardless of what the Critic rejected, so the loop always hits `max_iterations` and makes no progress.
**Prevention:** `ralph_loop` must append `verdict.rejected_claims` to context before the next generation call. The Analyst prompt must include a "Previous feedback to address:" section.
**Phase:** Phase 3

### 4. `df` Reaching Agent Modules (Critical)
**Risk:** Passing `df` into LLM-touching modules breaches both confidentiality and hallucination control in one step.
**Prevention:** `df` stays in `orchestrator.py` scope only. Build a `build_analyst_context(state)` helper that extracts exactly the signal fields the LLM needs. Audit every new LLM call site.
**Phase:** Phase 4 + Phase 5

### 5. Unvalidated LLM JSON Output (High)
**Risk:** Parsing LLM responses with string splitting or regex allows malformed or hallucinated structure to enter the pipeline.
**Prevention:** Always use `model_validate_json()` on the target Pydantic BaseModel. Validation failure = rejection; do not attempt to salvage partial output. Log the raw response for debugging.
**Phase:** Phase 4

### 6. Forecasting on Insufficient Data (High)
**Risk:** `ExponentialSmoothing` on fewer than 12 data points produces wide, meaningless intervals that mislead rather than inform.
**Prevention:** Gate forecasting behind a minimum 12-period check AND `adfuller` stationarity test. If either fails, output direction-only trend and note "Insufficient data for forecast range."
**Phase:** Phase 1

### 7. Groq Rate Limits Crashing the Run (Moderate)
**Risk:** Unhandled 429 errors abort the entire analysis run, violating the v2 guarantee of single-run completion.
**Prevention:** Wrap all Groq calls in exponential backoff retry logic (same pattern as existing `llm_report_writer.py`). If retries exhausted, fall back to deterministic output only.
**Phase:** Phase 4

### 8. Breaking `critic.py` Interface Without Plan (Moderate)
**Risk:** Existing `critic.py` returns free-text strings; v3 Critic must return `CriticVerdict(BaseModel)` for programmatic Ralph Loop consumption.
**Prevention:** Treat this as a planned breaking interface change in Phase 2, not a surprise during integration.
**Phase:** Phase 2

---

## Build Order Recommendation

Phases ordered by dependency chain — each phase's output is required input for the next.

### Phase 1: State Schema + Temporal Profiler
**Delivers:** Extended `AgentState` schema, `temporal_profiler.py` with date detection, OLS trend slope, MoM/YoY deltas, `adfuller` quality gate, and graceful fallback messaging.
**Rationale:** Foundational — no LLM dependency, fully testable offline, everything else depends on the state schema being stable.
**Pitfalls to avoid:** Pitfall 6 (forecasting gate), assume date is well-formed (use `errors='coerce'`), irregular time-series gap detection.
**Research flag:** Standard statsmodels patterns — no additional research needed.

### Phase 2: Critic Agent
**Delivers:** `critic_agent.py` with deterministic dict comparison, `CriticVerdict` Pydantic schema, breaking interface change on `critic.py`.
**Rationale:** Fully testable without API key. Establishing the Critic first means the Ralph Loop and LLM Analyst can be built against a real, testable gate rather than a mock.
**Pitfalls to avoid:** Pitfall 1 (LLM-based Critic), Pitfall 8 (interface change plan), Pitfall 5 (unvalidated output).
**Research flag:** Standard pattern — no additional research needed.

### Phase 3: Ralph Loop Utility
**Delivers:** `ralph_loop.py` shared utility, tested with mocks, max_iterations=5 cap, feedback threading confirmed working.
**Rationale:** Shared infrastructure must be solid before real agents depend on it. Testing with mocks is faster and more reliable than testing with live API calls.
**Pitfalls to avoid:** Pitfall 2 (unbounded loop), Pitfall 3 (feedback not passed forward).
**Research flag:** No additional research needed — pattern is fully specified.

### Phase 4: LLM Analyst
**Delivers:** `llm_analyst.py`, `AnalystDecision` schema, `build_analyst_context()` helper, Groq retry wrapper, integration with Ralph Loop + Critic.
**Rationale:** First Groq dependency. Building after Phases 1-3 means the full gate infrastructure exists before the first LLM call is made.
**Pitfalls to avoid:** Pitfall 4 (`df` reaching agent), Pitfall 5 (unvalidated JSON), Pitfall 7 (Groq rate limits), Pitfall 9 (column names/values in prompts — note in PITFALLS.md as confidentiality risk).
**Research flag:** May need research on token budget for wide CSVs (100+ columns) — the `global_synthesizer` aggregate context is an open question flagged in ARCHITECTURE.md.

### Phase 5: Orchestrator Restructure
**Delivers:** `orchestrator.py` restructured around Analyst+Critic loop, Ralph Loop Gate 1 integrated, `df` boundary enforced structurally.
**Rationale:** Most regression risk of any phase — touches the main pipeline. All components must exist before integration. Do last among core components.
**Pitfalls to avoid:** Pitfall 4 (`df` boundary), nested loop termination guard (v3 Ralph Loop inside outer orchestrator loop).
**Research flag:** Potential need for research on state management as `AgentState` grows.

### Phase 6: Global Synthesizer + Output Review Loop
**Delivers:** `global_synthesizer.py`, multi-angle synthesis, Ralph Loop Gate 2, ranked report with business labels, final `report.md` + `report_llm.md` output.
**Rationale:** Depends on all prior phases. Adding the second Ralph Loop checkpoint and the synthesis layer is the final integration step.
**Pitfalls to avoid:** Token budget for aggregate context (open question — may need top-N column cap), maintaining v2 output format compatibility.
**Research flag:** Token budget measurement recommended before implementing `global_synthesizer` on wide CSVs.

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Stack | HIGH | Confirmed against existing codebase; Prophet/Windows issue well-documented |
| Features | HIGH | Grounded in v2 delivered capabilities and clear business analyst expectations |
| Architecture | HIGH | Derived from direct analysis of v2 source files, not speculation |
| Pitfalls | HIGH | Specific to this codebase's v2 patterns and known Groq API behavior |

### Gaps to Address During Planning

1. **Token budget for wide CSVs** — `GlobalSynthesizer` aggregate context across 100+ columns has not been measured. Consider a top-N risk column cap before implementing Phase 6.
2. **`scipy` presence** — verify `scipy` is in the current environment before Phase 1; add to requirements.txt if missing.
3. **`adfuller` minimum sample size** — confirm the 12-period minimum is appropriate for the expected CSV sizes in practice; may need adjustment.

---

## Sources

- Existing v2 codebase (direct source analysis via ARCHITECTURE.md + PITFALLS.md)
- `statsmodels` documentation (trend detection, ExponentialSmoothing, adfuller)
- Prophet Windows installation failure documentation
- Pydantic v2 `model_validate_json()` pattern
- Groq OpenAI-compatible API (confirmed working in `llm_report_writer.py`)
- `.planning/PROJECT.md` — v3 requirements and constraints

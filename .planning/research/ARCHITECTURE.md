# Architecture Research — EDA Agent v3

## Confidence: HIGH — derived from direct analysis of existing v2 source files

---

## Key Architectural Principles

### 1. Signal Envelope Pattern (Already Established in v2)

`llm_report_writer._build_llm_input_summary` already enforces this: the LLM sees a serialized summary string built from `state` dicts, **never a `df`**. v3 must enforce this consistently at every new LLM call site.

**Rule:** `df: pd.DataFrame` is held exclusively by `orchestrator.py`. All agent modules (`llm_analyst`, `critic_agent`, report modules) receive `state: AgentState` only. This is the architectural boundary that enforces both confidentiality and hallucination control.

### 2. Critic Must Be Deterministic (Not LLM-Based)

A Critic that calls an LLM to evaluate another LLM's output does not ground claims — it rephrases them. **Grounding means:** every numeric claim in Analyst output must match a value in `signals` or `analysis_results` (within tolerance).

Critic logic = pure dict comparison. No API call. No tokens consumed.

### 3. Ralph Loop Pattern

```python
# ralph_loop.py — shared utility
def ralph_loop(generate_fn, critic_fn, context, max_iterations=5):
    for i in range(max_iterations):
        result = generate_fn(context)
        verdict = critic_fn(result, context)
        if verdict.approved:
            return result
        context["feedback"] = verdict.rejected_claims
    return result  # return best attempt after max iterations
```

Called at exactly **two checkpoints**:
- **Gate 1** — after `InsightGenerator`: loop until Critic approves each insight batch
- **Gate 2** — after `GlobalSynthesizer`: loop until report meets quality bar

---

## Component Map

```
orchestrator.py  (holds df exclusively)
│
├── profiling/
│   ├── signal_extractor.py      (existing — add temporal signals)
│   └── temporal_profiler.py     (NEW — date detection, trend slope, MoM/YoY deltas)
│
├── planning/
│   └── risk_planner.py          (existing — extend to feed LLM Analyst context)
│
├── agents/                      (NEW directory)
│   ├── llm_analyst.py           (NEW — LLM drives investigation strategy)
│   │   └── returns AnalystDecision(BaseModel)
│   └── critic_agent.py          (NEW — deterministic hallucination validator)
│       └── returns CriticVerdict(BaseModel)
│
├── orchestrator/
│   └── ralph_loop.py            (NEW — shared loop utility)
│
├── execution/
│   └── analysis_tools.py        (existing — add trend/forecast/comparison tools)
│
├── insight/
│   ├── insight_generator.py     (existing — outputs feed into Ralph Loop Gate 1)
│   └── critic.py                (existing rule-based critic — keep, extend)
│
├── report/
│   ├── report_generator.py      (existing — extend for ranked insights format)
│   ├── global_synthesizer.py    (NEW — multi-angle synthesis before Gate 2)
│   └── llm_report_writer.py     (existing — preserve, minor extensions)
│
└── state/
    └── runtime_state.py         (existing — extend AgentState schema)
```

---

## Data Flow

```
CSV file (df held by orchestrator only)
  │
  ▼
signal_extractor.py → signals dict
temporal_profiler.py → temporal_signals dict (if date col detected)
  │
  ▼
risk_planner.py → ranked columns + context dict
  │
  ▼
llm_analyst.py ← receives {signals, risk_scores, insights} (NO raw df)
  │ returns AnalystDecision {column, hypothesis, recommended_tools, reasoning}
  ▼
analysis_tools.py → analysis_results dict (deterministic)
  │
  ▼
insight_generator.py → insights list
  │
  ▼
[RALPH LOOP GATE 1]
critic_agent.py ← receives {insight, signals, analysis_results}
  ├── approved → add to state
  └── rejected → feedback to analyst → retry (max 5)
  │
  ▼
global_synthesizer.py → ranked report draft
  │
  ▼
[RALPH LOOP GATE 2]
critic_agent.py (report-level checks)
  ├── approved → finalize
  └── rejected → feedback → regenerate synthesis
  │
  ▼
report_generator.py → outputs/report.md + plots
llm_report_writer.py → outputs/report_llm.md (optional, Groq)
```

---

## Pydantic Schemas

```python
# agents/schemas.py
from pydantic import BaseModel

class AnalystDecision(BaseModel):
    column: str
    hypothesis: str
    recommended_tools: list[str]
    reasoning: str
    business_label: str  # "risk" | "opportunity" | "anomaly" | "trend"

class CriticVerdict(BaseModel):
    approved: bool
    rejected_claims: list[str]  # empty if approved
    reason: str
```

All LLM JSON responses parsed via `model_validate_json()` — validation failure = automatic rejection.

---

## Build Order (Dependency Chain)

| Phase | Component | Why First |
|-------|-----------|-----------|
| 1 | `AgentState` extensions + `temporal_profiler.py` | Foundational — no LLM risk, everything depends on state schema |
| 2 | `critic_agent.py` | Purely deterministic, fully testable without API key |
| 3 | `ralph_loop.py` utility | Shared infrastructure — test with mocks before real agents |
| 4 | `llm_analyst.py` | First Groq dependency, needs API key; builds on critic + loop |
| 5 | Orchestrator restructure | Integration work — most regression risk, do last among core |
| 6 | `global_synthesizer.py` + output review loop | Depends on all prior phases |

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why Dangerous | Prevention |
|-------------|---------------|-----------|
| Passing `df` to any agent module | Confidentiality breach + hallucination risk | `df` stays in `orchestrator.py` scope only |
| LLM-based Critic | Doesn't ground claims, just rephrases | Critic is pure dict comparison |
| Unlimited Ralph Loop | Infinite loop on persistently failing inputs | `max_iterations=5` hard cap, return best attempt |
| Critic calling LLM for each individual signal | Token explosion on wide CSVs | Batch signals per column, one Critic call per insight |
| Silent temporal skip | User doesn't know why trends are missing | Explicit message in report: "No date column detected — trend analysis skipped" |

---

## Open Questions for Phase Planning

1. **Token budget for large CSVs** — signal dict per column is bounded but `GlobalSynthesizer` aggregate context (100+ columns) needs measurement. Consider summarizing top-N risk columns only.
2. **statsmodels vs scipy** for trend detection — needs feasibility check when building `temporal_tools.py`. (`adfuller` for stationarity, `OLS` for slope, `ExponentialSmoothing` for forecast.)

---
phase: 04-llm-analyst
created: 2026-03-29
status: ready
---

# Phase 04: LLM Analyst — Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Build `agents/llm_analyst.py` — a module that receives serialized signal context (no DataFrame), calls the MiniMax API via the raw openai SDK, parses the structured response into an `AnalystDecision` Pydantic model, and returns it. Also includes `build_analyst_context()` to enforce the df boundary.

Phase 4 delivers the agent module in isolation. Phase 5 (Orchestrator Restructure) wires it into the full investigation loop.

This phase covers ANLST-01 through ANLST-06.

</domain>

<decisions>
## Implementation Decisions

### AnalystDecision Schema — Single LLM Call

**D-01:** One `AnalystDecision` per column. A single LLM call receives signal context and returns all of: column to investigate, hypothesis, recommended tools, business label, narrative, and claims array.

```python
class AnalystDecision(BaseModel):
    column: str
    hypothesis: str
    recommended_tools: List[str]  # names from ACTION_TO_TOOL keys
    business_label: Literal["risk", "opportunity", "anomaly", "trend"]
    narrative: str  # plain business language, no statistical jargon
    claims: List[dict]  # [{"field": "skewness", "value": 2.3}, ...]
```

Rationale: Signals are rich enough (skewness, outlier_ratio, missing_ratio, variance + temporal) for the LLM to make accurate business label determinations without needing post-tool results. The Critic validates `claims[]` against both `signals` and `analysis_results` (Phase 02 decision), so claims can target signal values directly. Single call means simpler implementation, fewer API calls, and easier isolation testing in Phase 4.

**D-02:** `AnalystDecision` is added to `agents/schemas.py` alongside `CriticVerdict` (same package, same file pattern as Phase 02).

**D-03:** `recommended_tools` values must be drawn from the known `ACTION_TO_TOOL` keys: `analyze_distribution`, `detect_outliers`, `analyze_missing_pattern`, `analyze_correlation`. The LLM prompt must enumerate valid tool names explicitly so the output can be validated.

**D-04:** `AnalystDecision` must pass `model_validate_json()`. Any malformed MiniMax response is treated as a validation failure (not a recoverable parse error) and triggers the fallback path.

### LLM Provider — MiniMax

**D-05:** Provider is **MiniMax** (not Groq). Raw `openai` SDK with `base_url` override — same pattern established in STATE.md ("Raw openai SDK over LangChain"). Model name and base URL to be discovered by the researcher agent from MiniMax API documentation.

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["MINIMAX_API_KEY"],
    base_url="<to be filled by researcher>",
)
```

**D-06:** Environment variable name: `MINIMAX_API_KEY`. The existing `GROQ_API_KEY` pattern is replaced. If `MINIMAX_API_KEY` is unset, the Analyst falls back to deterministic mode immediately (same as API failure).

### API Failure Fallback — Deterministic

**D-07:** When the MiniMax API call fails or all retries are exhausted (network error, timeout, rate limit), the Analyst falls back to the **existing deterministic pipeline**:
- Column selection: `risk_driven_planner(state)`
- Finding: `generate_insight_for_column(column, column_type, signals, analysis_results)`

The fallback wraps the deterministic result into an `AnalystDecision`-compatible shape so the caller receives a consistent return type. The run never aborts. A warning is logged indicating which column fell back to deterministic mode.

**D-08:** Retry policy: exponential backoff, max 3 retries before triggering fallback. Specific backoff values (e.g., 1s, 2s, 4s) are Claude's discretion.

### Signal Context Serialization — Key Fields Only

**D-09:** `build_analyst_context()` extracts only the most diagnostic signal fields — not the full signals dict. This is context-window-safe regardless of MiniMax model size, and avoids token pressure on wide CSVs.

**Fields extracted per column:**
- `missing_ratio`, `skewness`, `outlier_ratio`, `variance` (numeric columns)
- `entropy`, `dominant_ratio`, `unique_count` (categorical columns)
- Temporal signals if present: `trend_direction`, `trend_confidence`, `mom_delta`, `yoy_delta`, `forecast_values`

**D-10:** `build_analyst_context()` accepts an `AgentState` and a target column name. It returns a plain dict with no DataFrame references, no raw column values, and no PII. This must be confirmed by a test with a sentinel-value DataFrame (per ROADMAP success criteria 3).

**D-11:** The context dict also includes `risk_score` for the target column (from `state["risk_scores"]`) and a list of already-analyzed columns so the LLM can avoid re-recommending them.

### Prompt Placement — Claude's Discretion

The system prompt (tool names, output format schema, signal field definitions, business label definitions) placement is Claude's discretion. Researcher and planner may choose inline constants in `llm_analyst.py` or a separate template file.

### Inherited Decisions (locked from prior phases)

- **`df` boundary is non-negotiable** — `llm_analyst.py` must never import or receive a DataFrame. `build_analyst_context()` is the only entry point from state to agent context.
- **`CriticVerdict` shape is locked** — `approved: bool`, `rejected_claims: List[str]` (Phase 02)
- **`agents/schemas.py`** is the home for new Pydantic models (Phase 02 pattern)
- **Raw openai SDK** — no LangChain, no other LLM framework (STATE.md active decision)
- **Hard max 5 iterations** on any loop — Phase 03 architecture

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/ROADMAP.md` — Phase 4 goal and success criteria (ANLST-01 through ANLST-06)
- `.planning/REQUIREMENTS.md` — ANLST-01, ANLST-02, ANLST-03, ANLST-04, ANLST-05, ANLST-06

### Existing Agent Contracts
- `agents/schemas.py` — `CriticVerdict(BaseModel)` — add `AnalystDecision` here
- `insight/critic.py` — `validate_finding()` — the Gate 1 critic; shows claim validation pattern
- `orchestrator/ralph_loop.py` — `run_loop()` and `quality_bar_critic()` — Phase 4 Analyst will be passed as `generator_fn` in Phase 5

### Existing Deterministic Pipeline (fallback sources)
- `planning/risk_planner.py` — `risk_driven_planner(state)` — fallback column selector
- `insight/insight_generator.py` — `generate_insight_for_column()` — fallback finding generator
- `orchestrator/orchestrator.py` — `ACTION_TO_TOOL` dict — valid tool names the LLM must choose from

### State Schema
- `state/runtime_state.py` — `AgentState` TypedDict — `signals`, `analysis_results`, `risk_scores`, `analyzed_columns` are the keys `build_analyst_context()` reads from

### Project Constraints
- `.planning/STATE.md` — Active Risks: "df reaching agent modules" mitigation; Active Decisions: raw openai SDK, deterministic Critic strategy

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agents/schemas.py`: add `AnalystDecision` alongside `CriticVerdict` — same Pydantic BaseModel pattern
- `planning/risk_planner.py` → `risk_driven_planner()`: direct fallback for column selection on API failure
- `insight/insight_generator.py` → `generate_insight_for_column()`: direct fallback for finding generation on API failure
- `orchestrator/orchestrator.py` → `ACTION_TO_TOOL` dict: the exact tool name strings the LLM must output (enumerate in system prompt)

### Established Patterns
- OpenAI SDK with base_url override: already established via Groq pattern in STATE.md — same approach for MiniMax
- Pydantic BaseModel + `model_validate_json()`: CriticVerdict in agents/schemas.py is the exact pattern to follow for AnalystDecision
- Signal dict structure: `state["signals"][column]` contains `missing_ratio`, `skewness`, `outlier_ratio`, `variance`, `entropy`, etc. — read `profiling/signal_extractor.py` for full field list

### Integration Points
- `agents/llm_analyst.py` is a new file in the existing `agents/` package (already has `__init__.py`)
- Phase 5 will call `llm_analyst.analyze_column(state, column)` as the `generator_fn` passed to `run_loop()`
- `build_analyst_context()` is the sentinel function — any df reference passing through it is a bug

</code_context>

<specifics>
## Specific Ideas

- User has two MiniMax API accounts ($30 each) — budget is not a concern for development/testing
- Model name unknown at context time — researcher must discover from MiniMax API docs
- The `rejected_claims` list from `CriticVerdict` will be passed back to the Analyst as part of the next `generator_fn` call in Phase 5 — the Analyst prompt should be designed to accept and act on this list (plan for it even if Phase 4 tests don't exercise it end-to-end)

</specifics>

<deferred>
## Deferred Ideas

None surfaced during discussion.

</deferred>

---

*Phase: 04-llm-analyst*
*Context gathered: 2026-03-29*

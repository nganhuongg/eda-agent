# Roadmap: Risk-Driven EDA Agent v3

**Project:** Risk-Driven EDA Agent — Version 3
**Milestone:** v3 — LLM Analyst + Critic + Ralph Loop
**Created:** 2026-03-28
**Granularity:** Fine
**Coverage:** 29/29 v1 requirements mapped

---

## Phases

- [x] **Phase 1: State Schema + Temporal Profiler** - Extend AgentState and build temporal signal extraction with graceful fallback (completed 2026-03-29)
- [x] **Phase 2: Critic Agent** - Build deterministic Critic with CriticVerdict schema and planned interface migration (completed 2026-03-29)
- [ ] **Phase 3: Ralph Loop Utility** - Build shared iterative refinement loop with feedback threading and max-iteration cap
- [ ] **Phase 4: LLM Analyst** - Build LLM Analyst agent with AnalystDecision schema, context builder, and Groq retry wrapper
- [ ] **Phase 5: Orchestrator Restructure** - Rewire orchestrator around Analyst+Critic loop with df boundary enforcement and Ralph Loop Gate 1
- [ ] **Phase 6: Global Synthesizer + Output Review** - Build multi-angle synthesis, Ralph Loop Gate 2, and produce final ranked report

---

## Phase Details

### Phase 1: State Schema + Temporal Profiler
**Goal**: The pipeline has a stable, extended state schema and can extract temporal signals from any CSV — or skip gracefully when no date column is found
**Depends on**: Nothing (first phase)
**Requirements**: TEMP-01, TEMP-02, TEMP-03, TEMP-04, TEMP-05, TEMP-06
**Success Criteria** (what must be TRUE):
  1. Given a CSV with a date column, the profiler detects it automatically and attaches trend direction (up/down/flat) plus confidence to each numeric column in the state dict
  2. Given a CSV with fewer than 12 data points or a non-stationary series, the profiler outputs direction-only trend and notes "Insufficient data for forecast range" — no exception is raised
  3. Given a CSV with a valid date column and >= 12 data points, the profiler computes month-over-month and year-over-year deltas and flags any irregular time-series gaps
  4. Given a CSV with no parseable date column, the run completes and the state contains an explicit "No date column detected — trend analysis skipped" message
  5. `AgentState` schema accepts all new temporal fields without breaking existing v2 field access
**Plans:** 2/2 plans complete

Plans:
- [x] 01-01-PLAN.md — Test infrastructure (Wave 0) + temporal_profiler.py implementation (Wave 1)
- [x] 01-02-PLAN.md — AgentState extension + main.py integration wiring (Wave 2)

### Phase 2: Critic Agent
**Goal**: A fully deterministic Critic agent exists that validates LLM claims against computed signals and returns a structured CriticVerdict — with no API calls
**Depends on**: Phase 1 (stable AgentState schema)
**Requirements**: CRIT-01, CRIT-02, CRIT-03, CRIT-04, CRIT-05
**Success Criteria** (what must be TRUE):
  1. Given a finding that contains a numeric claim matching a value in `signals` or `analysis_results` within tolerance, the Critic returns `CriticVerdict(approved=True, rejected_claims=[])`
  2. Given a finding with a numeric claim that has no match in `signals` or `analysis_results`, the Critic returns `approved=False` with the offending claim listed in `rejected_claims`
  3. The Critic module makes zero network or API calls — it passes with the Groq API key unset
  4. `CriticVerdict` is a Pydantic BaseModel that passes `model_validate_json()` round-trip without error
  5. Rejected findings carry the Critic's `rejected_claims` list so the Analyst can address specific failures in the next attempt
**Plans:** 2/2 plans complete

Plans:
- [x] 02-01-PLAN.md — agents/ package scaffold + CriticVerdict schema + test_critic.py (RED state)
- [x] 02-02-PLAN.md — validate_finding() implementation + gut insight/critic.py + remove orchestrator import

### Phase 3: Ralph Loop Utility
**Goal**: A shared iterative refinement utility exists that gates generation on Critic approval, threads feedback forward each iteration, and always exits within the iteration cap
**Depends on**: Phase 2 (Critic with CriticVerdict)
**Requirements**: LOOP-01, LOOP-02, LOOP-03, LOOP-04, LOOP-05
**Success Criteria** (what must be TRUE):
  1. Given a generator function and Critic function (mocked), the loop iterates until the Critic returns `approved=True` and then exits immediately
  2. Given a Critic that never approves, the loop exits after exactly 5 iterations and returns the best available result — never raises an exception or blocks run completion
  3. Each iteration receives the `rejected_claims` from the previous Critic verdict appended to its context — verified by inspecting context state at iteration N+1
  4. The output review loop (Gate 2) variant checks all three quality bar rules: business labels present, no unsupported numeric claims, ranked order present
**Plans:** 2 plans

Plans:
- [ ] 03-01-PLAN.md — TDD Wave 0: test stubs (RED state) + ralph_loop.py shell
- [ ] 03-02-PLAN.md — Implementation: run_loop() + quality_bar_critic() GREEN

### Phase 4: LLM Analyst
**Goal**: The LLM Analyst agent can receive signal context, form a testable hypothesis, recommend analysis tools, and return a validated AnalystDecision — without ever receiving a DataFrame
**Depends on**: Phase 1 (state schema + signals), Phase 3 (Ralph Loop)
**Requirements**: ANLST-01, ANLST-02, ANLST-03, ANLST-04, ANLST-05, ANLST-06
**Success Criteria** (what must be TRUE):
  1. Given a signal dict for a column, the Analyst returns an `AnalystDecision` that specifies the column to investigate, a stated hypothesis, a list of recommended tools, and a business label (risk/opportunity/anomaly/trend)
  2. `AnalystDecision` passes `model_validate_json()` — any malformed Groq response is treated as rejection, not a recoverable parse error, and logged in full
  3. The `build_analyst_context()` helper produces a dict containing only signal fields — no column values, no DataFrame references — confirmed by code inspection and a test with a DataFrame that contains PII sentinel values
  4. Given a 429 Groq rate-limit response, the Analyst retries with exponential backoff and falls back to deterministic output if retries are exhausted — the run does not abort
  5. Each Analyst finding is labeled as risk, opportunity, anomaly, or trend and described in plain business language with no raw statistical jargon in the output text
**Plans**: TBD

### Phase 5: Orchestrator Restructure
**Goal**: The orchestrator runs the full Analyst+Critic investigation loop (Ralph Loop Gate 1) for each column, enforces the df boundary structurally, and produces a complete per-column findings set
**Depends on**: Phase 4 (LLM Analyst), Phase 3 (Ralph Loop)
**Requirements**: (integration phase — no exclusive requirements; enables RPT-04 output contract to be met)
**Success Criteria** (what must be TRUE):
  1. Running the agent end-to-end on a sales CSV produces per-column findings for all high-risk columns, each Critic-approved or exhausted after 5 iterations, without any exception propagating to the user
  2. No agent module (llm_analyst, critic_agent, insight_generator) receives a `pd.DataFrame` object — confirmed by running a sentinel-df smoke test where any unexpected df access raises immediately
  3. The orchestrator loop handles a column whose Analyst consistently fails Critic review — it logs the exhaustion warning, uses the best attempt, and continues to the next column
  4. The v2 output contract is preserved: `outputs/report.md` and `outputs/plots/` are still produced when the run completes
**Plans**: TBD

### Phase 6: Global Synthesizer + Output Review
**Goal**: All per-column findings are synthesized into a single ranked report, reviewed through Ralph Loop Gate 2, and written to disk in v2-compatible output format with optional LLM narrative
**Depends on**: Phase 5 (complete per-column findings)
**Requirements**: SYNTH-01, SYNTH-02, RPT-01, RPT-02, RPT-03, RPT-04, RPT-05
**Success Criteria** (what must be TRUE):
  1. Each high-risk column in the output report shows evidence of at least two distinct analytical angles (e.g., distribution analysis + trend analysis) before its synthesized finding appears
  2. The final `outputs/report.md` ranks all findings highest-risk first, and every finding carries a business label (risk / opportunity / anomaly / trend)
  3. When a date column is present, the report includes a temporal section with trend directions, MoM/YoY period comparisons, and forecasts (or an explicit data-quality note if forecasting was gated)
  4. The output review loop (Gate 2) runs until all three quality bar checks pass or 5 iterations are reached — the final report always exists on disk regardless
  5. When a Groq API key is set, `outputs/report_llm.md` is also generated; when no key is set, the deterministic `outputs/report.md` alone is produced and the run exits cleanly
**Plans**: TBD
**UI hint**: no

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. State Schema + Temporal Profiler | 2/2 | Complete   | 2026-03-29 |
| 2. Critic Agent | 2/2 | Complete   | 2026-03-29 |
| 3. Ralph Loop Utility | 0/2 | In progress | - |
| 4. LLM Analyst | 0/? | Not started | - |
| 5. Orchestrator Restructure | 0/? | Not started | - |
| 6. Global Synthesizer + Output Review | 0/? | Not started | - |

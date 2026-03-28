# Project State: Risk-Driven EDA Agent v3

**Last updated:** 2026-03-28
**Session:** Roadmap initialized

---

## Project Reference

**Core Value:** Surface the most important business risks and opportunities hidden in a CSV — ranked, grounded, and critic-verified — so decision-makers can act without needing to read tables.

**Current Focus:** Phase 1 — State Schema + Temporal Profiler

---

## Current Position

**Milestone:** v3 — LLM Analyst + Critic + Ralph Loop
**Phase:** 1 of 6
**Plan:** Not started
**Status:** Roadmap created, awaiting phase planning

**Progress:**
```
Phase 1 [          ] 0%   State Schema + Temporal Profiler
Phase 2 [          ] 0%   Critic Agent
Phase 3 [          ] 0%   Ralph Loop Utility
Phase 4 [          ] 0%   LLM Analyst
Phase 5 [          ] 0%   Orchestrator Restructure
Phase 6 [          ] 0%   Global Synthesizer + Output Review
```

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total | 6 |
| Phases complete | 0 |
| Requirements total | 29 |
| Requirements complete | 0 |
| Plans written | 0 |
| Plans complete | 0 |

---

## Accumulated Context

### Key Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| LLM sees signals, not raw data | Confidentiality + hallucination control in one constraint | Pending |
| Analyst + Critic (2 agents) vs. more specialized agents | Simpler coordination, clearer responsibility boundary | Pending |
| Ralph Loop at both investigation and output checkpoints | Investigation quality AND output quality both need iteration gates | Pending |
| Skip temporal analysis if no date column | Graceful degradation, no false time-series from row order | Pending |
| Extend v2 rather than rewrite | Preserve proven deterministic pipeline, reduce risk | Pending |
| statsmodels over Prophet | Prophet fails on Windows 11 without build tools; statsmodels confirmed working | Active |
| Raw openai SDK over LangChain | Zero new dependencies; already pointed at Groq's OpenAI-compatible API | Active |
| Deterministic Critic (no API calls) | LLM-vs-LLM rephrases claims, not grounds them; dict comparison is the only grounding strategy | Active |

### Active Risks

| Risk | Phase | Mitigation |
|------|-------|------------|
| `df` reaching agent modules | Phase 4+5 | build_analyst_context() helper extracts signal fields only; sentinel-df smoke test |
| Unbounded Ralph Loop | Phase 3 | for i in range(5), never while; always return best attempt |
| Forecasting on sparse data | Phase 1 | Gate behind 12-period minimum AND adfuller stationarity check |
| Token budget for wide CSVs (100+ columns) | Phase 6 | Consider top-N risk column cap before implementing global_synthesizer |
| scipy not in environment | Phase 1 | Verify before starting Phase 1; add to requirements.txt if missing |

### Technical Notes

- **New dependencies to add:** `statsmodels>=0.14.0`; verify `scipy` present
- **New directory:** `agents/` (llm_analyst.py, critic_agent.py, schemas.py)
- **New files:** `orchestrator/ralph_loop.py`, `profiling/temporal_profiler.py`, `report/global_synthesizer.py`, `state/runtime_state.py` (extend)
- **Breaking change:** `insight/critic.py` interface changes from free-text string return to `CriticVerdict(BaseModel)` — planned in Phase 2

### Todos

- [ ] Verify `scipy` is in current environment before Phase 1 starts
- [ ] Measure token budget for GlobalSynthesizer aggregate context on wide CSVs before Phase 6
- [ ] Confirm 12-period minimum for adfuller is appropriate for expected CSV sizes

### Blockers

None.

---

## Session Continuity

### How to Resume

1. Read `.planning/STATE.md` (this file) for current position
2. Read `.planning/ROADMAP.md` for phase goals and success criteria
3. Read `.planning/REQUIREMENTS.md` for requirement traceability
4. Run `/gsd:plan-phase 1` to begin Phase 1 planning

### Context Warnings

- The `df` boundary is non-negotiable — any agent module that receives a DataFrame violates both the confidentiality constraint and the hallucination control strategy simultaneously
- Phase 5 (Orchestrator Restructure) has the highest regression risk — all prior phases must be complete and tested before touching the orchestrator
- Ralph Loop must always have a hard max_iterations cap — never use `while not approved:`

---

*State initialized during roadmap creation. Updated at each phase transition via `/gsd:transition`.*

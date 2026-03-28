# Risk-Driven EDA Agent — Version 3

## What This Is

A local AI-powered exploratory data analysis agent that investigates confidential business CSV files (sales, revenue, customer data) and delivers ranked, actionable insights — without ever sending data to an external service. Version 3 extends the v2 deterministic pipeline with an LLM Analyst that drives investigation strategy and a Critic agent that blocks any hallucinated claim, producing grounded insights across distributions, anomalies, trends, period comparisons, and forecasts.

## Core Value

Surface the most important business risks and opportunities hidden in a CSV — ranked, grounded, and critic-verified — so decision-makers can act without needing to read tables.

## Requirements

### Validated

- ✓ Risk-scored column investigation (missingness, skewness, outlier ratio, entropy) — v2
- ✓ Deterministic signal extraction pipeline — v2
- ✓ Insight-triggered visualization (not unconditional) — v2
- ✓ Optional LLM narrative rewriting (Groq API) — v2
- ✓ Deterministic markdown report output — v2
- ✓ Follow-up investigation queue driven by critic — v2

### Active

- [ ] LLM Analyst drives investigation strategy (column selection, hypothesis formation, follow-up decisions)
- [ ] LLM Analyst contextualizes findings in business terms (risk/opportunity/anomaly labels)
- [ ] Critic agent validates every LLM claim against deterministic signals before output
- [ ] Critic agent forces rewrite when unsupported claims are detected
- [ ] Ralph Loop at investigation checkpoint — cycles until Critic is satisfied
- [ ] Ralph Loop at output checkpoint — refines final report until quality bar is met
- [ ] Multi-angle analysis — same data investigated from multiple analytical perspectives before synthesis
- [ ] Trend detection for time-series columns (direction: up/down/flat + confidence)
- [ ] Period comparison — month-over-month and year-over-year when date column exists
- [ ] Forecasting — next 1-3 month predictions with ranges when data quality allows
- [ ] Graceful temporal fallback — skip trend/forecast analysis if no date column detected
- [ ] Ranked insights report with risk/opportunity/anomaly labels per finding
- [ ] Works on any CSV, optimized for sales/revenue and customer datasets

### Out of Scope

- Sending data to external APIs for analysis — confidentiality requirement; LLM only receives derived signals, not raw data
- Interactive Q&A after analysis — deferred; focus is on single-run report for v3
- Dashboard or web UI — CLI-first; visualization stays as saved plot files
- Real-time streaming data — CSV batch analysis only

## Context

Built on top of v2's proven deterministic pipeline (signal extractor, risk planner, analysis tools, insight generator). The existing architecture separates concerns cleanly: profiling → signals → risk scoring → analysis → insights → report. V3 layers LLM intelligence as a strategic layer above this pipeline — the LLM sees computed signals and insights, never raw rows, which is both the hallucination control strategy and the confidentiality guarantee.

**Why this project exists:** Business datasets are confidential and cannot be uploaded to Claude or ChatGPT. Humans reviewing tables miss patterns. The agent provides the analytical depth of an AI without the data leaving the local machine.

**Ralph Loop context:** The ralph-loop skill runs Claude in iterative cycles. In v3, it gates two checkpoints — the investigation cycle (loop until Critic approves the analysis) and the output review cycle (loop until report meets quality bar).

**Existing v2 modules to preserve and extend:**
- `profiling/signal_extractor.py` — keep as-is, add temporal signal extraction
- `planning/risk_planner.py` — extend to feed LLM Analyst context
- `execution/analysis_tools.py` — add trend, comparison, forecast tools
- `insight/critic.py` — extend into full Critic agent with hallucination checks
- `orchestrator/orchestrator.py` — restructure around Analyst+Critic loop

## Constraints

- **Privacy**: LLM receives only computed signals/insights, never raw CSV rows — non-negotiable confidentiality requirement
- **Local execution**: All analysis runs locally; only Groq API call is for narrative rewriting (optional)
- **Determinism**: Numeric results must come from the deterministic pipeline only; LLM cannot modify statistics
- **Tech stack**: Python, existing v2 dependencies; Groq API optional for LLM calls
- **Compatibility**: Must retain v2 output format (report.md, plots/) so existing users aren't broken

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LLM sees signals, not raw data | Confidentiality + hallucination control in one constraint | — Pending |
| Analyst + Critic (2 agents) vs. more specialized agents | Simpler coordination, clearer responsibility boundary | — Pending |
| Ralph Loop at both investigation and output checkpoints | Investigation quality AND output quality both need iteration gates | — Pending |
| Skip temporal analysis if no date column | Graceful degradation, no false time-series from row order | — Pending |
| Extend v2 rather than rewrite | Preserve proven deterministic pipeline, reduce risk | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-28 after initialization*

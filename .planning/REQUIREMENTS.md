# Requirements: Risk-Driven EDA Agent v3

**Defined:** 2026-03-28
**Core Value:** Surface the most important business risks and opportunities hidden in a CSV — ranked, grounded, and critic-verified — so decision-makers can act without needing to read tables.

## v1 Requirements

### LLM Analyst Agent

- [ ] **ANLST-01**: LLM Analyst selects the next column to investigate based on risk scores and prior findings
- [ ] **ANLST-02**: LLM Analyst forms a testable hypothesis before each analysis tool is invoked
- [ ] **ANLST-03**: LLM Analyst recommends which analysis tools to run based on column signals
- [ ] **ANLST-04**: LLM Analyst labels each finding as risk, opportunity, or anomaly
- [ ] **ANLST-05**: LLM Analyst explains each finding in plain business language without statistical jargon
- [ ] **ANLST-06**: LLM Analyst receives only computed signal dicts — never raw CSV rows or column values

### Critic Agent

- [x] **CRIT-01**: Critic agent validates every LLM claim against deterministic signals before the finding is accepted
- [x] **CRIT-02**: Critic agent rejects any claim that cannot be traced to a value in `signals` or `analysis_results`
- [x] **CRIT-03**: Critic agent returns a structured `CriticVerdict` with approved flag and list of rejected claims
- [x] **CRIT-04**: Critic agent is fully deterministic — no LLM call, no API dependency
- [x] **CRIT-05**: Rejected findings trigger Analyst rewrite with critic feedback included in next prompt

### Ralph Loop — Investigation Checkpoint

- [ ] **LOOP-01**: Investigation loop runs until Critic approves the insight batch or max iterations (5) reached
- [ ] **LOOP-02**: Each loop iteration passes prior rejection feedback to the Analyst for the next attempt
- [ ] **LOOP-03**: Loop exits gracefully after max iterations with best available result, never blocking run completion

### Ralph Loop — Output Review Checkpoint

- [ ] **LOOP-04**: Output review loop runs after global synthesis until report quality bar is met or max iterations reached
- [ ] **LOOP-05**: Quality bar checks: all findings have business labels, no unsupported numeric claims, ranked order present

### Multi-Angle Synthesis

- [ ] **SYNTH-01**: Agent investigates each high-risk column from at least two analytical angles before synthesizing findings
- [ ] **SYNTH-02**: Global synthesizer combines per-column findings into a unified ranked report before output review loop

### Temporal Analysis

- [x] **TEMP-01**: Agent detects date/time columns automatically using `pd.to_datetime` with parse success rate gate (>80%)
- [x] **TEMP-02**: Agent computes trend direction (up/down/flat) with confidence level for each numeric column when date column present
- [x] **TEMP-03**: Agent computes month-over-month and year-over-year deltas for numeric columns when date column present
- [x] **TEMP-04**: Agent forecasts next 1-3 month values with uncertainty ranges when >= 12 data points and stationarity check passes
- [x] **TEMP-05**: Agent outputs "No date column detected — trend analysis skipped" when no parseable date column found
- [x] **TEMP-06**: Agent flags irregular time series gaps before computing period comparisons

### Output & Report

- [ ] **RPT-01**: Final report ranks all findings by importance (highest-risk first)
- [ ] **RPT-02**: Each finding includes a business label (risk / opportunity / anomaly / trend)
- [ ] **RPT-03**: Report includes a temporal section with trends, comparisons, and forecasts when date column detected
- [ ] **RPT-04**: Report preserves v2 output format: `outputs/report.md` + `outputs/plots/`
- [ ] **RPT-05**: Optional LLM narrative report (`outputs/report_llm.md`) still generated via Groq when API key set

---

## v2 Requirements

Deferred to future release.

### Interactive Analysis
- **IQNA-01**: After run completes, user can ask follow-up questions about the dataset in natural language
- **IQNA-02**: Agent maintains session context to answer questions referencing prior findings

### Output Formats
- **OUT-01**: HTML report with embedded interactive plots
- **OUT-02**: Executive summary slide export (PDF)

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Sending raw CSV data to external APIs | Confidentiality requirement — LLM sees signals only |
| LLM modifying statistics or recalculating values | Hallucination + correctness risk — numerics are deterministic only |
| Dashboard or web UI | CLI-first for v3; adds frontend complexity with no analytical value |
| Streaming / real-time data | CSV batch analysis only |
| Prescriptive business decisions ("you should do X") | Agent surfaces findings; human decides |
| Multiple forecast model selection UI | Over-engineered for this scope |
| Row-level anomaly flagging (flag specific records) | Column-level analysis only for v3 |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEMP-01 | Phase 1 | Complete |
| TEMP-02 | Phase 1 | Complete |
| TEMP-03 | Phase 1 | Complete |
| TEMP-04 | Phase 1 | Complete |
| TEMP-05 | Phase 1 | Complete |
| TEMP-06 | Phase 1 | Complete |
| CRIT-01 | Phase 2 | Complete |
| CRIT-02 | Phase 2 | Complete |
| CRIT-03 | Phase 2 | Complete |
| CRIT-04 | Phase 2 | Complete |
| CRIT-05 | Phase 2 | Complete |
| LOOP-01 | Phase 3 | Pending |
| LOOP-02 | Phase 3 | Pending |
| LOOP-03 | Phase 3 | Pending |
| LOOP-04 | Phase 3 | Pending |
| LOOP-05 | Phase 3 | Pending |
| ANLST-01 | Phase 4 | Pending |
| ANLST-02 | Phase 4 | Pending |
| ANLST-03 | Phase 4 | Pending |
| ANLST-04 | Phase 4 | Pending |
| ANLST-05 | Phase 4 | Pending |
| ANLST-06 | Phase 4 | Pending |
| SYNTH-01 | Phase 6 | Pending |
| SYNTH-02 | Phase 6 | Pending |
| RPT-01 | Phase 6 | Pending |
| RPT-02 | Phase 6 | Pending |
| RPT-03 | Phase 6 | Pending |
| RPT-04 | Phase 6 | Pending |
| RPT-05 | Phase 6 | Pending |

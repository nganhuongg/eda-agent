# Risk-Driven EDA Agent

## Overview

This project implements a local AI-powered exploratory data analysis agent that investigates confidential business CSV files and delivers ranked, actionable insights — without sending any data to an external service.

The agent reads a CSV file, investigates it column by column in order of risk, generates visualizations, and writes a structured report. An optional AI narrative layer rewrites the deterministic findings into plain business language.

---

## Version Evolution

### Version 1: Coverage-Driven Baseline

Version 1 focused on coverage of all columns in the dataset.

The main objective was simple:

1. Load the dataset and identify column types.
2. Select columns that had not been analyzed yet.
3. Run basic statistical summaries for those columns.
4. Mark them as covered.
5. Repeat until all columns had been visited.

This design worked well as a baseline because it guaranteed broad exploration and made termination easy to define. Once every column had been inspected at least once, the run could stop.

However, Version 1 had an important limitation: coverage does not reflect importance. A stable low-risk column and a highly problematic column could receive the same attention. That meant the agent was systematic, but not selective or adaptive.

### Version 2: Risk-Driven Agent

Version 2 shifts from coverage-first exploration to risk-driven investigation.

Instead of only asking whether a column has been visited, the agent asks:

- Which column currently has the highest risk?
- Does this column require deeper follow-up investigation?

The Version 2 workflow:

1. Profile the dataset and collect column metadata.
2. Extract deterministic signals: missingness, skewness, variance, entropy, outlier ratio.
3. Compute a risk score for each column.
4. Investigate the highest-risk unexplored column.
5. Generate rule-based insights from the analysis results.
6. Let the critic decide whether follow-up analysis is needed.
7. Trigger visualizations only when the insight layer justifies them.
8. Write a deterministic report, with optional LLM narrative rewriting.

What improved from V1 to V2:

- V1 prioritized breadth of coverage; V2 prioritizes analytical importance.
- V1 treated columns more uniformly; V2 adapts investigation depth based on signals.
- V1 mainly ensured every column was visited; V2 supports follow-up actions such as outlier checks, missingness analysis, and correlation analysis.

### Version 3: Agentic AI — The Major Milestone

Version 3 is a fundamental shift in what kind of system this is.

Versions 1 and 2 were deterministic pipelines with a fixed program flow. The agent followed a script: extract signals, score risk, run tool, generate insight, repeat. Every decision was pre-programmed. The LLM in Version 2 was only allowed to rewrite the final narrative — it had no influence over what was investigated or why.

**Version 3 is a genuine AI agent.** The LLM is no longer a narrator at the end of the pipeline. It is the investigator driving the analysis from within the loop.

#### Why Version 3 Is Agentic AI

An AI agent is a system that follows this cycle:

```
Observe → Reason → Decide → Act → Observe again
```

The key property is that **the agent's decisions change what happens next**, and it continues this loop until a goal condition is met — not until a fixed script runs out of steps.

Version 3 has all of these properties:

| Property | How Version 3 implements it |
|---|---|
| **Perceives state** | The LLM Analyst reads computed signals for each column — missingness ratio, skewness, outlier ratio, entropy, trend direction |
| **Reasons** | The Analyst forms a hypothesis before acting: *"This column has high skewness and 18% missingness — I expect outlier-driven distortion. I recommend outlier detection followed by missing pattern analysis."* |
| **Decides autonomously** | The Analyst selects which column to investigate next and which tools to run, based on reasoning — not a fixed script |
| **Acts** | Analysis tools execute deterministically on the selected column |
| **Evaluates outcomes** | The Critic agent checks whether the findings are grounded in actual computed values |
| **Loops until satisfied** | The Ralph Loop repeats the investigation until the Critic approves, or the iteration cap is reached |

This is not a chatbot. It does not wait for user input between steps. It runs autonomously, makes decisions, evaluates its own output, and produces a final report — all without human intervention during the run.

#### What the Critic Agent Does

The Critic is the hallucination control mechanism. Every claim the LLM Analyst makes must be traceable to a number that came from the deterministic pipeline.

If the Analyst says *"this column has a high outlier rate"*, the Critic checks `outlier_ratio` in the signal dict. If the value is 0.003, the claim is rejected and the Analyst must revise. If the value is 0.31, the claim is approved.

The Critic makes zero API calls. It is pure Python logic. This is by design:

- An LLM evaluating another LLM does not ground claims — it only rephrases them.
- Grounding means comparison against numbers that came from actual computation.
- The Critic is the trust boundary between probabilistic AI and deterministic facts.

#### What the Ralph Loop Does

The Ralph Loop is an iterative refinement gate. It runs at two checkpoints:

**Investigation checkpoint** — after each insight is generated:
- The Critic evaluates the Analyst's finding.
- If rejected, the Analyst receives the list of rejected claims and tries again.
- The loop exits when the Critic approves, or after 5 iterations.
- The run never blocks: after 5 iterations, the best available result is used.

**Output review checkpoint** — after global synthesis:
- The full ranked report is evaluated against quality criteria.
- Quality bar: every finding has a business label, no unsupported numeric claims, findings are ranked by importance.
- If the bar is not met, the synthesizer revises and the loop runs again.

This two-checkpoint design addresses two different failure modes: individual finding errors and synthesis-level assembly errors.

#### Privacy Architecture

A key constraint in Version 3 is that **the LLM never receives raw CSV data**.

Business datasets are confidential. They cannot be sent to an external service for analysis. Version 3 enforces this at the architecture level:

- The `df: pd.DataFrame` object is held exclusively by `orchestrator.py`.
- All agent modules — `llm_analyst`, `critic_agent`, report modules — receive only computed signal dicts from the deterministic pipeline.
- The LLM sees descriptions like: `{"outlier_ratio": 0.18, "skewness": 2.4, "missing_ratio": 0.12}` — never the actual row values.

This constraint simultaneously solves confidentiality and hallucination control. The LLM cannot invent values it was never given.

#### New Capabilities in Version 3

**Temporal analysis (when a date column is detected):**

- Trend direction per numeric column: up / down / flat, with confidence level.
- Month-over-month and year-over-year comparisons.
- Forecast for the next 1–3 months with uncertainty ranges, when data quality allows (minimum 12 data points, stationarity check).
- Explicit skip message when no date column is found — the run still completes cleanly.

**Multi-angle synthesis:**

- Each high-risk column is investigated from at least two analytical angles before a finding is synthesized.
- A global synthesizer combines per-column findings into a unified ranked report.

**Business-oriented output:**

- Every finding is labeled: risk, opportunity, anomaly, or trend.
- Findings are ranked by importance — most critical first.
- Written in plain language, not statistical jargon.

**Web UI:**

- Upload a CSV file in the browser.
- View risk rankings, insights, anomaly findings, and visualizations inline.
- Download the deterministic report and the optional AI narrative report.

#### Version Comparison

| Capability | V1 | V2 | V3 | V4 (Planned) |
|---|---|---|---|---|
| Column investigation order | Fixed (coverage) | Risk-scored | LLM Analyst decides | LLM Analyst + business context |
| LLM role | None | Narrative rewriting only | Drives investigation strategy | Strategy + context-aware interpretation |
| Hallucination control | None | None | Critic agent (deterministic) | Critic + business threshold validation |
| Self-correction | None | Rule-based follow-up | Ralph Loop with feedback | Ralph Loop with feedback |
| Temporal analysis | None | None | Trend, MoM/YoY, forecast | Trend + declared seasonal patterns |
| Output labels | None | None | Risk / opportunity / anomaly / trend | Labels informed by business definitions |
| Output ranking | None | None | Ranked by importance | Ranked by importance + business priority |
| Privacy enforcement | N/A | Convention | Architectural boundary | Architectural boundary |
| Business context | None | None | None | Company context file (YAML/JSON) |
| UI | CLI only | CLI only | Streamlit web UI | Streamlit web UI |

### Version 4: Context-Aware Agent (Planned)

Version 4 introduces **company context files** — structured documents that describe the business domain, column semantics, KPI definitions, known data issues, and analyst preferences. The agent reads this context before investigation and uses it to generate insights that are grounded in both statistical signals and business meaning.

Examples of what company context unlocks:

- A column named `rev` is understood as `monthly recurring revenue` — the agent labels findings accordingly instead of treating it as an unknown numeric.
- A known seasonal pattern (e.g. "Q4 always spikes") is declared in context — the agent does not flag Q4 outliers as anomalies.
- Business thresholds are declared (e.g. "refund_rate > 5% is a critical risk") — the Analyst can reason against these thresholds instead of relying only on statistical deviation.
- Column relationships are declared (e.g. "profit is derived from revenue minus cost") — the agent can validate internal consistency and flag contradictions.

The context file format is TBD (likely YAML or JSON), and the Analyst prompt will be extended to include a context section alongside the signal dict. The Critic will also be extended to validate claims against declared business thresholds in addition to computed statistics.

---

## What the Agent Does (V3)

For each high-risk column, the agent:

1. Extracts deterministic signals: missingness, skewness, variance, entropy, outlier ratio, trend direction.
2. Passes a signal summary (never raw data) to the LLM Analyst.
3. The Analyst forms a hypothesis and recommends analysis tools.
4. Analysis tools run deterministically and return results.
5. The Analyst generates a finding with a business label.
6. The Critic validates the finding against computed values.
7. If rejected, the Analyst revises (Ralph Loop, up to 5 iterations).
8. If approved, the finding is added to the report.
9. After all columns, the global synthesizer ranks all findings.
10. The output review loop validates the final report (Ralph Loop, up to 5 iterations).
11. The deterministic report is written to `outputs/report.md`.
12. If an API key is set, an AI narrative version is written to `outputs/report_llm.md`.

Main loop: `observe → reason → act → evaluate → update state → repeat`

---

## Project Structure

```
eda_agent/
├── app.py              Streamlit web UI entry point
├── main.py             CLI entry point
├── config.py           Agent configuration (MAX_STEPS)
├── .env.local          API keys (not committed to git)
├── data/               Input CSV files
├── outputs/            Generated reports and plots
├── execution/          Analysis tools (distribution, outliers, missing, correlation)
├── insight/            Critic and insight generation
├── orchestrator/       Agent loop
├── planning/           Risk scoring and investigation planning
├── profiling/          Signal extraction and dataset profiling
├── report/             Report writing (deterministic + LLM narrative)
├── state/              Runtime agent state
└── visualization/      Plot generation
```

---

## Requirements

- Windows PowerShell
- Python environment with the packages in `requirements.txt`

This repo already uses a local virtual environment at `.venv`.

---

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## API Key Setup

Copy `.env.local.example` or create `.env.local` in the project root:

```
MINIMAX_API_KEY=your_key_here
MINIMAX_BASE_URL=https://api.minimax.chat/v1
MINIMAX_MODEL=MiniMax-Text-01
```

The AI narrative report (`outputs/report_llm.md`) is generated only when `MINIMAX_API_KEY` is set. The deterministic analysis always runs regardless.

---

## How to Run

**Web UI (recommended):**

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

Open `http://localhost:8501`, upload a CSV file, and click Run Analysis.

**CLI:**

```powershell
.\.venv\Scripts\python.exe main.py
```

The default input file is `data/sample.csv`. To use a different dataset, edit the `file_path` value in `main.py`.

---

## Outputs

After a run:

- `outputs/report.md` — deterministic ranked insights report
- `outputs/plots/` — insight-triggered visualizations
- `outputs/report_llm.md` — AI narrative version (only when API key is set)

---

## LLM Safety Rule

The LLM is restricted to interpretation and strategy only.

It must not:

- Modify numeric values
- Recalculate statistics
- Invent new measurements
- Change deterministic analysis results

All numeric results come from the deterministic pipeline. The Critic agent enforces this at runtime by rejecting any LLM claim that cannot be traced to a computed value.

---

## Main Files

- `app.py` — Streamlit web UI
- `main.py` — CLI entrypoint
- `orchestrator/orchestrator.py` — agent loop
- `profiling/signal_extractor.py` — deterministic signal extraction
- `planning/risk_planner.py` — risk scoring and planning
- `execution/analysis_tools.py` — analysis actions
- `insight/insight_generator.py` — categorical insight mapping
- `insight/critic.py` — follow-up investigation suggestions
- `report/report_generator.py` — deterministic reporting
- `report/llm_report_writer.py` — AI narrative rewriting (MiniMax API)

---

## Notes

- Boolean columns are treated as categorical features.
- Visualization is insight-driven, not unconditional.
- Temporal analysis (trends, comparisons, forecasts) requires a parseable date column.
- If the LLM API is unavailable, the deterministic run still completes successfully.

# Risk-Driven EDA Agent

## Overview

This project implements a Version 2 exploratory data analysis agent that prioritizes investigation by risk instead of simple column coverage.

The agent is deterministic for all numeric computation and state updates. An LLM is optional and is limited to narrative report rewriting only. It does not control planning, tool execution, or numeric results.

## Version Evolution

### Version 1: Coverage-Driven Baseline

Version 1 of the agent focused on coverage of all columns in the dataset.

The main objective was simple:

1. Load the dataset and identify column types.
2. Select columns that had not been analyzed yet.
3. Run basic statistical summaries for those columns.
4. Mark them as covered.
5. Repeat until all columns had been visited.

This design worked well as a baseline because it guaranteed broad exploration and made termination easy to define. Once every column had been inspected at least once, the run could stop.

However, Version 1 had an important limitation: coverage does not reflect importance. A stable low-risk column and a highly problematic column could receive the same attention. That meant the agent was systematic, but not selective or adaptive.

### Version 2: Risk-Driven Agent

Version 2 improves the agent by shifting from coverage-first exploration to risk-driven investigation.

Instead of only asking whether a column has been visited, the agent now asks:

- Which column currently has the highest risk?
- Does this column require deeper follow-up investigation?

The Version 2 workflow is:

1. Profile the dataset and collect column metadata.
2. Extract deterministic signals such as missingness, skewness, variance, entropy, and outlier ratio.
3. Compute a risk score for each column.
4. Investigate the highest-risk unexplored column.
5. Generate rule-based insights from the analysis results.
6. Let the critic decide whether follow-up analysis is needed.
7. Trigger visualizations only when the insight layer justifies them.
8. Write a deterministic report, with optional LLM narrative rewriting.

### What Improved From V1 To V2

- Version 1 prioritized breadth of coverage; Version 2 prioritizes analytical importance.
- Version 1 treated columns more uniformly; Version 2 adapts investigation depth based on signals and insights.
- Version 1 mainly ensured every column was visited; Version 2 supports follow-up actions such as outlier checks, missingness analysis, and correlation analysis.
- Version 1 was a useful baseline; Version 2 is more targeted, anomaly-aware, and useful for real investigation.

## What The Agent Does

For each dataset column, the agent:

1. Profiles the dataset and records metadata.
2. Extracts signals such as missingness, skewness, variance, entropy, and outlier ratio.
3. Scores column risk.
4. Plans the next investigation based on the highest-risk unexplored column or critic-recommended follow-up work.
5. Runs analysis tools.
6. Converts raw analysis into categorical insights.
7. Triggers visualizations only when the insights justify them.
8. Writes a deterministic markdown report.

The main loop is:

`observe -> assess -> plan -> act -> evaluate -> update state -> repeat`

## Global Agent State

The runtime state includes:

- `dataset_metadata`
- `signals`
- `risk_scores`
- `analysis_results`
- `insights`
- `investigation_queue`
- `analyzed_columns`
- `action_history`

## Analysis Signals

Numeric columns:

- `mean`
- `std`
- `skewness`
- `missing_ratio`
- `outlier_ratio`

Categorical columns:

- `unique_count`
- `dominant_ratio`
- `entropy`
- `missing_ratio`

## Available Analysis Tools

- `analyze_distribution`
- `detect_outliers`
- `analyze_missing_pattern`
- `analyze_correlation`

## Project Structure

```text
eda_agent/
├── config.py
├── main.py
├── data/
├── execution/
├── insight/
├── orchestrator/
├── planning/
├── profiling/
├── report/
├── state/
├── visualization/
└── outputs/
```

## Requirements

- Windows PowerShell
- Python environment with the packages in `requirements.txt`

This repo already uses a local virtual environment at `.venv`. Use it if your system Python does not have the required packages.

## Install

Create and activate a virtual environment if needed:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## How To Run The Agent

The default input file is:

```text
data/sample.csv
```

Run the agent from the repo root:

```powershell
.\.venv\Scripts\python.exe main.py
```

If your active Python already has the dependencies installed, this also works:

```powershell
python main.py
```

## How To Use A Different Dataset

Edit the `file_path` value in [main.py](eda_agent/main.py) and point it to another CSV file.

Current code expects a CSV readable by `pandas.read_csv`.

## Outputs

After a run, the agent writes:

- `outputs/report.md`
- `outputs/plots/` for insight-triggered visualizations

If `GROQ_API_KEY` is set and the network is available, it can also write:

- `outputs/report_llm.md`

## Report Contents

The deterministic report includes:

- Risk ranking of columns
- Extracted signals
- Investigation history
- Analysis results
- Anomaly findings
- Generated visualizations

## LLM Safety Rule

The LLM is optional and restricted to narrative rewriting.

It must not:

- Modify numeric values
- Recalculate statistics
- Invent new measurements
- Change deterministic analysis results

All numeric results come from the deterministic pipeline only.

## Main Files

- [main.py](eda_agent/main.py): entrypoint
- [orchestrator.py](eda_agent/orchestrator/orchestrator.py): agent loop
- [signal_extractor.py](eda_agent/profiling/signal_extractor.py): deterministic signal extraction
- [risk_planner.py](eda_agent/planning/risk_planner.py): risk scoring and planning
- [analysis_tools.py](eda_agent/execution/analysis_tools.py): analysis actions
- [insight_generator.py](eda_agent/insight/insight_generator.py): categorical insight mapping
- [critic.py](eda_agent/insight/critic.py): follow-up investigation suggestions
- [report_generator.py](eda_agent/report/report_generator.py): deterministic reporting

## Notes

- Boolean columns are treated as categorical features.
- Visualization is insight-driven, not unconditional.
- If the optional LLM report cannot reach the API, the main run still completes successfully.

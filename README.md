# Risk-Driven EDA Agent

## Overview

This project implements a Version 2 exploratory data analysis agent that prioritizes investigation by risk instead of simple column coverage.

The agent is deterministic for all numeric computation and state updates. An LLM is optional and is limited to narrative report rewriting only. It does not control planning, tool execution, or numeric results.

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

Edit the `file_path` value in [main.py](d:/Test/eda_agent/main.py) and point it to another CSV file.

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

- [main.py](d:/Test/eda_agent/main.py): entrypoint
- [orchestrator.py](d:/Test/eda_agent/orchestrator/orchestrator.py): agent loop
- [signal_extractor.py](d:/Test/eda_agent/profiling/signal_extractor.py): deterministic signal extraction
- [risk_planner.py](d:/Test/eda_agent/planning/risk_planner.py): risk scoring and planning
- [analysis_tools.py](d:/Test/eda_agent/execution/analysis_tools.py): analysis actions
- [insight_generator.py](d:/Test/eda_agent/insight/insight_generator.py): categorical insight mapping
- [critic.py](d:/Test/eda_agent/insight/critic.py): follow-up investigation suggestions
- [report_generator.py](d:/Test/eda_agent/report/report_generator.py): deterministic reporting

## Notes

- Boolean columns are treated as categorical features.
- Visualization is insight-driven, not unconditional.
- If the optional LLM report cannot reach the API, the main run still completes successfully.

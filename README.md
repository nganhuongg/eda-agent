# Governed EDA Agent

## Overview

This project implements a bounded autonomous Exploratory Data Analysis (EDA) agent with deterministic governance and structured LLM-based report synthesis.

Unlike typical LLM-based data tools, this system separates:

- Deterministic control logic
- Stochastic policy (planner)
- Deterministic statistical execution
- Structured semantic interpretation
- Controlled LLM narrative generation

The result is a layered analytical agent that preserves correctness while leveraging generative AI safely.

---

## Core Architecture

The system follows a multi-layer control architecture:

Dataset (Environment)

↓

Profiler

↓

Planner (stochastic)

↓

Controller (deterministic governance)

↓

Executor (statistical feature extraction)

↓

Structured Insight Layer

↓

Visualization Layer

↓

Deterministic Report Template

↓

LLM Narrative Rewriter

↓

Numeric Validation Guardrail


### Deterministic Layers

- Profiler (metadata extraction)
- Controller (bounded retry + progress enforcement)
- Executor (mean, std, skewness, missing ratio, dominance ratio)
- Insight mapping (categorical schema)
- Visualization generation
- Report template
- Numeric hallucination validator

### Stochastic Layers

- Coverage-biased planner
- LLM narrative rewriter (constrained, non-governing)

The LLM does not control termination, retry logic, or state mutation.

---

## Governance Design

The agent uses a bounded retry mechanism:

- Retry counts consecutive non-progress events.
- Termination occurs on:
  - Full coverage
  - MAX_RETRY exceeded
- State mutation is transactional and only occurs on successful execution.

This prevents infinite loops and hallucination-driven control flow.

---

## Insight Schema

### Numeric Columns

- variance_level: low | moderate | high
- skewness_direction: left | right | symmetric
- data_quality_flag: clean | moderate_missing | high_missing

### Categorical Columns

- balance_level: balanced | moderate_imbalance | high_imbalance
- cardinality_level: low | medium | high

---

## Visual Outputs

- Missing value heatmap
- Distribution plots for numeric features
- Category frequency plots for categorical features

---

## LLM Safety Mechanism

The LLM is restricted to narrative rewriting only.

After generation:

- All numerical values are extracted.
- They are compared against deterministic report.
- Mismatch triggers validation failure.

This enforces numeric consistency.

---

## Project Structure

eda_agent/

│

├── config.py

├── main.py

│

├── profiling/

├── planning/

├── controller/

├── execution/

├── insight/

├── visualization/

├── report/

│

└── outputs/


---

## Example Outputs

- Markdown audit report
- Enhanced LLM technical report
- Generated plots

---

## Version 1 Scope

- Governed coverage-based exploration
- Deterministic statistical analysis
- Structured semantic interpretation
- Controlled LLM narrative generation

---

## Future Work (Version 2+)

- Semantic critic influencing retry logic
- Adaptive planner based on risk signals
- Multi-objective optimization (coverage + anomaly detection)
- Interactive tool-use via natural language
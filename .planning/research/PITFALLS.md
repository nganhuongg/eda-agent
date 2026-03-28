# Pitfalls Research — EDA Agent v3

## Confidence: HIGH — derived from v2 codebase analysis + domain knowledge

---

## LLM Hallucination Control

### Pitfall 1: LLM Receives More Context Than It Needs
**Warning sign:** Agent function signatures accept `state: AgentState` and access `state.df` or raw row data inside the function.
**Prevention:** Analyst and Critic receive only a pre-serialized signal dict. Build a `build_analyst_context(state)` helper that extracts exactly the fields the LLM needs — no more. Audit every new LLM call site.
**Phase:** Phase 4 (LLM Analyst implementation)

### Pitfall 2: Critic Is LLM-Based
**Warning sign:** `critic_agent.py` makes a Groq API call to evaluate Analyst output.
**Prevention:** Critic is pure Python dict comparison. For every numeric claim in `AnalystDecision.reasoning`, extract the referenced value and compare against `signals` or `analysis_results`. If no matching key exists, reject. Zero API calls in the Critic.
**Phase:** Phase 2 (Critic agent)

### Pitfall 3: Unstructured LLM Output Accepted Without Validation
**Warning sign:** Code does `response.choices[0].message.content` and parses it with string splitting or regex.
**Prevention:** Always use `model_validate_json(response_text)` on a Pydantic BaseModel. If validation fails, treat as rejection — do not attempt to salvage partial output. Log the raw response for debugging.
**Phase:** Phase 4 (LLM Analyst)

---

## Critic-Analyst Loop Mechanics

### Pitfall 4: Unbounded Retry Loop
**Warning sign:** `while not approved:` with no exit condition.
**Prevention:** Always `for i in range(max_iterations)` with `max_iterations=5`. After exhausting retries, return the best attempt with a flag `{"approved": false, "final_attempt": true}` and log a warning. Never block report generation entirely on loop failure.
**Phase:** Phase 3 (Ralph Loop utility)

### Pitfall 5: Feedback Not Passed to Next Iteration
**Warning sign:** Each Analyst call receives the same context regardless of what the Critic rejected.
**Prevention:** The `ralph_loop` utility must append `verdict.rejected_claims` to context before the next generation call. Analyst prompt must include a "Previous feedback to address:" section. Without this, the loop reruns identically and always hits `max_iterations`.
**Phase:** Phase 3 (Ralph Loop utility)

---

## Temporal Analysis Failures

### Pitfall 6: Assuming Date Column Is Always Well-Formed
**Warning sign:** `pd.to_datetime(df[col])` called without error handling, crashing on mixed formats or nulls.
**Prevention:** Date detection in `temporal_profiler.py` should use `pd.to_datetime(..., errors='coerce')` and only proceed if parse success rate > 80%. Otherwise, log "Date column detected but unparseable — temporal analysis skipped."
**Phase:** Phase 1 (Temporal profiler)

### Pitfall 7: Forecasting on Insufficient Data
**Warning sign:** `ExponentialSmoothing` called on series with fewer than 12 data points, producing wide/meaningless intervals.
**Prevention:** Gate forecasting behind a minimum data point check (e.g., >= 12 periods) AND an `adfuller` stationarity test. If either fails, output direction-only trend and note "Insufficient data for forecast range."
**Phase:** Phase 1 (Temporal profiler) + execution tools

### Pitfall 8: Period Comparison on Irregular Time Series
**Warning sign:** MoM comparison calculated as `df.groupby(month)` on data with missing months, producing misleading deltas.
**Prevention:** Detect gaps in the time series before computing period comparisons. If gaps > 2 consecutive periods exist, flag in report: "Irregular intervals detected — comparison may be unreliable."
**Phase:** Phase 1 (Temporal profiler)

---

## Data Confidentiality

### Pitfall 9: Column Names or Values Leaking Into LLM Prompts
**Warning sign:** Analyst prompt includes `f"Column '{col_name}' has value '{sample_value}'"`.
**Prevention:** LLM prompts should reference columns by their signal profile only (e.g., "a numeric column with high skewness and 12% missing ratio"), not by name or sample values. Column names may contain PII or business-sensitive terms.
**Phase:** Phase 4 (LLM Analyst)

---

## Groq API Handling

### Pitfall 10: Groq Rate Limit Crashing the Agent Loop
**Warning sign:** Groq 429 error propagates as an unhandled exception, aborting the entire run.
**Prevention:** Wrap all Groq calls in retry logic with exponential backoff (same pattern already used in `llm_report_writer.py`). If retries exhausted, fall back to deterministic output only — do not crash. This preserves the v2 guarantee that the run always completes.
**Phase:** Phase 4 (LLM Analyst)

---

## V2 Code Issues That Affect V3

### Note 1: `critic.py` Returns Strings, Not Structured Data
Current `critic.py` returns free-text follow-up suggestions. v3's Critic must return `CriticVerdict(BaseModel)` for programmatic consumption by the Ralph Loop. Plan a breaking interface change here.
**Phase:** Phase 2 (Critic agent)

### Note 2: `orchestrator.py` Passes `df` Into Multiple Modules
The current orchestrator passes `df` into `signal_extractor`, `analysis_tools`, and others by reference. While these are deterministic modules (safe), the pattern normalizes passing `df` around. When adding LLM agent modules in v3, explicitly block `df` from reaching them via architecture convention, not just trust.
**Phase:** Phase 5 (Orchestrator restructure)

### Note 3: No Max-Iteration Guard in Current Investigation Loop
The v2 loop terminates on `analyzed_columns` coverage — safe for deterministic tools. The v3 Ralph Loop within this outer loop could cause nested looping. Ensure the outer orchestrator loop has its own independent termination guard.
**Phase:** Phase 5 (Orchestrator restructure)

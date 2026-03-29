# Phase 1: State Schema + Temporal Profiler - Research

**Researched:** 2026-03-28
**Domain:** Python time-series signal extraction — statsmodels, pandas DatetimeIndex, AgentState extension
**Confidence:** HIGH

---

## Summary

Phase 1 is a pure-Python, no-LLM, no-API-call phase. It extends the existing `AgentState` TypedDict with a `temporal_signals` key and creates `profiling/temporal_profiler.py` — a new module that detects date columns, computes OLS trend slopes, MoM/YoY deltas, flags irregular gaps, and gates forecasting behind a 12-point minimum + ADF stationarity check. All work is deterministic and offline-testable.

The integration point is `main.py`: after `profile_dataset()` returns `(df, metadata, total_columns)`, a new call to `temporal_profiler.profile_temporal(df, metadata)` is added. Its return value (a `TemporalResult` TypedDict or dict) is stored in `state["temporal_signals"]`. The orchestrator does not change in this phase. `AgentState` is extended using `TypedDict` inheritance (`total=False` on the new key), preserving all existing v2 field access.

The two critical gating rules from prior research are confirmed by this technical investigation: (1) `adfuller` p-value < 0.05 means stationary — only then proceed to `ExponentialSmoothing` forecasting; (2) the 12-point minimum gate should be checked before calling `adfuller` itself, because the ADF default lag formula (`12*(nobs/100)^0.25`) is undefined for very small samples. No external blocking dependencies exist beyond installing `statsmodels>=0.14.0` and `scipy>=1.13.0` (neither is present in the venv today).

**Primary recommendation:** Create `profiling/temporal_profiler.py` as a standalone module with a single public function `profile_temporal(df, metadata) -> dict`. Extend `AgentState` with one new optional key `temporal_signals`. Wire into `main.py` after `profile_dataset`. Do not touch the orchestrator loop.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TEMP-01 | Agent detects date/time columns automatically using `pd.to_datetime` with parse success rate gate (>80%) | `pd.to_datetime(col, errors='coerce')` returns NaT for failures; `notna().mean() > 0.80` gives the gate |
| TEMP-02 | Agent computes trend direction (up/down/flat) with confidence level for each numeric column when date column present | `statsmodels.api.OLS` with `np.arange(n)` as regressor; slope sign = direction; p-value from results gives confidence |
| TEMP-03 | Agent computes month-over-month and year-over-year deltas for numeric columns when date column present | `series.resample('ME').mean()` + `.pct_change()` for MoM; `.pct_change(periods=12)` for YoY |
| TEMP-04 | Agent forecasts next 1-3 month values with uncertainty ranges when >= 12 data points and stationarity check passes | `ExponentialSmoothing(endog, trend='add').fit().forecast(steps=3)` — only after adfuller p < 0.05 and n >= 12 |
| TEMP-05 | Agent outputs "No date column detected — trend analysis skipped" when no parseable date column found | Set `state["temporal_signals"]["status"] = "No date column detected — trend analysis skipped"` |
| TEMP-06 | Agent flags irregular time series gaps before computing period comparisons | `DatetimeIndex.to_series().diff()` — compare each interval to median interval; flag if ratio > 2.0 |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `statsmodels` | >=0.14.0 | OLS slope, `adfuller` stationarity test, `ExponentialSmoothing` forecast | Confirmed working on Windows 11; Prophet rejected (C++ build requirement) |
| `pandas` | 2.3.3 (installed) | DatetimeIndex operations, `resample`, `pct_change`, `diff` | Already installed; all temporal pandas APIs confirmed current |
| `numpy` | 2.4.2 (installed) | `np.arange(n)` for OLS regressor, array ops | Already installed |
| `pydantic` | 2.12.5 (installed) | `AgentState` extension schema validation in later phases | Already installed — not used in Phase 1 directly, but schema decisions here affect Phases 2-4 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `scipy` | >=1.13.0 | Mann-Kendall trend test via `scipy.stats.kendalltau` | Optional supplementary confidence check — not required for Phase 1 core path |

**Not in stack for this phase:**
- `scipy` is absent from venv today. The core Phase 1 path (OLS + adfuller + ExponentialSmoothing) does not require it. Add it to `requirements.txt` alongside `statsmodels` to satisfy STATE.md's standing risk mitigation item, but do not write code that imports it unless Mann-Kendall is explicitly added to TEMP-02.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `statsmodels` | Prophet | Prophet requires compiled C++/Stan backend — reliably fails on Windows 11 without build tools |
| `statsmodels` ExponentialSmoothing | ARIMA | ARIMA adds order-selection complexity for a 3-month horizon; ExponentialSmoothing with `trend='add'` is sufficient |
| OLS for trend | Mann-Kendall (scipy) | Mann-Kendall is non-parametric and more robust for non-normal data, but adds a scipy dependency and is not required for this phase |

**Installation:**
```bash
pip install "statsmodels>=0.14.0" "scipy>=1.13.0"
```

**Version verification (run before implementation):**
```bash
pip show statsmodels scipy
```

---

## Architecture Patterns

### Recommended Project Structure Changes
```
profiling/
├── profiler.py          # existing — unchanged
├── signal_extractor.py  # existing — unchanged
└── temporal_profiler.py # NEW — single public function profile_temporal()

state/
└── runtime_state.py     # EXTEND — add temporal_signals key to AgentState
```

No new directories. The `agents/` directory is deferred to Phase 2.

### Pattern 1: AgentState Extension via TypedDict Inheritance

**What:** Add `temporal_signals` as a new optional key using a separate `TypedDict` that extends `AgentState`, or by adding the key directly with `total=False`.

**When to use:** Any time a new field must not break existing code that accesses the v2 fields.

**Approach — add directly to existing AgentState with `total=False` guard:**

The simplest approach is to add `temporal_signals` directly to `AgentState` with a `TypedDict` comment noting it is optional, and update `initialize_state()` to include it. TypedDict does not natively support per-field optionality in Python < 3.11 without inheritance tricks, but adding a key to `initialize_state()` with a default of `{}` is sufficient — any code that accessed the old keys continues to work unchanged.

```python
# state/runtime_state.py — extend AgentState
class AgentState(TypedDict):
    dataset_metadata: Dict[str, Dict[str, Any]]
    signals: Dict[str, Dict[str, Any]]
    risk_scores: Dict[str, float]
    analysis_results: Dict[str, Dict[str, Any]]
    insights: Dict[str, Dict[str, Any]]
    investigation_queue: List[InvestigationAction]
    analyzed_columns: Set[str]
    action_history: List[ActionRecord]
    total_columns: int
    visualizations: Dict[str, str]
    # v3 additions
    temporal_signals: Dict[str, Any]  # populated by temporal_profiler; {} if no date column


def initialize_state() -> AgentState:
    return {
        "dataset_metadata": {},
        "signals": {},
        "risk_scores": {},
        "analysis_results": {},
        "insights": {},
        "investigation_queue": [],
        "analyzed_columns": set(),
        "action_history": [],
        "total_columns": 0,
        "visualizations": {},
        "temporal_signals": {},   # empty dict — safe default
    }
```

### Pattern 2: temporal_profiler Public Interface

**What:** One public function that receives `df` and `metadata` and returns a structured dict. Internal helpers are prefixed `_`.

**When to use:** Mirrors the existing `signal_extractor.extract_signals()` and `profiler.profile_dataset()` conventions exactly.

```python
# profiling/temporal_profiler.py

from __future__ import annotations
from typing import Any, Dict
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.holtwinters import ExponentialSmoothing


def profile_temporal(
    df: pd.DataFrame,
    metadata: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Returns temporal signal dict to store in state["temporal_signals"].
    If no date column is found, returns:
        {"status": "No date column detected — trend analysis skipped"}
    """
    date_col = _detect_date_column(df)
    if date_col is None:
        return {"status": "No date column detected — trend analysis skipped"}

    date_series = pd.to_datetime(df[date_col], errors="coerce")
    df_sorted = df.copy()
    df_sorted["__date__"] = date_series
    df_sorted = df_sorted.dropna(subset=["__date__"]).sort_values("__date__")
    df_sorted = df_sorted.set_index("__date__")

    gap_flags = _detect_gaps(df_sorted.index)
    numeric_cols = [c for c, m in metadata.items() if m["type"] == "numeric" and c != date_col]

    column_signals: Dict[str, Any] = {}
    for col in numeric_cols:
        if col not in df_sorted.columns:
            continue
        series = df_sorted[col].dropna()
        column_signals[col] = _analyze_column(series)

    return {
        "status": "ok",
        "date_column": date_col,
        "gap_flags": gap_flags,
        "columns": column_signals,
    }
```

### Pattern 3: Date Column Detection (TEMP-01)

**What:** Try `pd.to_datetime` with `errors='coerce'` on each non-numeric column; accept the column if >= 80% of non-null values parse successfully.

```python
def _detect_date_column(df: pd.DataFrame) -> str | None:
    """Return the first column name that parses as datetime with >80% success."""
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        parsed = pd.to_datetime(df[col], errors="coerce")
        non_null = df[col].notna().sum()
        if non_null == 0:
            continue
        success_rate = parsed.notna().sum() / non_null
        if success_rate > 0.80:
            return col
    return None
```

**Key detail:** Only non-numeric columns are checked. Numeric columns that happen to look like Unix timestamps are excluded — this prevents misidentification of integer ID columns.

### Pattern 4: OLS Trend Slope (TEMP-02)

**What:** Fit OLS with time index as regressor. Slope sign gives direction; p-value gives confidence.

```python
def _compute_trend(series: pd.Series) -> Dict[str, Any]:
    """Compute trend direction and confidence via OLS slope."""
    n = len(series)
    if n < 3:
        return {"direction": "insufficient_data", "confidence": None, "slope": None}

    x = sm.add_constant(np.arange(n, dtype=float))
    y = series.values.astype(float)
    results = sm.OLS(y, x).fit()

    slope = float(results.params[1])
    p_value = float(results.pvalues[1])
    r_squared = float(results.rsquared)

    # Direction thresholds: p < 0.05 and slope != ~0
    if p_value >= 0.05:
        direction = "flat"
    elif slope > 0:
        direction = "up"
    else:
        direction = "down"

    # Confidence: HIGH if p < 0.01, MEDIUM if p < 0.05, LOW otherwise
    if p_value < 0.01:
        confidence = "HIGH"
    elif p_value < 0.05:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "direction": direction,
        "confidence": confidence,
        "slope": slope,
        "p_value": p_value,
        "r_squared": r_squared,
    }
```

### Pattern 5: MoM and YoY Deltas (TEMP-03)

**What:** Resample to monthly, compute period-over-period percent changes.

```python
def _compute_period_deltas(series: pd.Series) -> Dict[str, Any]:
    """Compute MoM and YoY percent change series."""
    monthly = series.resample("ME").mean()

    mom = monthly.pct_change()               # 1-period: month-over-month
    yoy = monthly.pct_change(periods=12)     # 12-period: year-over-year

    def _series_to_dict(s: pd.Series) -> Dict[str, float]:
        return {str(k.date()): round(float(v), 4) for k, v in s.dropna().items()}

    return {
        "mom_pct_change": _series_to_dict(mom),
        "yoy_pct_change": _series_to_dict(yoy),
        "monthly_points": len(monthly),
    }
```

**Key detail:** `resample('ME')` uses month-end frequency (the pandas 2.x alias — `'M'` is deprecated in pandas 2.2+). Use `'ME'` for month-end. For yearly: `'YE'` not `'Y'`.

### Pattern 6: ADF Stationarity + Forecast Gate (TEMP-04)

**What:** Gate ExponentialSmoothing behind n >= 12 AND adfuller p < 0.05.

```python
def _compute_forecast(series: pd.Series) -> Dict[str, Any]:
    """Compute 3-step forecast with gate checks."""
    n = len(series)

    if n < 12:
        return {
            "forecast": None,
            "note": "Insufficient data for forecast range",
        }

    # ADF stationarity gate — p < 0.05 means stationary (reject unit root null)
    adf_stat, p_value, *_ = adfuller(series.values, autolag="AIC")

    if p_value >= 0.05:
        return {
            "forecast": None,
            "adf_p_value": round(p_value, 4),
            "note": "Insufficient data for forecast range",
        }

    # Fit Holt-Winters additive trend, no seasonality
    try:
        model = ExponentialSmoothing(
            series.values,
            trend="add",
            seasonal=None,
            initialization_method="estimated",
        )
        fit = model.fit()
        forecast_values = fit.forecast(steps=3)  # returns ndarray of length 3
    except Exception:
        return {"forecast": None, "note": "Insufficient data for forecast range"}

    return {
        "forecast": [round(float(v), 4) for v in forecast_values],
        "adf_p_value": round(p_value, 4),
        "note": None,
    }
```

**Critical detail:** `ExponentialSmoothing` does not provide confidence intervals via `forecast()` — it returns a plain `ndarray`. For uncertainty ranges in Phase 6, use `fit.simulate(nsimulations=100, anchor="end")` to generate a distribution and compute percentile bounds. For Phase 1, returning the point forecast is sufficient; note this gap in Open Questions.

### Pattern 7: Irregular Gap Detection (TEMP-06)

**What:** Detect irregular intervals in the DatetimeIndex using `diff()` on sorted timestamps.

```python
def _detect_gaps(index: pd.DatetimeIndex) -> Dict[str, Any]:
    """Flag irregular time-series gaps."""
    if len(index) < 2:
        return {"irregular": False, "gap_count": 0, "details": []}

    diffs = pd.Series(index).diff().dropna()
    median_interval = diffs.median()

    # Flag any gap more than 2x the median interval
    threshold = median_interval * 2
    large_gaps = diffs[diffs > threshold]

    return {
        "irregular": len(large_gaps) > 0,
        "gap_count": int(len(large_gaps)),
        "median_interval_days": round(median_interval.days, 1),
        "gap_details": [
            {"at": str(index[i + 1].date()), "interval_days": diffs.iloc[i + 1].days}
            for i in large_gaps.index
            if (i + 1) < len(index)
        ],
    }
```

**Threshold choice:** 2x median interval is a pragmatic default. This catches monthly datasets where a 90-day gap exists, or daily datasets missing whole weeks. Document the threshold constant so the planner can make it configurable.

### Pattern 8: main.py Integration Point

**What:** After `profile_dataset()`, call `profile_temporal()` and store the result in state.

```python
# main.py — addition after line 17 (after profile_dataset)
from profiling.temporal_profiler import profile_temporal

# ... existing code ...
df, metadata, total_columns = profile_dataset(file_path)
state["dataset_metadata"] = metadata
state["total_columns"] = total_columns
state["temporal_signals"] = profile_temporal(df, metadata)  # NEW
```

No change to `run_agent()` call signature. `temporal_signals` is available in state throughout the orchestrator loop for later phases.

### Anti-Patterns to Avoid

- **Using `resample('M')` or `resample('Y')`:** These aliases are deprecated in pandas 2.2+. Use `'ME'` (month-end), `'MS'` (month-start), `'YE'` (year-end), `'YS'` (year-start).
- **Running adfuller on fewer than 12 points:** The lag formula `12*(nobs/100)^0.25` produces 0 lags at very small n, making the test result meaningless. Always check `n >= 12` before calling `adfuller`.
- **Calling ExponentialSmoothing on non-stationary series without the gate:** Results produce wide, meaningless intervals. The gate (`adfuller p < 0.05`) is mandatory.
- **Using `errors='raise'` in to_datetime:** Will crash the run on a single bad date value. Always use `errors='coerce'`.
- **Storing raw DataFrame rows in `temporal_signals`:** The dict must be serializable (plain Python types only). Never store `pd.Series` or `pd.DataFrame` objects in `AgentState`.
- **Detecting numeric columns as potential date columns:** A Unix timestamp column (int64) would falsely trigger date detection. Skip any `is_numeric_dtype` column in the detection loop.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Stationarity testing | Custom variance/mean stability check | `statsmodels.tsa.stattools.adfuller` | Unit root test has well-understood statistical properties; hand-rolled checks are unreliable |
| Linear trend slope + significance | Manual covariance formula | `statsmodels.api.OLS + sm.add_constant` | Built-in p-value and R² — no derivation needed |
| Exponential smoothing forecast | Rolling average or manual EWMA | `statsmodels.tsa.holtwinters.ExponentialSmoothing` | Handles initialization, damped trend, and fit optimization automatically |
| Date parsing robustness | Custom regex or strptime loop | `pd.to_datetime(errors='coerce')` | Handles >50 date format variants; coerce handles mixed/dirty data |
| Period-over-period change | Manual loop over months | `pd.Series.pct_change(periods=N)` | Handles index alignment and NaN propagation automatically |

**Key insight:** Every custom time-series utility reimplements edge cases that pandas and statsmodels have already handled for a decade. The only custom code in this phase is the orchestration glue — which columns to analyze, when to gate, how to store results.

---

## Runtime State Inventory

> Not applicable — this is a greenfield extension phase with no renaming, no migration, and no stored external state.

None — verified by reviewing all source files. No databases, no external service configs, no OS-registered state, no secrets tied to column names.

---

## Common Pitfalls

### Pitfall 1: Deprecated Pandas Resample Aliases
**What goes wrong:** `series.resample('M')` raises a `FutureWarning` in pandas 2.2 and will break in a future release. Code silently degrades.
**Why it happens:** Pandas 2.2 renamed frequency aliases. `'M'` → `'ME'`, `'Y'` → `'YE'`, `'Q'` → `'QE'`.
**How to avoid:** Always use the new aliases: `'ME'`, `'MS'`, `'YE'`, `'YS'`, `'QE'`, `'QS'`.
**Warning signs:** `FutureWarning: 'M' is deprecated` in test output.

### Pitfall 2: ExponentialSmoothing Called on Non-Stationary Series
**What goes wrong:** Forecast values diverge exponentially or produce `inf` / `nan`. The 3-step forecast is meaningless and will mislead downstream agents.
**Why it happens:** Exponential smoothing has no built-in stationarity requirement — it will run on any data.
**How to avoid:** The `adfuller` gate (p < 0.05) is mandatory before calling `ExponentialSmoothing`. If the gate fails, return `{"forecast": None, "note": "Insufficient data for forecast range"}`.
**Warning signs:** Forecast values > 10x the series mean; `nan` in forecast array.

### Pitfall 3: AgentState Key Access Breaking v2 Code
**What goes wrong:** Downstream code (e.g., `report_generator.py`, `insight_generator.py`) that accesses `state["signals"]` raises `KeyError` if `temporal_signals` addition breaks the TypedDict structure.
**Why it happens:** In Python, TypedDict keys that are added to the class definition but not to `initialize_state()` will be absent at runtime.
**How to avoid:** Add `"temporal_signals": {}` to the dict literal in `initialize_state()`. All existing code that never reads `temporal_signals` is unaffected.
**Warning signs:** `KeyError: 'temporal_signals'` in any module that reads state.

### Pitfall 4: Date Column Detecting an Integer Column as Datetime
**What goes wrong:** An integer column with values like `20230101` passes `pd.to_datetime(errors='coerce')` because pandas interprets it as a valid nanosecond timestamp or year.
**Why it happens:** `pd.to_datetime` is permissive with integer inputs in some pandas versions.
**How to avoid:** Skip any column where `pd.api.types.is_numeric_dtype(col)` returns `True` before attempting datetime parse.
**Warning signs:** `date_col` is set to an ID column; date index is sorted into implausible order.

### Pitfall 5: adfuller Crash on Very Short Series
**What goes wrong:** `adfuller` with `maxlag=None` calculates `maxlag = 12*(nobs/100)^0.25`. For `nobs < 5`, this rounds to 0, and the test may raise a `ValueError` about degrees of freedom.
**Why it happens:** The lag formula assumes a reasonable sample size.
**How to avoid:** Always check `len(series) >= 12` before calling `adfuller`. The 12-point minimum gate protects against this.
**Warning signs:** `ValueError: The number of lags is 0` from statsmodels.

### Pitfall 6: Non-Serializable Values in temporal_signals
**What goes wrong:** Downstream phases (Phase 2 Critic, Phase 4 LLM Analyst context builder) cannot serialize `temporal_signals` to JSON for the Critic dict comparison or LLM context string.
**Why it happens:** `pd.Timestamp`, `np.float64`, `np.int64`, and `pd.NaT` are not JSON-serializable.
**How to avoid:** Convert all values before storing: use `float()`, `int()`, `str(timestamp.date())`, and replace `NaT` / `nan` with `None` explicitly.
**Warning signs:** `TypeError: Object of type Timestamp is not JSON serializable` in Phase 4.

---

## Code Examples

### Full _analyze_column helper (verified patterns)
```python
# Source: statsmodels OLS docs + pandas timeseries docs
def _analyze_column(series: pd.Series) -> Dict[str, Any]:
    """Run all temporal analyses on one numeric column."""
    result: Dict[str, Any] = {}

    # Trend (always run if n >= 3)
    result["trend"] = _compute_trend(series)

    # Period deltas (always run — resample handles sparse data gracefully)
    result["period_deltas"] = _compute_period_deltas(series)

    # Forecast (gated behind n >= 12 + stationarity)
    result["forecast"] = _compute_forecast(series)

    return result
```

### adfuller gate pattern
```python
# Source: https://www.statsmodels.org/stable/examples/notebooks/generated/stationarity_detrending_adf_kpss.html
from statsmodels.tsa.stattools import adfuller

adf_stat, p_value, used_lag, n_obs, critical_values, icbest = adfuller(
    series.values, autolag="AIC"
)
is_stationary = p_value < 0.05  # reject null hypothesis of unit root
```

### ExponentialSmoothing forecast pattern
```python
# Source: statsmodels.tsa.holtwinters documentation
from statsmodels.tsa.holtwinters import ExponentialSmoothing

model = ExponentialSmoothing(
    endog=series.values,
    trend="add",
    seasonal=None,
    initialization_method="estimated",
)
fit = model.fit()
forecast_array = fit.forecast(steps=3)  # returns np.ndarray of length 3
```

### OLS trend slope pattern
```python
# Source: statsmodels.api OLS documentation
import statsmodels.api as sm
import numpy as np

x = sm.add_constant(np.arange(len(series), dtype=float))
results = sm.OLS(series.values.astype(float), x).fit()
slope = results.params[1]       # trend coefficient
p_value = results.pvalues[1]    # significance of slope
r_squared = results.rsquared    # goodness of fit
```

### pandas MoM/YoY delta pattern
```python
# Source: https://pandas.pydata.org/docs/user_guide/timeseries.html
monthly = series.resample("ME").mean()        # pandas 2.x: 'ME' not 'M'
mom_pct = monthly.pct_change()               # month-over-month
yoy_pct = monthly.pct_change(periods=12)     # year-over-year
```

### Date column detection pattern (TEMP-01, >80% parse gate)
```python
# Source: pandas.to_datetime documentation
parsed = pd.to_datetime(df[col], errors="coerce")
non_null_count = df[col].notna().sum()
success_rate = parsed.notna().sum() / non_null_count  # > 0.80 = accept
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `resample('M')` | `resample('ME')` | pandas 2.2 (2024) | Old alias deprecated; raises FutureWarning |
| `resample('Y')` | `resample('YE')` | pandas 2.2 (2024) | Old alias deprecated |
| `ExponentialSmoothing(...).fit().predict(...)` | `.forecast(steps=N)` | statsmodels 0.12 | `forecast()` is the out-of-sample method; `predict()` is in-sample |
| Prophet for short series | statsmodels ExponentialSmoothing | — (architecture decision) | Prophet's C++ backend fails on Windows 11 without build tools |

**Deprecated/outdated:**
- `pd.to_datetime(errors='ignore')`: Deprecated in pandas 2.x — use `errors='coerce'` or `errors='raise'` only.
- `resample('M')`, `resample('Y')`, `resample('Q')`: All deprecated in pandas 2.2+ in favor of `ME`, `YE`, `QE` etc.

---

## Open Questions

1. **Forecast confidence intervals (uncertainty ranges)**
   - What we know: `ExponentialSmoothing.fit().forecast(steps=3)` returns point forecasts only (ndarray, no confidence intervals).
   - What's unclear: TEMP-04 requires "uncertainty ranges." The `simulate(nsimulations=100, anchor='end')` method on `HoltWintersResults` can generate a distribution from which percentile bounds can be computed. This needs to be confirmed working with the installed statsmodels version at implementation time.
   - Recommendation: Plan a task to verify `simulate()` API during Wave 0. If unavailable, use `±1.96 * residual_std` as the uncertainty range approximation (standard practice for exponential smoothing).

2. **Gap detection threshold (2x median interval)**
   - What we know: A 2x threshold for flagging irregular gaps is a pragmatic default with no authoritative source.
   - What's unclear: Whether the project's typical CSVs (sales, financial) warrant a stricter (1.5x) or looser (3x) threshold.
   - Recommendation: Make the threshold a module-level constant `GAP_THRESHOLD_MULTIPLIER = 2.0` so it can be tuned without touching function logic.

3. **YoY delta when data has < 13 months**
   - What we know: `pct_change(periods=12)` produces all `NaN` if fewer than 13 monthly points exist.
   - What's unclear: Whether this should produce an empty dict result or a descriptive note.
   - Recommendation: Check `len(monthly) > 12` before computing YoY; if not met, set `yoy_pct_change` to `{}` with a note `"yoy_note": "Fewer than 13 monthly periods — YoY comparison not available"`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (venv) | All | ✓ | `.venv/Scripts/python` | — |
| pandas | Core data ops | ✓ | 2.3.3 | — |
| numpy | OLS regressor construction | ✓ | 2.4.2 | — |
| pydantic | AgentState schema (later phases) | ✓ | 2.12.5 | — |
| statsmodels | OLS, adfuller, ExponentialSmoothing | ✗ | not installed | None — must install |
| scipy | Mann-Kendall (optional in Phase 1) | ✗ | not installed | Skip Mann-Kendall; OLS p-value sufficient |
| pytest | Test execution | ✗ | not installed | Must install for Wave 0 test infrastructure |

**Missing dependencies with no fallback:**
- `statsmodels` — required for all of TEMP-02, TEMP-04. Must be added to requirements.txt and installed before any temporal_profiler code is written.

**Missing dependencies with fallback:**
- `scipy` — optional for Phase 1. OLS p-value (statsmodels) provides sufficient confidence signal. Add to requirements.txt now per STATE.md standing item, but no Phase 1 code imports it.
- `pytest` — no project tests exist. Wave 0 must create the test directory and install pytest before any test tasks run.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (not yet installed) |
| Config file | `pytest.ini` — none exists; Wave 0 creates it |
| Quick run command | `.venv/Scripts/python -m pytest tests/ -x -q` |
| Full suite command | `.venv/Scripts/python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEMP-01 | `_detect_date_column` returns the date col for a CSV with a parseable date col | unit | `.venv/Scripts/python -m pytest tests/test_temporal_profiler.py::test_detect_date_column -x` | ❌ Wave 0 |
| TEMP-01 | `_detect_date_column` returns `None` when no column exceeds 80% parse rate | unit | `.venv/Scripts/python -m pytest tests/test_temporal_profiler.py::test_detect_date_column_none -x` | ❌ Wave 0 |
| TEMP-02 | `_compute_trend` returns `direction="up"` for monotonically increasing series | unit | `.venv/Scripts/python -m pytest tests/test_temporal_profiler.py::test_trend_up -x` | ❌ Wave 0 |
| TEMP-02 | `_compute_trend` returns `direction="flat"` when slope p-value >= 0.05 | unit | `.venv/Scripts/python -m pytest tests/test_temporal_profiler.py::test_trend_flat -x` | ❌ Wave 0 |
| TEMP-03 | `_compute_period_deltas` returns non-empty `mom_pct_change` for 24-month series | unit | `.venv/Scripts/python -m pytest tests/test_temporal_profiler.py::test_period_deltas -x` | ❌ Wave 0 |
| TEMP-04 | `_compute_forecast` returns `note="Insufficient data for forecast range"` for n=6 | unit | `.venv/Scripts/python -m pytest tests/test_temporal_profiler.py::test_forecast_gate_n -x` | ❌ Wave 0 |
| TEMP-04 | `_compute_forecast` returns `forecast=list[float]` for stationary 24-point series | unit | `.venv/Scripts/python -m pytest tests/test_temporal_profiler.py::test_forecast_stationary -x` | ❌ Wave 0 |
| TEMP-04 | No exception raised when series is non-stationary (adfuller p >= 0.05) | unit | `.venv/Scripts/python -m pytest tests/test_temporal_profiler.py::test_forecast_nonstationary -x` | ❌ Wave 0 |
| TEMP-05 | `profile_temporal` returns status message when df has no date column | integration | `.venv/Scripts/python -m pytest tests/test_temporal_profiler.py::test_no_date_column -x` | ❌ Wave 0 |
| TEMP-06 | `_detect_gaps` returns `irregular=True` when one gap is 3x median | unit | `.venv/Scripts/python -m pytest tests/test_temporal_profiler.py::test_gap_detection -x` | ❌ Wave 0 |
| TEMP-05 (AgentState) | `initialize_state()` includes `temporal_signals` key; existing keys intact | unit | `.venv/Scripts/python -m pytest tests/test_runtime_state.py::test_state_schema -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/Scripts/python -m pytest tests/test_temporal_profiler.py -x -q`
- **Per wave merge:** `.venv/Scripts/python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/__init__.py` — empty file to make tests a package
- [ ] `tests/test_temporal_profiler.py` — unit tests for all helper functions
- [ ] `tests/test_runtime_state.py` — schema regression tests for AgentState
- [ ] `pytest.ini` — minimal config: `[pytest] testpaths = tests`
- [ ] Framework install: `.venv/Scripts/pip install pytest` — no pytest detected in venv

---

## Sources

### Primary (HIGH confidence)
- statsmodels 0.14.6 official docs — `adfuller` signature, return values, p-value interpretation
  - https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.adfuller.html
- statsmodels 0.14.6 official docs — `ExponentialSmoothing` constructor signature
  - https://www.statsmodels.org/stable/generated/statsmodels.tsa.holtwinters.ExponentialSmoothing.html
- statsmodels 0.14.6 official docs — `HoltWintersResults.forecast(steps)` returns ndarray
  - https://www.statsmodels.org/stable/generated/statsmodels.tsa.holtwinters.HoltWintersResults.html
- statsmodels official example — ADF test p-value 0.05 threshold and usage pattern
  - https://www.statsmodels.org/stable/examples/notebooks/generated/stationarity_detrending_adf_kpss.html
- pandas 2.3.3 official docs — resample aliases `ME`/`YE`, `pct_change(periods=N)`, `diff()`
  - https://pandas.pydata.org/docs/user_guide/timeseries.html
- Direct source analysis — `state/runtime_state.py`, `profiling/signal_extractor.py`, `profiling/profiler.py`, `orchestrator/orchestrator.py`, `main.py`
- Prior research documents — `.planning/research/SUMMARY.md`, `ARCHITECTURE.md`, `STACK.md`

### Secondary (MEDIUM confidence)
- WebSearch verification of `HoltWintersResults.forecast(steps=1)` signature — confirmed against statsmodels dev docs
- WebSearch verification of pandas `resample('ME')` deprecation of `'M'` alias in pandas 2.2

### Tertiary (LOW confidence)
- None — all claims verified against official documentation or direct source analysis.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — confirmed installed versions from venv; statsmodels/scipy absence confirmed by pip list
- Architecture patterns: HIGH — derived from direct analysis of v2 source files; all code examples use verified APIs
- Pitfalls: HIGH — all pitfalls are specific to the confirmed pandas 2.3.3 + statsmodels API surface
- Validation architecture: HIGH — no existing test infrastructure to misread; gaps are definitively documented

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (statsmodels and pandas APIs are stable; resample alias change is already in effect)

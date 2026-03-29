# profiling/temporal_profiler.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.stattools import adfuller


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def profile_temporal(
    df: pd.DataFrame,
    metadata: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Extract temporal signals from df using metadata to identify column types.

    Returns:
        If no date column detected:
            {"status": "No date column detected — trend analysis skipped"}
        If date column found:
            {
                "status": "ok",
                "date_column": str,
                "gap_flags": {...},
                "columns": {col_name: signal_dict, ...},
            }
    """
    date_col = _detect_date_column(df)
    if date_col is None:
        return {"status": "No date column detected — trend analysis skipped"}

    date_series = pd.to_datetime(df[date_col], errors="coerce")
    df_work = df.copy()
    df_work["__date__"] = date_series
    df_work = df_work.dropna(subset=["__date__"]).sort_values("__date__")
    df_work = df_work.set_index("__date__")
    df_work.index.name = None  # clean index name

    gap_flags = _detect_gaps(df_work.index)

    numeric_cols = [
        c for c, m in metadata.items()
        if m["type"] == "numeric" and c != date_col and c in df_work.columns
    ]

    column_signals: Dict[str, Any] = {}
    for col in numeric_cols:
        series = df_work[col].dropna()
        column_signals[col] = {
            "trend": _compute_trend(series),
            "period_deltas": _compute_period_deltas(series),
            "forecast": _compute_forecast(series),
        }

    return {
        "status": "ok",
        "date_column": date_col,
        "gap_flags": gap_flags,
        "columns": column_signals,
    }


# ---------------------------------------------------------------------------
# Internal helpers — all prefixed with _
# ---------------------------------------------------------------------------

def _detect_date_column(df: pd.DataFrame) -> Optional[str]:
    """Return the first column that parses as datetime with >80% success rate.

    Numeric columns are skipped to avoid misidentifying Unix timestamp integers.
    """
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        parsed = pd.to_datetime(df[col], errors="coerce")
        non_null = int(df[col].notna().sum())
        if non_null == 0:
            continue
        success_rate = parsed.notna().sum() / non_null
        if success_rate > 0.80:
            return col
    return None


def _compute_trend(series: pd.Series) -> Dict[str, Any]:
    """Compute trend direction and confidence via OLS slope.

    Returns direction in {"up", "down", "flat", "insufficient_data"}.
    Returns confidence in {"HIGH", "MEDIUM", "LOW", None}.
    """
    n = len(series)
    if n < 3:
        return {
            "direction": "insufficient_data",
            "confidence": None,
            "slope": None,
            "p_value": None,
            "r_squared": None,
        }

    x = sm.add_constant(np.arange(n, dtype=float))
    y = series.values.astype(float)
    results = sm.OLS(y, x).fit()

    slope = float(results.params[1])
    p_value = float(results.pvalues[1])
    r_squared = float(results.rsquared)

    if p_value >= 0.05:
        direction = "flat"
    elif slope > 0:
        direction = "up"
    else:
        direction = "down"

    if p_value < 0.01:
        confidence = "HIGH"
    elif p_value < 0.05:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "direction": direction,
        "confidence": confidence,
        "slope": round(slope, 6),
        "p_value": round(p_value, 6),
        "r_squared": round(r_squared, 6),
    }


def _compute_period_deltas(series: pd.Series) -> Dict[str, Any]:
    """Compute MoM and YoY percent change using month-end resampling.

    Uses pandas 2.x aliases: 'ME' for month-end (not deprecated 'M').
    """
    monthly = series.resample("ME").mean()

    mom = monthly.pct_change(fill_method=None)           # month-over-month
    yoy = monthly.pct_change(periods=12, fill_method=None) # year-over-year

    def _to_dict(s: pd.Series) -> Dict[str, float]:
        return {
            str(k.date()): round(float(v), 4)
            for k, v in s.dropna().items()
        }

    return {
        "mom_pct_change": _to_dict(mom),
        "yoy_pct_change": _to_dict(yoy),
        "monthly_points": int(len(monthly)),
    }


def _compute_forecast(series: pd.Series) -> Dict[str, Any]:
    """Gate Holt-Winters forecast behind n >= 12 AND adfuller p < 0.05.

    Returns point forecast for 3 steps ahead, or None with an explanatory note.
    """
    n = len(series)

    if n < 12:
        return {
            "forecast": None,
            "adf_p_value": None,
            "note": "Insufficient data for forecast range",
        }

    try:
        adf_stat, p_value, *_ = adfuller(series.values, autolag="AIC")
    except Exception:
        return {
            "forecast": None,
            "adf_p_value": None,
            "note": "Insufficient data for forecast range",
        }

    if p_value >= 0.05:
        return {
            "forecast": None,
            "adf_p_value": round(float(p_value), 4),
            "note": "Insufficient data for forecast range",
        }

    try:
        model = ExponentialSmoothing(
            series.values,
            trend="add",
            seasonal=None,
            initialization_method="estimated",
        )
        fit = model.fit()
        forecast_values = fit.forecast(steps=3)
    except Exception:
        return {
            "forecast": None,
            "adf_p_value": round(float(p_value), 4),
            "note": "Insufficient data for forecast range",
        }

    return {
        "forecast": [round(float(v), 4) for v in forecast_values],
        "adf_p_value": round(float(p_value), 4),
        "note": None,
    }


def _detect_gaps(index: pd.DatetimeIndex) -> Dict[str, Any]:
    """Flag irregular time-series gaps where any interval exceeds 2x median.

    Returns gap_details as list of dicts with "at" (date string) and
    "interval_days" (int). All values are plain Python types.
    """
    if len(index) < 2:
        return {
            "irregular": False,
            "gap_count": 0,
            "median_interval_days": None,
            "gap_details": [],
        }

    diffs = pd.Series(index).diff().dropna()
    median_interval = diffs.median()
    threshold = median_interval * 2
    large_gaps = diffs[diffs > threshold]

    gap_details: List[Dict[str, Any]] = []
    sorted_index = index.sort_values()
    for iloc_pos in large_gaps.index:
        next_pos = iloc_pos  # diff index aligns to the LATER timestamp
        if next_pos < len(sorted_index):
            gap_details.append({
                "at": str(sorted_index[next_pos].date()),
                "interval_days": int(diffs.loc[iloc_pos].days),
            })

    return {
        "irregular": len(large_gaps) > 0,
        "gap_count": int(len(large_gaps)),
        "median_interval_days": round(float(median_interval.days), 1),
        "gap_details": gap_details,
    }

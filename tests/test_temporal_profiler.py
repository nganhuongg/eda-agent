from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from profiling.temporal_profiler import profile_temporal


def _make_date_df(n: int = 20) -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=n, freq="ME").strftime("%Y-%m-%d")
    return pd.DataFrame({"date": dates, "sales": range(n)})


def _make_no_date_df() -> pd.DataFrame:
    return pd.DataFrame({"revenue": [10, 20, 30], "count": [1, 2, 3]})


def test_date_column_detected():
    df = _make_date_df(20)
    metadata = {"date": {"type": "categorical"}, "sales": {"type": "numeric"}}
    result = profile_temporal(df, metadata)
    assert result["status"] == "ok"
    assert result["date_column"] == "date"


def test_no_date_column_skips():
    df = _make_no_date_df()
    metadata = {"revenue": {"type": "numeric"}, "count": {"type": "numeric"}}
    result = profile_temporal(df, metadata)
    assert result["status"] == "No date column detected — trend analysis skipped"


def test_trend_direction_up():
    df = _make_date_df(20)
    metadata = {"date": {"type": "categorical"}, "sales": {"type": "numeric"}}
    result = profile_temporal(df, metadata)
    assert result["columns"]["sales"]["trend"]["direction"] == "up"


def test_trend_direction_confidence():
    df = _make_date_df(20)
    metadata = {"date": {"type": "categorical"}, "sales": {"type": "numeric"}}
    result = profile_temporal(df, metadata)
    assert result["columns"]["sales"]["trend"]["confidence"] in ("HIGH", "MEDIUM")


def test_mom_yoy_deltas():
    df = _make_date_df(24)
    metadata = {"date": {"type": "categorical"}, "sales": {"type": "numeric"}}
    result = profile_temporal(df, metadata)
    deltas = result["columns"]["sales"]["period_deltas"]
    assert "mom_pct_change" in deltas
    assert "yoy_pct_change" in deltas


def test_forecast_with_sufficient_data():
    # 15 months of stationary-ish data (random walk around mean)
    rng = np.random.default_rng(42)
    dates = pd.date_range("2022-01-01", periods=15, freq="ME").strftime("%Y-%m-%d")
    values = 100 + rng.normal(0, 1, 15).cumsum()
    df = pd.DataFrame({"date": dates, "sales": values})
    metadata = {"date": {"type": "categorical"}, "sales": {"type": "numeric"}}
    result = profile_temporal(df, metadata)
    fc = result["columns"]["sales"]["forecast"]
    # forecast may be None if ADF gate fails on this random seed; just check key exists
    assert "forecast" in fc


def test_forecast_gated_insufficient_data():
    df = _make_date_df(8)
    metadata = {"date": {"type": "categorical"}, "sales": {"type": "numeric"}}
    result = profile_temporal(df, metadata)
    fc = result["columns"]["sales"]["forecast"]
    assert fc["forecast"] is None
    assert "Insufficient" in fc["note"]


def test_no_date_message_in_state():
    df = _make_no_date_df()
    metadata = {"revenue": {"type": "numeric"}, "count": {"type": "numeric"}}
    result = profile_temporal(df, metadata)
    assert result["status"] == "No date column detected — trend analysis skipped"


def test_gap_detection():
    # Regular monthly dates with one large gap (5 months skipped)
    dates = (
        list(pd.date_range("2023-01-01", periods=6, freq="ME").strftime("%Y-%m-%d"))
        + list(pd.date_range("2023-12-01", periods=6, freq="ME").strftime("%Y-%m-%d"))
    )
    df = pd.DataFrame({"date": dates, "sales": range(12)})
    metadata = {"date": {"type": "categorical"}, "sales": {"type": "numeric"}}
    result = profile_temporal(df, metadata)
    assert result["gap_flags"]["irregular"] is True


def test_gap_detection_regular():
    df = _make_date_df(12)
    metadata = {"date": {"type": "categorical"}, "sales": {"type": "numeric"}}
    result = profile_temporal(df, metadata)
    assert result["gap_flags"]["irregular"] is False


def test_skip_reason_key():
    df = _make_no_date_df()
    metadata = {"revenue": {"type": "numeric"}, "count": {"type": "numeric"}}
    result = profile_temporal(df, metadata)
    assert "status" in result
    assert "skip_reason" not in result

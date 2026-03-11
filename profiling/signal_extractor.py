from __future__ import annotations

import math
from typing import Any, Dict

import pandas as pd


def _safe_float(value: Any, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def _numeric_outlier_ratio(series: pd.Series) -> float:
    clean = series.dropna()
    if clean.empty:
        return 0.0

    q1 = clean.quantile(0.25)
    q3 = clean.quantile(0.75)
    iqr = q3 - q1

    if pd.isna(iqr) or iqr == 0:
        return 0.0

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    outlier_count = int(((clean < lower) | (clean > upper)).sum())
    return float(outlier_count / len(clean))


def _categorical_entropy(series: pd.Series) -> float:
    clean = series.dropna()
    if clean.empty:
        return 0.0

    probabilities = clean.value_counts(normalize=True)
    entropy = -sum(float(p) * math.log2(float(p)) for p in probabilities if p > 0)
    return float(entropy)


def extract_signals(
    df: pd.DataFrame,
    dataset_metadata: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    signals: Dict[str, Dict[str, Any]] = {}

    for column, meta in dataset_metadata.items():
        series = df[column]
        missing_ratio = float(series.isna().mean())

        if meta["type"] == "numeric":
            std = _safe_float(series.std(ddof=1))
            signals[column] = {
                "mean": _safe_float(series.mean()),
                "std": std,
                "variance": float(std ** 2),
                "skewness": _safe_float(series.skew()),
                "missing_ratio": missing_ratio,
                "outlier_ratio": _numeric_outlier_ratio(series),
            }
        else:
            clean = series.dropna()
            counts = clean.value_counts(normalize=True) if not clean.empty else pd.Series(dtype=float)
            dominant_ratio = float(counts.iloc[0]) if not counts.empty else 0.0

            signals[column] = {
                "unique_count": int(series.nunique(dropna=True)),
                "dominant_ratio": dominant_ratio,
                "entropy": _categorical_entropy(series),
                "missing_ratio": missing_ratio,
            }

    return signals

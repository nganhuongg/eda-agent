from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def _safe_float(value: Any, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def analyze_distribution(df: pd.DataFrame, column: str, column_type: str) -> Dict[str, Any]:
    series = df[column]

    if column_type == "numeric":
        clean = series.dropna()
        return {
            "count": int(clean.shape[0]),
            "min": _safe_float(clean.min()) if not clean.empty else 0.0,
            "max": _safe_float(clean.max()) if not clean.empty else 0.0,
            "median": _safe_float(clean.median()) if not clean.empty else 0.0,
            "q1": _safe_float(clean.quantile(0.25)) if not clean.empty else 0.0,
            "q3": _safe_float(clean.quantile(0.75)) if not clean.empty else 0.0,
        }

    clean = series.dropna()
    top_values = clean.value_counts().head(5).to_dict()
    return {
        "count": int(clean.shape[0]),
        "top_values": {str(key): int(value) for key, value in top_values.items()},
    }


def detect_outliers(df: pd.DataFrame, column: str) -> Dict[str, Any]:
    series = df[column].dropna()
    if series.empty:
        return {"outlier_count": 0, "outlier_ratio": 0.0, "lower_bound": 0.0, "upper_bound": 0.0}

    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1

    if pd.isna(iqr) or iqr == 0:
        return {"outlier_count": 0, "outlier_ratio": 0.0, "lower_bound": _safe_float(q1), "upper_bound": _safe_float(q3)}

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    mask = (series < lower_bound) | (series > upper_bound)
    outlier_count = int(mask.sum())

    return {
        "outlier_count": outlier_count,
        "outlier_ratio": float(outlier_count / len(series)),
        "lower_bound": _safe_float(lower_bound),
        "upper_bound": _safe_float(upper_bound),
    }


def analyze_missing_pattern(df: pd.DataFrame, column: str) -> Dict[str, Any]:
    missing_mask = df[column].isna()
    missing_count = int(missing_mask.sum())

    if missing_count == 0:
        return {"missing_count": 0, "missing_ratio": 0.0, "co_missing_columns": {}}

    co_missing = {}
    for other_column in df.columns:
        if other_column == column:
            continue
        overlap = int((missing_mask & df[other_column].isna()).sum())
        if overlap > 0:
            co_missing[other_column] = overlap

    ranked = dict(sorted(co_missing.items(), key=lambda item: (-item[1], item[0]))[:5])
    return {
        "missing_count": missing_count,
        "missing_ratio": float(missing_count / len(df)) if len(df) else 0.0,
        "co_missing_columns": ranked,
    }


def analyze_correlation(df: pd.DataFrame, column: str) -> Dict[str, Any]:
    numeric_df = df.select_dtypes(include="number")
    if column not in numeric_df.columns or numeric_df.shape[1] < 2:
        return {"strongest_correlations": {}}

    correlations = numeric_df.corr(numeric_only=True)[column].drop(labels=[column]).dropna()
    ranked = correlations.abs().sort_values(ascending=False).head(5).index.tolist()
    strongest = {other: float(correlations[other]) for other in ranked}
    return {"strongest_correlations": strongest}

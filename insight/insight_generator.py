from __future__ import annotations

from typing import Any, Dict, List


def _numeric_insight(column: str, signals: Dict[str, Any], analysis_results: Dict[str, Any]) -> Dict[str, Any]:
    missing_ratio = float(signals.get("missing_ratio", 0.0))
    skewness = float(signals.get("skewness", 0.0))
    variance = float(signals.get("variance", 0.0))
    outlier_ratio = float(signals.get("outlier_ratio", 0.0))

    if missing_ratio >= 0.2:
        missing_level = "high_missing"
    elif missing_ratio >= 0.05:
        missing_level = "moderate_missing"
    else:
        missing_level = "low_missing"

    if abs(skewness) >= 1.0:
        skew_category = "high_skew"
    elif abs(skewness) >= 0.5:
        skew_category = "moderate_skew"
    else:
        skew_category = "low_skew"

    if variance >= 1000:
        variance_level = "high_variance"
    elif variance >= 10:
        variance_level = "moderate_variance"
    else:
        variance_level = "low_variance"

    if outlier_ratio >= 0.1:
        outlier_flag = "high_outlier_risk"
    elif outlier_ratio > 0:
        outlier_flag = "some_outliers"
    else:
        outlier_flag = "no_outliers"

    visualizations: List[str] = []
    anomaly_findings: List[str] = []

    if skew_category != "low_skew":
        visualizations.append("distribution")
    if outlier_flag != "no_outliers":
        visualizations.append("boxplot")
        anomaly_findings.append(f"{column} shows {outlier_flag}.")
    if missing_level != "low_missing":
        visualizations.append("missingness")
        anomaly_findings.append(f"{column} has {missing_level}.")

    correlations = analysis_results.get("analyze_correlation", {}).get("strongest_correlations", {})
    strong_correlations = {
        other: value for other, value in correlations.items() if abs(float(value)) >= 0.7
    }
    if strong_correlations:
        visualizations.append("correlation")
        anomaly_findings.append(f"{column} has strong linear relationships with peer features.")

    return {
        "column_kind": "numeric",
        "missing_level": missing_level,
        "skew_category": skew_category,
        "variance_level": variance_level,
        "outlier_flag": outlier_flag,
        "anomaly_findings": anomaly_findings,
        "recommended_visualizations": sorted(set(visualizations)),
    }


def _categorical_insight(column: str, signals: Dict[str, Any]) -> Dict[str, Any]:
    missing_ratio = float(signals.get("missing_ratio", 0.0))
    dominant_ratio = float(signals.get("dominant_ratio", 0.0))
    unique_count = int(signals.get("unique_count", 0))
    entropy = float(signals.get("entropy", 0.0))

    if missing_ratio >= 0.2:
        missing_level = "high_missing"
    elif missing_ratio >= 0.05:
        missing_level = "moderate_missing"
    else:
        missing_level = "low_missing"

    if dominant_ratio >= 0.8:
        balance_level = "high_imbalance"
    elif dominant_ratio >= 0.6:
        balance_level = "moderate_imbalance"
    else:
        balance_level = "balanced"

    if unique_count >= 50:
        cardinality_level = "very_high_cardinality"
    elif unique_count >= 20:
        cardinality_level = "high_cardinality"
    elif unique_count >= 6:
        cardinality_level = "medium_cardinality"
    else:
        cardinality_level = "low_cardinality"

    if entropy <= 1.0 and unique_count > 1:
        entropy_level = "low_entropy"
    elif entropy >= 3.0:
        entropy_level = "high_entropy"
    else:
        entropy_level = "moderate_entropy"

    anomaly_findings: List[str] = []
    visualizations: List[str] = []

    if balance_level != "balanced":
        visualizations.append("category_distribution")
        anomaly_findings.append(f"{column} is {balance_level}.")
    if missing_level != "low_missing":
        visualizations.append("missingness")
        anomaly_findings.append(f"{column} has {missing_level}.")

    return {
        "column_kind": "categorical",
        "missing_level": missing_level,
        "balance_level": balance_level,
        "cardinality_level": cardinality_level,
        "entropy_level": entropy_level,
        "anomaly_findings": anomaly_findings,
        "recommended_visualizations": sorted(set(visualizations)),
    }


def generate_insight_for_column(
    column: str,
    column_type: str,
    signals: Dict[str, Any],
    analysis_results: Dict[str, Any],
) -> Dict[str, Any]:
    if column_type == "numeric":
        return _numeric_insight(column, signals, analysis_results)
    return _categorical_insight(column, signals)

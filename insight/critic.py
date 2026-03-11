from __future__ import annotations

from typing import Any, Dict, List


def suggest_investigations(
    column: str,
    column_type: str,
    signals: Dict[str, Any],
    insight: Dict[str, Any],
    analysis_results: Dict[str, Any],
) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    completed_actions = set(analysis_results.keys())

    if column_type == "numeric":
        if abs(float(signals.get("skewness", 0.0))) >= 0.75 and "detect_outliers" not in completed_actions:
            suggestions.append(
                {
                    "column": column,
                    "action": "detect_outliers",
                    "priority": 0.95,
                    "reason": "High skewness can hide tail anomalies",
                    "source": "critic",
                }
            )

        if float(signals.get("missing_ratio", 0.0)) >= 0.05 and "analyze_missing_pattern" not in completed_actions:
            suggestions.append(
                {
                    "column": column,
                    "action": "analyze_missing_pattern",
                    "priority": 0.9,
                    "reason": "Non-trivial missingness requires structure checks",
                    "source": "critic",
                }
            )

        if "analyze_correlation" not in completed_actions:
            if insight.get("variance_level") != "low_variance" or insight.get("outlier_flag") != "no_outliers":
                suggestions.append(
                    {
                        "column": column,
                        "action": "analyze_correlation",
                        "priority": 0.8,
                        "reason": "High-variance or anomalous numeric features should be checked for dependencies",
                        "source": "critic",
                    }
                )
    else:
        if float(signals.get("missing_ratio", 0.0)) >= 0.05 and "analyze_missing_pattern" not in completed_actions:
            suggestions.append(
                {
                    "column": column,
                    "action": "analyze_missing_pattern",
                    "priority": 0.85,
                    "reason": "Categorical missingness may reflect process issues",
                    "source": "critic",
                }
            )

    return suggestions

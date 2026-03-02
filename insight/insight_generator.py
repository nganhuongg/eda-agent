# insight/insight_generator.py

from typing import Dict, Any


def generate_insights(state: Dict[str, Any]) -> None:
    """
    Deterministically convert execution_results
    into structured categorical insights.
    Stores results in state["insights"].
    """

    insights = {}

    for column, stats in state["execution_results"].items():

        col_type = state["dataset_metadata"][column]["type"]

        if col_type == "numeric":

            mean = stats.get("mean", 0)
            std = stats.get("std", 0)
            skewness = stats.get("skewness", 0)
            missing_ratio = stats.get("missing_ratio", 0)

            # ---- variance_level ----
            if abs(mean) > 1e-8:
                ratio = std / abs(mean)
            else:
                ratio = std

            if ratio < 0.1:
                variance_level = "low"
            elif ratio < 0.5:
                variance_level = "moderate"
            else:
                variance_level = "high"

            # ---- skewness_direction ----
            if skewness > 0.5:
                skewness_direction = "right"
            elif skewness < -0.5:
                skewness_direction = "left"
            else:
                skewness_direction = "symmetric"

            # ---- data_quality_flag ----
            if missing_ratio < 0.05:
                data_quality_flag = "clean"
            elif missing_ratio < 0.2:
                data_quality_flag = "moderate_missing"
            else:
                data_quality_flag = "high_missing"

            insights[column] = {
                "variance_level": variance_level,
                "skewness_direction": skewness_direction,
                "data_quality_flag": data_quality_flag
            }

        else:  # categorical

            dominant_ratio = stats.get("dominant_ratio", 0)
            unique_count = stats.get("unique_count", 0)

            # ---- balance_level ----
            if dominant_ratio > 0.8:
                balance_level = "high_imbalance"
            elif dominant_ratio > 0.6:
                balance_level = "moderate_imbalance"
            else:
                balance_level = "balanced"

            # ---- cardinality_level ----
            if unique_count <= 5:
                cardinality_level = "low"
            elif unique_count <= 20:
                cardinality_level = "medium"
            else:
                cardinality_level = "high"

            insights[column] = {
                "balance_level": balance_level,
                "cardinality_level": cardinality_level
            }

    state["insights"] = insights
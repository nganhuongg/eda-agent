# execution/stat_executor.py

from typing import Set, Dict, Any
import pandas as pd

def stat_executor(state: Dict[str, Any], accepted_columns: Set[str], df: pd.DataFrame) -> bool:
    """
    Executes statistical analysis for accepted columns.
    Stores results in state["execution_results"].
    """

    for column in accepted_columns:

        column_type = state["dataset_metadata"][column]["type"]

        # Ensure dict exists
        if column not in state["execution_results"]:
            state["execution_results"][column] = {}

        series = df[column]

        if column_type == "numeric":

            result = {
                "mean": float(series.mean()),
                "std": float(series.std()),
                "missing_ratio": float(series.isna().mean()),
                "skewness": float(series.skew())
            }

        else:  # categorical
            non_missing = series.dropna()
            total_non_missing = len(non_missing)

            if total_non_missing > 0:
                counts = non_missing.value_counts(normalize=True)
                dominant_ratio = float(counts.iloc[0])
            else:
                dominant_ratio = 0.0

            result = {
                "unique_count": int(series.nunique(dropna=True)),
                "dominant_ratio": dominant_ratio,
                "missing_ratio": float(series.isna().mean())
            }

        state["execution_results"][column] = result

    return True
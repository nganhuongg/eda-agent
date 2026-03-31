from __future__ import annotations

import os
from typing import Any, Dict

import matplotlib
import pandas as pd
import seaborn as sns

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def ensure_output_dir() -> None:
    os.makedirs("outputs/plots", exist_ok=True)


def plot_missing_heatmap(df: pd.DataFrame) -> str:
    ensure_output_dir()
    plt.figure(figsize=(12, 6))
    sns.heatmap(df.isnull(), cbar=False)
    plt.title("Missing Value Heatmap")

    path = "outputs/plots/missing_heatmap.png"
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    return path


def plot_numeric_distribution(df: pd.DataFrame, column: str) -> str:
    ensure_output_dir()
    plt.figure(figsize=(8, 5))
    sns.histplot(df[column].dropna(), kde=True)
    plt.title(f"Distribution of {column}")

    path = f"outputs/plots/{column}_distribution.png"
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    return path


def plot_boxplot(df: pd.DataFrame, column: str) -> str:
    ensure_output_dir()
    plt.figure(figsize=(8, 5))
    sns.boxplot(x=df[column].dropna())
    plt.title(f"Outlier Check for {column}")

    path = f"outputs/plots/{column}_boxplot.png"
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    return path


def plot_categorical_distribution(df: pd.DataFrame, column: str) -> str:
    ensure_output_dir()
    plt.figure(figsize=(8, 5))
    df[column].value_counts(dropna=False).head(10).plot(kind="bar")
    plt.title(f"Category Distribution of {column}")

    path = f"outputs/plots/{column}_category_distribution.png"
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    return path


def plot_correlation_heatmap(df: pd.DataFrame, focus_column: str) -> str | None:
    numeric_df = df.select_dtypes(include="number")
    if focus_column not in numeric_df.columns or numeric_df.shape[1] < 2:
        return None

    ensure_output_dir()
    correlations = numeric_df.corr(numeric_only=True)
    ranked = correlations[focus_column].abs().sort_values(ascending=False).head(6).index.tolist()
    subset = correlations.loc[ranked, ranked]

    plt.figure(figsize=(8, 6))
    sns.heatmap(subset, annot=True, cmap="coolwarm", center=0)
    plt.title(f"Correlation Heatmap around {focus_column}")

    path = f"outputs/plots/{focus_column}_correlation_heatmap.png"
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    return path


# Signal thresholds that trigger each plot type.
# These are named constants so they are easy to find and tune.
MISSING_RATIO_THRESHOLD = 0.05   # any column above this → whole-dataset heatmap (once)
SKEWNESS_THRESHOLD = 1.0         # absolute skewness above this → distribution plot
DOMINANT_RATIO_THRESHOLD = 0.5   # categorical column → bar plot
OUTLIER_RATIO_THRESHOLD = 0.10   # numeric column → boxplot


def generate_insight_driven_plots(state: Dict[str, Any], df: pd.DataFrame) -> Dict[str, str]:
    """Generate plots driven entirely by computed signal values.

    Replaces the old recommended_visualizations approach, which never worked
    because the orchestrator's insights bridge never populated that key.
    Each threshold above controls when a plot is triggered.
    """
    plot_paths: Dict[str, str] = {}
    missing_heatmap_created = False

    for column, signals in state.get("signals", {}).items():
        column_type = state["dataset_metadata"].get(column, {}).get("type", "unknown")

        # Missing heatmap — one per dataset, triggered by the first column that
        # crosses the threshold. Shows the whole-dataset missing-value pattern.
        if not missing_heatmap_created and signals.get("missing_ratio", 0) > MISSING_RATIO_THRESHOLD:
            plot_paths["missing_heatmap"] = plot_missing_heatmap(df)
            missing_heatmap_created = True

        if column_type == "numeric":
            if abs(signals.get("skewness", 0)) > SKEWNESS_THRESHOLD:
                plot_paths[f"{column}_distribution"] = plot_numeric_distribution(df, column)
            if signals.get("outlier_ratio", 0) > OUTLIER_RATIO_THRESHOLD:
                plot_paths[f"{column}_boxplot"] = plot_boxplot(df, column)

        elif column_type == "categorical":
            if signals.get("dominant_ratio", 0) > DOMINANT_RATIO_THRESHOLD:
                plot_paths[f"{column}_category_distribution"] = plot_categorical_distribution(df, column)

    return plot_paths

# visualization/plot_generator.py

import os
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from typing import Dict, Any


def ensure_output_dir():
    os.makedirs("outputs/plots", exist_ok=True)


def plot_missing_heatmap(df: pd.DataFrame) -> str:
    ensure_output_dir()

    plt.figure(figsize=(12, 6))
    sns.heatmap(df.isnull(), cbar=False)
    plt.title("Missing Value Heatmap")

    path = "outputs/plots/missing_heatmap.png"
    plt.savefig(path)
    plt.close()

    return path


def plot_numeric_distribution(df: pd.DataFrame, column: str) -> str:
    ensure_output_dir()

    plt.figure(figsize=(8, 5))
    sns.histplot(df[column].dropna(), kde=True)
    plt.title(f"Distribution of {column}")

    path = f"outputs/plots/{column}_distribution.png"
    plt.savefig(path)
    plt.close()

    return path


def plot_categorical_distribution(df: pd.DataFrame, column: str) -> str:
    ensure_output_dir()

    plt.figure(figsize=(8, 5))
    df[column].value_counts().plot(kind="bar")
    plt.title(f"Category Distribution of {column}")

    path = f"outputs/plots/{column}_distribution.png"
    plt.savefig(path)
    plt.close()

    return path

def generate_all_plots(state: Dict[str, Any], df: pd.DataFrame) -> Dict[str, str]:
    """
    Generate all plots and return mapping of plot names to file paths.
    """

    plot_paths = {}

    plot_paths["missing_heatmap"] = plot_missing_heatmap(df)

    for column, meta in state["dataset_metadata"].items():

        if meta["type"] == "numeric":
            path = plot_numeric_distribution(df, column)
        else:
            path = plot_categorical_distribution(df, column)

        plot_paths[column] = path

    return plot_paths
# profiling/profiler.py

from __future__ import annotations

from typing import Any, Dict, Tuple

import pandas as pd


def profile_dataset(file_path: str) -> Tuple[pd.DataFrame, Dict[str, Dict[str, Any]], int]:
    df = pd.read_csv(file_path)

    metadata: Dict[str, Dict[str, Any]] = {}
    row_count = int(len(df))

    for column in df.columns:
        series = df[column]

        if pd.api.types.is_bool_dtype(series):
            column_type = "categorical"
        elif pd.api.types.is_numeric_dtype(series):
            column_type = "numeric"
        else:
            column_type = "categorical"

        metadata[column] = {
            "type": column_type,
            "dtype": str(series.dtype),
            "non_null_count": int(series.notna().sum()),
            "row_count": row_count,
        }

    return df, metadata, len(df.columns)

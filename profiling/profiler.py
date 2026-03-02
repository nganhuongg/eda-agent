# profiling/profiler.py

import pandas as pd
from typing import Tuple, Dict, Any

def profile_dataset(file_path: str) -> Tuple[pd.DataFrame, Dict[str, Any], int]:
    """
    Load dataset and extract:
    - DataFrame
    - Column metadata (type only)
    - Total column count
    """

    df = pd.read_csv(file_path)

    metadata = {}

    for column in df.columns:
        if pd.api.types.is_numeric_dtype(df[column]):
            col_type = "numeric"
        else:
            col_type = "categorical"

        metadata[column] = {
            "type": col_type
        }

    total_columns = len(df.columns)

    return df, metadata, total_columns
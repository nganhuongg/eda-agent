# planning/dummy_planner.py

import random
from typing import Set, Dict, Any

def dummy_planner(state: Dict[str, Any]) -> Set[str]:
    """
    Randomly selects 1 or 2 columns from ALL columns.
    Purpose: stress-test controller logic.
    """

    all_columns = list(state["dataset_metadata"].keys())

    # Randomly choose 1 or 2 columns
    k = random.randint(1, min(2, len(all_columns)))
    selected = random.sample(all_columns, k)

    return set(selected)
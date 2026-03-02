# planning/coverage_planner.py

import random
from typing import Set, Dict, Any

def coverage_planner(state: Dict[str, Any]) -> Set[str]:
    """
    Coverage-biased probabilistic planner.

    - If unseen columns exist:
        80% choose from unseen
        20% choose random from all columns (to stress-test controller)
    - Select 1 or 2 columns randomly
    """

    all_columns = list(state["dataset_metadata"].keys())
    analyzed = state["columns_analyzed"]

    unseen = list(set(all_columns) - analyzed)

    # Choose number of columns to propose
    k = random.randint(1, min(2, len(all_columns)))

    if unseen and random.random() < 0.8:
        # Prefer unseen
        k = min(k, len(unseen))
        selected = random.sample(unseen, k)
    else:
        # Random fallback
        selected = random.sample(all_columns, k)

    return set(selected)
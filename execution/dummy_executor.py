# execution/dummy_executor.py

import random
from typing import Set, Dict, Any

def dummy_executor(state: Dict[str, Any], accepted_columns: Set[str], df) -> bool:
    """
    Simulates execution.
    Randomly succeeds or fails to test retry logic.
    """

    print(f"Executing columns: {accepted_columns}")

    # 80% chance success, 20% chance failure
    success = random.random() < 0.8

    if success:
        print("Execution success.")
        return True
    else:
        print("Execution failed.")
        return False
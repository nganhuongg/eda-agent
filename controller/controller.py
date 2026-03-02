# controller/controller.py

from typing import Set, Dict, Any, Tuple

def controller_step(
    state: Dict[str, Any],
    proposed_columns: Set[str],
    config: Dict[str, Any]
) -> Tuple[str, Set[str]]:

    columns_analyzed = state["columns_analyzed"]
    max_retry = config["MAX_RETRY"]

    new_columns = proposed_columns - columns_analyzed

    if len(new_columns) == 0:
        state["retry_count"] += 1
        state["last_rejection_reason"] = "NO_NEW_COLUMNS"

        if state["retry_count"] >= max_retry:
            return "STOP_FAILURE", set()

        return "REPLAN", set()

    state["last_rejection_reason"] = None
    return "CONTINUE", new_columns

"""Overall, the controller prevent AI Agent to infinitely retry to find 
the best answer. Without controller, planner may propose the same column
repeatedly and coverage never increases --> system can run forever. Without 
any guaranteed termination, even planner eventually covers all columns, the
system will still continue running"""

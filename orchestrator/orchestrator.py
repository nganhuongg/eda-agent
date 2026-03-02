# orchestrator/orchestrator.py

from controller.controller import controller_step

def run_agent(state, planner, executor, config, df):

    status = None
    reason = None

    while True:

        proposed_columns = planner(state)

        decision, accepted_columns = controller_step(
            state, proposed_columns, config
        )

        if decision == "STOP_FAILURE":
            status = "FAILURE"
            reason = "MAX_RETRY_EXCEEDED"
            break

        if decision == "REPLAN":
            continue

        if decision == "CONTINUE":

            success = executor(state, accepted_columns, df)

            if not success:
                state["retry_count"] += 1

                if state["retry_count"] >= config["MAX_RETRY"]:
                    status = "FAILURE"
                    reason = "MAX_RETRY_EXCEEDED"
                    break

                continue

            # Transactional commit
            state["columns_analyzed"].update(accepted_columns)

            # Success termination
            if len(state["columns_analyzed"]) == state["total_columns"]:
                status = "SUCCESS"
                reason = "COVERAGE_COMPLETE"
                break

    # ---- After loop ----

    coverage_ratio = (
        len(state["columns_analyzed"]) / state["total_columns"]
        if state["total_columns"] > 0 else 0
    )

    result = {
        "status": status,
        "reason": reason,
        "coverage_ratio": coverage_ratio,
        "columns_analyzed": len(state["columns_analyzed"]),
        "total_columns": state["total_columns"]
    }

    return result
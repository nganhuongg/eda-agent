def generate_global_summary(state):

    total_columns = state["total_columns"]
    analyzed = len(state["columns_analyzed"])

    numeric_cols = [
        col for col, meta in state["dataset_metadata"].items()
        if meta["type"] == "numeric"
    ]

    categorical_cols = [
        col for col, meta in state["dataset_metadata"].items()
        if meta["type"] == "categorical"
    ]

    return {
        "coverage_ratio": analyzed / total_columns,
        "numeric_columns": len(numeric_cols),
        "categorical_columns": len(categorical_cols)
    }
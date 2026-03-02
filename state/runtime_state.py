from typing import TypedDict, List, Dict, Any

class AgentState(TypedDict):
    # Dataset understand (record data types in each feature and description of these features)
    dataset_metadata: Dict[str, Any]


    total_columns: int
    columns_analyzed: set[str]
    last_rejection_reason: List[str]

    # Planning
    current_plan: Dict[str, Any] # know what to do next
    plan_history: List[Dict[str, Any]] # record previous plan for retry

    # Execution
    execution_results: Dict[str, Any] # for insight layer

    # Insight
    insights: Dict[str, Any] # for critic

    # Evaluation
    evaluation: Dict[str, Any] # for controller to decide retry or not

    # Governance
    retry_count: int 

    # Observability
    logs: List[Dict[str, Any]] # recording the whole process
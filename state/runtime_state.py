from __future__ import annotations

from typing import Any, Dict, List, Set, TypedDict


class InvestigationAction(TypedDict, total=False):
    column: str
    action: str
    priority: float
    reason: str
    source: str


class ActionRecord(TypedDict, total=False):
    step: int
    phase: str
    column: str
    action: str
    source: str
    reason: str
    priority: float
    status: str
    details: Dict[str, Any]


class AgentState(TypedDict):
    dataset_metadata: Dict[str, Dict[str, Any]]
    signals: Dict[str, Dict[str, Any]]
    temporal_signals: Dict[str, Any]
    risk_scores: Dict[str, float]
    analysis_results: Dict[str, Dict[str, Any]]
    insights: Dict[str, Dict[str, Any]]
    analyst_decisions: Dict[str, Any]  # AnalystDecision objects keyed by column (D-03)
    investigation_queue: List[InvestigationAction]
    analyzed_columns: Set[str]
    action_history: List[ActionRecord]
    total_columns: int
    visualizations: Dict[str, str]


def initialize_state() -> AgentState:
    return {
        "dataset_metadata": {},
        "signals": {},
        "temporal_signals": {},
        "risk_scores": {},
        "analysis_results": {},
        "insights": {},
        "analyst_decisions": {},
        "investigation_queue": [],
        "analyzed_columns": set(),
        "action_history": [],
        "total_columns": 0,
        "visualizations": {},
    }

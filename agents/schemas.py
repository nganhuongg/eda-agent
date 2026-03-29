from __future__ import annotations

from typing import List

from pydantic import BaseModel


class CriticVerdict(BaseModel):
    """Structured result returned by the Critic agent for a single finding.

    approved: True only when every claim in the finding matched a signal value
              within tolerance (rel_tol=0.01, abs_tol=0.001).
    rejected_claims: List of field names that failed validation. Empty when approved=True.
                     This list is threaded forward to the Analyst in the next Ralph Loop
                     iteration (CRIT-05).
    """

    approved: bool
    rejected_claims: List[str]

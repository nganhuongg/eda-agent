from __future__ import annotations

import math
from typing import Any, Dict, List

from agents.schemas import CriticVerdict


def validate_finding(
    finding: Dict[str, Any],
    signals: Dict[str, Any],
    analysis_results: Dict[str, Any],
) -> CriticVerdict:
    """Validate a structured LLM finding dict against deterministic signal values.

    Each claim in finding["claims"] is validated by looking up its field name in
    signals[column] first, then analysis_results[column]. Numeric comparison uses
    math.isclose(rel_tol=0.01, abs_tol=0.001).

    Returns a CriticVerdict where:
    - approved=True only when all claims pass (or claims list is empty)
    - rejected_claims lists field names that failed (absent key or value out of tolerance)

    Flat key lookup only — nested analysis_results values are not searched recursively.
    Non-numeric signal values (None, non-castable) are treated as unavailable and
    the corresponding claim is rejected.

    Does not mutate the finding dict. Makes zero network or API calls.
    """
    column: str = finding["column"]
    claims: List[Dict[str, Any]] = finding.get("claims", [])

    col_signals = signals.get(column, {})
    col_results = analysis_results.get(column, {})

    rejected: List[str] = []

    for claim in claims:
        field: str = claim["field"]

        # Two-source lookup: signals first, then analysis_results
        if field in col_signals:
            raw_truth = col_signals[field]
        elif field in col_results:
            raw_truth = col_results[field]
        else:
            rejected.append(field)
            continue

        try:
            claimed_value = float(claim["value"])
            ground_truth = float(raw_truth)
        except (TypeError, ValueError):
            # Signal or claim value is None or non-numeric — reject
            rejected.append(field)
            continue

        if not math.isclose(claimed_value, ground_truth, rel_tol=0.01, abs_tol=0.001):
            rejected.append(field)

    return CriticVerdict(
        approved=len(rejected) == 0,
        rejected_claims=rejected,
    )

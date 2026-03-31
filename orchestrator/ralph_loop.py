from __future__ import annotations

from typing import Any, Callable, List

from insight.critic import CriticVerdict


def run_loop(
    generator_fn: Callable[[List[str]], Any],
    critic_fn: Callable[[Any], CriticVerdict],
    max_iter: int = 5,
) -> Any:
    """Iterative refinement loop. Always exits within max_iter. Never raises.

    LOOP-01: exits immediately when critic_fn returns approved=True.
    LOOP-02: passes rejected_claims from prior CriticVerdict to next generator_fn call.
             On iteration 0, passes an empty list.
    LOOP-03: returns last_result after range(max_iter) exhaustion without raising.

    D-01: caller supplies critic_fn — run_loop is generic (Gate 1 and Gate 2 both use it).
    D-02: generator_fn(rejected_claims: List[str]) -> Any; empty list on iter 0.
    D-03: only the most-recent rejected_claims list is forwarded (replace, not extend).
    D-04: last iteration's result is returned on exhaustion (most-informed attempt).

    NEVER use while loop. NEVER wrap generator_fn in try/except.
    NEVER import validate_finding or orchestrator.orchestrator here.
    """
    rejected_claims: List[str] = []
    last_result: Any = None

    for _i in range(max_iter):
        last_result = generator_fn(rejected_claims)
        verdict: CriticVerdict = critic_fn(last_result)
        if verdict.approved:
            return last_result
        rejected_claims = verdict.rejected_claims

    return last_result


def quality_bar_critic(result: Any) -> CriticVerdict:
    """Gate 2 critic. Three deterministic quality checks. No API calls.

    LOOP-04: intended as the critic_fn argument to run_loop() for Gate 2 (output review).
    LOOP-05: implements D-06 three checks:
      Check 1: all findings have business_label (non-empty string)
      Check 2: all numeric claims have a source in signals or analysis_results for that column
      Check 3: findings are in descending order by score (or priority) field

    Assumed result dict shape (documented here; Phase 6 may adapt):
      result = {
        "findings": [{"business_label": str, "score": float, "column": str, "claims": [...]}],
        "signals": {col: {field: value}},
        "analysis_results": {col: {field: value}},
      }

    Phase 3 tests against minimal synthetic dicts. Phase 6 will update if field names drift.
    """
    rejected: List[str] = []

    findings = result.get("findings", []) if isinstance(result, dict) else []
    signals = result.get("signals", {}) if isinstance(result, dict) else {}
    analysis_results = result.get("analysis_results", {}) if isinstance(result, dict) else {}

    # Check 1 (D-06, LOOP-05): All findings have business_label (non-empty)
    for i, f in enumerate(findings):
        if not f.get("business_label"):
            rejected.append(f"findings[{i}].business_label")

    # Check 2 (D-06, LOOP-05): No unsupported numeric claims
    # Claim is supported if its field exists in signals[column] or analysis_results[column]
    for i, f in enumerate(findings):
        col = f.get("column", "")
        col_signals = signals.get(col, {})
        col_analysis = analysis_results.get(col, {})
        for claim in f.get("claims", []):
            field = claim.get("field", "")
            if field and field not in col_signals and field not in col_analysis:
                rejected.append(f"findings[{i}].claims.{field}")

    # Check 3 (D-06, LOOP-05): Findings in ranked/sorted order (descending by score or priority)
    scores = [f.get("score", f.get("priority", None)) for f in findings]
    numeric_scores = [s for s in scores if s is not None]
    if len(numeric_scores) > 1 and numeric_scores != sorted(numeric_scores, reverse=True):
        rejected.append("findings_order")

    return CriticVerdict(approved=len(rejected) == 0, rejected_claims=rejected)

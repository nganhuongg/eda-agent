from __future__ import annotations

from typing import Any, Callable, List

from agents.schemas import CriticVerdict


def run_loop(
    generator_fn: Callable[[List[str]], Any],
    critic_fn: Callable[[Any], CriticVerdict],
    max_iter: int = 5,
) -> Any:
    """Iterative refinement loop. Always exits within max_iter. Never raises.

    LOOP-01: exits immediately when critic returns approved=True.
    LOOP-02: passes rejected_claims from prior verdict to next generator call.
    LOOP-03: returns last result after max_iter exhaustion without raising.
    """
    raise NotImplementedError("run_loop not yet implemented — Wave 1 task")


def quality_bar_critic(result: Any) -> CriticVerdict:
    """Gate 2 critic. Three deterministic quality checks. No API calls.

    LOOP-04: used as critic_fn argument to run_loop() for Gate 2.
    LOOP-05: checks business_label presence, numeric claim grounding, ranked order.
    """
    raise NotImplementedError("quality_bar_critic not yet implemented — Wave 1 task")

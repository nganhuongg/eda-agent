---
phase: 04-llm-analyst
plan: "02"
subsystem: agents
tags: [tdd, llm, minimax, tenacity, fallback, pydantic]
dependency_graph:
  requires: [04-01]
  provides: [agents/llm_analyst.py:analyze_column, agents/llm_analyst.py:_deterministic_fallback, agents/llm_analyst.py:_call_minimax]
  affects: [agents/llm_analyst.py, tests/test_llm_analyst.py]
tech_stack:
  added: []
  patterns: [tenacity-retry-ratelimit-only, deterministic-fallback-claims-empty, lazy-import-insight-generator, RetryError-catch-analyze-column]
key_files:
  created: []
  modified:
    - agents/llm_analyst.py
    - tests/test_llm_analyst.py
decisions:
  - "Catch tenacity.RetryError in analyze_column — reraise=False does not return None when all attempts raise; it raises RetryError which must be caught explicitly"
  - "_infer_label_from_signals is a private helper above _deterministic_fallback — not exported, keeps label inference collocated with fallback logic"
  - "Lazy import of generate_insight_for_column inside _deterministic_fallback body — avoids circular import risk, mirrors test_ralph_loop.py pattern"
  - "claims=[] always in fallback — prevents Critic rejections from ungrounded claims (Pitfall 4 guard)"
metrics:
  duration: "12min"
  completed_date: "2026-03-29"
  tasks: 2
  files: 2
---

# Phase 4 Plan 2: LLM Analyst Full Implementation Summary

**One-liner:** MiniMax API call path with tenacity 3-retry (RateLimitError only), deterministic fallback wrapping generate_insight_for_column, and all 12 test stubs converted to GREEN behavioral assertions.

## What Was Built

**Task 1 — Implement four stub functions in agents/llm_analyst.py:**

- `_build_messages(context, rejected_claims)`: Builds `[system, user]` message list. User content serializes column name, type, risk score, analyzed columns, and signal scalars. Appends rejected claims section if non-empty.
- `_call_minimax(client, messages)`: Calls `client.chat.completions.create(model="MiniMax-M2.7", ...)` with `response_format={"type": "json_object"}`, returns `response.choices[0].message.content`. Tenacity `@retry` decorator (already present from Plan 04-01) handles 3-attempt retry on `openai.RateLimitError` with `reraise=False`.
- `_infer_label_from_signals(signals)`: Private helper mapping signal thresholds to `business_label`. Outlier/missing > 10% → "risk"; skewness > 1.5 → "opportunity"; variance > 500 → "anomaly"; else → "trend".
- `_deterministic_fallback(state, column)`: Lazy-imports `generate_insight_for_column`, extracts column_type/signals/analysis_results from state, returns `AnalystDecision` with `claims=[]` always.
- `analyze_column(state, column, rejected_claims=None)`: Full flow — client None check → fallback; build context and messages; call `_call_minimax`; catch `openai.APIError` and `tenacity.RetryError` → fallback; parse JSON → catch `ValidationError`/`ValueError` → fallback.

**Task 2 — Convert 9 RED stubs in tests/test_llm_analyst.py to GREEN:**

- ANLST-01 through ANLST-05: All use no-API-key fallback mode via `monkeypatch.delenv("MINIMAX_API_KEY")`. Assert on `isinstance(result, AnalystDecision)`, non-empty fields, valid business_label.
- D-04: Patches `agents.llm_analyst._call_minimax` to return malformed JSON `'{"invalid": true}'` — verifies fallback triggers and `claims == []`.
- D-06: No API key → direct fallback → `column == "revenue"` and `claims == []`.
- D-07: Same as D-06, additionally asserts non-empty `hypothesis` and valid `business_label`.
- D-08: Patches `agents.llm_analyst.OpenAI` so `instance.chat.completions.create` raises `RateLimitError` every call. Asserts `call_count["n"] == 3` (tenacity retried 3 times) then fallback returns valid `AnalystDecision` with `claims == []`.

## Test Results

| Suite | Passed | Failed | Notes |
|-------|--------|--------|-------|
| tests/test_llm_analyst.py | 12 | 0 | All 12 GREEN — 9 stubs converted |
| All prior-phase tests | 48 | 0 | No regressions across all 5 test files |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Catch tenacity.RetryError in analyze_column**
- **Found during:** Task 2 — `test_rate_limit_retries_then_fallback` failed with `tenacity.RetryError`
- **Issue:** Plan stated "reraise=False means tenacity returns None after 3 failed attempts" but actual tenacity behavior is: when all attempts raise, tenacity raises `RetryError` regardless of `reraise=False`. `reraise=False` only controls whether the original exception is re-raised vs wrapped in `RetryError`. Since all attempts raised, `RetryError` propagated out of `_call_minimax` and was not caught by `except openai.APIError`.
- **Fix:** Imported `RetryError` from tenacity and added `except RetryError: pass` clause alongside `except openai.APIError: pass` in `analyze_column`. This causes the fallback path to activate after tenacity exhausts its retry budget.
- **Files modified:** `agents/llm_analyst.py`
- **Commit:** dfe46a2

## Commits

| Hash | Message |
|------|---------|
| 84a2ce0 | feat(04-02): implement _call_minimax, _build_messages, _deterministic_fallback, analyze_column |
| dfe46a2 | feat(04-02): convert 9 RED stubs to GREEN behavioral assertions + fix RetryError handling |

## Self-Check: PASSED

| Item | Status |
|------|--------|
| agents/llm_analyst.py | FOUND |
| tests/test_llm_analyst.py | FOUND |
| commit 84a2ce0 | FOUND |
| commit dfe46a2 | FOUND |
| 12 tests GREEN | VERIFIED |
| 48 total tests GREEN | VERIFIED |
| No pandas imports in llm_analyst.py | VERIFIED |
| max_retries=0 present | VERIFIED |
| stop_after_attempt(3) present | VERIFIED |
| retry_if_exception_type(openai.RateLimitError) present | VERIFIED |
| claims=[] in _deterministic_fallback | VERIFIED |

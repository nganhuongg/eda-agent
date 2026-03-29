# Phase 3: Ralph Loop Utility - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 03-ralph-loop-utility
**Areas discussed:** Loop interface, Feedback threading, Best-attempt selection, Gate 2 quality checker

---

## Loop Interface

| Option | Description | Selected |
|--------|-------------|----------|
| Single generic `run_loop()` | One function accepting `generator_fn` and `critic_fn` as callables; Gate 1 and Gate 2 pass different critic functions | ✓ |
| Two separate functions | `run_investigation_loop()` and `run_output_review_loop()` with hardcoded logic inside each | |

**User's choice:** Claude recommended — user deferred to analysis ("I do not have knowledge for foundation in this, analyze and recommend the best option + reasons for me")
**Notes:** Recommendation based on identical loop mechanics for both gates; separation of concerns via caller-supplied critic_fn rather than separate loop implementations.

---

## Feedback Threading

| Option | Description | Selected |
|--------|-------------|----------|
| Flat list as argument | `generator_fn(rejected_claims=[...])` on each iteration; empty list on iteration 0 | ✓ |
| Accumulated context dict | A `context` dict built up across iterations and passed in full | |

**User's choice:** Claude recommended — user deferred to analysis
**Notes:** LOOP-02 specifies "prior rejection feedback" (singular iteration). Flat list keeps prompt lean and is easier to verify in tests.

---

## Best-Attempt Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Last attempt | Return result from the final iteration — most informed by correction passes | ✓ |
| Fewest rejected claims | Track all attempts, return the one with the shortest rejected_claims list | |

**User's choice:** Claude recommended — user deferred to analysis
**Notes:** Last attempt is strictly most-informed due to cumulative feedback threading. Avoids bookkeeping complexity with no correctness advantage.

---

## Gate 2 Quality Checker

| Option | Description | Selected |
|--------|-------------|----------|
| Inline in `ralph_loop.py` | `quality_bar_critic()` function in same file, passed as `critic_fn` to `run_loop()` | ✓ |
| Separate `report/quality_checker.py` | Extracted module — one function used only by `ralph_loop.py` | |

**User's choice:** Claude recommended — user deferred to analysis
**Notes:** Quality checker is the Gate 2 critic — belongs with the loop that uses it. No decoupling benefit from extraction at this phase; Phase 6 can extract if logic grows.

---

## Claude's Discretion

None — all areas had clear recommended options that were accepted.

## Deferred Ideas

None.

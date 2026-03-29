# Phase 4: LLM Analyst - Research

**Researched:** 2026-03-29
**Domain:** LLM integration (MiniMax via openai SDK), Pydantic structured output, exponential backoff retry
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** One `AnalystDecision` per column. A single LLM call receives signal context and returns: column, hypothesis, recommended_tools, business_label, narrative, claims[].

```python
class AnalystDecision(BaseModel):
    column: str
    hypothesis: str
    recommended_tools: List[str]  # names from ACTION_TO_TOOL keys
    business_label: Literal["risk", "opportunity", "anomaly", "trend"]
    narrative: str  # plain business language, no statistical jargon
    claims: List[dict]  # [{"field": "skewness", "value": 2.3}, ...]
```

**D-02:** `AnalystDecision` is added to `agents/schemas.py` alongside `CriticVerdict`.

**D-03:** `recommended_tools` values must be drawn from `ACTION_TO_TOOL` keys: `analyze_distribution`, `detect_outliers`, `analyze_missing_pattern`, `analyze_correlation`. The LLM prompt must enumerate valid tool names explicitly.

**D-04:** `AnalystDecision` must pass `model_validate_json()`. Any malformed MiniMax response triggers the fallback path — not a recoverable parse error.

**D-05:** Provider is MiniMax. Raw `openai` SDK with `base_url` override. Model name and base URL confirmed by researcher (see Standard Stack below).

**D-06:** Environment variable: `MINIMAX_API_KEY`. If unset, Analyst falls back to deterministic mode immediately.

**D-07:** On API failure or retry exhaustion, fall back to:
- Column selection: `risk_driven_planner(state)`
- Finding: `generate_insight_for_column(column, column_type, signals, analysis_results)`
- Wrap result in `AnalystDecision`-compatible shape. Log warning. Run never aborts.

**D-08:** Retry policy: exponential backoff, max 3 retries before triggering fallback.

**D-09:** `build_analyst_context()` extracts only diagnostic signal fields — not the full signals dict. Fields per column type:
- Numeric: `missing_ratio`, `skewness`, `outlier_ratio`, `variance`
- Categorical: `entropy`, `dominant_ratio`, `unique_count`
- Temporal (if present): `trend_direction`, `trend_confidence`, `mom_delta`, `yoy_delta`, `forecast_values`

**D-10:** `build_analyst_context()` accepts `AgentState` + target column. Returns plain dict with no DataFrame references, no raw column values, no PII. Confirmed by sentinel-df test.

**D-11:** Context dict also includes `risk_score` for the target column (from `state["risk_scores"]`) and list of already-analyzed columns.

**Inherited Locked Decisions:**
- `df` boundary is non-negotiable — `llm_analyst.py` must never import or receive a DataFrame
- `CriticVerdict` shape locked: `approved: bool`, `rejected_claims: List[str]`
- `agents/schemas.py` is the home for new Pydantic models
- Raw openai SDK — no LangChain, no other LLM framework
- Hard max 5 iterations on any loop

### Claude's Discretion

- **Prompt placement:** System prompt (tool names, output format schema, signal field definitions, business label definitions) may be inline constants in `llm_analyst.py` or a separate template file.
- **Backoff values:** Specific wait durations (e.g., 1s, 2s, 4s base) are Claude's discretion within the 3-retry policy.

### Deferred Ideas (OUT OF SCOPE)

None surfaced during discussion.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ANLST-01 | LLM Analyst selects the next column to investigate based on risk scores and prior findings | D-11: `risk_score` + `analyzed_columns` included in context; `risk_driven_planner` as fallback column selector |
| ANLST-02 | LLM Analyst forms a testable hypothesis before each analysis tool is invoked | D-01: `hypothesis` field in `AnalystDecision`; single LLM call produces hypothesis before tools run |
| ANLST-03 | LLM Analyst recommends which analysis tools to run based on column signals | D-03: `recommended_tools` constrained to `ACTION_TO_TOOL` keys, enumerated in prompt |
| ANLST-04 | LLM Analyst labels each finding as risk, opportunity, anomaly, or trend | D-01: `business_label: Literal["risk", "opportunity", "anomaly", "trend"]` in schema |
| ANLST-05 | LLM Analyst explains each finding in plain business language without statistical jargon | D-01: `narrative` field; system prompt instructs plain language output |
| ANLST-06 | LLM Analyst receives only computed signal dicts — never raw CSV rows or column values | D-09/D-10: `build_analyst_context()` enforces df boundary; confirmed by sentinel-df test |
</phase_requirements>

---

## Summary

Phase 4 builds a single module, `agents/llm_analyst.py`, that integrates the MiniMax LLM as an analyst agent. The module has two public responsibilities: `build_analyst_context(state, column)` — which serializes signal fields from `AgentState` into a plain dict with no DataFrame references — and `analyze_column(state, column, rejected_claims=[])` — which calls MiniMax, parses the response into an `AnalystDecision`, and falls back to the deterministic pipeline if the API fails.

The technical stack is confirmed available in the project environment: `openai==2.24.0`, `pydantic==2.12.5`, `tenacity==9.1.4`. MiniMax's OpenAI-compatible endpoint is `https://api.minimax.io/v1`. The best available text reasoning model is `MiniMax-M2.7` (204,800 token context, ~60 tokens/sec). Rate limits for paid accounts are 500 RPM / 20M TPM, making 429 errors unlikely but still requiring a retry wrapper per D-08.

The phase is entirely self-contained (no changes to the orchestrator) and testable without a live API key by relying on fallback mode and mock-patching the OpenAI client.

**Primary recommendation:** Use `tenacity` with `wait_random_exponential(min=1, max=30)` and `stop_after_attempt(3)` retrying on `openai.RateLimitError` only; wrap in a try/except for all other `openai.APIError` subclasses that immediately triggers fallback without retrying.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| openai | 2.24.0 (installed) | MiniMax API client via base_url override | Already in project; confirmed working with non-OpenAI providers |
| pydantic | 2.12.5 (installed) | `AnalystDecision` schema + `model_validate_json()` | Project-established pattern from Phase 2 `CriticVerdict` |
| tenacity | 9.1.4 (installed) | Exponential backoff retry decorator | OpenAI cookbook recommendation; already in requirements.txt |
| python-dotenv | 1.2.2 (installed) | Load `MINIMAX_API_KEY` from `.env` | Already used in project |

### MiniMax API Facts (HIGH confidence — verified from platform.minimax.io)

| Property | Value |
|----------|-------|
| Base URL | `https://api.minimax.io/v1` |
| Best text model | `MiniMax-M2.7` (204,800 token context) |
| Fast variant | `MiniMax-M2.7-highspeed` (~100 tokens/sec vs 60 for standard) |
| Paid RPM | 500 requests/minute |
| Paid TPM | 20,000,000 tokens/minute |
| Rate limit status | HTTP 429 (standard; confirmed via openai SDK `RateLimitError`) |

**Recommended model choice:** `MiniMax-M2.7` (standard, not highspeed). The context window (204,800 tokens) far exceeds any signal dict we could send. Standard variant is more suitable for batch/analytical workloads where low latency is not the primary concern.

**Installation:** All dependencies already present. No `pip install` required.

**Version verification:** `openai` 2.24.0, `pydantic` 2.12.5, `tenacity` 9.1.4 confirmed via `requirements.txt` in working directory.

---

## Architecture Patterns

### Recommended Module Structure

```
agents/
├── __init__.py          # existing
├── schemas.py           # existing — add AnalystDecision here (D-02)
└── llm_analyst.py       # new — build_analyst_context() + analyze_column()
tests/
└── test_llm_analyst.py  # new — sentinel-df, fallback, retry, schema tests
```

No new directories. Prompt constants live as module-level strings inside `llm_analyst.py` (Claude's discretion — inline is simpler for this scope, avoids template file dependency).

### Pattern 1: OpenAI Client with MiniMax base_url

```python
# Source: platform.minimax.io/docs/api-reference/text-openai-api
import os
from openai import OpenAI

def _build_client() -> OpenAI:
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        return None  # triggers fallback immediately (D-06)
    return OpenAI(
        api_key=api_key,
        base_url="https://api.minimax.io/v1",
        max_retries=0,  # tenacity handles retries; disable SDK-level retries
    )
```

**Important:** Set `max_retries=0` on the `OpenAI` client. The SDK has built-in retry logic (`max_retries=2` by default) that conflicts with tenacity's retry loop. Disabling SDK retries gives tenacity full control over the 3-attempt budget (D-08).

### Pattern 2: Tenacity Retry Wrapper

```python
# Source: developers.openai.com/cookbook/examples/how_to_handle_rate_limits
import openai
from tenacity import retry, stop_after_attempt, wait_random_exponential

@retry(
    wait=wait_random_exponential(min=1, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(openai.RateLimitError),
    reraise=False,
)
def _call_minimax(client: OpenAI, messages: list[dict]) -> str:
    response = client.chat.completions.create(
        model="MiniMax-M2.7",
        messages=messages,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content
```

`reraise=False` means tenacity returns `None` after exhausting retries rather than raising — the caller checks for `None` and activates fallback.

**Catching non-rate-limit errors:** Wrap the tenacity call in an outer `try/except openai.APIError` to catch network failures, timeouts, and auth errors. These should trigger fallback immediately without retrying.

```python
try:
    raw_json = _call_minimax(client, messages)
except openai.APIError:
    raw_json = None  # triggers deterministic fallback
```

### Pattern 3: Pydantic model_validate_json() for LLM Output

```python
# Source: pydantic docs + established CriticVerdict pattern in agents/schemas.py
import json
from pydantic import ValidationError
from agents.schemas import AnalystDecision

def _parse_analyst_decision(raw_json: str | None) -> AnalystDecision | None:
    if raw_json is None:
        return None
    try:
        return AnalystDecision.model_validate_json(raw_json)
    except (ValidationError, json.JSONDecodeError):
        # D-04: malformed response = fallback, not recoverable parse error
        import warnings
        warnings.warn(f"AnalystDecision parse failure: {raw_json[:200]}")
        return None
```

**Key insight:** `response_format={"type": "json_object"}` in the API call forces valid JSON output from MiniMax (supported by the OpenAI-compatible endpoint). This eliminates `JSONDecodeError` in practice, but catching it provides defense-in-depth.

### Pattern 4: System Prompt for Structured Output

The system prompt must do three things to make `model_validate_json()` reliable:

1. **Enumerate valid tool names exactly** (D-03) — copy from `ACTION_TO_TOOL` keys
2. **Include the JSON schema** for `AnalystDecision` (field names, types, allowed values)
3. **Forbid explanatory text** outside the JSON object — instruct the model to return only the JSON

Recommended system prompt structure:
```
You are a data analyst. For the given column signals, return ONLY a JSON object
matching this exact schema:
{
  "column": "<string: column name>",
  "hypothesis": "<string: testable prediction>",
  "recommended_tools": ["<one or more of: analyze_distribution, detect_outliers,
                          analyze_missing_pattern, analyze_correlation>"],
  "business_label": "<one of: risk, opportunity, anomaly, trend>",
  "narrative": "<string: plain business language, no statistical jargon>",
  "claims": [{"field": "<signal_field_name>", "value": <numeric_value>}]
}
Return no text before or after the JSON object.
```

The user message provides the serialized signal context from `build_analyst_context()`.

### Pattern 5: build_analyst_context() — df Boundary Enforcement

```python
from state.runtime_state import AgentState

def build_analyst_context(state: AgentState, column: str) -> dict:
    """Returns a plain dict with no DataFrame references. D-09, D-10, D-11."""
    col_signals = state["signals"].get(column, {})
    col_type = state["dataset_metadata"].get(column, {}).get("type", "unknown")

    if col_type == "numeric":
        extracted = {
            k: col_signals.get(k)
            for k in ("missing_ratio", "skewness", "outlier_ratio", "variance")
        }
    else:
        extracted = {
            k: col_signals.get(k)
            for k in ("entropy", "dominant_ratio", "unique_count", "missing_ratio")
        }

    # Temporal signals (optional — D-09)
    temporal = state.get("temporal_signals", {}).get(column, {})
    for k in ("trend_direction", "trend_confidence", "mom_delta", "yoy_delta", "forecast_values"):
        if k in temporal:
            extracted[k] = temporal[k]

    return {
        "column": column,
        "column_type": col_type,
        "signals": extracted,
        "risk_score": state["risk_scores"].get(column, 0.0),
        "analyzed_columns": list(state.get("analyzed_columns", set())),
    }
```

**The contract:** This function must never access `df`, never call `.values`, `.to_dict()`, or any DataFrame method. The sentinel-df test (see Validation Architecture) proves this.

### Pattern 6: Deterministic Fallback

```python
from planning.risk_planner import risk_driven_planner
from insight.insight_generator import generate_insight_for_column
import logging

def _deterministic_fallback(state: AgentState, column: str) -> AnalystDecision:
    """D-07: wrap deterministic pipeline output into AnalystDecision shape."""
    column_type = state["dataset_metadata"].get(column, {}).get("type", "numeric")
    signals = state["signals"].get(column, {})
    analysis_results = state["analysis_results"].get(column, {})

    insight = generate_insight_for_column(column, column_type, signals, analysis_results)

    logging.warning(f"LLM Analyst fell back to deterministic mode for column '{column}'")

    return AnalystDecision(
        column=column,
        hypothesis=f"Deterministic fallback — column '{column}' flagged by risk planner",
        recommended_tools=["analyze_distribution"],
        business_label=_infer_label_from_insight(insight),
        narrative=_insight_to_narrative(insight),
        claims=[],  # no claims in fallback — avoids false Critic rejections
    )
```

**Why `claims=[]` in fallback:** The Critic validates claims against signals. Fallback findings with `claims=[]` pass Critic validation unconditionally (`approved=True` per `validate_finding` behavior confirmed in test_critic.py line 143). This prevents the fallback from triggering spurious Critic rejections.

### Anti-Patterns to Avoid

- **Anti-pattern — SDK retries + tenacity both active:** Having both `max_retries=2` (SDK default) and `stop_after_attempt(3)` (tenacity) active means up to 6 total attempts. Set `max_retries=0` on the client.
- **Anti-pattern — catch all exceptions in tenacity:** Only retry `RateLimitError`. Retrying `AuthenticationError` or `BadRequestError` wastes quota and delays fallback.
- **Anti-pattern — `claims` with free-text fields in fallback:** The Critic rejects claims whose `field` value is not in `signals` or `analysis_results`. Fallback must use `claims=[]`.
- **Anti-pattern — importing `df` for `build_analyst_context`:** The function signature must accept `AgentState` (TypedDict), not `pd.DataFrame`. The sentinel-df test catches this.
- **Anti-pattern — streaming mode:** Do not use `stream=True` with MiniMax's OpenAI-compatible endpoint for structured output. The response must be complete before `model_validate_json()` is called.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exponential backoff | Manual sleep/retry loop | `tenacity` (9.1.4, installed) | Handles jitter, max attempts, reraise control; battle-tested against OpenAI APIs |
| JSON validation of LLM output | Custom regex/dict parsing | `pydantic.model_validate_json()` | Established project pattern; gives typed object + clear error on malformed response |
| Rate-limit detection | Parsing error message strings | `openai.RateLimitError` exception type | SDK provides typed exceptions; string parsing is fragile across API provider changes |
| Key-missing fallback | `os.getenv()` + string comparison | `os.environ.get("MINIMAX_API_KEY")` returns `None` which is falsy — no custom class needed | Simple and consistent with D-06 |

**Key insight:** The openai SDK with `base_url` override is a zero-cost integration pattern — no new adapter, no wrapper class. MiniMax's endpoint speaks the same protocol as the standard OpenAI API. The entire integration fits in ~50 lines.

---

## Runtime State Inventory

Phase 4 is a new-file phase (no rename/refactor). Step 2.5 is not applicable.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `openai` Python SDK | MiniMax API client | Yes | 2.24.0 | — |
| `pydantic` | `AnalystDecision` schema | Yes | 2.12.5 | — |
| `tenacity` | Retry decorator | Yes | 9.1.4 | — |
| `MINIMAX_API_KEY` env var | Live MiniMax calls | Unknown at research time | — | Deterministic fallback (D-06, D-07) |
| `https://api.minimax.io/v1` | LLM calls | Reachable (MiniMax production) | — | Deterministic fallback |
| `pytest` | Test execution | Yes | confirmed | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** `MINIMAX_API_KEY` — if unset or invalid, the Analyst falls back to deterministic mode. All tests must pass without the key present.

---

## Common Pitfalls

### Pitfall 1: SDK Built-in Retries Interfering with Tenacity

**What goes wrong:** The openai SDK defaults to `max_retries=2`. Combined with tenacity's `stop_after_attempt(3)`, you get up to 6 actual HTTP requests for one logical attempt. Worse, the SDK may raise after its own 2 retries before tenacity sees the error.

**Why it happens:** The `OpenAI` class has its own retry loop at the HTTP transport layer; tenacity sits above it at the Python call level.

**How to avoid:** Always construct the client with `max_retries=0` when using tenacity.

**Warning signs:** Retry tests show more HTTP calls than expected; backoff delays are inconsistent.

### Pitfall 2: `response_format` Not Enforcing Schema Compliance

**What goes wrong:** Even with `response_format={"type": "json_object"}`, MiniMax returns valid JSON that does not match `AnalystDecision`'s field names or `Literal` constraints. `model_validate_json()` raises `ValidationError`.

**Why it happens:** `json_object` mode only guarantees valid JSON syntax — not schema conformance. The LLM must be instructed about the exact schema through the system prompt.

**How to avoid:** Include the full field list and allowed values for `business_label` in the system prompt. Treat `ValidationError` the same as a null response (D-04) — log the raw response, activate fallback.

**Warning signs:** Fallback triggered unexpectedly; check logs for the first 200 chars of the raw response.

### Pitfall 3: `df` Boundary Leak via State Reference

**What goes wrong:** Code inside `build_analyst_context()` accesses `state["dataset_metadata"]` for the column type — acceptable. But then a refactor accidentally adds `df[column]` or passes `state` to a function that still has `df` in scope.

**Why it happens:** `AgentState` does not hold a DataFrame, but `orchestrator.py` holds both `state` and `df`. If `llm_analyst.py` imports from `orchestrator`, it could gain indirect access.

**How to avoid:** `llm_analyst.py` must not import from `orchestrator.orchestrator`. The sentinel-df test (inject a DataFrame with PII sentinel values into a fake state, confirm `build_analyst_context()` output contains none of them) is the enforcement mechanism.

**Warning signs:** `pandas` or `pd` appears in imports of `llm_analyst.py`.

### Pitfall 4: Fallback Claims Causing Critic Rejection

**What goes wrong:** Deterministic fallback builds an `AnalystDecision` with `claims` derived from insight dict fields (e.g., `"missing_level": "high_missing"`). The Critic looks for this field in `signals` (which contains `"missing_ratio"`, not `"missing_level"`) and rejects it.

**Why it happens:** `generate_insight_for_column()` returns category strings (`"high_missing"`, `"high_skew"`) not numeric signal values. The Critic's `validate_finding()` requires numeric field lookups.

**How to avoid:** Fallback `AnalystDecision` always uses `claims=[]`. This is confirmed safe by the existing `test_empty_claims_returns_approved` test.

### Pitfall 5: `analyze_column()` Signature Incompatible with `run_loop`

**What goes wrong:** Phase 5 will pass `analyze_column` as `generator_fn` to `run_loop()`. The `run_loop` contract is `generator_fn(rejected_claims: List[str]) -> Any`. If `analyze_column` has signature `(state, column, rejected_claims)`, Phase 5 must partially apply the first two arguments with `functools.partial` or a lambda.

**Why it happens:** `run_loop` is generic — it does not know about state or column.

**How to avoid:** Design `analyze_column(state, column, rejected_claims=[])` now. Phase 5 will call `run_loop(partial(analyze_column, state, column), critic_fn)`. Document this in the module docstring. Phase 4 tests should test the full `analyze_column(state, column, rejected_claims)` signature directly.

---

## Code Examples

### Complete analyze_column() Skeleton

```python
# agents/llm_analyst.py
import os
import logging
import warnings
from typing import List

import openai
from openai import OpenAI
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from agents.schemas import AnalystDecision
from state.runtime_state import AgentState
from planning.risk_planner import risk_driven_planner
from insight.insight_generator import generate_insight_for_column

_VALID_TOOLS = [
    "analyze_distribution",
    "detect_outliers",
    "analyze_missing_pattern",
    "analyze_correlation",
]

_SYSTEM_PROMPT = """..."""  # inline constant (Claude's discretion)


def build_analyst_context(state: AgentState, column: str) -> dict:
    """Returns a signal-only context dict. No DataFrame references. (D-09, D-10, D-11)"""
    ...


def _get_client() -> OpenAI | None:
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        return None
    return OpenAI(
        api_key=api_key,
        base_url="https://api.minimax.io/v1",
        max_retries=0,  # tenacity owns retry budget
    )


@retry(
    wait=wait_random_exponential(min=1, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(openai.RateLimitError),
    reraise=False,
)
def _call_minimax(client: OpenAI, messages: list) -> str | None:
    response = client.chat.completions.create(
        model="MiniMax-M2.7",
        messages=messages,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def analyze_column(
    state: AgentState,
    column: str,
    rejected_claims: List[str] | None = None,
) -> AnalystDecision:
    """Public entry point. Phase 5 wraps this with functools.partial for run_loop."""
    client = _get_client()
    if client is None:
        return _deterministic_fallback(state, column)

    context = build_analyst_context(state, column)
    messages = _build_messages(context, rejected_claims or [])

    raw_json = None
    try:
        raw_json = _call_minimax(client, messages)
    except openai.APIError:
        pass  # network, auth, timeout — go to fallback immediately

    if raw_json is not None:
        try:
            return AnalystDecision.model_validate_json(raw_json)
        except (ValidationError, ValueError):
            warnings.warn(f"AnalystDecision parse failure for '{column}': {raw_json[:200]}")

    return _deterministic_fallback(state, column)
```

### AnalystDecision Schema Addition

```python
# agents/schemas.py — add after CriticVerdict
from typing import List, Literal

class AnalystDecision(BaseModel):
    column: str
    hypothesis: str
    recommended_tools: List[str]
    business_label: Literal["risk", "opportunity", "anomaly", "trend"]
    narrative: str
    claims: List[dict]
```

### Sentinel-df Test Pattern

```python
# tests/test_llm_analyst.py
import pandas as pd
from state.runtime_state import initialize_state

_SENTINEL = "SHOULD_NOT_APPEAR_IN_CONTEXT"

def _make_state_with_sentinel_df():
    """State built from signal extraction — df is not stored in AgentState."""
    state = initialize_state()
    state["signals"] = {
        "revenue": {
            "missing_ratio": 0.05,
            "skewness": 2.3,
            "outlier_ratio": 0.08,
            "variance": 150.0,
        }
    }
    state["dataset_metadata"] = {"revenue": {"type": "numeric"}}
    state["risk_scores"] = {"revenue": 0.42}
    # Note: df is NOT in AgentState — it cannot leak through state alone.
    # The sentinel verifies that build_analyst_context does not call any
    # function that could access the original DataFrame.
    return state

def test_build_analyst_context_contains_no_df_reference():
    """ANLST-06: context dict must contain only signal scalars."""
    from agents.llm_analyst import build_analyst_context
    state = _make_state_with_sentinel_df()
    ctx = build_analyst_context(state, "revenue")

    import json
    ctx_str = json.dumps(ctx, default=str)
    assert _SENTINEL not in ctx_str
    assert "DataFrame" not in ctx_str
    assert isinstance(ctx["signals"]["missing_ratio"], float)
    assert isinstance(ctx["signals"]["skewness"], float)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `openai.ChatCompletion.create()` (v0.x) | `client.chat.completions.create()` (v1.x+) | openai 1.0 (Nov 2023) | Must use instance method, not class method |
| `pydantic.parse_raw()` | `model_validate_json()` | Pydantic v2 (2023) | `parse_raw` removed; project already on Pydantic 2.12.5 |
| `resample("M")` | `resample("ME")` | pandas 2.x | Already applied in Phase 1 (see STATE.md) |
| Groq as LLM provider | MiniMax as LLM provider | Phase 4 decision (D-05) | `GROQ_API_KEY` pattern replaced by `MINIMAX_API_KEY`; endpoint changes from `api.groq.com/openai/v1` to `api.minimax.io/v1` |

**Deprecated/outdated in this codebase:**
- `GROQ_API_KEY` pattern: replaced by `MINIMAX_API_KEY` in Phase 4. The ROADMAP still mentions "Groq retry wrapper" (outdated text from before D-05 decision) — the plan should use "MiniMax retry wrapper".

---

## Open Questions

1. **MiniMax `reasoning_split` parameter**
   - What we know: The MiniMax docs example includes `extra_body={"reasoning_split": True}` in the Python sample
   - What's unclear: Whether this is required, optional, or only for reasoning-heavy tasks
   - Recommendation: Omit in initial implementation. Add only if response quality is poor in testing. It adds no overhead if unused.

2. **MiniMax response on `ValidationError` — exact error shape**
   - What we know: The endpoint returns JSON in `json_object` mode
   - What's unclear: Whether MiniMax wraps parse errors differently than vanilla OpenAI (e.g., custom error codes)
   - Recommendation: Catch `openai.APIStatusError` as the broadest API-level error; catch `openai.RateLimitError` specifically for retry. This covers all known MiniMax error shapes.

3. **`analyze_column` return type when fallback is used and `column` is not in `dataset_metadata`**
   - What we know: `risk_driven_planner` could theoretically return a column not in metadata (edge case)
   - What's unclear: Whether `generate_insight_for_column` handles a missing `column_type` gracefully
   - Recommendation: Guard in `_deterministic_fallback` with `column_type = state["dataset_metadata"].get(column, {}).get("type", "numeric")` — default to "numeric" to avoid KeyError.

---

## Project Constraints (from CLAUDE.md)

CLAUDE.md does not exist in this project. Constraints are sourced from STATE.md and CONTEXT.md.

From STATE.md Active Decisions:
- Raw openai SDK over LangChain — enforced
- Deterministic Critic strategy — unaffected by Phase 4
- `df` boundary — enforced by `build_analyst_context()`

From STATE.md Active Risks:
- "`df` reaching agent modules" — mitigated by sentinel-df test (this phase implements the mitigation)

---

## Validation Architecture

Nyquist validation is enabled (`workflow.nyquist_validation: true` in config.json).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (confirmed installed) |
| Config file | None detected — uses default pytest discovery |
| Quick run command | `pytest tests/test_llm_analyst.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ANLST-01 | `analyze_column` returns `AnalystDecision` with column, hypothesis, tools, label | unit | `pytest tests/test_llm_analyst.py::test_analyze_column_returns_analyst_decision -x` | No — Wave 0 |
| ANLST-02 | `AnalystDecision.hypothesis` is a non-empty string | unit | `pytest tests/test_llm_analyst.py::test_analyst_decision_hypothesis_non_empty -x` | No — Wave 0 |
| ANLST-03 | `recommended_tools` values are all in `ACTION_TO_TOOL` keys | unit | `pytest tests/test_llm_analyst.py::test_recommended_tools_valid -x` | No — Wave 0 |
| ANLST-04 | `business_label` is one of risk/opportunity/anomaly/trend | unit | `pytest tests/test_llm_analyst.py::test_business_label_valid -x` | No — Wave 0 |
| ANLST-05 | `narrative` is plain text (no jargon — tested via non-empty string + fallback label helper) | unit | `pytest tests/test_llm_analyst.py::test_narrative_non_empty -x` | No — Wave 0 |
| ANLST-06 | `build_analyst_context()` output contains no DataFrame references | unit (sentinel-df) | `pytest tests/test_llm_analyst.py::test_build_analyst_context_contains_no_df_reference -x` | No — Wave 0 |
| D-04 | Malformed JSON triggers fallback, not exception | unit | `pytest tests/test_llm_analyst.py::test_malformed_json_triggers_fallback -x` | No — Wave 0 |
| D-06 | Missing API key triggers fallback immediately | unit | `pytest tests/test_llm_analyst.py::test_missing_api_key_triggers_fallback -x` | No — Wave 0 |
| D-07 | Fallback returns valid `AnalystDecision` with `claims=[]` | unit | `pytest tests/test_llm_analyst.py::test_fallback_returns_analyst_decision -x` | No — Wave 0 |
| D-08 | 429 RateLimitError triggers retry up to 3 times then fallback | unit (mock) | `pytest tests/test_llm_analyst.py::test_rate_limit_retries_then_fallback -x` | No — Wave 0 |
| D-10 | `build_analyst_context()` only returns signal scalar fields | unit (sentinel-df) | `pytest tests/test_llm_analyst.py::test_build_analyst_context_contains_no_df_reference -x` | No — Wave 0 |
| CRIT-04 (regression) | `AnalystDecision` passes `model_validate_json()` round-trip | unit | `pytest tests/test_llm_analyst.py::test_analyst_decision_json_roundtrip -x` | No — Wave 0 |

### Key Test Designs

**Sentinel-df test (ANLST-06, D-10):**
Construct an `AgentState` manually — signals, metadata, risk_scores — without any DataFrame present (AgentState TypedDict does not hold a `df` key). Call `build_analyst_context(state, column)`. Serialize output to JSON string. Assert that no DataFrame-type strings, no sentinel PII values, and no pandas Series representations appear. This test works because `AgentState` structurally cannot hold a `df` reference, so any leak would require importing pandas inside `llm_analyst.py` — which is itself an anti-pattern detectable by `grep`.

**Fallback without API key (D-06):**
```python
def test_missing_api_key_triggers_fallback(monkeypatch):
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    result = analyze_column(minimal_state, "revenue", rejected_claims=[])
    assert isinstance(result, AnalystDecision)
    assert result.column == "revenue"
    assert result.claims == []
```

**Retry logic with mock 429 (D-08):**
```python
from unittest.mock import patch, MagicMock

def test_rate_limit_retries_then_fallback(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    call_count = {"n": 0}

    def mock_create(**kwargs):
        call_count["n"] += 1
        raise openai.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body={},
        )

    with patch("agents.llm_analyst.OpenAI") as MockClient:
        instance = MockClient.return_value
        instance.chat.completions.create.side_effect = mock_create
        result = analyze_column(minimal_state, "revenue")

    # tenacity retries 3 times before giving up and returning None
    assert call_count["n"] == 3
    # fallback must have activated — AnalystDecision with claims=[]
    assert isinstance(result, AnalystDecision)
    assert result.claims == []
```

**Malformed JSON fallback (D-04):**
```python
def test_malformed_json_triggers_fallback(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    with patch("agents.llm_analyst._call_minimax", return_value='{"invalid": true}'):
        result = analyze_column(minimal_state, "revenue")

    assert isinstance(result, AnalystDecision)
    # Validation failed → fallback → claims = []
    assert result.claims == []
```

**Schema round-trip (project pattern from CriticVerdict):**
```python
def test_analyst_decision_json_roundtrip():
    decision = AnalystDecision(
        column="revenue",
        hypothesis="Revenue distribution is right-skewed due to outliers",
        recommended_tools=["analyze_distribution", "detect_outliers"],
        business_label="risk",
        narrative="Revenue shows concentrated risk from extreme values",
        claims=[{"field": "skewness", "value": 2.3}],
    )
    restored = AnalystDecision.model_validate_json(decision.model_dump_json())
    assert restored == decision
```

### Sampling Rate

- **Per task commit:** `pytest tests/test_llm_analyst.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_llm_analyst.py` — covers all ANLST-01..06, D-04, D-06, D-07, D-08, D-10, and `AnalystDecision` schema round-trip (12 tests total minimum)
- [ ] `agents/llm_analyst.py` — new file, does not exist yet
- [ ] `AnalystDecision` in `agents/schemas.py` — new class to add

No new test framework or config needed — pytest discovery already works for the `tests/` directory.

---

## Sources

### Primary (HIGH confidence)

- `platform.minimax.io/docs/api-reference/text-openai-api` — base URL (`https://api.minimax.io/v1`), model names, Python SDK example
- `platform.minimax.io/docs/guides/rate-limits` — 500 RPM / 20M TPM for text models (paid tier)
- `openai` Python package 2.24.0 (installed) — `RateLimitError`, `APIError`, `APIConnectionError`, `APITimeoutError` exception types confirmed via `dir(openai)`
- `tenacity` 9.1.4 (installed) — `retry`, `stop_after_attempt`, `wait_random_exponential`, `retry_if_exception_type` imports confirmed
- `agents/schemas.py` — `CriticVerdict` pattern for `AnalystDecision` schema design
- `tests/test_critic.py` — lazy import pattern, `model_validate_json` round-trip test pattern
- `orchestrator/orchestrator.py` — `ACTION_TO_TOOL` keys: `analyze_distribution`, `detect_outliers`, `analyze_missing_pattern`, `analyze_correlation`
- `state/runtime_state.py` — `AgentState` TypedDict field names
- `profiling/signal_extractor.py` — signal field names per column type

### Secondary (MEDIUM confidence)

- `developers.openai.com/cookbook/examples/how_to_handle_rate_limits` — tenacity decorator pattern with `wait_random_exponential`, `stop_after_attempt`, `retry_if_exception_type`
- `requirements.txt` — confirmed `tenacity==9.1.4`, `openai==2.24.0`, `pydantic==2.12.5` installed

### Tertiary (LOW confidence)

- WebSearch result on `reasoning_split` parameter — MiniMax-specific extension; unverified whether required for chat completions

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all versions confirmed from installed packages and official MiniMax docs
- Architecture: HIGH — patterns derived from existing codebase (CriticVerdict, ralph_loop) + OpenAI official cookbook
- Pitfalls: HIGH — SDK built-in retry interaction is a known documented behavior; df boundary is codebase-specific and confirmed by reading existing code
- Test architecture: HIGH — follows established project patterns from test_critic.py and test_ralph_loop.py exactly

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (MiniMax API endpoints and model names are stable; openai SDK patterns are stable)

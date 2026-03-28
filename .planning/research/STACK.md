# Stack Research — EDA Agent v3

## LLM Orchestration

**Recommendation: Raw `openai` SDK (already installed) — NO LangChain**

| Library | Decision | Rationale |
|---------|----------|-----------|
| `openai==2.24.0` | ✓ Use | Already installed, already pointed at Groq's OpenAI-compatible API in `llm_report_writer.py`. Zero new dependencies. |
| `pydantic==2.12.5` | ✓ Use | Already installed. Use `BaseModel` for `AnalystDecision` and `CriticVerdict` schemas — parse all LLM JSON via `model_validate_json()` for automatic hallucination rejection. |
| LangChain | ✗ Reject | 50+ transitive dependencies for features this project doesn't need. The orchestrator is a plain Python dict loop — extend it, don't replace it. |
| LlamaIndex | ✗ Reject | RAG-oriented, irrelevant for this use case. |

**Pattern:** Each agent (Analyst, Critic) is a Python function accepting a context dict and returning a Pydantic BaseModel. No framework needed.

---

## Time-Series Analysis

**Recommendation: `statsmodels` + `scipy` — NO Prophet**

| Library | Decision | Rationale |
|---------|----------|-----------|
| `statsmodels>=0.14.0` | ✓ Add | OLS slope for trend detection, `ExponentialSmoothing` for 1-3 month forecasts, `adfuller` as data-quality gate before forecasting. |
| `scipy>=1.13.0` | ✓ Add (likely already present) | Mann-Kendall trend test via `scipy.stats.kendalltau`. |
| Prophet | ✗ Reject | Requires compiled C++/Stan backend (`pystan` or `cmdstanpy`) — routinely fails on Windows 11 without build tools. Over-specified for short CSV series. |
| sktime | ✗ Reject | Full ML pipeline infrastructure for a simple trend + 3-month forecast is overkill. |

**New dependencies:** `statsmodels>=0.14.0` (add to requirements.txt). `scipy` may already be present.

---

## Hallucination Control

**Recommendation: Pydantic schema contracts + rule-based critic verification**

- Define `AnalystDecision(BaseModel)` — fields: `column`, `hypothesis`, `recommended_tools`, `reasoning`
- Define `CriticVerdict(BaseModel)` — fields: `approved: bool`, `rejected_claims: list[str]`, `reason`
- All LLM responses parsed via `model_validate_json()` — validation failure = automatic rejection, forces retry
- Critic verification is **rule-based, not LLM-vs-LLM**: Critic receives Analyst claim + deterministic signal dict, compares numerically (e.g. "claim says high outlier risk but `outlier_ratio=0.002` — reject")
- LLM never receives raw CSV rows, only computed signal dicts

---

## Full Dependency Summary

| Package | Version | Status | Purpose |
|---------|---------|--------|---------|
| `openai` | 2.24.0 | Already installed | Groq API (LLM Analyst + Critic prompts) |
| `pydantic` | 2.12.5 | Already installed | Schema validation for agent outputs |
| `statsmodels` | >=0.14.0 | **Add** | Trend detection, forecasting |
| `scipy` | >=1.13.0 | Verify/Add | Mann-Kendall test |
| `pandas` | existing | Already installed | Data backbone |
| `matplotlib` | existing | Already installed | Visualization |

---

## Confidence

- LLM orchestration: **High** — confirmed from existing codebase
- Time-series stack: **High** — statsmodels is standard, Prophet Windows issues well-documented
- Hallucination control via Pydantic: **High** — established pattern for structured LLM output

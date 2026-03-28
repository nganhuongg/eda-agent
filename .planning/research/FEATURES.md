# Features Research — EDA Agent v3

## What v2 Already Delivers (Validated)

- Risk-scored column investigation (missingness, skewness, outlier ratio, entropy)
- Deterministic signal extraction pipeline
- Insight-triggered visualization (not unconditional)
- Follow-up investigation queue driven by rule-based critic
- Optional LLM narrative rewriting (Groq API)
- Deterministic markdown report output

---

## Table Stakes
*Must have — users expect these from an AI-powered EDA tool*

| Feature | Complexity | Notes |
|---------|-----------|-------|
| Natural-language summaries of findings | Low | LLM Analyst output |
| Risk/opportunity/anomaly labeling per insight | Low | Taxonomy applied by Analyst |
| Ranked insight output (most important first) | Low | Derived from risk scores |
| Time-series trend direction (up/down/flat + confidence) | Medium | statsmodels OLS slope |
| Period comparison (MoM, YoY) | Medium | Requires date column detection |
| Graceful temporal fallback (skip if no date column) | Low | Guard at pipeline entry |
| Grounded claims (every LLM statement cites a signal) | Medium | Critic enforcement |
| Single-run completion without human intervention | Low | Existing v2 behavior |
| Shareable report artifact (markdown + plots) | Low | Existing v2 behavior |
| Deterministic numeric results | Low | Existing v2 behavior, must be preserved |

---

## Differentiators
*Competitive advantage — set v3 apart from generic EDA tools*

| Feature | Complexity | Notes |
|---------|-----------|-------|
| LLM Analyst drives investigation strategy | High | Core v3 feature — column selection, hypothesis formation |
| Critic agent rejects hallucinated claims and forces rewrite | High | Core v3 hallucination control |
| Multi-angle analysis (same data, multiple analytical lenses) | Medium | Run before synthesis/ranking |
| Forecasting with uncertainty ranges (next 1-3 months) | High | ExponentialSmoothing, data-quality gated |
| Explicit data quality fallback messaging | Low | "Insufficient data for forecast" vs silent skip |
| Ralph Loop iterative refinement at two checkpoints | High | Investigation loop + output review loop |
| Privacy-by-design: LLM sees signals only, never raw rows | Medium | Architectural constraint, key trust feature |
| Business-label taxonomy (risk/opportunity/anomaly) | Low | Standardized vocabulary for decision-makers |
| Confidence-scored trend claims | Medium | Distinguishes strong from weak signals |

---

## Anti-Features
*Deliberately NOT building — with rationale*

| Feature | Why Not |
|---------|---------|
| Interactive Q&A after analysis | Out of scope for v3 — single-run focus |
| LLM modifying statistics | Non-negotiable — hallucination + confidentiality risk |
| Dashboard or web UI | CLI-first; adds frontend complexity with no analytical value |
| Unconditional visualization | v2 already gates on insight justification — preserve |
| Streaming / real-time data | CSV batch only |
| Raw CSV rows sent to external API | Confidentiality requirement |
| Prescriptive business decisions ("you should fire X") | Agent surfaces risks/opportunities, human decides |
| Multiple forecast model selection UI | Over-engineered for this use case |
| False-precision probability statements | Use ranges and confidence labels, not fake decimals |

---

## Feature Dependency Chain

```
Date column detection
  └─► Temporal signal extraction (trend slope, period deltas)
        └─► Trend direction labels
        └─► Period comparison (MoM/YoY)
        └─► Forecast (data-quality gated via adfuller)

Deterministic signals (existing v2)
  └─► LLM Analyst receives signal dict (never raw rows)
        └─► Analyst forms hypotheses + recommends tools
        └─► Analysis tools execute deterministically
              └─► Insights generated
                    └─► Critic validates claims vs signals
                          ├─► Approved → add to ranked report
                          └─► Rejected → force Analyst rewrite (Ralph Loop)

Ranked report (all approved insights)
  └─► Output review loop (Ralph Loop checkpoint 2)
        └─► Final report.md + plots
```

---

## MVP Priority Order

1. LLM Analyst strategy driver (column selection + hypothesis)
2. Critic agent with Pydantic schema validation
3. Ralph Loop at investigation checkpoint
4. Trend direction detection (statsmodels)
5. Period comparison (MoM/YoY)
6. Ranked insights report with business labels
7. Forecasting with uncertainty ranges
8. Ralph Loop at output review checkpoint
9. Multi-angle analysis synthesis

---

## What Business Analysts Expect

1. **Plain language** — no statistical jargon without explanation
2. **Prioritization** — tell me what to look at first
3. **Confidence signals** — distinguish strong findings from weak ones
4. **Actionability** — findings should connect to decisions, not just describe data
5. **Trust** — every number must trace back to the actual data, not AI invention

# Phase 06: Global Synthesizer + Output Review — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 06-global-synthesizer-output-review
**Areas discussed:** Synthesizer ranking, Report structure, Multi-angle enforcement

---

## Synthesizer Ranking

| Option | Description | Selected |
|--------|-------------|----------|
| Pure risk score | Use state["risk_scores"] — deterministic, already computed, no new logic | ✓ |
| Analyst-weighted hybrid | Combine risk_score with business_label multiplier | |
| Label-first, then risk score | Group by label (risk > anomaly > opportunity > trend), rank within group | |

**User's choice:** Pure risk score (recommended default)
**Notes:** Simple and reliable — risk scores already computed by risk_planner.py.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Include with 'not analyzed' note | All columns appear; unanalyzed get "Below risk threshold" note | ✓ |
| Analyzed columns only | Drop unanalyzed columns from report entirely | |

**User's choice:** Include with note
**Notes:** Full coverage visible — nothing silently dropped.

---

## Report Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Replace generate_report() | Rewrite in-place; main.py unchanged | ✓ |
| Add new alongside | Keep v2 function, add synthesizer_report() in parallel | |
| Replace call in main.py only | Preserve function, route main.py to new synthesizer | |

**User's choice:** Replace generate_report() (recommended)
**Notes:** No wiring changes to main.py needed.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Structured paragraph | Business label + summary + key signals + narrative (~5-8 lines per column) | ✓ |
| One-liner | Terse format — fast scan, low density | |
| Full narrative | Full AnalystDecision narrative verbatim — verbose | |

**User's choice:** Structured paragraph (recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Ranked findings + temporal (3 sections) | Executive Summary + Ranked Findings + Temporal Analysis | ✓ (modified) |
| Keep v2 sections + add findings | Prepend findings to existing v2 sections | |
| Minimal: findings only | Just ranked findings list | |

**User's choice:** Ranked findings + temporal — with modification
**User's notes:** "In each section, adding the visualization for the content of this section directly instead of putting all visualizations at the end of the report like version 2. For visualizations, write caption to capture the figure meaning."

Decision captured as: inline visualizations with descriptive captions, placed in the section they belong to (not batched at end).

---

| Option | Description | Selected |
|--------|-------------|----------|
| Relative path reference | Standard Markdown ![caption](path) | ✓ |
| Base64 inline | Embed PNG bytes as data URI | |
| Path only, no image syntax | Code block with path | |

**User's choice:** Relative Markdown path (recommended)

---

## Multi-Angle Enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Trust Phase 5, verify in synthesizer | Check analysis_results[column] count; flag if < 2 with inline note | ✓ |
| Trust Phase 5, no check | No verification — trust Phase 5 execution quality | |
| Synthesizer re-runs tools if only 1 angle | Add df dependency to synthesizer for gap-filling | |

**User's choice:** Trust Phase 5, verify in synthesizer (recommended)
**Notes:** No re-investigation; synthesizer stays df-free. Column with 1 tool result gets: "⚠ Single analytical angle — distribution analysis only"

---

## Claude's Discretion

- Gate 2 generator_fn design (deterministic re-sort, not discussed explicitly) — decided
  as D-07: deterministic findings list fed to quality_bar_critic(), LLM narrative runs after
- Exact caption format for inline visualizations — Claude decides per figure

## Deferred Ideas

None surfaced during discussion.

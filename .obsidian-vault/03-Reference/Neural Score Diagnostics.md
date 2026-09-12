---
tags:
  - concept
  - diagnostics
  - neural-score
created: 2026-08-28
---

# Neural Score Diagnostics

> 7-dimension self-diagnostic — the brain checks its own health.

---

## Dimensions

| Dimension | Weight | What It Measures |
|---|---|---|
| Exploration Efficiency | 15% | Diversity of recommendations (entropy) |
| Reward Convergence | 20% | Is average reward trending up? |
| Context Sensitivity | 15% | Do different students get different recs? |
| Recommendation Precision | 20% | Fraction of positive rewards |
| Grade Prediction | 10% | Accuracy of predicted vs actual grades |
| Cohort Purity | 10% | Balance of student cluster sizes |
| Objective Balance | 10% | Variance of reward signals |

**Each dimension scored 0-10.**

## How To Interpret

- **Dropping score** = signal worth investigating, not just a number
- [[David — QA/Testing]] and [[Alice — Documentation]] should treat drops as alerts

## Example Output

```
Exploration Efficiency  →  8.3/10
Reward Convergence      →  7.1/10
Context Sensitivity     →  6.8/10
Recommendation Precision→  7.5/10
Grade Prediction        →  6.2/10
Cohort Purity           →  7.0/10
Objective Balance       →  7.5/10
─────────────────────────────────
NEURAL SCORE            →  7.2/10
```

## Owner

[[Sam — AI/ML Engineer]]

---

*Source: SAM_TECHNICAL_HANDOFF.md*

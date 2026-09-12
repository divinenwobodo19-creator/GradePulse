---
tags:
  - concept
  - reward
  - anti-gaming
created: 2026-08-28
---

# Anti-Gaming Reward Shaping

> Prevents students from exploiting the system by intentionally scoring low.

---

## How It Works

Improvement reward is scaled by `current_performance`:

```python
performance_factor = max(0.1, current_performance)
imp_signal = clip(improvement * 5.0 * performance_factor, -1.0, 1.0)
```

## Effect

| Scenario | Improvement | Performance Factor | imp_signal |
|---|---|---|---|
| Low student improves | 0.4 | 0.1 | 0.2 (low reward) |
| High student improves | 0.3 | 0.6 | 0.9 (high reward) |

**Gaming the system by scoring low first yields minimal improvement reward.**

## Files

- `brain.py` — `calculate_multi_objective_reward()`
- `core/reward.py` — `calculate_reward()`

## Owner

[[Sam — AI/ML Engineer]]

---

*Source: SAM_TECHNICAL_HANDOFF.md*

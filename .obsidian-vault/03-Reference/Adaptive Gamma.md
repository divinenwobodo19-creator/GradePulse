---
tags:
  - concept
  - adaptive-gamma
  - non-stationarity
created: 2026-08-28
---

# Adaptive Gamma

> Auto-adjusts discount factor when reward variance spikes.

---

## Mechanism

1. Tracks a rolling window of **50 recent rewards**
2. Every **25 updates**, compares variance between first and second half of window
3. If variance spikes (>40% increase or >0.35 absolute):
   - Gamma **decreases** by 0.03, floor at 0.85
4. When variance normalizes:
   - Gamma **creeps back** toward baseline at 0.005 per cycle
5. LinUCB model gamma synced in real-time

## Use Cases

- Exam weeks
- Seasonal shifts
- Curriculum changes

## Test Coverage

6 tests in `test_adaptive_gamma.py`

## Known Issue

- [[Decision Log#Flaky test|Flaky test]] in restore assertion (gamma 0.91 vs expected ≥ 0.94)

## Owner

[[Sam — AI/ML Engineer]]

---

*Source: SAM_TECHNICAL_HANDOFF.md*

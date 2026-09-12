---
tags:
  - concept
  - algorithm
  - linucb
created: 2026-08-28
---

# LinUCB Algorithm

> Linear Upper Confidence Bound — the core recommendation algorithm.

---

## Two Variants

| Variant | File | Key Feature |
|---|---|---|
| Disjoint | `linucb.py` | Per-arm independent matrices |
| Hybrid | `linucb_hybrid.py` | Shared + arm-specific + cluster parameters |

## How It Works

1. **Context vector** ([[Context Vector — 17 Dimensions]]) describes student + content
2. **Per-arm matrices** track which content works for which student profiles
3. **Confidence bound** balances exploration (try new things) vs exploitation (use what works)
4. **Sherman-Morrison updates** — O(d²) not O(d³), computationally efficient
5. **Discounted LinUCB** — handles non-stationary environments

## Adaptive Gamma

See [[Adaptive Gamma]] — auto-adjusts discount factor when reward variance spikes.

## Anti-Gaming

See [[Anti-Gaming Reward Shaping]] — prevents students from exploiting the system.

## Multi-Worker Safety

See [[Multi-Worker Sync]] — `sync.py` with file-based locking.

## Owner

[[Sam — AI/ML Engineer]]

---

*Source: SAM_TECHNICAL_HANDOFF.md*

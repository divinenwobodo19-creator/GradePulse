---
tags:
  - role
  - team
  - sam
created: 2026-08-28
---

# Sam — AI/ML Engineer

> Core algorithms, reward design, REST API, diagnostics, test suite.

---

## Scope

| Area | Detail |
|---|---|
| Core algorithms | [[LinUCB Algorithm]] Disjoint & Hybrid |
| Reward design | [[Anti-Gaming Reward Shaping]], multi-objective |
| Diagnostics | [[Neural Score Diagnostics]] (7 dimensions) |
| REST API | [[API Endpoints — 16]] with JWT auth |
| Test suite | 73 tests, all passing |
| Context vector | [[Context Vector — 17 Dimensions]] |
| Persistence | JSON save/load, [[Multi-Worker Sync]] |

## Out of Scope

- UI/UX → [[Mia — UI/UX Designer]]
- Deployment → [[Ali — Infrastructure]]
- Data ingestion → [[Bob — Data Engineer]]
- Product decisions → [[Divine — Founder]]

## Key Files

- `linucb_brain/core/linucb.py` — LinUCB Disjoint
- `linucb_brain/core/linucb_hybrid.py` — LinUCB Hybrid
- `linucb_brain/brain.py` — Main Brain class
- `linucb_brain/api/app.py` — FastAPI app
- `tests/` — Full test suite

## Open Items

- [[Decision Log#Flaky test|Flaky test]] in `test_adaptive_gamma.py` (restore assertion)
- [[Decision Log#Topic normalization|Topic normalization]] — uppercase topics, confirm model compatibility
- Update `SAM_TECHNICAL_HANDOFF.md` Section 2.7 per-file test counts

## Reference

- [[Sam's Technical Handoff]]
- [[GradePulse Architecture]]

---

*Source: SAM_TECHNICAL_HANDOFF.md, TEAM_HANDBOOK.md*

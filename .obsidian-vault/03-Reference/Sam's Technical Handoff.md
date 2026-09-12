---
tags:
  - reference
  - technical-handoff
created: 2026-08-28
---

# Sam's Technical Handoff

> Full technical architecture reference. Read before every session.

---

## What's In It

- [[LinUCB Algorithm]] — Disjoint & Hybrid implementation
- [[Context Vector — 17 Dimensions]] — input contract
- [[Neural Score Diagnostics]] — 7-dimension health check
- [[Anti-Gaming Reward Shaping]] — reward function
- [[Adaptive Gamma]] — non-stationarity detection
- [[API Endpoints — 16]] — all endpoints with auth
- [[Multi-Tenant Data Model]] — School → SchoolClass → Student
- Test suite breakdown (73 tests)
- File reference and directory structure

## Source File

`Team Handbooks/SAM_TECHNICAL_HANDOFF.md`

## Known Stale Sections

- Section 2.7: Per-file test counts are outdated
  - `test_api.py`: documented 18, actual 25
  - `test_multi_school.py`: documented 8, actual 9
  - `test_sync.py`: not documented (8 tests added by [[Ali — Infrastructure]])

---

*Source: SAM_TECHNICAL_HANDOFF.md*

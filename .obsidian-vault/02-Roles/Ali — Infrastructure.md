---
tags:
  - role
  - team
  - ali
  - infrastructure
created: 2026-08-28
---

# Ali — Infrastructure

> Deployment, scaling, multi-worker sync, production storage.

---

## Scope

| Area | Detail |
|---|---|
| Deployment | FastAPI service, uvicorn config |
| Multi-worker sync | [[Multi-Worker Sync]] — RESOLVED via `sync.py` |
| Scaling | Worker count, auto-save intervals |
| SQLite migration | Planned v0.2 P2 — do not start early |
| Production storage | Backups, environment config |

## Out of Scope

- API endpoint design → [[Sam — AI/ML Engineer]]
- Algorithm/model code → [[Sam — AI/ML Engineer]]
- UI/UX → [[Mia — UI/UX Designer]]
- Data ingestion → [[Bob — Data Engineer]]

## Key Files

- `linucb_brain/sync.py` — BrainSynchronizer
- `linucb_brain/api/app.py` — FastAPI app (modified lifespan)

## Completed

- **P0: Single-worker constraint resolved** — `sync.py` with file-based locking (`fcntl`), periodic auto-save (30s, configurable via `AUTO_SAVE_INTERVAL`), independent disk load per worker
- Added 8 tests in `test_sync.py`

## Reference

- [[GradePulse Architecture]]
- [[Decision Log]]

---

*Source: TEAM_HANDBOOK.md, infra-engineer.md*

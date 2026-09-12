---
tags:
  - concept
  - api
  - endpoints
created: 2026-08-28
---

# API Endpoints — 16

> FastAPI REST API with JWT auth. Contract belongs to [[Sam — AI/ML Engineer]].

---

## Endpoints

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/health` | GET | No | Health check |
| `/auth/signup` | POST | No | Create account |
| `/auth/login` | POST | No | Get JWT token |
| `/auth/me` | GET | Yes | Current user info |
| `/schools` | GET/POST | Yes | List/create schools |
| `/schools/{id}/classes` | GET/POST | Yes | List/create classes |
| `/schools/{id}/classes/{cid}/students` | GET/POST/PUT/DELETE | Yes | CRUD students |
| `/schools/{id}/classes/{cid}/content` | GET/POST | Yes | CRUD content |
| `/recommend` | POST | Yes | Get recommendations |
| `/update` | POST | Yes | Submit reward signal |
| `/bulk-update` | POST | Yes | Submit class scores |
| `/triage/{subject}` | GET | Yes | Student triage by subject |
| `/summary` | GET | Yes | Brain state summary |
| `/neural-score` | GET | Yes | Run diagnostics |
| `/save` | POST | Yes | Persist brain state |
| `/reward/calculate` | POST | Yes | Calculate reward from scores |

## Auth

All protected endpoints require `Authorization: Bearer <token>` header.

## Contract Rules

- All agents treat these as **fixed** unless [[Sam — AI/ML Engineer]] changes them
- Breaking changes must be flagged in [[Decision Log]]
- [[Alice — Documentation]] documents changes only **after** they're made

## Files

- `linucb_brain/api/app.py` — FastAPI application
- `linucb_brain/api/schemas.py` — Pydantic models
- `linucb_brain/api/auth.py` — JWT authentication

## Owner

[[Sam — AI/ML Engineer]]

---

*Source: SAM_TECHNICAL_HANDOFF.md*

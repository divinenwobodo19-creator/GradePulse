---
tags:
  - reference
  - team-handbook
created: 2026-08-28
---

# Team Handbook Summary

> Condensed version of `TEAM_HANDBOOK.md` for quick reference.

---

## Team

| Role | Agent | Key Deliverable |
|---|---|---|
| Founder | [[Divine — Founder]] | Vision, decisions |
| AI/ML | [[Sam — AI/ML Engineer]] | LinUCB, API, tests |
| UI/UX | [[Mia — UI/UX Designer]] | Teacher portal, Next.js |
| Infra | [[Ali — Infrastructure]] | Deployment, sync |
| Data | [[Bob — Data Engineer]] | Ingestion pipeline |
| QA | [[David — QA/Testing]] | Load/messy testing |
| Docs | [[Alice — Documentation]] | PROJECT_INDEX, README |

## Critical Constraints

| Constraint | Owner | Status |
|---|---|---|
| Single-worker | [[Ali — Infrastructure]] | RESOLVED |
| JSON ceiling (~50 students) | [[Ali — Infrastructure]] | P2 in v0.2 |
| 65-test baseline | [[David — QA/Testing]] | Extend, never duplicate |
| 17-dim context vector | [[Bob — Data Engineer]] | Fixed contract |
| API contract (16 endpoints) | [[Sam — AI/ML Engineer]] | Frozen |

## v0.2 Roadmap

| Feature | Priority |
|---|---|
| Thompson Sampling cold-start | P0 |
| `/group_recommendations` | P1 |
| Context diversity regularization | P1 |
| SQLite migration | P2 |
| Off-policy evaluation | P2 |

---

*Source: TEAM_HANDBOOK.md*

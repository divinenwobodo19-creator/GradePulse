# GradePulse — Project Index

Codebase navigation map. Each section maps to an owner role.

> **Ownership note (2026-09-27):** All original role-agents (Sam, Mia, Ali, Bob, David, Alice) were AI models and have been **scrapped by Divine**. The **Backend Engineer (opencode session)** is now the sole engineering agent and owns everything backend-related: engine, API, auth, storage/sync/backup, ingestion, infra config, QA/testing, and tech docs. Frontend (`gradepulse-web/`) has no agent; it ships as-is and its API contract is maintained backend-side. Owners below are updated to match (Unassigned = no agent).

---

## Root-Level Files

| File | Purpose | Owner |
|---|---|---|
| `README.md` | Quick start, project structure, API examples | Backend Engineer |
| `PROJECT_INDEX.md` | This file — codebase navigation | Backend Engineer |
| `CHANGELOG.md` | Release notes | Backend Engineer |
| `RELEASE_CHECKLIST.md` | Pre-release verification steps | Backend Engineer |
| `API_REFERENCE.md` | All documented endpoints with request/response examples | Backend Engineer |
| `DEPLOYMENT.md` | Production deployment runbook | Backend Engineer |
| `requirements.txt` | Python dependencies | Backend Engineer |
| `pyproject.toml` | Project metadata | Backend Engineer |
| `teacher_portal.py` | Streamlit teacher dashboard | Unassigned (legacy) |
| `generate_offline.py` | Offline HTML tool generator | Unassigned (legacy) |
| `offline_teacher.html` | Generated standalone tool | Unassigned (legacy) |
| `brain_state.json` | Model persistence (LinUCB state) | Backend Engineer |
| `class_config.json` | School/class registry | Backend Engineer |
| `gradepulse_users.db` | SQLite user accounts (JWT auth) | Backend Engineer |
| `ingest.py` | Data ingestion CLI (CSV/Excel → 17-dim vector) | Backend Engineer |
| `generate_pilot_data.py` | Generate pilot-grade validation datasets | Backend Engineer |
| `sample_data/` | Sample pilot-school data | Backend Engineer |
| `sample_data/large/` | Large sample dataset | Backend Engineer |
| `sample_data/pilot_grade/` | Pilot-grade validation data (edge cases) | Backend Engineer |
| `.env.example` | Production configuration variables | Backend Engineer |
| `Consolidated QA Audit Report.md` | Consolidated QA findings across all modules | Backend Engineer |
| `QA AUDIT REPORT.md` | QA audit report | Backend Engineer |
| `INVESTOR_CHECKLIST.md` | Investor due diligence checklist | Divine |
| `Model Specifications.md` | Model technical specifications | Backend Engineer |
| `backups/` | Automated brain state backups (rotated, timestamped) | Backend Engineer |
| `Dockerfile` | Multi-stage Docker build (backend + frontend targets) | Backend Engineer |
| `docker-compose.yml` | Docker Compose orchestration (API + web services, volumes) | Backend Engineer |
| `.dockerignore` | Excludes dev/test files from Docker build context | Backend Engineer |
| `DEPLOYMENT.md` | Production deployment runbook (VPS, HTTPS, backup/restore) | Backend Engineer |

---

## `.github/workflows/` — CI/CD

| File | Purpose | Owner |
|---|---|---|
| `ci.yml` | Test on push/PR to main (Python 3.12, pip cache, pytest) | Backend Engineer |
| `docker.yml` | Build + push Docker images to GHCR on version tags | Backend Engineer |

---

## `linucb_brain/` — Core Engine (Backend Engineer)

### `linucb_brain/core/` — Algorithms

| File | Purpose |
|---|---|
| `linucb.py` | LinUCB Disjoint — per-arm matrices, Sherman-Morrison O(d²) updates |
| `linucb_hybrid.py` | LinUCB Hybrid — shared + arm-specific + cluster parameters |
| `clustering.py` | MiniBatchKMeans online clustering, SHA-256 cold-start |
| `context.py` | 17-dim context vector builder (8 student + 9 content features) |
| `reward.py` | Standalone reward calculator with anti-gaming scaling |

### `linucb_brain/models/` — Data Models

| File | Purpose |
|---|---|
| `student.py` | Student data model |
| `content.py` | Content item data model |
| `session.py` | Session/interaction data model |
| `school.py` | School/class hierarchy model |

### `linucb_brain/diagnostics/` — Health Checks

| File | Purpose |
|---|---|
| `neural_score.py` | 7-dimension self-diagnostic engine |
| `report.py` | Report renderer |

### `linucb_brain/api/` — REST API

| File | Purpose |
|---|---|
| `app.py` | FastAPI application (8 endpoints — auth, schools, classes, students, backup routes missing, see Decision Log) |
| `schemas.py` | Pydantic request/response models |
| `auth.py` | JWT authentication |

### Other

| File | Purpose |
|---|---|
| `brain.py` | Main Brain class — single public interface |
| `storage.py` | JSON save/load |
| `sync.py` | Multi-worker brain state synchronization (file-based locking, auto-save) |
| `backup.py` | Automated backup system (rotation, atomic writes, metadata tracking) |
| `registry.py` | School/class registry |
| `utils.py` | Utilities |

---

## `tests/` — Test Suite (Backend Engineer)

> Per-file counters below are informational and drift as tests evolve; the canonical number is what CI/`pytest` reports. **Latest verified (2026-09-27, after Phase 2): 352 total — 315 offline-file tests + 37 live tests** (backup-api, ingest-api, load) against a real `:8000` server.

| File | Tests | Coverage |
|---|---|---|
| `test_adaptive_gamma.py` | 6 | Gamma adaptation, variance detection, floor, restore, sync |
| `test_anti_gaming.py` | 7 | Anti-gaming scaling, gaming scenario, churn |
| `test_api.py` | 25 | All API endpoints, auth, CRUD |
| `test_brain.py` | 4 | Student/content add, recommend, update, save/load |
| `test_hybrid.py` | 7 | Hybrid model init, recommend, save/load, cluster state |
| `test_integration.py` | 1 | Full pipeline end-to-end |
| `test_linucb.py` | 3 | Arm selection, matrix updates, alpha=0 |
| `test_multi_school.py` | 9 | Triage, multi-tenant, legacy migration |
| `test_neural_score.py` | 3 | Score ranges, weighted calculation, report |
| `test_sync.py` | 20 | BrainSynchronizer, file locking, auto-save, edge cases, concurrent |
| `test_backup.py` | 10 | BackupManager, rotation, restore, metadata |
| `test_load.py` | 7 | Concurrent API load tests (require running server) |
| `test_ingest.py` | 60 | CSV readers, validators, grade parsing, student/content ingestion |
| `test_backup_api.py` | 17 | Backup API endpoints: create, list, restore, auth, integration |
| `test_security.py` | 11 | Phase 2: school-isolation 403s, JWT claims, rate limiting, fail-fast secret |
| **Total (latest verified)** | **352** | **315 offline + 37 live on :8000** |

---

## `gradepulse-web/` — Next.js Frontend (Unassigned — ships as-is)

### All Pages Complete (15/15)

| File | Purpose |
|---|---|
| `src/app/layout.tsx` | Root layout with AuthProvider |
| `src/app/page.tsx` | Root redirect (authenticated → dashboard) |
| `src/app/globals.css` | Design system tokens, component classes |
| `src/app/(auth)/login/page.tsx` | Branded split-panel login |
| `src/app/(auth)/signup/page.tsx` | Branded split-panel signup |
| `src/app/(dashboard)/layout.tsx` | Sidebar navigation, user profile |
| `src/app/(dashboard)/dashboard/page.tsx` | Main dashboard (metrics + triage breakdown + student table) |
| `src/app/(dashboard)/students/page.tsx` | Student management (CRUD + filters) |
| `src/app/(dashboard)/scores/page.tsx` | Score entry (bulk + prefill) |
| `src/app/(dashboard)/triage/page.tsx` | Student triage (run + tier cards) |
| `src/app/(dashboard)/progress/page.tsx` | Progress tracking (detail + recommendations) |
| `src/app/(dashboard)/settings/page.tsx` | Settings (account + system + sign-out) |
| `src/lib/types.ts` | Full TypeScript type definitions |
| `src/lib/api.ts` | Typed API client with JWT management |
| `src/lib/auth.tsx` | React context auth provider |

---

## `assets/` — Branding

| File | Purpose |
|---|---|
| `logo.png` | GradePulse logo |

---

## `Team Handbooks/` — Agent Coordination

> All former role-agents were scrapped 2026-09-27; files below are **archived reference** (authored by removed agents) or maintained by Divine/Backend Engineer.

| File | Purpose | Maintainer |
|---|---|---|
| `TEAM_HANDBOOK.md` | Master source of truth — roles, rules, Decision Log | Divine |
| `SAM_TECHNICAL_HANDOFF.md` | Full technical architecture | Reference (archived) |
| `SAM_UNDERSTANDING.md` | Sam's role declaration | Reference (archived) |
| `MIA_ENGINEERING_PROFILE.md` | Mia's engineering profile | Reference (archived) |
| `MIA_UNDERSTANDING_AND_ROLE.md` | Mia's role declaration | Reference (archived) |
| `docs-writer.md` | Former Documentation role scope | Reference (archived) |
| `data-engineer.md` | Former Data Engineer role scope | Reference (archived) |
| `infra-engineer.md` | Former Infra/DevOps role scope | Reference (archived) |
| `qa-tester.md` | Former QA/Testing role scope | Reference (archived) |

---

*Last updated: 2026-09-27 by Backend Engineer (opencode) — sole-agent restructuring; Owner column updated; verified test count 352*

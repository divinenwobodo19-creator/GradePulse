# GradePulse — Project Index

Codebase navigation map. Each section maps to an owner role.

---

## Root-Level Files

| File | Purpose | Owner |
|---|---|---|
| `README.md` | Quick start, project structure, results | Documentation |
| `PROJECT_INDEX.md` | This file — codebase navigation | Documentation |
| `requirements.txt` | Python dependencies | Sam / Infra |
| `pyproject.toml` | Project metadata | Sam |
| `teacher_portal.py` | Streamlit teacher dashboard | Mia |
| `generate_offline.py` | Offline HTML tool generator | Mia |
| `offline_teacher.html` | Generated standalone tool | Mia |
| `brain_state.json` | Model persistence (LinUCB state) | Sam |
| `class_config.json` | School/class registry | Sam |
| `gradepulse_users.db` | SQLite user accounts (JWT auth) | Sam |
| `ingest.py` | Data ingestion CLI (CSV/Excel → 17-dim vector) | Data Engineer |
| `generate_pilot_data.py` | Generate pilot-grade validation datasets | Data Engineer |
| `sample_data/` | Sample pilot-school data (5 students, 8 content items) | Data Engineer |
| `sample_data/large/` | Large sample dataset (56 students, 24 content items) | Data Engineer |
| `sample_data/pilot_grade/` | Pilot-grade validation data (edge cases) | Data Engineer |
| `.env.example` | Production configuration variables (backup, sync, env) | Infrastructure |
| `Consolidated QA Audit Report.md` | Consolidated QA findings across all modules | QA |
| `QA AUDIT REPORT.md` | QA audit report | QA |
| `INVESTOR_CHECKLIST.md` | Investor due diligence checklist | Divine |
| `Model Specifications.md` | Model technical specifications | Sam |
| `backups/` | Automated brain state backups (rotated, timestamped) | Infrastructure |

---

## `linucb_brain/` — Core Engine (Sam)

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
| `app.py` | FastAPI application (29 endpoints) |
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

## `tests/` — Test Suite (Sam + Infra)

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
| **Total** | **179** | **172 passed, 7 skipped (load tests require server)** |

---

## `gradepulse-web/` — Next.js Frontend (Mia)

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

## `assets/` — Branding (Mia)

| File | Purpose |
|---|---|
| `logo.png` | GradePulse logo |

---

## `Team Handbooks/` — Agent Coordination

| File | Purpose | Owner |
|---|---|---|
| `TEAM_HANDBOOK.md` | Master source of truth — roles, rules, Decision Log | Divine |
| `SAM_TECHNICAL_HANDOFF.md` | Full technical architecture | Sam |
| `SAM_UNDERSTANDING.md` | Sam's role declaration | Sam |
| `MIA_ENGINEERING_PROFILE.md` | Mia's engineering profile | Mia |
| `MIA_UNDERSTANDING_AND_ROLE.md` | Mia's role declaration | Mia |
| `docs-writer.md` | Documentation role scope | Divine |
| `data-engineer.md` | Data Engineer role scope | Divine |
| `infra-engineer.md` | Infrastructure/DevOps role scope | Divine |
| `qa-tester.md` | QA/Testing role scope | Divine |

---

*Last updated: 2026-08-31 by Alice (Documentation) — v5: added generate_pilot_data.py, pilot_grade sample data, corrected API endpoint count to 29*

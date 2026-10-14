# GradePulse — Project Index

File-by-file map of the repository. Product decisions belong to Divine; open engineering work is tracked in GitHub issue #9.

## Root

| File | Purpose |
|---|---|
| `README.md` | What GradePulse does, how to run it, configuration |
| `API_REFERENCE.md` | Every endpoint with request and response examples |
| `DEPLOYMENT.md` | Production runbook: server setup, HTTPS, backups, restores, upgrades |
| `FRONTEND_BACKEND_HANDOFF.md` | API contract notes; every contract change is announced here |
| `CHANGELOG.md` | Release notes |
| `RELEASE_CHECKLIST.md` | Steps before tagging a release |
| `INVESTOR_CHECKLIST.md` | Running a school or investor demo |
| `AGENTS.md` | Coordination rules for the engineering agents |
| `requirements.txt`, `pyproject.toml` | Python dependencies and package metadata (version comes from `linucb_brain/__init__.py`) |
| `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example` | Container build and configuration |
| `ingest.py` | Class list and content import from CSV/Excel; used by `POST /ingest` and runnable as a CLI |
| `generate_pilot_data.py` | Generates the pilot-grade sample datasets in `sample_data/` |
| `teacher_portal.py`, `generate_offline.py`, `offline_teacher.html` | Legacy Streamlit portal and offline HTML tool; not maintained |
| `Model Specifications.md`, `MODEL_SPEC.md` | Recommendation engine specification (historical) |
| `QA AUDIT REPORT.md`, `QA_REPORT.md`, `Consolidated QA Audit Report.md` | Past QA audits (historical) |

Runtime files, never committed: `gradepulse_users.db` (accounts, schools, classes, subjects, students, scores), `brain_state.json` (engine state), `backups/`. `class_config.json` is the old school registry; if present it is copied into the database on first start and not written again.

## `linucb_brain/` — backend

| File | Purpose |
|---|---|
| `__init__.py` | Package exports and `__version__` |
| `api/app.py` | FastAPI application: all HTTP endpoints, startup and shutdown |
| `api/store.py` | SQLite store for schools, classes, subjects, students and dated scores |
| `api/auth.py` | Accounts, roles, invites, password changes and resets, JWT |
| `api/schemas.py` | Request and response models |
| `api/ratelimit.py` | Sliding-window rate limiter for sign-in and sign-up |
| `brain.py` | Recommendation engine entry point |
| `core/linucb.py`, `core/linucb_hybrid.py` | LinUCB disjoint and hybrid models |
| `core/context.py`, `core/clustering.py`, `core/reward.py` | Context features, student clustering, reward shaping |
| `core/triage.py` | WAEC-band tiering shared by the API and the engine |
| `diagnostics/` | Neural Score self-diagnostics (not exposed in the product) |
| `models/` | Student, content, session and school data classes |
| `registry.py` | Old JSON school registry; used by the `ingest.py` CLI and the one-off upgrade |
| `storage.py`, `sync.py` | Engine-state file save/load and file locking |
| `backup.py` | Scheduled and manual backups |

## `gradepulse-web/` — web app (Next.js)

| Path | Purpose |
|---|---|
| `src/app/(auth)/login`, `signup`, `reset-password` | Sign-in, sign-up (with invite codes), password reset |
| `src/app/pricing` | Pricing page |
| `src/app/(dashboard)/layout.tsx` | Sidebar and signed-in shell |
| `src/app/(dashboard)/dashboard` | Tiers and counts per subject and class |
| `src/app/(dashboard)/students` | Roster, add/edit/move students, class list import |
| `src/app/(dashboard)/classes` | Create, rename and delete classes |
| `src/app/(dashboard)/scores` | Score sheet for a test |
| `src/app/(dashboard)/triage` | Tiers for one subject |
| `src/app/(dashboard)/progress` | One student's test history |
| `src/app/(dashboard)/reports` | Printable class summary and student progress sheets |
| `src/app/(dashboard)/settings` | Account, password, subjects, invites, people, sign out |
| `src/components/` | Shared components (class list import dialog, test history) |
| `src/lib/api.ts`, `types.ts`, `auth.tsx` | API client, shared types, signed-in user |
| `src/lib/scores.ts`, `reports.ts`, `subjects.ts` | Score formatting, report calculations, per-school subjects |
| `src/**/__tests__/` | Vitest unit and render tests |

## `deploy/`

| File | Purpose |
|---|---|
| `pilot_schools.json`, `pilot_seed.py` | Two pilot schools with rosters; the script creates them through the API |
| `demo/` | Offline one-laptop demo bundle (`run-demo.sh`, compose file, quick card) |

## `tests/`

Pytest suite. `conftest.py` turns content suggestions on for the engine tests. `test_load.py`, `test_backup_api.py` and `test_ingest_api.py` need a live server (`TEST_API_URL`); the rest run offline. Main files by area:

| Area | Files |
|---|---|
| School isolation, auth, roles | `test_security.py`, `test_roles_invites.py`, `test_passwords.py` |
| Store, scores, reports, subjects | `test_score_store.py` |
| API end to end | `test_api.py`, `test_full_qa.py` |
| Import | `test_ingest.py`, `test_ingest_api.py`, `test_pilot_grade.py` |
| Engine | `test_brain.py`, `test_linucb.py`, `test_hybrid.py`, `test_adaptive_gamma.py`, `test_anti_gaming.py`, `test_neural_score.py`, `test_integration.py`, `test_multi_school.py` |
| Persistence and ops | `test_sync.py`, `test_backup.py`, `test_backup_api.py`, `test_load.py` |

## Other folders

| Folder | Purpose |
|---|---|
| `sample_data/` | Sample rosters and content catalogues used by tests and demos |
| `investor-deck/` | Investor deck (HTML) and screenshots |
| `Team Handbooks/` | Archived role handbooks from the earlier AI role-agents |
| `.obsidian-vault/` | Planning notes |

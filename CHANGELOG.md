# Changelog

All notable changes to GradePulse will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Security

- **Signup no longer joins an existing school by name.** `POST /auth/signup`, `POST /schools` and a first roster `POST /ingest` always create a new school owned by the caller; school names are labels and may repeat. Previously anyone who signed up with an existing school's name (or with no name, landing in the shared `MY SCHOOL`) could read that school's students.
- **`/triage` is scoped before tiering.** The old post-filter never ran, so every school's students were returned; `total_students` and tier `count` now cover only the caller's (and unclaimed) students.
- **`/summary` `student_count` is per school** (was platform-wide).
- **Student IDs are per school.** Two schools can both have an `S001`; another school's student with the same ID can no longer be returned, edited or moved by a roster upload. Acting on an ID that is not in your school returns **404** (`/recommend` keeps **400**) where a foreign student used to return 403.
- **Signup validation:** emails are format-checked and lower-cased, passwords need at least 8 characters (HTTP 422 otherwise). A duplicate email in different letter case now returns 400 instead of a 500.

### Added

- **Student and score store.** Students and scores now live in SQLite (same file as the accounts, so scheduled backups cover them) instead of inside `brain_state.json`. Every score is a dated row with an optional test name; `grade_history` and `performance_score` are derived from those rows. On first start, students already in `brain_state.json` that belong to a school are moved across automatically.
- **`POST /bulk-update` takes a sitting:** optional `assessed_on` (date, today by default) and `label` (e.g. "Week 4 test"). Re-sending the same student, subject, date and label corrects the earlier score instead of adding a second one.
- **`GET /students/{student_id}/scores`** returns a student's dated score records.
- **Roles.** Whoever creates a school at signup is its `admin`; existing accounts become admins. `role` is returned by `/auth/signup`, `/auth/login` and `/auth/me`.
- **Teacher invites.** `POST /invites`, `GET /invites`, `DELETE /invites/{code}` (admin only). An invite is single-use and expires after 7 days; a teacher redeems it with `invite_code` on `POST /auth/signup` and joins that school as a `teacher`. This is now the only way to join a school someone else created.
- **Frontend:** invite code field on signup (prefilled from `/signup?invite=CODE`), and an "Invite a Teacher" section in Settings for admins. Settings shows the real role.

### Changed

- **`performance_score` is calculated**: the mean of the student's five most recent scores. It used to stay at whatever was supplied when the student was created. The supplied value is now only the starting point until a score exists.
- **`/update` rewards are no longer stored as grades.** They train the engine but do not appear in `grade_history` or affect triage.
- **Triage is computed from recorded scores** (same thresholds and response shape).
- **Deleting a student, class or school archives** the students and their scores instead of erasing them; an archived student's ID can be reused.
- **A fresh install starts empty.** The five sample students and eight sample content items are only seeded with `SEED_DEMO_DATA=true`. Students with no school ("unclaimed") no longer exist.
- **Score sheets no longer rewrite the whole engine state** on every save; the engine state is saved by the periodic auto-save.
- **Frontend:** scores, grades and progress show the calculated values, with a dash for students who have no scores yet. Score entry starts blank, shows each student's last score in the chosen subject, and has a test date and optional test name.
- **Backup endpoints are operator-only.** `POST /backup`, `GET /backups` and `POST /backup/restore` now require `X-Operator-Key` matching the new `OPERATOR_KEY` env var, instead of any logged-in user. Unset key = disabled (scheduled backups still run). **Deployments must set `OPERATOR_KEY` to keep using these endpoints.**
- **Admin-only actions:** renaming or deleting a school and deleting a class return 403 for teachers.
- Frontend signup form enforces the same 8-character minimum.

## [0.2.1] - 2026-09-30

### Added

- **Offline demo bundle** (`deploy/demo/`): `docker-compose.demo.yml` + `run-demo.sh` run the published images on one laptop with an isolated data volume, so the school demos work with no internet at the venue. Full-device build target; the two demo images are also pulled straight from GHCR when online.
- **Pilot seed tooling** (`deploy/pilot_seed.py`, `deploy/pilot_schools.json`): creates the two pilot school accounts, ingests their 28-student rosters and the pilot content catalog via `/ingest`, and optionally runs recommend→update rounds so `recommend` is non-cold-start at demo time.

### Changed

- **Rate-limits are now env-tunable** — `RATE_LIMIT_LOGIN_EMAIL` (default 30), `RATE_LIMIT_LOGIN_HOST` (120), `RATE_LIMIT_SIGNUP_HOST` (30). Production defaults are unchanged when the vars are absent; the demo stack opens them for a classroom sharing one public IP.
- **Frontend request timeout is env-tunable** — `NEXT_PUBLIC_GRADEPULSE_API_TIMEOUT_MS` (default `15000`), baked via a new `Dockerfile` build arg. Base behaviour at production defaults is unchanged; the demo build raises it to `30000` for slow school WiFi.

## [0.2.0] - 2026-09-28

### Added

- **Phase 2 security:** school-ownership scoping across all data endpoints (schools, classes, students, recommend, update, bulk-update, triage, ingest); unclaimed students visible to any authenticated user until claimed.
- **JWT hardening:** `iss`/`aud`/`iat`/`jti` claims, future-clock rejection, and production **fail-fast** — the server refuses to boot on a missing/placeholder/weak `JWT_SECRET` when `GRADEPULPE_ENV=production`.
- **Auth rate limiting:** dependency-free sliding-window limiter — login 30/min per host|email + 120/min per host, signup 30/min per host (HTTP 429).
- **`tests/test_security.py`** — 13 security regression tests (cross-school 403s, scoped triage, ingest isolation, token claims, fail-fast).
- **Deployment hardening:** backups now include the user/account DB (SQLite + WAL sidecars); uvicorn honors `HOST`/`PORT`/`WEB_CONCURRENCY`/`LOG_LEVEL`; CI installs `pytest`; updated production runbook.

### Changed

- `/recommend` **always returns a JSON array** (was a bare object at `top_n=1`). Normalised at the HTTP boundary; `Brain.recommend()` unchanged for ML callers.
- Hybrid recommend now delegates every round to the vectorized `select()` path, so `top_n` no longer changes which scoring (recency penalty + noise) applies.
- School/class/student CRUD is server-derived: a request's school is the authenticated user's school; cross-school requests return **403**.
- Runtime state files (`brain_state.json*`, `class_config.json`, `gradepulse_users.db*`, `backups/`) are no longer committed.

### Fixed

- `POST /ingest` returned HTTP 500 (relative import of the top-level `ingest.py` module).
- Signup lost the newly-created school (registry saved from a stale disk copy).
- `FileLock` closures raced under concurrency, letting unsynchronized writers corrupt state.
- Ingest handler's blanket `except Exception` swallowed `HTTPException`s into 500s.
- Pre-existing JWTs (pre-claims) now decode-fail → all users must log in once after upgrading.

## [0.1.0] - 2026-08-31

### Added

#### Core Engine
- LinUCB Disjoint algorithm with Sherman-Morrison O(d²) updates
- LinUCB Hybrid algorithm with shared + arm-specific + cluster parameters
- 17-dim context vector (8 student features + 9 content features)
- Online clustering (MiniBatchKMeans, COBART-style)
- Multi-objective reward calculation with anti-gaming scaling
- Adaptive gamma for non-stationarity detection
- Neural Score diagnostics (7 dimensions, 0-10 scale)

#### REST API (29 Endpoints)
- JWT authentication (signup, login, current user)
- School management (CRUD)
- Class management (CRUD)
- Student management (CRUD)
- Content management
- Recommendation engine
- Score updates (single + bulk)
- Student triage (3 tiers: remediation, on_track, ahead)
- Reward calculation
- Brain state summary and save
- Backup management (create, list, restore)
- Data ingestion (CSV/Excel upload)
- Health check

#### Data Models
- Student profile with grade history and OULAD features
- Content items with difficulty and type
- Session tracking
- School/Class hierarchy (multi-tenant)

#### Infrastructure
- Multi-worker synchronization (file-based locking)
- Automated backup system (rotation, atomic writes)
- Docker containerization (multi-stage build)
- Docker Compose orchestration
- CI/CD pipeline (GitHub Actions)
- Environment configuration (.env.example)

#### Frontend
- Next.js frontend (15 pages)
- Login/Signup (branded split-panel)
- Dashboard (metrics + triage + student table)
- Student management (CRUD + filters)
- Score entry (bulk + prefill)
- Triage (tier cards)
- Progress tracking
- Settings
- Pricing page (Freemium tiers)

#### Tools
- Teacher Portal (Streamlit dashboard)
- Data ingestion CLI (CSV/Excel → 17-dim vector)
- Pilot data generator
- Offline HTML tool generator

#### Testing
- 339 tests (pytest)
- Adaptive gamma tests
- Anti-gaming reward tests
- API endpoint tests
- Brain core tests
- Hybrid model tests
- Multi-school/tenant tests
- LinUCB arm selection tests
- Neural Score tests
- Sync/locking tests
- Backup tests
- Load tests
- Ingestion tests

#### Documentation
- README.md with quick start and API examples
- PROJECT_INDEX.md (codebase navigation)
- DEPLOYMENT.md (production runbook)
- API reference (29 endpoints)
- Team handbooks (6 roles)
- Investor deck

### Deferred to v0.2
- Thompson Sampling cold-start
- `/group_recommendations` endpoint
- Context diversity regularization
- SQLite migration
- Off-policy evaluation (OPE)

---

## Release Notes

### v0.1.0 Highlights

1. **Real-time Personalization**: The Brain learns from every score a teacher enters, recommending the right content for each student.

2. **Production-Ready API**: 29 endpoints with JWT auth, multi-tenant data model, and multi-worker synchronization.

3. **Teacher-Friendly**: Streamlit portal for teachers who aren't technical. Simple score entry, student triage, and progress tracking.

4. **Data Ingestion**: CSV/Excel import with validation against the 17-dim context vector schema.

5. **Self-Diagnostics**: Neural Score measures 7 dimensions of model health, giving visibility into system performance.

6. **Docker Deployment**: One-command production deployment with `docker compose up`.

### Known Limitations

- JSON-based storage (SQLite migration planned for v0.2)
- Single-node deployment (no clustering)
- No off-policy evaluation yet
- No Thompson Sampling (cold-start improvement deferred)

### Upgrade Path

This is the initial release. Future versions will maintain backward compatibility for:
- API request/response formats
- Brain state file format
- Data ingestion CSV/Excel format

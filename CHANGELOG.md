# Changelog

All notable changes to GradePulse will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Billing

- **Paystack payments, per student, per term.** Admins see a Billing page: the school's standing, a "Pay with Paystack" checkout for N students (card, bank transfer, USSD), and past payments. Payments are confirmed when the admin returns from Paystack and by Paystack's signed webhook. Off until `PAYSTACK_SECRET_KEY` and `PRICE_PER_STUDENT_NAIRA` are set. `DEPLOYMENT.md` has the setup.
- **Soft limits.** An unpaid, expired or over-the-limit school keeps full use; its admin sees a reminder bar linking to Billing. Teachers never see it.
- **Pricing page** shows the per-student, per-term price from the server.


### Admins and teachers

- **Teachers see only the classes they teach.** The school admin ticks each teacher's classes in Settings → People (`PUT /members/{user_id}/classes`; `GET /members` lists them). A teacher's students, scores, triage, dashboard counts, progress and reports cover those classes only; a teacher with no classes sees no students. Admins still see the whole school.
- **Admin-only:** deleting students, importing a class list, and creating or renaming classes (deleting classes already was). Teachers add students into one of their classes and cannot move a student out of them.
- The sidebar shows whether the signed-in account is an admin or a teacher, and the dashboard tells a teacher which classes it covers.


### Operations

- **Content and engine-state changes are operator-only.** `POST /content`, content imports (`POST /ingest` with `type=content`) and `POST /save` need `X-Operator-Key`; any school login could change the shared content catalogue before. `deploy/pilot_seed.py` takes `--operator-key` (or `$OPERATOR_KEY`) to load the catalogue and skips it otherwise.
- **`/summary` `total_sessions`** counts the caller's school's recorded scores (it was the engine's platform-wide counter). `content_count` remains the size of the shared catalogue.
- **`TRUST_FORWARDED_FOR`** (default `false`) lets the sign-in rate limits use `X-Forwarded-For` behind a front proxy that overwrites it. Without it, every visitor behind the web app's proxy shares one allowance. `DEPLOYMENT.md` explains when it is safe to turn on.
- **Logging.** The API logs through Python's `logging` at `LOG_LEVEL`, instead of `print`. An unexpected error is logged with its traceback, and the client gets `{"detail": "Internal server error", "error_id": "..."}` so a report can be matched to the log line.
- **One version number.** `linucb_brain.__version__` feeds `pyproject.toml`, the FastAPI app and `/health` (which used to say 1.0.0).
- **`GRADEPULSE_ENV`** is the setting's name; the misspelt `GRADEPULPE_ENV` is still read, with a warning. Config files and docs use the new name.
- **Docs.** README, `PROJECT_INDEX.md` and `INVESTOR_CHECKLIST.md` (now a demo checklist) rewritten to match the product.


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
- **Schools and classes in the database.** They moved from `class_config.json` (rewritten whole, without a lock, on every change) into the same SQLite store as students and scores. An existing `class_config.json` is copied across on first start, keeping IDs; the file is not written to any more. Deleting a class or school archives it, and a deleted class's name can be reused.
- **Per-school subject lists.** `GET /subjects` returns the caller's school's subjects; `PUT /subjects` (admin) replaces the list. New schools start with MATH, ENGLISH, SCIENCE, HISTORY. The frontend's subject pickers use the school's list, and admins edit it in Settings.
- **Test history on the Progress page.** Each student's recorded tests by subject, newest first, with date, test name, score and grade, a small chart against the 40% and 75% lines, and the subject average, remark and latest trend.
- **Content suggestions are off by default.** `POST /recommend` returns 404 unless `RECOMMENDATIONS_ENABLED=true`; `/health` reports `features.recommendations`, and the Progress page hides "Suggest Materials" when it is off. The engine has no content library or feedback to learn from yet, so its suggestions and their "reward" / "recommended N times" figures were not meaningful to teachers.
- **Change password.** `POST /auth/change-password` (current + new password) and a form in Settings. Changing or resetting a password signs out every session started before it; the session that made the change continues on a new token.
- **Password reset without email.** A school admin creates a single-use, 24-hour reset link for a teacher in their school (`GET /members`, `POST /members/{user_id}/password-reset`; "People" in Settings), which the teacher opens at `/reset-password` (`POST /auth/reset-password`). For a locked-out admin, the deployment operator issues the code with `POST /auth/operator-reset` and the `X-Operator-Key` header. Only a hash of each code is stored.
- **Reports** (new sidebar item): a one-page class summary (each student's average and WAEC grade per subject, overall, and the subjects they need help in) and a progress sheet per student for parents (tests taken, latest score with trend, average, grade, remark, signature lines). Both print with the menu and controls hidden; student sheets print one per page. `/reports?view=students` opens on the student sheets.
- **`GET /scores`** returns every recorded score in the caller's school, optionally for one `class_id`.
- **Classes screen** (new sidebar item): add and rename classes, with student counts; admins can delete a class.
- **Edit a student** from the Students page: name, primary subject and class, including moving between classes or out of one. The Add Student dialog also has a class picker, and the table shows each student's class.
- **Import a class list** from the Students page: upload a CSV or Excel file, check it first (nothing is saved), then import. A template can be downloaded from the dialog.
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
- **`PUT /students/{id}` accepts `class_id: ""`** to take a student out of their class.
- **`PUT /classes/{school_id}/{class_id}`** returns 400 for an empty name or one another class in the school already has.
- **`POST /ingest` rejects files over 2 MB** (413).
- **`POST /triage` accepts an optional `class_id`** to limit the report to one class.
- **Frontend cleanup:** the dashboard has subject and class selectors and shows students, assessed, need-help and ahead counts; score entry has a class filter. Engine internals (alpha, gamma, regret, Neural Score, "Save Brain State"), static "Engine Active" badges, invented login-page statistics and "AI / Neural Hybrid" wording are removed. The pricing page is linked from login and signup. Fixed the duplicate Subject label on Triage and the dead "All Schools" filter on Students.
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

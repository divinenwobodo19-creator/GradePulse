# GradePulse — Backend → Frontend Handoff

**For:** The frontend build (`gradepulse-web/`), whoever maintains it. Originally authored for Mia (Frontend / UI/UX), who — with all other role-agents — was **scrapped by Divine on 2026-09-27**. There is no frontend agent; the backend engineer maintains this contract.
**From:** Backend Engineer (opencode) — sole engineering agent, owns all backend per Divine
**Date:** 2026-09-24 · **Status:** Phase 0 COMPLETE → Phase 1 (engine) COMPLETE → Phase 2 (security) COMPLETE

> **Status banner (2026-09-27):** `/recommend` now **always returns a JSON array** (see §8 + `/recommend` row). Class membership (`class_id`/`metadata.class_id`) and the triage payload were resolved end-to-end on 2026-09-27 (class_id + school_id are on every student response). All school/student/class/brain endpoints are now **school-scoped server-side** (Phase 2): cross-school requests → 403, `GET /students` ignores a foreign `school_id` filter, unclaimed students (`school_id: ""`) stay visible to any authenticated user until claimed, signup/login are rate-limited (429), and every user must **re-login once** (old tokens invalidated by `iss`/`aud`/`iat` validation). Backend suite: **352 passed / 0 failed** (315 offline + 37 live on `:8000`).

---

## 1. TL;DR

- Backend (`linucb_brain/api/app.py`) is now **stable and runnable**: 302 tests pass / 0 fail offline, and all 37 live-server tests (load, backup, ingest) pass too.
- Three real bugs were found and **fixed** this sprint: `/ingest` was broken (500), school signup data was being dropped, and the file-lock had a concurrency race that corrupted state under parallel requests.
- The API surface is **unchanged** — no endpoint signatures were touched (Sam's frozen contract is intact). This is a *stabilization*, not a redesign.
- Auth is **JWT + bcrypt** (7-day tokens). All data endpoints require `Authorization: Bearer <token>`.
- Your Next.js app at `gradepulse-web/` already has a working API client (`src/lib/api.ts`) and token store (`src/lib/auth.tsx`). It currently **does not compile** — 4 TypeScript errors block `next build` (details in §8).
- One contract mismatch to resolve with me: **class membership** on students, and the **triage** payload fields.

---

## 2. What I've DONE (Phase 0 — stabilization)

| # | Change | Detail & proof |
|---|---|---|
| 1 | **Fixed `POST /ingest` (HTTP 500)** | `linucb_brain/api/app.py` imported the ingestion functions with `from ...ingest import`, which crashes past the top-level package. Changed to absolute `from ingest import ...` (`ingest.py` is a top-level module; the launch contract is `PYTHONPATH=<project root>`). Verified live: CSV roster upload → `200`, students persisted and visible via `GET /students`. |
| 2 | **Fixed signup losing schools** | `signup` re-read the registry *from disk* before saving (`_save_registry(_get_registry())`), so newly-registered schools vanished. Now the in-memory registry is saved. Verified: signup → school on disk → login resolves the school. |
| 3 | **Fixed file-lock race (data corruption under concurrency)** | `FileLock` in `linucb_brain/sync.py` kept a shared `_lock_fd` on one instance. A blocked thread closed the *holder's* file descriptor mid-write (`OSError: Bad file descriptor`), then writers ran unsynchronized. Fix: per-instance `threading.Lock` (held until release) + per-attempt local fd + `__enter__` raises on acquire timeout. **Load suite: was 4 failed / 509 s → now 7 passed / 21 s.** |
| 4 | **Fixed stale/misconfigured tests** | 4 tests pounded the API without checking the server was up (they failed with connection-refused instead of asserting their 401 behavior) — now they use the `api_ready` fixture. `TestIngestImportBug` was itself asserting the old 500 bug; rewritten to assert success. |
| 5 | **Baseline locked** | Offline: **302 passed / 0 failed / 37 skipped**. With server running, all 37 live tests (load 7 / backup 17 / ingest 13) also pass. |
| 6 | **Logged to team Decision Log** | Entry added to `Team Handbooks/TEAM_HANDBOOK.md`. |
| 7 | **Students now expose `class_id` + `school_id`** | The engine already stored them but the API dropped them (`StudentSchema` omitted the fields). Added to schema + all three handlers (`GET`/`POST`/`PUT /students`); `PUT` keeps `class_id` and `metadata.class_id` in sync. Verified live: create → reclass → list all round-trip correctly. |
| 8 | **Live tests now verify server identity** | A mock API (Mia's `~/gradepulse-demo`) on `:8000` was passing the health-check skip-guard, so live tests ran against it and showered 404s (25 failures). Added `tests/live_api.py` — `api_ready` only passes when `/health` reports `engine: "GradePulse"`. Live suites now skip against the mock and run against the real backend via `TEST_API_URL`. **All 37 live tests green against the real app (29 s).** |
| 9 | **Canonical port + mock neutralization (with Mia)** | Mia confirmed `:8000` is the documented canonical port and moved her demo mock to `:8020`; I restarted the real backend on **`:8000`** (default state) and removed `gradepulse-web/.env.local`. Verified: health reports `engine: "GradePulse"` on `:8000`, mock on `:8020`, all **37 live tests green on `:8000`**. Also made the backup-retention test deterministic (the repo `backups/` dir was already at the 24-capacity rotation cap, so the old `final >= initial + 1` assertion was environment-dependent). |

Files I changed: `linucb_brain/api/app.py`, `linucb_brain/sync.py`, `linucb_brain/api/schemas.py`, `tests/test_ingest_api.py`, `tests/test_backup_api.py`, `tests/test_load.py`, `tests/live_api.py` (+ this doc + Decision Log). Nothing is committed (Divine decides when).

---

## 3. What I'm DOING NEXT (my plan) — and how it affects YOUR contract

| Phase | What | Does it change the API for you? |
|---|---|---|
| **1 (engine correctness)** | Done 2026-09-27: crash-safe persistence, consistent `top_n > 1`, `times_recommended` surfaced, adaptive gamma audited, Neural Score `balance_score` computed. **Includes the `/recommend` always-array change below.** | `/recommend` now **always returns an array** (even `top_n=1`); `[]` = nothing. Your `api.recommend()` normalisation still works unchanged. No other breaking changes. |
| **2 (security)** | **Done 2026-09-27** — school ownership scoping, JWT hardening, rate limiting shipped. | **Watch:** `/students`, `/classes`, `/schools`, `/recommend`, `/update`, `/bulk-update`, `/triage`, `/ingest` are now school-scoped **server-side** (school context comes from the logged-in user, never from query params/body). Cross-school requests → **403**. `GET /students` ignores a foreign `school_id` filter (403 on mismatch). Unclaimed students (`school_id: ""`) remain visible to any authenticated user until claimed. **No contract change**, but re-login is required once (old tokens are invalidated by new `iss`/`aud`/`iat` validation). Signup/login are rate-limited (429 on bursts). |
| **3 (data/scale)** | CSV import/export, pagination on list endpoints. | Additive (query params like `?limit/offset`). |
| **4 (frontend integration)** | Fix the 4 TS errors so `next build` passes; verify every page against the real API. | This is the sprint where we close the loop. |
| **5 (release readiness)** | Demo account seed, docs, env review. | None. |

Deferred to v0.2 (not in MVP): Thompson sampling, group recommendations, context diversity, online policy evaluation.

---

## 4. Running the backend locally (for your dev)

```bash
# from the project root (this is where ingest.py lives)
cd "/home/jazzman/Projects/N - Tech/Projects/GradePulse"

# use the project venv (built with --system-site-packages)
source .venv/bin/activate

# optional state overrides
export BRAIN_STATE_PATH=/tmp/mia/brain_state.json
export CONFIG_PATH=/tmp/mia/class_config.json
export USER_DB_PATH=/tmp/mia/gradepulse_users.db
export BACKUP_DIR=/tmp/mia/backups
export BACKUP_ENABLED=true
export FRONTEND_URL=http://localhost:3000   # CORS allow origin
export JWT_SECRET=some-long-random-secret   # production only; dev has a default

python -m uvicorn linucb_brain.api.app:app --host 0.0.0.0 --port 8000
```

- Interactive docs: `http://localhost:8000/docs` (Swagger).
- Health check: `GET /health`.
- **How the frontend reaches it:** the browser calls same-origin `/api`, and `next.config.ts` rewrites it server-side to `API_URL` (default `http://localhost:8000`). `NEXT_PUBLIC_API_URL` still works as a direct-to-backend escape hatch, but it bypasses the proxy and brings back the CORS dependency — **don't use it for dev**. Set `API_URL` in `gradepulse-web/.env.local` only when you must deviate from `:8000`.

**Env var summary** (all optional — sane defaults exist):

| Env var | Default | Meaning |
|---|---|---|
| `BRAIN_STATE_PATH` | `brain_state.json` | Students + content + model weights (JSON) |
| `CONFIG_PATH` | `class_config.json` | Class/school structure |
| `USER_DB_PATH` | `gradepulse_users.db` | SQLite: users, schools, registry |
| `BACKUP_DIR` | `backups/` | Backup snapshots (enable with `BACKUP_ENABLED`) |
| `BACKUP_ENABLED` | `false` | Auto-backup on writes + exposes `/backup*` endpoints |
| `FRONTEND_URL` | `http://localhost:3000` | CORS allowed origin(s) |
| `JWT_SECRET` | dev default | HS256 signing key. **Phase 2 will fail-fast on the default in prod.** |

---

## 5. Auth

- **Signup:** `POST /auth/signup` `{email, password, school_name?}` → returns user + JWT (`token`).
- **Login:** `POST /auth/login` `{email, password}` → returns user + JWT.
- **Verify:** `GET /auth/me` → current user.
- **Token:** JWT, HS256, **valid 7 days**. Send as `Authorization: Bearer <token>`.
- **Your app already handles this** — `src/lib/api.ts` stores the token in `localStorage["gradepulse_token"]` and attaches the header automatically; `src/lib/auth.tsx` wraps pages.

All routes require the token **except**: `/health`, `/`, and the three `/auth/*` routes.

---

## 6. Full API reference (frozen contract)

> Response shapes below match what the code actually returns today (verified by reading `app.py`, `schemas.py`, `brain.py`). When in doubt, the Swagger docs at `/docs` are authoritative.

### Auth

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/auth/signup` | `{email, password, school_name?}` | `{id, email, school_id, school_name, token}` |
| POST | `/auth/login` | `{email, password}` | `{id, email, school_id, school_name, token}` |
| GET | `/auth/me` | — | `{id, email, school_id, school_name, token}` |

### Schools & classes

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/schools` | — | `[{school_id, name, classes: []}]` |
| POST | `/schools` | `{name}` | `{school_id, name, classes}` |
| PUT | `/schools/{school_id}` | `{name}` | `{school_id, name, classes}` |
| DELETE | `/schools/{school_id}` | — | `{status: "deleted"}` |
| GET | `/classes/{school_id}` | — | `[{class_id, label, grade_level, arm}]` |
| POST | `/classes/{school_id}` | `{label}` | `{class_id, label, grade_level, arm}` |
| PUT | `/classes/{school_id}/{class_id}` | `{label}` | `{class_id, label, grade_level, arm}` |
| DELETE | `/classes/{school_id}/{class_id}` | — | `{status: "deleted"}` |

### Students & content

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/students` | — | `[{student_id, name, class_id, school_id, grade_history, performance_score, current_topic, metadata}]` |
| POST | `/students` | `{student_id, name, grade_history?, performance_score?=0.5, current_topic?, metadata?, class_id?}` | student object (incl. `class_id`, `school_id`) |
| PUT | `/students/{student_id}` | `{name?, current_topic?, class_id?}` (partial) | student object (incl. `class_id`, `school_id`) |
| DELETE | `/students/{student_id}` | — | `{status: "deleted"}` |
| POST | `/content` | `{content_id, title, topic, difficulty(1–5), content_type}` | content object |

`grade_history` is `{topic_name: [scores 0–1]}`. `performance_score` is 0–1.

### Learning engine

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/recommend` | `{student_id, topic?, top_n?=1}` | **Always a JSON array.** `top_n=1` → `[one content object]`; `top_n>1` → `[n objects]`; `[]` = nothing to recommend. Normalised at the backend (2026-09-27) so the shape no longer changes with `top_n`. |
| POST | `/update` | `{student_id, content_id, reward(-1…1)}` | `{status: "success"}` |
| POST | `/bulk-update` | `{entries: [{student_id, subject, score(0…1)}]}` | result object |
| POST | `/triage` | `{subject}` | tiering report (see below) |
| POST | `/calculate-reward` | `{before_score, after_score, completed, time_spent_ratio?=1.0, engaged?=true, churned?=false}` | `{reward}` |
| GET | `/summary` | — | brain summary (see below) |
| POST | `/save` | — | `{status: "saved", path}` |

**`/triage` response** (scores on the Nigerian WAEC 0–1 scale; only students with ≥1 actual score in the subject are tiered):
```json
{
  "subject": "MATH",
  "total_students": 12,
  "tiers": {
    "remediation": { "students": [{"student_id", "name", "predicted_score", "attempts"}], "count": 2, "recommended_difficulty": 1, "note": "Scored below 40% (F9)..." },
    "on_track":    { "students": [...], "count": 8, "recommended_difficulty": 3, "note": "..." },
    "ahead":       { "students": [...], "count": 2, "recommended_difficulty": 5, "note": "..." }
  },
  "scope": "assessed_only"
}
```
Thresholds: remediation `< 0.40` (F9) · on_track `0.40–0.749` (E8–B2) · ahead `>= 0.75` (A1). `predicted_score` is 0–1 (rounded to 2 dp) — **multiply by 100 before displaying or grading** (`scoreToGrade(scoreToPercentage(x))`).

**`/summary` response:**
```json
{
  "student_count": 12, "content_count": 40, "total_sessions": 1234,
  "model_type": "linucb", "current_alpha": 0.2, "current_gamma": 0.9,
  "cumulative_regret": 3.14, "last_neural_score": 82.5
}
```
(`last_neural_score` is a `0.0–100.0`-ish number; the engine may return `0.0` when not yet computed. See TS error #1.)

### Backup & data

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/backup` | — | `{status:"created", path, timestamp, files, size_bytes}` — 503 if `BACKUP_ENABLED` is off |
| GET | `/backups` | — | `{backups: [{path, timestamp, files, size_bytes}], total}` |
| POST | `/backup/restore` | `?backup_path=...` (query string!) | `{status:"restored", backup_path, message}` — server reload required after |
| POST | `/ingest` | **multipart form**: `file` (csv/xlsx/xls), `type` (`students`\|`content`), `school?`, `school_id?`, `dry_run?` | `{status:"success"\|"completed_with_errors", report:{...}}` |

### Misc

| Method | Path | Response |
|---|---|---|
| GET | `/health` | `{status:"alive", engine, version, worker_pid, expected_workers, backup_status, backup_count}` |
| GET | `/` | API info object |

---

## 7. Data model (single source of truth)

- **Students, content, and model weights** live in `brain_state.json` (JSON document). Students are keyed by `student_id`; content by `content_id`.
- **Content object** (as returned by `/recommend`): `content_id, title, topic, difficulty(1–5), content_type(video|quiz|exercise|reading)`. Engine-internals also track `times_recommended`, `times_rewarded`, `avg_reward` — surfaced in Phase 1.
- **Classes/schools** live in `class_config.json` (`{label, grade_level, arm}` per class).
- **Users/school registry** live in SQLite `gradepulse_users.db` (bcrypt password hashes).
- ⚠️ These are **runtime data files** — deliberately not committed to git. A fresh clone starts with a demo seed. **Do not hardcode student/content data in the frontend.**

---

## 8. Frontend integration status — what needs YOUR attention

**Update 2026-09-27 (Phase 1):** `/recommend` now **always returns a JSON array** (your polymorphism ask). `top_n=1` → `[one object]`, `top_n>1` → `[n objects]`, `[]` → nothing to recommend. Normalised backend-side; `api.recommend()` needs no change. `times_recommended` (≥1) is present on every returned item. Verified: 341 tests passed (304 offline + 37 live on :8000) including response-time tests.

**Update 2026-09-24:** Your `types.ts` now matches the real API — `tsc --noEmit` passes (exit 0). Verified against the live backend: triage (`predicted_score`, `recommended_difficulty`, `note`, `scope`), grade units (`scoreToPercent` → `scoreToGrade`), and recommend list/object handling are all correct. The two items below were **resolved today**:

- **Triage fields** — ✅ aligned, you were right. Earlier version of THIS doc had wrong field names; now corrected in §6.
- **`class_id` on students** — ✅ **FIXED BACKEND-SIDE TODAY.** `class_id` + `school_id` are now serialized on every student response (`GET`/`POST`/`PUT /students`), and `PUT` keeps `class_id` and `metadata.class_id` in sync. Your `getStudentClassId()` fallback now actually receives data from the API. Verified live end-to-end (create → reclass → list).

**The 4 TS errors that blocked `next build` earlier — you cleared them; nothing left blocking compile.**

**Remaining smaller notes for you:**
1. `BrainSummary.last_neural_score` — backend always sends a plain `number` (defaults to `0.0`); your type `number | null` is fine but treat `null` defensively in the dashboard health bar.
2. `/recommend` now ALWAYS returns an array (decided on the backend 2026-09-27, as you requested). `top_n=1` → `[obj]`, `top_n>1` → `[obj, ...]`, `[]` → nothing. Your wrapper's normalisation still works; no JS change needed.
3. `subject` is case-sensitive: send **uppercase** (`MATH`, `SCIENCE`, `ENGLISH`, `HISTORY`) to `/triage`, `/update`, `/bulk-update` — the engine normalizes/stores uppercase; lowercase lookups miss.
4. Signup response already returns `token` — you can skip a follow-up login call.

---

## 9. Gotchas & constraints

- **No package-CDN / pip network right now.** Do not try to `pip install` fresh packages; the project venv uses `--system-site-packages` against the global `~/.local` site-packages which already has every pinned dep.
- **Run uvicorn from the project root** (import contract for `ingest.py`). Don't `cd linucb_brain` and run from there.
- Multi-worker safety: the `FileLock` fix makes concurrent reads/writes safe (verified under parallel bulk-update + auto-save load). Background auto-save every Nth write is now non-destructive; `/save` still exists for explicit persistence.
- `brain_state.json` grows with each student/content — expect it to grow to a few MB in a real pilot. Phase 3 addresses scale.
- Backend responses for mutations (`/students`, `/schools`, `/content`, …) return the saved object; `DELETE` returns `{status: "deleted"}`.
- **⚠️ Port map (current).** Real backend = **`:8000`** (engine `GradePulse`, canonical). Demo mock = **`:8020`** (`node mock-api.mjs` at `~/gradepulse-demo`, engine `LinUCB`, no real routes). If you ever see `engine: "LinUCB"` from `:8000`, a mock has squatted the real port. The `api_ready` fixtures verify identity (`/health` must report `engine: "GradePulse"`) so live tests **skip** against the mock instead of silently testing the wrong thing:
  ```bash
  TEST_API_URL=http://localhost:8000 pytest tests/test_backup_api.py tests/test_ingest_api.py tests/test_load.py
  ```

---

## 10. What I need from you

1. **✅ Port question RESOLVED (2026-09-27).** **`:8000` is the canonical backend port** (matches `docker-compose.yml`, Dockerfile healthcheck, `DEPLOYMENT.md`). The real backend now runs on **`:8000`** (engine `GradePulse`); Mia's demo mock moved to **`:8020`**. `gradepulse-web/.env.local` was removed so the built-in `API_URL=http://localhost:8000` default applies. Nothing to do on your side.
2. **Students/classes**: classes are now returned on students too — when you build class filtering, use the top-level `class_id` (it's the single source of truth; `metadata.class_id` is kept in sync by the backend).
3. **A green `next build`** on `gradepulse-web` now that `tsc` passes — that's the Phase 4 gate.
4. Ping me if Swagger (`/docs`) shows anything that disagrees with §6 — the contract is frozen but reality wins for now.

> One process note from the team: log decisions to `Team Handbooks/TEAM_HANDBOOK.md` when a choice affects another role. Scope/ownership decisions (Phase 2) count.
# Release Checklist — v0.2.0 (Production MVP)

Pre-release gate. Every item must be complete before tagging `v0.2.0`. Owners: **Backend Engineer (opencode)** owns all backend/QA/docs/infra items; the Frontend Engineer (other agent) owns the frontend items; Divine signs off.

---

## Backend Engineer (opencode) — Engine, API, Security, Tests

- [x] Core engine green: `python -m pytest tests/test_brain.py tests/test_linucb.py tests/test_hybrid.py tests/test_adaptive_gamma.py -q`
- [x] Neural Score, anti-gaming, sync, backup suites green
- [x] Phase 1 contract frozen: `/recommend` always returns a JSON array; `times_recommended` surfaced
- [x] Phase 2 security: school-ownership scoping, JWT claims, rate limiting, `tests/test_security.py`
- [x] Full suite: **360 passed** — verified locally 28 Sep and green in CI 28 Sep after the fixes below. Note the earlier "exact CI command" claim was not accurate: the CI test job had never run to completion before 28 Sep (missing pytest, then a missing starlette/httpx pin), so 360 had only ever been observed on a dev machine.
- [x] Live suite against a real server on `:8000`: **37 passed**
- [x] Runtime state untracked: `brain_state.json*`, `class_config.json`, `gradepulse_users.db*`, `backups/` gitignored — note `*.csv` was also narrowed 28 Sep so the generated `sample_data/` fixtures are tracked; a fresh clone previously lacked them and ~15 integrity tests failed
- [x] `requirements.txt` fully pinned (no `>=` ranges) — completed 28 Sep: `starlette==1.0.0` and `httpx==0.28.1` were missing entirely, so CI floated to starlette 1.7 and 3 API test files failed to collect. Added both.
- [x] Backups include the user DB (accounts) + WAL sidecars, not just model + registry
- [x] JWT fail-fast verified in the container: production refuses placeholder/weak secrets

## Backend Engineer — Infra / Deploy (was Ali)

- [x] `docker build --target backend` succeeds; image smoke-tested (signup → login → summary in prod mode)
- [x] uvicorn honors `HOST`/`PORT`/`WEB_CONCURRENCY`/`LOG_LEVEL` envs (Dockerfile `CMD` now shell-form)
- [x] Health check passes: `curl http://localhost:8000/health` → `engine:"GradePulse"`
- [x] `.env.example` complete: `GRADEPULPE_ENV`, `JWT_SECRET`, `FRONTEND_URL`, `LOG_LEVEL` documented
- [x] `docker-compose.yml` passes `JWT_SECRET`/`GRADEPULPE_ENV` into the API; default `WEB_CONCURRENCY=1`
- [x] CI `ci.yml` installs `pytest` (test job would otherwise fail); runs `npm run check` for web — first fully green run 28 Sep
- [x] `DEPLOYMENT.md` accurate: correct repo URL, token key (`token`), HTTPS, backups/restore, rollback

## Frontend Engineer (other agent)

- [x] `cd gradepulse-web && npm run check` passes (lint → typecheck → vitest → build) — verified 28 Sep, 27 tests
- [x] Builds against the real API (`API_URL`) — server-side proxy `/api/*`; `docker build --target frontend` succeeds and the container serves `:3000` and reaches `:8000` through the proxy (`engine: "GradePulse"`)
- [x] All pages render; login/signup + dashboards work end-to-end against `:8000` — verified 28 Sep: fresh signup → login, 6/6 routes HTTP 200 with 0 console errors and 0px overflow at 1440 and 768, every proxied `/api` call 200
- [x] Handles 401 (logged out / re-login) and 403/429 gracefully — `ApiError` carries the status (`gradepulse-web/src/lib/api.ts`); 401 re-login, 403 explains the school-link cause, 429 keeps the server wording
- [x] `npm run check` green in CI (`ci.yml` frontend job) — verified 28 Sep (PR #2)

## Divine (Founder)

- [ ] Pricing model confirmed (Freemium: Free ₦0 / Starter ₦5,000/mo / School ₦15,000/mo)
- [ ] Pilot school(s) selected
- [ ] Legal/compliance reviewed (FERPA or equivalent)
- [x] `LICENSE` file committed (repo metadata already says MIT) — MIT text added 28 Sep
- [ ] Investor deck + release announcement prepared

---

## Pre-Release Verification (run exactly like CI)

```bash
# Backend: full offline suite (no server needed)
PYTHONPATH=. python -m pytest tests/ -q --tb=short

# Live suite (needs the API running on :8000)
PYTHONPATH=. python -m pytest tests/test_load.py tests/test_backup_api.py tests/test_ingest_api.py -q

# Production-mode boot check (must refuse weak secrets)
GRADEPULPE_ENV=production JWT_SECRET="short" pip-run uvicorn ...   # expect abort

# Docker
docker build --target backend -t gradepulse-api:test .

# Frontend
cd gradepulse-web && npm run check
```

---

## Release Steps

1. All items above are checked, frontend agent green, Divine approves
2. Bump version in `pyproject.toml` (→ `0.2.0`) and `CHANGELOG.md`
3. Commit: `git commit -m "release: v0.2.0"`
4. Tag + push (triggers GHCR image publish via `docker.yml`):
   ```bash
   git tag v0.2.0
   git push origin main --tags
   ```
5. GitHub Actions builds + pushes `ghcr.io/...-api` and `...-web` images
6. Deploy per `DEPLOYMENT.md` (VPS: clone → `.env` → `docker compose up -d --build` → HTTPS)
7. Announce release
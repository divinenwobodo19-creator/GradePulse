# GradePulse — Agent Coordination

Shared workspace rules so the **Backend Engineer (opencode)** and the **Frontend Engineer (other agent)** never clobber each other.

> **People note (2026-10-02):** Divine owns the product. Agents are the lead engineers. **Dan-BOY72** (GitHub) assists on frontend and other areas but is not an owner — he works under these coordination rules, goes through the same branch-with-PR flow, and the relevant agent keeps directional ownership of each area.

## Agent map

| Side | Owner |
|---|---|
| Product / final say | Divine (human) |
| Backend — everything under `linucb_brain/`, `tests/`, `ingest.py`, Docker/compose, CI, API docs | Backend Engineer (opencode) |
| Frontend — everything under `gradepulse-web/` | Frontend Engineer (other agent) |

## Hard ownership (single-writer — never edit another side's files)

- **Frontend owns:** `gradepulse-web/src/**`, `gradepulse-web/package*.json`, `gradepulse-web/tsconfig.json`, `gradepulse-web/vitest.config.mts`, `gradepulse-web/next.config.ts`, `gradepulse-web/.gitignore`.
- **Backend owns:** `linucb_brain/**`, `tests/**`, `ingest.py`, `generate_pilot_data.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.github/workflows/**`, `.env.example`, `requirements.txt`, `pyproject.toml`, root `*.md` docs, `Team Handbooks/**`.
- **Shared (coordinated):** `FRONTEND_BACKEND_HANDOFF.md` (the API contract — single source of truth), and the frontend API surface files `gradepulse-web/src/lib/api.ts`, `src/lib/types.ts`, `src/lib/auth.tsx`. The backend updates these **in lockstep with a contract change, in the same commit**, and announces it in `TEAM_HANDBOOK.md` Decision Log + the handoff doc **before** merging. If both agents touch one of these files, the frontend agent's version of *client code* wins and the backend's version of *types/endpoints* wins — but ideally one agent files the change first and the other rebases onto it.

## Workflow to avoid merge conflicts

1. **Branch per workstream.** Frontend works on `frontend/<feature>`; backend on `main` (or `backend/<feature>` for big changes). Never work on a branch another agent has open for the same area.
2. **Merge small and often.** Prefer PRs into `main` via GitHub so CI (`ci.yml`) runs; keep merges < a few files where possible.
3. **Rebase/pull before you merge.** If `origin/main` moved (the other agent pushed), `git pull --rebase` onto your branch before merging — do NOT force-push or rebase shared branches.
4. **Contract changes are announced, never silent.** Any endpoint shape change goes through: Decision Log entry + handoff doc update + (if frontend files affected) updated `api.ts`/`types.ts` in the same commit as the backend change.

## Never commit

Runtime state is already in `.gitignore` — do not force-add it: `brain_state.json*`, `class_config.json`, `gradepulse_users.db*`, `backups/`, `.vercel`. Session transcripts (`backend`, `frontend`) are untracked by design.

## Verification

- Backend: `cd "<project root>" && .venv/bin/python -m pytest -q` (offline) — live tests need the server on `:8000` (`tests/test_load.py`, `test_backup_api.py`, `test_ingest_api.py`).
- Frontend: `cd gradepulse-web && npm run check` (lint → typecheck → tests → build).
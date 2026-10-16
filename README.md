# GradePulse

See every week which students are falling behind, in every subject.

Teachers already give weekly tests. GradePulse turns those scores into a weekly picture for each class: who needs extra help, who is on track and who is ahead, on WAEC grade bands (below 40%, 40–74%, 75% and above). Schools get printable class summaries and a progress sheet per student to send home. It is built for Nigerian classrooms of 40–80 students.

The repository also contains a contextual-bandit recommendation engine (LinUCB). It is switched off in the product until schools have a content library and teachers can record whether a suggestion helped; see [Content suggestions](#content-suggestions).

## What a school can do

| Area | What it does |
|---|---|
| **Accounts** | The person who signs up creates the school and is its admin. Teachers join with a single-use invite link from the admin. Each school sees only its own data. |
| **Classes and students** | Create classes; add, edit and move students; import a class list from CSV or Excel (checked before anything is saved). Student IDs are per school. |
| **Subjects** | Each school keeps its own subject list; the admin edits it in Settings. |
| **Scores** | Enter a test for a class in one sheet, with the test date and name. Re-entering the same test corrects it. Every score is kept as a dated record. |
| **Dashboard and triage** | Per subject and class: students assessed, needing help, on track and ahead. |
| **Progress** | Each student's test history by subject, with a chart, average, grade and trend. |
| **Reports** | A one-page class summary, and one progress sheet per student for parents. Both print cleanly. |
| **Billing** | Free for up to 40 students. For the whole school, plus printable reports and parent progress sheets, the admin pays per student, per term, through Paystack. A school's data is never locked away; a lapsed term gets 14 days' grace before falling back to the free plan. |
| **Passwords** | Change password in Settings. There is no email service: a forgotten password is reset with a single-use link from the school admin, or from the operator for a locked-out admin. |

## Running it locally

Needs Python 3.12 and Node 22.

```bash
# API on :8000
pip install -r requirements.txt
PYTHONPATH=. uvicorn linucb_brain.api.app:app --port 8000

# Web app on :3000 (in another terminal)
cd gradepulse-web
npm install
npm run dev
```

Open http://localhost:3000 and sign up; that creates your school. The web app calls the API through its own `/api` proxy, which points at `http://localhost:8000` unless `API_URL` says otherwise.

To fill a fresh instance with the two pilot schools (14 students each):

```bash
python3 deploy/pilot_seed.py --api http://localhost:8000
```

Logins are in `deploy/pilot_schools.json`.

## Running it with Docker

```bash
cp .env.example .env      # set JWT_SECRET; set OPERATOR_KEY if you want the backup endpoints
docker compose up -d --build
curl http://localhost:8000/health
```

The web app is on port 3000. `DEPLOYMENT.md` covers a production server, HTTPS, backups, restores and upgrades. `deploy/demo/` runs the published images on one laptop with no internet (`run-demo.sh prepare`, `start`, `seed`).

## Configuration

API (environment variables; `.env.example` has them all with comments):

| Variable | Default | Purpose |
|---|---|---|
| `GRADEPULSE_ENV` | `development` | `production` refuses to start without a strong `JWT_SECRET`. The old misspelling `GRADEPULPE_ENV` is still read. |
| `JWT_SECRET` | dev placeholder | Signs login tokens. At least 32 random characters in production. |
| `USER_DB_PATH` | `gradepulse_users.db` | SQLite file with accounts, schools, classes, students and scores. The file that matters most. |
| `BRAIN_STATE_PATH` | `brain_state.json` | Recommendation engine state. |
| `FRONTEND_URL` | `http://localhost:3000` | Allowed browser origin (CORS). |
| `OPERATOR_KEY` | empty | Unlocks `/backup`, `/backups`, `/backup/restore` and `/auth/operator-reset`. Empty disables them. |
| `BACKUP_ENABLED`, `BACKUP_DIR`, `BACKUP_INTERVAL`, `BACKUP_MAX_COUNT` | on, `backups/`, 6 h, 24 | Scheduled backups of the data files. |
| `PAYSTACK_SECRET_KEY`, `PRICE_PER_STUDENT_NAIRA`, `TERM_DAYS` | empty, empty, 120 | Online payment through Paystack, per student per term. Off until the key and price are set, and then nothing is limited; see `DEPLOYMENT.md`. |
| `FREE_STUDENTS`, `GRACE_DAYS` | 40, 14 | Students the free plan covers, and days a paid plan lasts after its term ends. |
| `TRUST_FORWARDED_FOR` | `false` | Use `X-Forwarded-For` for sign-in rate limits behind nginx; see `DEPLOYMENT.md`. |
| `RECOMMENDATIONS_ENABLED` | `false` | Turns content suggestions on. |
| `SEED_DEMO_DATA` | `false` | Seeds sample students and content into a brand-new engine state. Demos only. |
| `LOG_LEVEL` | `info` | Application and uvicorn log level. |
| `RATE_LIMIT_LOGIN_EMAIL`, `RATE_LIMIT_LOGIN_HOST`, `RATE_LIMIT_SIGNUP_HOST` | 30, 120, 30 per minute | Sign-in and sign-up throttles. |

Web app: `API_URL` (where the `/api` proxy points, fixed at build time) and `NEXT_PUBLIC_GRADEPULSE_API_TIMEOUT_MS` (request timeout, default 15000).

## Content suggestions

`POST /recommend` serves suggestions from the LinUCB engine in `linucb_brain/`. It returns 404 unless `RECOMMENDATIONS_ENABLED=true`, and the web app hides the feature while it is off. It stays off until there is a per-school content library and a way to record whether a suggestion was used and helped; without those the engine has nothing real to learn from.

## Project layout

```
linucb_brain/
  api/app.py        FastAPI app: every HTTP endpoint
  api/store.py      SQLite store: schools, classes, subjects, students, scores
  api/auth.py       accounts, roles, invites, password resets, JWT
  core/             LinUCB engine, context features, triage tiering
  brain.py          engine entry point
  backup.py, sync.py  scheduled backups; engine-state file locking
ingest.py           class list / content import (CSV, Excel); also a CLI
gradepulse-web/     Next.js web app (src/app = pages, src/lib = API client and helpers)
deploy/             pilot seed data and script, offline demo bundle
tests/              pytest suite
```

## Tests

```bash
PYTHONPATH=. python3 -m pytest tests/ -q       # backend
cd gradepulse-web && npm run check             # frontend: lint, typecheck, tests, build
```

`tests/test_load.py`, `test_backup_api.py` and `test_ingest_api.py` run against a live server at `TEST_API_URL` (default `http://localhost:8000`) and are skipped when none is running. They write data into that server, so point them at a throwaway instance.

## More documentation

- `API_REFERENCE.md`: every endpoint with request and response examples
- `DEPLOYMENT.md`: production runbook
- `FRONTEND_BACKEND_HANDOFF.md`: API contract notes and contract changes
- `CHANGELOG.md`: release notes
- `PROJECT_INDEX.md`: file-by-file map
- Open work is tracked in GitHub issue #9.

## License

MIT

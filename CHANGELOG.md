# Changelog

All notable changes to GradePulse will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Security: the session is an httpOnly cookie (16 November 2026)

From the security assessment of 4 November (L1, token storage).

- **The sign-in token is no longer kept in browser storage.** Sign-up, sign-in and password change set `gp_session`, an httpOnly, Secure (in production), SameSite=Strict cookie that page scripts cannot read, so an injected script could not steal a session. A readable `gp_signed_in` marker tells the web app someone is signed in.
- **Changes made with the cookie need `X-Requested-With: GradePulse`** (403 otherwise), which a page on another site cannot send. Bearer tokens still work for scripts and are not affected.
- **`POST /auth/logout`** removes the cookies. Sign Out calls it.
- **Nobody is signed out by the change:** a token found in the old storage is sent once to `GET /auth/me`, which moves the session into the cookie, and is then deleted.
- `COOKIE_SECURE` (default: on in production) controls the Secure flag.

### Security fixes: invite and reset codes, orphan accounts (16 November 2026)

From the security assessment of 4 November (L9, L10).

- **Invite codes are stored as a hash**, like reset codes. An invite's code is shown once, when it is created; the list shows "Invite ending XXXX" with Revoke. `GET /invites` returns `id` and `hint` with `code: ""`, and `DELETE /invites/{id}` takes the ID. Pending invites from before keep working.
- **Codes stay out of logs and history.** Invite and reset links put the code after `#` (`/signup#invite=…`, `/reset-password#code=…`), which browsers never send to a server, and the pages clear it from the address bar once read. Old `?invite=` and `?code=` links still work.
- **No orphan accounts or schools.** If two people use one invite at once, the loser's new account is removed instead of being left without a school; `POST /schools` is refused (400) for an account that already has a school.

### Data protection (16 November 2026)

From the security assessment of 4 November (H7, M11) and the NDPA review.

- **Deleted records are now deleted.** Students, classes and schools that are deleted stay archived for 14 days (`ARCHIVE_PURGE_DAYS`) so a mistake can be undone, then a daily job removes them for good with their scores and engine state. Before, nothing was ever really deleted, contrary to the privacy page.
- **Audit log:** viewing students or scores, adding, changing or deleting students, entering scores, importing class lists, deleting classes or the school, removing teachers, reset links and exports are recorded with who did it. Entries are kept for 12 months (`AUDIT_KEEP_DAYS`). `GET /audit` (admin) and "Show Recent Activity" in Settings list the school's own.
- **School data export:** `GET /export` (admin) and "Download School Data" in Settings give every class, student and score as CSV files in a .zip, on every plan. Cells that start like a formula are defused for Excel.
- **Privacy page:** names Google Drive (encrypted off-site backups, possibly outside Nigeria), the activity record, the 14-day deletion plus up to 30 days for backups, and the export.

### Security hardening (16 November 2026)

From the security assessment of 4 November (L2, L3, L4, L5, L11, L12, M9).

- **Operator tools are off the public path.** The web app's `/api` proxy answers 404 for backups, restore, save, the content catalogue, pilot terms and operator resets. They are used against the API's local port on the server, so a leaked operator key alone is not enough from the internet.
- **API responses** carry `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` and `Cache-Control: no-store`, so student data is never cached by a browser or Cloudflare. The Docker image starts uvicorn with `--no-server-header`.
- **CORS** trusts `localhost:3000/3001` only outside production, and `FRONTEND_URL` may list several origins separated by commas.
- **`/health`** tells strangers only that the server is alive. Version, process ID and backup details need the operator key.
- **`TRUST_CF_CONNECTING_IP`:** behind a Cloudflare Tunnel, sign-in limits use Cloudflare's visitor address, which a visitor cannot fake.
- **docker-compose** has no default JWT secret (it stops until `.env` sets one), defaults to production, and publishes both ports on `127.0.0.1` only (`WEB_BIND` to change).
- **CI** actions are pinned to commits, and `.github/dependabot.yml` opens weekly update PRs for pip, npm and the actions.

### Security fixes: sign-in (16 November 2026)

From the security assessment of 4 November (M1, M2).

- **Long passwords work.** Passwords over bcrypt's 72-byte limit are hashed with SHA-256 first, so a long passphrase now signs up and every character counts. Before, they caused a 500 error for registered emails and a 401 for unknown ones, which showed who had an account. Existing passwords are unchanged. New passwords can be up to 256 characters.
- **Sign-in takes as long for an unknown email** as for a real one (a dummy password check), so timing no longer reveals accounts.
- **Nobody can lock a school's admin out any more.** Wrong passwords are counted per email and address. The address doing the guessing is slowed and then paused as before, but the owner signing in from their own address gets in with the right password. A password reset clears every pause for the account.

### Removing a teacher (16 November 2026)

- **An admin can remove a teacher who has left** (security assessment M4): **Remove** on the Settings page, People list, or `DELETE /members/{user_id}`. The teacher's account is deleted, so every session they have stops at once and they cannot sign in; they can join again only with a new invite. The scores they entered stay. Admin accounts cannot be removed this way.

### Security fix: late top-ups (16 November 2026)

- **A small top-up can no longer buy a whole term** (security assessment M3). Whether a payment is a top-up or a new term is now decided when Paystack confirms it. A top-up started during a term but confirmed after the term ended used to start a full term for the whole school, so ₦500 unlocked reports. Such a payment is now recorded as `late_top_up` and grants nothing; the server logs it for a refund or credit, and the Billing page tells the admin to get in touch.

### Security fixes: teacher scope and request limits (16 November 2026)

From the security assessment of 4 November (H1, H2, H3, L6, L7).

- **A teacher can no longer read a student outside their classes through `POST /students`.** Sending an ID that already belongs to another class's student used to return that student's record and scores; it now returns **409** "That student ID is already used in your school".
- **Uploads cannot freeze the API.** `/ingest` runs in the worker's thread pool instead of the event loop; files are read row by row (Excel in streaming mode), stop at 5,000 rows (`INGEST_MAX_ROWS`) and 60 columns, `.xlsx` files that unpack to over 40 MB are refused, and 1,000 blank rows in a row end the sheet. Each user may upload 30 files per 10 minutes (`RATE_LIMIT_INGEST_USER`). A 170,000-row file used to stop the API for 84 seconds.
- **Score sheets are capped:** at most 2,000 entries per `POST /bulk-update`, and only the school's own subjects (400 otherwise), so free-text subjects can no longer add items to the shared engine.
- **Request bodies over 512 KB are refused with 413** (uploads: 2 MB plus form overhead).
- **Length limits** on names (120), topics (120), IDs (64), subjects (40), class labels (60), student metadata (4 KB) and `grade_history`; `top_n` on `/recommend` is 1 to 20.
- **Upload errors no longer show internal exception text.** File problems get a plain message (400); anything unexpected is logged with a reference the uploader can quote.

### Safe backups and restore (3 November 2026)

- **Backups copy the database through SQLite** (online backup API) instead of copying the live file, which in WAL mode could miss recent writes or catch a half-written page. No loose `-wal`/`-shm` files are stored any more.
- **Restore is checked and reversible:** only folders inside `BACKUP_DIR` can be restored (by name or path; others 404), every file is checked first (SQLite integrity check, valid JSON) and nothing changes if one fails, and a `pre-restore` backup is taken first.
- **Restore no longer undoes itself:** before, the endpoint saved the running engine over the `brain_state.json` it had just restored. It now reloads the engine from the restored file, and writes the database through SQLite into the live file.

### Weekly triage (3 November 2026)

- **"Who needs help" is now weekly.** Each student is grouped on the average of their last 3 tests in the subject, so an old bad test stops counting and the list follows recent work. Before, every score ever entered was averaged.
- **Change since last week:** `POST /triage` compares with the tests before this week and reports who moved into or out of needs help, who rose or fell 10 points or more, and who scored below 40% on their latest test without being in needs help yet (`watch`). Optional `as_of` gives the report for an earlier day.
- **Dashboard:** "Who needs help this week" with the week's date, how many were tested this week, and three boxes: new in needs help, moved out, and watch. Each student shows their change in points.
- **Triage page:** now the full weekly list with subject and class filters, loaded automatically. The leftover "Run Triage" button, "Recommended Difficulty" panel, raw `assessed_only` badge and "Previous Runs" list are gone, as is "Difficulty: N" on the dashboard.
- "Needs Intervention" is now "Needs Help" everywhere in the app.

### Free pilot terms (3 November 2026)

- **`POST /billing/pilot`** (operator key): gives a school a free pilot term, so a pilot school can add its whole roster and print reports and parent progress sheets without paying. Stored as a ₦0 payment with a `pilot_` reference; it ends like a paid term, with the grace period and then the free plan.
- A payment made during a pilot starts a full term instead of topping up the pilot (which would have ended with it).
- The Billing page shows "Free pilot term" and lists the pilot as "Free pilot" in the payments table. `GET /billing` adds `pilot_until` and a `pilot` flag on each payment.

### Security update (24 October 2026)

- **python-jose replaced by PyJWT 2.15.1** for login tokens. python-jose 3.5.0 has a critical, unpatched advisory (algorithm-confusion guard bypassed by DER-encoded public keys). GradePulse only uses HS256 with a shared secret, but the library has no fix. Existing tokens keep working; forged and unsigned tokens are refused.
- Server packages from Dependabot: starlette 1.0.0 → 1.3.1 and python-multipart 0.0.26 → 0.0.31 (form-parsing denial of service and request-path issues).
- Test-only packages: happy-dom → 21.0.4 and vitest → 5.0.3. `npm audit` reports 0 vulnerabilities.
- GitHub Dependabot alerts and automatic security pull requests are now on for the repository.

### Public site redesign

- **New look for the public pages** (homepage, pricing, calculator, guide, privacy): warm paper background, deep green ink and the brand gold, Source Serif 4 headings over Public Sans text, flat colours, no hover motion, no icons, emoji or dashes in the copy, and no rows of three cards.
- **Fonts across the app:** Geist replaced by Public Sans (text) and IBM Plex Mono (codes); Source Serif 4 for public headings.
- **Homepage:**
  - a real classroom photograph from Lagos (Doug Linstedt, Unsplash licence, credited);
  - the 40 second demo video with captions, loaded only when played;
  - how it works as alternating rows with real screens, including the score sheet;
  - benefits as a two column list;
  - one primary action ("Book a free demo on WhatsApp") at the top and bottom.
- Pricing and privacy use the shared header and footer. The calculator's "✕" buttons now say "Remove".
- Photos, screenshots and the video are cacheable by Cloudflare for a day.

### Security update (23 October 2026)

- **Next.js 16.3.3 → 16.4.3**, for the 14 October advisories: remote code execution in the Image Optimization API with SVG files (CVE-2026-96889), remote code execution in `use cache` functions (GHSA-673q-mjm6-r5xr) and a Server Actions denial of service (CVE-2026-94482). GradePulse uses neither `use cache` nor Server Actions, but its image optimizer was enabled. `npm audit` for production packages now reports no vulnerabilities (it reported 1 critical and 2 high).
- Removed the unused default SVG files from `public/`.

### Sign-in protection

- **Wrong passwords are counted per account**, from any address: from the 5th within 15 minutes each try waits longer (15 s, doubling), and the 10th pauses sign-in for that account for 15 minutes. The account is checked before the password, emails with no account behave the same, and a correct sign-in or a reset clears it. The record is kept in the database, so a restart does not reset it.
- **Stronger new passwords:** at least 10 characters (was 8), common passwords and common words padded with digits refused, and the email's name not allowed in the password. Existing passwords keep working.
- **Rejected values are no longer echoed back.** A 422 used to repeat every rejected field, typed passwords included; it now returns only where the problem is and the message.
- The web app now shows the server's own validation messages (such as "That password is too easy to guess") instead of "Unprocessable Entity".

### Website and search

- **The WAEC grade calculator works on phones:** each subject is a card with its CA and exam boxes side by side and the total, grade and remark under them; larger screens keep the table.
- **Cloudflare Web Analytics is allowed** by the content security policy (`static.cloudflareinsights.com` for the script, `cloudflareinsights.com` for its reports), so visitor counts appear in the Cloudflare dashboard. The policy was blocking Cloudflare's beacon.
- **Public homepage** at `/` instead of a spinner that sent everyone to the login page: what GradePulse does, how it works with real screens (sample data), what it is built for, the two plans, questions school owners ask, and a WhatsApp demo link. Signed-in users still go straight to their dashboard. Rendered on the server so search engines read it.
- **Free WAEC grade calculator** at `/waec-grade-calculator`: CA and exam to total, grade (A1–F9) and remark per subject, with an average, plus the grading table and an example.
- **Guide** at `/guides/spot-struggling-students`: using weekly tests to find struggling students before exams.
- **Search and sharing:** a site address for every page, per-page titles and descriptions, link previews with an image for WhatsApp, Facebook and LinkedIn, `robots.txt` that keeps the signed-in app out of search engines, `sitemap.xml`, and structured data (software, FAQ, article).
- **Printed reports carry the site address**, so every parent sheet that goes home points back to gradepulse.com.ng.

### Billing

- **Paystack payments, per student, per term.** Admins see a Billing page: the school's standing, a "Pay with Paystack" checkout for N students (card, bank transfer, USSD), and past payments. Payments are confirmed when the admin returns from Paystack and by Paystack's signed webhook. Off until `PAYSTACK_SECRET_KEY` and `PRICE_PER_STUDENT_NAIRA` are set. `DEPLOYMENT.md` has the setup.
- **Free plan and paid plan.** A school that has not paid can have up to 40 students (`FREE_STUDENTS`) and use everything except printable reports; paying covers the whole school plus class reports and parent progress sheets. Adding or importing students past the limit, entering scores while over it, and loading reports answer 402 with what to do next, and the web app shows that message (Reports shows a "Reports come with a paid term" panel). A school's data always stays visible.
- **Top-ups and renewals.** Paying for extra students during a term adds them to it until the term ends. A new term must cover every student. When a term ends the school keeps its paid plan for 14 days (`GRACE_DAYS`) before falling back to the free plan.
- **Reminder bar** for admins when a term has ended or is in its grace period, when the school has more students than it paid for, or when a free school reaches its limit. Teachers never see it.
- **Pricing page** shows the free plan next to the per-student, per-term price from the server, and explains what happens when a term is not renewed.


### Admins and teachers

- **Invites can carry classes.** When creating an invite the admin ticks the classes the teacher will teach (`POST /invites` with `class_ids`); the teacher joins straight into them, with no empty first login. Pending invites show their classes.
- **No "primary subject" on students.** The Add/Edit Student form and the student tables no longer ask for or show a single subject: secondary students take every subject, and scores are entered per subject. The Students and dashboard tables show the class instead, and a student's Progress page shows how many tests are recorded. (`current_topic` stays in the API for the recommendation engine.)
- **Teachers see only the classes they teach.** The school admin ticks each teacher's classes in Settings → People (`PUT /members/{user_id}/classes`; `GET /members` lists them). A teacher's students, scores, triage, dashboard counts, progress and reports cover those classes only; a teacher with no classes sees no students. Admins still see the whole school.
- **Admin-only:** deleting students, importing a class list, and creating or renaming classes (deleting classes already was). Teachers add students into one of their classes and cannot move a student out of them.
- The sidebar shows whether the signed-in account is an admin or a teacher, and the dashboard tells a teacher which classes it covers.


### Operations

- **API docs are hidden in production.** `/docs`, `/redoc` and `/openapi.json` answer 404 when `GRADEPULSE_ENV=production`; development keeps them.
- **Production refuses the offline demo's JWT secret**, which is published in `deploy/demo`, like the other placeholder secrets.
- **The offline demo listens on this computer only** (`127.0.0.1:3000` and `:8000`): with a public secret it must never be reachable from the network.
- **Privacy policy** at `/privacy`, written for the Nigeria Data Protection Act 2023, linked from sign-up and pricing.
- **Content and engine-state changes are operator-only.** `POST /content`, content imports (`POST /ingest` with `type=content`) and `POST /save` need `X-Operator-Key`; any school login could change the shared content catalogue before. `deploy/pilot_seed.py` takes `--operator-key` (or `$OPERATOR_KEY`) to load the catalogue and skips it otherwise.
- **`/summary` `total_sessions`** counts the caller's school's recorded scores (it was the engine's platform-wide counter). `content_count` remains the size of the shared catalogue.
- **`TRUST_FORWARDED_FOR`** (default `false`) lets the sign-in rate limits use `X-Forwarded-For` behind a front proxy that overwrites it. Without it, every visitor behind the web app's proxy shares one allowance. `DEPLOYMENT.md` explains when it is safe to turn on.
- **Logging.** The API logs through Python's `logging` at `LOG_LEVEL`, instead of `print`. An unexpected error is logged with its traceback, and the client gets `{"detail": "Internal server error", "error_id": "..."}` so a report can be matched to the log line.
- **One version number.** `linucb_brain.__version__` feeds `pyproject.toml`, the FastAPI app and `/health` (which used to say 1.0.0).
- **`GRADEPULSE_ENV`** is the setting's name; the misspelt `GRADEPULPE_ENV` is still read, with a warning. Config files and docs use the new name.
- **Docs.** README, `PROJECT_INDEX.md` and `INVESTOR_CHECKLIST.md` (now a demo checklist) rewritten to match the product.

### Fixed

- **Excel class lists failed to import** ("Missing optional dependency 'openpyxl'"). `openpyxl` (for .xlsx) and `xlrd` (for .xls) are now in `requirements.txt`, so the Docker image can read them too.
- **CSV files saved from Excel as "CSV UTF-8"** lost their first column to a hidden byte-order mark, so `student_id` was reported missing.
- **Spreadsheet headers are matched loosely**: `Student ID`, ` student_id ` and `STUDENT_ID` all work. Blank rows below the data, which spreadsheets often carry, are skipped instead of reported as errors.


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

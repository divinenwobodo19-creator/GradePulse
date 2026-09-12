# Sam's Understanding — Team Handbooks Review

**Author:** Sam (AI/ML Engineer)
**Date:** August 28, 2026
**Source:** Review of all 7 files in `Team Handbooks/`

---

## 1. What This Project Is

GradePulse is a contextual bandit-powered learning personalization engine for African classrooms. It recommends the right content to the right student at the right time, using teachers' weekly test scores as its learning signal.

The project is being built entirely by AI agents. There is one human — Divine (Founder/Product) — who owns every strategic decision. The rest of the team is AI.

---

## 2. Team Structure (As I Understand It)

| Role | Agent | Status | First Session Priority |
|------|-------|--------|----------------------|
| Founder / Product | **Divine** (human) | Active | — |
| AI/ML Engineer | **Sam** (me) | Active — v0.1 complete | — |
| UI/UX Designer | **Mia** | Active — all complete (design system, Streamlit, Next.js 15/15, branding) | — |
| Infrastructure/DevOps | **Ali** | Active — sync.py, backup system, timestamp bug fixed | Production hardening |
| Data Engineer | **Bob** | Active — ingestion pipeline, sample data, API endpoint complete | Pilot data validation |
| QA/Testing | **David** | Active — load tests, sync edge cases, ingestion tests complete | Extend 179-test baseline |
| Documentation | **Alice** | Active — PROJECT_INDEX.md, audit pass, doc sync complete | Keep docs in sync |

---

## 3. Ground Rules (What Every Agent Must Follow)

1. **Read before you write.** Every session starts with `TEAM_HANDBOOK.md` and `SAM_TECHNICAL_HANDOFF.md`.
2. **Log decisions, not just code.** Anything that affects another role goes in the Decision Log before the session ends.
3. **The API contract belongs to Sam.** No one touches the 22 endpoints or JWT auth unless I change them.
4. **Don't silently change contracts.** Breaking changes must be flagged in the Decision Log.
5. **No session has roadmap authority.** Only Divine decides scope and priority.

---

## 4. My Role — Sam (AI/ML Engineer)

### 4.1 What I Own

| Area | Details |
|------|---------|
| **Core Algorithms** | LinUCB Disjoint (`linucb.py`), LinUCB Hybrid (`linucb_hybrid.py`) — the mathematical engine that makes recommendations |
| **Reward Design** | Multi-objective reward function (`brain.py:calculate_multi_objective_reward`), standalone reward calculator (`reward.py`), anti-gaming shaping |
| **Adaptive Gamma** | Non-stationarity detection (`brain.py:_adapt_gamma`) — auto-adjusts discount factor when reward variance spikes |
| **Clustering** | COBART-style online clustering (`clustering.py`) — groups similar students to share knowledge |
| **Neural Score** | 7-dimension self-diagnostic (`neural_score.py`) — the brain's health check |
| **REST API** | All 20 endpoints (`api/app.py`), JWT auth (`api/auth.py`), Pydantic schemas (`api/schemas.py`) |
| **Test Suite** | 179 tests across 14 test files (172 passed, 7 skipped — load tests require running server) |
| **Data Model** | Multi-tenant School→SchoolClass→Student hierarchy, JSON persistence |
| **Context Vector** | 17-dimensional feature builder (`context.py`) — the model's input contract |

### 4.2 What I Do Not Own

| Area | Owner |
|------|-------|
| Teacher portal UI/UX | Mia |
| Next.js frontend | Mia |
| Design system, branding | Mia |
| Deployment, scaling | Infra/DevOps |
| SQLite migration | Infra/DevOps (P2, after pilot) |
| Pilot data ingestion | Data Engineer |
| Load testing, messy data testing | QA/Testing |
| PROJECT_INDEX.md, API docs sync | Documentation |
| Product decisions, roadmap | Divine |

### 4.3 The API Contract (22 Endpoints)

Every other agent treats these as fixed unless I change them:

| Endpoint | Method | Auth |
|----------|--------|------|
| `/health` | GET | No |
| `/auth/signup` | POST | No |
| `/auth/login` | POST | No |
| `/auth/me` | GET | Yes |
| `/schools` | GET/POST | Yes |
| `/schools/{school_id}` | PUT/DELETE | Yes |
| `/classes/{school_id}` | GET/POST | Yes |
| `/classes/{school_id}/{class_id}` | PUT/DELETE | Yes |
| `/students` | GET/POST | Yes |
| `/students/{student_id}` | PUT/DELETE | Yes |
| `/content` | POST | Yes |
| `/recommend` | POST | Yes |
| `/update` | POST | Yes |
| `/bulk-update` | POST | Yes |
| `/triage` | POST | Yes |
| `/calculate-reward` | POST | Yes |
| `/summary` | GET | Yes |
| `/save` | POST | Yes |
| `/backup` | POST | Yes |
| `/backups` | GET | Yes |
| `/backup/restore` | POST | Yes |
| `/ingest` | POST | Yes |

### 4.4 The Context Vector (My Input Contract)

This is the shape every agent must respect when working with student or content data:

**Shared features (z, 8 dims):** performance_score, session_count, grade_trend_slope, education_level, age_band, credits_studied, imd_band, region_code

**Arm-specific features (x, 9 dims):** difficulty, topic_match, content_type (4 one-hot), perf_diff, perf_video, perf_quiz

If the Data Engineer changes this shape, my model breaks. If Mia's frontend sends data in the wrong shape, recommendations fail.

---

## 5. Critical Constraints (What I Flag for Other Agents)

| Constraint | Who It Affects | Why It Matters |
|-----------|---------------|----------------|
| ~~**Single-worker uvicorn**~~ | ~~Infra/DevOps~~ | **RESOLVED** — `sync.py` with `BrainSynchronizer` provides multi-worker safety via file locking + auto-save. |
| **JSON storage ceiling** | Infra/DevOps | Works for <50 students. SQLite migration is P2 in v0.2. Don't re-litigate. |
| **179-test baseline** | QA/Testing | Extend, never duplicate. If a test finds a bug in my code, log it — don't fix it. |
| **Multi-tenant hierarchy** | Data Engineer | School→SchoolClass→Student is fixed. New features must respect it. |
| **17-dim context vector** | Data Engineer | Real pilot data must map into this exact shape. No deviations without Decision Log entry. |
| **Neural Score** | QA, Docs | A dropping score is a signal worth investigating, not just a number to report. |

---

## 6. v0.2 Roadmap (What I'll Build Next)

| Feature | Priority | When |
|---------|----------|------|
| Thompson Sampling cold-start | P0 | After 2+ schools onboarded |
| `/group_recommendations` endpoint | P1 | When Mia's UI needs it |
| Context diversity regularization | P1 | When a school hits 50+ students |
| SQLite migration | P2 | When JSON breaks (~50 students) |
| Off-policy evaluation (OPE) | P2 | When 500+ sessions exist |

I do not reprioritize this list. Only Divine changes scope.

---

## 7. What I Learned From Mia's Profile

Mia (UI/UX Designer) has completed:
- Full design system (navy/gold palette, Inter font, 8-32px spacing)
- Streamlit teacher portal — full rewrite with branding, ARIA, score prefill, error handling
- Next.js frontend — 15/15 files complete (auth, dashboard, students, scores, triage, progress, settings)
- Offline HTML tool — branded redesign
- Logo integration across all surfaces
- Topic normalization fix — all pages send uppercase subjects to match `normalize_label()`

**Mia's dependency on me:** She needs my 22 API endpoints and their request/response shapes to build the frontend client layer. My `SAM_TECHNICAL_HANDOFF.md` Section 2.6 is her reference.

---

## 8. Open Questions (Only Divine Can Answer)

1. Which pilot schools first, and in what order?
2. Legal/compliance for student data (FERPA or equivalent)?

~~3. Pricing/business model?~~ — **Decided:** Freemium (Free ₦0 / Starter ₦5,000/mo / School ₦15,000/mo)
~~4. Investor-facing narrative and demo scope?~~ — **Decided:** Slides with app screenshots, investor deck built
~~5. SQLite migration timing relative to pilot scale?~~ — **Decided:** P2 in v0.2, when JSON breaks (~50 students)

The remaining questions are product/legal blockers — no code change unblocks them.

---

## 9. Decision Log Status

The Decision Log in `TEAM_HANDBOOK.md` is now active with entries from all roles. Key areas I'm tracking:

- **Single-worker constraint** — RESOLVED by Ali (sync.py)
- **Backup system** — COMPLETE by Ali, tested by David
- **Data ingestion** — COMPLETE by Bob, CLI + API endpoint
- **Test suite** — 179 tests (172 passed, 7 skipped). David extending baseline.
- **Documentation** — Alice sync'd PROJECT_INDEX.md, README.md, handoff docs

Any API changes, algorithm modifications, or schema updates I make will be logged before session end.

---

## 10. My Assessment of the Team Structure

This is a well-designed AI-agent coordination system. The key decisions that make it work:

- **Clear ownership boundaries.** Every file in the codebase has one owner. No dual ownership.
- **The API contract is frozen.** Agents build against it, not against each other's assumptions.
- **The Decision Log prevents silent breakage.** If I change an endpoint, the log tells Infra/DevOps and Mia before they discover it in production.
- **Divine is the single source of truth for scope.** No agent can unilaterally reprioritize the roadmap.

The risk is cross-role coordination. The Decision Log is the only coordination mechanism — every agent must log changes that affect others. Silent breakage is the failure mode to watch for.

---

*Reviewed and updated by Sam — August 31, 2026 (resolved 5 stale entries: test count, API count, Mia status, open questions, team structure)*

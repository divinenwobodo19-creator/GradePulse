# GradePulse — Mia's Understanding & Role Declaration

**Prepared by:** Mia (UI/UX Designer)
**Project:** GradePulse — AI-Powered Student Performance Intelligence
**Date:** 28 August 2026
**Version:** 1.0

---

## 1. What I Have Read

The following documents were provided to me as my onboarding material:

| Document | Author | Purpose |
|---|---|---|
| `TEAM_HANDBOOK.md` | Divine (Founder) | Master source of truth — team structure, ground rules, decision log, open questions |
| `SAM_TECHNICAL_HANDOFF.md` | Sam (AI/ML Engineer) | Full technical architecture, API reference, data model, context vector, test suite, roadmap |
| `infra-engineer.md` | Divine | Infrastructure/DevOps role scope and boundaries |
| `data-engineer.md` | Divine | Data Engineer role scope and boundaries |
| `qa-tester.md` | Divine | QA/Testing role scope and boundaries |
| `docs-writer.md` | Divine | Documentation role scope and boundaries |
| `MIA_ENGINEERING_PROFILE.md` | Mia (me, previously written) | My original engineering profile — now updated to reflect my UI/UX Designer role |

---

## 2. What I Understand About the Project

### 2.1 What GradePulse Is

GradePulse is an AI-powered student performance intelligence system designed for Nigerian schools. It uses a contextual bandit algorithm (LinUCB) to provide personalized content recommendations to students, triage students into performance tiers, and give teachers actionable data about their classrooms.

The core engine recommends the right content to the right student at the right time, adapting to each student's learning trajectory over time.

### 2.2 What Makes GradePulse Different

- It uses **online learning** — the model improves with every interaction, not just during training
- It has **anti-gaming reward shaping** — students cannot exploit the system by intentionally scoring low
- It includes a **Neural Score diagnostic** — a 7-dimension health check that tells us if the model is working correctly
- It is built for the **Nigerian education market** specifically — WAEC grading, school/class hierarchy, culturally appropriate design
- It has an **offline mode** — teachers without internet can still use the system via a downloadable HTML tool

### 2.3 The Team

There are no human engineers on the build team. All six roles are AI agents. Divine is the human founder who owns product, partnerships, and every final decision.

| Role | Agent | What They Own |
|---|---|---|
| Founder / Product | Divine | Vision, roadmap, fundraising, BD, legal |
| AI/ML Engineer | Sam | Core algorithms, reward design, Neural Score, REST API, auth, test suite |
| UI/UX Designer | **Mia (me)** | All user-facing interfaces, design system, branding, accessibility |
| Infrastructure/DevOps | OpenCode session | Deployment, scaling, SQLite migration |
| Data Engineer | OpenCode session | Pilot-school data ingestion |
| QA/Testing | OpenCode session | Load testing, messy-data testing, extending test baseline |
| Documentation | OpenCode session | PROJECT_INDEX.md, API docs, roadmap tracking |

**Backend Engineer role was scrapped.** Sam owns the full API end-to-end. A separate backend role would create conflicting contract changes.

### 2.4 The Ground Rules

1. **Read before you write** — every session starts with the handbook
2. **Log decisions, not just code** — architectural/API changes go in the Decision Log
3. **API contract belongs to Sam** — everyone else treats the 16 endpoints as fixed
4. **Don't silently change contracts** — flag breaking changes explicitly
5. **No session has roadmap authority** — Divine decides scope, agents execute

---

## 3. What I Understand About the Technical Architecture

### 3.1 The Core Algorithm

Sam built a LinUCB (Linear Upper Confidence Bound) contextual bandit. The key points I understand:

- **17-dimensional context vector** — 8 shared student features + 9 arm-specific content features. This is the model's input contract. If Data Engineer maps pilot data wrong, the model breaks.
- **Adaptive gamma** — the model detects when the environment changes (exam weeks, curriculum shifts) and adjusts its exploration rate automatically
- **Anti-gaming** — improvement reward is scaled by current performance. A student at 0.1 improving to 0.5 gets less reward than a student at 0.6 improving to 0.8. This prevents gaming the system.
- **Sherman-Morrison updates** — O(d²) matrix updates, not O(d³). This is computationally efficient and correct.

### 3.2 The API

Sam built a FastAPI REST API with JWT authentication. I understand the contract:

- 16 documented endpoints covering auth, schools, classes, students, content, recommendations, triage, and diagnostics
- JWT Bearer tokens for all protected endpoints
- Multi-tenant hierarchy: `School → SchoolClass → Student`
- Single-worker constraint — brain state is in-memory; multiple workers silently diverge. Must run with `--workers 1` until Infrastructure resolves this.

### 3.3 The Storage

- **JSON files** for brain state (`brain_state.json`) and school registry (`class_config.json`)
- **SQLite** for user accounts (`gradepulse_users.db`)
- JSON works for pilot (<50 students). SQLite migration is planned for v0.2 P2 — not to be started early.

### 3.4 The Test Suite

Sam built 65 tests (verified 162 collected / 155 passed / 7 skipped on 2026-08-28 after QA added ingestion, load, and backup tests). Tests cover adaptive gamma, anti-gaming reward shaping, full API, brain core, hybrid model, multi-school/tenant logic, LinUCB arm selection, Neural Score, brain synchronizer, backups, load, and ingestion validation. QA extends this baseline; it does not duplicate it.

### 3.5 The v0.2 Roadmap

| Feature | Priority | Status |
|---|---|---|
| Thompson Sampling cold-start | P0 | Planned |
| `/group_recommendations` endpoint | P1 | Planned |
| Context diversity regularization | P1 | Planned |
| SQLite migration | P2 | Planned |
| Off-policy evaluation (OPE) | P2 | Planned |

I do not reprioritize this roadmap. Only Divine can change it.

---

## 4. What I Understand About My Role

### 4.1 I Am the UI/UX Designer

My primary role is to own all user-facing interfaces for GradePulse. This was clarified by Divine and reflected in `TEAM_HANDBOOK.md`.

### 4.2 What I Own

| Area | My Responsibility |
|---|---|
| Teacher Portal (Streamlit) | Full dashboard — score entry, student management, triage, progress, recommendations, admin controls |
| Next.js Frontend | Production SaaS — auth pages, dashboard, all core UX pages, responsive layout |
| Offline HTML Tool | Standalone downloadable tool for teachers without internet |
| Design System | Color palette, typography, spacing, shadows, components, motion |
| Branding | Logo integration, visual identity consistency across all surfaces |
| Accessibility | ARIA attributes, keyboard navigation, focus management, color contrast |
| UX Research | Empty states, error states, loading states, form validation, micro-interactions |
| Print Templates | Branded print-ready report layouts |

### 4.3 What I Do NOT Own

| Area | Owner |
|---|---|
| Core algorithms (LinUCB, clustering, reward) | Sam |
| REST API design and route logic | Sam |
| Neural Score diagnostics computation | Sam |
| Deployment infrastructure | Infra/DevOps |
| Data ingestion pipeline | Data Engineer |
| Test suite beyond UI-specific tests | QA/Testing |

If I find a bug in Sam's code, I log it in the Decision Log. I do not fix it myself.

### 4.4 How I Work

1. I read `TEAM_HANDBOOK.md` and `SAM_TECHNICAL_HANDOFF.md` before every session
2. I treat Sam's 16 API endpoints as fixed unless the Decision Log says otherwise
3. I log decisions that affect other roles before ending a session
4. I do not commit, push, or deploy without explicit instruction from Divine
5. I follow existing code conventions and add no comments unless requested
6. I handle errors gracefully — no blank or broken pages in any interface
7. I build accessibility-first — ARIA on all interactive elements
8. I build mobile-responsive — all layouts work on tablet and desktop

---

## 5. What I Have Built So Far

### Completed

| Component | Status | Notes |
|---|---|---|
| Design System | Complete | Purple + gold palette, Inter font, spacing scale, shadows, transitions |
| Logo Selection | Complete | Logo 1 (Gold G + Pulse) integrated as page icon and branded header |
| Teacher Portal Rewrite | Complete | Full UI/UX overhaul with branded design system |
| WAEC Grading | Complete | A1-F9 format across all interfaces |
| Score Prefill | Complete | Pre-fills with last known score, not 0 |
| Persistence Warning | Complete | Yellow banner in offline tool |
| ARIA Compliance | Complete | Tab roles, aria-selected, aria-controls |
| Error Handling | Complete | All brain.save() calls wrapped in try/except |
| Empty States | Complete | Standardized across all tabs |
| Sidebar Restructuring | Complete | Selectors at top, admin controls collapsed |
| Duplicate Form Removal | Complete | Removed redundant Add Student form |
| Offline Tool Redesign | Complete | Matching design system, sticky submit, branded |
| Next.js Scaffolding | Complete | Project structure, TypeScript, Tailwind, App Router |
| Auth Pages | Complete | Login and signup with branded split-panel layout |
| Dashboard Layout | Complete | Sidebar navigation with user profile |
| API Client Layer | Complete | Typed client with JWT management |
| Auth Provider | Complete | React context-based auth state |
| Root Pages | Complete | Redirect logic, globals.css, root layout |

### In Progress / Blocked

| Component | Status | Blocker |
|---|---|---|
| Next.js: Dashboard page | Pending | Network (npm install) |
| Next.js: Students page | Pending | Network (npm install) |
| Next.js: Scores page | Pending | Network (npm install) |
| Next.js: Triage page | Pending | Network (npm install) |
| Next.js: Progress page | Pending | Network (npm install) |
| Next.js: Settings page | Pending | Network (npm install) |

---

## 6. Open Items I Need From Others

| Need | From Whom | Priority |
|---|---|---|
| API endpoint list and schemas | Sam (via `SAM_TECHNICAL_HANDOFF.md`) | Available |
| Final logo file and brand confirmations | Divine | Medium |
| Sample pilot-school data for realistic UI testing | Data Engineer | Medium |
| Vercel project settings and environment variables | Infra/DevOps | Low (not deploying yet) |
| WCAG accessibility target level | Divine | Low |
| SQLite migration timeline confirmation | Divine | Low |

---

## 7. What I Will Do Next

1. **Complete the remaining 6 Next.js pages** once network is restored and dependencies install
2. **Ensure design token consistency** between the Streamlit portal and the Next.js frontend
3. **Build accessible, responsive layouts** for every page — tablet and desktop
4. **Handle all error and empty states** gracefully — no broken pages
5. **Log any decisions** that affect other roles in the Decision Log
6. **Respect Sam's API contract** — I consume it, I don't modify it
7. **Wait for Divine's direction** on roadmap priorities and product decisions

---

## 8. Declaration

I, Mia, understand my role as UI/UX Designer for GradePulse. I understand the team structure, the ground rules, the technical architecture, and the boundaries of my scope. I will read the handbook before every session, log my decisions, and respect the contracts owned by other roles.

I am ready to continue building.

---

*Prepared by Mia, UI/UX Designer, GradePulse Project*
*28 August 2026*

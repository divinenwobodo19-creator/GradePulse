---
tags:
  - reference
  - grade-pulse
created: 2026-08-28
---

# GradePulse File Index

> Full codebase navigation. See also: [[GradePulse Architecture]]

---

## Root

| File | Purpose | Owner |
|---|---|---|
| `README.md` | Quick start, structure | [[Alice — Documentation]] |
| `PROJECT_INDEX.md` | Codebase navigation | [[Alice — Documentation]] |
| `requirements.txt` | Python dependencies | [[Sam — AI/ML Engineer]] |
| `pyproject.toml` | Project metadata | [[Sam — AI/ML Engineer]] |
| `teacher_portal.py` | Streamlit dashboard | [[Mia — UI/UX Designer]] |
| `generate_offline.py` | Offline HTML generator | [[Mia — UI/UX Designer]] |
| `offline_teacher.html` | Generated standalone tool | [[Mia — UI/UX Designer]] |
| `ingest.py` | Data ingestion CLI | [[Bob — Data Engineer]] |
| `brain_state.json` | Model persistence | [[Sam — AI/ML Engineer]] |
| `class_config.json` | School/class registry | [[Sam — AI/ML Engineer]] |
| `gradepulse_users.db` | User accounts | [[Sam — AI/ML Engineer]] |

## `linucb_brain/core/`

| File | Purpose |
|---|---|
| `linucb.py` | [[LinUCB Algorithm]] Disjoint |
| `linucb_hybrid.py` | [[LinUCB Algorithm]] Hybrid |
| `clustering.py` | Online KMeans clustering |
| `context.py` | [[Context Vector — 17 Dimensions]] |
| `reward.py` | [[Anti-Gaming Reward Shaping]] |

## `linucb_brain/models/`

| File | Purpose |
|---|---|
| `student.py` | Student model |
| `content.py` | Content model |
| `session.py` | Session model |
| `school.py` | School hierarchy model |

## `linucb_brain/diagnostics/`

| File | Purpose |
|---|---|
| `neural_score.py` | [[Neural Score Diagnostics]] |
| `report.py` | Report renderer |

## `linucb_brain/api/`

| File | Purpose |
|---|---|
| `app.py` | [[API Endpoints — 16]] |
| `schemas.py` | Pydantic models |
| `auth.py` | JWT auth |

## `linucb_brain/`

| File | Purpose |
|---|---|
| `brain.py` | Main Brain class |
| `storage.py` | JSON save/load |
| `sync.py` | [[Multi-Worker Sync]] |
| `registry.py` | School registry |
| `utils.py` | Utilities |

## `tests/` — 73 tests

| File | Tests |
|---|---|
| `test_adaptive_gamma.py` | 6 |
| `test_anti_gaming.py` | 7 |
| `test_api.py` | 25 |
| `test_brain.py` | 4 |
| `test_hybrid.py` | 7 |
| `test_integration.py` | 1 |
| `test_linucb.py` | 3 |
| `test_multi_school.py` | 9 |
| `test_neural_score.py` | 3 |
| `test_sync.py` | 8 |

## `sample_data/`

| File | Contents |
|---|---|
| `sample_students.csv` | 5 Nigerian students, 2 schools |
| `sample_content.csv` | 8 content items |

## `gradepulse-web/src/`

| Path | Purpose |
|---|---|
| `app/layout.tsx` | Root layout |
| `app/page.tsx` | Root redirect |
| `app/globals.css` | Design tokens |
| `app/(auth)/login/` | Login page |
| `app/(auth)/signup/` | Signup page |
| `app/(dashboard)/layout.tsx` | Sidebar nav |
| `app/(dashboard)/dashboard/` | Main dashboard |
| `app/(dashboard)/students/` | Student CRUD |
| `app/(dashboard)/scores/` | Score entry |
| `app/(dashboard)/triage/` | Student triage |
| `app/(dashboard)/progress/` | Progress tracking |
| `app/(dashboard)/settings/` | Settings |
| `lib/types.ts` | TypeScript types |
| `lib/api.ts` | API client |
| `lib/auth.tsx` | Auth provider |

---

*Source: PROJECT_INDEX.md*

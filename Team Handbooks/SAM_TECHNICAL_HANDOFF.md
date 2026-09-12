# GradePulse — Technical Handoff Document

**Author:** Sam (AI/ML Engineer)
**Date:** August 2026
**Version:** v0.1
**Project:** Contextual Bandit-Powered Learning Personalization Engine

---

## 1. Role Overview

Sam is the AI/ML engineer responsible for the backend intelligence of GradePulse. All algorithmic decisions, model architecture, reward design, diagnostics, and API layer fall under this role.

**Core Responsibilities:**
- LinUCB algorithm implementation (Disjoint and Hybrid variants)
- Contextual bandit model design and tuning
- Reward function engineering (anti-gaming, multi-objective)
- Adaptive gamma (non-stationarity handling)
- Online clustering engine (COBART-style)
- Neural Score diagnostic system
- REST API design and implementation
- Test suite (179 tests, 172 passed, 7 skipped)
- Model persistence (save/load)
- Multi-tenant school data architecture

---

## 2. What Has Been Built

### 2.1 Core Engine (`linucb_brain/core/`)

| File | Purpose |
|------|---------|
| `linucb.py` | LinUCB Disjoint — per-arm独立 matrices, Sherman-Morrison O(d²) updates, discounted LinUCB for non-stationary environments |
| `linucb_hybrid.py` | LinUCB Hybrid — shared + arm-specific + cluster-specific parameters, vectorized arm selection |
| `clustering.py` | MiniBatchKMeans online clustering, SHA-256 deterministic cold-start assignment |
| `context.py` | 17-dimensional context vector builder (8 shared student features + 9 arm-specific content features) |
| `reward.py` | Standalone reward calculator with anti-gaming scaling |

### 2.2 Brain (`linucb_brain/brain.py`)

The single public interface. Key methods:

| Method | What It Does |
|--------|-------------|
| `add_student()` | Register a student profile |
| `add_content()` | Register a content item |
| `recommend()` | Get top-N content recommendations for a student |
| `update()` | Feed a reward signal back into the model |
| `calculate_multi_objective_reward()` | Combine improvement/completion/engagement into a single reward |
| `triage()` | Group students into remediation/on_track/ahead tiers |
| `bulk_update()` | Submit scores for an entire class at once |
| `predict_grade()` | Predict a student's grade based on history |
| `neural_score()` | Run 7-dimension self-diagnostic |
| `save()` / `load()` | Persist and restore brain state |

### 2.3 Adaptive Gamma (Non-Stationarity Detection)

**File:** `brain.py` — `_adapt_gamma()`

- Tracks a rolling window of 50 recent rewards
- Every 25 updates, compares variance between first and second half of window
- If variance spikes (>40% increase or >0.35 absolute): gamma decreases by 0.03, floor at 0.85
- When variance normalizes: gamma creeps back toward baseline at 0.005 per cycle
- LinUCB model gamma is synced in real-time

**Use case:** Exam weeks, seasonal shifts, curriculum changes.

### 2.4 Anti-Gaming Reward Shaping

**Files:** `brain.py` — `calculate_multi_objective_reward()`, `core/reward.py` — `calculate_reward()`

Improvement reward is scaled by `current_performance`:

```
performance_factor = max(0.1, current_performance)
imp_signal = clip(improvement * 5.0 * performance_factor, -1.0, 1.0)
```

**Effect:**
- Student at 0.1 improving by 0.4 → imp_signal = 0.2 (low reward)
- Student at 0.6 improving by 0.3 → imp_signal = 0.9 (high reward)

Gaming the system by scoring low first yields minimal improvement reward.

### 2.5 Neural Score Diagnostics

**File:** `linucb_brain/diagnostics/neural_score.py`

7 dimensions, each scored 0-10:

| Dimension | Weight | What It Measures |
|-----------|--------|-----------------|
| Exploration Efficiency | 15% | Diversity of recommendations (entropy) |
| Reward Convergence | 20% | Is average reward trending up? |
| Context Sensitivity | 15% | Do different students get different recs? |
| Recommendation Precision | 20% | Fraction of positive rewards |
| Grade Prediction | 10% | Accuracy of predicted vs actual grades |
| Cohort Purity | 10% | Balance of student cluster sizes |
| Objective Balance | 10% | Variance of reward signals |

### 2.6 REST API

**File:** `linucb_brain/api/app.py`

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/health` | GET | No | Health check |
| `/auth/signup` | POST | No | Create account |
| `/auth/login` | POST | No | Get JWT token |
| `/auth/me` | GET | Yes | Current user info |
| `/schools` | GET/POST | Yes | List/create schools |
| `/schools/{school_id}` | PUT/DELETE | Yes | Update/delete school |
| `/classes/{school_id}` | GET/POST | Yes | List/create classes |
| `/classes/{school_id}/{class_id}` | PUT/DELETE | Yes | Update/delete class |
| `/students` | GET/POST | Yes | List/create students |
| `/students/{student_id}` | PUT/DELETE | Yes | Update/delete student |
| `/content` | POST | Yes | Create content item |
| `/recommend` | POST | Yes | Get recommendations |
| `/update` | POST | Yes | Submit reward signal |
| `/bulk-update` | POST | Yes | Submit class scores |
| `/triage` | POST | Yes | Student triage by subject |
| `/calculate-reward` | POST | Yes | Calculate reward from scores |
| `/summary` | GET | Yes | Brain state summary |
| `/save` | POST | Yes | Persist brain state |
| `/backup` | POST | Yes | Create backup |
| `/backups` | GET | Yes | List backups |
| `/backup/restore` | POST | Yes | Restore from backup |
| `/ingest` | POST | Yes | Upload CSV/Excel for ingestion |

**Auth:** JWT Bearer tokens. Pass `Authorization: Bearer <token>` header.

### 2.7 Test Suite

**Location:** `tests/`

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_adaptive_gamma.py` | 6 | Gamma adaptation, variance detection, floor, restore, model sync |
| `test_anti_gaming.py` | 7 | Anti-gaming scaling, gaming scenario, churn, standalone function |
| `test_api.py` | 25 | All API endpoints, auth, CRUD |
| `test_brain.py` | 4 | Student/content add, recommend, update, save/load |
| `test_hybrid.py` | 7 | Hybrid model init, recommend, save/load, cluster state, backward compat |
| `test_integration.py` | 1 | Full pipeline: init → add → recommend → update → save → load → verify |
| `test_linucb.py` | 3 | Arm selection, matrix updates, alpha=0 exploitation |
| `test_multi_school.py` | 9 | Triage, multi-tenant, legacy migration |
| `test_neural_score.py` | 3 | Score ranges, weighted calculation, report rendering |
| `test_sync.py` | 20 | File lock, synchronizer load/save, auto-save, force reload, edge cases (QA) |
| `test_backup.py` | 10 | Backup rotation, listing, restore, metadata, lifecycle |
| `test_backup_api.py` | 17 | Backup API endpoints: create, list, restore, auth, integration |
| `test_load.py` | 7 | Concurrent API load tests (require running server) |
| `test_ingest.py` | 60 | CSV readers, validators, grade parsing, student/content ingestion |
| **Total** | **179** | **172 passed, 7 skipped** (load tests require running server) |

Run tests:
```bash
cd "Contextual Band brain model"
PYTHONPATH=. python3 -m pytest tests/ -v
```

---

## 3. Context Vector Architecture

17-dimensional feature vector, split into shared (student) and arm-specific (content):

### Shared Features (z, 8 dims)
| Index | Feature | Source |
|-------|---------|--------|
| 0 | performance_score | Student's overall score (0-1) |
| 1 | session_count | log1p(sessions) / log1p(100) |
| 2 | grade_trend_slope | Linear regression slope of recent grades |
| 3 | education_level | Numeric education level |
| 4 | age_band | Numeric age band |
| 5 | credits_studied | Credits completed |
| 6 | imd_band | Deprivation index (default 0.5) |
| 7 | region_code | Numeric region |

### Arm-Specific Features (x, 9 dims)
| Index | Feature | Source |
|-------|---------|--------|
| 0 | difficulty | (content.difficulty - 1) / 4 |
| 1 | topic_match | 1.0 if student topic matches content topic |
| 2-5 | content_type | One-hot: video, quiz, exercise, reading |
| 6 | perf_diff | performance × difficulty interaction |
| 7 | perf_video | performance × video interaction |
| 8 | perf_quiz | performance × quiz interaction |

---

## 4. Data Model

### Multi-Tenant Architecture
```
School (school_id) → SchoolClass (class_id, school_id) → Student (student_id, class_id, school_id)
```

### Files
| File | Purpose |
|------|---------|
| `class_config.json` | School/class registry |
| `brain_state.json` | LinUCB brain state (students, contents, sessions, model matrices) |

### Storage Limitation
JSON files work for pilot (<50 students). Migration to SQLite is planned for v0.2 when student count exceeds 50.

---

## 5. How to Run

### Start the API
```bash
cd "Contextual Band brain model"
PYTHONPATH=. uvicorn linucb_brain.api.app:app --host 0.0.0.0 --port 8000
```

**Important:** The single-worker constraint has been resolved by Infrastructure (`sync.py` with `BrainSynchronizer`). Multiple workers can now safely share brain state via file locking and periodic auto-save.

### Start the Teacher Portal (Streamlit)
```bash
PYTHONPATH=. streamlit run teacher_portal.py
```

### Generate Offline HTML Tool
```bash
PYTHONPATH=. python3 generate_offline.py
```

### Example API Calls
```bash
# Get a recommendation
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"student_id": "608041", "top_n": 3}'

# Submit scores for a class
curl -X POST http://localhost:8000/bulk-update \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "entries": [
      {"student_id": "S01", "subject": "Math", "score": 0.85},
      {"student_id": "S02", "subject": "Math", "score": 0.42}
    ]
  }'

# Get triage (remediation/on_track/ahead)
curl http://localhost:8000/triage/Math \
  -H "Authorization: Bearer <token>"
```

---

## 6. v0.2 Roadmap (Post-Pilot)

| Feature | Priority | Status |
|---------|----------|--------|
| Thompson Sampling cold-start | P0 | Planned |
| `/group_recommendations` endpoint | P1 | Planned |
| Context diversity regularization | P1 | Planned |
| SQLite migration | P2 | Planned |
| Off-policy evaluation (OPE) | P2 | Planned |

These will be implemented after pilot data is collected and analyzed.

---

## 7. Key Contacts

| Role | Responsibility |
|------|---------------|
| **Sam** (AI/ML) | Backend engine, algorithms, API, diagnostics |
| **UI/UX Team** | Teacher portal frontend, student-facing interface |
| **Project Owner** | School partnerships, pilot coordination, product direction |

---

## 8. File Reference

```
Contextual Band brain model/
├── linucb_brain/
│   ├── core/
│   │   ├── linucb.py              # LinUCB Disjoint
│   │   ├── linucb_hybrid.py       # LinUCB Hybrid + Clustering
│   │   ├── clustering.py          # Online KMeans clustering
│   │   ├── context.py             # 17-dim context builder
│   │   └── reward.py              # Standalone reward calculator
│   ├── diagnostics/
│   │   ├── neural_score.py        # 7-dimension self-diagnostic
│   │   └── report.py              # Report renderer
│   ├── api/
│   │   ├── app.py                 # FastAPI application
│   │   ├── schemas.py             # Pydantic models
│   │   └── auth.py                # JWT authentication
│   ├── models/                    # Data models (Student, Content, Session, School)
│   ├── brain.py                   # Main Brain class
│   ├── storage.py                 # JSON save/load
│   ├── sync.py                    # Multi-worker file locking + auto-save
│   └── utils.py                   # Utilities
├── tests/                         # 73 tests, all passing
├── teacher_portal.py              # Streamlit dashboard
├── generate_offline.py            # Offline HTML generator
├── ingest.py                      # Data ingestion pipeline (CSV/Excel)
├── sample_data/                   # Sample pilot-school data
├── brain_state.json               # Model persistence
├── class_config.json              # School/class registry
└── requirements.txt               # Dependencies
```

---

*Updated by Sam — August 31, 2026. API endpoints 16→22, test count 162→179 (added test_backup_api.py), paths aligned to actual code.*

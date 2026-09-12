---
tags:
  - architecture
  - grade-pulse
created: 2026-08-28
---

# GradePulse Architecture

---

## System Flow

```
Student (context) → Brain recommends (explore/exploit) → Student engages
                                                              ↓
Brain updates matrices ← Reward signal (score, complete)
```

---

## Core Engine (`linucb_brain/`)

### Algorithms (`core/`)

| File | Algorithm |
|---|---|
| `linucb.py` | LinUCB Disjoint — per-arm matrices, Sherman-Morrison O(d²) |
| `linucb_hybrid.py` | LinUCB Hybrid — shared + arm-specific + cluster params |
| `clustering.py` | MiniBatchKMeans online clustering, SHA-256 cold-start |
| `context.py` | [[Context Vector — 17 Dimensions]] builder |
| `reward.py` | [[Anti-Gaming Reward Shaping]] calculator |

### Data Models (`models/`)

| File | Model |
|---|---|
| `student.py` | Student profile |
| `content.py` | Content item |
| `session.py` | Interaction session |
| `school.py` | School/class hierarchy |

### API (`api/`)

| File | Purpose |
|---|---|
| `app.py` | FastAPI — [[API Endpoints — 16]] |
| `schemas.py` | Pydantic request/response models |
| `auth.py` | JWT authentication |

### Diagnostics (`diagnostics/`)

| File | Purpose |
|---|---|
| `neural_score.py` | [[Neural Score Diagnostics]] engine |
| `report.py` | Report renderer |

### Infrastructure

| File | Purpose |
|---|---|
| `sync.py` | [[Multi-Worker Sync]] — file-based locking, auto-save |
| `brain.py` | Main Brain class — single public interface |
| `storage.py` | JSON save/load |
| `registry.py` | School/class registry |

---

## Frontend

| Component | Tech | Owner |
|---|---|---|
| Teacher Portal | Streamlit | [[Mia — UI/UX Designer]] |
| Production SaaS | Next.js (15/15 files) | [[Mia — UI/UX Designer]] |
| Offline Tool | Standalone HTML | [[Mia — UI/UX Designer]] |

---

## Storage

| Store | Contents | Ceiling |
|---|---|---|
| `brain_state.json` | LinUCB model state | ~50 students |
| `class_config.json` | School/class registry | Unlimited |
| `gradepulse_users.db` | User accounts (JWT) | Unlimited |

Migration to SQLite planned for v0.2 (P2).

---

## Test Suite

**73 tests, all passing.** See [[GradePulse File Index]] for per-file breakdown.

---

*Source: SAM_TECHNICAL_HANDOFF.md*

# Changelog

All notable changes to GradePulse will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

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
- 179 tests (pytest)
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

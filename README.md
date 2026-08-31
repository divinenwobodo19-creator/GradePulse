# GradePulse

A self-learning personalization engine for education, powered by Contextual Bandit algorithms.

## Why This Matters

In Nigeria and across Africa, teachers manage 40-80 students per class with no way to personalize learning. A student struggling with fractions gets the same content as one ready for algebra. GradePulse changes that — it learns what works for each student and recommends the right content at the right time, using the teacher's existing weekly test scores as its signal.

Most LMS platforms are content repositories. GradePulse is a recommendation engine that gets smarter with every score a teacher enters.

## What It Does

Every student is different. Most LMS platforms serve the same content to everyone. The Brain learns **what works for whom** — adapting in real-time as each student interacts with the platform.

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│ Student      │────>│ Brain recommends │────>│ Student      │
│ (context)    │     │ (explore/exploit)│     │ engages with │
└─────────────┘     └──────────────────┘     │ content      │
                                             └──────┬───────┘
                                                    │
┌─────────────┐     ┌──────────────────┐            │
│ Brain       │<────│ Reward signal    │<───────────┘
│ updates     │     │ (score, complete)│
│ matrices    │     └──────────────────┘
└─────────────┘
```

## Key Features

| Capability | What It Means |
|---|---|
| **2 Algorithms** | Disjoint LinUCB and Hybrid LinUCB with online clustering |
| **Real-time Learning** | Updates after every interaction — no batch retraining |
| **Cold-start Ready** | Explores when it has no data; exploits when it does |
| **Self-Diagnostics** | Neural Score measures 7 dimensions of model health |
| **Online Clustering** | Groups similar students to share knowledge (COBART-style) |
| **FastAPI REST API** | Production-ready REST API with demo seeding |
| **Multi-Tenant** | School-scoped data model with class management |
| **Multi-Worker Safe** | File-based brain state sync with locking — safe for multiple uvicorn workers |
| **Data Ingestion** | CLI tool for pilot-school data (CSV/Excel) with 17-dim context vector validation |
| **Automated Backups** | Periodic brain state backups with rotation, atomic writes, and restore capability |
| **Docker Ready** | Multi-stage Dockerfile + docker-compose for one-command production deployment |
| **CI/CD Pipeline** | GitHub Actions: test on every push, Docker images built on release tags |

## Neural Score — Built-in Diagnostics

The Brain scores itself on 7 dimensions (each 0–10):

```
Exploration Efficiency  →  8.3/10  (Are we trying diverse content?)
Reward Convergence      →  7.1/10  (Is average reward improving?)
Context Sensitivity     →  6.8/10  (Do different students get different recs?)
Recommendation Precision→  7.5/10  (Are recommended items getting good rewards?)
Grade Prediction        →  6.2/10  (Can we forecast student performance?)
Cohort Purity           →  7.0/10  (Are student clusters well-separated?)
Objective Balance       →  7.5/10  (Are all reward signals being used?)
─────────────────────────────────
NEURAL SCORE            →  7.2/10
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the REST API (auto-loads brain_state.json, seeds demo data if empty)
PYTHONPATH=. uvicorn linucb_brain.api.app:app --host 0.0.0.0 --port 8000

# 3. Get a recommendation
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"student_id": "608041", "top_n": 3}'

# 4. Open the Teacher Portal (Streamlit)
PYTHONPATH=. streamlit run teacher_portal.py

# 5. Generate offline HTML tool
PYTHONPATH=. python3 generate_offline.py

# 6. Ingest pilot-school data
PYTHONPATH=. python3 ingest.py sample_data/sample_students.csv --school-name "Lagos Model School"

# 7. Create a backup (requires running API + auth token)
curl -X POST http://localhost:8000/backup -H "Authorization: Bearer <token>"

# 8. List backups
curl http://localhost:8000/backups -H "Authorization: Bearer <token>"
```

> **Windows?** Use `set PYTHONPATH=. && uvicorn ...` (CMD) or `$env:PYTHONPATH='.'; uvicorn ...` (PowerShell) instead of `PYTHONPATH=.`.

> **Multi-worker safe:** Brain state is synced to disk with file-based locking (`linucb_brain/sync.py`). Multiple uvicorn workers are now supported.

### Docker (Production)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — set JWT_SECRET at minimum

# 2. Start all services
docker compose up -d --build

# 3. Verify
curl http://localhost:8000/health
# Frontend: http://localhost:3000
```

Data persists in the `gradepulse-data` Docker volume across restarts. See `DEPLOYMENT.md` for full production setup (HTTPS, Nginx, backups, upgrades).

## Running Tests

```bash
PYTHONPATH=. python3 -m pytest tests/ -v
```

## Project Structure

```
├── linucb_brain/           # Core engine
│   ├── core/               # Algorithms (linucb, hybrid, clustering, reward)
│   ├── models/             # Data models (student, content, session, school)
│   ├── diagnostics/        # Neural Score engine
│   ├── api/                # FastAPI application (29 endpoints)
│   ├── sync.py             # Multi-worker brain state synchronization
│   └── backup.py           # Automated backup system (rotation, restore)
├── tests/                  # Test suite (179 tests, pytest)
├── sample_data/            # Sample pilot-school data (CSV)
│   ├── large/              # Large sample dataset (56 students)
│   └── pilot_grade/        # Pilot-grade validation data
├── .github/workflows/      # CI/CD (GitHub Actions)
│   ├── ci.yml              # Test on push/PR to main
│   └── docker.yml          # Build Docker images on version tags
├── ingest.py               # Data ingestion CLI tool
├── generate_pilot_data.py  # Pilot data generation script
├── Dockerfile              # Multi-stage Docker build (backend + frontend)
├── docker-compose.yml      # Docker Compose orchestration
├── DEPLOYMENT.md           # Production deployment runbook
├── .env.example            # Production configuration variables
├── .dockerignore           # Docker build context exclusions
├── teacher_portal.py       # Streamlit teacher dashboard
├── generate_offline.py     # Offline HTML tool generator
├── offline_teacher.html    # Generated standalone tool
├── brain_state.json        # Model persistence
└── class_config.json       # School/class registry
```

## Deployment

See `DEPLOYMENT.md` for the full production runbook covering:
- First-time VPS setup
- Docker deployment
- HTTPS/SSL with Nginx
- Backup and restore procedures
- Upgrades and troubleshooting

## License

MIT

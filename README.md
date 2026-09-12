# GradePulse v0.1.0

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
| **FastAPI REST API** | 29 production-ready endpoints with JWT authentication |
| **Multi-Tenant** | School → Class → Student hierarchy with scoped data |
| **Multi-Worker Safe** | File-based brain state sync with locking — safe for multiple uvicorn workers |
| **Data Ingestion** | CLI + API for pilot-school data (CSV/Excel) with 17-dim context vector validation |
| **Automated Backups** | Periodic brain state backups with rotation, atomic writes, and restore capability |
| **Docker Ready** | Multi-stage Dockerfile + docker-compose for one-command production deployment |
| **CI/CD Pipeline** | GitHub Actions: test on every push, Docker images built on release tags |

## Quick Start

### Option 1: Local Development

```bash
# 1. Clone the repository
git clone https://github.com/divinenwobodo19-creator/GradePulse.git
cd GradePulse

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the REST API
PYTHONPATH=. uvicorn linucb_brain.api.app:app --host 0.0.0.0 --port 8000

# 4. Open a new terminal and try the API
# Sign up
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "teacher@school.com", "password": "password123", "school_name": "My School"}'

# Get a recommendation (use the token from signup)
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{"student_id": "608041", "top_n": 3}'
```

### Option 2: Docker (Production)

```bash
# 1. Clone and configure
git clone https://github.com/divinenwobodo19-creator/GradePulse.git
cd GradePulse
cp .env.example .env
# Edit .env — set JWT_SECRET at minimum

# 2. Start all services
docker compose up -d --build

# 3. Verify
curl http://localhost:8000/health
# Frontend: http://localhost:3000
```

### Option 3: Teacher Portal (Streamlit)

```bash
# Start the teacher dashboard
PYTHONPATH=. streamlit run teacher_portal.py

# Open http://localhost:8501
```

## API Usage Examples

### Authentication

```bash
# Sign up
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "teacher@school.com", "password": "password123", "school_name": "Lagos Model School"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "teacher@school.com", "password": "password123"}'
```

### Student Management

```bash
# Add a student
curl -X POST http://localhost:8000/students \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"student_id": "S001", "name": "Chinwe Okoro", "performance_score": 0.75, "current_topic": "MATH"}'

# List students
curl http://localhost:8000/students \
  -H "Authorization: Bearer <token>"
```

### Recommendations

```bash
# Get a recommendation for a student
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"student_id": "S001", "top_n": 3}'

# Get recommendation for a specific topic
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"student_id": "S001", "topic": "MATH", "top_n": 1}'
```

### Score Entry

```bash
# Update with a reward signal
curl -X POST http://localhost:8000/update \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"student_id": "S001", "content_id": "C001", "reward": 0.85}'

# Bulk update scores for a class
curl -X POST http://localhost:8000/bulk-update \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"entries": [{"student_id": "S001", "subject": "MATH", "score": 0.85}, {"student_id": "S002", "subject": "MATH", "score": 0.72}]}'
```

### Student Triage

```bash
# Group students by performance
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"subject": "MATH"}'
```

### Data Ingestion

```bash
# Ingest student roster via API
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer <token>" \
  -F "file=@students.csv" \
  -F "type=students" \
  -F "school=My School"

# Or use the CLI
PYTHONPATH=. python3 ingest.py sample_data/sample_students.csv --school-name "Lagos Model School"
```

### Backups

```bash
# Create a backup
curl -X POST http://localhost:8000/backup \
  -H "Authorization: Bearer <token>"

# List backups
curl http://localhost:8000/backups \
  -H "Authorization: Bearer <token>"

# Restore from backup
curl -X POST "http://localhost:8000/backup/restore?backup_path=/path/to/backup" \
  -H "Authorization: Bearer <token>"
```

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

## Running Tests

```bash
# Run all tests
PYTHONPATH=. python3 -m pytest tests/ -v

# Run specific test file
PYTHONPATH=. python3 -m pytest tests/test_brain.py -v

# Run with coverage
PYTHONPATH=. python3 -m pytest tests/ --cov=linucb_brain
```

## Project Structure

```
├── linucb_brain/           # Core engine
│   ├── core/               # Algorithms (linucb, hybrid, clustering, reward)
│   ├── models/             # Data models (student, content, session, school)
│   ├── diagnostics/        # Neural Score engine
│   ├── api/                # FastAPI application (29 endpoints)
│   │   ├── app.py          # Main application
│   │   ├── auth.py         # JWT authentication
│   │   └── schemas.py      # Pydantic request/response models
│   ├── sync.py             # Multi-worker brain state synchronization
│   └── backup.py           # Automated backup system (rotation, restore)
├── tests/                  # Test suite (179 tests, pytest)
├── sample_data/            # Sample pilot-school data (CSV)
│   ├── large/              # Large sample dataset (56 students)
│   └── pilot_grade/        # Pilot-grade validation data
├── .github/workflows/      # CI/CD (GitHub Actions)
│   ├── ci.yml              # Test on push/PR to main
│   └── docker.yml          # Build Docker images on version tags
├── gradepulse-web/         # Next.js frontend (15 pages)
├── ingest.py               # Data ingestion CLI tool
├── generate_pilot_data.py  # Pilot data generation script
├── Dockerfile              # Multi-stage Docker build (backend + frontend)
├── docker-compose.yml      # Docker Compose orchestration
├── DEPLOYMENT.md           # Production deployment runbook
├── .env.example            # Production configuration variables
├── teacher_portal.py       # Streamlit teacher dashboard
├── generate_offline.py     # Offline HTML tool generator
├── offline_teacher.html    # Generated standalone tool
├── brain_state.json        # Model persistence
└── class_config.json       # School/class registry
```

## API Endpoints

| Category | Endpoint | Method | Description |
|----------|----------|--------|-------------|
| **Auth** | `/auth/signup` | POST | Create account |
| | `/auth/login` | POST | Login |
| | `/auth/me` | GET | Get current user |
| **Schools** | `/schools` | GET/POST | List/Create schools |
| | `/schools/{id}` | PUT/DELETE | Update/Delete school |
| **Classes** | `/classes/{school_id}` | GET/POST | List/Create classes |
| | `/classes/{school_id}/{class_id}` | PUT/DELETE | Update/Delete class |
| **Students** | `/students` | GET/POST | List/Create students |
| | `/students/{id}` | PUT/DELETE | Update/Delete student |
| **Content** | `/content` | POST | Add content item |
| **Brain** | `/recommend` | POST | Get recommendations |
| | `/update` | POST | Update with reward |
| | `/bulk-update` | POST | Bulk score entry |
| | `/triage` | POST | Group students by performance |
| | `/calculate-reward` | POST | Calculate reward signal |
| | `/summary` | GET | Brain state summary |
| | `/save` | POST | Save brain state |
| **Backups** | `/backup` | POST | Create backup |
| | `/backups` | GET | List backups |
| | `/backup/restore` | POST | Restore from backup |
| **Data** | `/ingest` | POST | Ingest CSV/Excel data |
| **Health** | `/health` | GET | Health check |

## Deployment

See `DEPLOYMENT.md` for the full production runbook covering:
- First-time VPS setup
- Docker deployment
- HTTPS/SSL with Nginx
- Backup and restore procedures
- Upgrades and troubleshooting

## What's Included in v0.1.0

- Core LinUCB engine (Disjoint + Hybrid)
- 29 REST API endpoints with JWT auth
- Multi-tenant data model (School → Class → Student)
- Multi-worker synchronization
- Automated backup system
- Data ingestion pipeline (CLI + API)
- Teacher Portal (Streamlit)
- Next.js frontend (15 pages)
- Docker containerization
- CI/CD pipeline (GitHub Actions)
- 179 tests

## What's Deferred to v0.2

- Thompson Sampling cold-start
- `/group_recommendations` endpoint
- Context diversity regularization
- SQLite migration
- Off-policy evaluation (OPE)

## License

MIT

# Changelog

All notable changes to GradePulse will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-02

### Added
- **Core Engine:** LinUCB Disjoint and Hybrid algorithms with online clustering
- **Context Vector:** 17-dimensional feature builder (8 student + 9 content features)
- **Anti-Gaming Reward:** Scaling system that resists score manipulation
- **Adaptive Gamma:** Auto-adjusts discount factor based on reward variance
- **Neural Score:** 7-dimension self-diagnostic engine (0-10 per dimension)
- **REST API:** 29 endpoints with JWT authentication (FastAPI)
- **Multi-Tenant:** School → SchoolClass → Student hierarchy
- **Multi-Worker Sync:** File-based locking (`sync.py`) for uvicorn workers
- **Automated Backups:** Periodic brain state backups with rotation and restore
- **Data Ingestion:** CLI tool for CSV/Excel pilot-school data with 17-dim validation
- **Next.js Frontend:** 15 pages — dashboard, students, scores, triage, progress, settings, auth, pricing
- **Teacher Portal:** Streamlit dashboard for quick access
- **Offline HTML Tool:** Standalone teacher tool for low-connectivity environments
- **Sample Data:** 5 students, 56-student large dataset, 101-student pilot-grade dataset
- **Docker:** Multi-stage Dockerfile + docker-compose.yml
- **CI/CD:** GitHub Actions (test on push/PR, Docker build on tags)
- **Deployment Runbook:** VPS setup, HTTPS, backup/restore, upgrades, troubleshooting

### Fixed
- Single-worker constraint resolved (BrainSynchronizer with file-based locking)
- Backup timestamp collision bug (microsecond precision)
- Flaky adaptive gamma test (absolute std threshold)

### Known Limitations
- JSON storage scales to ~50 students (SQLite migration planned for v0.2)
- No monitoring/observability stack yet
- No rate limiting on API endpoints

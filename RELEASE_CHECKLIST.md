# Release Checklist — v0.1.0

Pre-release verification steps for all agents. Complete every item before tagging v0.1.0.

---

## For All Agents

- [ ] Read `CHANGELOG.md` — verify your contributions are listed accurately
- [ ] Read `README.md` — verify Quick Start works for your component
- [ ] Run `git status` — ensure no uncommitted changes in your scope
- [ ] Check `Decision Log` in `TEAM_HANDBOOK.md` — all your decisions are logged

---

## Sam (AI/ML Engineer)

- [ ] Core engine tests pass: `PYTHONPATH=. pytest tests/test_brain.py tests/test_linucb.py tests/test_hybrid.py -v`
- [ ] Neural Score tests pass: `PYTHONPATH=. pytest tests/test_neural_score.py -v`
- [ ] Anti-gaming tests pass: `PYTHONPATH=. pytest tests/test_anti_gaming.py -v`
- [ ] Adaptive gamma tests pass: `PYTHONPATH=. pytest tests/test_adaptive_gamma.py -v`
- [ ] `brain_state.json` loads correctly with demo data
- [ ] `SAM_TECHNICAL_HANDOFF.md` reflects current API (29 endpoints, not 16)
- [ ] `SAM_UNDERSTANDING.md` reflects current test count (179)

---

## Mia (UI/UX Designer)

- [ ] Next.js frontend builds: `cd gradepulse-web && npm run build`
- [ ] All 15 pages render without errors
- [ ] Login/Signup flow works end-to-end
- [ ] Design system tokens consistent across all pages
- [ ] Topic normalization matches backend (uppercase subjects)

---

## Ali (Infrastructure)

- [ ] Docker builds: `docker compose build`
- [ ] Docker starts: `docker compose up -d`
- [ ] Health check passes: `curl http://localhost:8000/health`
- [ ] Multi-worker sync works (test with `WEB_CONCURRENCY=2`)
- [ ] Backup system works (create + list + restore)
- [ ] `.env.example` has all required variables
- [ ] `DEPLOYMENT.md` is accurate and complete

---

## Bob (Data Engineer)

- [ ] Ingestion CLI works: `PYTHONPATH=. python3 ingest.py sample_data/sample_students.csv --school-name "Test School"`
- [ ] Ingestion API works: `POST /ingest` with CSV upload
- [ ] Context vector validates (17-dim)
- [ ] `sample_data/` files are valid and parseable
- [ ] `generate_pilot_data.py` produces valid output

---

## David (QA)

- [ ] Full test suite passes (or document known failures)
- [ ] Load tests pass (if server running)
- [ ] Backup API tests pass
- [ ] Ingestion tests pass
- [ ] Test count documented accurately (179 total)
- [ ] `QA AUDIT REPORT.md` is up to date

---

## Alice (Documentation)

- [ ] `README.md` is release-ready (v0.1.0, all sections complete)
- [ ] `PROJECT_INDEX.md` matches actual file structure
- [ ] `CHANGELOG.md` lists all features and deferrals
- [ ] `RELEASE_CHECKLIST.md` (this file) is complete
- [ ] API reference documents all 29 endpoints
- [ ] Decision Log is summarized (not unbounded)
- [ ] `INVESTOR_CHECKLIST.md` reflects current state

---

## Divine (Founder)

- [ ] Pricing model confirmed (Freemium: Free ₦0 / Starter ₦5,000/mo / School ₦15,000/mo)
- [ ] Pilot school(s) selected
- [ ] Legal/compliance reviewed (FERPA or equivalent)
- [ ] Investor deck updated with current screenshots
- [ ] Release announcement prepared

---

## Pre-Release Verification

Run this before tagging:

```bash
# 1. Run full test suite
PYTHONPATH=. pytest tests/ -v --tb=short

# 2. Start API and verify health
PYTHONPATH=. uvicorn linucb_brain.api.app:app --port 8000 &
curl http://localhost:8000/health

# 3. Test signup and login
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "password": "test123"}'

# 4. Test recommendation
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"student_id": "608041", "top_n": 1}'

# 5. Test triage
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"subject": "MATH"}'

# 6. Verify Docker builds
docker compose build

# 7. Verify frontend builds
cd gradepulse-web && npm run build
```

---

## Release Steps

1. All agents complete their checklist items
2. Divine approves release
3. Update version in `pyproject.toml` to `0.1.0`
4. Commit: `git commit -m "release: v0.1.0"`
5. Tag: `git tag v0.1.0`
6. Push: `git push origin main --tags`
7. GitHub Actions builds Docker images automatically
8. Announce release

---

## Post-Release

- Monitor GitHub Issues for bug reports
- Track Neural Score over time
- Collect teacher feedback
- Plan v0.2 based on real-world usage

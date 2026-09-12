---
tags:
  - decisions
  - operations
  - grade-pulse
created: 2026-08-28
---

# Decision Log

> Cross-role coordination. Newest at top. Summarized by [[Alice — Documentation]] periodically.

---

## Status Summary

| Area | Status | Key Detail |
|---|---|---|
| Single-worker constraint | RESOLVED | `sync.py` — multi-worker safe |
| Data ingestion | VERIFIED | `ingest.py` CLI tested end-to-end |
| Next.js frontend | COMPLETE | 15/15 files |
| Test suite | 172 passed, 7 skipped | 179 total. 7 load tests require server. 0 failures. |
| Documentation | NEEDS UPDATE | Test count stale (162→179), orphaned files missing |
| Flaky test | FIXED | Absolute std threshold added to `_adapt_gamma()` |
| Topic normalization | COMPATIBLE | Case-insensitive matching — uppercase works |
| test_backup.py failures | RESOLVED | Both tests now passing |
| backup.py timestamp bug | RESOLVED | Fixed — `%f` microsecond in `backup.py:124` |
| Pricing model | DECIDED | Freemium: Free ₦0 / Starter ₦5,000/mo / School ₦15,000/mo |
| Demo format | DECIDED | Slides with app screenshots — investor deck built |
| API endpoints | 19 | 16 original + 3 backup endpoints |

---

## Log

### 2026-08-28

| Role | Decision / Change | Affects |
|---|---|---|
| [[Alice — Documentation]] | **Full audit — 14 conflicts found, tagged to agents.** Closed: backup timestamp bug (fixed), pricing/investor (decided). Tagged to [[Sam — AI/ML Engineer]]: update `SAM_UNDERSTANDING.md` (remove decided open questions, fix stale test/API counts, single-worker status). Add `test_backup_api.py` to handoff doc. Tagged to [[Alice — Documentation]]: update PROJECT_INDEX.md & README.md (test count 162→179, add orphaned files). | [[Sam — AI/ML Engineer]], [[Alice — Documentation]] |
| [[Alice — Documentation]] | **Reconciliation pass.** Fixed stale counts across 4 files: PROJECT_INDEX.md (+5 files, API 19, tests 162), README.md (backup system, endpoints, structure), SAM_TECHNICAL_HANDOFF.md (Section 2.7), MIA_UNDERSTANDING_AND_ROLE.md (line 96). Closed test_backup.py item. Logged reconciliation in TEAM_HANDBOOK.md. | All |
| [[Alice — Documentation]] | **Major doc sync.** Updated README (test count, features, project structure). Updated PROJECT_INDEX (sync.py, ingest.py, sample_data, test_sync.py). Added summary section. | All |
| [[Ali — Infrastructure]] | **P0: Single-worker resolved.** `sync.py` with BrainSynchronizer, file-based locking, auto-save. 8 new tests. 73/73 passing. | [[Sam — AI/ML Engineer]], [[David — QA/Testing]], [[Alice — Documentation]] |
| [[Bob — Data Engineer]] | **Ingestion pipeline built.** `ingest.py` CLI — CSV/Excel, 17-dim validation, cleaning, hierarchy mapping. | [[Mia — UI/UX Designer]], [[Sam — AI/ML Engineer]], [[Ali — Infrastructure]] |
| [[Bob — Data Engineer]] | **Sample data generated.** 5 students, 8 content items, Nigerian names, WAEC grades. | [[Mia — UI/UX Designer]], [[David — QA/Testing]] |
| [[Bob — Data Engineer]] | **Topics normalized to uppercase.** Matches existing `student.py`/`school.py`. If [[Sam — AI/ML Engineer]]'s model expects lowercase, mapping needed. | [[Sam — AI/ML Engineer]] |
| [[Alice — Documentation]] | **Created PROJECT_INDEX.md.** Full codebase navigation. | All |
| [[Alice — Documentation]] | **Fixed README test count.** 33 → 65. | [[Sam — AI/ML Engineer]], [[David — QA/Testing]] |
| [[David — QA/Testing]] | **Test count resolved.** Actual 65. Sam's handoff has stale per-file counts. | [[Sam — AI/ML Engineer]], [[Mia — UI/UX Designer]], [[Alice — Documentation]] |
| [[Mia — UI/UX Designer]] | **Flaky test flagged.** `test_adaptive_gamma_restores_when_variance_normalizes` — gamma 0.91 vs expected ≥ 0.94. | [[Sam — AI/ML Engineer]] |
| [[Mia — UI/UX Designer]] | **Next.js complete.** 15/15 files. Dashboard, students, scores, triage, progress, settings. | All |
| [[David — QA/Testing]] | **SOP established.** All findings logged to Decision Log before session ends. | All |

---

## Action Items (Tagged)

### [[Sam — AI/ML Engineer]] — 4 items

- [ ] Update `SAM_UNDERSTANDING.md` Section 8 — remove pricing & investor from open questions (decided by Divine)
- [ ] Update `SAM_UNDERSTANDING.md` Section 5 — single-worker resolved, test count → 179, API count → 19
- [ ] Update `SAM_UNDERSTANDING.md` Section 7 — API count 16 → 19
- [ ] Add `test_backup_api.py` (17 tests) to `SAM_TECHNICAL_HANDOFF.md` Section 2.7, update total to 179

### [[Alice — Documentation]] — 3 items

- [ ] Add `test_backup_api.py` to `PROJECT_INDEX.md`, update test count 162 → 179
- [ ] Update `README.md` project structure test count 162 → 179
- [ ] Add orphaned root files to `PROJECT_INDEX.md` (QA reports, investor checklist, model specs, backups/)

---

*Source: TEAM_HANDBOOK.md*

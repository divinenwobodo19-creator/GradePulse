# QA Audit Report
## Contextual Band Brain Model (GradePulse)

| Field | Value |
|---|---|
| Version | 1.0 |
| Date | 2026-08-22 |
| Auditor | Independent Code Review |
| Build | v0.1.0 |
| Language | Python 3.12 |
| Stack | NumPy, scikit-learn, FastAPI, Streamlit, vanilla JS |

---

## 1. Scope and Methodology

**Coverage: 100% of project source.**
Static line-by-line review of both bandit algorithms, orchestrator (brain.py, 526 LOC), persistence layer, registry, diagnostics, FastAPI layer, Streamlit portal (743 LOC), offline HTML generator (329 LOC), all 7 test suites (590 LOC), configs, plus forensic inspection of live production state (brain_state.json, 1.86 MB). Cross-checked against the project's own prior QA claims.

| Layer | Files Reviewed |
|---|---|
| Algorithms | core/linucb.py, core/linucb_hybrid.py, core/context.py, core/clustering.py, core/reward.py |
| Orchestration | linucb_brain/brain.py, storage.py, registry.py, utils.py, all __init__.py |
| Models | student.py, content.py, session.py, school.py |
| Diagnostics | neural_score.py, report.py |
| Interfaces | api/app.py, api/schemas.py, teacher_portal.py, generate_offline.py |
| Tests | 7 files, 28 test functions |
| Config/Data | pyproject.toml, requirements.txt, class_config.json, brain_state.json |

---

## 2. Executive Summary

This is a **genuinely sound algorithm wrapped in fragile plumbing, documented beyond its actual edges**. The core bandit math (LinUCB disjoint + hybrid variants) is correctly implemented and numerically verified. The engineering instincts are good -- thread locks, tenant isolation, tested persistence paths. But the system **loses learned knowledge on every restart**, **silently corrupts aggregates through UI workflows**, ships an **offline tool that violates its own core guarantee**, and carries **documentation that demos features which do not exist** -- fatal in front of a technical investor.

| Category | Verdict |
|---|---|
| Algorithm correctness | PASS -- no math bugs found |
| State durability | FAIL -- cohort learning wiped each restart |
| Data integrity (UI paths) | FAIL -- duplicates, orphans, silent loss |
| Documentation accuracy | FAIL -- phantom files/endpoints/metrics |
| Test coverage | PARTIAL -- 28 tests, real but weakly asserted |
| Production readiness | NOT READY (pitch-demo: conditional pass) |

**Release Verdict:** Not production-ready. Pitch-demo-ready after Phases 0+1+2 minimal fix set.

---
## 3. Verified Strengths (What Can Be Trusted)

These areas have been confirmed correct through code review and cross-verification with the project's own numerical QA:

| # | Area | Detail |
|---|---|---|
| S1 | Disjoint LinUCB math | Sherman-Morrison incremental inverse exact; A_inv == inv(A) verified; L2-initialized arms; correct UCB form |
| S2 | Hybrid LinUCB + clustering | Vectorized select across arms; lazy inverse recomputation; correct contribution bookkeeping on A0 |
| S3 | Reward pipeline | Clipped [-1, 1] everywhere; churn hard-caps at -1.0; consistent in both calculate_reward() and calculate_multi_objective_reward() |
| S4 | Thread safety | RLock re-entrancy in brain.py; per-model locks in linucb.py and linucb_hybrid.py; ClusteringEngine lock |
| S5 | Multi-tenant identity | Surrogate UUID keys; same label (JSS1A) legal across schools; collision enforced within school only |
| S6 | Assessed-only triage | Unassessed students excluded; full response shape on empty; WAEC boundaries exact (0.39/0.40/0.74/0.75) |
| S7 | Registry migration | Legacy flat config auto-migrates to school-scoped schema; idempotent; tested |
| S8 | Internal QA culture | Prior QA_REPORT candidly flags own weaknesses -- rare and valuable |

---

## 4. Findings Inventory

### 4.1 CRITICAL (S1) -- Data Loss or Corruption

**F1: Hybrid cluster state never persisted (storage.py)**
- Location: storage.py lines 43-54 (save) and 95-105 (load)
- Evidence: save_brain() serializes A0, A0_inv, b0, and linucb_arms, but never Ak, bk, Ak_inv, n_clusters, or last_cluster_id. Load returns default identity matrices.
- Live confirmation: brain_state.json keys are [students, contents, sessions, model_type, alpha, gamma, update_count, auto_diagnose_every, A0, A0_inv, b0, linucb_arms] -- no cluster state. Model is hybrid with real data (20 students, 21 arms, 3120 sessions).
- Impact: Every restart wipes all cohort-level learning. Students reassigned to random clusters. Forgetting that persists across the entire session history.
- Also missing from persistence: reward_weights, clustering centers, Brain.cumulative_regret, Brain.total_predicted_reward, last_neural_score.

**F2: Nondeterministic cold-start clustering**
- Location: clustering.py line 35: hash(student_id) % n_clusters
- Evidence: Python salts string hashes per process (PYTHONHASHSEED). Same student lands in different cohorts after every restart until MiniBatchKMeans initializes.
- Impact: Two fresh instances loaded from the same checkpoint will disagree on cluster assignments. Reproducibility broken for debugging and demo.

**F3: Delete class orphans students**
- Location: registry.py remove_class() line 151-157; teacher_portal.py lines 212-217
- Evidence: remove_class() only removes the class entry from the registry. The portal's Delete Class button calls remove_class() then persists the registry, but never touches brain.students. Students with that class_id become invisible in class-scoped views but remain in brain_state.json.
- Impact: Students vanish from portal views; data persists silently. No warning, no reassignment, no scrub.

**F4: Duplicate-score double counting**
- Location: teacher_portal.py lines 390-478
- Evidence: Score editor pre-fills each student's last score (line 393). Every Submit builds entries for ALL non-absent students (lines 452-463) and calls bulk_update(). If a teacher opens scores, clicks Submit without changing anything, or re-opens to check, the full class's scores are appended again as a new test round.
- Impact: Triages based on averages get inflated by duplicate entries. Teacher error silently corrupts aggregates with no undo.

**F5: Offline tool silent data loss**
- Location: generate_offline.py lines 237-260 (submitScores JS function)
- Evidence: submitScores() mutates the in-memory DATA JS object. No persistence mechanism exists -- no download, no localStorage, no export. The message 'Scores saved!' is misleading; closing the tab loses everything.
- Impact: Teacher enters scores, sees results, closes browser. All work lost. Regenerating from brain_state.json does not include it.

**F6: bulk_update drops explicit 0.0 rewards**
- Location: brain.py line 387: entry.get('reward') or entry.get('score', 0.0)
- Evidence: In Python, 0.0 is falsy. An explicit reward of 0.0 falls through to the score fallback. If both reward=0.0 and score are present, 0.0 is still returned (harmless). But if only reward=0.0 is provided, it falls through to score which may be absent or different.
- Impact: Minor data integrity issue. Portal path unaffected (uses score key only). API paths could be affected.

---

### 4.2 HIGH (S2) -- Credibility or Claim Accuracy

**F7: Phantom features and endpoints in documentation**
- Location: README.md Quick Start + Project Structure; INVESTOR_CHECKLIST.md Steps 2/3/6/7
- Evidence: Both files reference demo_investor.py, dashboard.py, docker-compose.yml, oulad_preprocessor.py, oulad_brain_run.py, examples/, figures/ -- NONE of these exist in the project. INVESTOR_CHECKLIST.md Step 3 demos GET /recommend/S001 and GET /neural-score endpoints that do not exist in api/app.py (would return 405 and 404).
- Also: all absolute paths point to /home/jazzman/Documents/trae_projects/ which is stale (project now lives at Desktop/N - Tech).
- Impact: An investor or technical evaluator following the README or checklist will hit missing files and 404s within minutes. Fatal credibility gap.

**F8: Test count contradictions**
- Locations: INVESTOR_CHECKLIST.md says '24 passed'; QA_REPORT.md says '29/29 pass'; portal footer button says 'Run all 20 tests'
- Actual count: 28 test functions across 7 files (test_linucb:3, test_hybrid:3, test_brain:4, test_integration:1, test_api:6, test_multi_school:8, test_neural_score:3).
- Impact: Minor but shows sloppy maintenance of meta-documents.

**F9: Offline tool violates assessed-only triage guarantee**
- Location: generate_offline.py JS triage() function, lines 147-161
- Evidence: JS triage() maps over ALL students and tiers them using predictGrade(), which falls back to performance (cold-start prior) when no grade_history exists. Brain.triage() excludes unassessed students (n_attempts == 0 check). MODEL_SPEC.md explicitly states 'no false F9s'.
- Impact: The offline tool shows brand-new students with zero scores as 'F9 remediation' based on their cold-start value. Directly contradicts the documented design guarantee.

**F10: Grade prediction mislabeling**
- Locations: brain.py predict_grade() line 301; triage() line 436; Neural Score dimension 'Grade Prediction'
- Evidence: predict_grade() returns the arithmetic mean of historical scores for a subject, falling back to the static performance_score. The LinUCB bandit plays no role in prediction. The word 'predicted' in triage output and 'Grade Prediction' in the Neural Score imply model-driven forecasting.
- Impact: The bandit only powers content recommendations, not assessment. The label oversells what is computed. A technical probe during pitch would expose this gap.

---
### 4.3 MEDIUM (S3) -- Algorithmic, API, or Robustness

**F11: performance_score never updated by Brain.update()**
- Location: brain.py update() method, lines 229-299; student.py dataclass comment '# rolling average'
- Evidence: update() appends to grade_history, increments session_count, updates content stats -- but never touches student.performance_score. The dataclass comment says 'rolling average' but nothing rolls it. The offline tool evolves it differently: (performance + score) / 2.
- Impact: The 'performance' context feature in build_context() (context.py line 24) stays frozen at its initial value for the entire session history. Grade-trend slope partially compensates, but a design intent mismatch exists.

**F12: Neural Score integrity issues**
- Locations: neural_score.py lines 82-95 (context check mutates alpha), line 143 (balance_score), lines 99-106 (precision_score)
- Evidence: (a) balance_score is hard-coded to 7.5 as a placeholder, never computed. (b) precision_score measures fraction of sessions above the global mean reward, which hovers near 50% by construction regardless of model quality. (c) context-sensitivity check temporarily sets brain_instance.alpha = 0.05 while calling recommend(), which under the RLock blocks concurrent API calls. (d) exploration diagnostics call brain.recommend() which increments times_recommended counters as a side effect.
- Impact: Two of seven diagnostic dimensions are unreliable (balance, precision). Diagnostics contaminate the model they measure.

**F13: Hybrid algorithm deviates from Li et al. 2010**
- Location: linucb_hybrid.py lines 64-66 (beta_hat), lines 93-97 (noise + rec_penalty)
- Evidence: beta_hat = (global + cluster) / 2 is an ad hoc average not in Algorithm 2. Variance estimate uses global A0 only, ignoring cluster contribution. Two undocumented heuristics are injected: rec_penalty = 2 * alpha * log1p(rec_count) penalizes frequently recommended arms; Gaussian noise N(0, 0.1) is added to all UCB scores in select(). Neither is in the paper.
- Impact: The algorithm is a reasonable heuristic but its behavior diverges from the cited reference. Do not claim Li et al. 2010 guarantees in investor pitch; a technical evaluator could push on this.

**F14: API robustness gaps**
- Location: api/app.py lines 25-48, 83-84, 132-169
- Evidence: (a) Global brain loaded at module import (line 83); if BRAIN_STATE_PATH file is missing and no checkpoints exist, it seeds demo data and runs forever. (b) No lifespan handler; no auto-save on shutdown; every /update and /recommend mutation is lost unless someone explicitly POSTs /save. (c) No school_id/class_id on any endpoint -- the school-scoped model is portal-only; API clients bypass tenancy. (d) No authentication; anyone can POST /update to poison rewards or POST /save to overwrite state. (e) Multiple uvicorn workers each hold separate in-memory brains that silently overwrite each other's JSON.
- Impact: API state durability and tenant isolation are absent. Multi-worker deployment silently corrupts.

**F15: Legacy alpha restores near-pure exploitation**
- Location: brain_state.json (alpha=0.06613); storage.py load_brain()
- Evidence: brain_state.json was saved with alpha=0.066 from the old alpha_decay era. New code has fixed alpha (default 1.0). load_brain() restores the persisted alpha value of 0.066, which means the model runs in near-pure-exploitation mode. No documentation of this legacy behavior or path to reset.
- Impact: Existing saved state silently degrades exploration. New deployments inherit degraded behavior.

**F16: JSON storage scaling ceiling**
- Locations: storage.py save_brain(); brain_state.json (1.86 MB with 3120 sessions)
- Evidence: Sessions are serialized fully as JSON arrays. The 3120 sessions dominate the 1.86 MB file. MODEL_SPEC.md itself admits the format dies at roughly 50 students x weekly updates. At 3000+ sessions, load time becomes noticeable.
- Impact: Performance degrades with scale. Not blocking for demo; blocking for production.

**F17: Regret metric is not regret; tie-breaking noise**
- Location: brain.py lines 196-199 (cumulative_regret); lines 169-178 (disjoint tie-break)
- Evidence: cumulative_regret += (best_ucb - mean(ucbs)) measures UCB gap between selected and average arm, not true regret (optimal - actual). Tie-breaking uses np.random.normal(0, 1e-9), making recommendations nondeterministic even with identical inputs and no exploration.
- Impact: Misleading metric; nondeterminism complicates debugging and reproducibility.

**F18: Cluster semantics inconsistency**
- Locations: brain.py recommend() lines 180-182; clustering.py
- Evidence: In the hybrid recommend() top_n>1 path, cluster_id is computed from build_context() using the FIRST remaining item's arm features (line 180-182). Since arm features differ across items, the cluster assignment depends on dict iteration order. A different content ordering puts the same student in a different cohort. Additionally, clustering operates on the 17-dim combined (shared + arm) vector, so cohorts reflect content interactions, not pure student similarity.
- Impact: Subtle nondeterminism in cluster-dependent recommendations; cohort semantics are interaction-based not student-based (possibly acceptable but undocumented).

---

### 4.4 LOW (S4) -- Cosmetic or Minor

**F19: Grade label parsing gaps**
- Location: school.py split_label() line 52-58; class_config.json
- Evidence: split_label() matches only unspaced prefixes (JSS1, not JSS 1). class_config.json shows 'JSS 1' parsed as grade_level='' arm='JSS 1' and '300 LEVEL' parsed as grade_level='' arm='300 LEVEL'. Any grade-level grouping feature would fail for these labels.

**F20: Three inconsistent grading presentations**
- Locations: teacher_portal.py nigerian_grade() (returns A-F); generate_offline.py JS nigerianGrade() (returns A1-F9); teacher_portal.py printable report legend (WAEC bands with meanings)
- Evidence: Portal letters (A/B/C/D/E/F) do not match offline tool's WAEC labels (A1/B2/B3/C4/C5/C6/D7/E8/F9) or the report legend bands. Three different systems in one project.

**F21: Dependency drift between pyproject.toml and requirements.txt**
- Location: pyproject.toml vs requirements.txt
- Evidence: pyproject.toml lists numpy>=1.20, scipy>=1.7, fastapi>=0.70, uvicorn>=0.15, pydantic>=1.8, scikit-learn>=1.0. requirements.txt lists numpy>=1.23, scipy>=1.10, fastapi>=0.100, uvicorn>=0.20, pydantic>=2.0, plus pandas, matplotlib, kaggle, streamlit, plotly, python-multipart, requests, python-dotenv. Version floors differ significantly; streamlit (required by teacher_portal.py) is only in requirements.txt.

**F22: Dead fallback to deleted school_brain_state.json**
- Location: teacher_portal.py lines 81-84
- Evidence: get_brain() checks for school_brain_state.json if brain_state.json is missing. Prior QA removed the file but the fallback code remains. If the file ever reappears, the portal would load a different state than the API.

**F23: Weak test assertions**
- Locations: test_api.py lines 51, 65, 81 (accept 400 as pass); test_integration.py line 86 (n_clusters round-trip)
- Evidence: API tests assert response.status_code in [200, 400] -- a 400 (error) is treated the same as 200 (success). test_integration asserts loaded_brain.n_clusters == brain.n_clusters which passes only because both default to 5; it would not catch a bug where persistence fails to save/restore the value.

**F24: Minor items**
- brain.py line 292: content.times_recommended = max(times_recommended, times_rewarded) couples counters unnaturally
- linucb.py discounted branch: O(d^3) full inverse recomputation per update vs O(d^2) Sherman-Morrison
- Long-running sessions: no periodic inv(A) refresh; Sherman-Morrison accumulates float drift over thousands of updates
- API /summary endpoint reports update_count as 'total_sessions' (cosmetic mislabel)
- teacher_portal.py line 393: editable Student column silently renames students on any score submit
- Offline HTML name editor: names injected into innerHTML without escaping (self-XSS only in local file)
- Subject-key pollution: 'Math' vs 'Maths' vs trailing spaces treated as different keys, fragmenting triage

---
## 5. Test Suite Assessment

### Coverage Summary

| File | Tests | Area |
|---|---|---|
| test_linucb.py | 3 | Arm selection, Sherman-Morrison, alpha=0 exploitation |
| test_hybrid.py | 3 | Hybrid init, recommend+update, save/load |
| test_brain.py | 4 | Add entities, recommend, update, save/load roundtrip |
| test_integration.py | 1 | Full pipeline: init, add, recommend, update, save, load, verify |
| test_api.py | 6 | All API endpoints (root, summary, student, content, recommend, reward) |
| test_multi_school.py | 8 | Triage boundaries, assessed-only, school/class scoping, migration |
| test_neural_score.py | 3 | Dimension ranges, weighted sum, report rendering |
| **Total** | **28** | |

### Strengths of the Test Suite
- Triage boundary tests are precise: 0.39/0.40/0.74/0.75 tested with exact tier assertions (test_multi_school.py)
- Assessed-only guarantee tested: unassessed student excluded from tiering, scope flag verified
- Multi-tenant isolation tested: same label across schools, collision enforcement within school
- Migration idempotency tested: legacy flat config migrates correctly, double-migrate produces same result
- Save/load roundtrip verified for both disjoint and hybrid models

### Weaknesses of the Test Suite
- **No cluster persistence test**: Would catch F1 immediately if it tested Ak/bk roundtrip
- **Weak API assertions**: Accepting 400 as pass (test_api.py lines 51, 65, 81) masks regressions
- **Accidental n_clusters pass**: test_integration.py:86 asserts roundtrip but both sides use default 5
- **No negative-path storage tests**: What happens loading a corrupt file, wrong model_type, or missing keys
- **No concurrency tests**: Brain thread safety is implemented but never tested under contention
- **Shared global state**: API tests mutate the module-global brain_instance with no isolation or cleanup
- **28 tests total**: Adequate for current scope but below 29 (QA_REPORT claim) and 24 (checklist claim)

---

## 6. Live State Forensics (brain_state.json)

Direct inspection of the production state file confirms several findings:

| Property | Value |
|---|---|
| model_type | hybrid |
| Students | 20 |
| Content items | 21 |
| Sessions (serialized) | 3120 |
| update_count | 3120 |
| alpha | 0.06613 (legacy decayed) |
| gamma | 1.0 |

**Keys present:** students, contents, sessions, model_type, alpha, gamma, update_count, auto_diagnose_every, A0, A0_inv, b0, linucb_arms

**Keys absent:** Ak, bk, Ak_inv, n_clusters, last_cluster_id, reward_weights, clustering_centers, cumulative_regret, last_neural_score

This confirms **F1 (cluster loss)** and **F15 (legacy alpha)** against real production data. The model is hybrid, so the missing Ak/bk matrices mean every restart destroys cohort learning for all 20 students.

**class_config.json inspection:** Labels '300 LEVEL' and 'JSS 1' both have grade_level='' because split_label() only matches unspaced prefixes (confirms **F19**).

---

## 7. Risk Matrix

| Risk | Likelihood | Impact | Severity |
|---|---|---|---|
| Investor follows checklist, hits missing file or 404 | High | Critical | RED |
| Server restart mid-term loses all cohort learning | Certain | High | RED |
| Teacher double-submits, corrupts triage averages | High | Medium-High | RED |
| Offline tool shows unassessed student as F9 | Medium | Reputation | AMBER |
| Offline tool silently loses all teacher work | Certain | Medium | AMBER |
| Multi-worker deployment forks brain state | Medium | High | AMBER |
| API client poisons rewards (no auth) | Low | High | AMBER |
| JSON file bloats beyond 5MB at scale | Medium | Low-Medium | YELLOW |

---

## 8. Remediation Roadmap

### Phase 0 -- Documentation Truth Pass (HIGH, quick)
- Remove or create all phantom files referenced in README and INVESTOR_CHECKLIST
- Fix API endpoint examples (POST /recommend, remove /neural-score or add it)
- Correct absolute paths to current location
- Reconcile test counts (actual: 28)
- Clean dead fallback to school_brain_state.json in portal

### Phase 1 -- Durability (CRITICAL, core fix)
- Serialize Ak, bk, Ak_inv, n_clusters, last_cluster_id, reward_weights in storage.py
- Persist kmeans.cluster_centers_ for clustering init on reload
- Backward-compatible load with defaults for old files
- Deterministic cold-start: SHA-256(student_id) replaces salted hash()
- Reset/normalize legacy alpha on load or add documentation
- Regression tests: cluster roundtrip, hash determinism, legacy alpha path

### Phase 2 -- Data Integrity (HIGH)
- Cascade delete: removing a class deletes its students from brain + registry
- Portal confirmation dialog showing student count before delete
- Auto-backup brain_state.json before any destructive operation
- Duplicate-score guard: clear form after submit, no pre-fill, or confirm Nth-test label
- bulk_update None-checks for explicit 0.0 rewards
- Offline tool: triage parity with assessed-only rule; add export/download; add loss warning

### Phase 3 -- Honesty and Diagnostics (MEDIUM)
- Relabel 'predicted' to 'Average score' in triage output and reports
- Compute balance_score from session data or remove dimension
- Replace precision_score with meaningful metric (e.g., avg reward of recommended vs overall)
- Make context-sensitivity check non-mutating (compute UCB without flipping alpha)
- Add track=False option to recommend() for diagnostic use
- Decide performance_score policy: implement rolling update or fix the comment

### Phase 4 -- API Robustness and Tenancy (MEDIUM)
- FastAPI lifespan handler: load at startup, auto-save on shutdown
- Document or enforce uvicorn --workers 1
- Optional school_id/class_id params on /students, /recommend, /update
- Add GET /schools and GET /classes/{school_id} read endpoints
- Validate student tenancy matches request on recommend/update
- Optional: API key auth for /update and /save

### Phase 5 -- Deferred (post-pitch)
- SQLite for sessions/state (addresses F16 scaling ceiling)
- Subject-key canonicalization at write time (Math vs Maths)
- Periodic inv(A) refresh to prevent float drift
- Concurrency test suite
- Grade presentation unification across portal/offline/report

---

## Open Decisions

1. **performance_score**: Implement rolling update in Brain.update() vs freeze-by-design?
2. **Phantom docs**: Build the missing files (demo_investor.py, dashboard.py, etc.) vs strip references from README/checklist?
3. **Offline tool scope**: Full parity with portal (bidirectional persistence) or add prominent 'this is a preview-only tool' warning?

---

*End of QA Audit Report*
# GradePulse QA Report — Model & Portal Credibility Audit

Date: 2026-08-14 · Scope: model internals (LinUCB/Hybrid), Brain API, registry,
portal UI flows, persistence. Method: static review + 29 automated tests +
numerical verification + AppTest UI simulations.

## 1. Verified as CORRECT (what the model can be trusted on)

| Area | Result |
|---|---|
| LinUCB math (Sherman–Morrison + UCB) | Verified numerically against hand-computed A, A_inv, b — exact match, `A_inv == inv(A)` |
| Exploration behavior | alpha=0 → pure exploit; alpha=100 → flips to the higher-variance arm (true UCB uncertainty) |
| Reward function | Always clipped to [-1, 1]; churn hard-caps at -1.0 |
| Duplicate student IDs | `add_student` returns the existing record — no silent overwrite |
| `bulk_update` (portal submit path) | Subject → auto-created content arm; zero scores stored correctly; `processed` counts accurate |
| `recommend` | top_n distinct arms; topic filter exact; empty-set raises; hybrid/cluster path consistent |
| save/load fidelity | students, contents, sessions, update_count, A0, arm matrices, predictions all round-trip exactly |
| triage | WAEC boundaries exact (0.39→F, 0.40→E, 0.74→E, 0.75→A); assessed-only with `scope` flag; full shape on empty |
| School/class identity | Same label ("JSS1A") legal across schools, collision enforced within a school; students carry both IDs; legacy migration idempotent |
| Portal flows (AppTest) | Onboarding (create school → create class → add student → scores → report): 0 exceptions end-to-end |
| Neural score | All 5 dimensions in [0,10]; weighted correctly |
| Automated suite | 29/29 pass |

## 2. Fixed this session

**HIGH — crash on "Create School" (and Create Class / Delete Class / demo loader)**
```
StreamlitAPIException: st.session_state.selected_school_id cannot be modified
after the widget with key `selected_school_id` is instantiated
```
Root cause: buttons wrote to widget-keyed session state *after* the sidebar
selectboxes were instantiated. Fix: all programmatic selection changes now go
through `pending_school_id` / `pending_class_id`, applied at the top of the
script before any widget exists. Verified: all four paths run clean.

## 3. Open anomalies — ranked by credibility impact

### HIGH
1. **Cluster knowledge evaporates on restart.** Hybrid `Ak`/`bk` matrices are
   never serialized, and `n_clusters` is not round-tripped (3 → 5 on load).
   Everything learned at cohort level resets to identity/zeros on reload.
2. **Delete Class silently orphans students.** Removing a class from the
   registry leaves its students holding a dangling `class_id` (verified: 16
   students vanish from class-scoped views, still present in `brain_state.json`).
   No warning, no reassignment, no scrub.
3. **Duplicate-score double-counting.** The score editor pre-fills the last
   score; re-submitting appends again → the same value counted twice, and
   triage (a plain mean) bends toward repeated entries. Teacher error silently
   corrupts aggregates.
4. **Triage is a mean, not a prediction.** `predict_grade` = historical
   average; the LinUCB/Hybrid bandit plays zero role in assessment and reports —
   it only powers content recommendation. The "predicted" label in reports is
   technically an average of past scores.

### MEDIUM
5. **API is not multi-tenant.** `/students`, `/content`, `/recommend`,
   `/update` carry no `school_id`/`class_id` — the school-scoped model is
   portal-only; API clients bypass tenancy.
6. **Cluster assignment is nondeterministic.** Uninitialized clusters use
   `hash(student_id) % n_clusters`; Python string hashing is randomized per
   process (PYTHONHASHSEED) and Python 3.13+ defaults to salted hashes — same
   student lands in a different cohort after every restart.
7. **Hybrid deviates from Li et al. (2010).** `beta_hat = (global + local)/2`
   and variance estimated via global A0 only — a defensible approximation, but
   not Algorithm 2; don't cite the paper's guarantees.
8. **Mismatched session semantics.** `/summary` reports `update_count` as
   "total_sessions"; one score entry = one session. Cosmetic but misleading.
9. **Subject deletion is cosmetic.** Removing a subject chip leaves
   `grade_history` intact — the subject still appears in Class Groups/Reports.
10. **Legacy subject-key pollution.** Same topic exists as "Math", "Maths",
    "Basic Science - Week 1 " (trailing space) — subjects are keyed verbatim, so
    one real subject can span several keys and fragment triage.

### LOW
11. `bulk_update`: `entry.get("reward") or entry.get("score")` — an explicit
    reward of 0.0 is dropped (falls through to score). Portal unaffected.
13. Portal `get_brain` falls back to `school_brain_state.json` when
    `brain_state.json` is missing, but always *saves* to `brain_state.json` — a
    crash between the two can create a divergent pair of state files.

## 2c. Resolved by dead-code removal (repo cleanup)

1. `linucb_brain/brain.py_tmp` (orphaned temp copy inside the package) —
   deleted.
2. Thompson Sampling (`core/lints.py` + all `model_type="ts"` branches in
   `brain.py` and `storage.py`) — unused by the portal and API (both hybrid);
   removed. Supported model types are now `disjoint` and `hybrid`.
3. `tests/debug_brain.py` and `tests/stress_test.py` — manual scripts, not
   pytest tests; `stress_test.py` was even slowing collection. Deleted.
4. `school_brain_state.json` (stale 2.4 MB pre-migration state) — deleted;
   resolves the dual-state-file hazard entirely (LOW-13).

## 2b. Resolved by design decision (lean-model simplification)

1. **Meta-learner removed** (`tune_parameters` + `POST /tune` + its test):
   auto-tuning of alpha/gamma was an OULAD-simulation feature with no caller in
   the teacher workflow and was the source of the dead-code bug at
   `brain.py:514-535`. Gone entirely.
2. **Alpha is fixed** (`alpha_decay` default 1.0, decay code removed):
   exploration no longer fades mid-term; behavior is reproducible run to run.
3. **Auto-diagnostics disabled by default** (`auto_diagnose_every=0`, with a
   guard so 0 means "never run"). Neural scoring remains available as a
   read-only diagnostic and never feeds back into the model.

## 4. Bottom line

No math bugs found in the core bandit: matrices, UCB selection, reward bounds,
and persistence of the primary arm/global parameters are all numerically
sound. The credibility gaps are **engineering** ones: durability of cluster
state, delete-path data integrity, duplicate-submission safeguards, and the
gap between "recommender intelligence" and what the reports actually show
(averages, not model predictions).
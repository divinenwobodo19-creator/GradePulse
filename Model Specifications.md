# GradePulse — Data Model Specification

School-scoped multi-tenant design so no two institutions can ever collide,
even when they both have a "JSS1A".

## Identity architecture

IDs are **surrogate keys** (UUID fragments). Labels are *display only*.

```
School (school_id) ──> SchoolClass (class_id, school_id) ──> Student (student_id, class_id, school_id)
```

| Entity | Key | Notes |
|---|---|---|
| `School` | `school_id` (UUID[:8]) | Name normalized (trim / collapse spaces / upper) |
| `SchoolClass` | `class_id` (UUID[:8]) | `grade_level` parsed from label (JSS1–SSS3), `arm` local |
| `Student` | `student_id` | `school_id` + `class_id` always set (no orphans) |

Two schools may both have a class labelled "JSS1A" — legal, because the
`class_id` UUIDs differ. Uniqueness of labels is enforced **within school
scope only** (`add_class` returns `None` on label collision in the same
school).

`SchoolClass.split_label()` maps labels like `JSS1A` → `grade_level="JSS1"`,
`arm="A"`. Display = `grade_level + arm`.

## Storage

Two JSON files (SQLite deferred post-pitch — JSON dies at roughly ~50
students × weekly updates):

| File | Contents |
|---|---|
| `class_config.json` | Registry: `{"term_subjects": [...], "schools": [{school_id, name, classes: [{class_id, label, grade_level, arm}]}]}` |
| `brain_state.json` | LinUCB brain: students (with `school_id`, `class_id`), contents, sessions, model matrices |

Legacy flat config `{"term_subjects": [...], "classes": ["JSS1A", ...]}`
auto-migrates on load into a default school **MY SCHOOL** (idempotent,
in-memory, written back on next save). The one-off migration already ran:
16 orphan students → MY SCHOOL / JSS 1, 4 "300 LEVEL" students → MY SCHOOL /
300 LEVEL (backup at `brain_state.json.bak`).

## Triage semantics

- Reports/triage include **only** students with ≥1 actual score in the
  subject (`n_attempts > 0`). `performance_score` is a cold-start fallback
  used **only** by the recommender, never by triage.
- Students without subject data appear in a **"Not yet assessed"** section
  (populated but not graded) — no false F9s.
- Absolute WAEC thresholds: `< 0.40` remediation (F9) · `0.40–0.74`
  on_track · `>= 0.75` ahead (A1).
- `triage()` always returns the full shape — `total_students`, `tiers`
  (all three keys even when empty), `scope: "assessed_only"`.

## Domains & persistence notes

- `GRADE_LEVELS = ["JSS1","JSS2","JSS3","SSS1","SSS2","SSS3"]`
  (`linucb_brain/models/school.py`).
- Term subjects: open question — leaning school-scoped list backed by a
  global dictionary of standard subjects (e.g. Maths, English, Science,
  History).
- Score history is per `(student, subject key)`; subject keys are used
  verbatim today, so clean-up of legacy labels ("Math" vs "Maths",
  trailing spaces) is a UI concern, not a model one.
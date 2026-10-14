# API Reference — GradePulse v0.1.0

Base URL: `http://localhost:8000`

All endpoints (except auth and health) require a JWT token in the `Authorization` header:
```
Authorization: Bearer <your-token>
```

---

## Authentication

### POST /auth/signup

Create a new user account.

**Request:**
```json
{
  "email": "teacher@school.com",
  "password": "password123",
  "school_name": "Lagos Model School"
}
```

**Response (200):**
```json
{
  "id": "a1b2c3d4",
  "email": "teacher@school.com",
  "school_id": "e5f6g7h8",
  "school_name": "LAGOS MODEL SCHOOL",
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

---

### POST /auth/login

Login with existing credentials.

**Request:**
```json
{
  "email": "teacher@school.com",
  "password": "password123"
}
```

**Response (200):**
```json
{
  "id": "a1b2c3d4",
  "email": "teacher@school.com",
  "school_id": "e5f6g7h8",
  "school_name": "LAGOS MODEL SCHOOL",
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

---

### GET /auth/me

Get current authenticated user.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "id": "a1b2c3d4",
  "email": "teacher@school.com",
  "school_id": "e5f6g7h8",
  "school_name": "LAGOS MODEL SCHOOL"
}
```

---

## Schools

### GET /schools

List all schools the user has access to.

**Response (200):**
```json
[
  {
    "school_id": "e5f6g7h8",
    "name": "LAGOS MODEL SCHOOL",
    "classes": [
      {"class_id": "i9j0k1l2", "label": "JSS1A"}
    ]
  }
]
```

---

### POST /schools

Create a new school.

**Request:**
```json
{
  "name": "Abuja Prep Academy"
}
```

**Response (200):**
```json
{
  "school_id": "m3n4o5p6",
  "name": "ABUJA PREP ACADEMY",
  "classes": []
}
```

---

### PUT /schools/{school_id}

Update a school name.

**Request:**
```json
{
  "name": "New School Name"
}
```

---

### DELETE /schools/{school_id}

Delete a school and all its classes/students.

**Response (200):**
```json
{"status": "deleted"}
```

---

## Subjects

Each school has its own subject list. It drives the subject pickers; it does not restrict which subjects `/bulk-update` accepts.

### GET /subjects

```json
{ "subjects": ["MATH", "ENGLISH", "SCIENCE", "HISTORY"] }
```

### PUT /subjects

Admin only. Replaces the whole list. Names are trimmed, upper-cased and de-duplicated; at most 40 subjects of up to 40 characters each. An empty result returns 400.

```json
{ "subjects": ["Mathematics", "English Language", "Basic Science"] }
```

---

## Classes

### GET /classes/{school_id}

List all classes in a school.

**Response (200):**
```json
[
  {
    "class_id": "i9j0k1l2",
    "label": "JSS1A",
    "grade_level": "",
    "arm": ""
  }
]
```

---

### POST /classes/{school_id}

Create a new class.

**Request:**
```json
{
  "label": "JSS2B"
}
```

---

### PUT /classes/{school_id}/{class_id}

Update a class.

---

### DELETE /classes/{school_id}/{class_id}

Delete a class and its students.

---

## Students

A student is identified by `student_id` **within the caller's school**; two schools can use the same ID. `grade_history` (`{subject: [scores]}`, oldest first) and `performance_score` (mean of the five most recent scores) are derived from the recorded scores. A student with an empty `grade_history` has no score yet, and `performance_score` is then just the starting value given at creation. Deleting archives the student.

### GET /students

List students (filtered by school/class).

**Query Parameters:**
- `school_id` (optional) — filter by school
- `class_id` (optional) — filter by class

**Response (200):**
```json
[
  {
    "student_id": "S001",
    "name": "Chinwe Okoro",
    "grade_history": {"MATH": [0.65, 0.72, 0.78]},
    "performance_score": 0.72,
    "current_topic": "MATH",
    "metadata": {}
  }
]
```

---

### POST /students

Add a new student.

**Request:**
```json
{
  "student_id": "S001",
  "name": "Chinwe Okoro",
  "performance_score": 0.75,
  "current_topic": "MATH",
  "metadata": {"class_id": "i9j0k1l2"}
}
```

---

### PUT /students/{student_id}

Update a student.

**Request:**
```json
{
  "name": "Chinwe Okoro (Updated)",
  "current_topic": "SCIENCE",
  "class_id": "i9j0k1l2"
}
```

---

### DELETE /students/{student_id}

Delete a student.

---

## Content

### POST /content

**Operator only.** Requires `X-Operator-Key`. The content catalogue is shared by every school.

Add a content item.

**Request:**
```json
{
  "content_id": "C001",
  "title": "Algebra Fundamentals",
  "topic": "MATH",
  "difficulty": 2,
  "content_type": "video"
}
```

**Content Types:** `video`, `quiz`, `exercise`, `reading`

**Difficulty:** 1-5 (1=easiest, 5=hardest)

---

## Brain Operations

### POST /recommend

**Off by default.** Returns 404 ("Content suggestions are switched off on this server") unless the server runs with `RECOMMENDATIONS_ENABLED=true`. `GET /health` reports the setting as `features.recommendations`.

Get content recommendations for a student.

**Request:**
```json
{
  "student_id": "S001",
  "topic": "MATH",
  "top_n": 3
}
```

**Response (200):**
```json
{
  "content_id": "C002",
  "title": "Advanced Calculus",
  "topic": "MATH",
  "difficulty": 5,
  "content_type": "quiz",
  "times_recommended": 12,
  "times_rewarded": 8,
  "avg_reward": 0.72
}
```

---

### POST /update

Update the model with a reward signal.

**Request:**
```json
{
  "student_id": "S001",
  "content_id": "C001",
  "reward": 0.85
}
```

**Reward Range:** -1.0 to 1.0

---

### POST /bulk-update

Bulk score entry for a class.

**Request:**
```json
{
  "entries": [
    {"student_id": "S001", "subject": "MATH", "score": 0.85},
    {"student_id": "S002", "subject": "MATH", "score": 0.72},
    {"student_id": "S003", "subject": "MATH", "score": 0.91}
  ]
}
```

**Response (200):**
```json
{
  "processed": 3,
  "avg_reward": 0.8267
}
```

---

Request body:

| Field | Type | Notes |
|---|---|---|
| `entries` | list | `{student_id, subject, score}` with `score` 0–1 |
| `assessed_on` | date, optional | Day the test was taken (`YYYY-MM-DD`); today if omitted |
| `label` | string, optional | Name of the test, e.g. `"Week 4 test"` (max 80 chars) |

Each entry is saved as a dated score record. Sending the same student, subject, `assessed_on` and `label` again **corrects** the earlier score. A `student_id` that is not in the caller's school returns 404.

### GET /scores

Every recorded score in the caller's school, oldest first. Optional `class_id` query parameter limits it to one class. Archived students are left out. Used by the Reports page.

```json
[
  { "student_id": "S001", "subject": "MATH", "score": 0.7, "assessed_on": "2026-09-07", "label": "Week 1 test" }
]
```

### GET /students/{student_id}/scores

Every recorded score for one student, oldest first.

```json
[
  { "subject": "MATH", "score": 0.7, "assessed_on": "2026-09-07", "label": "Week 1 test", "source": "teacher" }
]
```

`source` is `teacher` (score sheet) or `import` (history that came with a roster file).

### POST /triage

Optional `class_id` in the body limits the report to one class of the caller's school.

Group students by predicted performance.

**Request:**
```json
{
  "subject": "MATH"
}
```

**Response (200):**
```json
{
  "subject": "MATH",
  "total_students": 15,
  "tiers": {
    "remediation": {
      "students": [{"student_id": "S005", "name": "Tunde", "average_score": 0.35}],
      "count": 2,
      "recommended_difficulty": 1,
      "note": "Scored below 40% (F9). Needs extra practice."
    },
    "on_track": {
      "students": [...],
      "count": 8,
      "recommended_difficulty": 3,
      "note": "Scored 40-74% (E8 to B2). On track."
    },
    "ahead": {
      "students": [...],
      "count": 5,
      "recommended_difficulty": 5,
      "note": "Scored 75% or above (A1). Ahead of class."
    }
  },
  "scope": "assessed_only"
}
```

---

### POST /calculate-reward

Calculate reward signal from raw metrics.

**Request:**
```json
{
  "before_score": 0.5,
  "after_score": 0.7,
  "completed": true,
  "time_spent_ratio": 1.2,
  "engaged": true,
  "churned": false
}
```

**Response (200):**
```json
{"reward": 0.82}
```

---

### GET /summary

Get brain state summary.

**Response (200):**
```json
{
  "student_count": 45,
  "content_count": 24,
  "total_sessions": 312,
  "model_type": "hybrid",
  "current_alpha": 1.0,
  "current_gamma": 1.0,
  "cumulative_regret": 23.45,
  "last_neural_score": 7.2
}
```

---

### POST /save

**Operator only.** Requires `X-Operator-Key`. The engine state is also saved automatically.

Force save brain state to disk.

**Response (200):**
```json
{"status": "saved", "path": "brain_state.json"}
```

---

## Passwords

There is no email service. A forgotten password is recovered with a single-use reset code (valid 24 hours) handed over by a school admin, or by the deployment operator.

### POST /auth/change-password

Authenticated. Body `{ "current_password": "...", "new_password": "..." }`. Returns the same shape as login, with a **new token**: every session started before the change is signed out. 400 if the current password is wrong; 422 if the new one is under 8 characters.

### GET /members

Admin only. The accounts in the caller's school: `[{ "id", "email", "role" }]`.

### PUT /members/{user_id}/classes

Admin only, for a teacher in the caller's school. Body `{ "class_ids": ["..."] }` replaces the teacher's classes; IDs that are not current classes of the school are ignored. Returns the member with its `class_ids`. 400 for an admin (admins see every class); 404 for an account outside the school.

**What a teacher can reach.** Every student, score, triage and report endpoint is limited to the teacher's classes: other students return 404 (`/recommend` 400), and asking for another class by `class_id` returns 403. Deleting students, importing class lists and creating or renaming classes return 403 for teachers.

### POST /members/{user_id}/password-reset

Admin only, for another member of the caller's school. Returns `{ "code", "expires_at" }`. The code is returned once; only its hash is stored. Creating a new code cancels an earlier unused one for the same account. 404 for an account outside the school; 400 for the caller's own account.

### POST /auth/reset-password

Public, rate-limited. Body `{ "code": "...", "new_password": "..." }`. 400 if the code is unknown, used or expired. The web page for it is `/reset-password?code=CODE`.

### POST /auth/operator-reset

For an admin who is locked out. Requires the `X-Operator-Key` header. Body `{ "email": "..." }`; returns `{ "code", "expires_at" }`.

---

## Billing (Paystack)

Schools pay per student, per term. Billing is off until the server has `PAYSTACK_SECRET_KEY` and `PRICE_PER_STUDENT_NAIRA`. Limits are soft: nothing is ever blocked for non-payment.

### GET /billing/price

Public. `{ "configured": true, "price_per_student": 500, "currency": "NGN", "term_days": 120 }`

### GET /billing

Admin only. The school's standing:

```json
{ "state": "active", "configured": true, "price_per_student": 500, "currency": "NGN", "term_days": 120,
  "students": 41, "paid_students": 41, "paid_until": "2027-02-10T09:00:00+00:00",
  "payments": [{ "reference": "gp_...", "students": 41, "amount_naira": 20500, "paid_at": "...", "period_end": "..." }] }
```

`state` is `not_configured`, `unpaid`, `active`, `over_limit` (paid, but more students now than paid for) or `expired`.

### GET /billing/reminder

Any signed-in user. `{ "show": true, "state": "unpaid" }` for an admin whose school is `unpaid`, `expired` or `over_limit`; `{ "show": false }` otherwise and always for teachers.

### POST /billing/checkout

Admin only. Body `{ "students": 41 }`. Records a pending payment of students × price and returns Paystack's payment page: `{ "authorization_url": "https://checkout.paystack.com/...", "reference": "gp_..." }`. 503 if billing is not configured.

### POST /billing/verify

Admin only, for the caller's school. Body `{ "reference": "gp_..." }`. Asks Paystack about a pending payment and records it if the charge succeeded for the expected amount. Returns the `GET /billing` body plus `payment_status` (`success`, `pending`, `failed`, `abandoned`, `amount_mismatch`, ...). A paid term runs `TERM_DAYS` from the payment.

### POST /billing/webhook

Called by Paystack. Requires a valid `x-paystack-signature` (HMAC-SHA512 of the body with the secret key); otherwise 401. Records `charge.success` events the same way as `/billing/verify`; repeats are ignored.

---

## Invites

Admin only. A school's admin is whoever created it at signup; teachers join with an invite and get the `teacher` role. `role` is returned by `/auth/signup`, `/auth/login` and `/auth/me`.

### POST /invites

Create a single-use invite for the caller's school. Expires after 7 days.

```json
{ "code": "k3J9xQ2mVb1A", "created_at": "2026-10-12T09:00:00+00:00", "expires_at": "2026-10-19T09:00:00+00:00" }
```

A teacher redeems it by sending `invite_code` to `POST /auth/signup` (`school_name` is then ignored). An unknown, used or expired code returns 400 and no account is created.

### GET /invites

List the school's pending (unused, unexpired) invites.

### DELETE /invites/{code}

Revoke a pending invite. 404 if it is not a pending invite of the caller's school.

### Admin-only school actions

`PUT /schools/{school_id}`, `DELETE /schools/{school_id}` and `DELETE /classes/{school_id}/{class_id}` return 403 for teachers.

---

## Backups

These endpoints act on every school's data. They require the `X-Operator-Key` header to match the server's `OPERATOR_KEY`; a school login is neither needed nor sufficient. With `OPERATOR_KEY` unset they return 403.

### POST /backup

Create an immediate backup.

**Response (200):**
```json
{
  "status": "created",
  "path": "backups/20260831_120000_000000",
  "timestamp": "2026-08-31T12:00:00",
  "files": ["brain_state.json", "class_config.json"],
  "size_bytes": 4523
}
```

---

### GET /backups

List all available backups.

**Response (200):**
```json
{
  "backups": [
    {
      "path": "backups/20260831_120000_000000",
      "timestamp": "2026-08-31T12:00:00",
      "files": ["brain_state.json", "class_config.json"],
      "size_bytes": 4523
    }
  ],
  "total": 5
}
```

---

### POST /backup/restore

Restore from a backup.

**Query Parameters:**
- `backup_path` (required) — path to backup directory

**Response (200):**
```json
{
  "status": "restored",
  "backup_path": "backups/20260831_120000_000000",
  "message": "Brain state restored. Reload may be required."
}
```

---

## Data Ingestion

### POST /ingest

Importing `type=content` is operator-only (`X-Operator-Key`); importing `type=students` uses the caller's login and school.

Upload CSV/Excel file for ingestion.

**Form Data:**
- `file` — CSV or Excel file
- `type` — "students" or "content"
- `school` (optional) — school name
- `school_id` (optional) — school ID (overrides school name)
- `dry_run` (optional) — validate only, don't write

**Example (curl):**
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer <token>" \
  -F "file=@students.csv" \
  -F "type=students" \
  -F "school=Lagos Model School"
```

**Response (200):**
```json
{
  "status": "success",
  "report": {
    "students_read": 50,
    "students_valid": 48,
    "students_skipped": 2,
    "schools_created": 1,
    "classes_created": 3,
    "errors": [],
    "warnings": ["Row 15: performance_score out of range, clamped to 0.0-1.0"]
  }
}
```

---

## Health

### GET /health

Health check endpoint.

**Response (200):**
```json
{
  "status": "alive",
  "engine": "GradePulse",
  "version": "1.0.0",
  "worker_pid": 12345,
  "expected_workers": 1,
  "backup_status": "enabled",
  "backup_count": 5
}
```

---

### GET /

Root health check (same as `/health`).

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Error message here"
}
```

Common HTTP status codes:
- `400` — Bad request (validation error)
- `401` — Unauthorized (missing or invalid token)
- `404` — Not found (resource doesn't exist)
- `500` — Internal server error

---

## Rate Limiting

No rate limiting in v0.1.0. Planned for v0.2.

---

## Versioning

API version is embedded in the URL path (not yet implemented). Current version: v0.1.0.

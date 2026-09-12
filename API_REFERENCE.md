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

### POST /triage

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

Force save brain state to disk.

**Response (200):**
```json
{"status": "saved", "path": "brain_state.json"}
```

---

## Backups

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

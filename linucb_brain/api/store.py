"""
Student and score store — SQLite, in the same database file as the user
accounts (so the scheduled backup already covers it).

This is the record of a school's roster and test scores. The Brain keeps an
in-memory copy of a student only while it scores recommendations for them; it
is no longer where students or grades are saved.

- A student is identified by (school_id, student_id): two schools can both
  have an "S001".
- Every score is its own dated row. `grade_history` and `performance_score`
  on the API are derived from those rows.
- Deleting a student, class or school archives the rows instead of erasing
  them.
"""
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from .auth import _get_db

RECENT_SCORES = 5  # performance_score = mean of this many most recent scores

SOURCE_TEACHER = "teacher"  # entered on the score sheet
SOURCE_IMPORT = "import"    # history that arrived with a roster/CSV


@dataclass
class StudentRecord:
    pk: int
    school_id: str
    student_id: str
    name: str
    class_id: str = ""
    current_topic: str = ""
    baseline_score: float = 0.5
    metadata: Dict = field(default_factory=dict)
    features: Dict = field(default_factory=dict)
    grade_history: Dict[str, List[float]] = field(default_factory=dict)
    recent_scores: List[float] = field(default_factory=list)

    @property
    def performance_score(self) -> float:
        """Mean of the most recent scores; the baseline until one is entered."""
        if not self.recent_scores:
            return self.baseline_score
        return sum(self.recent_scores) / len(self.recent_scores)

    @property
    def engine_key(self) -> str:
        """Key for this student inside the Brain (student_id alone is not unique)."""
        return f"s{self.pk}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_store():
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_id TEXT NOT NULL,
            student_id TEXT NOT NULL,
            name TEXT NOT NULL,
            class_id TEXT NOT NULL DEFAULT '',
            current_topic TEXT NOT NULL DEFAULT '',
            baseline_score REAL NOT NULL DEFAULT 0.5,
            metadata TEXT NOT NULL DEFAULT '{}',
            features TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            archived_at TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS students_school_student
            ON students (school_id, student_id) WHERE archived_at IS NULL;
        CREATE INDEX IF NOT EXISTS students_school_class ON students (school_id, class_id);

        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_pk INTEGER NOT NULL REFERENCES students (id),
            subject TEXT NOT NULL,
            score REAL NOT NULL,
            assessed_on TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'teacher',
            entered_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS scores_student_subject ON scores (student_pk, subject, assessed_on, id);
    """)
    conn.commit()
    conn.close()


# ── Reading ────────────────────────────────────────────────────────────────

def _attach_scores(conn, records: List[StudentRecord]) -> List[StudentRecord]:
    if not records:
        return records
    by_pk = {r.pk: r for r in records}
    marks = ",".join("?" * len(by_pk))
    rows = conn.execute(
        f"SELECT student_pk, subject, score FROM scores WHERE student_pk IN ({marks}) "
        "ORDER BY assessed_on, id",
        list(by_pk),
    ).fetchall()
    for row in rows:
        record = by_pk[row["student_pk"]]
        record.grade_history.setdefault(row["subject"], []).append(row["score"])
        record.recent_scores.append(row["score"])
    for record in records:
        record.recent_scores = record.recent_scores[-RECENT_SCORES:]
    return records


def _record(row) -> StudentRecord:
    return StudentRecord(
        pk=row["id"], school_id=row["school_id"], student_id=row["student_id"],
        name=row["name"], class_id=row["class_id"], current_topic=row["current_topic"],
        baseline_score=row["baseline_score"],
        metadata=json.loads(row["metadata"]), features=json.loads(row["features"]),
    )


def get_student(school_id: str, student_id: str) -> Optional[StudentRecord]:
    if not school_id:
        return None
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM students WHERE school_id = ? AND student_id = ? AND archived_at IS NULL",
        (school_id, student_id),
    ).fetchone()
    records = _attach_scores(conn, [_record(row)]) if row else []
    conn.close()
    return records[0] if records else None


def list_students(school_id: str, class_id: str = "") -> List[StudentRecord]:
    if not school_id:
        return []
    query = "SELECT * FROM students WHERE school_id = ? AND archived_at IS NULL"
    params = [school_id]
    if class_id:
        query += " AND class_id = ?"
        params.append(class_id)
    conn = _get_db()
    rows = conn.execute(query + " ORDER BY name COLLATE NOCASE, id", params).fetchall()
    records = _attach_scores(conn, [_record(r) for r in rows])
    conn.close()
    return records


def count_students(school_id: str = "") -> int:
    """Students in one school, or in every school when school_id is empty."""
    conn = _get_db()
    if school_id:
        n = conn.execute(
            "SELECT COUNT(*) FROM students WHERE school_id = ? AND archived_at IS NULL", (school_id,)
        ).fetchone()[0]
    else:
        n = conn.execute("SELECT COUNT(*) FROM students WHERE archived_at IS NULL").fetchone()[0]
    conn.close()
    return n


def list_scores(student_pk: int) -> List[dict]:
    conn = _get_db()
    rows = conn.execute(
        "SELECT subject, score, assessed_on, label, source FROM scores "
        "WHERE student_pk = ? ORDER BY assessed_on, id",
        (student_pk,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Writing ────────────────────────────────────────────────────────────────

def add_student(
    school_id: str, student_id: str, name: str, *, class_id: str = "", current_topic: str = "",
    baseline_score: float = 0.5, metadata: Optional[Dict] = None, features: Optional[Dict] = None,
    grade_history: Optional[Dict[str, List[float]]] = None,
) -> Tuple[StudentRecord, bool]:
    """Create a student. Returns (record, created); an existing ID in the same
    school is returned unchanged with created=False."""
    existing = get_student(school_id, student_id)
    if existing:
        return existing, False
    now = _now()
    conn = _get_db()
    cur = conn.execute(
        "INSERT INTO students (school_id, student_id, name, class_id, current_topic, baseline_score, "
        "metadata, features, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (school_id, student_id, " ".join(name.split()), class_id, current_topic or "", baseline_score,
         json.dumps(metadata or {}), json.dumps(features or {}), now, now),
    )
    for subject, values in (grade_history or {}).items():
        _insert_scores(conn, cur.lastrowid, subject, values, SOURCE_IMPORT)
    conn.commit()
    conn.close()
    return get_student(school_id, student_id), True


def update_student(student_pk: int, **fields) -> None:
    """Update columns of a student. dict values (metadata, features) are stored as JSON."""
    if not fields:
        return
    columns, values = [], []
    for column, value in fields.items():
        columns.append(f"{column} = ?")
        values.append(json.dumps(value) if isinstance(value, dict) else value)
    conn = _get_db()
    conn.execute(
        f"UPDATE students SET {', '.join(columns)}, updated_at = ? WHERE id = ?",
        (*values, _now(), student_pk),
    )
    conn.commit()
    conn.close()


def _archive(where: str, params: Iterable) -> int:
    conn = _get_db()
    cur = conn.execute(
        f"UPDATE students SET archived_at = ? WHERE archived_at IS NULL AND {where}", (_now(), *params)
    )
    conn.commit()
    conn.close()
    return cur.rowcount


def archive_student(student_pk: int) -> int:
    return _archive("id = ?", (student_pk,))


def archive_class(school_id: str, class_id: str) -> int:
    return _archive("school_id = ? AND class_id = ?", (school_id, class_id))


def archive_school(school_id: str) -> int:
    return _archive("school_id = ?", (school_id,))


def _insert_scores(conn, student_pk: int, subject: str, values: Iterable[float], source: str,
                   assessed_on: Optional[str] = None, label: str = "", entered_by: str = ""):
    now = _now()
    conn.executemany(
        "INSERT INTO scores (student_pk, subject, score, assessed_on, label, source, entered_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(student_pk, subject, float(v), assessed_on or date.today().isoformat(), label, source, entered_by, now)
         for v in values],
    )


def record_scores(entries: Iterable[Tuple[int, str, float]], *, assessed_on: Optional[date] = None,
                  label: str = "", entered_by: str = "") -> int:
    """Save teacher-entered scores: (student_pk, subject, score) for one sitting.

    Entering a score again for the same student, subject, date and label
    corrects the earlier one instead of adding a second score.
    """
    day = (assessed_on or date.today()).isoformat()
    conn = _get_db()
    saved = 0
    for student_pk, subject, score in entries:
        cur = conn.execute(
            "UPDATE scores SET score = ?, entered_by = ? WHERE id = (SELECT id FROM scores WHERE "
            "student_pk = ? AND subject = ? AND assessed_on = ? AND label = ? AND source = ? "
            "ORDER BY id DESC LIMIT 1)",
            (float(score), entered_by, student_pk, subject, day, label, SOURCE_TEACHER),
        )
        if cur.rowcount == 0:
            _insert_scores(conn, student_pk, subject, [score], SOURCE_TEACHER, day, label, entered_by)
        saved += 1
    conn.commit()
    conn.close()
    return saved


def replace_imported_scores(student_pk: int, subject: str, values: Iterable[float]) -> None:
    """Set the imported history for one subject, leaving teacher-entered scores alone."""
    conn = _get_db()
    conn.execute(
        "DELETE FROM scores WHERE student_pk = ? AND subject = ? AND source = ?",
        (student_pk, subject, SOURCE_IMPORT),
    )
    _insert_scores(conn, student_pk, subject, values, SOURCE_IMPORT)
    conn.commit()
    conn.close()


init_store()

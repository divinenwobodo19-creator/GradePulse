"""
School data store — SQLite, in the same database file as the user accounts
(so the scheduled backup already covers it).

This is the record of schools, their classes and subjects, their students and
their test scores. The Brain keeps an
in-memory copy of a student only while it scores recommendations for them; it
is no longer where students or grades are saved.

- A student is identified by (school_id, student_id): two schools can both
  have an "S001".
- Every score is its own dated row. `grade_history` and `performance_score`
  on the API are derived from those rows.
- Deleting a student, class or school archives the rows instead of erasing
  them.
- Schools and classes used to live in class_config.json, which was rewritten
  whole on every change; each change is now its own row update.
"""
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from ..models.school import SchoolClass, normalize_label
from .auth import _get_db

RECENT_SCORES = 5  # performance_score = mean of this many most recent scores

DEFAULT_SCHOOL_NAME = "MY SCHOOL"
# A new school starts with these; its admin can change the list.
DEFAULT_SUBJECTS = ["MATH", "ENGLISH", "SCIENCE", "HISTORY"]
MAX_SUBJECTS = 40

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
        CREATE TABLE IF NOT EXISTS schools (
            school_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            subjects TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            archived_at TEXT
        );
        CREATE TABLE IF NOT EXISTS classes (
            class_id TEXT PRIMARY KEY,
            school_id TEXT NOT NULL REFERENCES schools (school_id),
            label TEXT NOT NULL,
            grade_level TEXT NOT NULL DEFAULT '',
            arm TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            archived_at TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS classes_school_label
            ON classes (school_id, label) WHERE archived_at IS NULL;

        -- Paystack payments. A school pays per student for one term; a row
        -- is written as "pending" when checkout starts and marked
        -- "success" once Paystack confirms the charge.
        CREATE TABLE IF NOT EXISTS payments (
            reference TEXT PRIMARY KEY,
            school_id TEXT NOT NULL,
            students INTEGER NOT NULL,
            amount_kobo INTEGER NOT NULL,
            currency TEXT NOT NULL DEFAULT 'NGN',
            status TEXT NOT NULL DEFAULT 'pending',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            paid_at TEXT,
            period_start TEXT,
            period_end TEXT
        );
        CREATE INDEX IF NOT EXISTS payments_school ON payments (school_id, status);

        -- Which classes a teacher teaches. Admins are not listed: they see
        -- every class in their school.
        CREATE TABLE IF NOT EXISTS teacher_classes (
            user_id TEXT NOT NULL,
            class_id TEXT NOT NULL,
            PRIMARY KEY (user_id, class_id)
        );

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

        -- Who viewed or changed student data, for a school's own records and
        -- for working out what a breach exposed (NDPA s.40). Kept for
        -- AUDIT_KEEP_DAYS, then deleted.
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            at TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT '',
            school_id TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            target TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS audit_log_school ON audit_log (school_id, at);

        -- Term report cards. A term is the window whose weekly tests make up
        -- the continuous assessment (CA); the exam, remarks, comments and
        -- attendance are entered once per term.
        CREATE TABLE IF NOT EXISTS terms (
            term_id TEXT PRIMARY KEY,
            school_id TEXT NOT NULL,
            session TEXT NOT NULL,
            name TEXT NOT NULL,
            starts_on TEXT NOT NULL,
            ends_on TEXT NOT NULL,
            next_term_begins TEXT NOT NULL DEFAULT '',
            days_opened INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            archived_at TEXT
        );
        CREATE INDEX IF NOT EXISTS terms_school ON terms (school_id, starts_on);
        CREATE TABLE IF NOT EXISTS exam_scores (
            term_id TEXT NOT NULL,
            student_pk INTEGER NOT NULL REFERENCES students (id),
            subject TEXT NOT NULL,
            score REAL NOT NULL,
            entered_by TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (term_id, student_pk, subject)
        );
        CREATE TABLE IF NOT EXISTS subject_remarks (
            term_id TEXT NOT NULL,
            student_pk INTEGER NOT NULL REFERENCES students (id),
            subject TEXT NOT NULL,
            remark TEXT NOT NULL,
            entered_by TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (term_id, student_pk, subject)
        );
        CREATE TABLE IF NOT EXISTS report_comments (
            term_id TEXT NOT NULL,
            student_pk INTEGER NOT NULL REFERENCES students (id),
            days_present INTEGER,
            form_teacher_comment TEXT NOT NULL DEFAULT '',
            principal_comment TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (term_id, student_pk)
        );
    """)
    school_columns = {row["name"] for row in conn.execute("PRAGMA table_info(schools)")}
    if "report_settings" not in school_columns:
        conn.execute("ALTER TABLE schools ADD COLUMN report_settings TEXT NOT NULL DEFAULT '{}'")
    conn.commit()
    conn.close()


# ── Schools, classes and subjects ──────────────────────────────────────────

def _new_id() -> str:
    return str(uuid.uuid4())[:8]


def _class_dict(row) -> dict:
    return {"class_id": row["class_id"], "label": row["label"],
            "grade_level": row["grade_level"], "arm": row["arm"]}


def _classes(conn, school_id: str) -> List[dict]:
    rows = conn.execute(
        "SELECT * FROM classes WHERE school_id = ? AND archived_at IS NULL ORDER BY created_at, rowid",
        (school_id,),
    ).fetchall()
    return [_class_dict(r) for r in rows]


def create_school(name: str = DEFAULT_SCHOOL_NAME) -> dict:
    """Always create a new school. Names are labels, not identifiers, so two
    schools may share one; membership is never granted by matching a name."""
    name = normalize_label(name) or DEFAULT_SCHOOL_NAME
    conn = _get_db()
    while True:
        school_id = _new_id()
        try:
            conn.execute(
                "INSERT INTO schools (school_id, name, subjects, created_at) VALUES (?, ?, ?, ?)",
                (school_id, name, json.dumps(DEFAULT_SUBJECTS), _now()),
            )
            break
        except sqlite3.IntegrityError:
            continue  # 8-character id already taken
    conn.commit()
    conn.close()
    return {"school_id": school_id, "name": name, "classes": []}


def get_school(school_id: str) -> Optional[dict]:
    if not school_id:
        return None
    conn = _get_db()
    row = conn.execute(
        "SELECT school_id, name FROM schools WHERE school_id = ? AND archived_at IS NULL", (school_id,)
    ).fetchone()
    school = {"school_id": row["school_id"], "name": row["name"], "classes": _classes(conn, school_id)} if row else None
    conn.close()
    return school


def rename_school(school_id: str, name: str) -> None:
    conn = _get_db()
    conn.execute("UPDATE schools SET name = ? WHERE school_id = ?", (normalize_label(name), school_id))
    conn.commit()
    conn.close()


def list_classes(school_id: str) -> List[dict]:
    conn = _get_db()
    classes = _classes(conn, school_id)
    conn.close()
    return classes


def get_class(school_id: str, class_id: str) -> Optional[dict]:
    if not school_id:
        return None
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM classes WHERE school_id = ? AND class_id = ? AND archived_at IS NULL",
        (school_id, class_id),
    ).fetchone()
    conn.close()
    return _class_dict(row) if row else None


def add_class(school_id: str, label: str, class_id: Optional[str] = None) -> Optional[dict]:
    """Add a class. None if the name is empty or already used in this school."""
    label = normalize_label(label)
    if not label:
        return None
    grade_level, arm = SchoolClass.split_label(label)
    conn = _get_db()
    try:
        while True:
            new_id = class_id or _new_id()
            try:
                conn.execute(
                    "INSERT INTO classes (class_id, school_id, label, grade_level, arm, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (new_id, school_id, label, grade_level, arm, _now()),
                )
                break
            except sqlite3.IntegrityError as exc:
                if "class_id" in str(exc) and class_id is None:
                    continue  # generated id already taken
                return None  # this school already has a class with that name
        conn.commit()
    finally:
        conn.close()
    return {"class_id": new_id, "label": label, "grade_level": grade_level, "arm": arm}


def rename_class(school_id: str, class_id: str, label: str) -> Optional[dict]:
    """Rename a class. None if another class in the school has that name."""
    label = normalize_label(label)
    grade_level, arm = SchoolClass.split_label(label)
    conn = _get_db()
    try:
        conn.execute(
            "UPDATE classes SET label = ?, grade_level = ?, arm = ? WHERE school_id = ? AND class_id = ?",
            (label, grade_level, arm, school_id, class_id),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()
    return get_class(school_id, class_id)


def get_teacher_classes(user_id: str, school_id: str) -> List[str]:
    """IDs of the current classes a teacher is assigned to in their school."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT tc.class_id FROM teacher_classes tc JOIN classes c ON c.class_id = tc.class_id "
        "WHERE tc.user_id = ? AND c.school_id = ? AND c.archived_at IS NULL ORDER BY c.created_at, c.rowid",
        (user_id, school_id),
    ).fetchall()
    conn.close()
    return [r["class_id"] for r in rows]


def set_teacher_classes(user_id: str, school_id: str, class_ids: Iterable[str]) -> List[str]:
    """Replace a teacher's classes. IDs that are not current classes of the
    school are ignored. Returns the classes now assigned."""
    valid = {c["class_id"] for c in list_classes(school_id)}
    conn = _get_db()
    conn.execute(
        "DELETE FROM teacher_classes WHERE user_id = ? AND class_id IN "
        "(SELECT class_id FROM classes WHERE school_id = ?)",
        (user_id, school_id),
    )
    conn.executemany(
        "INSERT OR IGNORE INTO teacher_classes (user_id, class_id) VALUES (?, ?)",
        [(user_id, cid) for cid in class_ids if cid in valid],
    )
    conn.commit()
    conn.close()
    return get_teacher_classes(user_id, school_id)


# ── Payments ───────────────────────────────────────────────────────────────

def create_payment(reference: str, school_id: str, students: int, amount_kobo: int, created_by: str) -> None:
    conn = _get_db()
    conn.execute(
        "INSERT INTO payments (reference, school_id, students, amount_kobo, created_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (reference, school_id, students, amount_kobo, created_by, _now()),
    )
    conn.commit()
    conn.close()


def get_payment(reference: str) -> Optional[dict]:
    conn = _get_db()
    row = conn.execute("SELECT * FROM payments WHERE reference = ?", (reference,)).fetchone()
    conn.close()
    return dict(row) if row else None


def complete_payment(reference: str, paid_at: str, period_start: str, period_end: str) -> bool:
    """Mark a pending payment paid. False if it was already settled (Paystack
    can report the same charge more than once)."""
    conn = _get_db()
    cur = conn.execute(
        "UPDATE payments SET status = 'success', paid_at = ?, period_start = ?, period_end = ? "
        "WHERE reference = ? AND status = 'pending'",
        (paid_at, period_start, period_end, reference),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def fail_payment(reference: str, status: str) -> None:
    conn = _get_db()
    conn.execute("UPDATE payments SET status = ? WHERE reference = ? AND status = 'pending'", (status, reference))
    conn.commit()
    conn.close()


def list_paid_payments(school_id: str) -> List[dict]:
    """Successful payments, newest first."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM payments WHERE school_id = ? AND status = 'success' ORDER BY paid_at DESC",
        (school_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_subjects(school_id: str) -> List[str]:
    conn = _get_db()
    row = conn.execute("SELECT subjects FROM schools WHERE school_id = ?", (school_id,)).fetchone()
    conn.close()
    subjects = json.loads(row["subjects"]) if row else []
    return subjects or list(DEFAULT_SUBJECTS)


def set_subjects(school_id: str, subjects: Iterable[str]) -> List[str]:
    """Replace a school's subject list (normalised, de-duplicated, order kept)."""
    cleaned: List[str] = []
    for subject in subjects:
        subject = normalize_label(subject)
        if subject and subject not in cleaned:
            cleaned.append(subject)
    conn = _get_db()
    conn.execute("UPDATE schools SET subjects = ? WHERE school_id = ?", (json.dumps(cleaned), school_id))
    conn.commit()
    conn.close()
    return cleaned


def adopt_legacy_registry(registry: dict) -> int:
    """One-off upgrade: copy schools and classes from class_config.json into
    the store, keeping their IDs (first start only)."""
    conn = _get_db()
    if conn.execute("SELECT COUNT(*) FROM schools").fetchone()[0] > 0:
        conn.close()
        return 0
    now, moved = _now(), 0
    for school in registry.get("schools", []):
        try:
            conn.execute(
                "INSERT INTO schools (school_id, name, subjects, created_at) VALUES (?, ?, ?, ?)",
                (school["school_id"], normalize_label(school.get("name", "")) or DEFAULT_SCHOOL_NAME,
                 json.dumps(DEFAULT_SUBJECTS), now),
            )
        except sqlite3.IntegrityError:
            continue  # another worker is adopting the same file
        moved += 1
        for cls in school.get("classes", []):
            try:
                conn.execute(
                    "INSERT INTO classes (class_id, school_id, label, grade_level, arm, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (cls["class_id"], school["school_id"], normalize_label(cls.get("label", "")),
                     cls.get("grade_level", ""), cls.get("arm", ""), now),
                )
            except sqlite3.IntegrityError:
                continue  # duplicate name or id in the old file
    conn.commit()
    conn.close()
    return moved


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


def _class_filter(column: str, class_id: str, class_ids: Optional[Iterable[str]]) -> Tuple[str, list]:
    """SQL for "in this class" and/or "in one of these classes" (a teacher's)."""
    sql, params = "", []
    if class_id:
        sql += f" AND {column} = ?"
        params.append(class_id)
    if class_ids is not None:
        class_ids = list(class_ids)
        if not class_ids:
            return " AND 0", []
        sql += f" AND {column} IN ({','.join('?' * len(class_ids))})"
        params.extend(class_ids)
    return sql, params


def list_students(school_id: str, class_id: str = "", class_ids: Optional[Iterable[str]] = None) -> List[StudentRecord]:
    """Current students of a school; optionally one class, and/or only the
    classes in `class_ids` (None means no such limit)."""
    if not school_id:
        return []
    extra, extra_params = _class_filter("class_id", class_id, class_ids)
    query = "SELECT * FROM students WHERE school_id = ? AND archived_at IS NULL" + extra
    params = [school_id, *extra_params]
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


def count_scores(school_id: str, class_ids: Optional[Iterable[str]] = None) -> int:
    """Scores recorded for the school's current students (optionally only some classes)."""
    extra, extra_params = _class_filter("st.class_id", "", class_ids)
    conn = _get_db()
    n = conn.execute(
        "SELECT COUNT(*) FROM scores sc JOIN students st ON st.id = sc.student_pk "
        "WHERE st.school_id = ? AND st.archived_at IS NULL" + extra,
        (school_id, *extra_params),
    ).fetchone()[0]
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


def list_school_scores(school_id: str, class_id: str = "", class_ids: Optional[Iterable[str]] = None,
                       subject: str = "") -> List[dict]:
    """Every recorded score in a school (or one class, or a teacher's classes,
    or one subject), oldest first."""
    if not school_id:
        return []
    extra, extra_params = _class_filter("st.class_id", class_id, class_ids)
    if subject:
        extra += " AND sc.subject = ?"
        extra_params = [*extra_params, subject]
    query = (
        "SELECT st.student_id, sc.subject, sc.score, sc.assessed_on, sc.label "
        "FROM scores sc JOIN students st ON st.id = sc.student_pk "
        "WHERE st.school_id = ? AND st.archived_at IS NULL" + extra
    )
    params = [school_id, *extra_params]
    conn = _get_db()
    rows = conn.execute(query + " ORDER BY sc.assessed_on, sc.id", params).fetchall()
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


def _archive_rows(table: str, where: str, params: Iterable) -> None:
    conn = _get_db()
    conn.execute(f"UPDATE {table} SET archived_at = ? WHERE archived_at IS NULL AND {where}", (_now(), *params))
    conn.commit()
    conn.close()


def archive_class(school_id: str, class_id: str) -> int:
    """Archive a class and the students in it."""
    _archive_rows("classes", "school_id = ? AND class_id = ?", (school_id, class_id))
    return _archive("school_id = ? AND class_id = ?", (school_id, class_id))


def archive_school(school_id: str) -> int:
    """Archive a school with its classes and students."""
    _archive_rows("classes", "school_id = ?", (school_id,))
    _archive_rows("schools", "school_id = ?", (school_id,))
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


# ── Deleting for good, the audit log, and export ────────────────────────────
# Deleting a student, class or school archives it first, so a mistake can be
# put right by the operator. After ARCHIVE_PURGE_DAYS the archived rows and
# their scores are deleted for good; the rolling backups lose them a few days
# later. Payments stay: they are the school's financial record.

def _days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def purge_archived(older_than_days: int) -> dict:
    """Delete students, classes and schools archived more than
    `older_than_days` ago, with their scores. Returns counts and the engine
    keys of the deleted students (for the caller to drop from the Brain)."""
    cutoff = _days_ago(older_than_days)
    conn = _get_db()
    old_students = "SELECT id FROM students WHERE archived_at IS NOT NULL AND archived_at < ?"
    keys = [f"s{row[0]}" for row in conn.execute(old_students, (cutoff,)).fetchall()]
    scores = conn.execute(f"DELETE FROM scores WHERE student_pk IN ({old_students})", (cutoff,)).rowcount
    for table in ("exam_scores", "subject_remarks", "report_comments"):
        conn.execute(f"DELETE FROM {table} WHERE student_pk IN ({old_students})", (cutoff,))
    old_terms = "SELECT term_id FROM terms WHERE archived_at IS NOT NULL AND archived_at < ?"
    for table in ("exam_scores", "subject_remarks", "report_comments"):
        conn.execute(f"DELETE FROM {table} WHERE term_id IN ({old_terms})", (cutoff,))
    conn.execute("DELETE FROM terms WHERE archived_at IS NOT NULL AND archived_at < ?", (cutoff,))
    students = conn.execute("DELETE FROM students WHERE archived_at IS NOT NULL AND archived_at < ?",
                            (cutoff,)).rowcount
    old_classes = "SELECT class_id FROM classes WHERE archived_at IS NOT NULL AND archived_at < ?"
    conn.execute(f"DELETE FROM teacher_classes WHERE class_id IN ({old_classes})", (cutoff,))
    classes = conn.execute("DELETE FROM classes WHERE archived_at IS NOT NULL AND archived_at < ?",
                           (cutoff,)).rowcount
    school_terms = ("SELECT term_id FROM terms WHERE school_id IN "
                    "(SELECT school_id FROM schools WHERE archived_at IS NOT NULL AND archived_at < ?)")
    for table in ("exam_scores", "subject_remarks", "report_comments"):
        conn.execute(f"DELETE FROM {table} WHERE term_id IN ({school_terms})", (cutoff,))
    conn.execute(f"DELETE FROM terms WHERE term_id IN ({school_terms})", (cutoff,))
    schools = conn.execute("DELETE FROM schools WHERE archived_at IS NOT NULL AND archived_at < ?",
                           (cutoff,)).rowcount
    conn.commit()
    conn.close()
    return {"students": students, "scores": scores, "classes": classes, "schools": schools, "engine_keys": keys}


def audit(user_id: str, school_id: str, action: str, target: str = "", address: str = "") -> None:
    conn = _get_db()
    conn.execute(
        "INSERT INTO audit_log (at, user_id, school_id, action, target, address) VALUES (?, ?, ?, ?, ?, ?)",
        (_now(), user_id, school_id, action, target[:200], address[:64]),
    )
    conn.commit()
    conn.close()


def purge_audit(older_than_days: int) -> int:
    conn = _get_db()
    n = conn.execute("DELETE FROM audit_log WHERE at < ?", (_days_ago(older_than_days),)).rowcount
    conn.commit()
    conn.close()
    return n


def list_audit(school_id: str, limit: int = 500) -> List[dict]:
    """The school's audit entries, newest first, with the email of who acted."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT a.at, a.action, a.target, COALESCE(u.email, a.user_id) AS who "
        "FROM audit_log a LEFT JOIN users u ON u.id = a.user_id "
        "WHERE a.school_id = ? ORDER BY a.at DESC, a.id DESC LIMIT ?",
        (school_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def export_rows(school_id: str) -> Dict[str, List[dict]]:
    """Everything a school has entered, for its own copy (NDPA s.34, s.38)."""
    conn = _get_db()
    classes = conn.execute(
        "SELECT class_id, label FROM classes WHERE school_id = ? AND archived_at IS NULL ORDER BY created_at, rowid",
        (school_id,)).fetchall()
    students = conn.execute(
        "SELECT st.student_id, st.name, COALESCE(c.label, '') AS class, st.created_at "
        "FROM students st LEFT JOIN classes c ON c.class_id = st.class_id "
        "WHERE st.school_id = ? AND st.archived_at IS NULL ORDER BY c.label, st.name", (school_id,)).fetchall()
    scores = conn.execute(
        "SELECT st.student_id, st.name, sc.subject, ROUND(sc.score * 100, 1) AS score_percent, sc.assessed_on, "
        "sc.label AS test, sc.source FROM scores sc JOIN students st ON st.id = sc.student_pk "
        "WHERE st.school_id = ? AND st.archived_at IS NULL ORDER BY sc.assessed_on, st.student_id, sc.id",
        (school_id,)).fetchall()
    conn.close()
    return {"classes": [dict(r) for r in classes], "students": [dict(r) for r in students],
            "scores": [dict(r) for r in scores]}


# ── Term report cards ──────────────────────────────────────────────────────

def get_report_settings(school_id: str) -> dict:
    """The school's saved report-card settings (raw; defaults are filled in
    by report_cards.settings_with_defaults)."""
    conn = _get_db()
    row = conn.execute("SELECT report_settings FROM schools WHERE school_id = ?", (school_id,)).fetchone()
    conn.close()
    return json.loads(row["report_settings"] or "{}") if row else {}


def set_report_settings(school_id: str, settings: dict) -> None:
    conn = _get_db()
    conn.execute("UPDATE schools SET report_settings = ? WHERE school_id = ?", (json.dumps(settings), school_id))
    conn.commit()
    conn.close()


def _term_dict(row) -> dict:
    return {"term_id": row["term_id"], "session": row["session"], "name": row["name"],
            "starts_on": row["starts_on"], "ends_on": row["ends_on"],
            "next_term_begins": row["next_term_begins"], "days_opened": row["days_opened"]}


def list_terms(school_id: str) -> List[dict]:
    """A school's terms, newest first."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM terms WHERE school_id = ? AND archived_at IS NULL ORDER BY starts_on DESC, created_at DESC",
        (school_id,),
    ).fetchall()
    conn.close()
    return [_term_dict(r) for r in rows]


def get_term(school_id: str, term_id: str) -> Optional[dict]:
    if not school_id:
        return None
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM terms WHERE school_id = ? AND term_id = ? AND archived_at IS NULL", (school_id, term_id)
    ).fetchone()
    conn.close()
    return _term_dict(row) if row else None


def add_term(school_id: str, fields: dict) -> dict:
    conn = _get_db()
    while True:
        term_id = _new_id()
        try:
            conn.execute(
                "INSERT INTO terms (term_id, school_id, session, name, starts_on, ends_on, next_term_begins, "
                "days_opened, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (term_id, school_id, fields["session"], fields["name"], fields["starts_on"], fields["ends_on"],
                 fields.get("next_term_begins", ""), fields.get("days_opened", 0), _now()),
            )
            break
        except sqlite3.IntegrityError:
            continue
    conn.commit()
    conn.close()
    return get_term(school_id, term_id)


def update_term(school_id: str, term_id: str, fields: dict) -> Optional[dict]:
    allowed = ("session", "name", "starts_on", "ends_on", "next_term_begins", "days_opened")
    changes = {k: v for k, v in fields.items() if k in allowed}
    if changes:
        conn = _get_db()
        conn.execute(
            f"UPDATE terms SET {', '.join(f'{k} = ?' for k in changes)} "
            "WHERE school_id = ? AND term_id = ? AND archived_at IS NULL",
            (*changes.values(), school_id, term_id),
        )
        conn.commit()
        conn.close()
    return get_term(school_id, term_id)


def archive_term(school_id: str, term_id: str) -> bool:
    conn = _get_db()
    cur = conn.execute(
        "UPDATE terms SET archived_at = ? WHERE school_id = ? AND term_id = ? AND archived_at IS NULL",
        (_now(), school_id, term_id),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def term_weekly_scores(student_pks: Iterable[int], starts_on: str, ends_on: str) -> List[dict]:
    """Weekly test scores taken inside a term, for these students."""
    pks = list(student_pks)
    if not pks:
        return []
    conn = _get_db()
    rows = conn.execute(
        f"SELECT student_pk, subject, score FROM scores WHERE student_pk IN ({','.join('?' * len(pks))}) "
        "AND assessed_on >= ? AND assessed_on <= ? ORDER BY assessed_on, id",
        (*pks, starts_on, ends_on),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _term_rows(table: str, term_id: str, student_pks: Iterable[int]) -> List[dict]:
    pks = list(student_pks)
    if not pks:
        return []
    conn = _get_db()
    rows = conn.execute(
        f"SELECT * FROM {table} WHERE term_id = ? AND student_pk IN ({','.join('?' * len(pks))})",
        (term_id, *pks),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def term_exam_scores(term_id: str, student_pks: Iterable[int]) -> List[dict]:
    return _term_rows("exam_scores", term_id, student_pks)


def term_subject_remarks(term_id: str, student_pks: Iterable[int]) -> List[dict]:
    return _term_rows("subject_remarks", term_id, student_pks)


def term_report_comments(term_id: str, student_pks: Iterable[int]) -> List[dict]:
    return _term_rows("report_comments", term_id, student_pks)


def save_exam_scores(term_id: str, entries: Iterable[Tuple[int, str, Optional[float]]], entered_by: str) -> None:
    """(student_pk, subject, score) rows; a score of None removes the entry."""
    conn = _get_db()
    now = _now()
    for pk, subject, score in entries:
        if score is None:
            conn.execute("DELETE FROM exam_scores WHERE term_id = ? AND student_pk = ? AND subject = ?",
                         (term_id, pk, subject))
        else:
            conn.execute(
                "INSERT INTO exam_scores (term_id, student_pk, subject, score, entered_by, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (term_id, student_pk, subject) "
                "DO UPDATE SET score = excluded.score, entered_by = excluded.entered_by, updated_at = excluded.updated_at",
                (term_id, pk, subject, score, entered_by, now),
            )
    conn.commit()
    conn.close()


def save_subject_remarks(term_id: str, entries: Iterable[Tuple[int, str, str]], entered_by: str) -> None:
    """(student_pk, subject, remark) rows; an empty remark removes the entry."""
    conn = _get_db()
    now = _now()
    for pk, subject, remark in entries:
        if not remark:
            conn.execute("DELETE FROM subject_remarks WHERE term_id = ? AND student_pk = ? AND subject = ?",
                         (term_id, pk, subject))
        else:
            conn.execute(
                "INSERT INTO subject_remarks (term_id, student_pk, subject, remark, entered_by, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (term_id, student_pk, subject) "
                "DO UPDATE SET remark = excluded.remark, entered_by = excluded.entered_by, updated_at = excluded.updated_at",
                (term_id, pk, subject, remark, entered_by, now),
            )
    conn.commit()
    conn.close()


def save_report_comment(term_id: str, student_pk: int, changes: dict, updated_by: str) -> None:
    """Set some of days_present / form_teacher_comment / principal_comment,
    leaving the others as they were."""
    allowed = ("days_present", "form_teacher_comment", "principal_comment")
    changes = {k: v for k, v in changes.items() if k in allowed}
    if not changes:
        return
    conn = _get_db()
    now = _now()
    conn.execute(
        "INSERT INTO report_comments (term_id, student_pk, updated_by, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (term_id, student_pk) DO NOTHING",
        (term_id, student_pk, updated_by, now),
    )
    conn.execute(
        f"UPDATE report_comments SET {', '.join(f'{k} = ?' for k in changes)}, updated_by = ?, updated_at = ? "
        "WHERE term_id = ? AND student_pk = ?",
        (*changes.values(), updated_by, now, term_id, student_pk),
    )
    conn.commit()
    conn.close()

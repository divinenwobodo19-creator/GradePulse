"""
Data protection from the November 2026 security assessment (H7, M11):
deleted records are removed for good after the purge period, a school can
export its data, and reads and changes of student data are logged.
"""
import csv
import io
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from linucb_brain.api import app as app_module
from linucb_brain.api import auth, store
from linucb_brain.api.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _fresh_limits():
    app_module.SIGNUP_LIMITER.reset()
    yield


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def school(client):
    admin = client.post("/auth/signup", json={
        "email": f"dp_{uuid.uuid4().hex[:6]}@dp.local", "password": "Kettle-Mango-42", "school_name": "Data School",
    }).json()
    h = _hdr(admin["token"])
    class_id = client.post(f"/classes/{admin['school_id']}", headers=h, json={"label": "JSS2A"}).json()["class_id"]
    for sid, name in (("D1", "Ada Obi"), ("D2", "=HYPERLINK(\"x\")")):
        client.post("/students", headers=h, json={"student_id": sid, "name": name, "class_id": class_id})
        client.post("/bulk-update", headers=h, json={"entries": [{"student_id": sid, "subject": "MATH", "score": 0.62}]})
    return {"h": h, "admin": admin, "class_id": class_id}


def _age_archives(school_id, days):
    then = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = auth._get_db()
    for table in ("students", "classes", "schools"):
        conn.execute(f"UPDATE {table} SET archived_at = ? WHERE school_id = ? AND archived_at IS NOT NULL",
                     (then, school_id))
    conn.commit()
    conn.close()


def _count(sql, *params):
    conn = auth._get_db()
    n = conn.execute(sql, params).fetchone()[0]
    conn.close()
    return n


def test_deleted_students_are_purged_with_their_scores_after_the_period(client, school):
    sid = school["admin"]["school_id"]
    pk = store.get_student(sid, "D1").pk
    assert client.delete("/students/D1", headers=school["h"]).status_code == 200

    app_module.run_maintenance()  # too recent: kept, so the operator can still undo a mistake
    assert _count("SELECT COUNT(*) FROM students WHERE id = ?", pk) == 1

    _age_archives(sid, app_module.ARCHIVE_PURGE_DAYS + 1)
    result = app_module.run_maintenance()
    assert result["students"] >= 1 and f"s{pk}" in result["engine_keys"]
    assert _count("SELECT COUNT(*) FROM students WHERE id = ?", pk) == 0
    assert _count("SELECT COUNT(*) FROM scores WHERE student_pk = ?", pk) == 0
    assert f"s{pk}" not in app_module.brain_instance.students
    # The other student is untouched.
    assert [s["student_id"] for s in client.get("/students", headers=school["h"]).json()] == ["D2"]


def test_a_deleted_school_is_purged_entirely(client, school):
    sid = school["admin"]["school_id"]
    assert client.delete(f"/schools/{sid}", headers=school["h"]).status_code == 200
    _age_archives(sid, app_module.ARCHIVE_PURGE_DAYS + 1)
    app_module.run_maintenance()
    assert _count("SELECT COUNT(*) FROM students WHERE school_id = ?", sid) == 0
    assert _count("SELECT COUNT(*) FROM classes WHERE school_id = ?", sid) == 0
    assert _count("SELECT COUNT(*) FROM schools WHERE school_id = ?", sid) == 0


def test_admin_exports_the_school_data_as_csv(client, school):
    r = client.get("/export", headers=school["h"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(r.content))
    assert sorted(archive.namelist()) == ["classes.csv", "scores.csv", "students.csv"]
    students = list(csv.DictReader(io.StringIO(archive.read("students.csv").decode())))
    assert {s["student_id"] for s in students} == {"D1", "D2"}
    # A name that looks like a formula is defused for Excel.
    assert any(s["name"].startswith("'=") for s in students)
    scores = list(csv.DictReader(io.StringIO(archive.read("scores.csv").decode())))
    assert {(s["student_id"], s["subject"], s["score_percent"]) for s in scores} == {("D1", "MATH", "62.0"), ("D2", "MATH", "62.0")}


def test_export_and_audit_log_are_admin_only(client, school):
    code = client.post("/invites", headers=school["h"]).json()["code"]
    t = client.post("/auth/signup", json={
        "email": f"dpt_{uuid.uuid4().hex[:6]}@dp.local", "password": "Kettle-Mango-42", "invite_code": code}).json()
    assert client.get("/export", headers=_hdr(t["token"])).status_code == 403
    assert client.get("/audit", headers=_hdr(t["token"])).status_code == 403


def test_reads_and_changes_of_student_data_are_logged(client, school):
    h = school["h"]
    client.get("/students", headers=h)
    client.get("/students/D1/scores", headers=h)
    client.put("/students/D1", headers=h, json={"name": "Ada O."})
    client.get("/export", headers=h)
    log = client.get("/audit", headers=h).json()
    actions = [e["action"] for e in log]
    for action in ("add_student", "enter_scores", "view_students", "view_student_scores", "edit_student",
                   "export_school_data"):
        assert action in actions, action
    assert all(e["who"] == school["admin"]["email"] for e in log)
    assert log[0]["action"] == "export_school_data"  # newest first


def test_audit_entries_expire(client, school):
    conn = auth._get_db()
    old = (datetime.now(timezone.utc) - timedelta(days=app_module.AUDIT_KEEP_DAYS + 1)).isoformat()
    conn.execute("UPDATE audit_log SET at = ? WHERE school_id = ?", (old, school["admin"]["school_id"]))
    conn.commit()
    conn.close()
    app_module.run_maintenance()
    assert client.get("/audit", headers=school["h"]).json() == []

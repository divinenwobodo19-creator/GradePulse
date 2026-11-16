"""
Fixes from the November 2026 security assessment (H1, H2, H3, L6, L7):
a teacher cannot read another class's student through POST /students, and
uploads, score sheets and text fields have upper bounds. Offline, TestClient.
"""
import io
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

import ingest
from linucb_brain.api import app as app_module
from linucb_brain.api.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _fresh_limits():
    app_module.SIGNUP_LIMITER.reset()
    app_module.INGEST_LIMITER.reset()
    yield


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def school(client):
    admin = client.post("/auth/signup", json={
        "email": f"adm_{uuid.uuid4().hex[:6]}@sl.local", "password": "Kettle-Mango-42", "school_name": "Limits School",
    }).json()
    a = _hdr(admin["token"])
    code = client.post("/invites", headers=a).json()["code"]
    teacher = client.post("/auth/signup", json={
        "email": f"tch_{uuid.uuid4().hex[:6]}@sl.local", "password": "Kettle-Mango-42", "invite_code": code,
    }).json()
    sid = admin["school_id"]
    class_a = client.post(f"/classes/{sid}", headers=a, json={"label": "JSS1A"}).json()["class_id"]
    class_b = client.post(f"/classes/{sid}", headers=a, json={"label": "JSS1B"}).json()["class_id"]
    for student_id, class_id in (("IN_A", class_a), ("IN_B", class_b)):
        assert client.post("/students", headers=a, json={
            "student_id": student_id, "name": f"Pupil {student_id}", "class_id": class_id,
        }).status_code == 200
        assert client.post("/bulk-update", headers=a, json={"entries": [
            {"student_id": student_id, "subject": "MATH", "score": 0.2}]}).status_code == 200
    client.put(f"/members/{teacher['id']}/classes", headers=a, json={"class_ids": [class_a]})
    return {"admin": a, "teacher": _hdr(teacher["token"]), "a": class_a, "b": class_b}


# ── H1: POST /students no longer returns a student from another class ─────────

def test_teacher_cannot_read_another_class_student_by_adding_its_id(client, school):
    r = client.post("/students", headers=school["teacher"], json={
        "student_id": "IN_B", "name": "anything", "class_id": school["a"]})
    assert r.status_code == 409
    assert "Pupil IN_B" not in r.text and "grade_history" not in r.text
    # Nothing moved: the student is still in class B, out of the teacher's view.
    assert [s["student_id"] for s in client.get("/students", headers=school["teacher"]).json()] == ["IN_A"]


def test_teacher_adding_an_existing_id_in_their_own_class_still_works(client, school):
    r = client.post("/students", headers=school["teacher"], json={
        "student_id": "IN_A", "name": "anything", "class_id": school["a"]})
    assert r.status_code == 200 and r.json()["name"] == "Pupil IN_A"


# ── H3 and L6: score sheets and text fields have limits ──────────────────────

def test_score_sheet_entry_count_is_capped(client, school):
    entries = [{"student_id": "IN_A", "subject": "MATH", "score": 0.5}] * 2001
    assert client.post("/bulk-update", headers=school["admin"], json={"entries": entries}).status_code == 422


def test_scores_only_for_the_school_subjects(client, school):
    a = school["admin"]
    ok = client.post("/bulk-update", headers=a, json={"entries": [{"student_id": "IN_A", "subject": " math ", "score": 0.5}]})
    assert ok.status_code == 200
    r = client.post("/bulk-update", headers=a, json={"entries": [{"student_id": "IN_A", "subject": "ASTROLOGY", "score": 0.5}]})
    assert r.status_code == 400
    r = client.post("/bulk-update", headers=a, json={"entries": [{"student_id": "IN_A", "subject": "M" * 41, "score": 0.5}]})
    assert r.status_code == 422


def test_text_fields_have_length_limits(client, school):
    a = school["admin"]
    assert client.post("/students", headers=a, json={"student_id": "LONG", "name": "N" * 121, "class_id": school["a"]}).status_code == 422
    assert client.put("/students/IN_A", headers=a, json={"name": "N" * 121}).status_code == 422
    assert client.post("/students", headers=a, json={
        "student_id": "META", "name": "Meta", "class_id": school["a"], "metadata": {"x": "y" * 5000}}).status_code == 422


def test_oversized_request_bodies_are_refused(client, school):
    body = b'{"entries": [' + b" " * (600 * 1024) + b"]}"
    r = client.post("/bulk-update", headers={**school["admin"], "Content-Type": "application/json"}, content=body)
    assert r.status_code == 413


# ── H2 and L7: uploads are capped, read off the event loop, and errors are plain ─

def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(client, headers, name, data, mime="text/csv"):
    return client.post("/ingest", headers=headers, data={"type": "students", "dry_run": "true"},
                       files={"file": (name, data, mime)})


def test_large_csv_is_refused_quickly(client, school):
    data = "student_id,name\n" + "".join(f"S{i},Name {i}\n" for i in range(ingest.MAX_ROWS + 10))
    started = time.monotonic()
    r = _upload(client, school["admin"], "big.csv", data.encode())
    assert r.status_code == 400 and "rows" in r.json()["detail"]
    assert time.monotonic() - started < 10


def test_large_xlsx_is_refused_quickly(client, school):
    data = _xlsx([["student_id", "name"]] + [[f"S{i}", f"Name {i}"] for i in range(ingest.MAX_ROWS + 10)])
    started = time.monotonic()
    r = _upload(client, school["admin"], "big.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert r.status_code == 400 and "rows" in r.json()["detail"]
    assert time.monotonic() - started < 10


def test_xlsx_that_unpacks_too_large_is_refused(client, school, monkeypatch):
    monkeypatch.setattr(ingest, "MAX_XLSX_UNPACKED_BYTES", 1000)
    r = _upload(client, school["admin"], "small.xlsx", _xlsx([["student_id", "name"], ["S1", "A"]]))
    assert r.status_code == 400 and "too large" in r.json()["detail"]


def test_broken_file_gets_a_plain_message(client, school):
    r = _upload(client, school["admin"], "list.xlsx", b"this is not a spreadsheet")
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "/tmp" not in detail and "Traceback" not in detail and "zip" not in detail.lower()


def test_uploads_are_rate_limited_per_user(client, school, monkeypatch):
    monkeypatch.setattr(app_module, "INGEST_LIMITER", app_module.SlidingWindowLimiter(max_requests=2, window_seconds=600))
    data = b"student_id,name\nS1,Ada\n"
    assert _upload(client, school["admin"], "a.csv", data).status_code == 200
    assert _upload(client, school["admin"], "a.csv", data).status_code == 200
    assert _upload(client, school["admin"], "a.csv", data).status_code == 429


# ── The streaming Excel reader reads what pandas used to ────────────────────

def test_xlsx_reader_handles_layout_quirks(tmp_path):
    path = tmp_path / "list.xlsx"
    path.write_bytes(_xlsx([
        [None, None, None],
        ["Student ID", "Name", "Name"],
        ["S1", "Ada Obi", "dup"],
        [None, None, None],
        [102, "Chidi", None],
        ["S3", 0.5, None],
    ]))
    rows = ingest.read_data_file(str(path))
    assert rows == [
        {"student_id": "S1", "name": "Ada Obi", "name.1": "dup"},
        {"student_id": "102", "name": "Chidi", "name.1": ""},
        {"student_id": "S3", "name": "0.5", "name.1": ""},
    ]


def test_trailing_blank_rows_end_the_sheet(tmp_path):
    path = tmp_path / "list.csv"
    path.write_text("student_id,name\nS1,Ada\n" + ",\n" * (ingest.BLANK_RUN_END + 5) + "S2,Late\n")
    assert [r["student_id"] for r in ingest.read_data_file(str(path))] == ["S1"]

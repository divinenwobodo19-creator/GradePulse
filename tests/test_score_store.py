"""
Scores as dated records: derived performance, corrections, per-student
history, archiving, and roster imports. Run offline against TestClient.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from linucb_brain.api import app as app_module
from linucb_brain.api.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _fresh_signup_budget():
    app_module.SIGNUP_LIMITER.reset()
    yield
    app_module.SIGNUP_LIMITER.reset()


@pytest.fixture
def school(client):
    r = client.post("/auth/signup", json={
        "email": f"store_{uuid.uuid4().hex[:6]}@store.local", "password": "Passw0rd!",
        "school_name": "Store School",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    return {"h": {"Authorization": f"Bearer {data['token']}"}, "id": data["school_id"]}


def _add(client, school, sid="S001", **extra):
    r = client.post("/students", headers=school["h"], json={"student_id": sid, "name": "Ada Obi", **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _enter(client, school, score, sid="S001", subject="MATH", **sitting):
    r = client.post("/bulk-update", headers=school["h"], json={
        "entries": [{"student_id": sid, "subject": subject, "score": score}], **sitting,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _student(client, school, sid="S001"):
    return next(s for s in client.get("/students", headers=school["h"]).json() if s["student_id"] == sid)


def test_performance_score_follows_entered_scores(client, school):
    assert _add(client, school)["performance_score"] == 0.5  # baseline until a score exists

    _enter(client, school, 0.2, assessed_on="2026-09-07")
    assert _student(client, school)["performance_score"] == pytest.approx(0.2)

    _enter(client, school, 0.8, subject="ENGLISH", assessed_on="2026-09-14")
    student = _student(client, school)
    assert student["performance_score"] == pytest.approx(0.5)
    assert student["grade_history"] == {"MATH": [0.2], "ENGLISH": [0.8]}


def test_performance_uses_only_the_most_recent_scores(client, school):
    _add(client, school)
    for week, score in enumerate([0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0], start=1):
        _enter(client, school, score, assessed_on=f"2026-09-{week:02d}")
    assert _student(client, school)["performance_score"] == pytest.approx(1.0)


def test_reentering_a_sitting_corrects_the_score(client, school):
    _add(client, school)
    sitting = {"assessed_on": "2026-09-07", "label": "Week 1 test"}
    _enter(client, school, 0.3, **sitting)
    _enter(client, school, 0.7, **sitting)                       # correction
    _enter(client, school, 0.9, assessed_on="2026-09-14", label="Week 2 test")

    assert _student(client, school)["grade_history"] == {"MATH": [0.7, 0.9]}
    scores = client.get("/students/S001/scores", headers=school["h"]).json()
    assert [(s["assessed_on"], s["label"], s["score"]) for s in scores] == [
        ("2026-09-07", "Week 1 test", 0.7), ("2026-09-14", "Week 2 test", 0.9),
    ]


def test_scores_are_ordered_by_test_date_not_entry_order(client, school):
    _add(client, school)
    _enter(client, school, 0.9, assessed_on="2026-09-14")
    _enter(client, school, 0.1, assessed_on="2026-09-07")  # entered late
    assert _student(client, school)["grade_history"] == {"MATH": [0.1, 0.9]}


def test_engine_reward_is_not_recorded_as_a_grade(client, school):
    _add(client, school)
    cid = f"C_{uuid.uuid4().hex[:6]}"
    assert client.post("/content", headers=school["h"], json={
        "content_id": cid, "title": "Fractions", "topic": "MATH", "difficulty": 2, "content_type": "video",
    }).status_code == 200
    assert client.post("/update", headers=school["h"], json={
        "student_id": "S001", "content_id": cid, "reward": -0.5,
    }).status_code == 200
    assert _student(client, school)["grade_history"] == {}


def test_triage_uses_recorded_scores_and_skips_unassessed(client, school):
    for sid in ("LOW", "MID", "HIGH", "NONE"):
        _add(client, school, sid)
    _enter(client, school, 0.2, "LOW")
    _enter(client, school, 0.3, "LOW", assessed_on="2026-09-01")
    _enter(client, school, 0.5, "MID")
    _enter(client, school, 0.9, "HIGH")
    _enter(client, school, 0.9, "NONE", subject="ENGLISH")

    triage = client.post("/triage", headers=school["h"], json={"subject": "MATH"}).json()
    tiers = {name: [s["student_id"] for s in tier["students"]] for name, tier in triage["tiers"].items()}
    assert tiers == {"remediation": ["LOW"], "on_track": ["MID"], "ahead": ["HIGH"]}
    assert triage["total_students"] == 3
    low = triage["tiers"]["remediation"]["students"][0]
    assert (low["predicted_score"], low["attempts"]) == (0.25, 2)


def test_deleted_student_is_archived_and_its_id_can_be_reused(client, school):
    _add(client, school)
    _enter(client, school, 0.4)
    assert client.delete("/students/S001", headers=school["h"]).status_code == 200
    assert client.get("/students", headers=school["h"]).json() == []
    assert client.get("/summary", headers=school["h"]).json()["student_count"] == 0

    fresh = _add(client, school)          # same ID, new student
    assert fresh["grade_history"] == {}


def test_deleting_a_class_archives_its_students_only(client, school):
    class_id = client.post(f"/classes/{school['id']}", headers=school["h"], json={"label": "JSS1A"}).json()["class_id"]
    _add(client, school, "IN", class_id=class_id)
    _add(client, school, "OUT")
    assert client.delete(f"/classes/{school['id']}/{class_id}", headers=school["h"]).status_code == 200
    assert [s["student_id"] for s in client.get("/students", headers=school["h"]).json()] == ["OUT"]


def test_roster_import_keeps_teacher_scores_and_replaces_imported_history(client, school):
    def upload(csv: str):
        r = client.post("/ingest", headers=school["h"], data={"type": "students"},
                        files={"file": ("roster.csv", csv.encode(), "text/csv")})
        assert r.status_code == 200, r.text
        return r.json()["report"]

    upload("student_id,name,grade_history_MATH\nS001,Ada Obi,0.4;0.5\n")
    assert _student(client, school)["grade_history"] == {"MATH": [0.4, 0.5]}
    _enter(client, school, 0.9, assessed_on="2030-01-01")
    upload("student_id,name,grade_history_MATH\nS001,Ada Obi,0.6\n")

    assert _student(client, school)["grade_history"] == {"MATH": [0.6, 0.9]}
    assert client.get("/summary", headers=school["h"]).json()["student_count"] == 1


def test_recommend_works_for_a_stored_student(client, school):
    _add(client, school)
    assert client.post("/content", headers=school["h"], json={
        "content_id": f"C_{uuid.uuid4().hex[:6]}", "title": "Algebra", "topic": "MATH",
        "difficulty": 2, "content_type": "video",
    }).status_code == 200
    r = client.post("/recommend", headers=school["h"], json={"student_id": "S001", "top_n": 1})
    assert r.status_code == 200 and len(r.json()) == 1


def test_triage_can_be_limited_to_one_class(client, school):
    class_id = client.post(f"/classes/{school['id']}", headers=school["h"], json={"label": "JSS2B"}).json()["class_id"]
    _add(client, school, "IN", class_id=class_id)
    _add(client, school, "OUT")
    _enter(client, school, 0.2, "IN")
    _enter(client, school, 0.9, "OUT")

    whole = client.post("/triage", headers=school["h"], json={"subject": "MATH"}).json()
    one = client.post("/triage", headers=school["h"], json={"subject": "MATH", "class_id": class_id}).json()
    assert whole["total_students"] == 2
    assert one["total_students"] == 1
    assert [s["student_id"] for s in one["tiers"]["remediation"]["students"]] == ["IN"]

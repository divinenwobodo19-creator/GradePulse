"""
Admins see the whole school; a teacher sees only the classes the admin
assigned them. Run offline against TestClient.
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


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def school(client):
    """An admin, a teacher, two classes (A taught by the teacher, B not) and
    one scored student in each class plus one with no class."""
    admin = client.post("/auth/signup", json={
        "email": f"adm_{uuid.uuid4().hex[:6]}@tc.local", "password": "Passw0rd!", "school_name": "Scope School",
    }).json()
    a = _hdr(admin["token"])
    code = client.post("/invites", headers=a).json()["code"]
    teacher = client.post("/auth/signup", json={
        "email": f"tch_{uuid.uuid4().hex[:6]}@tc.local", "password": "Passw0rd!", "invite_code": code,
    }).json()
    sid = admin["school_id"]
    class_a = client.post(f"/classes/{sid}", headers=a, json={"label": "JSS1A"}).json()["class_id"]
    class_b = client.post(f"/classes/{sid}", headers=a, json={"label": "JSS1B"}).json()["class_id"]
    for student_id, class_id in (("IN_A", class_a), ("IN_B", class_b), ("NO_CLASS", "")):
        assert client.post("/students", headers=a, json={
            "student_id": student_id, "name": student_id, "class_id": class_id,
        }).status_code == 200
        client.post("/bulk-update", headers=a, json={"entries": [
            {"student_id": student_id, "subject": "MATH", "score": 0.2}]})
    r = client.put(f"/members/{teacher['id']}/classes", headers=a, json={"class_ids": [class_a]})
    assert r.status_code == 200 and r.json()["class_ids"] == [class_a]
    return {"admin": a, "teacher": _hdr(teacher["token"]), "teacher_id": teacher["id"],
            "school_id": sid, "a": class_a, "b": class_b}


def _ids(rows):
    return sorted(r["student_id"] for r in rows)


def test_admin_sees_everything_teacher_sees_their_classes(client, school):
    assert _ids(client.get("/students", headers=school["admin"]).json()) == ["IN_A", "IN_B", "NO_CLASS"]
    assert _ids(client.get("/students", headers=school["teacher"]).json()) == ["IN_A"]
    assert [c["class_id"] for c in client.get(f"/classes/{school['school_id']}", headers=school["teacher"]).json()] == [school["a"]]
    assert _ids(client.get("/scores", headers=school["teacher"]).json()) == ["IN_A"]
    assert client.get("/summary", headers=school["teacher"]).json()["student_count"] == 1
    assert client.get("/summary", headers=school["admin"]).json()["student_count"] == 3

    triage = client.post("/triage", headers=school["teacher"], json={"subject": "MATH"}).json()
    assert triage["total_students"] == 1


def test_teacher_cannot_reach_students_or_classes_outside_their_own(client, school):
    t = school["teacher"]
    assert client.get("/students", headers=t, params={"class_id": school["b"]}).status_code == 403
    assert client.get("/scores", headers=t, params={"class_id": school["b"]}).status_code == 403
    assert client.post("/triage", headers=t, json={"subject": "MATH", "class_id": school["b"]}).status_code == 403
    assert client.put("/students/IN_B", headers=t, json={"name": "X"}).status_code == 404
    assert client.get("/students/IN_B/scores", headers=t).status_code == 404
    assert client.post("/bulk-update", headers=t, json={"entries": [
        {"student_id": "IN_B", "subject": "MATH", "score": 0.9}]}).status_code == 404
    assert client.post("/recommend", headers=t, json={"student_id": "IN_B"}).status_code == 400


def test_teacher_works_inside_their_classes_only(client, school):
    t = school["teacher"]
    assert client.post("/bulk-update", headers=t, json={"entries": [
        {"student_id": "IN_A", "subject": "MATH", "score": 0.9}]}).status_code == 200
    assert client.put("/students/IN_A", headers=t, json={"name": "Renamed"}).status_code == 200

    # Adding needs one of their classes; moving out of their classes is refused.
    assert client.post("/students", headers=t, json={"student_id": "NEW1", "name": "New"}).status_code == 400
    assert client.post("/students", headers=t, json={
        "student_id": "NEW2", "name": "New", "class_id": school["b"]}).status_code == 403
    assert client.post("/students", headers=t, json={
        "student_id": "NEW3", "name": "New", "class_id": school["a"]}).status_code == 200
    assert client.put("/students/IN_A", headers=t, json={"class_id": school["b"]}).status_code == 403
    assert client.put("/students/IN_A", headers=t, json={"class_id": ""}).status_code == 400


def test_only_admins_delete_students_import_lists_and_manage_classes(client, school):
    t, a, sid = school["teacher"], school["admin"], school["school_id"]
    assert client.delete("/students/IN_A", headers=t).status_code == 403
    r = client.post("/ingest", headers=t, data={"type": "students"},
                    files={"file": ("list.csv", b"student_id,name\nZ1,Zee\n", "text/csv")})
    assert r.status_code == 403
    assert client.post(f"/classes/{sid}", headers=t, json={"label": "JSS3C"}).status_code == 403
    assert client.put(f"/classes/{sid}/{school['a']}", headers=t, json={"label": "Renamed"}).status_code == 403
    assert client.delete("/students/IN_A", headers=a).status_code == 200


def test_unassigned_teacher_sees_nothing_and_assignment_changes_take_effect(client, school):
    a, t = school["admin"], school["teacher"]
    url = f"/members/{school['teacher_id']}/classes"
    assert client.put(url, headers=a, json={"class_ids": []}).json()["class_ids"] == []
    assert client.get("/students", headers=t).json() == []
    assert client.get(f"/classes/{school['school_id']}", headers=t).json() == []

    assert client.put(url, headers=a, json={"class_ids": [school["b"], "not-a-class"]}).json()["class_ids"] == [school["b"]]
    assert _ids(client.get("/students", headers=t).json()) == ["IN_B"]

    members = {m["id"]: m for m in client.get("/members", headers=a).json()}
    assert members[school["teacher_id"]]["class_ids"] == [school["b"]]


def test_class_assignment_is_admin_only_and_for_teachers_only(client, school):
    a, t = school["admin"], school["teacher"]
    assert client.put(f"/members/{school['teacher_id']}/classes", headers=t,
                      json={"class_ids": [school["b"]]}).status_code == 403
    admin_id = next(m["id"] for m in client.get("/members", headers=a).json() if m["role"] == "admin")
    assert client.put(f"/members/{admin_id}/classes", headers=a, json={"class_ids": []}).status_code == 400
    assert client.put("/members/nobody/classes", headers=a, json={"class_ids": []}).status_code == 404


def test_invite_can_put_the_teacher_straight_into_classes(client, school):
    a = school["admin"]
    r = client.post("/invites", headers=a, json={"class_ids": [school["b"]]})
    assert r.status_code == 200 and r.json()["class_ids"] == [school["b"]]
    assert client.get("/invites", headers=a).json()[0]["class_ids"] == [school["b"]]

    teacher = client.post("/auth/signup", json={
        "email": f"inv_{uuid.uuid4().hex[:6]}@tc.local", "password": "Passw0rd!", "invite_code": r.json()["code"],
    }).json()
    assert _ids(client.get("/students", headers=_hdr(teacher["token"])).json()) == ["IN_B"]

    assert client.post("/invites", headers=a, json={"class_ids": ["not-a-class"]}).status_code == 400
    assert client.post("/invites", headers=a).json()["class_ids"] == []  # no classes chosen: still allowed

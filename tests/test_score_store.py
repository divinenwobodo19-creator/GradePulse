"""
Scores as dated records: derived performance, corrections, per-student
history, archiving, and roster imports. Run offline against TestClient.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from linucb_brain.api import app as app_module
from linucb_brain.api.app import app
from conftest import OPERATOR_HEADERS


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
    assert client.post("/content", headers={**school["h"], **OPERATOR_HEADERS}, json={
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
    assert client.post("/content", headers={**school["h"], **OPERATOR_HEADERS}, json={
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


def test_student_can_be_moved_between_classes_and_out_of_one(client, school):
    a, b = (client.post(f"/classes/{school['id']}", headers=school["h"], json={"label": label}).json()["class_id"]
            for label in ("JSS1A", "JSS1B"))
    _add(client, school, class_id=a)

    moved = client.put("/students/S001", headers=school["h"], json={"class_id": b, "name": "Ada O."})
    assert moved.status_code == 200
    assert (moved.json()["class_id"], moved.json()["name"]) == (b, "Ada O.")

    cleared = client.put("/students/S001", headers=school["h"], json={"class_id": ""})
    assert cleared.status_code == 200 and cleared.json()["class_id"] == ""
    assert client.put("/students/S001", headers=school["h"], json={"class_id": "nope"}).status_code == 400


def test_class_cannot_be_renamed_to_an_existing_or_empty_name(client, school):
    a, b = (client.post(f"/classes/{school['id']}", headers=school["h"], json={"label": label}).json()["class_id"]
            for label in ("JSS3A", "JSS3B"))
    url = f"/classes/{school['id']}/{b}"
    assert client.put(url, headers=school["h"], json={"label": "jss3a"}).status_code == 400
    assert client.put(url, headers=school["h"], json={"label": "  "}).status_code == 400
    assert client.put(url, headers=school["h"], json={"label": "jss3b"}).status_code == 200   # its own name
    assert client.put(url, headers=school["h"], json={"label": "JSS3C"}).json()["label"] == "JSS3C"


def test_roster_upload_over_the_size_limit_is_rejected(client, school):
    big = b"student_id,name\n" + b"x" * (app_module.MAX_UPLOAD_BYTES + 1)
    r = client.post("/ingest", headers=school["h"], data={"type": "students"},
                    files={"file": ("roster.csv", big, "text/csv")})
    assert r.status_code == 413


def test_roster_dry_run_reports_without_saving(client, school):
    r = client.post("/ingest", headers=school["h"], data={"type": "students", "dry_run": "true"},
                    files={"file": ("roster.csv", b"student_id,name,class_label\nS9,Tobi Ade,JSS1A\n,No Id,JSS1A\n", "text/csv")})
    assert r.status_code == 200, r.text
    stats = r.json()["report"]["stats"]
    assert (stats["students_valid"], stats["students_skipped"]) == (1, 1)
    assert client.get("/students", headers=school["h"]).json() == []
    assert client.get(f"/classes/{school['id']}", headers=school["h"]).json() == []


# ── Schools, classes and subjects in the store ─────────────────────────────

def test_school_starts_with_default_subjects_and_admin_can_replace_them(client, school):
    assert client.get("/subjects", headers=school["h"]).json() == {
        "subjects": ["MATH", "ENGLISH", "SCIENCE", "HISTORY"]
    }
    r = client.put("/subjects", headers=school["h"], json={
        "subjects": ["Mathematics", " basic science ", "MATHEMATICS", "", "Yoruba"],
    })
    assert r.status_code == 200
    assert r.json() == {"subjects": ["MATHEMATICS", "BASIC SCIENCE", "YORUBA"]}
    assert client.get("/subjects", headers=school["h"]).json() == r.json()

    assert client.put("/subjects", headers=school["h"], json={"subjects": [" "]}).status_code == 400
    assert client.put("/subjects", headers=school["h"], json={"subjects": ["x" * 41]}).status_code == 422


def test_subjects_are_per_school_and_only_admins_change_them(client, school):
    client.put("/subjects", headers=school["h"], json={"subjects": ["IGBO"]})

    code = client.post("/invites", headers=school["h"]).json()["code"]
    teacher = client.post("/auth/signup", json={
        "email": f"subj_{uuid.uuid4().hex[:6]}@store.local", "password": "Passw0rd!", "invite_code": code,
    }).json()
    t = {"Authorization": f"Bearer {teacher['token']}"}
    assert client.get("/subjects", headers=t).json() == {"subjects": ["IGBO"]}
    assert client.put("/subjects", headers=t, json={"subjects": ["FRENCH"]}).status_code == 403

    other = client.post("/auth/signup", json={
        "email": f"other_{uuid.uuid4().hex[:6]}@store.local", "password": "Passw0rd!",
    }).json()
    assert "IGBO" not in client.get("/subjects", headers={"Authorization": f"Bearer {other['token']}"}).json()["subjects"]


def test_class_name_is_free_again_after_the_class_is_deleted(client, school):
    url = f"/classes/{school['id']}"
    first = client.post(url, headers=school["h"], json={"label": "SS1 Gold"}).json()
    assert (first["label"], first["grade_level"]) == ("SS1 GOLD", "")
    assert client.post(url, headers=school["h"], json={"label": "ss1 gold"}).status_code == 400
    assert client.delete(f"{url}/{first['class_id']}", headers=school["h"]).status_code == 200
    again = client.post(url, headers=school["h"], json={"label": "SS1 Gold"})
    assert again.status_code == 200 and again.json()["class_id"] != first["class_id"]
    assert [c["label"] for c in client.get(url, headers=school["h"]).json()] == ["SS1 GOLD"]


def test_roster_import_creates_classes_in_the_store(client, school):
    csv = b"student_id,name,class_label\nR1,Ada Obi,JSS2A\nR2,Tobi Ade,JSS2A\nR3,Yemi Bello,JSS2B\n"
    r = client.post("/ingest", headers=school["h"], data={"type": "students"},
                    files={"file": ("roster.csv", csv, "text/csv")})
    assert r.status_code == 200, r.text
    classes = {c["label"]: c["class_id"] for c in client.get(f"/classes/{school['id']}", headers=school["h"]).json()}
    assert set(classes) == {"JSS2A", "JSS2B"}
    by_class = {s["student_id"]: s["class_id"] for s in client.get("/students", headers=school["h"]).json()}
    assert by_class == {"R1": classes["JSS2A"], "R2": classes["JSS2A"], "R3": classes["JSS2B"]}

    # A second upload reuses the existing classes.
    client.post("/ingest", headers=school["h"], data={"type": "students"},
                files={"file": ("roster.csv", b"student_id,name,class_label\nR4,Kunle Ade,JSS2A\n", "text/csv")})
    assert len(client.get(f"/classes/{school['id']}", headers=school["h"]).json()) == 2


def test_legacy_registry_file_is_adopted_once(tmp_path, monkeypatch):
    from linucb_brain.api import auth, store

    monkeypatch.setattr(auth, "DB_PATH", str(tmp_path / "fresh.db"))
    auth.init_db()
    store.init_store()
    legacy = {"schools": [{"school_id": "old00001", "name": "Old School", "classes": [
        {"class_id": "cls00001", "label": "JSS1A", "grade_level": "JSS1", "arm": "A"},
    ]}]}
    assert store.adopt_legacy_registry(legacy) == 1
    assert store.get_school("old00001") == {"school_id": "old00001", "name": "OLD SCHOOL", "classes": [
        {"class_id": "cls00001", "label": "JSS1A", "grade_level": "JSS1", "arm": "A"},
    ]}
    assert store.adopt_legacy_registry({"schools": [{"school_id": "new00001", "name": "Late", "classes": []}]}) == 0
    assert store.get_school("new00001") is None


def test_school_scores_feed_reports_and_stay_inside_the_school(client, school):
    class_id = client.post(f"/classes/{school['id']}", headers=school["h"], json={"label": "JSS1R"}).json()["class_id"]
    _add(client, school, "IN", class_id=class_id)
    _add(client, school, "OUT")
    _add(client, school, "GONE")
    _enter(client, school, 0.9, "IN", assessed_on="2026-09-14", label="Week 2")
    _enter(client, school, 0.3, "IN", assessed_on="2026-09-07", label="Week 1")
    _enter(client, school, 0.5, "OUT", subject="ENGLISH", assessed_on="2026-09-07")
    _enter(client, school, 0.1, "GONE", assessed_on="2026-09-07")
    client.delete("/students/GONE", headers=school["h"])

    rows = client.get("/scores", headers=school["h"]).json()
    assert [(r["student_id"], r["subject"], r["score"], r["assessed_on"], r["label"]) for r in rows] == [
        ("IN", "MATH", 0.3, "2026-09-07", "Week 1"),
        ("OUT", "ENGLISH", 0.5, "2026-09-07", ""),
        ("IN", "MATH", 0.9, "2026-09-14", "Week 2"),
    ]
    one_class = client.get("/scores", headers=school["h"], params={"class_id": class_id}).json()
    assert {r["student_id"] for r in one_class} == {"IN"}

    other = client.post("/auth/signup", json={
        "email": f"rep_{uuid.uuid4().hex[:6]}@store.local", "password": "Passw0rd!",
    }).json()
    other_h = {"Authorization": f"Bearer {other['token']}"}
    assert client.get("/scores", headers=other_h).json() == []
    assert client.get("/scores", headers=other_h, params={"class_id": class_id}).json() == []
    assert client.get("/scores").status_code == 401


def test_recommendations_can_be_switched_off(client, school, monkeypatch):
    _add(client, school)
    monkeypatch.setattr(app_module, "RECOMMENDATIONS_ENABLED", False)
    r = client.post("/recommend", headers=school["h"], json={"student_id": "S001", "top_n": 1})
    assert r.status_code == 404
    assert client.get("/health").json()["features"] == {"recommendations": False}

    monkeypatch.setattr(app_module, "RECOMMENDATIONS_ENABLED", True)
    assert client.get("/health").json()["features"] == {"recommendations": True}


def test_health_reports_the_package_version(client):
    from linucb_brain import __version__
    assert client.get("/health").json()["version"] == __version__


def test_unexpected_error_is_logged_with_a_reference_the_client_can_quote(client, school, monkeypatch, caplog):
    from linucb_brain.api import store

    def boom(*args, **kwargs):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(store, "list_students", boom)
    with TestClient(app, raise_server_exceptions=False) as quiet:
        with caplog.at_level("ERROR", logger="gradepulse"):
            r = quiet.get("/students", headers=school["h"])
    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == "Internal server error" and "disk on fire" not in r.text
    assert any(body["error_id"] in rec.getMessage() and rec.exc_info for rec in caplog.records)


def test_summary_counts_only_this_schools_scores(client, school):
    _add(client, school)
    _enter(client, school, 0.5)
    _enter(client, school, 0.6, subject="ENGLISH")
    assert client.get("/summary", headers=school["h"]).json()["total_sessions"] == 2


def test_content_import_needs_the_operator_key(client, school):
    csv = b"content_id,title,topic,difficulty,content_type\nZ1,Fractions,MATH,2,video\n"
    r = client.post("/ingest", headers=school["h"], data={"type": "content"},
                    files={"file": ("content.csv", csv, "text/csv")})
    assert r.status_code == 403
    r = client.post("/ingest", headers={**school["h"], **OPERATOR_HEADERS}, data={"type": "content"},
                    files={"file": ("content.csv", csv, "text/csv")})
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("trusted, forwarded, expected", [
    (False, "6.6.6.6", "testclient"),             # header ignored unless trusted
    (True, "6.6.6.6", "6.6.6.6"),
    (True, "1.1.1.1, 6.6.6.6", "6.6.6.6"),         # right-most: added by the nearest proxy
    (True, "", "testclient"),
])
def test_client_address_for_rate_limits(monkeypatch, trusted, forwarded, expected):
    from starlette.requests import Request

    monkeypatch.setattr(app_module, "TRUST_FORWARDED_FOR", trusted)
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    request = Request({"type": "http", "headers": headers, "client": ("testclient", 50000)})
    assert app_module._client_host(request) == expected

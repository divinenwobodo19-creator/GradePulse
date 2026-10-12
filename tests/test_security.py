"""
Phase 2 security tests: school-ownership isolation, JWT hardening, and
auth rate limiting. Run offline against TestClient (no server required).
"""
import os
import subprocess
import sys
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from linucb_brain.api.app import app
from linucb_brain.api import auth

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _signup(client, prefix: str):
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@sec.local"
    r = client.post("/auth/signup", json={
        "email": email, "password": "Passw0rd!",
        "school_name": f"{prefix.upper()} School",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    return data["token"], data["school_id"]


def _hdr(token: str):
    return {"Authorization": f"Bearer {token}"}


# ── School-ownership isolation ────────────────────────────────────────────

@pytest.mark.parametrize("attempt", [
    "list_students_foreign_query",
    "update_foreign_student",
    "delete_foreign_student",
])
def test_cross_school_isolation(client, attempt):
    tok_a, sch_a = _signup(client, "alpha")
    tok_b, sch_b = _signup(client, "beta")

    # B creates a student in their own school.
    sid = f"b_stud_{uuid.uuid4().hex[:6]}"
    r = client.post("/students", headers=_hdr(tok_b), json={
        "student_id": sid, "name": "B Student", "current_topic": "Math",
    })
    assert r.status_code == 200

    if attempt == "list_students_foreign_query":
        # A cannot override the school filter to read B's roster.
        r = client.get("/students", params={"school_id": sch_b}, headers=_hdr(tok_a))
        assert r.status_code == 403
        # A's own list never contains B's student.
        r = client.get("/students", headers=_hdr(tok_a))
        assert r.status_code == 200
        assert all(s["student_id"] != sid for s in r.json())
    elif attempt == "update_foreign_student":
        r = client.put(f"/students/{sid}", headers=_hdr(tok_a),
                       json={"name": "Hacked"})
        assert r.status_code == 403
    else:
        r = client.delete(f"/students/{sid}", headers=_hdr(tok_a))
        assert r.status_code == 403
        assert sid in brain_student_ids(client, tok_b)["own"]


def brain_student_ids(client, token):
    r = client.get("/students", headers=_hdr(token))
    return {"own": [s["student_id"] for s in r.json()]}


def test_foreign_student_actions_blocked(client):
    tok_a, _ = _signup(client, "gamma")
    tok_b, _ = _signup(client, "delta")
    sid = f"act_{uuid.uuid4().hex[:6]}"
    assert client.post("/students", headers=_hdr(tok_b), json={
        "student_id": sid, "name": "Target", "current_topic": "Science",
    }).status_code == 200

    # recommend / update / bulk-update / triage on a foreign student -> 403
    assert client.post("/recommend", headers=_hdr(tok_a),
                       json={"student_id": sid}).status_code == 403
    assert client.post("/update", headers=_hdr(tok_a),
                       json={"student_id": sid, "content_id": "NO", "reward": 0.5}).status_code == 403
    assert client.post("/bulk-update", headers=_hdr(tok_a),
                       json={"entries": [{"student_id": sid, "subject": "Math", "score": 0.5}]}).status_code == 403

    # triage is scoped to the caller's own (and unclaimed) students
    # (B's student needs a Science score, or triage would skip it regardless.)
    assert client.post("/bulk-update", headers=_hdr(tok_b), json={
        "entries": [{"student_id": sid, "subject": "Science", "score": 0.2}],
    }).status_code == 200
    triage = client.post("/triage", headers=_hdr(tok_a), json={"subject": "Science"}).json()
    all_ids = {s["student_id"] for tier in triage["tiers"].values() for s in tier["students"]}
    assert sid not in all_ids
    assert triage["total_students"] == len(all_ids)
    assert all(tier["count"] == len(tier["students"]) for tier in triage["tiers"].values())

    # ...and B does see their own student there.
    own = client.post("/triage", headers=_hdr(tok_b), json={"subject": "Science"}).json()
    assert sid in {s["student_id"] for s in own["tiers"]["remediation"]["students"]}


def test_school_and_class_crud_scoped(client):
    tok_a, sch_a = _signup(client, "epsilon")
    tok_b, sch_b = _signup(client, "zeta")

    # A cannot rename/delete B's school, and only lists its own.
    assert client.put(f"/schools/{sch_b}", headers=_hdr(tok_a),
                      json={"name": "Rename"}).status_code == 403
    assert client.delete(f"/schools/{sch_b}", headers=_hdr(tok_a)).status_code == 403
    listed = client.get("/schools", headers=_hdr(tok_a)).json()
    assert [s["school_id"] for s in listed] == [sch_a]

    # A cannot add classes to B's school.
    assert client.post(f"/classes/{sch_b}", headers=_hdr(tok_a),
                       json={"label": "A Intruder"}).status_code == 403

    # A cannot assign a student into B's class.
    b_label = f"B_{uuid.uuid4().hex[:4]}"
    b_class = client.post(f"/classes/{sch_b}", headers=_hdr(tok_b),
                          json={"label": b_label}).json()["class_id"]
    r = client.post("/students", headers=_hdr(tok_a), json={
        "student_id": f"cls_{uuid.uuid4().hex[:6]}", "name": "A Kid",
        "metadata": {"class_id": b_class},
    })
    assert r.status_code == 400


def test_ingest_cannot_target_foreign_school(client):
    tok_a, sch_a = _signup(client, "eta")
    tok_b, sch_b = _signup(client, "theta")
    csv_data = "student_id,name,performance_score\nI001,Imp,0.5\n"
    r = client.post(
        "/ingest", headers=_hdr(tok_a),
        files={"file": ("roster.csv", csv_data, "text/csv")},
        data={"type": "students", "school_id": sch_b},
    )
    assert r.status_code == 403
    # And A cannot pass a school NAME that is not theirs either.
    r = client.post(
        "/ingest", headers=_hdr(tok_a),
        files={"file": ("roster.csv", csv_data, "text/csv")},
        data={"type": "students", "school": "THETA SCHOOL"},
    )
    assert r.status_code == 403


# ── JWT claims + rate limiting ────────────────────────────────────────────

def test_token_has_standard_claims():
    token = auth.create_access_token({"sub": "user123"})
    payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM],
                         audience=auth.ISSUER, issuer=auth.ISSUER)
    for claim in ("iat", "jti", "iss", "aud", "exp"):
        assert claim in payload
    assert auth.decode_token(token)["sub"] == "user123"


def test_token_with_future_iat_rejected():
    now = int(time.time())
    payload = {
        "sub": "user123", "exp": now + 3600, "iat": now + 999999,
        "iss": auth.ISSUER, "aud": auth.ISSUER,
    }
    token = jwt.encode(payload, auth.SECRET_KEY, algorithm=auth.ALGORITHM)
    assert auth.decode_token(token) is None


@pytest.mark.parametrize("bad_secret", [None, "gradepulse-dev-secret-change-in-production", "change-this-to-a-strong-random-secret-in-production"])
def test_jwt_secret_failfast_in_production(bad_secret):
    env = dict(os.environ)
    env["GRADEPULPE_ENV"] = "production"
    if bad_secret is None:
        env.pop("JWT_SECRET", None)
    else:
        env["JWT_SECRET"] = bad_secret
    r = subprocess.run(
        [sys.executable, "-c", "import linucb_brain.api.auth"],
        capture_output=True, text=True, env=env, cwd=PROJECT_ROOT,
    )
    assert r.returncode != 0
    assert "JWT_SECRET" in r.stderr


def test_login_rate_limited_after_burst(client):
    email = f"burst_{uuid.uuid4().hex[:6]}@sec.local"
    seen = set()
    for _ in range(31):
        r = client.post("/auth/login", json={"email": email, "password": "wrong"})
        seen.add(r.status_code)
    assert 429 in seen
    assert 401 in seen  # the legitimate first attempts still returned 401


def test_dev_placeholder_secret_warns_but_boots():
    env = dict(os.environ)
    env["GRADEPULPE_ENV"] = "development"
    env["JWT_SECRET"] = "change-this-to-a-strong-random-secret-in-production"
    r = subprocess.run(
        [sys.executable, "-c", "import linucb_brain.api.auth; print('OK')"],
        capture_output=True, text=True, env=env, cwd=PROJECT_ROOT,
    )
    assert r.returncode == 0
    assert "OK" in r.stdout

# ── Signup: no joining by name, validated credentials ─────────────────────

def test_signup_with_existing_school_name_creates_a_separate_school(client):
    name = f"Shared Name {uuid.uuid4().hex[:6]}"
    owner = client.post("/auth/signup", json={
        "email": f"owner_{uuid.uuid4().hex[:6]}@sec.local", "password": "Passw0rd!", "school_name": name,
    }).json()
    sid = f"own_{uuid.uuid4().hex[:6]}"
    assert client.post("/students", headers=_hdr(owner["token"]), json={
        "student_id": sid, "name": "Owner Student",
    }).status_code == 200

    stranger = client.post("/auth/signup", json={
        "email": f"stranger_{uuid.uuid4().hex[:6]}@sec.local", "password": "Passw0rd!",
        "school_name": name.lower(),
    }).json()
    assert stranger["school_id"] != owner["school_id"]
    assert client.get("/students", headers=_hdr(stranger["token"])).json() == []


def test_default_school_is_not_shared_between_signups(client):
    ids = {
        client.post("/auth/signup", json={
            "email": f"nodefault_{uuid.uuid4().hex[:6]}@sec.local", "password": "Passw0rd!",
        }).json()["school_id"]
        for _ in range(2)
    }
    assert len(ids) == 2


@pytest.mark.parametrize("payload", [
    {"email": "short@sec.local", "password": "1234567"},
    {"email": "not-an-email", "password": "Passw0rd!"},
])
def test_signup_rejects_weak_password_and_bad_email(client, payload):
    assert client.post("/auth/signup", json=payload).status_code == 422


def test_signup_email_is_case_insensitive(client):
    local = f"case_{uuid.uuid4().hex[:6]}"
    assert client.post("/auth/signup", json={
        "email": f"{local}@sec.local", "password": "Passw0rd!",
    }).status_code == 200
    r = client.post("/auth/signup", json={"email": f"{local.upper()}@SEC.local", "password": "Passw0rd!"})
    assert r.status_code == 400


def test_summary_student_count_is_per_school(client):
    tok_a, _ = _signup(client, "eta")
    tok_b, _ = _signup(client, "theta")
    for i in range(2):
        assert client.post("/students", headers=_hdr(tok_a), json={
            "student_id": f"eta_{uuid.uuid4().hex[:6]}", "name": f"Eta {i}",
        }).status_code == 200
    assert client.get("/summary", headers=_hdr(tok_a)).json()["student_count"] == 2
    assert client.get("/summary", headers=_hdr(tok_b)).json()["student_count"] == 0


# ── Student IDs are global: a clash must never expose or move a student ────

def test_student_id_clash_across_schools_is_rejected(client):
    tok_a, sch_a = _signup(client, "iota")
    tok_b, _ = _signup(client, "kappa")
    sid = f"clash_{uuid.uuid4().hex[:6]}"
    assert client.post("/students", headers=_hdr(tok_a), json={
        "student_id": sid, "name": "A Original",
    }).status_code == 200

    r = client.post("/students", headers=_hdr(tok_b), json={"student_id": sid, "name": "B Copy"})
    assert r.status_code == 409
    assert "A Original" not in r.text

    # A roster upload from B cannot take the student over either.
    r = client.post(
        "/ingest", headers=_hdr(tok_b),
        files={"file": ("roster.csv", f"student_id,name\n{sid},B Copy\n".encode(), "text/csv")},
        data={"type": "students"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["report"]["stats"]["students_skipped"] == 1
    owned = client.get("/students", headers=_hdr(tok_a)).json()
    assert [(s["student_id"], s["name"], s["school_id"]) for s in owned] == [(sid, "A Original", sch_a)]
    assert client.get("/students", headers=_hdr(tok_b)).json() == []

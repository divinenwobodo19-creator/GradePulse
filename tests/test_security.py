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
    triage = client.post("/triage", headers=_hdr(tok_a), json={"subject": "Science"}).json()
    all_ids = {s["student_id"] for tier in triage.values()
               if isinstance(tier, dict) for s in tier.get("students", [])}
    assert sid not in all_ids


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


def test_jwt_secret_failfast_in_production():
    env = dict(os.environ)
    env["GRADEPULPE_ENV"] = "production"
    env.pop("JWT_SECRET", None)
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


def test_dev_default_secret_warns_but_boots():
    env = dict(os.environ)
    env["GRADEPULPE_ENV"] = "development"
    env["JWT_SECRET"] = auth.DEV_SECRET
    r = subprocess.run(
        [sys.executable, "-c", "import linucb_brain.api.auth; print('OK')"],
        capture_output=True, text=True, env=env, cwd=PROJECT_ROOT,
    )
    assert r.returncode == 0
    assert "OK" in r.stdout
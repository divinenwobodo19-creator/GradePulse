"""
Changing and resetting passwords. Run offline against TestClient.

There is no email service: a forgotten password is recovered with a
single-use code issued by the school's admin (for a teacher) or by the
deployment's operator (for anyone).
"""
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from linucb_brain.api import app as app_module
from linucb_brain.api import auth
from linucb_brain.api.app import app

PASSWORD = "Kettle-Mango-42"
NEW_PASSWORD = "N3wKettle-Mango-42"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    for limiter in (app_module.SIGNUP_LIMITER, app_module.LOGIN_LIMITER, app_module.LOGIN_HOST_LIMITER):
        limiter.reset()
    yield


def _hdr(token: str):
    return {"Authorization": f"Bearer {token}"}


def _signup(client, **extra):
    r = client.post("/auth/signup", json={
        "email": f"pw_{uuid.uuid4().hex[:8]}@pw.local", "password": PASSWORD, **extra,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def _admin_and_teacher(client):
    admin = _signup(client, school_name="Password School")
    code = client.post("/invites", headers=_hdr(admin["token"])).json()["code"]
    return admin, _signup(client, invite_code=code)


def _next_second():
    # Tokens carry whole-second timestamps; make "before" and "after" distinct.
    time.sleep(1.1)


def test_change_password_needs_the_current_one_and_a_valid_new_one(client):
    user = _signup(client)
    h = _hdr(user["token"])
    assert client.post("/auth/change-password", headers=h, json={
        "current_password": "wrong", "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post("/auth/change-password", headers=h, json={
        "current_password": PASSWORD, "new_password": "short"}).status_code == 422
    assert client.post("/auth/change-password", json={
        "current_password": PASSWORD, "new_password": NEW_PASSWORD}).status_code == 401
    assert _login(client, user["email"], PASSWORD).status_code == 200


def test_change_password_signs_out_older_sessions_and_keeps_this_one(client):
    user = _signup(client)
    old_token = user["token"]
    _next_second()
    r = client.post("/auth/change-password", headers=_hdr(old_token), json={
        "current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert r.status_code == 200
    new_token = r.json()["token"]

    assert client.get("/auth/me", headers=_hdr(old_token)).status_code == 401
    assert client.get("/auth/me", headers=_hdr(new_token)).status_code == 200
    assert _login(client, user["email"], PASSWORD).status_code == 401
    assert _login(client, user["email"], NEW_PASSWORD).status_code == 200


def test_admin_resets_a_teachers_password_with_a_single_use_code(client):
    admin, teacher = _admin_and_teacher(client)
    members = client.get("/members", headers=_hdr(admin["token"])).json()
    assert {(m["email"], m["role"]) for m in members} == {(admin["email"], "admin"), (teacher["email"], "teacher")}

    _next_second()
    link = client.post(f"/members/{teacher['id']}/password-reset", headers=_hdr(admin["token"]))
    assert link.status_code == 200
    code = link.json()["code"]

    assert client.post("/auth/reset-password", json={"code": code, "new_password": "short"}).status_code == 422
    assert client.post("/auth/reset-password", json={"code": code, "new_password": NEW_PASSWORD}).status_code == 200
    assert client.post("/auth/reset-password", json={"code": code, "new_password": "Another-Kettle-9"}).status_code == 400

    assert _login(client, teacher["email"], PASSWORD).status_code == 401
    assert _login(client, teacher["email"], NEW_PASSWORD).status_code == 200
    assert client.get("/auth/me", headers=_hdr(teacher["token"])).status_code == 401  # old session signed out


def test_reset_code_is_stored_hashed_and_a_new_one_replaces_the_old(client):
    admin, teacher = _admin_and_teacher(client)
    url = f"/members/{teacher['id']}/password-reset"
    first = client.post(url, headers=_hdr(admin["token"])).json()["code"]
    second = client.post(url, headers=_hdr(admin["token"])).json()["code"]

    conn = auth._get_db()
    stored = [r["code_hash"] for r in conn.execute(
        "SELECT code_hash FROM password_resets WHERE user_id = ?", (teacher["id"],))]
    conn.close()
    assert len(stored) == 1 and first not in stored and second not in stored

    assert client.post("/auth/reset-password", json={"code": first, "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post("/auth/reset-password", json={"code": second, "new_password": NEW_PASSWORD}).status_code == 200


def test_expired_or_unknown_reset_code_is_rejected(client):
    admin, teacher = _admin_and_teacher(client)
    code = client.post(f"/members/{teacher['id']}/password-reset", headers=_hdr(admin["token"])).json()["code"]
    conn = auth._get_db()
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    conn.execute("UPDATE password_resets SET expires_at = ? WHERE user_id = ?", (past, teacher["id"]))
    conn.commit()
    conn.close()
    assert client.post("/auth/reset-password", json={"code": code, "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post("/auth/reset-password", json={"code": "nope", "new_password": NEW_PASSWORD}).status_code == 400
    assert _login(client, teacher["email"], PASSWORD).status_code == 200


def test_only_an_admin_can_reset_and_only_inside_their_school(client):
    admin, teacher = _admin_and_teacher(client)
    other_admin, other_teacher = _admin_and_teacher(client)

    assert client.get("/members", headers=_hdr(teacher["token"])).status_code == 403
    assert client.post(f"/members/{admin['id']}/password-reset", headers=_hdr(teacher["token"])).status_code == 403
    assert client.post(f"/members/{other_teacher['id']}/password-reset",
                       headers=_hdr(admin["token"])).status_code == 404
    assert client.post(f"/members/{admin['id']}/password-reset", headers=_hdr(admin["token"])).status_code == 400
    assert other_teacher["email"] not in {m["email"] for m in client.get("/members", headers=_hdr(admin["token"])).json()}


def test_operator_can_issue_a_reset_for_a_locked_out_admin(client, monkeypatch):
    admin = _signup(client, school_name="Locked Out School")
    body = {"email": admin["email"].upper()}

    monkeypatch.setattr(app_module, "OPERATOR_KEY", "")
    assert client.post("/auth/operator-reset", json=body, headers={"X-Operator-Key": ""}).status_code == 403
    monkeypatch.setattr(app_module, "OPERATOR_KEY", "op-key-for-tests")
    assert client.post("/auth/operator-reset", json=body, headers=_hdr(admin["token"])).status_code == 403
    assert client.post("/auth/operator-reset", json={"email": "nobody@pw.local"},
                       headers={"X-Operator-Key": "op-key-for-tests"}).status_code == 404

    r = client.post("/auth/operator-reset", json=body, headers={"X-Operator-Key": "op-key-for-tests"})
    assert r.status_code == 200
    assert client.post("/auth/reset-password", json={
        "code": r.json()["code"], "new_password": NEW_PASSWORD}).status_code == 200
    assert _login(client, admin["email"], NEW_PASSWORD).status_code == 200

"""
Roles, invites and the operator key. Run offline against TestClient.

- Signup without an invite creates a school and makes the caller its admin.
- A teacher can only join an existing school with an admin's single-use invite.
- Destructive school/class actions and invite management are admin-only.
- Backup endpoints need the deployment's operator key, not a school account.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from linucb_brain.api import app as app_module
from linucb_brain.api import auth
from linucb_brain.api.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _fresh_signup_budget():
    # Every test here signs up from the same test host; don't let that spend
    # the per-host signup rate limit for this module or the ones after it.
    app_module.SIGNUP_LIMITER.reset()
    yield
    app_module.SIGNUP_LIMITER.reset()


def _hdr(token: str):
    return {"Authorization": f"Bearer {token}"}


def _signup(client, prefix: str, **extra):
    r = client.post("/auth/signup", json={
        "email": f"{prefix}_{uuid.uuid4().hex[:6]}@roles.local", "password": "Kettle-Mango-42", **extra,
    })
    return r


def _admin(client, prefix: str):
    r = _signup(client, prefix, school_name=f"{prefix} School")
    assert r.status_code == 200, r.text
    return r.json()


def _invite(client, admin) -> str:
    r = client.post("/invites", headers=_hdr(admin["token"]))
    assert r.status_code == 200, r.text
    return r.json()["code"]


def test_signup_without_invite_is_admin_of_a_new_school(client):
    admin = _admin(client, "lambda")
    assert admin["role"] == "admin"
    assert client.get("/auth/me", headers=_hdr(admin["token"])).json()["role"] == "admin"


def test_invite_lets_a_teacher_join_the_school(client):
    admin = _admin(client, "mu")
    sid = f"mu_{uuid.uuid4().hex[:6]}"
    class_id = client.post(f"/classes/{admin['school_id']}", headers=_hdr(admin["token"]),
                           json={"label": "JSS1A"}).json()["class_id"]
    assert client.post("/students", headers=_hdr(admin["token"]), json={
        "student_id": sid, "name": "Mu Student", "class_id": class_id,
    }).status_code == 200

    # school_name is ignored when an invite is supplied.
    teacher = _signup(client, "mu_teacher", invite_code=_invite(client, admin), school_name="Elsewhere").json()
    assert teacher["role"] == "teacher"
    assert teacher["school_id"] == admin["school_id"]
    # A new teacher sees no students until the admin assigns them a class.
    assert client.get("/students", headers=_hdr(teacher["token"])).json() == []
    client.put(f"/members/{teacher['id']}/classes", headers=_hdr(admin["token"]), json={"class_ids": [class_id]})
    assert [s["student_id"] for s in client.get("/students", headers=_hdr(teacher["token"])).json()] == [sid]

    login = client.post("/auth/login", json={"email": teacher["email"], "password": "Kettle-Mango-42"}).json()
    assert login["role"] == "teacher"


def test_invite_is_single_use(client):
    admin = _admin(client, "nu")
    code = _invite(client, admin)
    assert _signup(client, "nu_first", invite_code=code).status_code == 200
    assert _signup(client, "nu_second", invite_code=code).status_code == 400
    assert client.get("/invites", headers=_hdr(admin["token"])).json() == []


def test_bad_or_expired_invite_is_rejected_without_creating_an_account(client):
    email = f"noaccount_{uuid.uuid4().hex[:6]}@roles.local"
    r = client.post("/auth/signup", json={"email": email, "password": "Kettle-Mango-42", "invite_code": "nope"})
    assert r.status_code == 400
    assert client.post("/auth/login", json={"email": email, "password": "Kettle-Mango-42"}).status_code == 401

    admin = _admin(client, "xi")
    code = _invite(client, admin)
    conn = auth._get_db()
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    conn.execute("UPDATE invites SET expires_at = ? WHERE code_hash = ?", (past, auth._hash_code(code)))
    conn.commit()
    conn.close()
    assert _signup(client, "xi_late", invite_code=code).status_code == 400


def test_admin_can_list_and_revoke_invites(client):
    admin = _admin(client, "omicron")
    created = client.post("/invites", headers=_hdr(admin["token"])).json()
    code, invite_id = created["code"], created["id"]
    listed = client.get("/invites", headers=_hdr(admin["token"])).json()
    # The list never shows the code again: only its ID and last 4 characters.
    assert [(i["id"], i["code"], i["hint"]) for i in listed] == [(invite_id, "", code[-4:])]

    other = _admin(client, "pi")
    assert client.delete(f"/invites/{invite_id}", headers=_hdr(other["token"])).status_code == 404
    assert client.delete(f"/invites/{code}", headers=_hdr(admin["token"])).status_code == 404  # the code is not the ID
    assert client.delete(f"/invites/{invite_id}", headers=_hdr(admin["token"])).status_code == 200
    assert _signup(client, "omicron_late", invite_code=code).status_code == 400


def test_teacher_cannot_do_admin_actions(client):
    admin = _admin(client, "rho")
    school_id = admin["school_id"]
    teacher = _signup(client, "rho_teacher", invite_code=_invite(client, admin)).json()
    t = _hdr(teacher["token"])

    assert client.post(f"/classes/{school_id}", headers=t, json={"label": "JSS1A"}).status_code == 403
    class_id = client.post(f"/classes/{school_id}", headers=_hdr(admin["token"]), json={"label": "JSS1A"}).json()["class_id"]

    assert client.post("/invites", headers=t).status_code == 403
    assert client.get("/invites", headers=t).status_code == 403
    assert client.put(f"/schools/{school_id}", headers=t, json={"name": "Renamed"}).status_code == 403
    assert client.delete(f"/classes/{school_id}/{class_id}", headers=t).status_code == 403
    assert client.delete(f"/schools/{school_id}", headers=t).status_code == 403

    assert client.delete(f"/classes/{school_id}/{class_id}", headers=_hdr(admin["token"])).status_code == 200


def test_backups_need_the_operator_key_not_a_school_account(client, monkeypatch):
    admin = _admin(client, "sigma")
    calls = [("post", "/backup"), ("get", "/backups"), ("post", "/backup/restore?backup_path=/nonexistent")]

    # No key configured on the server: disabled for everyone.
    monkeypatch.setattr(app_module, "OPERATOR_KEY", "")
    for method, path in calls:
        assert getattr(client, method)(path, headers=_hdr(admin["token"])).status_code == 403
        assert getattr(client, method)(path, headers={"X-Operator-Key": ""}).status_code == 403

    monkeypatch.setattr(app_module, "OPERATOR_KEY", "op-key-for-tests")
    for method, path in calls:
        assert getattr(client, method)(path, headers=_hdr(admin["token"])).status_code == 403
        assert getattr(client, method)(path, headers={"X-Operator-Key": "wrong"}).status_code == 403
    assert client.get("/backups", headers={"X-Operator-Key": "op-key-for-tests"}).status_code in (200, 503)


# ── Removing a teacher who has left (security assessment M4) ─────────────────

def test_admin_removes_a_teacher_who_is_signed_out_at_once(client):
    admin = client.post("/auth/signup", json={
        "email": f"rm_adm_{uuid.uuid4().hex[:6]}@rm.local", "password": "Kettle-Mango-42", "school_name": "Remove School",
    }).json()
    a = {"Authorization": f"Bearer {admin['token']}"}
    code = client.post("/invites", headers=a).json()["code"]
    email = f"rm_tch_{uuid.uuid4().hex[:6]}@rm.local"
    teacher = client.post("/auth/signup", json={"email": email, "password": "Kettle-Mango-42", "invite_code": code}).json()
    t = {"Authorization": f"Bearer {teacher['token']}"}
    assert client.get("/students", headers=t).status_code == 200

    assert client.delete(f"/members/{teacher['id']}", headers=t).status_code == 403  # teachers cannot
    assert client.delete(f"/members/{admin['id']}", headers=a).status_code == 400    # admins stay
    assert client.delete(f"/members/{teacher['id']}", headers=a).json() == {"status": "removed"}

    assert client.get("/students", headers=t).status_code == 401
    assert client.post("/auth/login", json={"email": email, "password": "Kettle-Mango-42"}).status_code == 401
    assert teacher["id"] not in [m["id"] for m in client.get("/members", headers=a).json()]
    assert client.delete(f"/members/{teacher['id']}", headers=a).status_code == 404


def test_an_admin_cannot_remove_another_schools_teacher(client):
    def _school():
        adm = client.post("/auth/signup", json={
            "email": f"rx_{uuid.uuid4().hex[:6]}@rm.local", "password": "Kettle-Mango-42", "school_name": "X School",
        }).json()
        return {"Authorization": f"Bearer {adm['token']}"}
    a1, a2 = _school(), _school()
    code = client.post("/invites", headers=a1).json()["code"]
    teacher = client.post("/auth/signup", json={
        "email": f"rx_t_{uuid.uuid4().hex[:6]}@rm.local", "password": "Kettle-Mango-42", "invite_code": code}).json()
    assert client.delete(f"/members/{teacher['id']}", headers=a2).status_code == 404


def test_invite_codes_are_stored_only_as_a_hash(client):
    admin = _admin(client, "rho")
    code = _invite(client, admin)
    conn = auth._get_db()
    rows = conn.execute("SELECT code, code_hash FROM invites WHERE code_hash = ?", (auth._hash_code(code),)).fetchall()
    assert len(rows) == 1 and rows[0]["code"] != code
    assert conn.execute("SELECT COUNT(*) FROM invites WHERE code = ?", (code,)).fetchone()[0] == 0
    conn.close()


def test_a_failed_invite_signup_leaves_no_account_behind(client, monkeypatch):
    # Two people using the same invite at once: the loser must not be left with
    # an account that has no school (security assessment L10).
    admin = _admin(client, "sigma")
    code = _invite(client, admin)
    monkeypatch.setattr(app_module, "redeem_invite", lambda *_: False)
    email = f"sigma_late_{uuid.uuid4().hex[:6]}@roles.local"
    r = client.post("/auth/signup", json={"email": email, "password": "Kettle-Mango-42", "invite_code": code})
    assert r.status_code == 400
    assert auth.get_user_by_email(email) is None


def test_a_user_with_a_school_cannot_create_another(client):
    admin = _admin(client, "tau")
    r = client.post("/schools", headers=_hdr(admin["token"]), json={"name": "Second School"})
    assert r.status_code == 400

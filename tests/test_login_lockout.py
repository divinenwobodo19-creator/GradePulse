"""
Brute-force protection per account, and the rules for new passwords.

Wrong passwords for one email from one address slow that address down from
the 5th (15 s, doubling) and pause it for 15 minutes at the 10th; other
addresses can still sign in with the right password. A correct sign-in ends
the address's pause, a reset ends them all. Waiting is simulated by moving
blocked_until into the past.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from linucb_brain.api import app as app_module
from linucb_brain.api import auth
from linucb_brain.api.app import app

PASSWORD = "Kettle-Mango-42"
HOST = "testclient"  # the address TestClient requests come from


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh_limits():
    for limiter in (app_module.LOGIN_LIMITER, app_module.LOGIN_HOST_LIMITER, app_module.SIGNUP_LIMITER):
        limiter.reset()


@pytest.fixture
def account(client):
    email = f"lock_{uuid.uuid4().hex[:8]}@lock.local"
    r = client.post("/auth/signup", json={"email": email, "password": PASSWORD, "school_name": "Lock School"})
    assert r.status_code == 200, r.text
    return {"email": email, "token": r.json()["token"]}


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def _wait_over(email):
    conn = auth._get_db()
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    conn.execute("UPDATE login_failures SET blocked_until = ? WHERE email = ?", (past, f"{email.lower()}|{HOST}"))
    conn.commit()
    conn.close()


def _failures(email):
    conn = auth._get_db()
    row = conn.execute("SELECT failures FROM login_failures WHERE email = ?", (f"{email.lower()}|{HOST}",)).fetchone()
    conn.close()
    return row["failures"] if row else 0


def test_four_wrong_passwords_cost_nothing_the_fifth_starts_a_wait(client, account):
    for _ in range(5):
        assert _login(client, account["email"], "wrong-password-1").status_code == 401
    r = _login(client, account["email"], "wrong-password-1")
    assert r.status_code == 429
    assert 13 <= int(r.headers["Retry-After"]) <= 15
    assert "Too many wrong passwords" in r.json()["detail"]


def test_a_paused_address_refuses_even_the_right_password(client, account):
    for _ in range(5):
        _login(client, account["email"], "wrong-password-1")
    assert _login(client, account["email"], PASSWORD).status_code == 429
    _wait_over(account["email"])
    assert _login(client, account["email"], PASSWORD).status_code == 200
    assert _failures(account["email"]) == 0  # a correct sign-in clears the record


def test_waits_double_then_ten_failures_pause_for_fifteen_minutes(client, account):
    waits = []
    for _ in range(10):
        _wait_over(account["email"])
        assert _login(client, account["email"], "wrong-password-1").status_code == 401
        waits.append(auth.login_wait_seconds(account["email"], HOST))
    assert waits[:4] == [0, 0, 0, 0]
    assert [w // 5 * 5 for w in waits[4:9]] == [15, 30, 60, 120, 240]
    assert 14 * 60 < waits[9] <= 15 * 60
    r = _login(client, account["email"], PASSWORD)
    assert r.status_code == 429 and "15 minutes" in r.json()["detail"]


def test_unknown_emails_are_treated_the_same(client):
    email = f"nobody_{uuid.uuid4().hex[:8]}@lock.local"
    for _ in range(5):
        assert _login(client, email, "wrong-password-1").status_code == 401
    assert _login(client, email, "wrong-password-1").status_code == 429


def test_failures_are_counted_per_email_whatever_its_case(client, account):
    for _ in range(5):
        _login(client, account["email"].upper(), "wrong-password-1")
    assert _login(client, account["email"], PASSWORD).status_code == 429


def test_a_reset_code_ends_the_pause(client, account):
    for _ in range(10):
        _wait_over(account["email"])
        _login(client, account["email"], "wrong-password-1")
    user = auth.get_user_by_email(account["email"])
    code = auth.create_password_reset(user["id"], created_by="operator")["code"]
    assert client.post("/auth/reset-password", json={"code": code, "new_password": "Fresh-Kettle-88"}).status_code == 200
    assert _login(client, account["email"], "Fresh-Kettle-88").status_code == 200


def test_wrong_current_password_on_change_counts_too(client, account):
    h = {"Authorization": f"Bearer {account['token']}"}
    for _ in range(5):
        r = client.post("/auth/change-password", headers=h,
                        json={"current_password": "wrong-password-1", "new_password": "Brand-New-Kettle-5"})
        assert r.status_code == 400
    r = client.post("/auth/change-password", headers=h,
                    json={"current_password": PASSWORD, "new_password": "Brand-New-Kettle-5"})
    assert r.status_code == 429


def test_failures_from_other_addresses_do_not_lock_the_owner_out(client, account, monkeypatch):
    # An attacker rotating addresses used to pause the account for everyone.
    monkeypatch.setattr(app_module, "TRUST_FORWARDED_FOR", True)
    for i in range(15):  # 5 failures from each of 3 addresses pauses all three
        client.post("/auth/login", headers={"X-Forwarded-For": f"203.0.113.{i % 3}"},
                    json={"email": account["email"], "password": "wrong-password-1"})
    owner = client.post("/auth/login", headers={"X-Forwarded-For": "198.51.100.7"},
                        json={"email": account["email"], "password": PASSWORD})
    assert owner.status_code == 200
    # The guessing addresses stay paused.
    r = client.post("/auth/login", headers={"X-Forwarded-For": "203.0.113.0"},
                    json={"email": account["email"], "password": PASSWORD})
    assert r.status_code == 429


def test_long_passwords_work_and_do_not_reveal_accounts(client):
    long_password = "correct horse battery staple " * 4  # 116 bytes, over bcrypt's 72
    email = f"long_{uuid.uuid4().hex[:8]}@lock.local"
    r = client.post("/auth/signup", json={"email": email, "password": long_password, "school_name": "Long School"})
    assert r.status_code == 200, r.text
    assert _login(client, email, long_password).status_code == 200
    # Only the first 72 bytes used to count: a different ending must fail.
    assert _login(client, email, long_password[:-1] + "X").status_code == 401
    # A long wrong password answers 401 for known and unknown emails alike (was 500 vs 401).
    assert _login(client, email, "x" * 100).status_code == 401
    assert _login(client, f"nobody_{uuid.uuid4().hex[:8]}@lock.local", "x" * 100).status_code == 401
    assert client.post("/auth/signup", json={"email": f"huge_{uuid.uuid4().hex[:8]}@lock.local",
                                              "password": "Kettle-Mango-" * 30, "school_name": "S"}).status_code == 422


def test_short_passwords_hash_exactly_as_before():
    import bcrypt
    old_style = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    assert auth.verify_password(PASSWORD, old_style)
    assert not auth.verify_password("other-password", old_style)


# ── New passwords ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("password", [
    "Short-9ch",          # under 10 characters
    "1234567890",         # a common password
    "Password2026!",      # a common word padded with digits and symbols
    "gradepulse123",
    "aaaaabbbbb",         # too few different characters
])
def test_weak_passwords_are_refused_at_signup(client, password):
    r = client.post("/auth/signup", json={"email": f"weak_{uuid.uuid4().hex[:8]}@lock.local",
                                          "password": password, "school_name": "Weak School"})
    assert r.status_code == 422, password


def test_a_password_containing_the_email_is_refused(client):
    r = client.post("/auth/signup", json={"email": "adaeze.okafor@school.ng",
                                          "password": "adaeze.okafor-2026", "school_name": "Weak School"})
    assert r.status_code == 422
    assert "email" in r.text


def test_change_password_applies_the_same_rules(client, account):
    h = {"Authorization": f"Bearer {account['token']}"}
    for weak in ("Password2026!", "1234567890"):
        r = client.post("/auth/change-password", headers=h, json={"current_password": PASSWORD, "new_password": weak})
        assert r.status_code == 422, weak
    name = account["email"].split("@")[0]
    r = client.post("/auth/change-password", headers=h,
                    json={"current_password": PASSWORD, "new_password": f"{name}-Kettle-1"})
    assert r.status_code == 422


def test_accounts_made_under_the_old_rules_still_sign_in(client):
    # The rules apply to new passwords only; an 8-character password set before
    # them keeps working.
    email = f"old_{uuid.uuid4().hex[:8]}@lock.local"
    auth.create_user(email, "Passw0rd")
    assert _login(client, email, "Passw0rd").status_code == 200


def test_a_rejected_password_is_never_echoed_back(client):
    r = client.post("/auth/signup", json={"email": f"echo_{uuid.uuid4().hex[:8]}@lock.local",
                                          "password": "Password2026!", "school_name": "Echo School"})
    assert r.status_code == 422
    assert "Password2026!" not in r.text
    assert r.json()["detail"][0]["msg"].endswith("too easy to guess. Use a few unrelated words or a longer mix of characters.")

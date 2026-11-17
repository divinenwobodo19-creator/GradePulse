"""
The web app's session is an httpOnly cookie (security assessment L1): page
scripts cannot read it, other sites cannot use it, and sign-out removes it.
Offline, TestClient over https:// (the cookie is Secure).
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from linucb_brain.api import app as app_module
from linucb_brain.api.app import app

PASSWORD = "Kettle-Mango-42"
APP = {"X-Requested-With": "GradePulse"}


@pytest.fixture(autouse=True)
def _fresh_limits():
    for limiter in (app_module.SIGNUP_LIMITER, app_module.LOGIN_LIMITER, app_module.LOGIN_HOST_LIMITER):
        limiter.reset()
    yield


@pytest.fixture
def browser():
    """A fresh client per test: its cookie jar is one browser."""
    with TestClient(app, base_url="https://testserver") as c:
        yield c


def _signup(browser):
    email = f"ck_{uuid.uuid4().hex[:6]}@ck.local"
    r = browser.post("/auth/signup", json={"email": email, "password": PASSWORD, "school_name": "Cookie School"})
    assert r.status_code == 200
    return email, r


def test_signup_sets_an_httponly_strict_cookie(browser):
    _, r = _signup(browser)
    cookies = r.headers.get_list("set-cookie")
    session = next(c for c in cookies if c.startswith("gp_session="))
    assert "HttpOnly" in session and "Secure" in session and "samesite=strict" in session.lower()
    hint = next(c for c in cookies if c.startswith("gp_signed_in="))
    assert "HttpOnly" not in hint


def test_the_cookie_alone_signs_requests_in(browser):
    _signup(browser)
    assert browser.get("/auth/me").status_code == 200
    assert browser.get("/students").status_code == 200


def test_changes_with_the_cookie_need_the_app_header(browser):
    _signup(browser)
    body = {"student_id": "C1", "name": "Ada"}
    r = browser.post("/students", json=body)
    assert r.status_code == 403  # what a form on another site would send
    assert browser.post("/students", json=body, headers=APP).status_code == 200


def test_logout_removes_the_cookie(browser):
    _signup(browser)
    assert browser.post("/auth/logout").json() == {"status": "signed_out"}
    assert browser.get("/auth/me").status_code == 401


def test_login_sets_the_cookie_too(browser):
    email, _ = _signup(browser)
    browser.post("/auth/logout")
    assert browser.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
    assert browser.get("/auth/me").status_code == 200


def test_an_old_stored_token_moves_into_the_cookie(browser):
    _, r = _signup(browser)
    token = r.json()["token"]
    browser.cookies.clear()
    assert browser.get("/auth/me").status_code == 401
    # The web app sends the old token once; the answer sets the cookie.
    assert browser.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert browser.get("/auth/me").status_code == 200


def test_bearer_tokens_still_work_without_the_header(browser):
    _, r = _signup(browser)
    token = r.json()["token"]
    browser.cookies.clear()
    r = browser.post("/students", headers={"Authorization": f"Bearer {token}"}, json={"student_id": "B1", "name": "Bo"})
    assert r.status_code == 200

"""
Paystack billing: per student, per term, soft limits. Paystack itself is
replaced by a stand-in; the webhook signature is checked for real.
"""
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from linucb_brain.api import app as app_module
from linucb_brain.api import billing, store
from linucb_brain.api.app import app

SECRET = "sk_test_gradepulse"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def billing_settings(monkeypatch):
    app_module.SIGNUP_LIMITER.reset()
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", SECRET)
    monkeypatch.setenv("PRICE_PER_STUDENT_NAIRA", "500")
    monkeypatch.setenv("TERM_DAYS", "120")
    monkeypatch.setenv("FRONTEND_URL", "https://web.example.ng")


class FakePaystack:
    """Stands in for billing.paystack: records calls and returns canned data."""

    def __init__(self):
        self.calls = []
        self.charges = {}  # reference -> data returned by verify

    def __call__(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if path == "/transaction/initialize":
            return {"authorization_url": f"https://checkout.paystack.com/{payload['reference']}"}
        reference = path.rsplit("/", 1)[-1]
        return self.charges[reference]


@pytest.fixture
def fake(monkeypatch):
    fake = FakePaystack()
    monkeypatch.setattr(billing, "paystack", fake)
    return fake


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def school(client):
    admin = client.post("/auth/signup", json={
        "email": f"bill_{uuid.uuid4().hex[:6]}@bill.local", "password": "Passw0rd!", "school_name": "Billing School",
    }).json()
    h = _hdr(admin["token"])
    for i in range(3):
        client.post("/students", headers=h, json={"student_id": f"B{i}", "name": f"Student {i}"})
    return {"h": h, "admin": admin}


def _signed(body: dict):
    raw = json.dumps(body).encode()
    return raw, {"x-paystack-signature": hmac.new(SECRET.encode(), raw, hashlib.sha512).hexdigest(),
                 "Content-Type": "application/json"}


def test_price_is_public(client):
    assert client.get("/billing/price").json() == {
        "configured": True, "price_per_student": 500, "currency": "NGN", "term_days": 120,
    }


def test_new_school_is_unpaid_and_admin_sees_a_reminder(client, school):
    status = client.get("/billing", headers=school["h"]).json()
    assert (status["state"], status["students"], status["paid_students"]) == ("unpaid", 3, 0)
    assert client.get("/billing/reminder", headers=school["h"]).json() == {"show": True, "state": "unpaid"}


def test_checkout_charges_per_student_and_returns_the_paystack_page(client, school, fake):
    r = client.post("/billing/checkout", headers=school["h"], json={"students": 3})
    assert r.status_code == 200
    body = r.json()
    method, path, payload = fake.calls[0]
    assert (method, path) == ("POST", "/transaction/initialize")
    assert payload["amount"] == 3 * 500 * 100  # kobo
    assert payload["email"] == school["admin"]["email"]
    assert payload["callback_url"] == "https://web.example.ng/billing"
    assert body["authorization_url"].endswith(body["reference"])
    assert store.get_payment(body["reference"])["status"] == "pending"


def test_verify_after_payment_activates_the_term(client, school, fake):
    reference = client.post("/billing/checkout", headers=school["h"], json={"students": 3}).json()["reference"]
    fake.charges[reference] = {"reference": reference, "status": "success", "amount": 150000, "currency": "NGN"}
    r = client.post("/billing/verify", headers=school["h"], json={"reference": reference})
    assert r.status_code == 200
    body = r.json()
    assert (body["payment_status"], body["state"], body["paid_students"]) == ("success", "active", 3)
    paid_until = datetime.fromisoformat(body["paid_until"])
    assert timedelta(days=119) < paid_until - datetime.now(timezone.utc) <= timedelta(days=120)
    assert client.get("/billing/reminder", headers=school["h"]).json()["show"] is False

    # Verifying again does not call Paystack or extend the term.
    calls = len(fake.calls)
    assert client.post("/billing/verify", headers=school["h"], json={"reference": reference}).json()["paid_until"] == body["paid_until"]
    assert len(fake.calls) == calls


def test_amount_mismatch_is_not_accepted(client, school, fake):
    reference = client.post("/billing/checkout", headers=school["h"], json={"students": 3}).json()["reference"]
    fake.charges[reference] = {"reference": reference, "status": "success", "amount": 100, "currency": "NGN"}
    body = client.post("/billing/verify", headers=school["h"], json={"reference": reference}).json()
    assert (body["payment_status"], body["state"]) == ("amount_mismatch", "unpaid")


def test_more_students_than_paid_for_is_over_limit_but_nothing_is_blocked(client, school, fake):
    reference = client.post("/billing/checkout", headers=school["h"], json={"students": 3}).json()["reference"]
    fake.charges[reference] = {"reference": reference, "status": "success", "amount": 150000, "currency": "NGN"}
    client.post("/billing/verify", headers=school["h"], json={"reference": reference})

    assert client.post("/students", headers=school["h"], json={"student_id": "B9", "name": "Extra"}).status_code == 200
    assert client.post("/bulk-update", headers=school["h"], json={"entries": [
        {"student_id": "B9", "subject": "MATH", "score": 0.5}]}).status_code == 200
    assert client.get("/billing", headers=school["h"]).json()["state"] == "over_limit"
    assert client.get("/billing/reminder", headers=school["h"]).json() == {"show": True, "state": "over_limit"}


def test_webhook_records_a_payment_only_with_a_valid_signature(client, school, fake):
    reference = client.post("/billing/checkout", headers=school["h"], json={"students": 3}).json()["reference"]
    event = {"event": "charge.success",
             "data": {"reference": reference, "status": "success", "amount": 150000, "currency": "NGN"}}
    raw, headers = _signed(event)

    assert client.post("/billing/webhook", content=raw, headers={**headers, "x-paystack-signature": "forged"}).status_code == 401
    assert store.get_payment(reference)["status"] == "pending"

    assert client.post("/billing/webhook", content=raw, headers=headers).status_code == 200
    assert client.post("/billing/webhook", content=raw, headers=headers).status_code == 200  # Paystack retries
    assert client.get("/billing", headers=school["h"]).json()["state"] == "active"
    assert len(store.list_paid_payments(school["admin"]["school_id"])) == 1


def test_expired_term_shows_as_expired(client, school, fake):
    reference = client.post("/billing/checkout", headers=school["h"], json={"students": 3}).json()["reference"]
    fake.charges[reference] = {"reference": reference, "status": "success", "amount": 150000, "currency": "NGN"}
    client.post("/billing/verify", headers=school["h"], json={"reference": reference})
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    conn = __import__("linucb_brain.api.auth", fromlist=["_get_db"])._get_db()
    conn.execute("UPDATE payments SET period_end = ? WHERE reference = ?", (past, reference))
    conn.commit()
    conn.close()
    assert client.get("/billing", headers=school["h"]).json()["state"] == "expired"


def test_billing_is_admin_only_and_scoped_to_the_school(client, school, fake):
    code = client.post("/invites", headers=school["h"]).json()["code"]
    teacher = client.post("/auth/signup", json={
        "email": f"tbill_{uuid.uuid4().hex[:6]}@bill.local", "password": "Passw0rd!", "invite_code": code,
    }).json()
    t = _hdr(teacher["token"])
    assert client.get("/billing", headers=t).status_code == 403
    assert client.post("/billing/checkout", headers=t, json={"students": 1}).status_code == 403
    assert client.get("/billing/reminder", headers=t).json() == {"show": False}

    reference = client.post("/billing/checkout", headers=school["h"], json={"students": 3}).json()["reference"]
    other = client.post("/auth/signup", json={
        "email": f"obill_{uuid.uuid4().hex[:6]}@bill.local", "password": "Passw0rd!",
    }).json()
    assert client.post("/billing/verify", headers=_hdr(other["token"]), json={"reference": reference}).status_code == 404


def test_without_paystack_settings_billing_is_off_and_never_nags(client, school, monkeypatch):
    monkeypatch.delenv("PAYSTACK_SECRET_KEY")
    assert client.get("/billing", headers=school["h"]).json()["state"] == "not_configured"
    assert client.get("/billing/reminder", headers=school["h"]).json()["show"] is False
    assert client.post("/billing/checkout", headers=school["h"], json={"students": 1}).status_code == 503
    raw, headers = _signed({"event": "charge.success", "data": {}})
    assert client.post("/billing/webhook", content=raw, headers=headers).status_code == 401


def test_receipt_email_can_be_chosen_and_must_be_valid(client, school, fake):
    r = client.post("/billing/checkout", headers=school["h"], json={"students": 2, "email": "bursar@school.ng"})
    assert r.status_code == 200
    assert fake.calls[-1][2]["email"] == "bursar@school.ng"
    assert client.post("/billing/checkout", headers=school["h"], json={"students": 2, "email": "nope"}).status_code == 422


def test_paystack_refusal_reason_reaches_the_admin(client, school, monkeypatch):
    class Refusal:
        status_code = 400

        def json(self):
            return {"status": False, "message": '"email" must be a valid email'}

    monkeypatch.setattr(billing.httpx, "request", lambda *a, **k: Refusal())
    r = client.post("/billing/checkout", headers=school["h"], json={"students": 2})
    assert r.status_code == 502
    assert '"email" must be a valid email' in r.json()["detail"]

    class BadKey(Refusal):
        status_code = 401

        def json(self):
            return {"status": False, "message": "Invalid key"}

    monkeypatch.setattr(billing.httpx, "request", lambda *a, **k: BadKey())
    r = client.post("/billing/checkout", headers=school["h"], json={"students": 2})
    assert "Invalid key" not in r.json()["detail"]  # key problems are for the operator's log, not the school

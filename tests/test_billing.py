"""
Paystack billing: per student, per term, with a free plan. Paystack itself is
replaced by a stand-in; the webhook signature is checked for real.

The free plan is set to 5 students here (40 on a real server) so the tests
stay small.
"""
import hashlib
import hmac
import io
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from linucb_brain.api import app as app_module
from linucb_brain.api import auth, billing, store
from linucb_brain.api.app import app

SECRET = "sk_test_gradepulse"
FREE = 5


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
    monkeypatch.setenv("FREE_STUDENTS", str(FREE))
    monkeypatch.setenv("GRACE_DAYS", "14")
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


def _add(client, h, student_id):
    return client.post("/students", headers=h, json={"student_id": student_id, "name": f"Student {student_id}"})


@pytest.fixture
def school(client):
    admin = client.post("/auth/signup", json={
        "email": f"bill_{uuid.uuid4().hex[:6]}@bill.local", "password": "Kettle-Mango-42", "school_name": "Billing School",
    }).json()
    h = _hdr(admin["token"])
    for i in range(3):
        _add(client, h, f"B{i}")
    return {"h": h, "admin": admin}


@pytest.fixture
def teacher(client, school):
    """A teacher with one class, holding student B0."""
    school_id = school["admin"]["school_id"]
    class_id = client.post(f"/classes/{school_id}", headers=school["h"], json={"label": "JSS1A"}).json()["class_id"]
    client.put("/students/B0", headers=school["h"], json={"class_id": class_id})
    code = client.post("/invites", headers=school["h"], json={"class_ids": [class_id]}).json()["code"]
    t = client.post("/auth/signup", json={
        "email": f"tbill_{uuid.uuid4().hex[:6]}@bill.local", "password": "Kettle-Mango-42", "invite_code": code,
    }).json()
    return {"h": _hdr(t["token"]), "class_id": class_id}


def _signed(body: dict):
    raw = json.dumps(body).encode()
    return raw, {"x-paystack-signature": hmac.new(SECRET.encode(), raw, hashlib.sha512).hexdigest(),
                 "Content-Type": "application/json"}


def _pay(client, school, fake, students):
    reference = client.post("/billing/checkout", headers=school["h"], json={"students": students}).json()["reference"]
    fake.charges[reference] = {"reference": reference, "status": "success",
                               "amount": students * 500 * 100, "currency": "NGN"}
    return client.post("/billing/verify", headers=school["h"], json={"reference": reference}).json()


def _end_terms(school, days_ago):
    """Move every payment of the school so its term ended `days_ago` days ago."""
    end = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    conn = auth._get_db()
    conn.execute("UPDATE payments SET period_end = ? WHERE school_id = ?", (end, school["admin"]["school_id"]))
    conn.commit()
    conn.close()


def _score(client, h, student_id="B0"):
    return client.post("/bulk-update", headers=h, json={"entries": [
        {"student_id": student_id, "subject": "MATH", "score": 0.5}]})


# ── Price and status ─────────────────────────────────────────────────────────

def test_price_is_public(client):
    assert client.get("/billing/price").json() == {
        "configured": True, "price_per_student": 500, "currency": "NGN", "term_days": 120, "free_students": FREE,
    }


def test_free_plan_is_40_students_by_default(client, monkeypatch):
    monkeypatch.delenv("FREE_STUDENTS")
    assert client.get("/billing/price").json()["free_students"] == 40


def test_new_school_is_on_the_free_plan_without_a_reminder(client, school):
    status = client.get("/billing", headers=school["h"]).json()
    assert (status["state"], status["students"], status["student_limit"], status["reports"]) == ("unpaid", 3, FREE, False)
    assert client.get("/billing/reminder", headers=school["h"]).json()["show"] is False


# ── The free plan ────────────────────────────────────────────────────────────

def test_free_plan_stops_at_the_student_limit(client, school, teacher):
    for i in range(3, FREE):
        assert _add(client, school["h"], f"B{i}").status_code == 200
    assert client.get("/billing/reminder", headers=school["h"]).json()["show"] is True  # at the limit

    r = _add(client, school["h"], "B99")
    assert r.status_code == 402
    assert f"free plan covers up to {FREE} students" in r.json()["detail"]
    assert "Billing page" in r.json()["detail"]
    # Re-adding an existing ID creates nothing, so it is not refused.
    assert _add(client, school["h"], "B0").status_code == 200

    r = client.post("/students", headers=teacher["h"], json={
        "student_id": "B98", "name": "Student B98", "metadata": {"class_id": teacher["class_id"]}})
    assert r.status_code == 402 and "Ask your school admin" in r.json()["detail"]


def test_free_plan_keeps_scores_triage_and_progress_but_not_reports(client, school, teacher):
    assert _score(client, school["h"]).status_code == 200
    assert client.post("/triage", headers=school["h"], json={"subject": "MATH"}).status_code == 200
    assert client.get("/students/B0/scores", headers=school["h"]).status_code == 200

    r = client.get("/scores", headers=school["h"])
    assert r.status_code == 402 and "reports" in r.json()["detail"]
    r = client.get("/scores", headers=teacher["h"])
    assert r.status_code == 402 and "Ask your school admin" in r.json()["detail"]


def test_class_list_import_respects_the_free_plan_even_in_preview(client, school):
    rows = "student_id,name\n" + "".join(f"N{i},New {i}\n" for i in range(FREE))
    for dry_run in ("true", "false"):
        r = client.post("/ingest", headers=school["h"], data={"type": "students", "dry_run": dry_run},
                        files={"file": ("roster.csv", io.BytesIO(rows.encode()), "text/csv")})
        assert r.status_code == 402, r.text
    assert client.get("/billing", headers=school["h"]).json()["students"] == 3

    small = "student_id,name\nN1,New 1\nB0,Student B0\n"  # one new, one already there
    r = client.post("/ingest", headers=school["h"], data={"type": "students"},
                    files={"file": ("roster.csv", io.BytesIO(small.encode()), "text/csv")})
    assert r.status_code == 200, r.text


# ── Paying ───────────────────────────────────────────────────────────────────

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


def test_a_new_term_must_cover_the_whole_school(client, school, fake):
    r = client.post("/billing/checkout", headers=school["h"], json={"students": 2})
    assert r.status_code == 422 and "at least 3 students" in r.json()["detail"]


def test_verify_after_payment_activates_the_term_and_the_reports(client, school, fake):
    body = _pay(client, school, fake, 3)
    assert (body["payment_status"], body["state"], body["paid_students"], body["reports"]) == ("success", "active", 3, True)
    paid_until = datetime.fromisoformat(body["paid_until"])
    assert timedelta(days=119) < paid_until - datetime.now(timezone.utc) <= timedelta(days=120)
    assert client.get("/billing/reminder", headers=school["h"]).json()["show"] is False
    assert client.get("/scores", headers=school["h"]).status_code == 200

    # Verifying again does not call Paystack or extend the term.
    reference = body["payments"][0]["reference"]
    calls = len(fake.calls)
    assert client.post("/billing/verify", headers=school["h"], json={"reference": reference}).json()["paid_until"] == body["paid_until"]
    assert len(fake.calls) == calls


def test_a_paid_term_covers_the_students_paid_for(client, school, fake):
    _pay(client, school, fake, FREE + 2)
    for i in range(3, FREE + 2):
        assert _add(client, school["h"], f"B{i}").status_code == 200
    r = _add(client, school["h"], "B99")
    assert r.status_code == 402 and f"paid for {FREE + 2} students" in r.json()["detail"]


def test_a_small_payment_never_covers_less_than_the_free_plan(client, school, fake):
    _pay(client, school, fake, 3)
    for i in range(3, FREE):
        assert _add(client, school["h"], f"B{i}").status_code == 200


def test_a_top_up_adds_students_and_ends_with_the_term(client, school, fake):
    first = _pay(client, school, fake, FREE)
    for i in range(3, FREE):
        _add(client, school["h"], f"B{i}")
    assert _add(client, school["h"], "B99").status_code == 402

    top_up = _pay(client, school, fake, 2)  # smaller than the school: fine during a term
    assert (top_up["state"], top_up["paid_students"], top_up["top_up"]) == ("active", FREE + 2, True)
    assert top_up["paid_until"] == first["paid_until"]
    assert _add(client, school["h"], "B99").status_code == 200


def test_more_students_than_paid_for_is_over_limit_and_blocks_only_new_students(client, school, fake):
    _pay(client, school, fake, 3)
    # Students added before the plan existed, straight into the store.
    for i in range(3, FREE + 1):
        store.add_student(school["admin"]["school_id"], f"L{i}", "Legacy")
    status = client.get("/billing", headers=school["h"]).json()
    assert status["state"] == "over_limit"
    assert client.get("/billing/reminder", headers=school["h"]).json()["show"] is True
    assert _score(client, school["h"]).status_code == 200
    assert client.get("/scores", headers=school["h"]).status_code == 200
    assert _add(client, school["h"], "B99").status_code == 402


# ── When a term ends ─────────────────────────────────────────────────────────

def test_ended_term_has_a_grace_period(client, school, fake):
    _pay(client, school, fake, FREE + 2)
    for i in range(3, FREE + 2):
        _add(client, school["h"], f"B{i}")
    _end_terms(school, days_ago=3)

    status = client.get("/billing", headers=school["h"]).json()
    assert (status["state"], status["reports"], status["paid_students"]) == ("grace", True, FREE + 2)
    grace_until = datetime.fromisoformat(status["grace_until"])
    assert timedelta(days=10) < grace_until - datetime.now(timezone.utc) <= timedelta(days=11)
    assert client.get("/billing/reminder", headers=school["h"]).json()["show"] is True
    assert client.get("/scores", headers=school["h"]).status_code == 200
    assert _score(client, school["h"]).status_code == 200

    # Renewing in the grace period starts a new term for the whole school.
    assert client.post("/billing/checkout", headers=school["h"], json={"students": 2}).status_code == 422
    assert _pay(client, school, fake, FREE + 2)["state"] == "active"


def test_after_the_grace_period_the_school_falls_back_to_the_free_plan(client, school, fake):
    _pay(client, school, fake, FREE + 2)
    for i in range(3, FREE + 2):
        _add(client, school["h"], f"B{i}")
    _end_terms(school, days_ago=20)

    status = client.get("/billing", headers=school["h"]).json()
    assert (status["state"], status["student_limit"], status["reports"]) == ("expired", FREE, False)
    assert client.get("/scores", headers=school["h"]).status_code == 402
    r = _score(client, school["h"])
    assert r.status_code == 402 and "stays visible" in r.json()["detail"]
    # The data itself is never locked away.
    assert len(client.get("/students", headers=school["h"]).json()) == FREE + 2
    assert client.get("/students/B0/scores", headers=school["h"]).status_code == 200
    assert client.post("/triage", headers=school["h"], json={"subject": "MATH"}).status_code == 200


# ── Webhook, access and settings ─────────────────────────────────────────────

def test_amount_mismatch_is_not_accepted(client, school, fake):
    reference = client.post("/billing/checkout", headers=school["h"], json={"students": 3}).json()["reference"]
    fake.charges[reference] = {"reference": reference, "status": "success", "amount": 100, "currency": "NGN"}
    body = client.post("/billing/verify", headers=school["h"], json={"reference": reference}).json()
    assert (body["payment_status"], body["state"]) == ("amount_mismatch", "unpaid")


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


def test_billing_is_admin_only_and_scoped_to_the_school(client, school, teacher, fake):
    assert client.get("/billing", headers=teacher["h"]).status_code == 403
    assert client.post("/billing/checkout", headers=teacher["h"], json={"students": 1}).status_code == 403
    assert client.get("/billing/reminder", headers=teacher["h"]).json() == {"show": False}

    reference = client.post("/billing/checkout", headers=school["h"], json={"students": 3}).json()["reference"]
    other = client.post("/auth/signup", json={
        "email": f"obill_{uuid.uuid4().hex[:6]}@bill.local", "password": "Kettle-Mango-42",
    }).json()
    assert client.post("/billing/verify", headers=_hdr(other["token"]), json={"reference": reference}).status_code == 404


def test_without_paystack_settings_billing_is_off_and_nothing_is_limited(client, school, monkeypatch):
    monkeypatch.delenv("PAYSTACK_SECRET_KEY")
    assert client.get("/billing", headers=school["h"]).json()["state"] == "not_configured"
    assert client.get("/billing/reminder", headers=school["h"]).json()["show"] is False
    assert client.post("/billing/checkout", headers=school["h"], json={"students": 1}).status_code == 503
    for i in range(3, FREE + 3):
        assert _add(client, school["h"], f"B{i}").status_code == 200
    assert client.get("/scores", headers=school["h"]).status_code == 200
    raw, headers = _signed({"event": "charge.success", "data": {}})
    assert client.post("/billing/webhook", content=raw, headers=headers).status_code == 401


def test_receipt_email_can_be_chosen_and_must_be_valid(client, school, fake):
    r = client.post("/billing/checkout", headers=school["h"], json={"students": 3, "email": "bursar@school.ng"})
    assert r.status_code == 200
    assert fake.calls[-1][2]["email"] == "bursar@school.ng"
    assert client.post("/billing/checkout", headers=school["h"], json={"students": 3, "email": "nope"}).status_code == 422


def test_paystack_refusal_reason_reaches_the_admin(client, school, monkeypatch):
    class Refusal:
        status_code = 400

        def json(self):
            return {"status": False, "message": '"email" must be a valid email'}

    monkeypatch.setattr(billing.httpx, "request", lambda *a, **k: Refusal())
    r = client.post("/billing/checkout", headers=school["h"], json={"students": 3})
    assert r.status_code == 502
    assert '"email" must be a valid email' in r.json()["detail"]

    class BadKey(Refusal):
        status_code = 401

        def json(self):
            return {"status": False, "message": "Invalid key"}

    monkeypatch.setattr(billing.httpx, "request", lambda *a, **k: BadKey())
    r = client.post("/billing/checkout", headers=school["h"], json={"students": 3})
    assert "Invalid key" not in r.json()["detail"]  # key problems are for the operator's log, not the school


def test_checking_before_paying_does_not_cancel_the_payment(client, school, fake):
    reference = client.post("/billing/checkout", headers=school["h"], json={"students": 3}).json()["reference"]
    fake.charges[reference] = {"reference": reference, "status": "abandoned", "amount": 150000, "currency": "NGN"}
    body = client.post("/billing/verify", headers=school["h"], json={"reference": reference}).json()
    assert (body["payment_status"], body["state"]) == ("pending", "unpaid")

    # The admin finishes paying afterwards; Paystack's webhook still counts.
    raw, headers = _signed({"event": "charge.success",
                            "data": {"reference": reference, "status": "success", "amount": 150000, "currency": "NGN"}})
    client.post("/billing/webhook", content=raw, headers=headers)
    assert client.get("/billing", headers=school["h"]).json()["state"] == "active"


def test_failed_charge_is_final(client, school, fake):
    reference = client.post("/billing/checkout", headers=school["h"], json={"students": 3}).json()["reference"]
    fake.charges[reference] = {"reference": reference, "status": "failed", "amount": 150000, "currency": "NGN"}
    assert client.post("/billing/verify", headers=school["h"], json={"reference": reference}).json()["payment_status"] == "failed"

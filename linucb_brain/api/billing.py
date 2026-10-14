"""
Billing through Paystack: a school pays per student, for one term at a time.

Flow: the school admin starts a checkout for N students; we record a pending
payment and ask Paystack for a payment page; the admin pays there (card,
bank transfer, USSD) and comes back to /billing, where the web app asks us to
verify the reference. Paystack also calls POST /billing/webhook, signed with
the secret key, so a payment is recorded even if the admin closes the tab.

Limits are soft: an unpaid, expired or over-the-limit school keeps full use
of GradePulse; the admin just sees a reminder.

Settings (environment):
  PAYSTACK_SECRET_KEY       sk_test_... or sk_live_...; billing is off without it
  PRICE_PER_STUDENT_NAIRA   price per student per term, whole naira
  TERM_DAYS                 how long one payment covers (default 120)
"""
import hashlib
import hmac
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import store
from .auth import get_current_user, require_admin

logger = logging.getLogger("gradepulse.billing")

router = APIRouter(prefix="/billing", tags=["billing"])

PAYSTACK_BASE_URL = os.getenv("PAYSTACK_BASE_URL", "https://api.paystack.co")
CURRENCY = "NGN"
MAX_STUDENTS = 100_000
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ── Settings (read on each call so a restart is not needed in tests) ─────────

def _secret_key() -> str:
    return os.getenv("PAYSTACK_SECRET_KEY", "").strip()


def _price_naira() -> Optional[int]:
    try:
        price = int(os.getenv("PRICE_PER_STUDENT_NAIRA", "").strip())
    except ValueError:
        return None
    return price if price > 0 else None


def _term_days() -> int:
    try:
        return max(1, int(os.getenv("TERM_DAYS", "120")))
    except ValueError:
        return 120


def _configured() -> bool:
    return bool(_secret_key()) and _price_naira() is not None


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Paystack ─────────────────────────────────────────────────────────────────

def paystack(method: str, path: str, payload: Optional[dict] = None) -> dict:
    """Call the Paystack API and return its `data`. Tests replace this."""
    try:
        response = httpx.request(
            method, PAYSTACK_BASE_URL + path, json=payload, timeout=20,
            headers={"Authorization": f"Bearer {_secret_key()}"},
        )
        body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Paystack %s %s failed: %s", method, path, exc)
        raise HTTPException(status_code=502, detail="Could not reach Paystack. Try again in a moment.")
    if response.status_code >= 400 or not body.get("status"):
        message = str(body.get("message") or "").strip()
        logger.error("Paystack %s %s refused: %s %s", method, path, response.status_code, message)
        if 400 <= response.status_code < 500 and response.status_code not in (401, 403) and message:
            # Paystack's own explanation (e.g. a bad receipt email) helps the admin fix it.
            raise HTTPException(status_code=502, detail=f"Paystack did not accept the payment: {message}")
        raise HTTPException(status_code=502, detail="Paystack did not accept the request. Try again in a moment.")
    return body.get("data") or {}


def _apply_charge(data: dict) -> None:
    """Record a charge Paystack reports, after checking it against our records."""
    reference = str(data.get("reference", ""))
    payment = store.get_payment(reference)
    if payment is None:
        logger.warning("Paystack reported unknown reference %s", reference)
        return
    if data.get("status") != "success":
        # "abandoned" only means the payer has not finished yet, so the
        # payment stays pending and can still succeed later.
        if data.get("status") in ("failed", "reversed"):
            store.fail_payment(reference, str(data["status"]))
        return
    if int(data.get("amount", -1)) != payment["amount_kobo"] or data.get("currency", CURRENCY) != payment["currency"]:
        logger.error("Paystack amount for %s does not match: got %s %s, expected %s %s",
                     reference, data.get("amount"), data.get("currency"), payment["amount_kobo"], payment["currency"])
        store.fail_payment(reference, "amount_mismatch")
        return
    now = _now()
    if store.complete_payment(reference, now.isoformat(), now.isoformat(),
                              (now + timedelta(days=_term_days())).isoformat()):
        logger.info("Payment %s recorded for school %s (%s students)", reference, payment["school_id"], payment["students"])


# ── Status ───────────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    students: int = Field(..., ge=1, le=MAX_STUDENTS)
    # Where Paystack sends the receipt, e.g. the school bursar; the admin's own by default.
    email: Optional[str] = Field(None, max_length=200)


class VerifyRequest(BaseModel):
    reference: str = Field(..., min_length=1, max_length=100)


def billing_status(school_id: str) -> dict:
    """Where a school stands. state is one of: not_configured, unpaid, active,
    over_limit (paid, but now has more students than it paid for), expired."""
    students = store.count_students(school_id)
    payments = store.list_paid_payments(school_id)
    now = _now()
    current = next((p for p in payments if p["period_end"] and datetime.fromisoformat(p["period_end"]) > now), None)
    if not _configured():
        state = "not_configured"
    elif current is None:
        state = "expired" if payments else "unpaid"
    elif students > current["students"]:
        state = "over_limit"
    else:
        state = "active"
    return {
        "state": state,
        "configured": _configured(),
        "price_per_student": _price_naira(),
        "currency": CURRENCY,
        "term_days": _term_days(),
        "students": students,
        "paid_students": current["students"] if current else 0,
        "paid_until": current["period_end"] if current else None,
        "payments": [
            {"reference": p["reference"], "students": p["students"], "amount_naira": p["amount_kobo"] // 100,
             "paid_at": p["paid_at"], "period_end": p["period_end"]}
            for p in payments[:20]
        ],
    }


def _admin_school_id(user: dict) -> str:
    school_id = user.get("school_id", "")
    if not school_id:
        raise HTTPException(status_code=403, detail="User has no school")
    return school_id


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/price")
def price():
    """Public: what GradePulse costs, for the pricing page."""
    return {"configured": _configured(), "price_per_student": _price_naira(),
            "currency": CURRENCY, "term_days": _term_days()}


@router.get("")
def status(user: dict = Depends(require_admin)):
    return billing_status(_admin_school_id(user))


@router.get("/reminder")
def reminder(user: dict = Depends(get_current_user)):
    """The small notice the web app shows an admin when payment is due.
    Teachers never see one."""
    if user.get("role") != "admin" or not user.get("school_id"):
        return {"show": False}
    state = billing_status(user["school_id"])["state"]
    return {"show": state in ("unpaid", "expired", "over_limit"), "state": state}


@router.post("/checkout")
def checkout(request: CheckoutRequest, user: dict = Depends(require_admin)):
    school_id = _admin_school_id(user)
    if not _configured():
        raise HTTPException(status_code=503, detail="Online payment is not set up on this server yet")
    email = (request.email or user["email"]).strip()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address for the receipt")
    amount_kobo = request.students * _price_naira() * 100
    reference = f"gp_{uuid.uuid4().hex[:20]}"
    store.create_payment(reference, school_id, request.students, amount_kobo, user["id"])
    frontend = os.getenv("FRONTEND_URL", "http://localhost:3000").split(",")[0].strip().rstrip("/")
    data = paystack("POST", "/transaction/initialize", {
        "email": email,
        "amount": amount_kobo,
        "currency": CURRENCY,
        "reference": reference,
        "callback_url": f"{frontend}/billing",
        "metadata": {"school_id": school_id, "students": request.students},
    })
    return {"authorization_url": data.get("authorization_url"), "reference": reference}


@router.post("/verify")
def verify(request: VerifyRequest, user: dict = Depends(require_admin)):
    """Called when the admin comes back from Paystack's payment page."""
    school_id = _admin_school_id(user)
    payment = store.get_payment(request.reference)
    if payment is None or payment["school_id"] != school_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment["status"] == "pending":
        _apply_charge(paystack("GET", f"/transaction/verify/{request.reference}"))
    return {"payment_status": store.get_payment(request.reference)["status"], **billing_status(school_id)}


@router.post("/webhook")
async def webhook(request: Request):
    """Paystack's server-to-server notice. Trusted only with a valid signature."""
    secret = _secret_key()
    raw = await request.body()
    signature = request.headers.get("x-paystack-signature", "")
    expected = hmac.new(secret.encode(), raw, hashlib.sha512).hexdigest() if secret else ""
    if not secret or not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")
    try:
        event = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid body")
    if event.get("event") == "charge.success":
        _apply_charge(event.get("data") or {})
    return {"status": "ok"}

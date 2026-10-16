"""
Billing through Paystack: a school pays per student, for one term at a time.

Flow: the school admin starts a checkout for N students; we record a pending
payment and ask Paystack for a payment page; the admin pays there (card,
bank transfer, USSD) and comes back to /billing, where the web app asks us to
verify the reference. Paystack also calls POST /billing/webhook, signed with
the secret key, so a payment is recorded even if the admin closes the tab.

Plans: a school that has not paid is on the free plan, which covers up to
FREE_STUDENTS students and everything except the printable reports. A paid
term covers the students paid for (never fewer than the free plan), reports
included. Paying for more students during a term is a top-up: it adds to the
term and ends with it. When a term ends the school keeps its paid plan for
GRACE_DAYS more, then falls back to the free plan. A school's data always
stays visible: the free plan only holds back adding students past the limit,
entering scores while over it, and the reports. With billing not configured
(no Paystack key or price) nothing is limited.

Settings (environment):
  PAYSTACK_SECRET_KEY       sk_test_... or sk_live_...; billing is off without it
  PRICE_PER_STUDENT_NAIRA   price per student per term, whole naira
  TERM_DAYS                 how long one payment covers (default 120)
  FREE_STUDENTS             students the free plan covers (default 40)
  GRACE_DAYS                days a paid plan lasts after its term ends (default 14)
"""
import hashlib
import hmac
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

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


def _int_setting(name: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _term_days() -> int:
    return _int_setting("TERM_DAYS", 120, 1)


def _free_students() -> int:
    return _int_setting("FREE_STUDENTS", 40, 0)


def _grace_days() -> int:
    return _int_setting("GRACE_DAYS", 14, 0)


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
    # A payment made during a paid term is a top-up and ends with that term.
    _, term_end = _current_term(store.list_paid_payments(payment["school_id"]), now)
    period_end = term_end or now + timedelta(days=_term_days())
    if store.complete_payment(reference, now.isoformat(), now.isoformat(), period_end.isoformat()):
        logger.info("Payment %s recorded for school %s (%s students)", reference, payment["school_id"], payment["students"])


# ── Plans ────────────────────────────────────────────────────────────────────

def _end(payment: dict) -> Optional[datetime]:
    return datetime.fromisoformat(payment["period_end"]) if payment.get("period_end") else None


def _current_term(payments: List[dict], now: datetime) -> Tuple[int, Optional[datetime]]:
    """Students paid for in the term running now (top-ups included) and when it ends."""
    running = [p for p in payments if _end(p) and _end(p) > now]
    if not running:
        return 0, None
    return sum(p["students"] for p in running), max(_end(p) for p in running)


def _last_term(payments: List[dict]) -> Tuple[int, Optional[datetime]]:
    """The most recent term that has ended: its students and end."""
    ends = [_end(p) for p in payments if _end(p)]
    if not ends:
        return 0, None
    last = max(ends)
    return sum(p["students"] for p in payments if _end(p) == last), last


def school_plan(school_id: str) -> dict:
    """What a school may do now. state is one of:
      not_configured  billing is off on this server: nothing is limited
      unpaid          never paid: free plan
      active          in a paid term
      over_limit      in a paid term, with more students than paid for
      grace           the paid term ended less than GRACE_DAYS ago
      expired         the grace period is over too: free plan
    """
    students = store.count_students(school_id)
    free = _free_students()
    plan = {"students": students, "free_students": free, "paid_students": 0,
            "paid_until": None, "grace_until": None}
    if not _configured():
        return {**plan, "state": "not_configured", "student_limit": None, "reports": True}
    payments = store.list_paid_payments(school_id)
    now = _now()
    paid, term_end = _current_term(payments, now)
    if term_end is not None:
        state = "over_limit" if students > paid else "active"
        return {**plan, "state": state, "paid_students": paid, "paid_until": term_end.isoformat(),
                "student_limit": max(paid, free), "reports": True}
    paid, last_end = _last_term(payments)
    if last_end is not None and now < last_end + timedelta(days=_grace_days()):
        return {**plan, "state": "grace", "paid_students": paid, "paid_until": last_end.isoformat(),
                "grace_until": (last_end + timedelta(days=_grace_days())).isoformat(),
                "student_limit": max(paid, free), "reports": True}
    return {**plan, "state": "expired" if payments else "unpaid", "student_limit": free, "reports": False}


def _payment_required(user: dict, reason: str, admin_action: str = "Pay for the term on the Billing page.") -> HTTPException:
    """402 with what to do next, worded for whoever is asking."""
    action = admin_action if user.get("role") == "admin" else "Ask your school admin to pay for the term."
    return HTTPException(status_code=402, detail=f"{reason} {action}")


def check_can_add_students(user: dict, new_students: int) -> None:
    """Refuse adding students past what the school's plan covers."""
    if new_students <= 0:
        return
    plan = school_plan(user.get("school_id", ""))
    limit = plan["student_limit"]
    total = plan["students"] + new_students
    if limit is None or total <= limit:
        return
    if plan["state"] in ("active", "over_limit"):
        raise _payment_required(user, f"This term is paid for {limit} students, and this would make {total}.",
                                "Pay for the extra students on the Billing page.")
    if plan["state"] == "grace":
        raise _payment_required(user, f"The last term was paid for {limit} students, and this would make {total}.",
                                "Pay for the new term on the Billing page.")
    raise _payment_required(user, f"The free plan covers up to {limit} students, and this would make {total}.")


def check_can_enter_scores(user: dict) -> None:
    """On the free plan, scores can be entered while the school is within it."""
    plan = school_plan(user.get("school_id", ""))
    if plan["state"] in ("unpaid", "expired") and plan["students"] > plan["student_limit"]:
        raise _payment_required(
            user, f"Your school has {plan['students']} students and the free plan covers {plan['student_limit']}, "
                  "so new scores need a paid term. Everything already entered stays visible.")


def check_reports(user: dict) -> None:
    """Printable class reports and parent progress sheets come with a paid term."""
    if not school_plan(user.get("school_id", ""))["reports"]:
        raise _payment_required(user, "Printable class reports and parent progress sheets come with a paid term.")


# ── Status ───────────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    students: int = Field(..., ge=1, le=MAX_STUDENTS)
    # Where Paystack sends the receipt, e.g. the school bursar; the admin's own by default.
    email: Optional[str] = Field(None, max_length=200)


class VerifyRequest(BaseModel):
    reference: str = Field(..., min_length=1, max_length=100)


def billing_status(school_id: str) -> dict:
    """The school's plan plus what the Billing page needs to take a payment."""
    plan = school_plan(school_id)
    payments = store.list_paid_payments(school_id) if _configured() else []
    return {
        **plan,
        "configured": _configured(),
        "price_per_student": _price_naira(),
        "currency": CURRENCY,
        "term_days": _term_days(),
        # A payment now adds students to the running term instead of starting one.
        "top_up": plan["state"] in ("active", "over_limit"),
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
            "currency": CURRENCY, "term_days": _term_days(), "free_students": _free_students()}


@router.get("")
def status(user: dict = Depends(require_admin)):
    return billing_status(_admin_school_id(user))


@router.get("/reminder")
def reminder(user: dict = Depends(get_current_user)):
    """The small notice the web app shows an admin when payment is due: a
    term that has ended or is about to fall back, more students than paid
    for, or a free school at its limit. Teachers never see one."""
    if user.get("role") != "admin" or not user.get("school_id"):
        return {"show": False}
    plan = school_plan(user["school_id"])
    state = plan["state"]
    at_free_limit = state == "unpaid" and plan["students"] >= plan["student_limit"]
    return {"show": state in ("grace", "expired", "over_limit") or at_free_limit, "state": state,
            "grace_until": plan["grace_until"]}


@router.post("/checkout")
def checkout(request: CheckoutRequest, user: dict = Depends(require_admin)):
    school_id = _admin_school_id(user)
    if not _configured():
        raise HTTPException(status_code=503, detail="Online payment is not set up on this server yet")
    email = (request.email or user["email"]).strip()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address for the receipt")
    plan = school_plan(school_id)
    if plan["state"] not in ("active", "over_limit") and request.students < plan["students"]:
        # A new term covers the whole school; top-ups during a term can be any size.
        raise HTTPException(status_code=422, detail=f"Pay for at least {plan['students']} students: "
                                                    f"that is how many the school has.")
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

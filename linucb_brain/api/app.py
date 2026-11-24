"""
GradePulse API — FastAPI backend with JWT auth, multi-tenant CRUD, and brain operations.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Query, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from typing import List, Dict, Optional
from datetime import date
import hmac
import json
import logging
import os
import glob
import sqlite3
import uuid
import tempfile
import threading
import csv
import io
import zipfile
import numpy as np

from .. import __version__
from ..brain import Brain
from ..core.triage import build_weekly_triage
from ..models.student import Student
from ..core.reward import calculate_reward
from ..sync import BrainSynchronizer
from ..backup import BackupManager
from ..registry import load_registry
from .auth import (
    create_user, authenticate_user, create_access_token,
    get_current_user, optional_user, update_user_school, get_user_by_id,
    require_admin, create_invite, list_pending_invites, revoke_invite,
    get_usable_invite, redeem_invite, ROLE_ADMIN, ROLE_TEACHER,
    verify_password, set_password, get_user_by_email, list_school_members,
    create_password_reset, redeem_password_reset, remove_member,
    login_wait_seconds, record_login_failure, clear_login_failures,
    ENV as AUTH_ENV, set_session_cookie, clear_session_cookie, security as bearer_scheme,
)
from fastapi.security import HTTPAuthorizationCredentials
from .ratelimit import SlidingWindowLimiter
from . import store
from .billing import router as billing_router
from . import billing
from .schemas import password_mentions_email
from .schemas import (
    StudentSchema, ContentSchema, RecommendationRequest, UpdateRequest,
    RewardRequest, NeuralScoreResponse, BrainSummary, SchoolResponse,
    ClassResponse, SignupRequest, LoginRequest, UserResponse,
    BulkUpdateRequest, TriageRequest, CreateSchoolRequest, CreateClassRequest,
    UpdateStudentRequest, IngestResponse, InviteResponse, ScoreRecord,
    SubjectsPayload, SchoolScoreRecord, ChangePasswordRequest, ResetPasswordRequest, ClassAssignment,
    InviteRequest,
    OperatorResetRequest, PasswordResetLink, MemberResponse,
    ReportSettings, TermRequest, TermUpdate, TermResponse, ExamSheetRequest, RemarksRequest, CommentsRequest,
)
from . import report_cards

# Application log lines go to stderr next to uvicorn's own, at LOG_LEVEL.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "info").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("gradepulse")

BRAIN_STATE_PATH = os.getenv("BRAIN_STATE_PATH", "brain_state.json")
CONFIG_PATH = os.getenv("CONFIG_PATH", "class_config.json")
USER_DB_PATH = os.getenv("USER_DB_PATH", "gradepulse_users.db")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Auto-save every 30 seconds to keep workers synchronized
AUTO_SAVE_INTERVAL = float(os.getenv("AUTO_SAVE_INTERVAL", "30.0"))

# Backup configuration
BACKUP_ENABLED = os.getenv("BACKUP_ENABLED", "true").lower() == "true"
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
BACKUP_MAX_COUNT = int(os.getenv("BACKUP_MAX_COUNT", "24"))
BACKUP_INTERVAL = float(os.getenv("BACKUP_INTERVAL", "21600"))  # 6 hours

MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # roster / content files

# Content suggestions (POST /recommend) stay off until schools have a content
# library and teachers can record whether a suggestion helped; until then the
# engine has no real signal to learn from.
RECOMMENDATIONS_ENABLED = os.getenv("RECOMMENDATIONS_ENABLED", "false").lower() == "true"

SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "false").lower() == "true"

# Data protection: deleted (archived) records are removed for good after
# ARCHIVE_PURGE_DAYS, and audit entries after AUDIT_KEEP_DAYS. The privacy
# page promises deletion, backups included, within 30 days.
ARCHIVE_PURGE_DAYS = int(os.getenv("ARCHIVE_PURGE_DAYS", "14"))
AUDIT_KEEP_DAYS = int(os.getenv("AUDIT_KEEP_DAYS", "365"))
MAINTENANCE_INTERVAL = float(os.getenv("MAINTENANCE_INTERVAL", "86400"))  # daily

brain_instance: Optional[Brain] = None
synchronizer: Optional[BrainSynchronizer] = None
backup_manager: Optional[BackupManager] = None


def _load_brain() -> Brain:
    """
    Load brain state from disk with file locking.
    
    Each worker loads its own copy from disk, ensuring they all start
    with the same state. This prevents forked copies from diverging.
    """
    global synchronizer
    
    # Initialize synchronizer if not done yet
    if synchronizer is None:
        synchronizer = BrainSynchronizer(
            brain_state_path=BRAIN_STATE_PATH,
            config_path=CONFIG_PATH,
            auto_save_interval=AUTO_SAVE_INTERVAL,
        )
    
    # Try loading from main state file
    if os.path.exists(BRAIN_STATE_PATH):
        try:
            logger.info("Worker %s: loading brain state from %s", os.getpid(), BRAIN_STATE_PATH)
            brain = synchronizer.load_brain(Brain.load)
            if brain is not None:
                logger.info("Worker %s: brain state loaded", os.getpid())
                return brain
        except Exception as e:
            logger.warning("Could not load %s: %s", BRAIN_STATE_PATH, e)
    
    # Try loading from checkpoints
    checkpoints = sorted(
        glob.glob("*_checkpoint_*.json") + glob.glob("oulad_checkpoint_*.json"),
        key=os.path.getmtime, reverse=True,
    )
    for cp in checkpoints:
        try:
            logger.info("Worker %s: loading brain state from checkpoint %s", os.getpid(), cp)
            brain = synchronizer.load_brain(lambda path: Brain.load(cp))
            if brain is not None:
                logger.info("Worker %s: brain state loaded from checkpoint", os.getpid())
                return brain
        except Exception as e:
            logger.warning("Could not load %s: %s", cp, e)
    
    # Start empty. Sample students/content are only seeded when asked for
    # (SEED_DEMO_DATA=true), never on a real deployment.
    brain = Brain(model_type="hybrid")
    if SEED_DEMO_DATA:
        logger.info("Worker %s: seeding demo students and content (SEED_DEMO_DATA)", os.getpid())
        _seed_demo_data(brain)
    synchronizer.set_brain(brain)
    # Save initial state so other workers can load it
    synchronizer.save_brain(brain.save)
    return brain


def _seed_demo_data(brain: Brain):
    students = [
        ("608041", "Alice", 0.72, "Math"), ("573152", "Bob", 0.45, "Science"),
        ("291018", "Charlie", 0.88, "History"), ("834729", "Diana", 0.61, "Math"),
        ("115503", "Eve", 0.93, "Science"),
    ]
    for sid, name, perf, topic in students:
        brain.add_student(sid, name, performance_score=perf, current_topic=topic)

    content_items = [
        ("C001", "Algebra Fundamentals", "Math", 2, "video"),
        ("C002", "Advanced Calculus", "Math", 5, "quiz"),
        ("C003", "Cell Biology", "Science", 3, "reading"),
        ("C004", "Quantum Physics", "Science", 5, "video"),
        ("C005", "World War II Overview", "History", 2, "reading"),
        ("C006", "Ancient Civilizations", "History", 4, "quiz"),
        ("C007", "Grammar Essentials", "English", 1, "video"),
        ("C008", "Creative Writing", "English", 3, "exercise"),
    ]
    for cid, title, topic, diff, ctype in content_items:
        brain.add_content(cid, title, topic, diff, ctype)

    for sid, _, _, _ in students:
        for _ in range(3):
            rec = brain.recommend(sid, top_n=1)
            brain.update(sid, rec.content_id, 0.5 + 0.5 * np.random.random())



# ── Students live in the store; the Brain only borrows them ─────────────────
# Features the engine reads that the roster import can supply.
ENGINE_FEATURES = ("education_level", "age_band", "credits_studied", "imd_band", "region_code")


def _audit(user: dict, action: str, target: str = "") -> None:
    """Record who viewed or changed student data. Never fails the request."""
    try:
        store.audit(user.get("id", ""), user.get("school_id", ""), action, target)
    except Exception:
        logger.exception("Could not write audit entry %s", action)


def run_maintenance() -> dict:
    """Delete archived records past ARCHIVE_PURGE_DAYS and old audit entries."""
    purged = store.purge_archived(ARCHIVE_PURGE_DAYS)
    if brain_instance is not None and purged["engine_keys"]:
        with brain_instance._lock:
            for key in purged["engine_keys"]:
                brain_instance.students.pop(key, None)
    purged["audit_entries"] = store.purge_audit(AUDIT_KEEP_DAYS)
    if any(purged[k] for k in ("students", "classes", "schools", "audit_entries")):
        logger.info("Maintenance deleted %s students (%s scores), %s classes, %s schools, %s audit entries",
                    purged["students"], purged["scores"], purged["classes"], purged["schools"],
                    purged["audit_entries"])
    return purged


def _maintenance_loop(stop: "threading.Event") -> None:
    while True:
        try:
            run_maintenance()
        except Exception:
            logger.exception("Maintenance run failed")
        if stop.wait(MAINTENANCE_INTERVAL):
            return


def _student_schema(rec: store.StudentRecord) -> StudentSchema:
    return StudentSchema(
        student_id=rec.student_id, name=rec.name, grade_history=rec.grade_history,
        performance_score=rec.performance_score, current_topic=rec.current_topic,
        class_id=rec.class_id, school_id=rec.school_id, metadata=rec.metadata,
    )


def _own_student(user: dict, student_id: str) -> store.StudentRecord:
    """The caller's student with this ID. IDs are per school, so another
    school's student with the same ID is simply not found."""
    rec = store.get_student(user.get("school_id", ""), student_id)
    scope = _class_scope(user)
    # A teacher's students are the ones in their classes; others are not found.
    if rec is None or (scope is not None and rec.class_id not in scope):
        raise HTTPException(status_code=404, detail="Student not found")
    return rec


# ── Admins see the whole school; teachers see the classes they teach ──────────

def _class_scope(user: dict) -> Optional[List[str]]:
    """None for an admin (every class); the teacher's assigned class IDs otherwise."""
    if user.get("role", ROLE_ADMIN) == ROLE_ADMIN:
        return None
    return store.get_teacher_classes(user["id"], user.get("school_id", ""))


def _require_class_in_scope(user: dict, class_id: str) -> None:
    scope = _class_scope(user)
    if scope is not None and class_id not in scope:
        raise HTTPException(status_code=403, detail="That class is not one of yours")


def _engine_student(rec: store.StudentRecord) -> str:
    """Give the Brain an up-to-date copy of a stored student; returns its key."""
    key = rec.engine_key
    with brain_instance._lock:
        student = brain_instance.students.get(key)
        if student is None:
            student = brain_instance.add_student(key, rec.name)
            student.session_count = int(rec.features.get("session_count", 0))
        student.name = rec.name
        student.school_id = rec.school_id
        student.class_id = rec.class_id
        student.current_topic = rec.current_topic
        student.performance_score = rec.performance_score
        student.grade_history = {subject: list(v) for subject, v in rec.grade_history.items()}
        for feature in ENGINE_FEATURES:
            if feature in rec.features:
                setattr(student, feature, rec.features[feature])
    return key


def _student_features(student: Student) -> dict:
    return {"session_count": student.session_count,
            **{feature: getattr(student, feature) for feature in ENGINE_FEATURES}}


def _clamp_scores(history: Dict[str, List[float]]) -> Dict[str, List[float]]:
    return {subject: [min(1.0, max(0.0, float(v))) for v in values] for subject, values in history.items()}


def _ingest_roster(filepath: str, school: dict, dry_run: bool, user: Optional[dict] = None):
    """Run a roster file through ingest.py against this school's classes and
    students, then save what it added or changed to the store."""
    from ingest import ingest_students

    school_id = school["school_id"]
    # ingest.py works on the old registry shape; hand it this school only.
    registry = {"term_subjects": [], "schools": [{**school, "classes": [dict(c) for c in school["classes"]]}]}
    known_classes = {c["class_id"] for c in school["classes"]}

    existing = {rec.student_id: rec for rec in store.list_students(school_id)}
    # grade_history starts empty so that, afterwards, a non-empty subject is
    # exactly one the file supplied.
    roster = {
        sid: Student(
            student_id=sid, name=rec.name, school_id=school_id, class_id=rec.class_id,
            current_topic=rec.current_topic, performance_score=rec.baseline_score,
            metadata=dict(rec.metadata), session_count=int(rec.features.get("session_count", 0)),
            **{f: rec.features[f] for f in ENGINE_FEATURES if f in rec.features},
        )
        for sid, rec in existing.items()
    }

    def snapshot(s: Student):
        return (s.class_id, s.current_topic, s.performance_score, _student_features(s))

    before = {sid: snapshot(s) for sid, s in roster.items()}
    # ingest.py only changes the in-memory registry and roster handed to it,
    # so it always runs for real here; a dry run just stops before the store.
    report = ingest_students(filepath, registry, roster, school_id=school_id, school_name=None, dry_run=False)
    # Checked on the preview too, so the admin learns before importing.
    if user is not None:
        billing.check_can_add_students(user, len(set(roster) - set(existing)))
    if dry_run:
        return report

    for cls in registry["schools"][0]["classes"]:
        if cls["class_id"] not in known_classes:
            store.add_class(school_id, cls["label"], class_id=cls["class_id"])

    for sid, s in roster.items():
        history = _clamp_scores(s.grade_history)
        rec = existing.get(sid)
        if rec is None:
            store.add_student(
                school_id, sid, s.name, class_id=s.class_id, current_topic=s.current_topic,
                baseline_score=s.performance_score, metadata=s.metadata,
                features=_student_features(s), grade_history=history,
            )
            continue
        if snapshot(s) != before[sid]:
            store.update_student(
                rec.pk, class_id=s.class_id, current_topic=s.current_topic,
                baseline_score=s.performance_score, features=_student_features(s),
            )
        # Imported history replaces earlier imports; teacher-entered scores stay.
        for subject, values in history.items():
            store.replace_imported_scores(rec.pk, subject, values)
    return report


def _adopt_legacy_students(brain: Brain) -> int:
    """One-off upgrade: students used to be saved inside brain_state.json.
    Move the ones that belong to a school into the store (first start only)."""
    if store.count_students() > 0:
        return 0
    moved = 0
    for key, s in list(brain.students.items()):
        if not s.school_id:
            continue
        try:
            store.add_student(
                s.school_id, s.student_id, s.name, class_id=s.class_id, current_topic=s.current_topic,
                baseline_score=s.performance_score, metadata=s.metadata, features=_student_features(s),
                grade_history=_clamp_scores(s.grade_history),
            )
        except sqlite3.IntegrityError:
            continue  # another worker is adopting the same file
        del brain.students[key]
        moved += 1
    return moved


# ── Phase 2 security: rate limiters + school-ownership enforcement ──────────
# Policy (2026-09-27, Divine/Sam sign-off): school context is DERIVED from the
# caller's authenticated user (users DB), not trusted from request bodies or
# query strings. Students with an EMPTY school_id are unclaimed/legacy and stay
# accessible to any authenticated user until a school claims them.
# Caps are env-tunable (RATE_LIMIT_*) so a pilot/demo instance can open the
# throttle (one shared classroom IP fires many logins); production defaults are
# unchanged when the env vars are absent.
def _limit_from_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


LOGIN_LIMITER = SlidingWindowLimiter(max_requests=_limit_from_env("RATE_LIMIT_LOGIN_EMAIL", 30), window_seconds=60)
LOGIN_HOST_LIMITER = SlidingWindowLimiter(max_requests=_limit_from_env("RATE_LIMIT_LOGIN_HOST", 120), window_seconds=60)
# Uploads per user: an admin importing a school's classes one by one needs a
# few dozen, not hundreds.
INGEST_LIMITER = SlidingWindowLimiter(max_requests=_limit_from_env("RATE_LIMIT_INGEST_USER", 30), window_seconds=600)
SIGNUP_LIMITER = SlidingWindowLimiter(max_requests=_limit_from_env("RATE_LIMIT_SIGNUP_HOST", 30), window_seconds=60)


# Behind the web app's /api proxy every request arrives from the proxy, so the
# per-address sign-in limits would cover all users at once. The proxy does not
# add the visitor's address itself; it passes on whatever X-Forwarded-For it
# received, which a visitor can set. So the header is only used when the
# operator says the front proxy (nginx) overwrites it and the app ports are not
# reachable except through that proxy. See DEPLOYMENT.md.
TRUST_FORWARDED_FOR = os.getenv("TRUST_FORWARDED_FOR", "false").lower() == "true"


# Behind Cloudflare (the tunnel), Cloudflare sets CF-Connecting-IP to the
# visitor's address and replaces any value the visitor sent. Trust it only
# when every request reaches the API through Cloudflare.
TRUST_CF_CONNECTING_IP = os.getenv("TRUST_CF_CONNECTING_IP", "false").lower() == "true"


def _client_host(request: Request) -> str:
    if TRUST_CF_CONNECTING_IP:
        address = request.headers.get("cf-connecting-ip", "").strip()
        if address:
            return address
    if TRUST_FORWARDED_FOR:
        forwarded = [a.strip() for a in request.headers.get("x-forwarded-for", "").split(",") if a.strip()]
        if forwarded:
            return forwarded[-1]  # the entry added by the proxy closest to us
    return request.client.host if request.client else "unknown"


# Backups and restore act on EVERY school's data at once, so they belong to
# whoever runs the deployment, not to any school account. Unset key = disabled.
OPERATOR_KEY = os.getenv("OPERATOR_KEY", "")


def require_operator(request: Request):
    supplied = request.headers.get("X-Operator-Key", "")
    if not OPERATOR_KEY or not hmac.compare_digest(supplied.encode(), OPERATOR_KEY.encode()):
        raise HTTPException(status_code=403, detail="Operator key required")


def _require_school_access(user: dict, school_id: str) -> str:
    user_school = user.get("school_id", "")
    if not user_school or user_school != school_id:
        raise HTTPException(status_code=403, detail="Not authorized for this school")
    return user_school


def _validate_class_belongs_to_user(user: dict, class_id: str):
    user_school = user.get("school_id", "")
    if not user_school:
        raise HTTPException(status_code=403, detail="User has no school — create/join a school first")
    if not store.get_class(user_school, class_id):
        raise HTTPException(status_code=400, detail="Class does not belong to your school")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global brain_instance, synchronizer, backup_manager
    
    # Load brain state for this worker
    brain_instance = _load_brain()
    if os.path.exists(CONFIG_PATH):
        # One-off upgrade from class_config.json; a no-op once schools exist.
        moved = store.adopt_legacy_registry(load_registry(CONFIG_PATH))
        if moved:
            logger.info("Worker %s: moved %s schools from %s into the store", os.getpid(), moved, CONFIG_PATH)
    adopted = _adopt_legacy_students(brain_instance)
    if adopted:
        logger.info("Worker %s: moved %s students from the brain state into the store", os.getpid(), adopted)
    
    # Set brain in synchronizer and start auto-save
    if synchronizer is not None:
        synchronizer.set_brain(brain_instance)
        synchronizer.start_auto_save(lambda path: brain_instance.save(path))
        logger.info("Worker %s: auto-save every %ss", os.getpid(), AUTO_SAVE_INTERVAL)
    
    # Initialize backup manager
    if BACKUP_ENABLED:
        backup_manager = BackupManager(
            backup_dir=BACKUP_DIR,
            max_backups=BACKUP_MAX_COUNT,
            backup_interval=BACKUP_INTERVAL,
        )
        # Register files for backup (brain, school/class registry, AND the
        # user/account DB — a restore must not lose signups or school ties).
        backup_manager.register_file(BRAIN_STATE_PATH)
        backup_manager.register_file(CONFIG_PATH)
        if USER_DB_PATH:
            # Copied through SQLite's backup API, uncheckpointed WAL writes included.
            backup_manager.register_file(USER_DB_PATH)
        # Create initial backup
        backup_manager.create_backup("startup")
        # Start periodic backups
        backup_manager.start()
        logger.info("Worker %s: backups every %ss, keeping %s", os.getpid(), BACKUP_INTERVAL, BACKUP_MAX_COUNT)
    
    maintenance_stop = threading.Event()
    threading.Thread(target=_maintenance_loop, args=(maintenance_stop,), daemon=True,
                     name="gradepulse-maintenance").start()

    yield

    maintenance_stop.set()
    # Shutdown: save brain state, stop auto-save, stop backups
    if backup_manager is not None:
        backup_manager.stop()
        backup_manager.create_backup("shutdown")
        logger.info("Worker %s: final backup created on shutdown", os.getpid())
    
    if synchronizer is not None:
        synchronizer.stop_auto_save()
        synchronizer.save_brain(brain_instance.save)
        logger.info("Worker %s: brain state saved on shutdown", os.getpid())


# The interactive API docs help in development; a production server does not
# advertise its endpoints.
_PRODUCTION = AUTH_ENV in ("production", "prod")
_DOCS = not _PRODUCTION
app = FastAPI(
    title="GradePulse API", version=__version__, lifespan=lifespan,
    docs_url="/docs" if _DOCS else None, redoc_url="/redoc" if _DOCS else None,
    openapi_url="/openapi.json" if _DOCS else None,
)

app.include_router(billing_router)


class _BodyTooLarge(HTTPException):
    # An HTTPException, so FastAPI's body parsing passes it on as a 413.
    def __init__(self):
        super().__init__(status_code=413, detail="Request is too large")


class BodySizeLimit:
    """Refuse request bodies over a size limit before they are read into
    memory: uploads up to MAX_UPLOAD_BYTES plus form overhead, everything
    else 512 KB (a full score sheet is under 200 KB)."""

    def __init__(self, app, default_limit: int, upload_limit: int):
        self.app = app
        self.default_limit = default_limit
        self.upload_limit = upload_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        limit = self.upload_limit if scope.get("path", "").rstrip("/").endswith("/ingest") else self.default_limit
        declared = dict(scope.get("headers") or []).get(b"content-length")
        too_large = JSONResponse(status_code=413, content={"detail": "Request is too large"})
        if declared is not None:
            try:
                if int(declared) > limit:
                    return await too_large(scope, receive, send)
            except ValueError:
                return await JSONResponse(status_code=400, content={"detail": "Bad Content-Length"})(scope, receive, send)
        received = 0
        response_started = False

        async def counted_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge()
            return message

        async def tracked_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counted_receive, tracked_send)
        except _BodyTooLarge:
            if not response_started:
                await too_large(scope, receive, send)


app.add_middleware(BodySizeLimit, default_limit=512 * 1024, upload_limit=MAX_UPLOAD_BYTES + 256 * 1024)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """API answers are data, never pages: no sniffing, no framing, and no
    caching of student data by browsers or Cloudflare."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    return response

app.add_middleware(
    CORSMiddleware,
    # Local dev origins are trusted only outside production.
    allow_origins=[u.strip().rstrip("/") for u in FRONTEND_URL.split(",") if u.strip()]
    + ([] if _PRODUCTION else ["http://localhost:3000", "http://localhost:3001"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # FastAPI's default 422 echoes every rejected value back, passwords
    # included. Keep the location, type and message; drop the values.
    errors = [{k: e[k] for k in ("type", "loc", "msg") if k in e} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # The client gets a short reference; the log line under it has the trace.
    error_id = uuid.uuid4().hex[:12]
    logger.exception("Unhandled error %s on %s %s", error_id, request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "error_id": error_id})


# ══════════════════════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/auth/signup", response_model=UserResponse)
def signup(request: Request, response: Response, signup_request: SignupRequest):
    if not SIGNUP_LIMITER.allow(_client_host(request)):
        raise HTTPException(status_code=429, detail="Too many signups from this address — try again later")
    invite_code = (signup_request.invite_code or "").strip()
    if invite_code:
        # Joining an existing school is only possible with an admin's invite.
        invite = get_usable_invite(invite_code)
        school = store.get_school(invite["school_id"]) if invite else None
        if not school:
            raise HTTPException(status_code=400, detail="This invite code is invalid or has expired")
        user = create_user(signup_request.email, signup_request.password)
        if not redeem_invite(invite_code, user["id"]):
            # Someone else used the invite in the meantime: take the new
            # account away again rather than leave it with no school.
            remove_member(user["id"])
            raise HTTPException(status_code=400, detail="This invite code is invalid or has expired")
        role = ROLE_TEACHER
        # Put the teacher straight into the classes the admin chose for the invite.
        invite_classes = json.loads(invite.get("class_ids") or "[]")
        if invite_classes:
            store.set_teacher_classes(user["id"], school["school_id"], invite_classes)
    else:
        user = create_user(signup_request.email, signup_request.password)
        # Without an invite, signup always creates the caller's OWN school.
        # Matching an existing school by name used to attach the new account
        # to it, which let anyone who knew a school's name read its students.
        school = store.create_school(signup_request.school_name or "MY SCHOOL")
        role = ROLE_ADMIN
    update_user_school(user["id"], school["school_id"], role=role)
    token = create_access_token({"sub": user["id"]})
    set_session_cookie(response, token)
    return {"id": user["id"], "email": user["email"], "school_id": school["school_id"],
            "school_name": school["name"], "role": role, "token": token}


def _wait_words(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} seconds"
    minutes = -(-seconds // 60)
    return "1 minute" if minutes == 1 else f"{minutes} minutes"


@app.post("/auth/login", response_model=UserResponse)
def login(request: Request, response: Response, login_request: LoginRequest):
    if not LOGIN_HOST_LIMITER.allow(_client_host(request)):
        raise HTTPException(status_code=429, detail="Too many login attempts — try again later")
    if not LOGIN_LIMITER.allow(f"{_client_host(request)}|{login_request.email.lower()}"):
        raise HTTPException(status_code=429, detail="Too many login attempts for this account — try again later")
    # Checked before the password, so a paused address cannot keep guessing.
    address = _client_host(request)
    wait = login_wait_seconds(login_request.email, address)
    if wait:
        raise HTTPException(status_code=429, headers={"Retry-After": str(wait)}, detail=(
            f"Too many wrong passwords for this account. Try again in {_wait_words(wait)}, "
            "or ask your school admin for a password reset link."))
    user = authenticate_user(login_request.email, login_request.password)
    if not user:
        record_login_failure(login_request.email, address)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    clear_login_failures(login_request.email, address)
    school = None
    if user.get("school_id"):
        school = store.get_school(user["school_id"])
    token = create_access_token({"sub": user["id"]})
    set_session_cookie(response, token)
    return {"id": user["id"], "email": user["email"],
            "school_id": user.get("school_id", ""),
            "school_name": school["name"] if school else "",
            "role": user.get("role", ROLE_ADMIN),
            "token": token}


@app.get("/auth/me", response_model=UserResponse)
def me(response: Response, user: dict = Depends(get_current_user),
       credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)):
    if credentials:
        # A session from before the cookie (token kept in the browser's
        # storage) moves to the cookie, so nobody is signed out by the change.
        set_session_cookie(response, credentials.credentials)
    school = None
    if user.get("school_id"):
        school = store.get_school(user["school_id"])
    return {"id": user["id"], "email": user["email"],
            "school_id": user.get("school_id", ""),
            "school_name": school["name"] if school else "",
            "role": user.get("role", ROLE_ADMIN)}


# ── Passwords ───────────────────────────────────────────────────────────────
# There is no email service, so a forgotten password is recovered with a
# single-use reset code handed over by someone already trusted: a school admin
# for the teachers in their school, the deployment's operator for anyone.

@app.post("/auth/change-password", response_model=UserResponse)
def change_password(http_request: Request, response: Response, request: ChangePasswordRequest,
                    user: dict = Depends(get_current_user)):
    address = _client_host(http_request)
    wait = login_wait_seconds(user["email"], address)
    if wait:
        raise HTTPException(status_code=429, headers={"Retry-After": str(wait)},
                            detail=f"Too many wrong passwords. Try again in {_wait_words(wait)}.")
    if not verify_password(request.current_password, user["password_hash"]):
        record_login_failure(user["email"], address)
        raise HTTPException(status_code=400, detail="Your current password is not correct")
    if password_mentions_email(request.new_password, user["email"]):
        raise HTTPException(status_code=422, detail="Your password must not contain your email address")
    set_password(user["id"], request.new_password)
    clear_login_failures(user["email"], address)
    school = store.get_school(user.get("school_id", ""))
    # Every earlier session is now signed out; this one continues on a new token.
    token = create_access_token({"sub": user["id"]})
    set_session_cookie(response, token)
    return {"id": user["id"], "email": user["email"], "school_id": user.get("school_id", ""),
            "school_name": school["name"] if school else "", "role": user.get("role", ROLE_ADMIN),
            "token": token}


@app.post("/auth/logout")
def logout(response: Response):
    """Ends the browser session: both session cookies are removed."""
    clear_session_cookie(response)
    return {"status": "signed_out"}


@app.post("/auth/reset-password")
def reset_password(http_request: Request, request: ResetPasswordRequest):
    if not LOGIN_HOST_LIMITER.allow(_client_host(http_request)):
        raise HTTPException(status_code=429, detail="Too many attempts — try again later")
    if not redeem_password_reset(request.code.strip(), request.new_password):
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired")
    return {"status": "password_updated"}


@app.post("/billing/pilot")
def grant_pilot_term(request: billing.PilotRequest, _: None = Depends(require_operator)):
    """Operator: give the school of this admin a free pilot term (reports
    included, no free-plan limit up to `students`). See billing.py."""
    account = get_user_by_email(request.email)
    if not account or account.get("role") != "admin" or not account.get("school_id"):
        raise HTTPException(status_code=404, detail="No school admin with that email")
    days = request.days or billing._term_days()
    payment = billing.grant_pilot(account["school_id"], request.students, days)
    return {"reference": payment["reference"], "school_id": account["school_id"],
            "pilot_until": payment["period_end"], **billing.billing_status(account["school_id"])}


@app.post("/auth/operator-reset", response_model=PasswordResetLink)
def operator_reset(request: OperatorResetRequest, _: None = Depends(require_operator)):
    """For an admin who is locked out: the operator issues the reset code."""
    account = get_user_by_email(request.email)
    if not account:
        raise HTTPException(status_code=404, detail="No account with that email")
    return create_password_reset(account["id"], created_by="operator")


@app.get("/members", response_model=List[MemberResponse])
def list_members(user: dict = Depends(require_admin)):
    school_id = _admin_school(user)
    return [
        {**member, "class_ids": store.get_teacher_classes(member["id"], school_id)
         if member["role"] == ROLE_TEACHER else []}
        for member in list_school_members(school_id)
    ]


@app.put("/members/{user_id}/classes", response_model=MemberResponse)
def assign_member_classes(user_id: str, request: ClassAssignment, user: dict = Depends(require_admin)):
    """Set which classes a teacher teaches (and so can see)."""
    school_id = _admin_school(user)
    member = next((m for m in list_school_members(school_id) if m["id"] == user_id), None)
    if member is None:
        raise HTTPException(status_code=404, detail="No such member in your school")
    if member["role"] != ROLE_TEACHER:
        raise HTTPException(status_code=400, detail="Admins see every class; only teachers are assigned classes")
    return {**member, "class_ids": store.set_teacher_classes(user_id, school_id, request.class_ids)}


@app.post("/members/{user_id}/password-reset", response_model=PasswordResetLink)
def member_password_reset(user_id: str, user: dict = Depends(require_admin)):
    school_id = _admin_school(user)
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Use Change Password for your own account")
    if not any(member["id"] == user_id for member in list_school_members(school_id)):
        raise HTTPException(status_code=404, detail="No such member in your school")
    _audit(user, "password_reset_link", user_id)
    return create_password_reset(user_id, created_by=user["id"])


@app.delete("/members/{user_id}")
def remove_school_member(user_id: str, user: dict = Depends(require_admin)):
    """Remove a teacher who has left: their account is deleted and every
    session they have stops working at once."""
    school_id = _admin_school(user)
    member = next((m for m in list_school_members(school_id) if m["id"] == user_id), None)
    if member is None:
        raise HTTPException(status_code=404, detail="No such member in your school")
    if member["role"] != ROLE_TEACHER:
        raise HTTPException(status_code=400, detail="Only teachers can be removed. An admin account stays with the school.")
    remove_member(user_id)
    _audit(user, "remove_teacher", member["email"])
    logger.info("Admin %s removed teacher %s from school %s", user["id"], user_id, school_id)
    return {"status": "removed"}


# ══════════════════════════════════════════════════════════════════════════════
# INVITES (admin only)
# ══════════════════════════════════════════════════════════════════════════════

def _admin_school(user: dict) -> str:
    school_id = user.get("school_id", "")
    if not school_id:
        raise HTTPException(status_code=403, detail="User has no school — create a school first")
    return school_id


@app.post("/invites", response_model=InviteResponse)
def create_school_invite(request: Optional[InviteRequest] = None, user: dict = Depends(require_admin)):
    """An invite link; the admin can choose the classes the teacher will teach."""
    school_id = _admin_school(user)
    wanted = (request.class_ids if request else []) or []
    valid = {c["class_id"] for c in store.list_classes(school_id)}
    unknown = [cid for cid in wanted if cid not in valid]
    if unknown:
        raise HTTPException(status_code=400, detail="Some of those classes are not in your school")
    return create_invite(school_id, user["id"], class_ids=list(dict.fromkeys(wanted)))


@app.get("/invites", response_model=List[InviteResponse])
def list_school_invites(user: dict = Depends(require_admin)):
    return list_pending_invites(_admin_school(user))


@app.delete("/invites/{invite_id}")
def revoke_school_invite(invite_id: str, user: dict = Depends(require_admin)):
    if not revoke_invite(invite_id, _admin_school(user)):
        raise HTTPException(status_code=404, detail="Invite not found")
    return {"status": "revoked"}


# ══════════════════════════════════════════════════════════════════════════════
# SCHOOLS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/schools", response_model=List[SchoolResponse])
def list_schools(user: dict = Depends(get_current_user)):
    school = store.get_school(user.get("school_id", ""))
    return [school] if school else []


@app.post("/schools", response_model=SchoolResponse)
def create_school(request: CreateSchoolRequest, user: dict = Depends(get_current_user)):
    """For an account with no school yet. A school nobody belongs to could
    never be used or deleted, so an account that has one cannot add another."""
    if store.get_school(user.get("school_id", "")):
        raise HTTPException(status_code=400, detail="Your account already has a school")
    school = store.create_school(request.name)
    update_user_school(user["id"], school["school_id"], role=ROLE_ADMIN)
    return school


@app.put("/schools/{school_id}", response_model=SchoolResponse)
def update_school(school_id: str, request: CreateSchoolRequest, user: dict = Depends(require_admin)):
    _require_school_access(user, school_id)
    if not store.get_school(school_id):
        raise HTTPException(status_code=404, detail="School not found")
    store.rename_school(school_id, request.name)
    return store.get_school(school_id)


@app.delete("/schools/{school_id}")
def delete_school(school_id: str, user: dict = Depends(require_admin)):
    _require_school_access(user, school_id)
    if not store.get_school(school_id):
        raise HTTPException(status_code=404, detail="School not found")
    store.archive_school(school_id)
    _audit(user, "delete_school", school_id)
    return {"status": "deleted"}


# ── Subjects: each school keeps its own list ────────────────────────────────

@app.get("/subjects", response_model=SubjectsPayload)
def list_subjects(user: dict = Depends(get_current_user)):
    return {"subjects": store.get_subjects(user.get("school_id", ""))}


@app.put("/subjects", response_model=SubjectsPayload)
def replace_subjects(request: SubjectsPayload, user: dict = Depends(require_admin)):
    school_id = _admin_school(user)
    subjects = store.set_subjects(school_id, request.subjects)
    if not subjects:
        raise HTTPException(status_code=400, detail="Keep at least one subject")
    return {"subjects": subjects}


# ══════════════════════════════════════════════════════════════════════════════
# CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/classes/{school_id}", response_model=List[ClassResponse])
def list_classes(school_id: str, user: dict = Depends(get_current_user)):
    _require_school_access(user, school_id)
    classes = store.list_classes(school_id)
    scope = _class_scope(user)
    return classes if scope is None else [c for c in classes if c["class_id"] in scope]


@app.post("/classes/{school_id}", response_model=ClassResponse)
def create_class(school_id: str, request: CreateClassRequest, user: dict = Depends(require_admin)):
    _require_school_access(user, school_id)
    cls = store.add_class(school_id, request.label)
    if not cls:
        raise HTTPException(status_code=400, detail="Class already exists in this school")
    return cls


@app.put("/classes/{school_id}/{class_id}", response_model=ClassResponse)
def update_class(school_id: str, class_id: str, request: CreateClassRequest, user: dict = Depends(require_admin)):
    _require_school_access(user, school_id)
    if not store.get_class(school_id, class_id):
        raise HTTPException(status_code=404, detail="Class not found")
    if not request.label.strip():
        raise HTTPException(status_code=400, detail="Class name cannot be empty")
    cls = store.rename_class(school_id, class_id, request.label)
    if not cls:
        raise HTTPException(status_code=400, detail="Class already exists in this school")
    return cls


@app.delete("/classes/{school_id}/{class_id}")
def delete_class(school_id: str, class_id: str, user: dict = Depends(require_admin)):
    _require_school_access(user, school_id)
    if not store.get_class(school_id, class_id):
        raise HTTPException(status_code=404, detail="Class not found")
    store.archive_class(school_id, class_id)
    _audit(user, "delete_class", class_id)
    return {"status": "deleted"}


# ══════════════════════════════════════════════════════════════════════════════
# STUDENTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/students", response_model=List[StudentSchema])
def list_students(
    school_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    user_school = user.get("school_id", "")
    # The caller can never override the school filter with the query param —
    # the school is always derived from the authenticated user (Phase 2).
    if school_id and school_id != user_school:
        raise HTTPException(status_code=403, detail="Not authorized for this school")
    if class_id:
        _require_class_in_scope(user, class_id)
    students = store.list_students(user_school, class_id or "", class_ids=_class_scope(user))
    _audit(user, "view_students", f"class {class_id}" if class_id else "all")
    return [_student_schema(rec) for rec in students]


@app.post("/students", response_model=StudentSchema)
def add_student(student: StudentSchema, user: dict = Depends(get_current_user)):
    school_id = user.get("school_id", "")
    if not school_id:
        raise HTTPException(status_code=403, detail="User has no school — create/join a school first")
    class_id = student.metadata.get("class_id") or student.class_id or ""
    if class_id:
        _validate_class_belongs_to_user(user, class_id)
    if _class_scope(user) is not None and not class_id:
        raise HTTPException(status_code=400, detail="Choose one of your classes for the student")
    if class_id:
        _require_class_in_scope(user, class_id)
    existing = store.get_student(school_id, student.student_id)
    if existing is None:
        billing.check_can_add_students(user, 1)
    else:
        scope = _class_scope(user)
        if scope is not None and existing.class_id not in scope:
            # The ID belongs to a student in a class this teacher does not
            # teach. Returning that record would hand over their scores.
            raise HTTPException(status_code=409, detail="That student ID is already used in your school")
    # An ID that already exists in this school returns that student unchanged.
    rec, _created = store.add_student(
        school_id, student.student_id, student.name,
        class_id=class_id, current_topic=student.current_topic or "",
        baseline_score=student.performance_score, metadata=student.metadata,
        grade_history=student.grade_history,
    )
    _audit(user, "add_student", student.student_id)
    return _student_schema(rec)


@app.put("/students/{student_id}", response_model=StudentSchema)
def update_student(student_id: str, request: UpdateStudentRequest, user: dict = Depends(get_current_user)):
    rec = _own_student(user, student_id)
    changes = {}
    if request.name is not None:
        changes["name"] = request.name
    if request.current_topic is not None:
        changes["current_topic"] = request.current_topic
    if request.class_id is not None:
        if request.class_id:  # "" takes the student out of their class
            _validate_class_belongs_to_user(user, request.class_id)
        if _class_scope(user) is not None and not request.class_id:
            raise HTTPException(status_code=400, detail="A teacher's students must stay in one of their classes")
        if request.class_id:
            _require_class_in_scope(user, request.class_id)
        changes["class_id"] = request.class_id
        # Keep metadata.class_id in sync — the create path and the frontend
        # convention treat metadata as the class key too.
        changes["metadata"] = {**rec.metadata, "class_id": request.class_id}
    store.update_student(rec.pk, **changes)
    _audit(user, "edit_student", f"{student_id}: {', '.join(sorted(changes))}")
    return _student_schema(_own_student(user, student_id))


@app.delete("/students/{student_id}")
def delete_student(student_id: str, user: dict = Depends(require_admin)):
    rec = _own_student(user, student_id)
    store.archive_student(rec.pk)
    brain_instance.students.pop(rec.engine_key, None)
    _audit(user, "delete_student", student_id)
    return {"status": "deleted"}


@app.get("/scores", response_model=List[SchoolScoreRecord])
def list_school_scores(class_id: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    """Every recorded score in the caller's school, or one class of it — the
    data behind class and parent reports, which come with a paid term."""
    billing.check_reports(user)
    if class_id:
        _require_class_in_scope(user, class_id)
    _audit(user, "view_scores", f"class {class_id}" if class_id else "all")
    return store.list_school_scores(user.get("school_id", ""), class_id or "", class_ids=_class_scope(user))


@app.get("/students/{student_id}/scores", response_model=List[ScoreRecord])
def list_student_scores(student_id: str, user: dict = Depends(get_current_user)):
    """Every recorded score for one student, oldest first."""
    rec = _own_student(user, student_id)
    _audit(user, "view_student_scores", student_id)
    return store.list_scores(rec.pk)


# ══════════════════════════════════════════════════════════════════════════════
# TERM REPORT CARDS
# CA from the term's weekly tests + an exam, graded, with positions, remarks,
# comments and attendance. Admins set up terms and settings; teachers enter
# exams, remarks and form-teacher comments for their own classes.
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/report-settings", response_model=ReportSettings)
def get_report_settings(user: dict = Depends(get_current_user)):
    return report_cards.settings_with_defaults(store.get_report_settings(user.get("school_id", "")))


@app.put("/report-settings", response_model=ReportSettings)
def put_report_settings(request: ReportSettings, user: dict = Depends(require_admin)):
    school_id = _admin_school(user)
    try:
        scale = report_cards.clean_grade_scale([b.model_dump() for b in request.grade_scale])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    settings = {**request.model_dump(), "grade_scale": scale,
                "address": request.address.strip(), "principal_name": request.principal_name.strip()}
    store.set_report_settings(school_id, settings)
    _audit(user, "update_report_settings")
    return settings


@app.get("/terms", response_model=List[TermResponse])
def list_terms(user: dict = Depends(get_current_user)):
    return store.list_terms(user.get("school_id", ""))


def _term_fields(data: dict) -> dict:
    fields = {k: v for k, v in data.items() if v is not None}
    for key in ("starts_on", "ends_on", "next_term_begins"):
        if key in fields:
            fields[key] = fields[key].isoformat()
    for key in ("session", "name"):
        if key in fields:
            fields[key] = " ".join(fields[key].split())
    return fields


@app.post("/terms", response_model=TermResponse)
def create_term(request: TermRequest, user: dict = Depends(require_admin)):
    term = store.add_term(_admin_school(user), _term_fields(request.model_dump()))
    _audit(user, "create_term", term["term_id"])
    return term


@app.put("/terms/{term_id}", response_model=TermResponse)
def update_term(term_id: str, request: TermUpdate, user: dict = Depends(require_admin)):
    school_id = _admin_school(user)
    current = _term(user, term_id)
    sent = request.model_dump(exclude_unset=True)
    fields = _term_fields(sent)
    if "next_term_begins" in sent and sent["next_term_begins"] is None:
        fields["next_term_begins"] = ""   # cleared
    starts, ends = fields.get("starts_on", current["starts_on"]), fields.get("ends_on", current["ends_on"])
    if ends < starts:
        raise HTTPException(status_code=400, detail="The term must end after it starts")
    _audit(user, "update_term", term_id)
    return store.update_term(school_id, term_id, fields)


@app.delete("/terms/{term_id}")
def delete_term(term_id: str, user: dict = Depends(require_admin)):
    if not store.archive_term(_admin_school(user), term_id):
        raise HTTPException(status_code=404, detail="Term not found")
    _audit(user, "delete_term", term_id)
    return {"status": "deleted"}


def _term(user: dict, term_id: str) -> dict:
    term = store.get_term(user.get("school_id", ""), term_id)
    if term is None:
        raise HTTPException(status_code=404, detail="Term not found")
    return term


def _report_class(user: dict, class_id: str) -> dict:
    """A class of the caller's school that the caller may see."""
    cls = store.get_class(user.get("school_id", ""), class_id)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    _require_class_in_scope(user, class_id)
    return cls


def _students_for_entries(user: dict, student_ids) -> dict:
    """student_id -> record, each one checked to be the caller's."""
    return {sid: _own_student(user, sid) for sid in dict.fromkeys(student_ids)}


@app.put("/terms/{term_id}/exam-scores")
def save_exam_scores(term_id: str, request: ExamSheetRequest, user: dict = Depends(get_current_user)):
    """One subject's exam scores (0-1 share of the exam) for some students."""
    billing.check_can_enter_scores(user)
    _term(user, term_id)
    subject = store.normalize_label(request.subject)
    known = {store.normalize_label(s) for s in store.get_subjects(user.get("school_id", ""))}
    if subject not in known:
        raise HTTPException(status_code=400, detail="Use one of your school's subjects (Settings, Subjects)")
    records = _students_for_entries(user, (e.student_id for e in request.entries))
    store.save_exam_scores(term_id, [(records[e.student_id].pk, subject, e.score) for e in request.entries],
                           entered_by=user["id"])
    _audit(user, "enter_exam_scores", f"term {term_id}, {subject}, {len(request.entries)} students")
    return {"status": "saved", "saved": len(request.entries)}


@app.put("/terms/{term_id}/remarks")
def save_subject_remarks(term_id: str, request: RemarksRequest, user: dict = Depends(get_current_user)):
    """Subject teachers' remarks, one per student and subject."""
    billing.check_can_enter_scores(user)
    _term(user, term_id)
    records = _students_for_entries(user, (e.student_id for e in request.entries))
    store.save_subject_remarks(
        term_id,
        [(records[e.student_id].pk, store.normalize_label(e.subject), " ".join(e.remark.split()))
         for e in request.entries],
        entered_by=user["id"],
    )
    _audit(user, "enter_remarks", f"term {term_id}, {len(request.entries)} remarks")
    return {"status": "saved", "saved": len(request.entries)}


@app.put("/terms/{term_id}/comments")
def save_report_comments(term_id: str, request: CommentsRequest, user: dict = Depends(get_current_user)):
    """Attendance and the form teacher's comment (any teacher of the class);
    the principal's comment (admins only)."""
    billing.check_can_enter_scores(user)
    _term(user, term_id)
    is_admin = user.get("role", ROLE_ADMIN) == ROLE_ADMIN
    if not is_admin and any("principal_comment" in e.model_fields_set for e in request.entries):
        raise HTTPException(status_code=403, detail="Only a school admin can write the principal's comment")
    records = _students_for_entries(user, (e.student_id for e in request.entries))
    for entry in request.entries:
        changes = entry.model_dump(include=entry.model_fields_set - {"student_id"})
        for key in ("form_teacher_comment", "principal_comment"):
            if key in changes:
                changes[key] = " ".join((changes[key] or "").split())
        store.save_report_comment(term_id, records[entry.student_id].pk, changes, updated_by=user["id"])
    _audit(user, "enter_report_comments", f"term {term_id}, {len(request.entries)} students")
    return {"status": "saved", "saved": len(request.entries)}


@app.get("/terms/{term_id}/report-cards")
def get_report_cards(term_id: str, class_id: str = Query(..., max_length=64), user: dict = Depends(get_current_user)):
    """Every report card for one class in one term, with what is still missing."""
    billing.check_reports(user)
    term = _term(user, term_id)
    cls = _report_class(user, class_id)
    school_id = user.get("school_id", "")
    settings = report_cards.settings_with_defaults(store.get_report_settings(school_id))
    records = store.list_students(school_id, class_id)
    pks = [r.pk for r in records]
    cards = report_cards.build_cards(
        [{"pk": r.pk, "student_id": r.student_id, "name": r.name} for r in records],
        store.get_subjects(school_id),
        store.term_weekly_scores(pks, term["starts_on"], term["ends_on"]),
        store.term_exam_scores(term_id, pks),
        store.term_subject_remarks(term_id, pks),
        store.term_report_comments(term_id, pks),
        settings,
    )
    school = store.get_school(school_id) or {}
    _audit(user, "view_report_cards", f"term {term_id}, class {class_id}")
    return {
        "term": term, "class": {"class_id": cls["class_id"], "label": cls["label"]},
        "school": {"name": school.get("name", ""), "address": settings["address"],
                   "principal_name": settings["principal_name"]},
        "settings": {"ca_weight": settings["ca_weight"], "exam_weight": 100 - settings["ca_weight"],
                     "show_positions": settings["show_positions"], "grade_scale": settings["grade_scale"]},
        "class_size": len(records),
        "cards": cards,
    }


# ── The school's own data: export and audit log (admin) ────────────────────

def _csv_text(rows: List[dict], columns: List[str]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        # A cell starting with = + - @ would run as a formula in Excel.
        writer.writerow({k: ("'" + v if isinstance(v, str) and v[:1] in "=+-@" else v) for k, v in row.items()})
    return out.getvalue()


@app.get("/export")
def export_school_data(user: dict = Depends(require_admin)):
    """Everything the school has entered, as CSV files in one .zip: its
    classes, students and every score. Free on every plan."""
    school_id = _admin_school(user)
    school = store.get_school(school_id)
    data = store.export_rows(school_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("classes.csv", _csv_text(data["classes"], ["class_id", "label"]))
        archive.writestr("students.csv", _csv_text(data["students"], ["student_id", "name", "class", "created_at"]))
        archive.writestr("scores.csv", _csv_text(
            data["scores"], ["student_id", "name", "subject", "score_percent", "assessed_on", "test", "source"]))
    _audit(user, "export_school_data", f"{len(data['students'])} students, {len(data['scores'])} scores")
    name = "".join(ch if ch.isalnum() else "-" for ch in (school["name"] if school else "school")).strip("-").lower()
    return Response(content=buffer.getvalue(), media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="gradepulse-{name or "school"}-{date.today().isoformat()}.zip"'})


@app.get("/audit")
def school_audit_log(limit: int = Query(200, ge=1, le=1000), user: dict = Depends(require_admin)):
    """Who in the school viewed or changed student data, newest first."""
    return store.list_audit(_admin_school(user), limit)


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT
# ══════════════════════════════════════════════════════════════════════════════

# The content catalogue is shared by every school until per-school content
# libraries exist, so only the deployment's operator may change it.
@app.post("/content", response_model=ContentSchema)
def add_content(content: ContentSchema, _: None = Depends(require_operator)):
    try:
        brain_instance.add_content(
            content.content_id, content.title, content.topic,
            content.difficulty, content.content_type,
        )
        return content
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════════
# BRAIN OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/recommend")
def recommend(request: RecommendationRequest, user: dict = Depends(get_current_user)):
    if not RECOMMENDATIONS_ENABLED:
        raise HTTPException(status_code=404, detail="Content suggestions are switched off on this server")
    try:
        # API contract: ALWAYS return a JSON array, even for top_n=1.
        # The bare-object-vs-array polymorphism was normalised at the HTTP
        # boundary (see Mia 2026-09-27); `brain.recommend()` is unchanged for
        # ML-layer callers. `[]` means "nothing to show".
        # /recommend keeps 400 for an unknown student (existing contract).
        rec = store.get_student(user.get("school_id", ""), request.student_id)
        scope = _class_scope(user)
        if rec is None or (scope is not None and rec.class_id not in scope):
            raise HTTPException(status_code=400, detail=f"Student ID {request.student_id} not found.")
        result = brain_instance.recommend(_engine_student(rec), topic=request.topic, top_n=request.top_n)
        if request.top_n == 1:
            return [result.__dict__] if result else []
        return [r.__dict__ for r in result]
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/update")
def update(request: UpdateRequest, user: dict = Depends(get_current_user)):
    # An engine reward is feedback on a recommendation, not a grade: it
    # trains the model but is not written to the student's scores.
    rec = _own_student(user, request.student_id)
    try:
        brain_instance.update(_engine_student(rec), request.content_id, request.reward)
        synchronizer.save_brain(brain_instance.save)
        return {"status": "success"}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/bulk-update")
def bulk_update(request: BulkUpdateRequest, user: dict = Depends(get_current_user)):
    billing.check_can_enter_scores(user)
    # Only the school's own subjects: every new subject name also becomes an
    # item in the shared engine, so free text would let one school grow it.
    known = {store.normalize_label(s) for s in store.get_subjects(user.get("school_id", ""))}
    if any(store.normalize_label(e.subject) not in known for e in request.entries):
        raise HTTPException(status_code=400, detail="Use one of your school's subjects (Settings, Subjects)")
    records = {}
    for entry in request.entries:
        if entry.student_id not in records:
            records[entry.student_id] = _own_student(user, entry.student_id)
    # The store is the record of the scores...
    store.record_scores(
        [(records[e.student_id].pk, e.subject, e.score) for e in request.entries],
        assessed_on=request.assessed_on, label=request.label.strip(), entered_by=user["id"],
    )
    _audit(user, "enter_scores", f"{len(request.entries)} scores, {len(records)} students")
    # ...and the engine learns from them. Its state is saved by the periodic
    # auto-save, not on every score sheet.
    keys = {student_id: _engine_student(rec) for student_id, rec in records.items()}
    return brain_instance.bulk_update(
        [{"student_id": keys[e.student_id], "subject": e.subject, "score": e.score} for e in request.entries]
    )


@app.post("/triage")
def triage(request: TriageRequest, user: dict = Depends(get_current_user)):
    # Triage is a school report over recorded scores: only the caller's own
    # students who have been assessed in the subject are tiered, on their
    # recent tests, with the change since last week (core/triage.py).
    if request.class_id:
        _require_class_in_scope(user, request.class_id)
    school_id = user.get("school_id", "")
    scope = _class_scope(user)
    students = store.list_students(school_id, request.class_id or "", class_ids=scope)
    dated: Dict[str, list] = {}
    for row in store.list_school_scores(school_id, request.class_id or "", class_ids=scope,
                                        subject=request.subject):
        dated.setdefault(row["student_id"], []).append((date.fromisoformat(row["assessed_on"]), row["score"]))
    return build_weekly_triage(
        request.subject,
        [{"student_id": r.student_id, "name": r.name, "scores": dated.get(r.student_id, [])} for r in students],
        as_of=request.as_of,
    )


@app.post("/calculate-reward")
def get_reward(request: RewardRequest, user: dict = Depends(get_current_user)):
    reward = calculate_reward(
        request.before_score, request.after_score, request.completed,
        request.time_spent_ratio, request.engaged, request.churned,
    )
    return {"reward": reward}


@app.get("/summary", response_model=BrainSummary)
def get_summary(user: dict = Depends(get_current_user)):
    score = brain_instance.last_neural_score
    user_school = user.get("school_id", "")
    scope = _class_scope(user)
    if not user_school:
        student_count = 0
    elif scope is None:
        student_count = store.count_students(user_school)
    else:
        student_count = len(store.list_students(user_school, class_ids=scope))
    return {
        "student_count": student_count,
        "content_count": len(brain_instance.contents),
        # Scores recorded in the caller's school (the engine's own counter
        # covered every school).
        "total_sessions": store.count_scores(user_school, class_ids=scope) if user_school else 0,
        "model_type": brain_instance.model_type,
        "current_alpha": brain_instance.alpha,
        "current_gamma": brain_instance.gamma,
        "cumulative_regret": brain_instance.cumulative_regret,
        "last_neural_score": score.get("neural_score") if score else 0.0,
    }


@app.post("/save")
def save_brain_state(_: None = Depends(require_operator)):
    synchronizer.save_brain(brain_instance.save)
    return {"status": "saved", "path": BRAIN_STATE_PATH}


# ══════════════════════════════════════════════════════════════════════════════
# BACKUP MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/backup")
def create_backup(_: None = Depends(require_operator)):
    """Create an immediate backup of brain state and config."""
    if backup_manager is None:
        raise HTTPException(status_code=503, detail="Backup system not enabled")
    
    backup_info = backup_manager.create_backup("manual")
    if backup_info is None:
        raise HTTPException(status_code=500, detail="Backup creation failed")
    
    return {
        "status": "created",
        "path": backup_info.path,
        "timestamp": backup_info.timestamp.isoformat(),
        "files": backup_info.files,
        "size_bytes": backup_info.size_bytes,
    }


@app.get("/backups")
def list_backups(_: None = Depends(require_operator)):
    """List all available backups."""
    if backup_manager is None:
        raise HTTPException(status_code=503, detail="Backup system not enabled")
    
    backups = backup_manager.list_backups()
    return {
        "backups": [
            {
                "path": b.path,
                "timestamp": b.timestamp.isoformat(),
                "files": b.files,
                "size_bytes": b.size_bytes,
            }
            for b in sorted(backups, key=lambda x: x.timestamp, reverse=True)
        ],
        "total": len(backups),
    }


@app.post("/backup/restore")
def restore_backup(backup_path: str, _: None = Depends(require_operator)):
    """Restore the database and engine state from one of the server's backups
    (its folder name from GET /backups, or its path). A "pre-restore" backup is
    taken first, so a restore can itself be undone. The engine is reloaded
    from the restored file; nothing in memory is written over it."""
    global brain_instance
    if backup_manager is None:
        raise HTTPException(status_code=503, detail="Backup system not enabled")
    if backup_manager.resolve_backup(backup_path) is None:
        raise HTTPException(status_code=404, detail="No such backup on this server")

    if synchronizer is not None:
        synchronizer.stop_auto_save()  # so it cannot save the old engine over the restored file
    try:
        result = backup_manager.restore_backup(backup_path)
        if result is None:
            raise HTTPException(status_code=500, detail="Backup restoration failed; nothing was changed")
        if os.path.basename(BRAIN_STATE_PATH) in result["restored"]:
            brain_instance = _load_brain()
            if synchronizer is not None:
                synchronizer.set_brain(brain_instance)
    finally:
        if synchronizer is not None:
            synchronizer.start_auto_save(lambda path: brain_instance.save(path))

    logger.warning("Restored %s from backup %s (pre-restore copy: %s)",
                   ", ".join(result["restored"]), backup_path, result["pre_restore"])
    return {
        "status": "restored",
        "backup_path": backup_path,
        "restored": result["restored"],
        "pre_restore_backup": result["pre_restore"],
        "message": "Restored. Run only one API worker, or restart the others so they reload.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# DATA INGESTION
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/ingest", response_model=IngestResponse)
def ingest_data(
    request: Request,
    file: UploadFile = File(...),
    type: str = Form(...),
    school: Optional[str] = Form(None),
    school_id: Optional[str] = Form(None),
    dry_run: bool = Form(False),
    user: dict = Depends(get_current_user),
):
    """
    Ingest student roster or content catalog from CSV/Excel upload.
    
    Args:
        file: CSV or Excel file to upload
        type: "students" or "content"
        school: School name (creates if not exists)
        school_id: School ID (overrides school name)
        dry_run: If true, validate only without writing
    """
    # Validate type parameter
    if type not in ("students", "content"):
        raise HTTPException(status_code=400, detail="type must be 'students' or 'content'")
    if type == "content":
        require_operator(request)  # shared catalogue: operator only, like POST /content
    
    # Validate file extension
    filename = file.filename or "upload.csv"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail="File must be CSV or Excel (.csv, .xlsx, .xls)")
    
    if not INGEST_LIMITER.allow(user["id"]):
        raise HTTPException(status_code=429, detail="Too many uploads. Wait a few minutes and try again.")

    # A plain def endpoint runs in the worker's thread pool, so reading a
    # file never stops the API answering other schools.
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (limit 2 MB)")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
    except Exception:
        logger.exception("Could not save an upload to a temporary file")
        raise HTTPException(status_code=500, detail="Could not save the upload. Try again.")
    
    try:
        # Import ingestion functions (ingest.py is a top-level module; launch
        # contract is PYTHONPATH=<project root>. The old relative `from ...ingest`
        # raised ImportError beyond the top-level package.)
        from ingest import ingest_content, IngestFileError
        
        # Run ingestion
        if type == "students":
            if user.get("role", ROLE_ADMIN) != ROLE_ADMIN:
                raise HTTPException(status_code=403, detail="Only a school admin can import a class list")
            # Phase 2: a user can only ingest rosters into THEIR OWN school.
            # Form school/school_id overrides are rejected unless consistent.
            # NOTE: a user's stored school_id can be dangling (the user DB
            # outlives registry restores), in which case fall back to the
            # form and re-attach the resolved school to the account.
            user_school = user.get("school_id", "")
            own_school = store.get_school(user_school)
            if own_school:
                if school_id and school_id != user_school:
                    raise HTTPException(status_code=403, detail="Cannot ingest students into another school")
                if school and own_school["name"] != school.strip().upper():
                    raise HTTPException(status_code=403, detail="Cannot ingest students into another school")
                # Force-school to the caller's own school regardless of form.
                report = _ingest_roster(tmp_path, own_school, dry_run, user)
            else:
                # No school yet (or a dangling one): the roster goes into a
                # NEW school owned by the caller. A form school/school_id is
                # only a label here and can never attach them to an existing
                # school. (A dry run checks against a placeholder instead.)
                if dry_run:
                    new_school = {"school_id": "dry-run", "name": school or "MY SCHOOL", "classes": []}
                else:
                    new_school = store.create_school(school or "MY SCHOOL")
                    update_user_school(user["id"], new_school["school_id"], role=ROLE_ADMIN)
                report = _ingest_roster(tmp_path, new_school, dry_run,
                                        {**user, "school_id": new_school["school_id"], "role": ROLE_ADMIN})
        else:
            report = ingest_content(
                tmp_path, brain_instance.contents,
                dry_run=dry_run,
            )
        
        # Save if not dry run
        if not dry_run and type == "students":
            _audit(user, "import_class_list", filename[:100])
        if not dry_run:
            # Content lives in the engine state; rosters are already saved.
            synchronizer.save_brain(brain_instance.save)
        
        return IngestResponse(
            status="success" if report.errors == [] else "completed_with_errors",
            report=report.to_dict(),
        )
    except HTTPException:
        raise
    except IngestFileError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        # The exception text can name server paths and libraries; it goes to
        # the log, and the uploader gets a reference to quote.
        error_id = uuid.uuid4().hex[:12]
        logger.exception("Ingestion %s of %s (%s) failed", error_id, filename, type)
        raise HTTPException(status_code=400, detail=(
            "Could not read this file. Check it is a class list saved as .xlsx or .csv, "
            f"and try again (reference {error_id})."))
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except:
            pass


def _is_operator(request: Request) -> bool:
    try:
        require_operator(request)
        return True
    except HTTPException:
        return False


@app.get("/health")
def health_check(request: Request):
    """Liveness for anyone; version, process and backup details only with
    the operator key (they help an attacker more than a visitor)."""
    public = {
        "status": "alive",
        "engine": "GradePulse",
        # Lets the web app hide screens for features this server has switched off.
        "features": {"recommendations": RECOMMENDATIONS_ENABLED},
    }
    if not _is_operator(request):
        return public
    return {
        **public,
        "version": __version__,
        "worker_pid": os.getpid(),
        "expected_workers": int(os.getenv("WEB_CONCURRENCY", "1")),
        "backup_status": "enabled" if backup_manager is not None else "disabled",
        "backup_count": len(backup_manager.list_backups()) if backup_manager is not None else 0,
    }


@app.get("/")
def root_health_check(request: Request):
    """Root health check endpoint (backward compatible)."""
    return health_check(request)

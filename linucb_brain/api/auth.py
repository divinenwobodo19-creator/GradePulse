"""
Authentication module — JWT + bcrypt + SQLite user store.
"""
import hashlib
import json
import logging
import os
import secrets
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

DEV_SECRET = "gradepulse-dev-secret-change-in-production"
PLACEHOLDER_SECRETS = {
    DEV_SECRET,
    "change-this-to-a-strong-random-secret-in-production",
}
logger = logging.getLogger("gradepulse.auth")

# GRADEPULSE_ENV is the setting; GRADEPULPE_ENV is the old misspelt name and
# still works so existing deployments keep their production checks.
_ENV_SETTING = os.getenv("GRADEPULSE_ENV") or os.getenv("GRADEPULPE_ENV") or os.getenv("ENV") or "development"
ENV = _ENV_SETTING.strip().lower()
if os.getenv("GRADEPULPE_ENV") and not os.getenv("GRADEPULSE_ENV"):
    logger.warning("GRADEPULPE_ENV is deprecated; rename it to GRADEPULSE_ENV.")
SECRET_KEY = os.getenv("JWT_SECRET", DEV_SECRET)

# Fail fast: never boot a production process on a known/absent signing secret.
if ENV in ("production", "prod"):
    if not SECRET_KEY or SECRET_KEY in PLACEHOLDER_SECRETS or len(SECRET_KEY) < 32:
        raise RuntimeError(
            "Refusing to start in production: set JWT_SECRET to a strong "
            "random value of at least 32 characters (see .env.example)."
        )
elif SECRET_KEY in PLACEHOLDER_SECRETS:
    logger.warning(
        "Using a development/placeholder JWT secret. Set JWT_SECRET "
        "before sharing this deployment (see .env.example)."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
ISSUER = "gradepulse"
ROLE_ADMIN = "admin"      # owns the school: invites teachers, deletes classes/school
ROLE_TEACHER = "teacher"  # joined through an invite
INVITE_TTL_DAYS = 7
PASSWORD_RESET_TTL_HOURS = 24
DB_PATH = os.getenv("USER_DB_PATH", "gradepulse_users.db")

security = HTTPBearer(auto_error=False)


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            school_id TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Accounts that pre-date roles each created their own school, so they
    # become its admin.
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "role" not in columns:
        conn.execute(f"ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT '{ROLE_ADMIN}'")
    if "password_changed_at" not in columns:
        # Epoch seconds of the last password change; tokens issued before it are refused.
        conn.execute("ALTER TABLE users ADD COLUMN password_changed_at INTEGER NOT NULL DEFAULT 0")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            code_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invites (
            code TEXT PRIMARY KEY,
            school_id TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_by TEXT,
            used_at TEXT
        )
    """)
    # Classes the invited teacher is put into on joining (JSON list).
    if "class_ids" not in {row["name"] for row in conn.execute("PRAGMA table_info(invites)")}:
        conn.execute("ALTER TABLE invites ADD COLUMN class_ids TEXT NOT NULL DEFAULT '[]'")
    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode.update({
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": now,
        "jti": uuid.uuid4().hex,
        "iss": ISSUER,
        "aud": ISSUER,
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM],
            audience=ISSUER, issuer=ISSUER,
            options={"require_sub": True, "verify_iat": True},
        )
    except JWTError:
        return None
    # Reject tokens with a future iat (clock-skew slack of 30s).
    iat = payload.get("iat")
    if iat is not None:
        now = datetime.now(timezone.utc)
        max_future = int(now.timestamp()) + 30
        if int(iat) > max_future:
            return None
    return payload


def create_user(email: str, password: str) -> dict:
    email = email.lower().strip()
    conn = _get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())[:8]
    password_hash = hash_password(password)
    conn.execute(
        "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
        (user_id, email, password_hash),
    )
    conn.commit()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user)


def authenticate_user(email: str, password: str) -> Optional[dict]:
    conn = _get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
    conn.close()
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return dict(user)


def get_user_by_id(user_id: str) -> Optional[dict]:
    conn = _get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


def update_user_school(user_id: str, school_id: str, role: Optional[str] = None):
    conn = _get_db()
    if role is None:
        conn.execute("UPDATE users SET school_id = ? WHERE id = ?", (school_id, user_id))
    else:
        conn.execute("UPDATE users SET school_id = ?, role = ? WHERE id = ?", (school_id, role, user_id))
    conn.commit()
    conn.close()


# ── Passwords ──────────────────────────────────────────────────────────────

def get_user_by_email(email: str) -> Optional[dict]:
    conn = _get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
    conn.close()
    return dict(user) if user else None


def list_school_members(school_id: str) -> list:
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, email, role FROM users WHERE school_id = ? ORDER BY role, email", (school_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_password(user_id: str, password: str) -> None:
    """Store a new password. Sessions started before now stop working."""
    conn = _get_db()
    conn.execute(
        "UPDATE users SET password_hash = ?, password_changed_at = ? WHERE id = ?",
        (hash_password(password), int(datetime.now(timezone.utc).timestamp()), user_id),
    )
    conn.commit()
    conn.close()


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def create_password_reset(user_id: str, created_by: str) -> dict:
    """A single-use reset code for one account. Only its hash is stored, so
    the code is shown once, to whoever asked for it."""
    now = datetime.now(timezone.utc)
    code = secrets.token_urlsafe(24)
    expires_at = (now + timedelta(hours=PASSWORD_RESET_TTL_HOURS)).isoformat()
    conn = _get_db()
    # A new code replaces any earlier unused one for the same account.
    conn.execute("DELETE FROM password_resets WHERE user_id = ? AND used_at IS NULL", (user_id,))
    conn.execute(
        "INSERT INTO password_resets (code_hash, user_id, created_by, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
        (_hash_code(code), user_id, created_by, now.isoformat(), expires_at),
    )
    conn.commit()
    conn.close()
    return {"code": code, "expires_at": expires_at}


def redeem_password_reset(code: str, new_password: str) -> bool:
    """Set a new password with a reset code. False if the code is unknown, used or expired."""
    conn = _get_db()
    now = _now_iso()
    cur = conn.execute(
        "UPDATE password_resets SET used_at = ? WHERE code_hash = ? AND used_at IS NULL AND expires_at > ?",
        (now, _hash_code(code), now),
    )
    row = conn.execute("SELECT user_id FROM password_resets WHERE code_hash = ?", (_hash_code(code),)).fetchone()
    conn.commit()
    conn.close()
    if cur.rowcount == 0 or row is None:
        return False
    set_password(row["user_id"], new_password)
    return True


# ── Invites: the only way to join a school someone else created ────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_invite(school_id: str, created_by: str, class_ids: Optional[list] = None) -> dict:
    """A single-use invite. `class_ids` are the classes the teacher is put
    into when they join (the caller checks they belong to the school)."""
    now = datetime.now(timezone.utc)
    invite = {
        "code": secrets.token_urlsafe(9),
        "school_id": school_id,
        "created_by": created_by,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=INVITE_TTL_DAYS)).isoformat(),
        "class_ids": list(class_ids or []),
    }
    conn = _get_db()
    conn.execute(
        "INSERT INTO invites (code, school_id, created_by, created_at, expires_at, class_ids) VALUES (?, ?, ?, ?, ?, ?)",
        (*list(invite.values())[:5], json.dumps(invite["class_ids"])),
    )
    conn.commit()
    conn.close()
    return invite


def list_pending_invites(school_id: str) -> list:
    conn = _get_db()
    rows = conn.execute(
        "SELECT code, created_at, expires_at, class_ids FROM invites "
        "WHERE school_id = ? AND used_by IS NULL AND expires_at > ? ORDER BY created_at DESC",
        (school_id, _now_iso()),
    ).fetchall()
    conn.close()
    return [{**dict(r), "class_ids": json.loads(r["class_ids"] or "[]")} for r in rows]


def revoke_invite(code: str, school_id: str) -> bool:
    conn = _get_db()
    cur = conn.execute(
        "DELETE FROM invites WHERE code = ? AND school_id = ? AND used_by IS NULL", (code, school_id)
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def get_usable_invite(code: str) -> Optional[dict]:
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM invites WHERE code = ? AND used_by IS NULL AND expires_at > ?", (code, _now_iso())
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def redeem_invite(code: str, user_id: str) -> bool:
    """Mark an invite used. Single-use: False if it was taken in the meantime."""
    conn = _get_db()
    cur = conn.execute(
        "UPDATE invites SET used_by = ?, used_at = ? WHERE code = ? AND used_by IS NULL AND expires_at > ?",
        (user_id, _now_iso(), code, _now_iso()),
    )
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def _token_predates_password(payload: dict, user: dict) -> bool:
    """A password change or reset signs every earlier session out."""
    return int(payload.get("iat", 0)) < int(user.get("password_changed_at") or 0)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = get_user_by_id(payload.get("sub"))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if _token_predates_password(payload, user):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role", ROLE_ADMIN) != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Only a school admin can do this")
    return user


def optional_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[dict]:
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    user = get_user_by_id(payload.get("sub"))
    if user and _token_predates_password(payload, user):
        return None
    return user


init_db()

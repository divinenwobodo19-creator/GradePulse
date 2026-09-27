"""
Authentication module — JWT + bcrypt + SQLite user store.
"""
import os
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
ENV = os.getenv("GRADEPULPE_ENV", os.getenv("ENV", "development")).strip().lower()
SECRET_KEY = os.getenv("JWT_SECRET", DEV_SECRET)

# Fail fast: never boot a production process on a known/absent signing secret.
if ENV in ("production", "prod"):
    if not SECRET_KEY or SECRET_KEY in PLACEHOLDER_SECRETS or len(SECRET_KEY) < 32:
        raise RuntimeError(
            "Refusing to start in production: set JWT_SECRET to a strong "
            "random value of at least 32 characters (see .env.example)."
        )
elif SECRET_KEY in PLACEHOLDER_SECRETS:
    print(
        "WARNING: using a development/placeholder JWT secret. Set JWT_SECRET "
        "before sharing this deployment (see .env.example).",
        file=sys.stderr,
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
ISSUER = "gradepulse"
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
    conn = _get_db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())[:8]
    password_hash = hash_password(password)
    conn.execute(
        "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)",
        (user_id, email.lower().strip(), password_hash),
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


def update_user_school(user_id: str, school_id: str):
    conn = _get_db()
    conn.execute("UPDATE users SET school_id = ? WHERE id = ?", (school_id, user_id))
    conn.commit()
    conn.close()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = get_user_by_id(payload.get("sub"))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def optional_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[dict]:
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    return get_user_by_id(payload.get("sub"))


init_db()

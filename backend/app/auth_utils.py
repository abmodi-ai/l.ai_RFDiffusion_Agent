"""
Ligant.ai Authentication Utilities (Backend)

Core functions for password hashing (bcrypt), JWT token management,
user registration, authentication, and database session lifecycle.
"""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.db.models import User, Session as SessionModel


# ── Password helpers ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt with 12 rounds."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plain-text password against a stored bcrypt hash."""
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


# ── JWT helpers ──────────────────────────────────────────────────────────────

def create_jwt(session_token: str, user_id: str, settings) -> str:
    """Create a signed JWT embedding the session token and user identity."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": session_token,
        "user_id": str(user_id),
        "exp": now + timedelta(days=settings.JWT_EXPIRY_DAYS),
        "iat": now,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_jwt(token: str, settings) -> dict | None:
    """Decode and validate a JWT. Returns payload or None."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
        return None


# ── User registration & authentication ───────────────────────────────────────

def register_user(
    db: Session,
    email: str,
    password: str,
    display_name: str,
) -> User:
    """Register a new user account. Raises ValueError if email is taken."""
    email_lower = email.strip().lower()

    existing = db.query(User).filter(User.email_lower == email_lower).first()
    if existing is not None:
        raise ValueError(f"A user with email '{email}' already exists.")

    user = User(
        email=email.strip(),
        email_lower=email_lower,
        password_hash=hash_password(password),
        display_name=display_name.strip(),
    )
    db.add(user)
    db.flush()
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Validate email/password pair. Returns User or None."""
    email_lower = email.strip().lower()

    user = (
        db.query(User)
        .filter(User.email_lower == email_lower, User.is_active.is_(True))
        .first()
    )
    if user is None:
        return None

    if not verify_password(password, user.password_hash):
        return None

    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    return user


# ── Database session management ──────────────────────────────────────────────

def create_session(
    db: Session,
    user_id: UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> SessionModel:
    """Create a new authenticated session row with 7-day expiry."""
    token = secrets.token_hex(32)
    now = datetime.now(timezone.utc)

    session_obj = SessionModel(
        user_id=user_id,
        session_token=token,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=now + timedelta(days=7),
        last_activity=now,
    )
    db.add(session_obj)
    db.flush()
    return session_obj


def verify_session(db: Session, session_token: str) -> User | None:
    """Look up an active session by token. Returns User or None."""
    now = datetime.now(timezone.utc)

    session_obj = (
        db.query(SessionModel)
        .filter(
            SessionModel.session_token == session_token,
            SessionModel.is_revoked.is_(False),
            SessionModel.expires_at > now,
        )
        .first()
    )
    if session_obj is None:
        return None

    session_obj.last_activity = now
    db.flush()

    user = db.query(User).filter(User.id == session_obj.user_id).first()
    return user


def revoke_session(db: Session, session_token: str, user_id: UUID) -> bool:
    """Revoke an active session. Returns True if updated."""
    rows_updated = (
        db.query(SessionModel)
        .filter(
            SessionModel.session_token == session_token,
            SessionModel.user_id == user_id,
            SessionModel.is_revoked.is_(False),
        )
        .update({"is_revoked": True})
    )
    db.flush()
    return rows_updated > 0

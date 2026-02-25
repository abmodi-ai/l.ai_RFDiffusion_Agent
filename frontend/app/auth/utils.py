"""
Ligant.ai Authentication Utilities

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


# ── Password helpers ──────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """
    Hash a plain-text password using bcrypt with 12 rounds.

    Returns the hash as a UTF-8 string suitable for database storage.
    """
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.

    Returns ``True`` if the password matches, ``False`` otherwise.
    """
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


# ── JWT helpers ───────────────────────────────────────────────────────────────


def create_jwt(session_token: str, user_id: str, settings) -> str:
    """
    Create a signed JWT embedding the session token and user identity.

    Parameters
    ----------
    session_token : str
        The random hex token stored in the ``sessions`` table.
    user_id : str
        String representation of the user UUID.
    settings : Settings
        Application settings providing ``JWT_SECRET_KEY``,
        ``JWT_ALGORITHM``, and ``JWT_EXPIRY_DAYS``.

    Returns
    -------
    str
        An encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": session_token,
        "user_id": str(user_id),
        "exp": now + timedelta(days=settings.JWT_EXPIRY_DAYS),
        "iat": now,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_jwt(token: str, settings) -> dict | None:
    """
    Decode and validate a JWT.

    Returns the payload dictionary on success, or ``None`` if the token is
    expired, malformed, or has an invalid signature.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
        return None


# ── User registration & authentication ────────────────────────────────────────


def register_user(
    db: Session,
    email: str,
    password: str,
    display_name: str,
) -> User:
    """
    Register a new user account.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy session.
    email : str
        The user's email address.
    password : str
        Plain-text password (will be hashed before storage).
    display_name : str
        Human-readable name shown in the UI.

    Returns
    -------
    User
        The newly created ``User`` ORM instance.

    Raises
    ------
    ValueError
        If a user with the same normalised email already exists.
    """
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
    db.flush()  # Populate user.id before returning
    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:
    """
    Validate an email/password pair and return the corresponding user.

    On success the user's ``last_login_at`` timestamp is updated.
    Returns ``None`` if the email is not found or the password is incorrect.
    """
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


# ── Database session management ───────────────────────────────────────────────


def create_session(
    db: Session,
    user_id: UUID,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> SessionModel:
    """
    Create a new authenticated session row.

    Generates a cryptographically random 64-character hex token and stores
    it in the ``sessions`` table with a 7-day expiry window.

    Returns the newly created ``Session`` ORM instance.
    """
    token = secrets.token_hex(32)  # 64 hex characters
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


def verify_session(
    db: Session,
    session_token: str,
) -> User | None:
    """
    Look up an active (non-revoked, non-expired) session by its token.

    If valid, updates the session's ``last_activity`` timestamp and returns
    the associated ``User``.  Returns ``None`` otherwise.
    """
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

    # Eagerly load the related user
    user = db.query(User).filter(User.id == session_obj.user_id).first()
    return user


def revoke_session(
    db: Session,
    session_token: str,
    user_id: UUID,
) -> bool:
    """
    Revoke an active session.

    Sets ``is_revoked = True`` for the session matching the given token
    **and** user.  Returns ``True`` if a matching row was updated, ``False``
    otherwise.
    """
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

"""
Authentication endpoints: register, login, logout, get current user.

Rate-limited: register (5/min per IP), login (10/min per IP).
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.auth_utils import (
    authenticate_user,
    create_jwt,
    create_session,
    register_user,
)
from app.config import get_settings, Settings
from app.db.audit import log_login, log_logout, log_register
from app.db.connection import get_db_session
from app.db.models import User
from app.rate_limit import get_client_ip, login_limiter, register_limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Request / response schemas ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=128)


class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str
    display_name: Optional[str] = None


class UserResponse(BaseModel):
    user_id: str
    email: str
    display_name: Optional[str] = None
    is_admin: bool = False
    created_at: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
def register(
    body: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    """Create a new user account and return a JWT.

    Disabled during alpha launch — accounts are created manually.
    """
    raise HTTPException(
        status_code=403,
        detail="Registration is disabled during alpha launch. Please contact the team for access.",
    )


@router.post("/login", response_model=AuthResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    """Authenticate with email/password and return a JWT."""
    login_limiter.check(get_client_ip(request))

    user = authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    session_obj = create_session(db, user.id, ip_address=ip, user_agent=user_agent)
    token = create_jwt(session_obj.session_token, str(user.id), settings)

    log_login(db, user_id=user.id, ip=ip)

    return AuthResponse(
        token=token,
        user_id=str(user.id),
        email=user.email,
        display_name=user.display_name,
    )


@router.post("/logout")
def logout(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """Revoke the current session."""
    from app.db.models import Session as SessionModel
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    db.query(SessionModel).filter(
        SessionModel.user_id == user.id,
        SessionModel.is_revoked.is_(False),
        SessionModel.expires_at > now,
    ).update({"is_revoked": True})

    log_logout(db, user_id=user.id)

    return {"status": "ok", "message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_me(
    user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the current authenticated user's profile."""
    return UserResponse(
        user_id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        created_at=user.created_at.isoformat(),
    )

"""
FastAPI authentication dependencies.

Supports two authentication methods:
  1. X-API-Key header — for service-to-service calls (legacy frontend, scripts)
  2. Bearer JWT token — for React frontend user authentication
"""

from uuid import UUID

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.auth_utils import decode_jwt, verify_session
from app.db.connection import get_db_session
from app.db.models import User

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_bearer_scheme = HTTPBearer(auto_error=False)


def verify_api_key(
    api_key: str | None = Security(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Validate the X-API-Key header against the configured BACKEND_API_KEY.

    Returns the validated key on success.
    Raises:
        HTTPException 401 if the header is missing.
        HTTPException 403 if the key is incorrect.
    """
    if api_key is None:
        raise HTTPException(
            status_code=401,
            detail="Missing X-API-Key header",
        )
    if api_key != settings.BACKEND_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
        )
    return api_key


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db_session),
) -> User:
    """
    Validate a Bearer JWT token and return the authenticated ``User``.

    Raises:
        HTTPException 401 if the token is missing, expired, or invalid.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    payload = decode_jwt(credentials.credentials, settings)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    session_token = payload.get("sub")
    if not session_token:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = verify_session(db, session_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Session expired or revoked")

    return user


def verify_api_key_or_jwt(
    api_key: str | None = Security(_api_key_header),
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db_session),
) -> User | str:
    """
    Accept either X-API-Key or Bearer JWT for backwards compatibility.

    Returns a ``User`` object (JWT) or the API key string (X-API-Key).
    """
    # Try API key first
    if api_key and api_key == settings.BACKEND_API_KEY:
        return api_key

    # Try Bearer JWT
    if credentials:
        payload = decode_jwt(credentials.credentials, settings)
        if payload:
            session_token = payload.get("sub")
            if session_token:
                user = verify_session(db, session_token)
                if user:
                    return user

    raise HTTPException(status_code=401, detail="Authentication required")

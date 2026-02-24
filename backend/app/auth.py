"""
FastAPI dependency for X-API-Key header validation.
"""

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
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

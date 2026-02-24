"""
Backend configuration using pydantic-settings.

All settings can be overridden via environment variables or a .env file.
"""

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root is two levels above this file: backend/app/config.py -> project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Backend configuration for the Ligant.ai RFdiffusion server."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- Authentication ----------
    BACKEND_API_KEY: str  # required, no default

    # ---------- RFdiffusion paths ----------
    RFDIFFUSION_DIR: Path = _PROJECT_ROOT / "RFdiffusion"
    RFDIFFUSION_MODEL_DIR: Path = _PROJECT_ROOT / "RFdiffusion" / "models"
    UPLOAD_DIR: Path = _PROJECT_ROOT / "data" / "uploads"
    OUTPUT_DIR: Path = _PROJECT_ROOT / "data" / "outputs"

    # ---------- Limits ----------
    MAX_UPLOAD_SIZE_MB: int = 50
    JOB_TIMEOUT_SECS: int = 600

    # ---------- CORS ----------
    ALLOWED_ORIGINS: List[str] = ["*"]


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()

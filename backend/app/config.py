"""
Backend configuration using pydantic-settings.

All settings can be overridden via environment variables or a .env file.
"""

from pathlib import Path
from typing import List, Optional

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

    # ---------- Anthropic API ----------
    ANTHROPIC_API_KEY: str = ""

    # ---------- Google Gemini API (fallback) ----------
    GOOGLE_API_KEY: str = ""

    # ---------- RFdiffusion paths ----------
    RFDIFFUSION_DIR: Path = _PROJECT_ROOT / "RFdiffusion"
    RFDIFFUSION_MODEL_DIR: Path = _PROJECT_ROOT / "models"
    UPLOAD_DIR: Path = _PROJECT_ROOT / "data" / "uploads"
    OUTPUT_DIR: Path = _PROJECT_ROOT / "data" / "outputs"

    # ---------- Limits ----------
    MAX_UPLOAD_SIZE_MB: int = 50
    JOB_TIMEOUT_SECS: int = 600

    # ---------- CORS ----------
    ALLOWED_ORIGINS: List[str] = ["*"]

    # ---------- Database ----------
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "ligant"
    DB_PASSWORD: str = "ligant"
    DB_NAME: str = "ligant"

    # ---------- JWT ----------
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_DAYS: int = 7

    @property
    def database_url(self) -> str:
        """Build a PostgreSQL connection string for psycopg2."""
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


def get_settings() -> Settings:
    """Return a Settings instance."""
    return Settings()

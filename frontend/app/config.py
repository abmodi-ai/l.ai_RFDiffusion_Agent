"""
Ligant.ai Frontend Configuration

All frontend settings using pydantic-settings with environment variable support.
Supports both local development (psycopg2 + local PostgreSQL) and cloud
deployment (Cloud SQL Python Connector + pg8000).
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to the project root (two levels up from this file)
_THIS_DIR = Path(__file__).resolve().parent  # frontend/app/
_PROJECT_ROOT = _THIS_DIR.parent.parent      # RFdiffusion_alpha_cluade/
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
    )

    # ── Environment ──────────────────────────────────────────────────────
    ENVIRONMENT: str = "local"  # "local" or "cloud"

    # ── Anthropic / LLM ──────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str

    # ── Backend service ──────────────────────────────────────────────────
    BACKEND_URL: str = "http://localhost:8000"
    BACKEND_API_KEY: str

    # ── Database ─────────────────────────────────────────────────────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "ligant"
    DB_PASSWORD: str = "ligant_dev"
    DB_NAME: str = "ligant"

    # Cloud SQL (only used when ENVIRONMENT == "cloud")
    CLOUD_SQL_INSTANCE: Optional[str] = None

    # ── JWT / Auth ───────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_DAYS: int = 7

    # ── Session ──────────────────────────────────────────────────────────
    SESSION_COOKIE_NAME: str = "ligant_session"

    # ── Derived properties ───────────────────────────────────────────────
    @property
    def database_url(self) -> str:
        """Build a psycopg2 connection string for local development."""
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance (read once, reused everywhere)."""
    return Settings()

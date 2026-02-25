"""
FastAPI application assembly for the Ligant.ai Backend.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.services.file_manager import FileManager
from app.services.job_manager import JobManager

# Import routers
from app.routers import health, upload, jobs, pdb, auth, chat

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    settings = get_settings()

    # ---- Singleton services ----
    file_manager = FileManager(
        upload_dir=settings.UPLOAD_DIR,
        output_dir=settings.OUTPUT_DIR,
    )
    job_manager = JobManager()

    # Attach to app.state so routers can access them
    app.state.settings = settings
    app.state.file_manager = file_manager
    app.state.job_manager = job_manager

    logger.info("Ligant.ai Backend starting up")
    logger.info("  RFDIFFUSION_DIR  = %s", settings.RFDIFFUSION_DIR)
    logger.info("  UPLOAD_DIR       = %s", settings.UPLOAD_DIR)
    logger.info("  OUTPUT_DIR       = %s", settings.OUTPUT_DIR)
    logger.info("  MAX_UPLOAD_SIZE  = %d MB", settings.MAX_UPLOAD_SIZE_MB)
    logger.info("  JOB_TIMEOUT      = %d s", settings.JOB_TIMEOUT_SECS)
    logger.info("  ALLOWED_ORIGINS  = %s", settings.ALLOWED_ORIGINS)

    yield  # Application is running

    logger.info("Ligant.ai Backend shutting down")


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Ligant.ai Backend",
        description="RFdiffusion protein design backend running on DGX Spark",
        version="0.2.0",
        lifespan=lifespan,
    )

    # ---- CORS ----
    # Allow any ngrok subdomain + explicit origins from config.
    # Wildcard entries (containing *) are filtered out of the explicit list
    # since CORSMiddleware doesn't support glob patterns in allow_origins.
    explicit_origins = [
        o for o in settings.ALLOWED_ORIGINS if "*" not in o
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=explicit_origins or ["*"],
        # Match ngrok-free.app and ngrok-free.dev subdomains
        allow_origin_regex=r"https://.*\.ngrok-free\.(app|dev)",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # ---- Routers ----
    # Existing (API-key auth)
    app.include_router(health.router)
    app.include_router(upload.router)
    app.include_router(jobs.router)
    app.include_router(pdb.router)

    # New (JWT auth)
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(jobs.jobs_user_router)

    return app


# Module-level app instance for uvicorn
app = create_app()

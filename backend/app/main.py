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
from app.routers import health, upload, jobs, pdb

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
        version="0.1.0",
        lifespan=lifespan,
    )

    # ---- CORS ----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Routers ----
    app.include_router(health.router)
    app.include_router(upload.router)
    app.include_router(jobs.router)
    app.include_router(pdb.router)

    return app


# Module-level app instance for uvicorn
app = create_app()

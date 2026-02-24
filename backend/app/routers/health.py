"""
Health-check endpoint — no authentication required.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request

from app.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """
    Return system health: GPU info and RFdiffusion availability.
    """
    gpu_available = False
    gpu_name: str | None = None
    gpu_memory_gb: float | None = None

    try:
        import torch

        gpu_available = torch.cuda.is_available()
        if gpu_available:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory_gb = round(
                torch.cuda.get_device_properties(0).total_mem / (1024**3), 2
            )
    except ImportError:
        logger.warning("PyTorch not installed — GPU check skipped")
    except Exception as exc:
        logger.warning("GPU detection failed: %s", exc)

    # Check whether the RFdiffusion inference script exists
    settings = request.app.state.settings
    rfdiffusion_script = Path(settings.RFDIFFUSION_DIR) / "scripts" / "run_inference.py"
    rfdiffusion_available = rfdiffusion_script.is_file()

    return HealthResponse(
        status="ok",
        gpu_available=gpu_available,
        gpu_name=gpu_name,
        gpu_memory_gb=gpu_memory_gb,
        rfdiffusion_available=rfdiffusion_available,
    )

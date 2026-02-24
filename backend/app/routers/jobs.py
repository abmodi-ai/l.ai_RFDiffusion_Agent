"""
Job management endpoints: run RFdiffusion, check status, get results.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Request

from app.auth import verify_api_key
from app.schemas import (
    JobResults,
    JobStatus,
    RFdiffusionRequest,
    RFdiffusionResponse,
)
from app.services.rfdiffusion_runner import run_rfdiffusion

logger = logging.getLogger(__name__)
router = APIRouter(tags=["jobs"], dependencies=[Depends(verify_api_key)])


@router.post("/api/run-rfdiffusion", response_model=RFdiffusionResponse)
async def start_rfdiffusion(
    request: Request,
    body: RFdiffusionRequest,
) -> RFdiffusionResponse:
    """
    Validate input, create a job, and launch RFdiffusion as an async task.
    """
    settings = request.app.state.settings
    file_manager = request.app.state.file_manager
    job_manager = request.app.state.job_manager

    # Validate that the input PDB exists
    input_pdb_path = file_manager.get_path(body.input_pdb_id)

    # Create a job record
    params = {
        "num_designs": body.num_designs,
        "diffuser_T": body.diffuser_T,
        "hotspot_res": body.hotspot_res,
    }
    job_id = job_manager.create_job(body.input_pdb_id, body.contigs, params)

    # Create a dedicated output directory for this job
    job_output_dir = file_manager.output_dir / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)

    # Launch the runner as a fire-and-forget background task
    asyncio.create_task(
        run_rfdiffusion(
            job_id=job_id,
            input_pdb_path=input_pdb_path,
            output_dir=job_output_dir,
            contigs=body.contigs,
            num_designs=body.num_designs,
            diffuser_T=body.diffuser_T,
            hotspot_res=body.hotspot_res,
            job_manager=job_manager,
            file_manager=file_manager,
            config=settings,
        ),
        name=f"rfdiffusion-{job_id}",
    )

    logger.info("Created job %s for input %s", job_id, body.input_pdb_id)

    return RFdiffusionResponse(
        job_id=job_id,
        status="pending",
        message="Job created and queued for execution",
    )


@router.get("/api/job/{job_id}/status", response_model=JobStatus)
async def get_job_status(
    job_id: str,
    request: Request,
) -> JobStatus:
    """Return the current status of a job."""
    job_manager = request.app.state.job_manager
    status = job_manager.get_status(job_id)
    return JobStatus(**status)


@router.get("/api/job/{job_id}/results", response_model=JobResults)
async def get_job_results(
    job_id: str,
    request: Request,
) -> JobResults:
    """
    Return the output PDB file_ids for a completed job.

    Returns 400 if the job has not completed yet.
    """
    job_manager = request.app.state.job_manager
    results = job_manager.get_results(job_id)
    return JobResults(**results)

"""
Job management endpoints: run RFdiffusion, check status, get results, SSE stream.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user, verify_api_key
from app.db.connection import get_db_session
from app.db.models import Job, User
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
    """Validate input, create a job, and launch RFdiffusion as an async task."""
    settings = request.app.state.settings
    file_manager = request.app.state.file_manager
    job_manager = request.app.state.job_manager

    input_pdb_path = file_manager.get_path(body.input_pdb_id)

    params = {
        "num_designs": body.num_designs,
        "diffuser_T": body.diffuser_T,
        "hotspot_res": body.hotspot_res,
    }
    job_id = job_manager.create_job(body.input_pdb_id, body.contigs, params)

    job_output_dir = file_manager.output_dir / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)

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
async def get_job_status(job_id: str, request: Request) -> JobStatus:
    """Return the current status of a job."""
    job_manager = request.app.state.job_manager
    status = job_manager.get_status(job_id)
    return JobStatus(**status)


@router.get("/api/job/{job_id}/results", response_model=JobResults)
async def get_job_results(job_id: str, request: Request) -> JobResults:
    """Return the output PDB file_ids for a completed job."""
    job_manager = request.app.state.job_manager
    results = job_manager.get_results(job_id)
    return JobResults(**results)


@router.get("/api/job/{job_id}/stream")
async def stream_job_progress(job_id: str, request: Request):
    """
    SSE stream for real-time job progress updates.

    Events:
      - event: progress — {status, progress, message}
      - event: completed — {status, output_pdb_ids}
      - event: failed — {status, message}
    """
    job_manager = request.app.state.job_manager

    async def event_generator():
        last_progress = None
        while True:
            try:
                status = job_manager.get_status(job_id)
            except Exception:
                yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            current_status = status.get("status")
            current_progress = status.get("progress")

            # Only send if something changed
            if current_progress != last_progress or current_status in ("completed", "failed", "cancelled"):
                data = json.dumps({
                    "job_id": job_id,
                    "status": current_status,
                    "progress": current_progress,
                    "message": status.get("message"),
                })

                if current_status == "completed":
                    try:
                        results = job_manager.get_results(job_id)
                        data = json.dumps({**status, **results})
                    except Exception:
                        pass
                    yield f"event: completed\ndata: {data}\n\n"
                    break
                elif current_status in ("failed", "cancelled"):
                    yield f"event: failed\ndata: {data}\n\n"
                    break
                else:
                    yield f"event: progress\ndata: {data}\n\n"

                last_progress = current_progress

            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── User-facing job list (requires JWT auth) ────────────────────────────────

jobs_user_router = APIRouter(tags=["jobs-user"])


@jobs_user_router.get("/api/jobs")
def list_user_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    """List all jobs for the current user."""
    jobs = (
        db.query(Job)
        .filter(Job.user_id == user.id)
        .order_by(Job.created_at.desc())
        .limit(100)
        .all()
    )

    return [
        {
            "job_id": str(j.id),
            "status": j.status,
            "contigs": j.contigs,
            "num_designs": j.num_designs,
            "params": j.params,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            "duration_secs": j.duration_secs,
            "error_message": j.error_message,
            "result_summary": j.result_summary,
            "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]

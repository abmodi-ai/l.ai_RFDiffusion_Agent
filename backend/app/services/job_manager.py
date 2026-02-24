"""
Async job state manager — tracks RFdiffusion jobs in memory.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException


# Valid state transitions (from -> allowed targets)
_VALID_STATES = {"pending", "queued", "running", "completed", "failed", "cancelled"}


class JobManager:
    """In-memory job tracker for RFdiffusion runs."""

    def __init__(self) -> None:
        self._jobs: Dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_job(
        self,
        input_pdb_id: str,
        contigs: str,
        params: Dict[str, Any],
    ) -> str:
        """
        Create a new job record in 'pending' state.

        Args:
            input_pdb_id: The file_id of the input PDB.
            contigs: Contig string for RFdiffusion.
            params: Additional parameters (num_designs, diffuser_T, etc.).

        Returns:
            A unique job_id string.
        """
        job_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        self._jobs[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "progress": None,
            "message": "Job created",
            "input_pdb_id": input_pdb_id,
            "contigs": contigs,
            "params": params,
            "output_pdb_ids": [],
            "started_at": now,
            "completed_at": None,
        }
        return job_id

    def update_status(
        self,
        job_id: str,
        status: str,
        progress: Optional[float] = None,
        message: Optional[str] = None,
    ) -> None:
        """
        Update the status / progress / message of an existing job.

        Raises:
            HTTPException 404 if the job_id does not exist.
            ValueError if the status is not a valid state.
        """
        job = self._get_job(job_id)
        if status not in _VALID_STATES:
            raise ValueError(f"Invalid job status: {status}")
        job["status"] = status
        if progress is not None:
            job["progress"] = progress
        if message is not None:
            job["message"] = message
        if status in ("completed", "failed", "cancelled"):
            job["completed_at"] = datetime.now(timezone.utc).isoformat()

    def get_status(self, job_id: str) -> dict:
        """
        Return the current status payload for a job.

        Raises:
            HTTPException 404 if the job_id does not exist.
        """
        job = self._get_job(job_id)
        return {
            "job_id": job["job_id"],
            "status": job["status"],
            "progress": job["progress"],
            "message": job["message"],
            "started_at": job["started_at"],
            "completed_at": job["completed_at"],
        }

    def set_results(self, job_id: str, output_pdb_ids: list[str]) -> None:
        """
        Attach output PDB file_ids to a completed job.

        Raises:
            HTTPException 404 if the job_id does not exist.
        """
        job = self._get_job(job_id)
        job["output_pdb_ids"] = output_pdb_ids

    def get_results(self, job_id: str) -> dict:
        """
        Return the result payload for a completed job.

        Raises:
            HTTPException 404 if the job_id does not exist.
            HTTPException 400 if the job has not completed.
        """
        job = self._get_job(job_id)
        if job["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Job {job_id} is not completed (status: {job['status']})",
            )
        return {
            "job_id": job["job_id"],
            "output_pdb_ids": job["output_pdb_ids"],
            "num_designs": len(job["output_pdb_ids"]),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_job(self, job_id: str) -> dict:
        job = self._jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        return job

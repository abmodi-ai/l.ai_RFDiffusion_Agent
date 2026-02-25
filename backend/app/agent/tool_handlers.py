"""
Ligant.ai Tool Dispatch — Backend (Direct Service Calls)

Each handler corresponds to one Claude tool. Unlike the frontend version,
these handlers call services directly via ``ToolContext`` instead of making
HTTP requests back to the backend.  No Streamlit dependency.
"""

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

import httpx

from app.db.models import Job, PDBFile
from app.db.audit import (
    log_job_submitted,
    log_job_completed,
    log_pdb_uploaded,
    log_pdb_fetched,
    log_viz_viewed,
)
from app.services.pdb_analyzer import analyze_pdb

logger = logging.getLogger(__name__)

RCSB_DOWNLOAD_URL = "https://files.rcsb.org/download/{pdb_id}.pdb"


class ToolContext:
    """
    Holds references to backend services so tool handlers can call them
    directly instead of making HTTP requests.
    """

    def __init__(self, file_manager, job_manager, settings):
        self.file_manager = file_manager
        self.job_manager = job_manager
        self.settings = settings


def handle_tool_call(
    tool_name: str,
    tool_input: Dict[str, Any],
    user_id: UUID,
    ctx: ToolContext,
    db_session,
) -> str:
    """Route a Claude tool_use call to the appropriate handler."""
    dispatch = {
        "upload_pdb": _handle_upload_pdb,
        "fetch_pdb": _handle_fetch_pdb,
        "run_rfdiffusion": _handle_run_rfdiffusion,
        "check_job_status": _handle_check_job_status,
        "get_results": _handle_get_results,
        "visualize_structure": _handle_visualize_structure,
        "get_pdb_info": _handle_get_pdb_info,
    }

    handler = dispatch.get(tool_name)
    if handler is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        return handler(tool_input, user_id, ctx, db_session)
    except Exception as exc:
        logger.exception("Tool %s failed", tool_name)
        return json.dumps({"error": str(exc)})


# ── Individual handlers ──────────────────────────────────────────────────────

def _handle_upload_pdb(
    tool_input: Dict[str, Any],
    user_id: UUID,
    ctx: ToolContext,
    db,
) -> str:
    """Upload a PDB file. In backend context, the file should already be on disk."""
    filename = tool_input["filename"]

    # In the backend agent, uploaded files are stored via the upload endpoint
    # before the agent runs. This handler is a placeholder for API compatibility.
    return json.dumps({
        "error": (
            f"File '{filename}' must be uploaded via the /api/upload-pdb endpoint first. "
            "Use fetch_pdb to fetch from RCSB instead."
        )
    })


def _handle_fetch_pdb(
    tool_input: Dict[str, Any],
    user_id: UUID,
    ctx: ToolContext,
    db,
) -> str:
    """Fetch a PDB file from RCSB and register it directly."""
    pdb_id = tool_input["pdb_id"].strip().upper()

    if not re.match(r"^[0-9][A-Za-z0-9]{3}$", pdb_id):
        return json.dumps({
            "error": f"Invalid PDB ID '{pdb_id}'. Must be 4 chars: digit + 3 alphanumeric."
        })

    rcsb_url = RCSB_DOWNLOAD_URL.format(pdb_id=pdb_id)
    try:
        resp = httpx.get(rcsb_url, timeout=30)
    except httpx.RequestError as exc:
        return json.dumps({"error": f"Failed to fetch PDB {pdb_id} from RCSB: {exc}"})

    if resp.status_code == 404:
        return json.dumps({"error": f"PDB ID '{pdb_id}' not found on RCSB."})
    if resp.status_code >= 400:
        return json.dumps({"error": f"RCSB returned HTTP {resp.status_code} for '{pdb_id}'."})

    file_bytes = resp.content
    filename = f"{pdb_id}.pdb"
    checksum = hashlib.sha256(file_bytes).hexdigest()

    # Save to disk
    save_path = ctx.file_manager.upload_dir / f"{uuid.uuid4().hex}_{filename}"
    save_path.write_bytes(file_bytes)

    # Register with file manager
    backend_file_id = ctx.file_manager.register(save_path, filename)

    # Persist to DB
    pdb_file = PDBFile(
        id=uuid.UUID(backend_file_id) if len(backend_file_id) == 32 else uuid.uuid4(),
        user_id=user_id,
        filename=filename,
        original_filename=filename,
        source="rcsb_fetch",
        file_size_bytes=len(file_bytes),
        checksum_sha256=checksum,
        metadata_json={"rcsb_pdb_id": pdb_id},
    )
    db.add(pdb_file)
    log_pdb_fetched(db, user_id=user_id, file_id=pdb_file.id,
                    pdb_id=pdb_id, filename=filename)
    db.flush()

    return json.dumps({
        "status": "success",
        "file_id": backend_file_id,
        "pdb_id": pdb_id,
        "filename": filename,
        "file_size_bytes": len(file_bytes),
        "message": f"PDB '{pdb_id}' fetched from RCSB ({len(file_bytes):,} bytes).",
    })


def _handle_run_rfdiffusion(
    tool_input: Dict[str, Any],
    user_id: UUID,
    ctx: ToolContext,
    db,
) -> str:
    """Submit an RFdiffusion job directly through the job manager."""
    import asyncio

    input_pdb_id = tool_input["input_pdb_id"]
    contigs = tool_input["contigs"]
    num_designs = tool_input.get("num_designs", 1)
    diffuser_T = tool_input.get("diffuser_T", 50)
    hotspot_res = tool_input.get("hotspot_res")

    # Validate input PDB exists
    input_pdb_path = ctx.file_manager.get_path(input_pdb_id)

    params = {
        "num_designs": num_designs,
        "diffuser_T": diffuser_T,
        "hotspot_res": hotspot_res,
    }
    backend_job_id = ctx.job_manager.create_job(input_pdb_id, contigs, params)

    # Create output directory
    job_output_dir = ctx.file_manager.output_dir / backend_job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)

    # Persist job row in DB
    job = Job(
        user_id=user_id,
        status="queued",
        input_pdb_id=uuid.UUID(input_pdb_id) if len(input_pdb_id) == 32 else None,
        contigs=contigs,
        params=params,
        backend_job_id=backend_job_id,
        num_designs=num_designs,
    )
    db.add(job)
    db.flush()
    log_job_submitted(db, user_id=user_id, job_id=job.id, params=params)

    local_job_id = str(job.id)

    # Launch the runner as a background task
    from app.services.rfdiffusion_runner import run_rfdiffusion

    loop = asyncio.get_event_loop()
    loop.create_task(
        run_rfdiffusion(
            job_id=backend_job_id,
            input_pdb_path=input_pdb_path,
            output_dir=job_output_dir,
            contigs=contigs,
            num_designs=num_designs,
            diffuser_T=diffuser_T,
            hotspot_res=hotspot_res,
            job_manager=ctx.job_manager,
            file_manager=ctx.file_manager,
            config=ctx.settings,
        ),
        name=f"rfdiffusion-{backend_job_id}",
    )

    return json.dumps({
        "status": "queued",
        "job_id": local_job_id,
        "backend_job_id": backend_job_id,
        "num_designs": num_designs,
        "diffuser_T": diffuser_T,
        "contigs": contigs,
        "message": (
            f"RFdiffusion job submitted. Generating {num_designs} design(s) "
            f"with {diffuser_T} timesteps. Job ID: '{local_job_id}'."
        ),
        "IMPORTANT_INSTRUCTION": (
            "DO NOT call check_job_status to poll. Tell the user the job has "
            "been submitted and they can ask for a status update later."
        ),
    })


def _handle_check_job_status(
    tool_input: Dict[str, Any],
    user_id: UUID,
    ctx: ToolContext,
    db,
) -> str:
    """Check job status directly from the job manager."""
    job_id = tool_input["job_id"]

    # Look up backend_job_id from DB
    job = db.query(Job).filter(
        Job.id == uuid.UUID(job_id),
        Job.user_id == user_id,
    ).first()

    if job is None:
        return json.dumps({"error": f"Job '{job_id}' not found."})

    backend_id = job.backend_job_id or job_id
    status_data = ctx.job_manager.get_status(backend_id)

    new_status = status_data.get("status", "unknown")

    # Update local DB
    job.status = new_status
    if new_status == "completed" and job.completed_at is None:
        job.completed_at = datetime.now(timezone.utc)
        if job.started_at:
            job.duration_secs = (job.completed_at - job.started_at).total_seconds()
        log_job_completed(db, user_id=user_id, job_id=job.id,
                          summary={"status": new_status})
    elif new_status == "running" and job.started_at is None:
        job.started_at = datetime.now(timezone.utc)
    elif new_status == "failed":
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = status_data.get("message")
        log_job_completed(db, user_id=user_id, job_id=job.id,
                          summary={"status": "failed", "error": job.error_message})
    db.flush()

    result: Dict[str, Any] = {"job_id": job_id, "status": new_status}
    if status_data.get("progress") is not None:
        result["progress"] = status_data["progress"]
    if new_status == "completed":
        result["message"] = "Job completed! Use get_results to retrieve designs."
    elif new_status == "running":
        result["message"] = f"Running. Progress: {status_data.get('progress', '?')}."
    elif new_status == "failed":
        result["message"] = f"Failed: {status_data.get('message', 'unknown')}"
    else:
        result["message"] = f"Status: {new_status}"

    return json.dumps(result)


def _handle_get_results(
    tool_input: Dict[str, Any],
    user_id: UUID,
    ctx: ToolContext,
    db,
) -> str:
    """Retrieve output PDB files from a completed job."""
    job_id = tool_input["job_id"]

    job = db.query(Job).filter(
        Job.id == uuid.UUID(job_id),
        Job.user_id == user_id,
    ).first()

    if job is None:
        return json.dumps({"error": f"Job '{job_id}' not found."})

    backend_id = job.backend_job_id or job_id
    results = ctx.job_manager.get_results(backend_id)

    output_pdb_ids = results.get("output_pdb_ids", [])

    # Register in DB
    registered_ids = []
    for fid in output_pdb_ids:
        existing = db.query(PDBFile).filter(PDBFile.id == uuid.UUID(fid) if len(fid) == 32 else None).first()
        if existing is None:
            info = ctx.file_manager.get_info(fid)
            pdb_file = PDBFile(
                user_id=user_id,
                filename=info.get("filename", f"design_{fid}.pdb"),
                original_filename=info.get("filename", f"design_{fid}.pdb"),
                source="rfdiffusion_output",
                file_size_bytes=info.get("size_bytes"),
                job_id=uuid.UUID(job_id),
            )
            db.add(pdb_file)
        registered_ids.append(fid)

    job.result_summary = {"num_output_files": len(registered_ids), "file_ids": registered_ids}
    db.flush()

    return json.dumps({
        "status": "success",
        "job_id": job_id,
        "num_files": len(registered_ids),
        "file_ids": registered_ids,
        "message": f"Retrieved {len(registered_ids)} designed binder structure(s).",
    })


def _handle_visualize_structure(
    tool_input: Dict[str, Any],
    user_id: UUID,
    ctx: ToolContext,
    db,
) -> str:
    """Fetch PDB contents and return them for the frontend viewer."""
    file_ids = tool_input["file_ids"]
    style = tool_input.get("style", "cartoon")
    color_by = tool_input.get("color_by", "chain")
    label = tool_input.get("label", "")

    pdb_contents = {}
    for fid in file_ids:
        path = ctx.file_manager.get_path(fid)
        pdb_contents[fid] = path.read_text()

    # Audit log
    for fid in file_ids:
        log_viz_viewed(db, user_id=user_id, file_id=uuid.UUID(fid) if len(fid) == 32 else uuid.uuid4())
    db.flush()

    return json.dumps({
        "status": "success",
        "num_structures": len(file_ids),
        "style": style,
        "color_by": color_by,
        "pdb_contents": pdb_contents,
        "message": f"Prepared {len(file_ids)} structure(s) for visualization.",
    })


def _handle_get_pdb_info(
    tool_input: Dict[str, Any],
    user_id: UUID,
    ctx: ToolContext,
    db,
) -> str:
    """Get structural metadata by calling the PDB analyzer directly."""
    file_id = tool_input["file_id"]

    path = ctx.file_manager.get_path(file_id)
    info = ctx.file_manager.get_info(file_id)
    analysis = analyze_pdb(path)

    chains = analysis.get("chains", [])
    chain_details = []
    for chain in chains:
        cid = chain.get("chain_id", "?")
        n_res = chain.get("num_residues", "?")
        first = chain.get("residue_start", "?")
        last = chain.get("residue_end", "?")
        chain_details.append(f"  Chain {cid}: {n_res} residues ({first}-{last})")

    summary = (
        f"PDB {file_id}:\n"
        f"  Chains: {analysis.get('num_chains', '?')}\n"
        f"  Residues: {analysis.get('total_residues', '?')}\n"
        f"  Atoms: {analysis.get('total_atoms', '?')}\n"
        + "\n".join(chain_details)
    )

    return json.dumps({
        "file_id": file_id,
        "summary": summary,
        "details": {**info, **analysis},
    })

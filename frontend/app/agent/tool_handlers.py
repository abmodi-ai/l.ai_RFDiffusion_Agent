"""
Ligant.ai Tool Dispatch & Backend Communication

Each handler corresponds to one Claude tool.  When Claude emits a tool_use
block the ``handle_tool_call`` dispatcher routes it to the correct handler,
which in turn calls the FastAPI backend over HTTP and persists state in the
PostgreSQL database via SQLAlchemy.
"""

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
import streamlit as st

from app.config import get_settings
from app.db.connection import get_db
from app.db.models import Job, PDBFile
from app.db.audit import (
    log_job_submitted,
    log_job_completed,
    log_pdb_uploaded,
    log_pdb_fetched,
    log_viz_viewed,
)

logger = logging.getLogger(__name__)

RCSB_DOWNLOAD_URL = "https://files.rcsb.org/download/{pdb_id}.pdb"

# ── Helper: backend HTTP request ─────────────────────────────────────────────

def _backend_request(
    method: str,
    path: str,
    **kwargs: Any,
) -> requests.Response:
    """
    Make an authenticated HTTP request to the FastAPI backend.

    Automatically prepends the backend base URL, injects the API key header,
    and raises a readable error on non-2xx responses.

    Parameters
    ----------
    method : str
        HTTP method (``"GET"``, ``"POST"``, etc.).
    path : str
        URL path relative to the backend root (e.g. ``"/api/upload-pdb"``).
    **kwargs
        Forwarded to ``requests.request`` (``json``, ``files``, ``params``...).

    Returns
    -------
    requests.Response
        The response object on success.

    Raises
    ------
    RuntimeError
        When the backend returns a non-2xx status code.
    """
    settings = get_settings()
    url = f"{settings.BACKEND_URL.rstrip('/')}{path}"

    headers = kwargs.pop("headers", {})
    headers["X-API-Key"] = settings.BACKEND_API_KEY

    timeout = kwargs.pop("timeout", 30)

    response = requests.request(
        method,
        url,
        headers=headers,
        timeout=timeout,
        **kwargs,
    )

    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except (ValueError, AttributeError):
            detail = response.text
        raise RuntimeError(
            f"Backend {method} {path} failed ({response.status_code}): {detail}"
        )

    return response


# ── Public dispatcher ─────────────────────────────────────────────────────────

def handle_tool_call(
    tool_name: str,
    tool_input: Dict[str, Any],
    user_id: uuid.UUID,
) -> str:
    """
    Route a Claude tool_use call to the appropriate handler.

    Returns a JSON-encoded string that will be sent back to Claude as the
    ``tool_result`` content.
    """
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
        return handler(tool_input, user_id)
    except RuntimeError as exc:
        logger.exception("Tool %s failed", tool_name)
        return json.dumps({"error": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error in tool %s", tool_name)
        return json.dumps({"error": f"Internal error: {exc}"})


# ── Individual handlers ──────────────────────────────────────────────────────

def _handle_upload_pdb(
    tool_input: Dict[str, Any],
    user_id: uuid.UUID,
) -> str:
    """Upload a PDB file from the Streamlit session to the backend."""

    filename = tool_input["filename"]

    # Retrieve the file bytes from the Streamlit session state
    uploaded_files: Dict[str, Any] = st.session_state.get("uploaded_files", {})
    file_data = uploaded_files.get(filename)
    if file_data is None:
        return json.dumps({
            "error": (
                f"File '{filename}' not found in session. "
                f"Available files: {list(uploaded_files.keys())}"
            )
        })

    # If file_data is a Streamlit UploadedFile, read its bytes; otherwise
    # assume it is already bytes.
    if hasattr(file_data, "read"):
        file_bytes = file_data.read()
        # Reset the read pointer so the file can be re-read if needed.
        file_data.seek(0)
    else:
        file_bytes = file_data

    # POST to the backend
    resp = _backend_request(
        "POST",
        "/api/upload-pdb",
        files={"file": (filename, file_bytes, "chemical/x-pdb")},
    )
    data = resp.json()

    backend_file_id = data.get("file_id") or data.get("id")
    file_size = data.get("file_size_bytes", len(file_bytes))
    checksum = data.get("checksum_sha256")

    # Persist to local DB
    with get_db() as db:
        pdb_file = PDBFile(
            id=uuid.UUID(backend_file_id) if backend_file_id else uuid.uuid4(),
            user_id=user_id,
            filename=data.get("filename", filename),
            original_filename=filename,
            source="upload",
            file_size_bytes=file_size,
            checksum_sha256=checksum,
        )
        db.add(pdb_file)
        log_pdb_uploaded(db, user_id=user_id, file_id=pdb_file.id, filename=filename)

    # Return the backend's original hex file_id so subsequent tool calls
    # (get_pdb_info, visualize_structure, run_rfdiffusion) can use it
    # directly against the backend API.  uuid.UUID() accepts both formats.
    return json.dumps({
        "status": "success",
        "file_id": backend_file_id,
        "filename": filename,
        "file_size_bytes": file_size,
        "message": f"PDB file '{filename}' uploaded successfully.",
    })


def _handle_fetch_pdb(
    tool_input: Dict[str, Any],
    user_id: uuid.UUID,
) -> str:
    """Fetch a PDB file from RCSB by PDB ID and upload it to the backend."""

    pdb_id = tool_input["pdb_id"].strip().upper()

    # Validate PDB ID format: starts with a digit, followed by 3 alphanumeric chars
    if not re.match(r"^[0-9][A-Za-z0-9]{3}$", pdb_id):
        return json.dumps({
            "error": (
                f"Invalid PDB ID '{pdb_id}'. "
                "PDB IDs must be 4 characters: a digit followed by 3 alphanumeric characters "
                "(e.g., '6AL5', '1BRS')."
            )
        })

    # Fetch from RCSB
    rcsb_url = RCSB_DOWNLOAD_URL.format(pdb_id=pdb_id)
    try:
        rcsb_resp = requests.get(rcsb_url, timeout=30)
    except requests.exceptions.RequestException as exc:
        return json.dumps({
            "error": f"Failed to fetch PDB {pdb_id} from RCSB: {exc}"
        })

    if rcsb_resp.status_code == 404:
        return json.dumps({
            "error": (
                f"PDB ID '{pdb_id}' not found on RCSB. "
                "Please verify the PDB ID is correct."
            )
        })
    if not rcsb_resp.ok:
        return json.dumps({
            "error": (
                f"RCSB returned HTTP {rcsb_resp.status_code} for PDB ID '{pdb_id}'."
            )
        })

    file_bytes = rcsb_resp.content
    filename = f"{pdb_id}.pdb"

    # Upload to backend via existing endpoint
    resp = _backend_request(
        "POST",
        "/api/upload-pdb",
        files={"file": (filename, file_bytes, "chemical/x-pdb")},
    )
    data = resp.json()

    backend_file_id = data.get("file_id") or data.get("id")
    file_size = data.get("file_size_bytes", len(file_bytes))
    checksum = data.get("checksum_sha256") or hashlib.sha256(file_bytes).hexdigest()

    # Persist to local DB
    with get_db() as db:
        pdb_file = PDBFile(
            id=uuid.UUID(backend_file_id) if backend_file_id else uuid.uuid4(),
            user_id=user_id,
            filename=data.get("filename", filename),
            original_filename=filename,
            source="rcsb_fetch",
            file_size_bytes=file_size,
            checksum_sha256=checksum,
            metadata_json={"rcsb_pdb_id": pdb_id},
        )
        db.add(pdb_file)
        log_pdb_fetched(
            db, user_id=user_id, file_id=pdb_file.id,
            pdb_id=pdb_id, filename=filename,
        )

    # Store in session state so sidebar/UI picks it up
    if "uploaded_files" not in st.session_state:
        st.session_state["uploaded_files"] = {}
    st.session_state["uploaded_files"][filename] = file_bytes

    # Return the backend's original hex file_id so subsequent tool calls
    # can use it directly against the backend API.
    return json.dumps({
        "status": "success",
        "file_id": backend_file_id,
        "pdb_id": pdb_id,
        "filename": filename,
        "file_size_bytes": file_size,
        "message": (
            f"PDB structure '{pdb_id}' fetched from RCSB and uploaded successfully "
            f"({file_size:,} bytes)."
        ),
    })


def _handle_run_rfdiffusion(
    tool_input: Dict[str, Any],
    user_id: uuid.UUID,
) -> str:
    """Submit an RFdiffusion job to the backend."""

    payload = {
        "input_pdb_id": tool_input["input_pdb_id"],
        "contigs": tool_input["contigs"],
        "num_designs": tool_input.get("num_designs", 1),
        "diffuser_T": tool_input.get("diffuser_T", 50),
    }
    if "hotspot_res" in tool_input:
        payload["hotspot_res"] = tool_input["hotspot_res"]

    resp = _backend_request(
        "POST",
        "/api/run-rfdiffusion",
        json=payload,
    )
    data = resp.json()

    backend_job_id = data.get("job_id") or data.get("id")

    # Persist job row in local DB
    with get_db() as db:
        job = Job(
            user_id=user_id,
            status="queued",
            input_pdb_id=uuid.UUID(tool_input["input_pdb_id"]),
            contigs=tool_input["contigs"],
            params={
                "num_designs": payload["num_designs"],
                "diffuser_T": payload["diffuser_T"],
                "hotspot_res": tool_input.get("hotspot_res"),
            },
            backend_job_id=str(backend_job_id),
            num_designs=payload["num_designs"],
        )
        db.add(job)
        db.flush()  # populate job.id before audit log
        log_job_submitted(db, user_id=user_id, job_id=job.id, params=job.params)
        local_job_id = str(job.id)

    return json.dumps({
        "status": "queued",
        "job_id": local_job_id,
        "backend_job_id": str(backend_job_id),
        "num_designs": payload["num_designs"],
        "diffuser_T": payload["diffuser_T"],
        "contigs": tool_input["contigs"],
        "message": (
            f"RFdiffusion job submitted successfully. "
            f"Generating {payload['num_designs']} design(s) with "
            f"{payload['diffuser_T']} diffusion timesteps. "
            f"Job ID: '{local_job_id}'."
        ),
        "IMPORTANT_INSTRUCTION": (
            "DO NOT call check_job_status to poll for this job. "
            "RFdiffusion jobs take several minutes. Tell the user the job has "
            "been submitted and that they can ask you to check its status later. "
            "Only call check_job_status if the user explicitly asks for a status "
            "update. Never poll in a loop."
        ),
    })


def _handle_check_job_status(
    tool_input: Dict[str, Any],
    user_id: uuid.UUID,
) -> str:
    """Poll the backend for the current status of a job."""

    job_id = tool_input["job_id"]

    # Look up the backend_job_id from our local DB
    with get_db() as db:
        job = db.query(Job).filter(
            Job.id == uuid.UUID(job_id),
            Job.user_id == user_id,
        ).first()

    if job is None:
        return json.dumps({"error": f"Job '{job_id}' not found."})

    backend_id = job.backend_job_id or job_id

    resp = _backend_request("GET", f"/api/job/{backend_id}/status")
    data = resp.json()

    new_status = data.get("status", "unknown")
    progress = data.get("progress")
    error_message = data.get("error_message")

    # Update local DB
    with get_db() as db:
        job = db.query(Job).filter(Job.id == uuid.UUID(job_id)).first()
        if job is not None:
            job.status = new_status
            if error_message:
                job.error_message = error_message
            if new_status == "completed":
                job.completed_at = datetime.now(timezone.utc)
                if job.started_at:
                    job.duration_secs = (
                        job.completed_at - job.started_at
                    ).total_seconds()
                elif data.get("duration_secs"):
                    job.duration_secs = data["duration_secs"]
                log_job_completed(
                    db,
                    user_id=user_id,
                    job_id=job.id,
                    summary={"status": new_status},
                )
            elif new_status == "running" and job.started_at is None:
                job.started_at = datetime.now(timezone.utc)
            elif new_status == "failed":
                job.completed_at = datetime.now(timezone.utc)
                log_job_completed(
                    db,
                    user_id=user_id,
                    job_id=job.id,
                    summary={"status": "failed", "error": error_message},
                )

    result: Dict[str, Any] = {
        "job_id": job_id,
        "status": new_status,
    }
    if progress is not None:
        result["progress"] = progress
    if error_message:
        result["error_message"] = error_message
    if new_status == "completed":
        result["message"] = (
            "Job completed successfully! Use get_results to retrieve "
            "the designed binder PDB files."
        )
    elif new_status == "running":
        result["message"] = "Job is currently running."
        if progress is not None:
            result["message"] += f" Progress: {progress}%."
    elif new_status == "failed":
        result["message"] = f"Job failed: {error_message or 'unknown error'}"
    else:
        result["message"] = f"Job status: {new_status}"

    return json.dumps(result)


def _handle_get_results(
    tool_input: Dict[str, Any],
    user_id: uuid.UUID,
) -> str:
    """Retrieve output PDB files from a completed job."""

    job_id = tool_input["job_id"]

    # Look up backend_job_id
    with get_db() as db:
        job = db.query(Job).filter(
            Job.id == uuid.UUID(job_id),
            Job.user_id == user_id,
        ).first()

    if job is None:
        return json.dumps({"error": f"Job '{job_id}' not found."})

    backend_id = job.backend_job_id or job_id

    resp = _backend_request("GET", f"/api/job/{backend_id}/results")
    data = resp.json()

    output_files = data.get("files", data.get("output_files", []))

    registered_ids = []
    with get_db() as db:
        for f in output_files:
            file_id_str = f.get("file_id") or f.get("id")
            file_id = uuid.UUID(file_id_str) if file_id_str else uuid.uuid4()

            # Avoid duplicates
            existing = db.query(PDBFile).filter(PDBFile.id == file_id).first()
            if existing is None:
                pdb_file = PDBFile(
                    id=file_id,
                    user_id=user_id,
                    filename=f.get("filename", f"design_{file_id}.pdb"),
                    original_filename=f.get(
                        "original_filename",
                        f.get("filename", f"design_{file_id}.pdb"),
                    ),
                    source="rfdiffusion_output",
                    file_size_bytes=f.get("file_size_bytes"),
                    job_id=uuid.UUID(job_id),
                )
                db.add(pdb_file)
            registered_ids.append(str(file_id))

        # Update job result summary
        job_row = db.query(Job).filter(Job.id == uuid.UUID(job_id)).first()
        if job_row is not None:
            job_row.result_summary = {
                "num_output_files": len(registered_ids),
                "file_ids": registered_ids,
            }

    return json.dumps({
        "status": "success",
        "job_id": job_id,
        "num_files": len(registered_ids),
        "file_ids": registered_ids,
        "message": (
            f"Retrieved {len(registered_ids)} designed binder structure(s). "
            f"Use visualize_structure with these file IDs to view the results, "
            f"or get_pdb_info to inspect individual structures."
        ),
    })


def _handle_visualize_structure(
    tool_input: Dict[str, Any],
    user_id: uuid.UUID,
) -> str:
    """Fetch PDB contents and stage them for rendering in the Streamlit UI."""

    file_ids = tool_input["file_ids"]
    style = tool_input.get("style", "cartoon")
    color_by = tool_input.get("color_by", "chain")
    label = tool_input.get("label", "")

    pdb_contents = {}
    for fid in file_ids:
        resp = _backend_request("GET", f"/api/pdb/{fid}/content")
        # The response may be raw PDB text or JSON-wrapped
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            pdb_text = resp.json().get("content", resp.text)
        else:
            pdb_text = resp.text
        pdb_contents[fid] = pdb_text

    # Store in session state for the Streamlit UI layer to pick up
    if "pending_visualizations" not in st.session_state:
        st.session_state["pending_visualizations"] = []

    st.session_state["pending_visualizations"].append({
        "file_ids": file_ids,
        "pdb_contents": pdb_contents,
        "style": style,
        "color_by": color_by,
        "label": label,
    })

    # Audit log
    with get_db() as db:
        for fid in file_ids:
            log_viz_viewed(db, user_id=user_id, file_id=uuid.UUID(fid))

    return json.dumps({
        "status": "success",
        "num_structures": len(file_ids),
        "style": style,
        "color_by": color_by,
        "message": (
            f"Prepared {len(file_ids)} structure(s) for 3D visualization "
            f"(style={style}, colored by {color_by}). "
            f"The visualization will render in the chat window."
        ),
    })


def _handle_get_pdb_info(
    tool_input: Dict[str, Any],
    user_id: uuid.UUID,
) -> str:
    """Retrieve structural metadata about a PDB file from the backend."""

    file_id = tool_input["file_id"]

    resp = _backend_request("GET", f"/api/pdb/{file_id}/info")
    data = resp.json()

    # Build a human-readable summary alongside the raw data
    chains = data.get("chains", [])
    total_residues = data.get("total_residues", "N/A")
    total_atoms = data.get("total_atoms", "N/A")

    chain_details = []
    for chain in chains:
        chain_id = chain.get("chain_id", "?")
        n_res = chain.get("num_residues", "?")
        first = chain.get("first_residue", "?")
        last = chain.get("last_residue", "?")
        chain_details.append(
            f"  Chain {chain_id}: {n_res} residues (range {first}-{last})"
        )

    summary = (
        f"PDB file {file_id}:\n"
        f"  Total chains: {len(chains)}\n"
        f"  Total residues: {total_residues}\n"
        f"  Total atoms: {total_atoms}\n"
    )
    if chain_details:
        summary += "\n".join(chain_details)

    return json.dumps({
        "file_id": file_id,
        "summary": summary,
        "details": data,
    })

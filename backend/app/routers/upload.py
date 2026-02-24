"""
PDB file upload endpoint.
"""

from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File

from app.auth import verify_api_key
from app.schemas import UploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["upload"], dependencies=[Depends(verify_api_key)])


@router.post("/api/upload-pdb", response_model=UploadResponse)
async def upload_pdb(
    request: Request,
    file: UploadFile = File(...),
) -> UploadResponse:
    """
    Accept a multipart PDB file upload, validate, save, and register it.
    """
    settings = request.app.state.settings
    file_manager = request.app.state.file_manager

    # ---- Validate filename extension ----
    original_filename = file.filename or "unknown.pdb"
    if not original_filename.lower().endswith(".pdb"):
        raise HTTPException(
            status_code=400,
            detail="Only .pdb files are accepted",
        )

    # ---- Read and validate size ----
    contents = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB} MB",
        )

    # ---- Save to upload directory with UUID prefix ----
    safe_name = f"{uuid.uuid4().hex}_{original_filename}"
    dest = file_manager.upload_dir / safe_name
    dest.write_bytes(contents)

    # ---- Register with FileManager ----
    file_id = file_manager.register(dest, original_filename)

    logger.info(
        "Uploaded %s (%d bytes) -> file_id=%s",
        original_filename,
        len(contents),
        file_id,
    )

    return UploadResponse(
        file_id=file_id,
        filename=original_filename,
        size_bytes=len(contents),
    )

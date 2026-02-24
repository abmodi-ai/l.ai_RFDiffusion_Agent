"""
PDB content and analysis endpoints.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from app.auth import verify_api_key
from app.schemas import PDBInfo
from app.services.pdb_analyzer import analyze_pdb

logger = logging.getLogger(__name__)
router = APIRouter(tags=["pdb"], dependencies=[Depends(verify_api_key)])


@router.get("/api/pdb/{file_id}/content", response_class=PlainTextResponse)
async def get_pdb_content(
    file_id: str,
    request: Request,
) -> PlainTextResponse:
    """Return the raw PDB file content as text/plain."""
    file_manager = request.app.state.file_manager
    path = file_manager.get_path(file_id)
    content = path.read_text(encoding="utf-8", errors="replace")
    return PlainTextResponse(content, media_type="text/plain")


@router.get("/api/pdb/{file_id}/info", response_model=PDBInfo)
async def get_pdb_info(
    file_id: str,
    request: Request,
) -> PDBInfo:
    """Analyze a PDB file and return structural metadata."""
    file_manager = request.app.state.file_manager
    path = file_manager.get_path(file_id)
    info = file_manager.get_info(file_id)

    analysis = analyze_pdb(path)

    return PDBInfo(
        file_id=file_id,
        filename=info["filename"],
        num_chains=analysis["num_chains"],
        chains=analysis["chains"],
        total_residues=analysis["total_residues"],
        total_atoms=analysis["total_atoms"],
    )

"""
Pydantic models for request / response validation.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---- Upload ----

class UploadResponse(BaseModel):
    file_id: str
    filename: str
    size_bytes: int


# ---- RFdiffusion ----

class RFdiffusionRequest(BaseModel):
    input_pdb_id: str = Field(..., description="file_id of the uploaded PDB")
    contigs: str = Field(..., description="Contig string for RFdiffusion, e.g. 'A1-50/0 50-100'")
    num_designs: int = Field(default=1, ge=1, le=100)
    diffuser_T: int = Field(default=50, ge=1, le=500)
    hotspot_res: Optional[list[str]] = Field(
        default=None,
        description="Optional list of hotspot residues, e.g. ['A30', 'A33']",
    )


class RFdiffusionResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ---- Jobs ----

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: Optional[float] = None
    message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class JobResults(BaseModel):
    job_id: str
    output_pdb_ids: list[str]
    num_designs: int


# ---- PDB analysis ----

class PDBInfo(BaseModel):
    file_id: str
    filename: str
    num_chains: int
    chains: list[dict]
    total_residues: int
    total_atoms: int


# ---- Health ----

class HealthResponse(BaseModel):
    status: str
    gpu_available: bool
    gpu_name: Optional[str] = None
    gpu_memory_gb: Optional[float] = None
    rfdiffusion_available: bool

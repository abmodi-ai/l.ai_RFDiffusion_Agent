"""
Async subprocess runner for RFdiffusion inference.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.config import Settings
    from app.services.file_manager import FileManager
    from app.services.job_manager import JobManager

logger = logging.getLogger(__name__)


async def run_rfdiffusion(
    job_id: str,
    input_pdb_path: Path,
    output_dir: Path,
    contigs: str,
    num_designs: int,
    diffuser_T: int,
    hotspot_res: Optional[list[str]],
    job_manager: "JobManager",
    file_manager: "FileManager",
    config: "Settings",
) -> None:
    """
    Launch RFdiffusion as an async subprocess and track progress.

    This function is designed to be fired off as a background task via
    ``asyncio.create_task``.  It updates job_manager in-place so that the
    status / results endpoints can report progress.

    Args:
        job_id: Unique job identifier.
        input_pdb_path: Path to the input PDB file.
        output_dir: Directory where outputs for this job will be written.
        contigs: Contig specification string.
        num_designs: Number of designs to generate.
        diffuser_T: Number of diffusion timesteps.
        hotspot_res: Optional list of hotspot residues.
        job_manager: Shared JobManager instance.
        file_manager: Shared FileManager instance.
        config: Application settings.
    """
    rfdiffusion_dir = config.RFDIFFUSION_DIR
    model_dir = config.RFDIFFUSION_MODEL_DIR

    # Build the output prefix for this job
    output_prefix = output_dir / "design"

    # Assemble command arguments (NO shell=True to prevent injection)
    cmd = [
        "python3",
        str(rfdiffusion_dir / "scripts" / "run_inference.py"),
        f"inference.output_prefix={output_prefix}",
        f"inference.input_pdb={input_pdb_path}",
        f"contigmap.contigs=[{contigs}]",
        f"inference.num_designs={num_designs}",
        f"diffuser.T={diffuser_T}",
        f"inference.model_directory_path={model_dir}",
    ]

    if hotspot_res:
        hotspot_str = ",".join(hotspot_res)
        cmd.append(f"ppi.hotspot_res=[{hotspot_str}]")

    logger.info("Starting RFdiffusion for job %s: %s", job_id, " ".join(cmd))
    job_manager.update_status(job_id, "running", progress=0.0, message="RFdiffusion started")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(rfdiffusion_dir),
        )

        # Read stdout line-by-line for progress monitoring
        assert process.stdout is not None
        timestep_pattern = re.compile(r"Timestep\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)

        async def _read_output() -> str:
            lines: list[str] = []
            async for raw_line in process.stdout:  # type: ignore[union-attr]
                line = raw_line.decode("utf-8", errors="replace").rstrip()
                lines.append(line)
                logger.debug("[job %s] %s", job_id, line)

                # Try to extract progress from "Timestep X/Y" lines
                match = timestep_pattern.search(line)
                if match:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    if total > 0:
                        progress = round(current / total, 3)
                        job_manager.update_status(
                            job_id,
                            "running",
                            progress=progress,
                            message=f"Timestep {current}/{total}",
                        )
            return "\n".join(lines)

        # Apply timeout
        full_output = await asyncio.wait_for(
            _read_output(),
            timeout=config.JOB_TIMEOUT_SECS,
        )

        # Wait for process to exit
        return_code = await asyncio.wait_for(
            process.wait(),
            timeout=30,  # short grace period after output is done
        )

        if return_code != 0:
            # Extract last few lines for the error message
            tail = "\n".join(full_output.splitlines()[-10:])
            job_manager.update_status(
                job_id,
                "failed",
                progress=None,
                message=f"RFdiffusion exited with code {return_code}.\n{tail}",
            )
            logger.error("Job %s failed (exit %d)", job_id, return_code)
            return

        # ---- Success: register output PDB files ----
        output_pdb_ids: list[str] = []
        for pdb_file in sorted(output_dir.glob("design_*.pdb")):
            fid = file_manager.register(pdb_file, pdb_file.name)
            output_pdb_ids.append(fid)
            logger.info("Registered output PDB %s -> %s", pdb_file.name, fid)

        job_manager.set_results(job_id, output_pdb_ids)
        job_manager.update_status(
            job_id,
            "completed",
            progress=1.0,
            message=f"Completed — {len(output_pdb_ids)} design(s) generated",
        )
        logger.info("Job %s completed with %d designs", job_id, len(output_pdb_ids))

    except asyncio.TimeoutError:
        logger.error("Job %s timed out after %ds", job_id, config.JOB_TIMEOUT_SECS)
        job_manager.update_status(
            job_id,
            "failed",
            progress=None,
            message=f"Timed out after {config.JOB_TIMEOUT_SECS}s",
        )
        # Attempt to kill the process
        try:
            process.kill()  # type: ignore[possibly-undefined]
        except ProcessLookupError:
            pass

    except Exception as exc:
        logger.exception("Job %s encountered an unexpected error", job_id)
        job_manager.update_status(
            job_id,
            "failed",
            progress=None,
            message=f"Unexpected error: {exc}",
        )

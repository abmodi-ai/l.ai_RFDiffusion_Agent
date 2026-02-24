"""
File ID registry — maps UUID-based file_ids to filesystem paths.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict

from fastapi import HTTPException


class FileManager:
    """In-memory file registry that maps file_id -> Path on disk."""

    def __init__(self, upload_dir: Path, output_dir: Path) -> None:
        self._upload_dir = upload_dir
        self._output_dir = output_dir
        self._registry: Dict[str, dict] = {}  # file_id -> {path, original_filename}

        # Ensure directories exist
        self._upload_dir.mkdir(parents=True, exist_ok=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, filepath: Path, original_filename: str) -> str:
        """
        Register a file and return a new UUID-based file_id.

        Args:
            filepath: Absolute path to the file on disk.
            original_filename: The user-facing filename.

        Returns:
            A unique file_id string.
        """
        file_id = uuid.uuid4().hex
        self._registry[file_id] = {
            "path": filepath,
            "original_filename": original_filename,
        }
        return file_id

    def get_path(self, file_id: str) -> Path:
        """
        Look up the filesystem path for a given file_id.

        Raises:
            HTTPException 404 if the file_id is unknown or the file is missing.
        """
        entry = self._registry.get(file_id)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")
        path: Path = entry["path"]
        if not path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File registered but missing on disk: {file_id}",
            )
        return path

    def get_info(self, file_id: str) -> dict:
        """
        Return metadata for a registered file.

        Returns:
            dict with file_id, filename, and size_bytes.

        Raises:
            HTTPException 404 if the file_id is unknown.
        """
        entry = self._registry.get(file_id)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"File not found: {file_id}")
        path: Path = entry["path"]
        return {
            "file_id": file_id,
            "filename": entry["original_filename"],
            "size_bytes": path.stat().st_size if path.exists() else 0,
        }

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def upload_dir(self) -> Path:
        return self._upload_dir

    @property
    def output_dir(self) -> Path:
        return self._output_dir

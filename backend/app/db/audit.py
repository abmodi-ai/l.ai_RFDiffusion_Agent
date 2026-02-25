"""
Ligant.ai Audit Logging Utilities (Backend)

Convenience helpers that create ``AuditLog`` rows for common application
events such as login, job submission, PDB upload, etc.
"""

import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.db.models import AuditLog


# ── Core helper ──────────────────────────────────────────────────────────────

def log_action(
    db_session: Session,
    user_id: Optional[uuid.UUID],
    action_type: str,
    action_details: Optional[Dict[str, Any]] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    session_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """
    Create an ``AuditLog`` entry and add it to the given *db_session*.

    The caller is responsible for committing the session.
    """
    entry = AuditLog(
        user_id=user_id,
        session_id=session_id,
        action_type=action_type,
        action_details=action_details,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
    )
    db_session.add(entry)
    return entry


# ── Convenience wrappers ─────────────────────────────────────────────────────

def log_login(db: Session, user_id: uuid.UUID, ip: Optional[str] = None) -> AuditLog:
    return log_action(db, user_id=user_id, action_type="user.login",
                      resource_type="user", resource_id=str(user_id), ip_address=ip)


def log_logout(db: Session, user_id: uuid.UUID) -> AuditLog:
    return log_action(db, user_id=user_id, action_type="user.logout",
                      resource_type="user", resource_id=str(user_id))


def log_register(db: Session, user_id: uuid.UUID) -> AuditLog:
    return log_action(db, user_id=user_id, action_type="user.register",
                      resource_type="user", resource_id=str(user_id))


def log_job_submitted(
    db: Session, user_id: uuid.UUID, job_id: uuid.UUID,
    params: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    return log_action(db, user_id=user_id, action_type="job.submitted",
                      action_details=params, resource_type="job",
                      resource_id=str(job_id))


def log_job_completed(
    db: Session, user_id: uuid.UUID, job_id: uuid.UUID,
    summary: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    return log_action(db, user_id=user_id, action_type="job.completed",
                      action_details=summary, resource_type="job",
                      resource_id=str(job_id))


def log_pdb_uploaded(
    db: Session, user_id: uuid.UUID, file_id: uuid.UUID, filename: str,
) -> AuditLog:
    return log_action(db, user_id=user_id, action_type="pdb.uploaded",
                      action_details={"filename": filename},
                      resource_type="pdb_file", resource_id=str(file_id))


def log_pdb_fetched(
    db: Session, user_id: uuid.UUID, file_id: uuid.UUID,
    pdb_id: str, filename: str,
) -> AuditLog:
    return log_action(db, user_id=user_id, action_type="pdb.fetched_rcsb",
                      action_details={"pdb_id": pdb_id, "filename": filename},
                      resource_type="pdb_file", resource_id=str(file_id))


def log_chat_message(
    db: Session, user_id: uuid.UUID, role: str, msg_id: uuid.UUID,
) -> AuditLog:
    return log_action(db, user_id=user_id,
                      action_type=f"chat.message_{role}",
                      resource_type="chat_message", resource_id=str(msg_id))


def log_viz_viewed(db: Session, user_id: uuid.UUID, file_id: uuid.UUID) -> AuditLog:
    return log_action(db, user_id=user_id, action_type="viz.structure_viewed",
                      resource_type="pdb_file", resource_id=str(file_id))

"""
Ligant.ai Job History & Audit Trail Page

Displays a browsable history of RFdiffusion jobs and a filterable audit
log for the authenticated user.
"""

import streamlit as st
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, desc, and_

from ..db.connection import get_db
from ..db.models import Job, AuditLog, PDBFile


def _status_badge(status: str) -> str:
    """Return a Streamlit markdown color badge for a job status."""
    color_map = {
        "completed": "green",
        "failed": "red",
        "running": "orange",
        "queued": "orange",
        "pending": "blue",
        "cancelled": "gray",
    }
    color = color_map.get(status, "gray")
    return f":{color}[{status}]"


def _format_duration(seconds: float | None) -> str:
    """Format a duration in seconds into a human-readable string."""
    if seconds is None:
        return "--"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.0f}s"


def render_history_page(user) -> None:
    """
    Render the job history and audit trail page.

    Parameters
    ----------
    user : User
        The authenticated User ORM instance.
    """
    st.header("Job History & Audit Trail")

    tab_jobs, tab_audit = st.tabs(["Jobs", "Audit Log"])

    # ── Jobs Tab ──────────────────────────────────────────────────────────
    with tab_jobs:
        _render_jobs_tab(user)

    # ── Audit Log Tab ─────────────────────────────────────────────────────
    with tab_audit:
        _render_audit_tab(user)


def _render_jobs_tab(user) -> None:
    """Query and display the user's RFdiffusion job history."""
    with get_db() as db:
        stmt = (
            select(Job)
            .where(Job.user_id == user.id)
            .order_by(desc(Job.created_at))
            .limit(100)
        )
        jobs = db.execute(stmt).scalars().all()

    if not jobs:
        st.info("No jobs found. Start a conversation to submit your first RFdiffusion job.")
        return

    # Summary table
    for job in jobs:
        job_id_short = str(job.id)[:8]
        status = job.status or "unknown"
        contigs = job.contigs or "N/A"
        num_designs = job.num_designs or 1
        started = (
            job.started_at.strftime("%Y-%m-%d %H:%M")
            if job.started_at
            else job.created_at.strftime("%Y-%m-%d %H:%M")
        )
        duration = _format_duration(job.duration_secs)

        col1, col2, col3, col4, col5 = st.columns([2, 2, 3, 2, 2])
        with col1:
            st.markdown(f"**`{job_id_short}`**")
        with col2:
            st.markdown(_status_badge(status))
        with col3:
            st.code(contigs, language=None)
        with col4:
            st.caption(f"Designs: {num_designs}")
        with col5:
            st.caption(f"{started} ({duration})")

        # Expandable details
        with st.expander(f"Details for job {job_id_short}...", expanded=False):
            detail_col1, detail_col2 = st.columns(2)

            with detail_col1:
                st.markdown("**Parameters:**")
                if job.params:
                    st.json(job.params)
                else:
                    st.caption("No parameters recorded")

                if job.error_message:
                    st.markdown("**Error:**")
                    st.error(job.error_message)

            with detail_col2:
                st.markdown("**Result Summary:**")
                if job.result_summary:
                    st.json(job.result_summary)
                else:
                    st.caption("No result summary available")

                # Show linked output PDB files
                st.markdown("**Output PDB Files:**")
                with get_db() as db:
                    pdb_stmt = (
                        select(PDBFile)
                        .where(PDBFile.job_id == job.id)
                        .order_by(PDBFile.created_at)
                    )
                    pdb_files = db.execute(pdb_stmt).scalars().all()

                if pdb_files:
                    for pf in pdb_files:
                        st.caption(
                            f"  {pf.original_filename} "
                            f"({pf.file_size_bytes or 0:,} bytes)"
                        )
                else:
                    st.caption("No output files")

        st.markdown("---")


def _render_audit_tab(user) -> None:
    """Query and display the user's audit log with filters."""
    # ── Filters ───────────────────────────────────────────────────────────
    filter_col1, filter_col2 = st.columns(2)

    with filter_col1:
        default_start = datetime.now(timezone.utc) - timedelta(days=7)
        date_range = st.date_input(
            "Date range",
            value=(default_start.date(), datetime.now(timezone.utc).date()),
            key="audit_date_range",
        )

    with filter_col2:
        action_types = [
            "user.login",
            "user.logout",
            "user.register",
            "job.submitted",
            "job.completed",
            "pdb.uploaded",
            "chat.message_user",
            "chat.message_assistant",
            "viz.structure_viewed",
        ]
        selected_actions = st.multiselect(
            "Action types",
            options=action_types,
            default=[],
            key="audit_action_filter",
            placeholder="All action types",
        )

    # Parse date range
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = datetime.now(timezone.utc).date() - timedelta(days=7)
        end_date = datetime.now(timezone.utc).date()

    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    # ── Query ─────────────────────────────────────────────────────────────
    with get_db() as db:
        conditions = [
            AuditLog.user_id == user.id,
            AuditLog.created_at >= start_dt,
            AuditLog.created_at <= end_dt,
        ]
        if selected_actions:
            conditions.append(AuditLog.action_type.in_(selected_actions))

        stmt = (
            select(AuditLog)
            .where(and_(*conditions))
            .order_by(desc(AuditLog.created_at))
            .limit(200)
        )
        logs = db.execute(stmt).scalars().all()

    if not logs:
        st.info("No audit log entries found for the selected filters.")
        return

    # ── Timeline-style display ────────────────────────────────────────────
    st.markdown(f"**{len(logs)} entries found**")

    for entry in logs:
        timestamp = (
            entry.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if entry.created_at
            else "N/A"
        )
        action = entry.action_type

        col_time, col_action, col_details = st.columns([2, 2, 4])

        with col_time:
            st.caption(timestamp)
        with col_action:
            st.markdown(f"**{action}**")
        with col_details:
            if entry.action_details:
                details_str = ", ".join(
                    f"{k}: {v}" for k, v in entry.action_details.items()
                )
                st.caption(details_str)
            elif entry.resource_type and entry.resource_id:
                st.caption(f"{entry.resource_type}: {entry.resource_id[:16]}...")
            else:
                st.caption("--")

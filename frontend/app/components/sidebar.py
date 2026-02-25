"""
Ligant.ai Sidebar UI Component

Renders the application sidebar with user info, backend connection test,
PDB file upload, active jobs list, and settings.
"""

import streamlit as st
import requests

from app.config import get_settings
from app.auth.middleware import logout


def render_sidebar(user):
    """
    Render the full application sidebar.

    Parameters
    ----------
    user : User
        The authenticated User ORM instance from ``require_auth()``.
    """
    settings = get_settings()

    # ── User Info ─────────────────────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**{user.display_name or user.email}**")
    st.sidebar.caption(user.email)

    # ── Backend Connection ────────────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.subheader("Backend Connection")
    st.sidebar.text(f"URL: {settings.BACKEND_URL}")

    if st.sidebar.button("Test Connection", key="btn_test_connection"):
        try:
            resp = requests.get(
                f"{settings.BACKEND_URL}/api/health",
                headers={"X-API-Key": settings.BACKEND_API_KEY},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                gpu_info = data.get("gpu", "N/A")
                st.session_state["backend_connected"] = True
                st.sidebar.success(f"Connected  --  GPU: {gpu_info}")
            else:
                st.session_state["backend_connected"] = False
                st.sidebar.error(
                    f"Connection failed (HTTP {resp.status_code})"
                )
        except requests.exceptions.RequestException as exc:
            st.session_state["backend_connected"] = False
            st.sidebar.error(f"Connection error: {exc}")

    # Show persisted connection status
    if st.session_state.get("backend_connected") is True:
        st.sidebar.caption("Status: Connected")
    elif st.session_state.get("backend_connected") is False:
        st.sidebar.caption("Status: Disconnected")

    # ── PDB File Upload ───────────────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.subheader("PDB File Upload")

    uploaded_file = st.sidebar.file_uploader(
        "Upload a PDB file",
        type=["pdb"],
        key="sidebar_pdb_uploader",
        help="Upload .pdb files for use as RFdiffusion targets.",
    )

    if uploaded_file is not None:
        if "uploaded_files" not in st.session_state:
            st.session_state["uploaded_files"] = {}

        file_bytes = uploaded_file.getvalue()
        filename = uploaded_file.name

        if filename not in st.session_state["uploaded_files"]:
            st.session_state["uploaded_files"][filename] = file_bytes
            st.sidebar.success(f"Uploaded: {filename}")

    # List uploaded files
    if st.session_state.get("uploaded_files"):
        st.sidebar.markdown("**Uploaded files:**")
        for fname in st.session_state["uploaded_files"]:
            st.sidebar.caption(f"  {fname}")

    # ── Active Jobs ───────────────────────────────────────────────────────
    st.sidebar.markdown("---")
    st.sidebar.subheader("Active Jobs")

    active_jobs = st.session_state.get("active_jobs", [])
    if active_jobs:
        for job in active_jobs:
            job_id_short = str(job.get("job_id", ""))[:8]
            status = job.get("status", "unknown")
            contigs = job.get("contigs", "N/A")

            # Color-code status
            if status == "completed":
                status_badge = f":green[{status}]"
            elif status == "failed":
                status_badge = f":red[{status}]"
            elif status in ("running", "queued"):
                status_badge = f":orange[{status}]"
            else:
                status_badge = status

            st.sidebar.markdown(
                f"**{job_id_short}...** {status_badge}  \n"
                f"`{contigs}`"
            )
    else:
        st.sidebar.caption("No active jobs")

    # ── Logout ────────────────────────────────────────────────────────────
    st.sidebar.markdown("---")
    if st.sidebar.button("Logout", key="btn_logout"):
        logout()

    # ── Settings (expandable) ─────────────────────────────────────────────
    with st.sidebar.expander("Settings"):
        st.text(f"Backend URL: {settings.BACKEND_URL}")
        st.text(f"Environment: {settings.ENVIRONMENT}")

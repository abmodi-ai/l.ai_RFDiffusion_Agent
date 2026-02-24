"""
Ligant.ai -- Main Streamlit Application

Entry point for the Streamlit frontend.  Orchestrates authentication,
the chat interface (backed by a Claude AI agent), 3D structure
visualization, and job history.
"""

import streamlit as st
from uuid import uuid4

# ── Page config (must be the first Streamlit call) ────────────────────────────
st.set_page_config(
    page_title="Ligant.ai",
    page_icon=":test_tube:",
    layout="wide",
)

from .auth.middleware import require_auth
from .components.sidebar import render_sidebar
from .components.viewer_3d import render_pdb_viewer, render_overlay_comparison
from .pages.history import render_history_page

# ── Authentication gate ──────────────────────────────────────────────────────
user = require_auth()
if user is None:
    st.stop()

# ── Initialize session state ─────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = {}
if "active_jobs" not in st.session_state:
    st.session_state["active_jobs"] = []
if "pending_visualizations" not in st.session_state:
    st.session_state["pending_visualizations"] = []
if "conversation_id" not in st.session_state:
    st.session_state["conversation_id"] = str(uuid4())

# ── Sidebar ──────────────────────────────────────────────────────────────────
render_sidebar(user)

# ── Main content area ────────────────────────────────────────────────────────
st.title("Ligant.ai -- Protein Binder Design")
st.caption(
    "Design protein binders using RFdiffusion, guided by a Claude AI agent. "
    "Upload a target PDB, describe what you want, and let the agent handle the rest."
)

tab_chat, tab_history = st.tabs(["Chat", "History"])

# ── Chat Tab ──────────────────────────────────────────────────────────────────
with tab_chat:

    # Display chat history
    for msg in st.session_state["chat_history"]:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls")

        with st.chat_message(role):
            st.markdown(content)

            # Show tool call details if present
            if tool_calls:
                with st.expander("Tool calls", expanded=False):
                    for tc in tool_calls:
                        tool_name = tc.get("name", "unknown")
                        tool_input = tc.get("input", {})
                        tool_result = tc.get("result", "")
                        st.markdown(f"**{tool_name}**")
                        if tool_input:
                            st.json(tool_input)
                        if tool_result:
                            st.code(str(tool_result)[:500], language=None)

    # Render any pending visualizations
    if st.session_state["pending_visualizations"]:
        st.subheader("Structure Visualizations")
        for viz in st.session_state["pending_visualizations"]:
            viz_type = viz.get("type", "single")
            viz_style = viz.get("style", "cartoon")
            viz_color = viz.get("color_by", "chain")
            viz_label = viz.get("label", "")
            pdb_contents = viz.get("pdb_contents", [])

            if viz_type == "overlay" and len(pdb_contents) >= 2:
                render_overlay_comparison(
                    target_pdb=pdb_contents[0],
                    design_pdbs=pdb_contents[1:],
                    label=viz_label,
                )
            elif pdb_contents:
                render_pdb_viewer(
                    pdb_contents=pdb_contents,
                    style=viz_style,
                    color_by=viz_color,
                    label=viz_label,
                )

        # Clear pending visualizations after rendering
        st.session_state["pending_visualizations"] = []

    # Chat input
    user_input = st.chat_input(
        "Describe the protein binder you want to design...",
        key="chat_input",
    )

    if user_input:
        # Add user message to history
        st.session_state["chat_history"].append({
            "role": "user",
            "content": user_input,
        })

        # Display user message immediately
        with st.chat_message("user"):
            st.markdown(user_input)

        # Run the agent
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    from .agent import run_agent

                    response = run_agent(
                        message=user_input,
                        user_id=str(user.id),
                        conversation_id=st.session_state["conversation_id"],
                    )

                    # Extract response content
                    assistant_content = response.get("content", "")
                    tool_calls = response.get("tool_calls", [])

                    st.markdown(assistant_content)

                    # Show tool calls if any
                    if tool_calls:
                        with st.expander("Tool calls", expanded=False):
                            for tc in tool_calls:
                                tool_name = tc.get("name", "unknown")
                                tool_input = tc.get("input", {})
                                tool_result = tc.get("result", "")
                                st.markdown(f"**{tool_name}**")
                                if tool_input:
                                    st.json(tool_input)
                                if tool_result:
                                    st.code(str(tool_result)[:500], language=None)

                    # Store assistant message in history
                    st.session_state["chat_history"].append({
                        "role": "assistant",
                        "content": assistant_content,
                        "tool_calls": tool_calls,
                    })

                    # Update active jobs if the agent submitted any
                    if response.get("active_jobs"):
                        st.session_state["active_jobs"] = response["active_jobs"]

                    # Queue any visualizations
                    if response.get("visualizations"):
                        st.session_state["pending_visualizations"].extend(
                            response["visualizations"]
                        )
                        st.rerun()

                except Exception as exc:
                    error_msg = f"Agent error: {exc}"
                    st.error(error_msg)
                    st.session_state["chat_history"].append({
                        "role": "assistant",
                        "content": error_msg,
                    })

# ── History Tab ───────────────────────────────────────────────────────────────
with tab_history:
    render_history_page(user)

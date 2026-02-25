"""
Ligant.ai -- Main Streamlit Application

Entry point for the Streamlit frontend.  Orchestrates authentication,
the chat interface (backed by a Claude AI agent), 3D structure
visualization, and job history.
"""

import os
import sys

# Ensure the frontend/ directory is on sys.path so absolute imports like
# ``from app.auth.middleware import ...`` work when Streamlit runs this file
# as __main__.
_frontend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _frontend_dir not in sys.path:
    sys.path.insert(0, _frontend_dir)

import streamlit as st
from uuid import uuid4

# ── Page config (must be the first Streamlit call) ────────────────────────────
st.set_page_config(
    page_title="Ligant.ai",
    page_icon=":test_tube:",
    layout="wide",
)

from app.auth.middleware import require_auth
from app.components.sidebar import render_sidebar
from app.components.viewer_3d import render_pdb_viewer, render_overlay_comparison
from app.pages.history import render_history_page

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

    # Display chat history (Anthropic message format: content may be str or list)
    for msg in st.session_state["chat_history"]:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")

        # Skip tool_result messages (role=user with tool results)
        if role == "user" and isinstance(content, list) and content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
            continue

        with st.chat_message(role):
            if isinstance(content, str):
                st.markdown(content)
            elif isinstance(content, list):
                tool_blocks = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            st.markdown(block["text"])
                        elif block.get("type") == "tool_use":
                            tool_blocks.append(block)
                if tool_blocks:
                    with st.expander("Tool calls", expanded=False):
                        for tc in tool_blocks:
                            st.markdown(f"**{tc.get('name', 'unknown')}**")
                            if tc.get("input"):
                                st.json(tc["input"])

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
                    from app.agent.claude_agent import run_agent

                    from uuid import UUID as _UUID
                    response = run_agent(
                        user_message=user_input,
                        user_id=user.id if isinstance(user.id, _UUID) else _UUID(str(user.id)),
                        conversation_id=_UUID(st.session_state["conversation_id"]),
                    )

                    # run_agent returns the full messages list and
                    # updates st.session_state["chat_history"] internally.
                    # Extract the last assistant text to display now.
                    messages = response
                    assistant_text_parts = []
                    tool_calls_display = []

                    # Walk backwards to find the last assistant message(s)
                    for msg in reversed(messages):
                        if msg.get("role") != "assistant":
                            continue
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            assistant_text_parts.insert(0, content)
                        elif isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict):
                                    if block.get("type") == "text":
                                        assistant_text_parts.insert(0, block["text"])
                                    elif block.get("type") == "tool_use":
                                        tool_calls_display.append(block)
                        break  # only the last assistant message

                    final_text = "\n\n".join(assistant_text_parts)
                    if final_text:
                        st.markdown(final_text)

                    if tool_calls_display:
                        with st.expander("Tool calls", expanded=False):
                            for tc in tool_calls_display:
                                st.markdown(f"**{tc.get('name', 'unknown')}**")
                                if tc.get("input"):
                                    st.json(tc["input"])

                    # Check for pending visualizations queued by tool handlers
                    if st.session_state.get("pending_visualizations"):
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

"""
Ligant.ai Claude Agent -- Agentic Tool-Use Loop

Implements the core agent loop that:
  1. Sends the conversation to Claude with the available tools.
  2. When Claude responds with ``tool_use`` blocks, dispatches each tool call
     through ``handle_tool_call``, collects the results, and feeds them back.
  3. Repeats until Claude emits a final ``end_turn`` response or the
     iteration limit is reached.

All messages and audit events are persisted to the database.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from uuid import UUID

import anthropic
import streamlit as st

from ..config import get_settings
from ..db.connection import get_db
from ..db.models import ChatMessage
from ..db.audit import log_chat_message
from .tools import TOOLS
from .tool_handlers import handle_tool_call

logger = logging.getLogger(__name__)

# ── Maximum iterations to prevent runaway tool loops ─────────────────────────
MAX_AGENT_ITERATIONS = 10

# ── Claude model to use ─────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

# ── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are **Ligant.ai**, an expert AI assistant for computational protein binder \
design powered by RFdiffusion.

## Your Capabilities
You help researchers design de-novo protein binders against target proteins \
using the RFdiffusion generative model.  You have access to tools for \
uploading PDB files, launching RFdiffusion jobs, monitoring their progress, \
retrieving results, analyzing structures, and visualizing them in 3D.

## Domain Knowledge
- **PDB format**: Protein Data Bank files describe 3D atomic coordinates of \
macromolecules.  Each file contains one or more chains (labeled A, B, C, ...) \
made up of residues.
- **RFdiffusion**: A generative model that designs new protein backbones by \
iterative denoising.  It can generate binder proteins that dock against a \
fixed target surface.
- **Contigs syntax**: Contigs tell RFdiffusion which regions to keep fixed \
and which to generate.
  - `A1-100` = keep chain A residues 1 through 100 fixed (the target).
  - `100-100` = generate exactly 100 new residues (the binder).
  - `70-100` = generate between 70 and 100 new residues.
  - `/0 ` separating two segments = place them as separate chains with a chain \
break (i.e. the binder will be a separate chain).
  - Example: `A1-150/0 80-100` means "fix target chain A (residues 1-150) and \
generate a new binder chain of 80-100 residues".
- **Hotspot residues**: Optionally list target residues (e.g. A30, A33, A34) \
that the binder should contact, biasing the design toward that surface patch.
- **diffuser_T**: Number of denoising timesteps. Lower (25) = faster & less \
diverse; higher (100-200) = slower & more diverse designs.

## Typical Workflow
1. **Upload** the target protein PDB.
2. **Analyze** the structure (get_pdb_info) to understand chains, residues, \
and identify the binding surface.
3. **Design** binders with run_rfdiffusion, choosing appropriate contigs, \
hotspots, and parameters.
4. **Monitor** job progress with check_job_status.
5. **Retrieve** results with get_results.
6. **Visualize** designs overlaid on the target with visualize_structure.

## Communication Style
- Always explain *what* you are doing and *why* before calling a tool.
- When suggesting parameters (contigs, hotspot residues, binder length), \
explain your reasoning.
- If the user provides ambiguous instructions, ask clarifying questions rather \
than guessing.
- Summarize results clearly: number of designs generated, key structural \
features, next steps.
- Be proactive: after uploading a PDB, offer to analyze it; after job \
completion, offer to visualize results.

## Important Notes
- Always verify that a PDB has been uploaded before running RFdiffusion.
- If a job is still running, inform the user about progress and offer to \
check again.
- When multiple designs are generated, suggest visualizing them overlaid on \
the target to compare binding modes.
"""


def run_agent(
    user_message: str,
    user_id: UUID,
    conversation_id: UUID,
) -> List[Dict[str, Any]]:
    """
    Execute the Claude agentic tool-use loop for a single user turn.

    Parameters
    ----------
    user_message : str
        The new message from the user.
    user_id : UUID
        ID of the authenticated user.
    conversation_id : UUID
        ID of the current conversation / chat session.

    Returns
    -------
    list[dict]
        The full ``messages`` list suitable for display in the UI, including
        both user and assistant messages with their content blocks.
    """
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # ── Build message history ────────────────────────────────────────────
    messages: List[Dict[str, Any]] = list(
        st.session_state.get("chat_history", [])
    )

    # Append the new user message
    messages.append({"role": "user", "content": user_message})

    # Persist user message to DB
    _save_message_to_db(
        user_id=user_id,
        conversation_id=conversation_id,
        role="user",
        content=user_message,
    )

    # ── Agentic loop ─────────────────────────────────────────────────────
    assistant_text_blocks: List[str] = []

    for iteration in range(MAX_AGENT_ITERATIONS):
        logger.info(
            "Agent iteration %d/%d for conversation %s",
            iteration + 1,
            MAX_AGENT_ITERATIONS,
            conversation_id,
        )

        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
        except anthropic.APIError as exc:
            logger.exception("Anthropic API error")
            error_text = f"I encountered an API error: {exc}. Please try again."
            messages.append({"role": "assistant", "content": error_text})
            _save_message_to_db(
                user_id=user_id,
                conversation_id=conversation_id,
                role="assistant",
                content=error_text,
                model_used=CLAUDE_MODEL,
            )
            break

        # ── Process content blocks ───────────────────────────────────────
        tool_use_blocks = []
        assistant_content: List[Dict[str, Any]] = []

        for block in response.content:
            if block.type == "text":
                assistant_text_blocks.append(block.text)
                assistant_content.append({
                    "type": "text",
                    "text": block.text,
                })
            elif block.type == "tool_use":
                tool_use_blocks.append(block)
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        # Append the full assistant message (text + tool_use blocks)
        messages.append({"role": "assistant", "content": assistant_content})

        # ── If stop_reason is end_turn, we are done ──────────────────────
        if response.stop_reason == "end_turn":
            logger.info("Agent finished (end_turn) after %d iterations", iteration + 1)
            break

        # ── If there are tool calls, execute them ────────────────────────
        if response.stop_reason == "tool_use" and tool_use_blocks:
            tool_results: List[Dict[str, Any]] = []

            for tool_block in tool_use_blocks:
                logger.info(
                    "Executing tool: %s (id=%s)",
                    tool_block.name,
                    tool_block.id,
                )

                result_str = handle_tool_call(
                    tool_name=tool_block.name,
                    tool_input=tool_block.input,
                    user_id=user_id,
                )

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": result_str,
                })

            # Append tool results as a user-role message (Anthropic format)
            messages.append({"role": "user", "content": tool_results})
        else:
            # Unexpected stop_reason; break to avoid infinite loop
            logger.warning(
                "Unexpected stop_reason '%s' with %d tool blocks; breaking.",
                response.stop_reason,
                len(tool_use_blocks),
            )
            break
    else:
        # Loop exhausted without end_turn
        logger.warning(
            "Agent hit iteration limit (%d) for conversation %s",
            MAX_AGENT_ITERATIONS,
            conversation_id,
        )
        limit_msg = (
            "I've reached the maximum number of tool-use steps for this turn. "
            "Please send another message to continue."
        )
        assistant_text_blocks.append(limit_msg)
        messages.append({"role": "assistant", "content": limit_msg})

    # ── Persist final assistant response ─────────────────────────────────
    final_text = "\n\n".join(assistant_text_blocks)
    if final_text.strip():
        _save_message_to_db(
            user_id=user_id,
            conversation_id=conversation_id,
            role="assistant",
            content=final_text,
            model_used=CLAUDE_MODEL,
            token_count=_safe_token_count(response),
        )

    # ── Update session state with the full history ───────────────────────
    st.session_state["chat_history"] = messages

    return messages


# ── Private helpers ──────────────────────────────────────────────────────────

def _save_message_to_db(
    user_id: UUID,
    conversation_id: UUID,
    role: str,
    content: str,
    model_used: Optional[str] = None,
    token_count: Optional[int] = None,
) -> None:
    """Persist a chat message to the database and create an audit log entry."""
    with get_db() as db:
        msg = ChatMessage(
            user_id=user_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            model_used=model_used,
            token_count=token_count,
        )
        db.add(msg)
        db.flush()  # populate msg.id
        log_chat_message(db, user_id=user_id, role=role, msg_id=msg.id)


def _safe_token_count(response: Any) -> Optional[int]:
    """Extract total token usage from an Anthropic response, or None."""
    try:
        usage = response.usage
        return (usage.input_tokens or 0) + (usage.output_tokens or 0)
    except (AttributeError, TypeError):
        return None

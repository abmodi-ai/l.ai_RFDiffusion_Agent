"""
Ligant.ai Claude Agent -- Agentic Tool-Use Loop

Implements the core agent loop that:
  1. Sends the conversation to Claude with the available tools.
  2. When Claude responds with ``tool_use`` blocks, dispatches each tool call
     through ``handle_tool_call``, collects the results, and feeds them back.
  3. Repeats until Claude emits a final ``end_turn`` response or the
     iteration limit is reached.

Optimisations (Phase 1):
  - Multi-model routing via ``model_router`` (Haiku / Sonnet / Opus).
  - Extended thinking enabled **only** for Opus calls.
  - Thinking blocks pruned from history (signature kept for API continuity).
  - Tool results compressed to ≤ 2 000 chars.
  - History auto-summarised when estimated tokens > 80 K.
  - Job-monitoring policy in system prompt prevents wasteful polling.

All messages and audit events are persisted to the database.
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from uuid import UUID

import anthropic
import streamlit as st

from app.config import get_settings
from app.db.connection import get_db
from app.db.models import ChatMessage
from app.db.audit import log_chat_message
from app.agent.tools import TOOLS
from app.agent.tool_handlers import handle_tool_call
from app.agent.model_router import select_model, get_thinking_config
from app.agent.context_manager import (
    compress_tool_result,
    maybe_summarize_history,
    prune_thinking_blocks,
)

logger = logging.getLogger(__name__)

# ── Maximum iterations to prevent runaway tool loops ─────────────────────────
MAX_AGENT_ITERATIONS = 15

# ── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are **Ligant.ai**, an expert AI assistant for computational protein binder \
design powered by RFdiffusion. You are working directly with scientists and \
researchers — accuracy, scientific rigor, and clarity are paramount.

## Core Principle: Ask Before You Act
You are assisting real scientists with real experiments. Mistakes waste time, \
compute, and reagents. **Always ask clarifying questions** before proceeding \
if any of the following are unclear or ambiguous:
- Which chain(s) in the PDB should be the target vs. which should be ignored?
- What binding surface or epitope the user wants to target (specific residues, \
  a functional site, or the full surface)?
- Desired binder length range and number of designs.
- Whether the user has specific hotspot residues in mind or wants suggestions.
- The biological context: what is the target protein? Is there a known binding \
  interface, an active site, or an allosteric site of interest?
- Whether the user wants diverse designs (higher diffuser_T) or faster results.

Do NOT guess critical parameters. It is always better to ask one clarifying \
question than to run a job with wrong settings. Frame questions concisely and \
offer sensible defaults where appropriate (e.g., "I'd suggest a binder length \
of 70-100 residues — does that work for your application?").

## Your Capabilities
You help researchers design de-novo protein binders against target proteins \
using the RFdiffusion generative model. You have access to tools for \
uploading PDB files, fetching structures from the RCSB Protein Data Bank by \
PDB ID, launching RFdiffusion jobs, monitoring their progress, retrieving \
results, analyzing structures, and visualizing them in 3D.

## Domain Knowledge
- **PDB format**: Protein Data Bank files describe 3D atomic coordinates of \
macromolecules. Each file contains one or more chains (labeled A, B, C, ...) \
made up of residues.
- **RFdiffusion**: A generative model that designs new protein backbones by \
iterative denoising. It can generate binder proteins that dock against a \
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
  - **CRITICAL**: Crystal structures often have gaps in residue numbering. \
Always use `get_pdb_info` first — it returns `segments` for each chain listing \
the contiguous residue ranges. Use ONE contiguous segment (or a subset) in the \
contigs string. If a chain has segments ["A21-39", "A48-137", "A153-284"], do \
NOT use "A21-284" — instead pick a specific segment like "A48-137". \
RFdiffusion will error on missing residue numbers.
- **Hotspot residues**: Optionally list target residues (e.g. A30, A33, A34) \
that the binder should contact, biasing the design toward that surface patch.
- **diffuser_T**: Number of denoising timesteps. Lower (25) = faster & less \
diverse; higher (100-200) = slower & more diverse designs.
- **Binder length considerations**: Shorter binders (40-70 residues) are easier \
to express and more drug-like; longer binders (80-120+) can bury more surface \
area but may be harder to produce experimentally.

## Typical Workflow
1. **Upload** the target protein PDB or **fetch** it from RCSB by PDB ID.
2. **Analyze** the structure (get_pdb_info) to understand chains, residues, \
and identify potential binding surfaces.
3. **Discuss** with the user: confirm target chain, binding region, hotspots, \
binder length, and number of designs before running.
4. **Design** binders with run_rfdiffusion using the agreed parameters.
5. **Monitor** job progress with check_job_status.
6. **Retrieve** results with get_results.
7. **Visualize** designs overlaid on the target with visualize_structure.
8. **Interpret** results: comment on binding mode diversity, interface quality, \
and suggest next steps (e.g., ProteinMPNN sequence design, Rosetta relaxation, \
AlphaFold2 validation).

## Job Monitoring Policy
RFdiffusion jobs take several minutes to complete. After submitting a job with \
`run_rfdiffusion`:
- **DO NOT** call `check_job_status` repeatedly in a loop to poll for completion.
- **DO** tell the user the job has been submitted and approximately how long \
  it may take.
- **DO** inform the user they can ask you to check the status whenever they want.
- **ONLY** call `check_job_status` when the user explicitly asks for an update.
- If `check_job_status` returns "running", report the progress to the user and \
  wait for them to ask again — do NOT call it again in the same turn.

## Conversational Flow — ONE QUESTION AT A TIME
This is critical: **ask only ONE question per message**. Never dump a list of \
questions. Guide the user step by step through a natural conversation.

When asking a question, **always provide numbered options** the user can pick \
from, plus a final option for them to explain their own answer. Format:

```
[Your brief context sentence]

1. **Option A** — short description
2. **Option B** — short description
3. **Option C** — short description
4. **Something else** — tell me what you have in mind
```

### Example flow for a binder design request:
- Message 1: Ask about the target structure (offer to fetch from RCSB or ask for upload)
- Message 2: After getting the structure, ask about the binding surface / epitope
- Message 3: Ask about binder length
- Message 4: Ask about number of designs and diversity
- Then proceed to run the job.

Do NOT front-load all questions. Each message should have exactly ONE question \
with options. Wait for the user's answer before moving to the next question.

## Communication Style
- Always explain *what* you are doing and *why* before calling a tool.
- When suggesting parameters (contigs, hotspot residues, binder length), \
explain your scientific reasoning.
- Summarize results clearly: number of designs generated, key structural \
features, and recommended next steps.
- Be proactive: after uploading a PDB, offer to analyze it; after job \
completion, offer to visualize results.
- Use precise scientific language. Refer to residues by their chain and number \
(e.g., "Lys A:52"), name protein regions correctly, and cite structural \
features (helices, sheets, loops, binding pockets) when relevant.
- When you are uncertain about biological context, say so honestly and suggest \
the user verify with literature or domain expertise.
- Keep responses concise — no walls of text or emoji-heavy formatting.

## Important Notes
- When a user mentions a PDB ID (e.g., "6AL5", "1BRS"), use `fetch_pdb` to \
retrieve it from RCSB rather than asking the user to upload it manually.
- Always verify that a PDB has been uploaded or fetched before running RFdiffusion.
- If a job is still running, inform the user about progress and offer to \
check again.
- When multiple designs are generated, suggest visualizing them overlaid on \
the target to compare binding modes.
- Never fabricate structural data or residue numbers — always derive them from \
actual PDB analysis via tools.
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
    last_model_used: str = ""

    for iteration in range(MAX_AGENT_ITERATIONS):
        # Select model for this iteration
        has_tool_use = (
            iteration > 0
            and len(messages) >= 2
            and isinstance(messages[-2].get("content"), list)
            and any(
                isinstance(b, dict) and b.get("type") == "tool_use"
                for b in messages[-2]["content"]
            )
        )
        model = select_model(user_message, iteration, has_tool_use)
        last_model_used = model

        logger.info(
            "Agent iteration %d/%d — model=%s — conversation=%s",
            iteration + 1,
            MAX_AGENT_ITERATIONS,
            model,
            conversation_id,
        )
        print(
            f"\n{'='*60}\n"
            f"[AGENT] Iteration {iteration + 1}/{MAX_AGENT_ITERATIONS}  "
            f"model={model}\n"
            f"{'='*60}",
            flush=True,
        )

        # ── Prepare messages: prune thinking & maybe summarise ───────
        api_messages = prune_thinking_blocks(messages)
        api_messages = maybe_summarize_history(api_messages)

        # ── Build API kwargs ─────────────────────────────────────────
        api_kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": 16_000,
            "system": SYSTEM_PROMPT,
            "tools": TOOLS,
            "messages": api_messages,
        }

        thinking_config = get_thinking_config(model)
        if thinking_config is not None:
            api_kwargs["thinking"] = thinking_config

        try:
            response = client.messages.create(**api_kwargs)
        except anthropic.APIError as exc:
            logger.exception("Anthropic API error")
            error_text = f"I encountered an API error: {exc}. Please try again."
            messages.append({"role": "assistant", "content": error_text})
            _save_message_to_db(
                user_id=user_id,
                conversation_id=conversation_id,
                role="assistant",
                content=error_text,
                model_used=model,
            )
            break

        # ── Process content blocks ───────────────────────────────────
        tool_use_blocks = []
        assistant_content: List[Dict[str, Any]] = []

        for block in response.content:
            if block.type == "thinking":
                # Extended thinking block — log but don't display or store
                logger.info(
                    "Thinking: %s", block.thinking[:200] if block.thinking else ""
                )
                # Include thinking in the message for API continuity
                assistant_content.append({
                    "type": "thinking",
                    "thinking": block.thinking,
                    "signature": block.signature,
                })
            elif block.type == "text":
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

        print(
            f"[AGENT] stop_reason={response.stop_reason}, "
            f"tool_blocks={len(tool_use_blocks)}",
            flush=True,
        )

        # ── If stop_reason is end_turn, we are done ──────────────────
        if response.stop_reason == "end_turn":
            logger.info(
                "Agent finished (end_turn) after %d iterations", iteration + 1
            )
            break

        # ── If there are tool calls, execute them ────────────────────
        if response.stop_reason == "tool_use" and tool_use_blocks:
            tool_results: List[Dict[str, Any]] = []

            for tool_block in tool_use_blocks:
                logger.info(
                    "Executing tool: %s (id=%s) input=%s",
                    tool_block.name,
                    tool_block.id,
                    json.dumps(tool_block.input)[:200],
                )
                print(
                    f"  [TOOL] {tool_block.name}"
                    f"({json.dumps(tool_block.input)[:120]})",
                    flush=True,
                )

                result_str = handle_tool_call(
                    tool_name=tool_block.name,
                    tool_input=tool_block.input,
                    user_id=user_id,
                )

                # Compress tool result before adding to context
                result_str = compress_tool_result(result_str)

                # Log truncated result for debugging
                result_preview = result_str[:200]
                logger.info("  -> result: %s", result_preview)
                print(f"  [RESULT] {result_preview}", flush=True)

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
            model_used=last_model_used,
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

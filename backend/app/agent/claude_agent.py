"""
Ligant.ai Claude Agent — Backend Async Streaming Version

This is the backend version of the agent that:
  - Runs as an async generator yielding SSE events
  - Calls services directly (no HTTP self-calls)
  - Uses multi-model routing and context management
  - Persists messages to the database
"""

import json
import logging
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

import anthropic

from app.agent.context_manager import (
    compress_tool_result,
    maybe_summarize_history,
    prune_thinking_blocks,
)
from app.agent.model_router import get_thinking_config, select_model
from app.agent.tool_handlers import ToolContext, handle_tool_call
from app.agent.tools import TOOLS
from app.db.audit import log_chat_message
from app.db.models import ChatMessage

logger = logging.getLogger(__name__)

MAX_AGENT_ITERATIONS = 15

# Same system prompt as the frontend agent
SYSTEM_PROMPT = """\
You are **Ligant.ai**, an expert AI assistant for computational protein binder \
design powered by RFdiffusion. You are working directly with scientists and \
researchers — accuracy, scientific rigor, and clarity are paramount.

## Core Principle: Ask Before You Act
You are assisting real scientists with real experiments. Mistakes waste time, \
compute, and reagents. **Always ask clarifying questions** before proceeding \
if any of the following are unclear or ambiguous:
- Which chain(s) in the PDB should be the target vs. which should be ignored?
- What binding surface or epitope the user wants to target?
- Desired binder length range and number of designs.
- Whether the user has specific hotspot residues in mind or wants suggestions.
- The biological context of the target protein.
- Whether the user wants diverse designs (higher diffuser_T) or faster results.

Do NOT guess critical parameters.

## Your Capabilities
You help researchers design de-novo protein binders using RFdiffusion. You have \
tools for uploading PDB files, fetching from RCSB, launching RFdiffusion jobs, \
monitoring progress, retrieving results, analyzing structures, and visualizing in 3D.

## Domain Knowledge
- **PDB format**: 3D atomic coordinates of macromolecules with chains (A, B, C...).
- **RFdiffusion**: Generative model for protein backbone design by iterative denoising.
- **Contigs syntax**: `A1-100` = fixed; `100-100` = generate 100 residues; `/0 ` = chain break.
  - **CRITICAL**: Always use `get_pdb_info` first to check for residue gaps.
- **Hotspot residues**: Target residues to bias binding toward.
- **diffuser_T**: Lower (25) = faster; higher (100-200) = more diverse.

## Job Monitoring Policy
After submitting a job with `run_rfdiffusion`:
- **DO NOT** call `check_job_status` repeatedly to poll.
- **DO** tell the user the job has been submitted.
- **ONLY** call `check_job_status` when the user explicitly asks.

## Communication Style
- Explain what you are doing and why before calling a tool.
- Summarize results clearly with next steps.
- Use precise scientific language.
- Never fabricate structural data.
"""


async def run_agent_streaming(
    user_message: str,
    user_id: UUID,
    conversation_id: UUID,
    messages: List[Dict[str, Any]],
    tool_context: ToolContext,
    api_key: str,
    db_session,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Async generator that runs the Claude agent loop and yields SSE events.

    Yields dicts like:
      {"event": "text", "data": "Hello..."}
      {"event": "tool_call", "data": {"name": "fetch_pdb", "input": {...}}}
      {"event": "tool_result", "data": {"name": "fetch_pdb", "result": {...}}}
      {"event": "visualization", "data": {"pdb_contents": {...}, ...}}
      {"event": "done", "data": {"model_used": "...", "iterations": N}}
    """
    client = anthropic.Anthropic(api_key=api_key)

    # Append new user message
    messages.append({"role": "user", "content": user_message})

    # Persist user message
    _save_message(db_session, user_id, conversation_id, "user", user_message)

    assistant_text_blocks: List[str] = []
    last_model_used = ""

    for iteration in range(MAX_AGENT_ITERATIONS):
        # Select model
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

        logger.info("Agent iteration %d/%d model=%s", iteration + 1, MAX_AGENT_ITERATIONS, model)

        # Prepare messages
        api_messages = prune_thinking_blocks(messages)
        api_messages = maybe_summarize_history(api_messages)

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
            yield {"event": "text", "data": error_text}
            messages.append({"role": "assistant", "content": error_text})
            _save_message(db_session, user_id, conversation_id, "assistant",
                          error_text, model_used=model)
            break

        # Process content blocks
        tool_use_blocks = []
        assistant_content: List[Dict[str, Any]] = []

        for block in response.content:
            if block.type == "thinking":
                assistant_content.append({
                    "type": "thinking",
                    "thinking": block.thinking,
                    "signature": block.signature,
                })
            elif block.type == "text":
                assistant_text_blocks.append(block.text)
                assistant_content.append({"type": "text", "text": block.text})
                yield {"event": "text", "data": block.text}
            elif block.type == "tool_use":
                tool_use_blocks.append(block)
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
                yield {
                    "event": "tool_call",
                    "data": {"name": block.name, "input": block.input},
                }

        messages.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use" and tool_use_blocks:
            tool_results: List[Dict[str, Any]] = []

            for tool_block in tool_use_blocks:
                result_str = handle_tool_call(
                    tool_name=tool_block.name,
                    tool_input=tool_block.input,
                    user_id=user_id,
                    ctx=tool_context,
                    db_session=db_session,
                )
                result_str = compress_tool_result(result_str)

                yield {
                    "event": "tool_result",
                    "data": {"name": tool_block.name, "result": result_str},
                }

                # Check for visualization data
                try:
                    parsed = json.loads(result_str)
                    if isinstance(parsed, dict) and "pdb_contents" in parsed:
                        yield {
                            "event": "visualization",
                            "data": {
                                "pdb_contents": parsed["pdb_contents"],
                                "style": parsed.get("style", "cartoon"),
                                "color_by": parsed.get("color_by", "chain"),
                            },
                        }
                except (json.JSONDecodeError, TypeError):
                    pass

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": result_str,
                })

            messages.append({"role": "user", "content": tool_results})
        else:
            break
    else:
        limit_msg = (
            "I've reached the maximum number of tool-use steps for this turn. "
            "Please send another message to continue."
        )
        assistant_text_blocks.append(limit_msg)
        messages.append({"role": "assistant", "content": limit_msg})
        yield {"event": "text", "data": limit_msg}

    # Persist final assistant response
    final_text = "\n\n".join(assistant_text_blocks)
    if final_text.strip():
        _save_message(
            db_session, user_id, conversation_id, "assistant",
            final_text, model_used=last_model_used,
            token_count=_safe_token_count(response),
        )

    yield {
        "event": "done",
        "data": {
            "model_used": last_model_used,
            "iterations": min(iteration + 1, MAX_AGENT_ITERATIONS),
        },
    }


def _save_message(
    db, user_id: UUID, conversation_id: UUID, role: str, content: str,
    model_used: Optional[str] = None, token_count: Optional[int] = None,
) -> None:
    msg = ChatMessage(
        user_id=user_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
        model_used=model_used,
        token_count=token_count,
    )
    db.add(msg)
    db.flush()
    log_chat_message(db, user_id=user_id, role=role, msg_id=msg.id)


def _safe_token_count(response: Any) -> Optional[int]:
    try:
        usage = response.usage
        return (usage.input_tokens or 0) + (usage.output_tokens or 0)
    except (AttributeError, TypeError):
        return None

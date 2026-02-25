"""
Chat endpoints with Server-Sent Events (SSE) streaming.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.agent.claude_agent import run_agent_streaming
from app.agent.tool_handlers import ToolContext
from app.db.connection import get_db_session
from app.db.models import ChatMessage, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=50000)
    conversation_id: Optional[str] = None


class ChatHistoryItem(BaseModel):
    id: str
    role: str
    content: str
    model_used: Optional[str] = None
    created_at: str


@router.post("/message")
async def send_message(
    body: ChatMessageRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Accept a chat message and return an SSE stream.

    Events:
      - event: text       — streaming text chunk from Claude
      - event: tool_call  — tool name + input
      - event: tool_result — tool execution result
      - event: visualization — PDB contents for Mol* viewer
      - event: done       — stream complete
    """
    settings = request.app.state.settings
    file_manager = request.app.state.file_manager
    job_manager = request.app.state.job_manager

    conversation_id = (
        uuid.UUID(body.conversation_id)
        if body.conversation_id
        else uuid.uuid4()
    )

    # Load conversation history from DB
    messages = _load_conversation_messages(db, user.id, conversation_id)

    tool_context = ToolContext(
        file_manager=file_manager,
        job_manager=job_manager,
        settings=settings,
    )

    async def event_generator():
        # Send conversation_id first
        yield _format_sse("conversation_id", {"conversation_id": str(conversation_id)})

        async for event in run_agent_streaming(
            user_message=body.message,
            user_id=user.id,
            conversation_id=conversation_id,
            messages=messages,
            tool_context=tool_context,
            api_key=settings.ANTHROPIC_API_KEY,
            db_session=db,
        ):
            yield _format_sse(event["event"], event["data"])

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{conversation_id}/history")
def get_conversation_history(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[ChatHistoryItem]:
    """Return the message history for a conversation."""
    messages = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.user_id == user.id,
            ChatMessage.conversation_id == uuid.UUID(conversation_id),
        )
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return [
        ChatHistoryItem(
            id=str(m.id),
            role=m.role,
            content=m.content,
            model_used=m.model_used,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@router.get("/conversations")
def list_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> list[dict]:
    """List all conversations for the current user with the first message as preview."""
    from sqlalchemy import func, distinct

    conversation_ids = (
        db.query(distinct(ChatMessage.conversation_id))
        .filter(ChatMessage.user_id == user.id)
        .all()
    )

    conversations = []
    for (conv_id,) in conversation_ids:
        first_msg = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.user_id == user.id,
                ChatMessage.conversation_id == conv_id,
                ChatMessage.role == "user",
            )
            .order_by(ChatMessage.created_at.asc())
            .first()
        )
        last_msg = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.user_id == user.id,
                ChatMessage.conversation_id == conv_id,
            )
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        conversations.append({
            "conversation_id": str(conv_id),
            "preview": (first_msg.content[:100] + "...") if first_msg and len(first_msg.content) > 100 else (first_msg.content if first_msg else ""),
            "last_activity": last_msg.created_at.isoformat() if last_msg else None,
        })

    # Sort by last activity descending
    conversations.sort(key=lambda c: c["last_activity"] or "", reverse=True)
    return conversations


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_conversation_messages(
    db: Session,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> list[dict]:
    """
    Load conversation history from the DB and reconstruct the Anthropic
    messages format (simplified: text-only, no tool blocks).
    """
    db_messages = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.user_id == user_id,
            ChatMessage.conversation_id == conversation_id,
        )
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    messages = []
    for m in db_messages:
        messages.append({"role": m.role, "content": m.content})

    return messages


def _format_sse(event: str, data) -> str:
    """Format a Server-Sent Event."""
    if isinstance(data, str):
        json_data = json.dumps(data)
    else:
        json_data = json.dumps(data)
    return f"event: {event}\ndata: {json_data}\n\n"

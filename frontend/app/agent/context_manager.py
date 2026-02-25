"""
Ligant.ai Context Manager

Keeps the conversation context within budget by:
  1. **Pruning thinking blocks** — strips content, retains only the ``signature``
     field required for Anthropic API continuity.
  2. **Compressing tool results** — truncates to MAX_TOOL_RESULT_CHARS; trims
     sequence previews in PDB-info payloads.
  3. **Summarising history** — when estimated tokens exceed TOKEN_THRESHOLD the
     older (middle) messages are aggressively condensed while preserving the
     user/assistant alternation pattern.
"""

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ── Tunables ─────────────────────────────────────────────────────────────────
MAX_TOOL_RESULT_CHARS = 2000
MAX_SEQUENCE_PREVIEW_CHARS = 20
TOKEN_THRESHOLD = 80_000
_CHARS_PER_TOKEN = 4  # rough approximation


# ── 1. Thinking-block pruning ────────────────────────────────────────────────

def prune_thinking_blocks(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return a *new* message list with thinking-block content stripped.

    The ``signature`` field is kept so that the Anthropic API still accepts the
    conversation, but the (often 5-10 KB) ``thinking`` text is replaced with an
    empty string.
    """
    pruned: List[Dict[str, Any]] = []
    for msg in messages:
        if msg["role"] == "assistant" and isinstance(msg.get("content"), list):
            new_content: List[Dict[str, Any]] = []
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "thinking":
                    new_content.append({
                        "type": "thinking",
                        "thinking": "",
                        "signature": block.get("signature", ""),
                    })
                else:
                    new_content.append(block)
            pruned.append({"role": msg["role"], "content": new_content})
        else:
            pruned.append(msg)
    return pruned


# ── 2. Tool-result compression ───────────────────────────────────────────────

def compress_tool_result(result_str: str) -> str:
    """
    Compress a single tool-result string:
      * Error payloads are returned unchanged.
      * ``sequence_preview`` fields inside PDB-info JSON are trimmed.
      * Total length is capped at ``MAX_TOOL_RESULT_CHARS``.
    """
    # Never compress error messages — they're usually short and important.
    try:
        parsed = json.loads(result_str)
        if isinstance(parsed, dict) and "error" in parsed:
            return result_str
    except (json.JSONDecodeError, TypeError):
        pass

    # Trim sequence previews in PDB info payloads
    result_str = _trim_sequence_previews(result_str)

    # Hard-cap length
    if len(result_str) > MAX_TOOL_RESULT_CHARS:
        return result_str[: MAX_TOOL_RESULT_CHARS - 60] + "\n...[truncated to 2000 chars]"

    return result_str


# ── 3. History summarisation ─────────────────────────────────────────────────

def maybe_summarize_history(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    If the estimated token count exceeds ``TOKEN_THRESHOLD``, aggressively
    condense older messages in the *middle* of the conversation while keeping
    the head (first 2 messages) and tail (last 8 messages) intact.

    The user/assistant alternation pattern is preserved — only the *content*
    of middle messages is truncated, not the messages themselves.
    """
    estimated = estimate_tokens(messages)
    if estimated <= TOKEN_THRESHOLD:
        return messages

    logger.info(
        "Context estimated at ~%d tokens (threshold %d); condensing history.",
        estimated,
        TOKEN_THRESHOLD,
    )

    if len(messages) <= 10:
        # Not enough messages to split; just return as-is.
        return messages

    keep_recent = 8
    head = messages[:2]
    tail = messages[-keep_recent:]
    middle = messages[2:-keep_recent]

    condensed_middle = [_condense_message(msg) for msg in middle]
    return head + condensed_middle + tail


def estimate_tokens(messages: List[Dict[str, Any]]) -> int:
    """Rough token estimate based on character count / 4."""
    total_chars = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "text":
                    total_chars += len(block.get("text", ""))
                elif btype == "tool_result":
                    total_chars += len(str(block.get("content", "")))
                elif btype == "tool_use":
                    total_chars += len(json.dumps(block.get("input", {})))
                elif btype == "thinking":
                    total_chars += len(block.get("thinking", ""))
    return total_chars // _CHARS_PER_TOKEN


# ── Private helpers ──────────────────────────────────────────────────────────

def _trim_sequence_previews(result_str: str) -> str:
    """Replace long ``sequence_preview`` values in a JSON string."""
    try:
        data = json.loads(result_str)
        if isinstance(data, dict):
            _trim_sequences_recursive(data)
            return json.dumps(data)
    except (json.JSONDecodeError, TypeError):
        pass
    return result_str


def _trim_sequences_recursive(obj: Any) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "sequence_preview" and isinstance(value, str):
                if len(value) > MAX_SEQUENCE_PREVIEW_CHARS:
                    obj[key] = value[:MAX_SEQUENCE_PREVIEW_CHARS] + "..."
            elif isinstance(value, (dict, list)):
                _trim_sequences_recursive(value)
    elif isinstance(obj, list):
        for item in obj:
            _trim_sequences_recursive(item)


def _condense_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aggressively condense a single message's content while preserving its
    ``role`` so that user/assistant alternation is unbroken.
    """
    role = msg["role"]
    content = msg.get("content", "")

    if isinstance(content, str):
        if len(content) > 200:
            return {"role": role, "content": content[:200] + "..."}
        return msg

    if isinstance(content, list):
        new_content: List[Dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                new_content.append(block)
                continue
            btype = block.get("type")
            if btype == "thinking":
                new_content.append({
                    "type": "thinking",
                    "thinking": "",
                    "signature": block.get("signature", ""),
                })
            elif btype == "text":
                text = block.get("text", "")
                if len(text) > 200:
                    new_content.append({"type": "text", "text": text[:200] + "..."})
                else:
                    new_content.append(block)
            elif btype == "tool_use":
                # Tool-use blocks are small; keep them.
                new_content.append(block)
            elif btype == "tool_result":
                rc = str(block.get("content", ""))
                if len(rc) > 200:
                    new_content.append({
                        "type": "tool_result",
                        "tool_use_id": block.get("tool_use_id"),
                        "content": rc[:200] + "...[condensed]",
                    })
                else:
                    new_content.append(block)
            else:
                new_content.append(block)
        return {"role": role, "content": new_content}

    return msg

"""
Ligant.ai Context Manager (Backend copy)

Keeps the conversation context within budget by:
  1. Pruning thinking blocks (strip content, keep signature).
  2. Compressing tool results (truncate to MAX_TOOL_RESULT_CHARS).
  3. Summarising history when estimated tokens exceed TOKEN_THRESHOLD.
"""

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

MAX_TOOL_RESULT_CHARS = 2000
MAX_SEQUENCE_PREVIEW_CHARS = 20
TOKEN_THRESHOLD = 80_000
_CHARS_PER_TOKEN = 4


def prune_thinking_blocks(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pruned: List[Dict[str, Any]] = []
    for msg in messages:
        if msg["role"] == "assistant" and isinstance(msg.get("content"), list):
            new_content = []
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


def compress_tool_result(result_str: str) -> str:
    try:
        parsed = json.loads(result_str)
        if isinstance(parsed, dict) and "error" in parsed:
            return result_str
    except (json.JSONDecodeError, TypeError):
        pass
    result_str = _trim_sequence_previews(result_str)
    if len(result_str) > MAX_TOOL_RESULT_CHARS:
        return result_str[:MAX_TOOL_RESULT_CHARS - 60] + "\n...[truncated to 2000 chars]"
    return result_str


def maybe_summarize_history(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    estimated = estimate_tokens(messages)
    if estimated <= TOKEN_THRESHOLD:
        return messages
    logger.info("Context ~%d tokens; condensing history.", estimated)
    if len(messages) <= 10:
        return messages
    keep_recent = 8
    head = messages[:2]
    tail = messages[-keep_recent:]
    middle = messages[2:-keep_recent]
    return head + [_condense_message(m) for m in middle] + tail


def estimate_tokens(messages: List[Dict[str, Any]]) -> int:
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


def _trim_sequence_previews(result_str: str) -> str:
    try:
        data = json.loads(result_str)
        if isinstance(data, dict):
            _trim_recursive(data)
            return json.dumps(data)
    except (json.JSONDecodeError, TypeError):
        pass
    return result_str


def _trim_recursive(obj: Any) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "sequence_preview" and isinstance(value, str) and len(value) > MAX_SEQUENCE_PREVIEW_CHARS:
                obj[key] = value[:MAX_SEQUENCE_PREVIEW_CHARS] + "..."
            elif isinstance(value, (dict, list)):
                _trim_recursive(value)
    elif isinstance(obj, list):
        for item in obj:
            _trim_recursive(item)


def _condense_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    role = msg["role"]
    content = msg.get("content", "")
    if isinstance(content, str):
        return {"role": role, "content": content[:200] + "..."} if len(content) > 200 else msg
    if isinstance(content, list):
        new_content = []
        for block in content:
            if not isinstance(block, dict):
                new_content.append(block)
                continue
            btype = block.get("type")
            if btype == "thinking":
                new_content.append({"type": "thinking", "thinking": "", "signature": block.get("signature", "")})
            elif btype == "text":
                text = block.get("text", "")
                new_content.append({"type": "text", "text": text[:200] + "..."} if len(text) > 200 else block)
            elif btype == "tool_use":
                new_content.append(block)
            elif btype == "tool_result":
                rc = str(block.get("content", ""))
                if len(rc) > 200:
                    new_content.append({"type": "tool_result", "tool_use_id": block.get("tool_use_id"), "content": rc[:200] + "...[condensed]"})
                else:
                    new_content.append(block)
            else:
                new_content.append(block)
        return {"role": role, "content": new_content}
    return msg

"""
Gemini adapter — converts between Anthropic and Google Gemini API formats.

Used as a fallback when Anthropic API returns transient errors.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Anthropic-like response dataclasses
# ---------------------------------------------------------------------------
# Lightweight stand-ins so the agent loop's block processing
# (block.type, block.text, block.id, block.name, block.input) works unchanged.


@dataclass
class AnthropicLikeTextBlock:
    text: str
    type: str = "text"


@dataclass
class AnthropicLikeToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass
class AnthropicLikeUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class AnthropicLikeResponse:
    content: list = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: AnthropicLikeUsage = field(default_factory=AnthropicLikeUsage)


# ---------------------------------------------------------------------------
# Tool conversion: Anthropic -> Gemini
# ---------------------------------------------------------------------------

def anthropic_tools_to_gemini(tools: List[Dict[str, Any]]) -> List[types.Tool]:
    """Convert Anthropic tool definitions to Gemini FunctionDeclarations."""
    declarations = []
    for tool in tools:
        declarations.append(
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=_clean_schema_for_gemini(tool.get("input_schema", {})),
            )
        )
    return [types.Tool(function_declarations=declarations)]


def _clean_schema_for_gemini(schema: dict) -> dict:
    """Remove JSON Schema features that Gemini doesn't support."""
    cleaned = dict(schema)
    # Gemini doesn't accept additionalProperties in function param schemas
    cleaned.pop("additionalProperties", None)
    if "properties" in cleaned:
        for key, prop in cleaned["properties"].items():
            if isinstance(prop, dict):
                cleaned["properties"][key] = _clean_schema_for_gemini(prop)
    if "items" in cleaned and isinstance(cleaned["items"], dict):
        cleaned["items"] = _clean_schema_for_gemini(cleaned["items"])
    return cleaned


# ---------------------------------------------------------------------------
# Message conversion: Anthropic -> Gemini
# ---------------------------------------------------------------------------

def anthropic_messages_to_gemini(
    messages: List[Dict[str, Any]],
) -> List[types.Content]:
    """Convert Anthropic message history to Gemini Content objects."""
    # Build a mapping of tool_use_id -> tool_name for resolving tool_result blocks
    tool_id_to_name: Dict[str, str] = {}
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_id_to_name[block["id"]] = block["name"]

    raw_contents: List[types.Content] = []

    for msg in messages:
        role = msg["role"]
        gemini_role = "model" if role == "assistant" else "user"
        content = msg.get("content")

        parts: List[types.Part] = []

        if isinstance(content, str):
            parts.append(types.Part(text=content))
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")

                if btype == "text":
                    text = block.get("text", "")
                    if text:
                        parts.append(types.Part(text=text))

                elif btype == "tool_use":
                    parts.append(types.Part(
                        function_call=types.FunctionCall(
                            name=block["name"],
                            args=block.get("input", {}),
                        )
                    ))

                elif btype == "tool_result":
                    tool_use_id = block.get("tool_use_id", "")
                    tool_name = tool_id_to_name.get(tool_use_id, "unknown_tool")
                    result_content = block.get("content", "")
                    # Parse result if it's JSON string
                    try:
                        result_data = json.loads(result_content) if isinstance(result_content, str) else result_content
                    except (json.JSONDecodeError, TypeError):
                        result_data = {"result": str(result_content)}
                    if not isinstance(result_data, dict):
                        result_data = {"result": str(result_data)}

                    parts.append(types.Part(
                        function_response=types.FunctionResponse(
                            name=tool_name,
                            response=result_data,
                        )
                    ))

                elif btype == "thinking":
                    # Anthropic-specific, skip for Gemini
                    continue

        if parts:
            raw_contents.append(types.Content(role=gemini_role, parts=parts))

    # Gemini requires alternating user/model turns — merge consecutive same-role
    merged: List[types.Content] = []
    for content in raw_contents:
        if merged and merged[-1].role == content.role:
            merged[-1].parts.extend(content.parts)
        else:
            merged.append(content)

    return merged


# ---------------------------------------------------------------------------
# Response conversion: Gemini -> Anthropic-like
# ---------------------------------------------------------------------------

def gemini_response_to_anthropic_like(
    response,
) -> AnthropicLikeResponse:
    """Convert a Gemini GenerateContentResponse to an AnthropicLikeResponse."""
    content_blocks: list = []
    has_function_calls = False

    if response.candidates:
        candidate = response.candidates[0]
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if part.text:
                    content_blocks.append(AnthropicLikeTextBlock(text=part.text))
                elif part.function_call:
                    has_function_calls = True
                    fc = part.function_call
                    tool_id = f"toolu_gemini_{uuid.uuid4().hex[:24]}"
                    args = dict(fc.args) if fc.args else {}
                    content_blocks.append(AnthropicLikeToolUseBlock(
                        id=tool_id,
                        name=fc.name,
                        input=args,
                    ))

    # Determine stop reason
    stop_reason = "tool_use" if has_function_calls else "end_turn"

    # Extract usage
    usage = AnthropicLikeUsage()
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        um = response.usage_metadata
        usage = AnthropicLikeUsage(
            input_tokens=getattr(um, "prompt_token_count", 0) or 0,
            output_tokens=getattr(um, "candidates_token_count", 0) or 0,
        )

    return AnthropicLikeResponse(
        content=content_blocks,
        stop_reason=stop_reason,
        usage=usage,
    )


# ---------------------------------------------------------------------------
# Main call function
# ---------------------------------------------------------------------------

async def call_gemini(
    gemini_client: genai.Client,
    model: str,
    system_prompt: str,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
) -> AnthropicLikeResponse:
    """Call Gemini and return an Anthropic-like response object."""
    gemini_tools = anthropic_tools_to_gemini(tools)
    gemini_messages = anthropic_messages_to_gemini(messages)

    config = types.GenerateContentConfig(
        tools=gemini_tools,
        system_instruction=system_prompt,
        max_output_tokens=16_000,
    )

    response = await gemini_client.aio.models.generate_content(
        model=model,
        contents=gemini_messages,
        config=config,
    )

    return gemini_response_to_anthropic_like(response)

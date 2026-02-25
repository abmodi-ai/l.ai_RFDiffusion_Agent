"""
Generate short conversation titles using Haiku.
"""

import logging
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

TITLE_PROMPT = (
    "Generate a very short title (max 6 words) for a conversation that starts with "
    "the following user message. The title should capture the intent. "
    "Return ONLY the title text, nothing else.\n\n"
    "User message: {message}"
)


def generate_conversation_title(api_key: str, user_message: str) -> Optional[str]:
    """Call Haiku to generate a concise conversation title."""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=30,
            messages=[
                {
                    "role": "user",
                    "content": TITLE_PROMPT.format(message=user_message[:500]),
                }
            ],
        )
        title = response.content[0].text.strip().strip('"').strip("'")
        # Cap at 100 chars
        return title[:100] if title else None
    except Exception:
        logger.exception("Failed to generate conversation title")
        return None

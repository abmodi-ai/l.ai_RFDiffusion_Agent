"""
Ligant.ai Multi-Model Router (Backend copy)

Routes Claude API requests to the optimal model based on:
  - Iteration number (0 = classify request; >0 = tool dispatch)
  - Message complexity (greetings vs. scientific reasoning)
  - Whether extended thinking should be enabled

Model tiers:
  Haiku 4.5  — simple greetings, clarifications, short queries with no tools
  Sonnet 4.6 — DEFAULT for all tool-dispatch iterations and standard interactions
  Opus 4.6   — complex scientific reasoning (result interpretation, design strategy)
"""

import re

# ── Model IDs ────────────────────────────────────────────────────────────────
HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"
OPUS = "claude-opus-4-6"

# ── Extended thinking budget (only used with Opus) ───────────────────────────
THINKING_BUDGET_TOKENS = 10_000

# ── Keywords / phrases that indicate complex scientific reasoning ────────────
_OPUS_KEYWORDS = (
    "explain", "interpret", "compare", "strategy", "analyze results",
    "evaluate", "design strategy", "binding mode", "interface quality",
    "next steps", "mechanism", "recommend", "trade-off", "trade off",
    "pros and cons", "which design", "summarize the results", "scientific",
)

# ── Patterns that match trivial / greeting messages ──────────────────────────
_SIMPLE_PATTERNS = [
    re.compile(r"^(hi|hello|hey|thanks|thank you|ok|okay|yes|no|sure|got it|great)\b", re.I),
    re.compile(r"^(can you|could you|please) (help|assist)\b", re.I),
]


def select_model(user_message: str, iteration: int, has_tool_use: bool = False) -> str:
    """Select the appropriate Claude model for this agent iteration."""
    if iteration > 0 and has_tool_use:
        return SONNET
    return _classify_complexity(user_message)


def should_enable_thinking(model: str) -> bool:
    """Return True if extended thinking should be enabled for *model*."""
    return model == OPUS


def get_thinking_config(model: str) -> dict | None:
    """Return the ``thinking`` parameter dict, or None if disabled."""
    if should_enable_thinking(model):
        return {"type": "enabled", "budget_tokens": THINKING_BUDGET_TOKENS}
    return None


def _classify_complexity(message: str) -> str:
    msg_lower = message.lower().strip()
    for pattern in _SIMPLE_PATTERNS:
        if pattern.match(msg_lower):
            return HAIKU
    if len(msg_lower.split()) <= 5 and not _has_opus_keyword(msg_lower):
        return HAIKU
    if _has_opus_keyword(msg_lower):
        return OPUS
    return SONNET


def _has_opus_keyword(msg_lower: str) -> bool:
    return any(kw in msg_lower for kw in _OPUS_KEYWORDS)

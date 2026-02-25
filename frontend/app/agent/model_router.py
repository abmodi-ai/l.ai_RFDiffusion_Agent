"""
Ligant.ai Multi-Model Router

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
from typing import Tuple

# ── Model IDs ────────────────────────────────────────────────────────────────
HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"
OPUS = "claude-opus-4-6"

# ── Extended thinking budget (only used with Opus) ───────────────────────────
THINKING_BUDGET_TOKENS = 10_000

# ── Keywords / phrases that indicate complex scientific reasoning ────────────
_OPUS_KEYWORDS = (
    "explain",
    "interpret",
    "compare",
    "strategy",
    "analyze results",
    "evaluate",
    "design strategy",
    "binding mode",
    "interface quality",
    "next steps",
    "mechanism",
    "recommend",
    "trade-off",
    "trade off",
    "pros and cons",
    "which design",
    "summarize the results",
    "scientific",
)

# ── Patterns that match trivial / greeting messages ──────────────────────────
_SIMPLE_PATTERNS = [
    re.compile(r"^(hi|hello|hey|thanks|thank you|ok|okay|yes|no|sure|got it|great)\b", re.I),
    re.compile(r"^(can you|could you|please) (help|assist)\b", re.I),
]


def select_model(
    user_message: str,
    iteration: int,
    has_tool_use: bool = False,
) -> str:
    """
    Select the appropriate Claude model for this agent iteration.

    Parameters
    ----------
    user_message : str
        The original user message (used for classification on iteration 0).
    iteration : int
        Current iteration in the agent loop (0-indexed).
    has_tool_use : bool
        Whether the previous response contained ``tool_use`` blocks.

    Returns
    -------
    str
        Model ID string (one of HAIKU, SONNET, OPUS).
    """
    # All tool-dispatch iterations (iteration > 0 with pending tool calls)
    # use Sonnet — fast and capable enough for tool orchestration.
    if iteration > 0 and has_tool_use:
        return SONNET

    # For iteration 0, or a final-response iteration after all tools are done,
    # classify the complexity of the original user message.
    return _classify_complexity(user_message)


def should_enable_thinking(model: str) -> bool:
    """Return True if extended thinking should be enabled for *model*."""
    return model == OPUS


def get_thinking_config(model: str) -> dict | None:
    """
    Return the ``thinking`` parameter dict for ``client.messages.create()``,
    or ``None`` if thinking should be disabled.
    """
    if should_enable_thinking(model):
        return {
            "type": "enabled",
            "budget_tokens": THINKING_BUDGET_TOKENS,
        }
    return None


# ── Private helpers ──────────────────────────────────────────────────────────

def _classify_complexity(message: str) -> str:
    """Classify a user message and return the appropriate model."""
    msg_lower = message.lower().strip()

    # Very short greetings / confirmations → Haiku
    for pattern in _SIMPLE_PATTERNS:
        if pattern.match(msg_lower):
            return HAIKU

    # Short messages (≤ 5 words) without scientific keywords → Haiku
    if len(msg_lower.split()) <= 5 and not _has_opus_keyword(msg_lower):
        return HAIKU

    # Complex scientific reasoning → Opus
    if _has_opus_keyword(msg_lower):
        return OPUS

    # Everything else → Sonnet (sensible default)
    return SONNET


def _has_opus_keyword(msg_lower: str) -> bool:
    """Check whether the message contains any Opus-triggering keywords."""
    return any(kw in msg_lower for kw in _OPUS_KEYWORDS)

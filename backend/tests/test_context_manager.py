"""Tests for the context manager (pruning, compression, summarization)."""

import json

from app.agent.context_manager import (
    MAX_TOOL_RESULT_CHARS,
    compress_tool_result,
    estimate_tokens,
    maybe_summarize_history,
    prune_thinking_blocks,
)


class TestPruneThinkingBlocks:
    def test_strips_thinking_content(self):
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "thinking",
                        "thinking": "This is a long internal thought " * 100,
                        "signature": "sig123",
                    },
                    {"type": "text", "text": "Here is my response."},
                ],
            }
        ]
        result = prune_thinking_blocks(messages)
        thinking_block = result[0]["content"][0]
        assert thinking_block["thinking"] == ""
        assert thinking_block["signature"] == "sig123"

    def test_preserves_text_blocks(self):
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Hello!"},
                ],
            }
        ]
        result = prune_thinking_blocks(messages)
        assert result[0]["content"][0]["text"] == "Hello!"

    def test_preserves_user_messages(self):
        messages = [{"role": "user", "content": "What is protein folding?"}]
        result = prune_thinking_blocks(messages)
        assert result[0]["content"] == "What is protein folding?"

    def test_handles_string_assistant_content(self):
        """Assistant messages with string content should pass through."""
        messages = [{"role": "assistant", "content": "Simple text response"}]
        result = prune_thinking_blocks(messages)
        assert result[0]["content"] == "Simple text response"


class TestCompressToolResult:
    def test_truncates_long_results(self):
        long_result = "x" * 5000
        compressed = compress_tool_result(long_result)
        assert len(compressed) <= MAX_TOOL_RESULT_CHARS
        assert "truncated" in compressed

    def test_preserves_short_results(self):
        short_result = "Short result"
        assert compress_tool_result(short_result) == short_result

    def test_preserves_error_messages(self):
        error_result = json.dumps({"error": "Something went wrong with a very " + "long " * 500 + "message"})
        compressed = compress_tool_result(error_result)
        assert compressed == error_result

    def test_trims_sequence_preview(self):
        data = {
            "chains": {
                "A": {"sequence_preview": "ACDEFGHIKLMNPQRSTVWYLONGSEQUENCEHERE"}
            }
        }
        result_str = json.dumps(data)
        compressed = compress_tool_result(result_str)
        parsed = json.loads(compressed)
        preview = parsed["chains"]["A"]["sequence_preview"]
        assert len(preview) <= 23  # 20 + "..."


class TestMaybeSummarizeHistory:
    def test_no_change_below_threshold(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = maybe_summarize_history(messages)
        assert result == messages

    def test_condenses_long_history(self):
        """Messages over TOKEN_THRESHOLD should be condensed."""
        messages = []
        for i in range(20):
            messages.append({"role": "user", "content": "x" * 20000})
            messages.append({"role": "assistant", "content": "y" * 20000})

        result = maybe_summarize_history(messages)
        # Should be shorter than original
        assert len(result) < len(messages) or any(
            "..." in str(m.get("content", "")) for m in result
        )

    def test_preserves_first_two_and_last_eight(self):
        """Head (2) and tail (8) should be preserved."""
        messages = []
        for i in range(20):
            messages.append({"role": "user", "content": f"user-msg-{i} " + "x" * 20000})
            messages.append({"role": "assistant", "content": f"assistant-msg-{i} " + "y" * 20000})

        result = maybe_summarize_history(messages)
        # First 2 messages should start with original content
        assert "user-msg-0" in result[0]["content"]
        # Last messages should be preserved
        assert "user-msg-19" in result[-2]["content"]


class TestEstimateTokens:
    def test_string_content(self):
        messages = [{"role": "user", "content": "hello world"}]  # 11 chars
        tokens = estimate_tokens(messages)
        assert tokens == 11 // 4

    def test_list_content_with_text(self):
        messages = [
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "a" * 400}],
            }
        ]
        tokens = estimate_tokens(messages)
        assert tokens == 100

    def test_empty_messages(self):
        assert estimate_tokens([]) == 0

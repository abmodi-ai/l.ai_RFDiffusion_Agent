"""Tests for the multi-model router."""

from app.agent.model_router import (
    HAIKU,
    OPUS,
    SONNET,
    get_thinking_config,
    select_model,
    should_enable_thinking,
)


class TestSelectModel:
    """select_model() should route to the correct model tier."""

    def test_greeting_routes_to_haiku(self):
        assert select_model("hello", iteration=0, has_tool_use=False) == HAIKU

    def test_hi_routes_to_haiku(self):
        assert select_model("Hi there!", iteration=0, has_tool_use=False) == HAIKU

    def test_thanks_routes_to_haiku(self):
        assert select_model("thanks", iteration=0, has_tool_use=False) == HAIKU

    def test_short_message_routes_to_haiku(self):
        assert select_model("yes", iteration=0, has_tool_use=False) == HAIKU

    def test_tool_dispatch_routes_to_sonnet(self):
        """After iteration 0 with tool use, always use Sonnet."""
        assert select_model("explain binding modes", iteration=1, has_tool_use=True) == SONNET

    def test_complex_routes_to_opus(self):
        assert select_model("Explain the binding mode analysis results", iteration=0, has_tool_use=False) == OPUS

    def test_interpret_routes_to_opus(self):
        assert select_model("Can you interpret these results?", iteration=0, has_tool_use=False) == OPUS

    def test_strategy_routes_to_opus(self):
        assert select_model("What design strategy should I use for this binder?", iteration=0, has_tool_use=False) == OPUS

    def test_standard_message_routes_to_sonnet(self):
        """Non-trivial, non-complex messages should go to Sonnet."""
        assert select_model("Fetch PDB 1ABC and analyze the chains", iteration=0, has_tool_use=False) == SONNET

    def test_iteration_zero_no_tool_use_classifies(self):
        """Iteration 0 without prior tool use should classify by complexity."""
        result = select_model("Upload my protein file and analyze all chains for binding sites", iteration=0, has_tool_use=False)
        assert result == SONNET

    def test_can_you_help_routes_to_haiku(self):
        assert select_model("Can you help me?", iteration=0, has_tool_use=False) == HAIKU


class TestThinkingConfig:
    """Thinking should only be enabled for Opus."""

    def test_opus_enables_thinking(self):
        assert should_enable_thinking(OPUS) is True

    def test_sonnet_disables_thinking(self):
        assert should_enable_thinking(SONNET) is False

    def test_haiku_disables_thinking(self):
        assert should_enable_thinking(HAIKU) is False

    def test_opus_thinking_config_has_budget(self):
        config = get_thinking_config(OPUS)
        assert config is not None
        assert config["type"] == "enabled"
        assert config["budget_tokens"] > 0

    def test_sonnet_thinking_config_is_none(self):
        assert get_thinking_config(SONNET) is None

    def test_haiku_thinking_config_is_none(self):
        assert get_thinking_config(HAIKU) is None

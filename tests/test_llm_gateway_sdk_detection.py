"""Tests for LLMGateway.sdk_available property."""
import pytest
from unittest.mock import patch

pytestmark = pytest.mark.unit


def test_sdk_available_false_when_package_missing():
    """Returns False when claude_agent_sdk import fails."""
    from src.core.llm_gateway import llm_gateway

    with patch.dict("sys.modules", {"claude_agent_sdk": None}):
        # Force re-check by clearing any cached state
        assert llm_gateway.sdk_available is False


def test_sdk_available_false_when_provider_not_claude_code():
    """Returns False when active provider is not claude-code."""
    from src.core.llm_gateway import llm_gateway

    with patch.object(llm_gateway, "_current_provider_name", "gemini"):
        assert llm_gateway.sdk_available is False


def test_sdk_available_true_when_package_and_provider_match():
    """Returns True when claude_agent_sdk importable AND provider is claude-code."""
    from src.core.llm_gateway import llm_gateway

    # Fake a claude_agent_sdk module in sys.modules
    import types
    fake_sdk = types.ModuleType("claude_agent_sdk")
    with patch.dict("sys.modules", {"claude_agent_sdk": fake_sdk}):
        with patch.object(llm_gateway, "_current_provider_name", "claude-code"):
            assert llm_gateway.sdk_available is True

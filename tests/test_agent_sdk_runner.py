"""Tests for AgentSDKRunner — the bridge between SAGE agents and Claude Agent SDK."""
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit


def test_is_sdk_available_false_without_sdk():
    """When claude_agent_sdk is not importable, is_sdk_available returns False."""
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    with patch.object(runner, "_llm_gateway") as mock_gw:
        mock_gw.sdk_available = False
        assert runner.is_sdk_available() is False


def test_is_sdk_available_true_when_gateway_reports_available():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    with patch.object(runner, "_llm_gateway") as mock_gw:
        mock_gw.sdk_available = True
        assert runner.is_sdk_available() is True


def test_resolve_tools_uses_per_role_sdk_tools_when_present():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    role_config = {
        "name": "Marketing Strategist",
        "system_prompt": "...",
        "sdk_tools": ["Read", "WebSearch"],
    }
    tools = runner._resolve_tools(role_config, task_type=None)
    assert tools == ["Read", "WebSearch"]


def test_resolve_tools_falls_back_to_task_type_mapping():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    role_config = {"name": "Analyst", "system_prompt": "..."}
    tools = runner._resolve_tools(role_config, task_type="analysis")
    assert set(tools) == {"Read", "Grep", "Glob"}


def test_resolve_tools_code_generation_includes_bash():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    role_config = {"name": "Coder", "system_prompt": "..."}
    tools = runner._resolve_tools(role_config, task_type="code_generation")
    assert "Bash" in tools
    assert "Edit" in tools
    assert "Write" in tools


def test_resolve_tools_unknown_task_type_returns_empty():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    role_config = {"name": "Unknown", "system_prompt": "..."}
    tools = runner._resolve_tools(role_config, task_type="unknown_task")
    assert tools == []


def test_build_agent_definition_uses_role_prompt_and_tools():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    role_config = {
        "name": "Security Analyst",
        "description": "Reviews code for security issues",
        "system_prompt": "You are a security expert.",
        "sdk_tools": ["Read", "Grep"],
    }
    agent_def = runner._build_agent_definition("security_analyst", role_config)

    assert agent_def["description"] == "Reviews code for security issues"
    assert agent_def["prompt"] == "You are a security expert."
    assert agent_def["tools"] == ["Read", "Grep"]

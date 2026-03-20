# tests/test_chat_router.py
import pytest
from unittest.mock import patch, MagicMock


def test_parse_answer_response():
    """parse_router_response extracts answer type correctly."""
    from src.core.chat_router import parse_router_response
    raw = '{"type": "answer", "reply": "Proposals are HITL-gated actions."}'
    result = parse_router_response(raw)
    assert result["type"] == "answer"
    assert "Proposals" in result["reply"]


def test_parse_action_response():
    """parse_router_response extracts action type with params."""
    from src.core.chat_router import parse_router_response
    raw = '{"type": "action", "action": "approve_proposal", "params": {"trace_id": "abc"}, "confirmation_prompt": "Approve?"}'
    result = parse_router_response(raw)
    assert result["type"] == "action"
    assert result["action"] == "approve_proposal"
    assert result["params"]["trace_id"] == "abc"
    assert result["confirmation_prompt"] == "Approve?"


def test_parse_malformed_falls_back_to_answer():
    """If LLM returns non-JSON, treat as plain answer."""
    from src.core.chat_router import parse_router_response
    raw = "Sure, here is the explanation."
    result = parse_router_response(raw)
    assert result["type"] == "answer"
    assert result["reply"] == raw


def test_build_router_system_prompt_includes_actions():
    """System prompt contains all action names."""
    from src.core.chat_router import build_router_system_prompt
    prompt = build_router_system_prompt(solution="test", domain="testing", page_context="")
    for action in ["approve_proposal", "reject_proposal", "undo_proposal",
                   "submit_task", "query_knowledge", "propose_yaml_edit"]:
        assert action in prompt


def test_route_calls_llm_and_returns_parsed():
    """route() calls llm_gateway.generate and returns parsed dict."""
    from src.core.chat_router import route
    mock_gw = MagicMock()
    mock_gw.generate.return_value = '{"type": "answer", "reply": "Hello"}'
    with patch("src.core.chat_router.llm_gateway", mock_gw):
        result = route("Hello", solution="test", domain="", page_context="")
    assert result["type"] == "answer"
    assert mock_gw.generate.called

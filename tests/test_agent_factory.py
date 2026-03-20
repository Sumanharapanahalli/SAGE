# tests/test_agent_factory.py
import pytest
from unittest.mock import patch, MagicMock


def test_metaprompt_contains_required_keys():
    """METAPROMPT instructs LLM to return all required fields."""
    from src.core.agent_factory import METAPROMPT
    for key in ["role_key", "name", "system_prompt", "task_types", "output_schema"]:
        assert key in METAPROMPT


def test_jd_to_role_config_parses_valid_response():
    """jd_to_role_config returns a dict with required fields from valid LLM JSON."""
    from src.core.agent_factory import jd_to_role_config
    mock_response = '''{
        "role_key": "security_reviewer",
        "name": "Security Reviewer",
        "description": "Reviews code for OWASP top 10 vulnerabilities",
        "system_prompt": "You are a Security Reviewer...",
        "task_types": [
            {"name": "REVIEW_CODE_SECURITY", "description": "Review code diffs for vulnerabilities"}
        ],
        "output_schema": {"severity": "RED|AMBER|GREEN", "issues": "list"},
        "eval_case": {"input": "SQL query with user input", "expected_keywords": ["injection", "RED"]}
    }'''
    mock_gw = MagicMock()
    mock_gw.generate.return_value = mock_response
    with patch("src.core.agent_factory.llm_gateway", mock_gw):
        result = jd_to_role_config("Senior Security Engineer JD...", solution_context="Node.js API")
    assert result["role_key"] == "security_reviewer"
    assert result["name"] == "Security Reviewer"
    assert len(result["task_types"]) == 1
    assert mock_gw.generate.called


def test_jd_to_role_config_handles_fenced_json():
    """jd_to_role_config strips markdown code fences before parsing."""
    from src.core.agent_factory import jd_to_role_config
    mock_response = '```json\n{"role_key": "qa_engineer", "name": "QA Engineer", "description": "...", "system_prompt": "...", "task_types": [], "output_schema": {}, "eval_case": {"input": "x", "expected_keywords": []}}\n```'
    mock_gw = MagicMock()
    mock_gw.generate.return_value = mock_response
    with patch("src.core.agent_factory.llm_gateway", mock_gw):
        result = jd_to_role_config("QA role...", solution_context="")
    assert result["role_key"] == "qa_engineer"


def test_jd_to_role_config_raises_on_bad_json():
    """jd_to_role_config raises ValueError when LLM returns non-JSON."""
    from src.core.agent_factory import jd_to_role_config
    mock_gw = MagicMock()
    mock_gw.generate.return_value = "Sorry, I cannot process that request."
    with patch("src.core.agent_factory.llm_gateway", mock_gw):
        with pytest.raises(ValueError, match="Could not parse"):
            jd_to_role_config("some JD text", solution_context="")


def test_jd_to_role_config_none_gateway_raises():
    """jd_to_role_config raises RuntimeError when gateway is None."""
    from src.core import agent_factory
    original = agent_factory.llm_gateway
    try:
        agent_factory.llm_gateway = None
        with pytest.raises(RuntimeError, match="LLM gateway"):
            agent_factory.jd_to_role_config("some JD")
    finally:
        agent_factory.llm_gateway = original

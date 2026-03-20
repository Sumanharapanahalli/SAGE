import pytest
from unittest.mock import patch, MagicMock


def test_get_agent_budget_returns_limit():
    """project_loader exposes per-agent budget when declared in project.yaml."""
    from src.core.project_loader import ProjectConfig
    cfg = ProjectConfig.__new__(ProjectConfig)
    cfg._project = {"agent_budgets": {"analyst": {"monthly_calls": 100}}}
    assert cfg.get_agent_budget("analyst") == {"monthly_calls": 100}


def test_get_agent_budget_returns_none_when_absent():
    from src.core.project_loader import ProjectConfig
    cfg = ProjectConfig.__new__(ProjectConfig)
    cfg._project = {}
    assert cfg.get_agent_budget("analyst") is None


def test_budget_exceeded_raises():
    """LLMGateway.generate() raises RuntimeError when agent exceeds monthly call budget."""
    from src.core.llm_gateway import LLMGateway
    gw = LLMGateway()
    # Pre-fill usage so the 2-call budget is already exhausted
    gw._usage["agent_analyst_calls"] = 2
    mock_pc = MagicMock()
    mock_pc.get_agent_budget.return_value = {"monthly_calls": 2}
    with patch("src.core.llm_gateway.project_config", mock_pc):
        with pytest.raises(RuntimeError, match="budget"):
            gw.generate("hello", agent_name="analyst")

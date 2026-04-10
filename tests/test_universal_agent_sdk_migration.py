from unittest.mock import patch

from src.agents.universal import UniversalAgent


def test_universal_agent_routes_through_sdk_bridge():
    agent = UniversalAgent()
    fake_response = (
        '{"summary": "ok", "analysis": "a", "recommendations": [], '
        '"next_steps": [], "severity": "low", "confidence": 0.9}'
    )

    # Mock the role configuration
    mock_roles = {
        "analyst": {
            "name": "Analyst",
            "system_prompt": "You are an analyst assistant.",
            "icon": "🔍"
        }
    }

    with patch.object(agent, "get_roles", return_value=mock_roles), \
         patch("src.agents.universal._sdk_bridge.run_agent", return_value=fake_response) as mock_run:
        result = agent.run(
            role_id="analyst",
            task="analyze signal X",
            context="prior context",
        )

    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs["role_id"] == "analyst"
    assert kwargs["task"] == "analyze signal X"
    assert "prior context" in kwargs["context"]
    assert result["summary"] == "ok"
    assert result["status"] != "error"
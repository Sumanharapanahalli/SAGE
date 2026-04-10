"""
Migration test for AnalystAgent SDK bridge integration (Task 4).
Verifies that analyze_log() routes through _sdk_bridge.run_agent() with correct parameters.
"""

from unittest.mock import patch

from src.agents.analyst import AnalystAgent


def test_analyst_routes_through_sdk_bridge():
    agent = AnalystAgent()
    fake_json = (
        '{"severity": "high", "root_cause_hypothesis": "OOM", '
        '"recommended_action": "restart"}'
    )
    with patch(
        "src.agents.analyst._sdk_bridge.run_agent",
        return_value=fake_json,
    ) as mock_run:
        result = agent.analyze_log("segfault at 0xdeadbeef")
    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs["role_id"] == "analyst"
    assert "segfault" in kwargs["task"]
    assert kwargs["task_type"] == "analysis"
    assert result["severity"] == "high"
    assert "trace_id" in result
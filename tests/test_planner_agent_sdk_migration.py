"""Test that PlannerAgent.create_plan routes through the SDK bridge correctly."""

from unittest.mock import patch

from src.agents.planner import PlannerAgent


def test_planner_create_plan_routes_through_sdk_bridge():
    """Test that PlannerAgent.create_plan uses SDK bridge instead of direct LLM calls."""
    agent = PlannerAgent()

    # Use the framework task types that are defined in PlannerAgent
    fake_response = (
        '[{"task_type": "ANALYZE", "description": "step 1"}, '
        '{"task_type": "DEVELOP", "description": "step 2"}]'
    )

    with patch(
        "src.agents.planner._sdk_bridge.run_agent",
        return_value=fake_response,
    ) as mock_run:
        # Use override_task_types to control what's valid
        plan = agent.create_plan("ship feature X", override_task_types=agent.FRAMEWORK_TASK_TYPES)

    # Verify SDK bridge was called
    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs["role_id"] == "planner"
    assert kwargs["task_type"] == "planning"
    assert "ship feature X" in kwargs["task"]

    # Verify the plan was parsed correctly
    assert isinstance(plan, list)
    assert len(plan) == 2
    assert plan[0]["task_type"] == "ANALYZE"
    assert plan[1]["task_type"] == "DEVELOP"
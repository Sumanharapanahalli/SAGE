from unittest.mock import patch

from src.agents.coder import CodingAgent


def test_coder_implement_step_routes_through_sdk_bridge():
    agent = CodingAgent()
    react_responses = iter(
        [
            "Thought: I need to write a file\n"
            "Action: write_file\n"
            "FinalAnswer: done",
        ]
    )

    def fake_run_agent(role_id, task, context="", *, task_type=None):
        assert role_id == "coder"
        assert task_type in ("code_generation", "implementation")
        return next(react_responses, "Thought: done\nFinalAnswer: complete")

    with patch(
        "src.agents.coder._sdk_bridge.run_agent",
        side_effect=fake_run_agent,
    ) as mock_run:
        result = agent.implement_step(
            step={"description": "write hello.py"},
            plan_trace_id="plan-123",
        )
    assert mock_run.called
    assert "summary" in result
    assert result["plan_trace_id"] == "plan-123"
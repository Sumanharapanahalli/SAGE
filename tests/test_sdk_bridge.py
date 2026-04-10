from unittest.mock import patch, AsyncMock

from src.agents import _sdk_bridge


def test_run_agent_returns_raw_response_string():
    fake_result = {
        "trace_id": "abc",
        "status": "ok",
        "summary": "short summary",
        "raw_response": "full text from model",
    }
    fake_runner = type("R", (), {})()
    fake_runner.run = AsyncMock(return_value=fake_result)
    with patch(
        "src.agents._sdk_bridge.get_agent_sdk_runner",
        return_value=fake_runner,
    ):
        out = _sdk_bridge.run_agent(
            role_id="analyst",
            task="analyze this log",
            context="prior decisions",
            task_type="analysis",
        )
    assert out == "full text from model"
    # Check that context is passed as dict with correct structure
    fake_runner.run.assert_awaited_once_with(
        role_id="analyst",
        task="analyze this log",
        context={"task_type": "analysis", "context_text": "prior decisions"},
    )


def test_run_agent_falls_back_to_summary_when_raw_response_missing():
    fake_runner = type("R", (), {})()
    fake_runner.run = AsyncMock(return_value={"summary": "only summary"})
    with patch(
        "src.agents._sdk_bridge.get_agent_sdk_runner",
        return_value=fake_runner,
    ):
        out = _sdk_bridge.run_agent(role_id="x", task="t")
    assert out == "only summary"
    # Check that context is passed as dict with task_type None for minimal call
    fake_runner.run.assert_awaited_once_with(
        role_id="x",
        task="t",
        context={"task_type": None},
    )


def test_run_agent_returns_empty_string_when_result_empty():
    fake_runner = type("R", (), {})()
    fake_runner.run = AsyncMock(return_value={})
    with patch(
        "src.agents._sdk_bridge.get_agent_sdk_runner",
        return_value=fake_runner,
    ):
        out = _sdk_bridge.run_agent(role_id="x", task="t")
    assert out == ""
    # Check that context is passed as dict with task_type None for minimal call
    fake_runner.run.assert_awaited_once_with(
        role_id="x",
        task="t",
        context={"task_type": None},
    )

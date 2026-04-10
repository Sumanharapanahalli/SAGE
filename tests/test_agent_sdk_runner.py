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


async def test_run_falls_back_to_gateway_when_sdk_unavailable():
    """When SDK is unavailable, run() delegates to LLMGateway.generate()."""
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()

    fake_gateway = MagicMock()
    fake_gateway.sdk_available = False
    fake_gateway.generate.return_value = '{"summary": "ok", "analysis": "done"}'

    fake_role = {
        "name": "Analyst",
        "system_prompt": "You analyze.",
    }

    with patch.object(runner, "_llm_gateway", fake_gateway), \
         patch.object(runner, "_load_role") as mock_load:
        mock_load.return_value = fake_role

        result = await runner.run(
            role_id="analyst",
            task="analyze the logs",
            context={"task_type": "analysis"},
        )

    assert fake_gateway.generate.called
    assert result["status"] in ("fallback_gateway", "success")
    assert result["role_id"] == "analyst"


async def test_run_returns_error_for_unknown_role():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    with patch.object(runner, "_load_role") as mock_load:
        mock_load.return_value = None  # unknown role

        result = await runner.run(
            role_id="does_not_exist",
            task="anything",
            context={},
        )

    assert result["status"] == "error"
    assert "unknown" in result["error"].lower() or "not found" in result["error"].lower()


async def test_gate1_creates_goal_alignment_proposal(tmp_audit_db):
    """Gate 1: SDK path creates a goal_alignment proposal before execution."""
    from src.core.agent_sdk_runner import AgentSDKRunner
    from src.core.proposal_store import get_proposal_store

    runner = AgentSDKRunner()
    fake_gateway = MagicMock()
    fake_gateway.sdk_available = True

    fake_role = {
        "name": "Analyst",
        "system_prompt": "analyze",
        "sdk_tools": ["Read", "Grep"],
    }

    store = get_proposal_store()
    created_proposals = []
    original_create = store.create

    def tracking_create(*args, **kwargs):
        p = original_create(*args, **kwargs)
        created_proposals.append(p)
        return p

    async def fake_sdk_query(agent_def, task, trace_id):
        return "result text"

    with patch.object(runner, "_llm_gateway", fake_gateway), \
         patch.object(runner, "_load_role", return_value=fake_role), \
         patch.object(store, "create", side_effect=tracking_create), \
         patch.object(runner, "_run_sdk_query", side_effect=fake_sdk_query):

        import threading
        import time

        def approve_all_when_ready():
            seen = set()
            for _ in range(200):
                for p in list(created_proposals):
                    if p.trace_id not in seen:
                        seen.add(p.trace_id)
                        time.sleep(0.05)
                        store.approve(p.trace_id, decided_by="test")
                if len(seen) >= 2:
                    return
                time.sleep(0.05)

        threading.Thread(target=approve_all_when_ready, daemon=True).start()

        result = await runner.run(
            role_id="analyst",
            task="look at the logs",
            context={"task_type": "analysis"},
        )

    gate1_proposals = [p for p in created_proposals if p.action_type == "goal_alignment"]
    assert len(gate1_proposals) == 1
    assert result["status"] == "success"


async def test_gate1_rejection_aborts_execution(tmp_audit_db):
    """Gate 1 rejection prevents SDK execution from starting."""
    from src.core.agent_sdk_runner import AgentSDKRunner
    from src.core.proposal_store import get_proposal_store

    runner = AgentSDKRunner()
    fake_gateway = MagicMock()
    fake_gateway.sdk_available = True

    fake_role = {"name": "Analyst", "system_prompt": "analyze", "sdk_tools": ["Read"]}

    store = get_proposal_store()
    created_proposals = []
    original_create = store.create

    def tracking_create(*args, **kwargs):
        p = original_create(*args, **kwargs)
        created_proposals.append(p)
        return p

    sdk_query_called = MagicMock()

    with patch.object(runner, "_llm_gateway", fake_gateway), \
         patch.object(runner, "_load_role", return_value=fake_role), \
         patch.object(store, "create", side_effect=tracking_create), \
         patch.object(runner, "_run_sdk_query", side_effect=sdk_query_called):

        import threading
        import time

        def reject_when_ready():
            for _ in range(100):
                if created_proposals:
                    time.sleep(0.05)
                    store.reject(created_proposals[0].trace_id, decided_by="test",
                                 feedback="out of scope")
                    return
                time.sleep(0.05)

        threading.Thread(target=reject_when_ready, daemon=True).start()

        result = await runner.run(
            role_id="analyst",
            task="do something risky",
            context={"task_type": "analysis"},
        )

    assert result["status"] == "rejected_at_goal"
    assert "out of scope" in result.get("reason", "")
    sdk_query_called.assert_not_called()


async def test_gate2_creates_result_approval_proposal(tmp_audit_db):
    """Gate 2: after SDK execution, runner creates a result_approval proposal."""
    from src.core.agent_sdk_runner import AgentSDKRunner
    from src.core.proposal_store import get_proposal_store
    from src.core.sdk_change_tracker import sdk_change_tracker

    runner = AgentSDKRunner()
    fake_gateway = MagicMock()
    fake_gateway.sdk_available = True

    fake_role = {"name": "Coder", "system_prompt": "code", "sdk_tools": ["Edit"]}

    store = get_proposal_store()
    created_proposals = []
    original_create = store.create

    def tracking_create(*args, **kwargs):
        p = original_create(*args, **kwargs)
        created_proposals.append(p)
        return p

    async def fake_sdk_query(agent_def, task, trace_id):
        # Simulate the SDK modifying a file during execution
        sdk_change_tracker.record(trace_id, "Edit", {"file_path": "src/foo.py"})
        return "implemented"

    with patch.object(runner, "_llm_gateway", fake_gateway), \
         patch.object(runner, "_load_role", return_value=fake_role), \
         patch.object(store, "create", side_effect=tracking_create), \
         patch.object(runner, "_run_sdk_query", side_effect=fake_sdk_query):

        import threading
        import time

        def approve_all_when_ready():
            seen = set()
            for _ in range(200):
                for p in list(created_proposals):
                    if p.trace_id not in seen:
                        seen.add(p.trace_id)
                        time.sleep(0.05)
                        store.approve(p.trace_id, decided_by="test")
                if len(seen) >= 2:
                    return
                time.sleep(0.05)

        threading.Thread(target=approve_all_when_ready, daemon=True).start()

        result = await runner.run(
            role_id="coder",
            task="implement foo",
            context={"task_type": "implementation"},
        )

    gate2 = [p for p in created_proposals if p.action_type == "result_approval"]
    assert len(gate2) == 1
    assert "src/foo.py" in str(gate2[0].payload.get("files_modified", []))
    assert result["status"] == "success"


async def test_gate2_rejection_marks_result_rejected(tmp_audit_db):
    """Gate 2 rejection returns status=rejected_at_result with the reason."""
    from src.core.agent_sdk_runner import AgentSDKRunner
    from src.core.proposal_store import get_proposal_store

    runner = AgentSDKRunner()
    fake_gateway = MagicMock()
    fake_gateway.sdk_available = True

    fake_role = {"name": "Coder", "system_prompt": "code", "sdk_tools": ["Edit"]}

    store = get_proposal_store()
    created_proposals = []
    original_create = store.create

    def tracking_create(*args, **kwargs):
        p = original_create(*args, **kwargs)
        created_proposals.append(p)
        return p

    async def fake_sdk_query(agent_def, task, trace_id):
        return "some result"

    with patch.object(runner, "_llm_gateway", fake_gateway), \
         patch.object(runner, "_load_role", return_value=fake_role), \
         patch.object(store, "create", side_effect=tracking_create), \
         patch.object(runner, "_run_sdk_query", side_effect=fake_sdk_query):

        import threading
        import time

        def decide_proposals():
            seen = set()
            for _ in range(200):
                for p in list(created_proposals):
                    if p.trace_id not in seen:
                        seen.add(p.trace_id)
                        time.sleep(0.05)
                        if p.action_type == "goal_alignment":
                            store.approve(p.trace_id, decided_by="test")
                        else:
                            store.reject(p.trace_id, decided_by="test", feedback="bad output")
                if len(seen) >= 2:
                    return
                time.sleep(0.05)

        threading.Thread(target=decide_proposals, daemon=True).start()

        result = await runner.run(
            role_id="coder",
            task="do it",
            context={"task_type": "implementation"},
        )

    assert result["status"] == "rejected_at_result"
    assert "bad output" in result.get("reason", "")

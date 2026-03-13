"""
SAGE Framework — Phase 4 AutoGen Code Agent Tests
==================================================
Tests for:
  - AutoGenRunner.plan() returns awaiting_approval with plan + code
  - AutoGenRunner.plan() uses LLM fallback when AutoGen not installed
  - AutoGenRunner.approve() transitions status to approved
  - AutoGenRunner.approve() unknown run_id returns error
  - AutoGenRunner.execute() on unapproved run returns error
  - AutoGenRunner.execute() on approved run calls sandbox and returns output
  - AutoGenRunner.execute() with Docker available calls _run_in_docker
  - AutoGenRunner.execute() with Docker unavailable falls back to _run_local
  - AutoGenRunner.get_status() returns correct status dict
  - AutoGenRunner.get_status() unknown run returns error
  - POST /code/plan returns 200 with awaiting_approval
  - POST /code/plan missing task returns 400
  - POST /code/approve returns 200 for valid run
  - POST /code/approve missing run_id returns 400
  - POST /code/execute returns 200 for approved run
  - POST /code/execute missing run_id returns 400
  - GET /code/status/{run_id} returns 200 for known run
  - GET /code/status/{run_id} returns 404 for unknown run
  - TaskWorker dispatches CODE_TASK to autogen_runner.plan()
  - CODE_TASK missing task description raises ValueError
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_runner():
    from src.integrations.autogen_runner import AutoGenRunner
    return AutoGenRunner()


def _client():
    from src.interface.api import app
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# AutoGenRunner unit tests
# ---------------------------------------------------------------------------

class TestAutoGenRunner:

    def test_plan_returns_awaiting_approval(self):
        """plan() must always return status=awaiting_approval."""
        runner = _fresh_runner()
        with patch("src.integrations.autogen_runner._HAS_AUTOGEN", False), \
             patch("src.integrations.autogen_runner._plan_via_llm", return_value="Plan text\n```python\nprint('hi')\n```"), \
             patch.object(runner, "_audit"):
            result = runner.plan("Write hello world")
        assert result["status"] == "awaiting_approval"
        assert "run_id" in result
        assert result["task"] == "Write hello world"

    def test_plan_extracts_code_block(self):
        """plan() must extract the Python code block from the plan text."""
        runner = _fresh_runner()
        plan_text = "Explanation here.\n```python\nprint('hello')\n```"
        with patch("src.integrations.autogen_runner._HAS_AUTOGEN", False), \
             patch("src.integrations.autogen_runner._plan_via_llm", return_value=plan_text), \
             patch.object(runner, "_audit"):
            result = runner.plan("Say hello")
        assert result["code"] == "print('hello')"

    def test_plan_without_code_block_still_returns(self):
        """plan() with no code block returns empty code string, not an error."""
        runner = _fresh_runner()
        with patch("src.integrations.autogen_runner._HAS_AUTOGEN", False), \
             patch("src.integrations.autogen_runner._plan_via_llm", return_value="No code here"), \
             patch.object(runner, "_audit"):
            result = runner.plan("Explain something")
        assert result["status"] == "awaiting_approval"
        assert result["code"] == ""

    def test_approve_transitions_to_approved(self):
        """approve() must change status from awaiting_approval to approved."""
        runner = _fresh_runner()
        with patch("src.integrations.autogen_runner._HAS_AUTOGEN", False), \
             patch("src.integrations.autogen_runner._plan_via_llm", return_value="```python\npass\n```"), \
             patch.object(runner, "_audit"):
            plan = runner.plan("test task")

        result = runner.approve(plan["run_id"], comment="Looks good")
        assert result["status"] == "approved"
        assert runner._runs[plan["run_id"]]["status"] == "approved"

    def test_approve_unknown_run_returns_error(self):
        """approve() with unknown run_id must return an error dict."""
        runner = _fresh_runner()
        result = runner.approve("nonexistent_run")
        assert "error" in result

    def test_execute_unapproved_run_returns_error(self):
        """execute() on a run still awaiting_approval must return an error."""
        runner = _fresh_runner()
        with patch("src.integrations.autogen_runner._HAS_AUTOGEN", False), \
             patch("src.integrations.autogen_runner._plan_via_llm", return_value="```python\npass\n```"), \
             patch.object(runner, "_audit"):
            plan = runner.plan("test")

        result = runner.execute(plan["run_id"])
        assert "error" in result
        assert "approved" in result["error"].lower()

    def test_execute_approved_run_calls_sandbox(self):
        """execute() on an approved run must call the sandbox and return output."""
        runner = _fresh_runner()
        with patch("src.integrations.autogen_runner._HAS_AUTOGEN", False), \
             patch("src.integrations.autogen_runner._plan_via_llm", return_value="```python\nprint(1+1)\n```"), \
             patch.object(runner, "_audit"):
            plan = runner.plan("add numbers")

        runner.approve(plan["run_id"])

        mock_output = {"stdout": "2\n", "stderr": "", "returncode": 0, "sandbox": "docker"}
        with patch("src.integrations.autogen_runner._check_docker", return_value=True), \
             patch("src.integrations.autogen_runner._run_in_docker", return_value=mock_output), \
             patch.object(runner, "_audit"):
            result = runner.execute(plan["run_id"])

        assert result["status"] == "completed"
        assert result["output"]["stdout"] == "2\n"

    def test_execute_uses_local_when_docker_unavailable(self):
        """execute() must fall back to local subprocess when Docker is not available."""
        runner = _fresh_runner()
        with patch("src.integrations.autogen_runner._HAS_AUTOGEN", False), \
             patch("src.integrations.autogen_runner._plan_via_llm", return_value="```python\nprint('ok')\n```"), \
             patch.object(runner, "_audit"):
            plan = runner.plan("test local")

        runner.approve(plan["run_id"])

        mock_output = {"stdout": "ok\n", "stderr": "", "returncode": 0, "sandbox": "local_subprocess"}
        with patch("src.integrations.autogen_runner._check_docker", return_value=False), \
             patch("src.integrations.autogen_runner._run_local", return_value=mock_output), \
             patch.object(runner, "_audit"):
            result = runner.execute(plan["run_id"])

        assert result["output"]["sandbox"] == "local_subprocess"

    def test_execute_marks_error_on_nonzero_returncode(self):
        """execute() must set status=error when sandbox returns non-zero exit code."""
        runner = _fresh_runner()
        with patch("src.integrations.autogen_runner._HAS_AUTOGEN", False), \
             patch("src.integrations.autogen_runner._plan_via_llm", return_value="```python\nraise RuntimeError('boom')\n```"), \
             patch.object(runner, "_audit"):
            plan = runner.plan("bad code")

        runner.approve(plan["run_id"])

        mock_output = {"stdout": "", "stderr": "RuntimeError: boom", "returncode": 1, "sandbox": "docker"}
        with patch("src.integrations.autogen_runner._check_docker", return_value=True), \
             patch("src.integrations.autogen_runner._run_in_docker", return_value=mock_output), \
             patch.object(runner, "_audit"):
            result = runner.execute(plan["run_id"])

        assert result["status"] == "error"

    def test_get_status_known_run(self):
        """get_status() returns correct dict for a known run."""
        runner = _fresh_runner()
        with patch("src.integrations.autogen_runner._HAS_AUTOGEN", False), \
             patch("src.integrations.autogen_runner._plan_via_llm", return_value="```python\npass\n```"), \
             patch.object(runner, "_audit"):
            plan = runner.plan("status test")

        status = runner.get_status(plan["run_id"])
        assert status["run_id"] == plan["run_id"]
        assert status["status"] == "awaiting_approval"
        assert status["has_code"] is True

    def test_get_status_unknown_run_returns_error(self):
        """get_status() for unknown run_id must return error dict."""
        runner = _fresh_runner()
        result = runner.get_status("no_such_run")
        assert "error" in result


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestCodeAPIEndpoints:

    def test_code_plan_returns_200(self):
        """POST /code/plan with valid task must return 200 with awaiting_approval."""
        import src.integrations.autogen_runner as ar_module
        mock_runner = MagicMock()
        mock_runner.plan.return_value = {
            "run_id": "run_code_1",
            "status": "awaiting_approval",
            "task": "hello task",
            "plan": "Plan text",
            "code": "print('hi')",
            "autogen": False,
        }
        with patch.object(ar_module, "autogen_runner", mock_runner):
            resp = _client().post("/code/plan", json={"task": "hello task"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "awaiting_approval"
        assert data["run_id"] == "run_code_1"

    def test_code_plan_missing_task_returns_400(self):
        """POST /code/plan without task must return 400."""
        resp = _client().post("/code/plan", json={})
        assert resp.status_code == 400

    def test_code_approve_returns_200(self):
        """POST /code/approve with valid run_id must return 200."""
        import src.integrations.autogen_runner as ar_module
        mock_runner = MagicMock()
        mock_runner.approve.return_value = {"run_id": "run_code_1", "status": "approved"}
        with patch.object(ar_module, "autogen_runner", mock_runner):
            resp = _client().post("/code/approve", json={"run_id": "run_code_1"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_code_approve_missing_run_id_returns_400(self):
        """POST /code/approve without run_id must return 400."""
        resp = _client().post("/code/approve", json={})
        assert resp.status_code == 400

    def test_code_approve_error_returns_400(self):
        """POST /code/approve when runner returns error must return 400."""
        import src.integrations.autogen_runner as ar_module
        mock_runner = MagicMock()
        mock_runner.approve.return_value = {"error": "Run not found", "run_id": "bad_id"}
        with patch.object(ar_module, "autogen_runner", mock_runner):
            resp = _client().post("/code/approve", json={"run_id": "bad_id"})
        assert resp.status_code == 400

    def test_code_execute_returns_200_for_approved_run(self):
        """POST /code/execute returns 200 for an approved run."""
        import src.integrations.autogen_runner as ar_module
        mock_runner = MagicMock()
        mock_runner.execute.return_value = {
            "run_id": "run_code_1",
            "status": "completed",
            "task": "hello task",
            "output": {"stdout": "hi\n", "returncode": 0, "sandbox": "docker"},
        }
        with patch.object(ar_module, "autogen_runner", mock_runner):
            resp = _client().post("/code/execute", json={"run_id": "run_code_1"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_code_execute_missing_run_id_returns_400(self):
        """POST /code/execute without run_id must return 400."""
        resp = _client().post("/code/execute", json={})
        assert resp.status_code == 400

    def test_code_execute_unapproved_returns_400(self):
        """POST /code/execute when runner returns error must return 400."""
        import src.integrations.autogen_runner as ar_module
        mock_runner = MagicMock()
        mock_runner.execute.return_value = {
            "error": "Run 'x' has not been approved",
            "run_id": "x",
        }
        with patch.object(ar_module, "autogen_runner", mock_runner):
            resp = _client().post("/code/execute", json={"run_id": "x"})
        assert resp.status_code == 400

    def test_code_status_known_run_returns_200(self):
        """GET /code/status/{run_id} for known run must return 200."""
        import src.integrations.autogen_runner as ar_module
        mock_runner = MagicMock()
        mock_runner.get_status.return_value = {
            "run_id": "r1",
            "status": "awaiting_approval",
            "task": "some task",
            "has_code": True,
        }
        with patch.object(ar_module, "autogen_runner", mock_runner):
            resp = _client().get("/code/status/r1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "awaiting_approval"

    def test_code_status_unknown_run_returns_404(self):
        """GET /code/status/{run_id} for unknown run must return 404."""
        import src.integrations.autogen_runner as ar_module
        mock_runner = MagicMock()
        mock_runner.get_status.return_value = {"error": "Run 'x' not found", "run_id": "x"}
        with patch.object(ar_module, "autogen_runner", mock_runner):
            resp = _client().get("/code/status/x")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TaskWorker CODE_TASK dispatch
# ---------------------------------------------------------------------------

class TestCodeTaskDispatch:

    def test_code_task_dispatched_to_autogen_runner(self):
        """CODE_TASK must call autogen_runner.plan() and return plan result."""
        from src.core.queue_manager import TaskWorker, TaskQueue, Task

        mock_q = MagicMock(spec=TaskQueue)
        worker = TaskWorker.__new__(TaskWorker)
        worker._queue = mock_q
        worker.logger = __import__("logging").getLogger("test")

        task = Task.__new__(Task)
        task.task_type = "CODE_TASK"
        task.payload = {"task": "Write a fibonacci function"}

        import src.integrations.autogen_runner as ar_module
        mock_runner = MagicMock()
        mock_runner.plan.return_value = {
            "run_id": "r1",
            "status": "awaiting_approval",
            "plan": "Here's how...",
        }

        with patch.object(ar_module, "autogen_runner", mock_runner):
            result = worker._dispatch(task)

        mock_runner.plan.assert_called_once_with("Write a fibonacci function", trace_id=None)
        assert result["status"] == "awaiting_approval"

    def test_code_task_missing_description_raises(self):
        """CODE_TASK without 'task' key must raise ValueError."""
        from src.core.queue_manager import TaskWorker, TaskQueue, Task

        mock_q = MagicMock(spec=TaskQueue)
        worker = TaskWorker.__new__(TaskWorker)
        worker._queue = mock_q
        worker.logger = __import__("logging").getLogger("test")

        task = Task.__new__(Task)
        task.task_type = "CODE_TASK"
        task.payload = {}

        with pytest.raises(ValueError, match="task"):
            worker._dispatch(task)

"""
SAGE Framework — Phase 3 LangGraph Orchestration Tests
========================================================
Tests for:
  - LangGraphRunner.list_workflows() returns list (empty when no dir)
  - LangGraphRunner.run() with unknown workflow returns error dict
  - LangGraphRunner.run() with mock workflow returns completed status
  - LangGraphRunner.run() with interrupting workflow returns awaiting_approval
  - LangGraphRunner.resume() advances an interrupted workflow
  - LangGraphRunner.get_status() returns correct status
  - POST /workflow/run returns 200 on valid request
  - POST /workflow/run returns 400 on missing workflow_name
  - POST /workflow/resume returns 200 when run is awaiting_approval
  - GET /workflow/status/{run_id} returns 200 on known run
  - GET /workflow/status/{run_id} returns 404 on unknown run
  - GET /workflow/list returns tools/count shape
  - TaskWorker dispatches WORKFLOW task type correctly
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_runner():
    from src.integrations.langgraph_runner import LangGraphRunner
    return LangGraphRunner()


def _client():
    from src.interface.api import app
    return TestClient(app, raise_server_exceptions=False)


def _mock_completed_graph(return_value: dict):
    """Return a mock LangGraph compiled graph that always completes."""
    g = MagicMock()
    g.invoke.return_value = return_value
    # get_state returns object with next=() → not interrupted
    state_mock = MagicMock()
    state_mock.next = ()
    g.get_state.return_value = state_mock
    return g


def _mock_interrupting_graph(return_value: dict):
    """Return a mock graph that returns awaiting_approval on first invoke."""
    g = MagicMock()
    g.invoke.return_value = return_value
    # get_state returns next=("finalize",) on first call → interrupted
    #              returns next=()           on second call → completed
    state_interrupted = MagicMock()
    state_interrupted.next = ("finalize",)
    state_done = MagicMock()
    state_done.next = ()
    g.get_state.side_effect = [state_interrupted, state_done]
    return g


# ---------------------------------------------------------------------------
# LangGraphRunner unit tests
# ---------------------------------------------------------------------------

class TestLangGraphRunner:

    def test_list_workflows_empty_when_no_dir(self):
        """list_workflows() must return [] when no workflows/ dir exists."""
        runner = _fresh_runner()
        with patch.object(runner, "_get_workflows_dir", return_value="/nonexistent/path"):
            workflows = runner.list_workflows()
        assert isinstance(workflows, list)
        assert len(workflows) == 0

    def test_run_unknown_workflow_returns_error(self):
        """run() with unknown workflow name must return an error dict."""
        runner = _fresh_runner()
        with patch.object(runner, "_get_workflows_dir", return_value="/nonexistent/path"):
            result = runner.run("nonexistent_workflow", {})
        assert "error" in result
        assert "nonexistent_workflow" in result["error"]

    def test_run_known_workflow_returns_completed(self):
        """run() with a registered mock workflow must return status=completed."""
        runner = _fresh_runner()
        runner._loaded_solution = "test"
        runner._workflows["simple"] = _mock_completed_graph({"analysis": "done"})
        runner._checkpointer = None  # no checkpointer needed for mock

        with patch.object(runner, "load", return_value=1), \
             patch.object(runner, "_audit"):
            result = runner.run("simple", {"task": "test input"})

        assert result["status"] == "completed"
        assert result["run_id"] is not None
        assert result["workflow_name"] == "simple"

    def test_run_interrupting_workflow_returns_awaiting_approval(self):
        """run() with a graph that interrupts must return status=awaiting_approval."""
        runner = _fresh_runner()
        runner._loaded_solution = "test"
        runner._workflows["review"] = _mock_interrupting_graph({"analysis": "needs review"})
        runner._checkpointer = None

        with patch.object(runner, "load", return_value=1), \
             patch.object(runner, "_audit"):
            result = runner.run("review", {"task": "test"})

        assert result["status"] == "awaiting_approval"
        assert "run_id" in result

    def test_resume_advances_interrupted_workflow(self):
        """resume() must call invoke again and return completed when not interrupted."""
        runner = _fresh_runner()
        runner._loaded_solution = "test"
        graph = _mock_interrupting_graph({"analysis": "reviewed"})
        runner._workflows["review"] = graph

        with patch.object(runner, "load", return_value=1), \
             patch.object(runner, "_audit"):
            first = runner.run("review", {"task": "check this"})

        run_id = first["run_id"]
        assert first["status"] == "awaiting_approval"

        with patch.object(runner, "_audit"):
            second = runner.resume(run_id, {"approved": True, "comment": "LGTM"})

        assert second["status"] == "completed"
        assert second["run_id"] == run_id

    def test_resume_unknown_run_returns_error(self):
        """resume() with an unknown run_id must return an error dict."""
        runner = _fresh_runner()
        result = runner.resume("nonexistent_run_id")
        assert "error" in result

    def test_resume_non_interrupted_run_returns_error(self):
        """resume() on a completed run must return error (not awaiting_approval)."""
        runner = _fresh_runner()
        runner._loaded_solution = "test"
        runner._workflows["simple"] = _mock_completed_graph({"analysis": "done"})
        runner._checkpointer = None

        with patch.object(runner, "load", return_value=1), \
             patch.object(runner, "_audit"):
            first = runner.run("simple", {})

        result = runner.resume(first["run_id"], {})
        assert "error" in result

    def test_get_status_known_run(self):
        """get_status() returns correct dict for a known run_id."""
        runner = _fresh_runner()
        runner._loaded_solution = "test"
        runner._workflows["simple"] = _mock_completed_graph({"done": True})
        runner._checkpointer = None

        with patch.object(runner, "load", return_value=1), \
             patch.object(runner, "_audit"):
            run = runner.run("simple", {})

        status = runner.get_status(run["run_id"])
        assert status["run_id"] == run["run_id"]
        assert status["status"] == "completed"
        assert status["workflow_name"] == "simple"

    def test_get_status_unknown_run_returns_error(self):
        """get_status() for unknown run_id must return error dict."""
        runner = _fresh_runner()
        result = runner.get_status("no_such_run")
        assert "error" in result


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestWorkflowAPIEndpoints:

    def test_workflow_list_returns_json(self):
        """GET /workflow/list must return JSON with 'workflows' and 'count'."""
        import src.integrations.langgraph_runner as lr_module
        mock_runner = MagicMock()
        mock_runner.list_workflows.return_value = [{"name": "analysis_workflow"}]
        with patch.object(lr_module, "langgraph_runner", mock_runner):
            resp = _client().get("/workflow/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "workflows" in data
        assert "count" in data
        assert data["count"] == 1

    def test_workflow_run_returns_200(self):
        """POST /workflow/run with valid body must return 200."""
        import src.integrations.langgraph_runner as lr_module
        mock_runner = MagicMock()
        mock_runner.run.return_value = {
            "run_id": "run_abc",
            "status": "completed",
            "workflow_name": "analysis_workflow",
            "result": {"analysis": "ok"},
        }
        with patch.object(lr_module, "langgraph_runner", mock_runner):
            resp = _client().post("/workflow/run", json={
                "workflow_name": "analysis_workflow",
                "state": {"task": "check logs"},
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "run_abc"
        assert data["status"] == "completed"

    def test_workflow_run_missing_name_returns_400(self):
        """POST /workflow/run without workflow_name must return 400."""
        resp = _client().post("/workflow/run", json={"state": {}})
        assert resp.status_code == 400

    def test_workflow_run_error_returns_400(self):
        """POST /workflow/run when runner returns error must return 400."""
        import src.integrations.langgraph_runner as lr_module
        mock_runner = MagicMock()
        mock_runner.run.return_value = {"error": "Workflow not found", "run_id": "x"}
        with patch.object(lr_module, "langgraph_runner", mock_runner):
            resp = _client().post("/workflow/run", json={"workflow_name": "bad_wf"})
        assert resp.status_code == 400

    def test_workflow_resume_returns_200(self):
        """POST /workflow/resume returns 200 when runner succeeds."""
        import src.integrations.langgraph_runner as lr_module
        mock_runner = MagicMock()
        mock_runner.resume.return_value = {
            "run_id": "run_abc",
            "status": "completed",
            "workflow_name": "analysis_workflow",
            "result": {"final_output": "approved"},
        }
        with patch.object(lr_module, "langgraph_runner", mock_runner):
            resp = _client().post("/workflow/resume", json={
                "run_id": "run_abc",
                "feedback": {"approved": True},
            })
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_workflow_resume_missing_run_id_returns_400(self):
        """POST /workflow/resume without run_id must return 400."""
        resp = _client().post("/workflow/resume", json={"feedback": {}})
        assert resp.status_code == 400

    def test_workflow_status_known_run_returns_200(self):
        """GET /workflow/status/{run_id} for known run must return 200."""
        import src.integrations.langgraph_runner as lr_module
        mock_runner = MagicMock()
        mock_runner.get_status.return_value = {
            "run_id": "run_abc",
            "status": "awaiting_approval",
            "workflow_name": "analysis_workflow",
        }
        with patch.object(lr_module, "langgraph_runner", mock_runner):
            resp = _client().get("/workflow/status/run_abc")
        assert resp.status_code == 200
        assert resp.json()["status"] == "awaiting_approval"

    def test_workflow_status_unknown_run_returns_404(self):
        """GET /workflow/status/{run_id} for unknown run must return 404."""
        import src.integrations.langgraph_runner as lr_module
        mock_runner = MagicMock()
        mock_runner.get_status.return_value = {
            "error": "Run 'xyz' not found",
            "run_id": "xyz",
        }
        with patch.object(lr_module, "langgraph_runner", mock_runner):
            resp = _client().get("/workflow/status/xyz")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TaskWorker WORKFLOW dispatch
# ---------------------------------------------------------------------------

class TestWorkflowTaskDispatch:

    def test_workflow_task_dispatched_to_langgraph_runner(self):
        """WORKFLOW task type must call langgraph_runner.run() and return result."""
        from src.core.queue_manager import TaskWorker, TaskQueue
        from src.core.queue_manager import Task

        mock_q = MagicMock(spec=TaskQueue)
        worker = TaskWorker.__new__(TaskWorker)
        worker._queue = mock_q
        worker.logger = __import__("logging").getLogger("test")

        task = Task.__new__(Task)
        task.task_type = "WORKFLOW"
        task.payload = {"workflow_name": "analysis_workflow", "state": {"task": "check"}}

        import src.integrations.langgraph_runner as lr_module
        mock_runner = MagicMock()
        mock_runner.run.return_value = {"run_id": "r1", "status": "completed"}

        with patch.object(lr_module, "langgraph_runner", mock_runner):
            result = worker._dispatch(task)

        mock_runner.run.assert_called_once_with("analysis_workflow", {"task": "check"})
        assert result["status"] == "completed"

    def test_workflow_task_missing_name_raises(self):
        """WORKFLOW task missing workflow_name must raise ValueError."""
        from src.core.queue_manager import TaskWorker, TaskQueue, Task

        mock_q = MagicMock(spec=TaskQueue)
        worker = TaskWorker.__new__(TaskWorker)
        worker._queue = mock_q
        worker.logger = __import__("logging").getLogger("test")

        task = Task.__new__(Task)
        task.task_type = "WORKFLOW"
        task.payload = {}

        with pytest.raises(ValueError, match="workflow_name"):
            worker._dispatch(task)

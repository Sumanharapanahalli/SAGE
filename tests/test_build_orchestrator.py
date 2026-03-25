"""
SAGE Framework — Build Orchestrator Tests (TDD)
=================================================
Tests for:
  - BuildOrchestrator.start() returns run_id + plan + critic scores
  - BuildOrchestrator.start() handles empty plan from planner
  - BuildOrchestrator.start() sets state to awaiting_plan on success
  - BuildOrchestrator.start() includes HITL level in response
  - BuildOrchestrator.approve_plan() triggers scaffold + execution
  - BuildOrchestrator.approve_plan() rejects when not awaiting_plan
  - BuildOrchestrator.approve_plan() unknown run returns error
  - BuildOrchestrator.approve_build() finalizes and completes
  - BuildOrchestrator.approve_build() rejects when not awaiting_build
  - BuildOrchestrator.get_status() returns full run summary
  - BuildOrchestrator.get_status() returns error for unknown run
  - BuildOrchestrator.list_runs() returns all runs
  - BuildOrchestrator.list_runs() returns empty when no runs
  - _decompose() calls PlannerAgent with BUILD_TASK_TYPES
  - _decompose() enriches tasks with acceptance criteria
  - _decompose() enriches tasks with agent routing
  - _decompose() enriches tasks with dependencies
  - _decompose() includes agent context in planner prompt
  - _build_agent_context() includes framework agents
  - _build_agent_context() includes agentic patterns
  - _build_agent_context() includes solution-defined roles
  - _compute_waves() produces correct waves from dependencies
  - _compute_waves() handles circular dependencies
  - _compute_waves() handles empty plan
  - _compute_waves() independent tasks in one wave
  - _route_to_agent() enriches task with acceptance criteria
  - _scaffold() creates directory structure
  - _scaffold() skips when no workspace_dir
  - _critic_review_plan() calls critic with threshold
  - _critic_review_code() handles empty code
  - _finalize() stores feedback in vector memory
  - BUILD_TASK_TYPES includes AGENTIC type
  - AGENTIC_PATTERNS registry is populated
  - HITL_LEVELS has three granularity levels
  - DEFAULT_ACCEPTANCE_CRITERIA covers all task types
  - API POST /build/start returns run with plan
  - API GET /build/status/{run_id} returns status
  - API POST /build/approve/{run_id} approves plan
  - API GET /build/runs returns list
  - API GET /build/status/unknown returns 404
  - API POST /build/approve when not awaiting returns 400
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_orchestrator():
    import tempfile
    from src.integrations.build_orchestrator import BuildOrchestrator
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return BuildOrchestrator(checkpoint_db=tmp.name)


def _client():
    from src.interface.api import app
    return TestClient(app, raise_server_exceptions=False)


MOCK_PLAN = [
    {"step": 1, "task_type": "DATABASE", "description": "Create schema", "payload": {}},
    {"step": 2, "task_type": "BACKEND", "description": "Build API", "payload": {}, "depends_on": [1]},
    {"step": 3, "task_type": "FRONTEND", "description": "Build UI", "payload": {}, "depends_on": [2]},
    {"step": 4, "task_type": "TESTS", "description": "Write tests", "payload": {}, "depends_on": [2]},
]

MOCK_CRITIC_RESULT = {
    "passed": True, "final_score": 85, "iterations": 1,
    "history": [{"score": 85, "iteration": 1}],
    "final_review": {"score": 85, "summary": "Looks good"},
    "threshold": 70,
}

MOCK_BUILD_RESULT = {
    "status": "completed", "tier": "llm_react", "code": "x=1",
    "files_changed": ["app.py"], "output": {},
}


# ---------------------------------------------------------------------------
# BuildOrchestrator.start()
# ---------------------------------------------------------------------------

class TestStart:

    def test_returns_run_id_and_plan(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            result = orch.start("Build a todo app")
            assert "run_id" in result
            assert result["task_count"] == 4
            assert result["state"] == "awaiting_plan"

    def test_handles_empty_plan(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=[]), \
             patch.object(orch, "_audit"):
            result = orch.start("Build something impossible")
            assert result["state"] == "failed"
            assert result["error"] is not None

    def test_includes_hitl_level(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            result = orch.start("Build app", hitl_level="strict")
            assert result["hitl_level"] == "strict"
            assert "wave" in result["hitl_gates"]

    def test_critic_scores_in_response(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            result = orch.start("Build a chat app")
            assert len(result["critic_scores"]) == 1
            assert result["critic_scores"][0]["phase"] == "plan"
            assert result["critic_scores"][0]["score"] == 85

    def test_default_solution_name(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            result = orch.start("test")
            assert result["solution_name"].startswith("build_")

    def test_custom_solution_name(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            result = orch.start("test", solution_name="my_app")
            assert result["solution_name"] == "my_app"


# ---------------------------------------------------------------------------
# BuildOrchestrator.approve_plan()
# ---------------------------------------------------------------------------

class TestApprovePlan:

    def test_triggers_execution(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_scaffold", return_value={"status": "skipped"}), \
             patch.object(orch, "_execute_agents"), \
             patch.object(orch, "_critic_review_code", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_integrate", return_value={"status": "completed"}), \
             patch.object(orch, "_critic_review_integration", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            start_result = orch.start("Build app")
            result = orch.approve_plan(start_result["run_id"])
            assert result["state"] == "awaiting_build"

    def test_rejects_when_not_awaiting(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=[]), \
             patch.object(orch, "_audit"):
            start_result = orch.start("test")  # state=failed
            result = orch.approve_plan(start_result["run_id"])
            assert "error" in result

    def test_unknown_run_returns_error(self):
        orch = _fresh_orchestrator()
        result = orch.approve_plan("nonexistent-id")
        assert "error" in result


# ---------------------------------------------------------------------------
# BuildOrchestrator.approve_build()
# ---------------------------------------------------------------------------

class TestApproveBuild:

    def test_completes_build(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_scaffold", return_value={"status": "skipped"}), \
             patch.object(orch, "_execute_agents"), \
             patch.object(orch, "_critic_review_code", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_integrate", return_value={"status": "completed"}), \
             patch.object(orch, "_critic_review_integration", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_finalize"), \
             patch.object(orch, "_audit"):
            start_result = orch.start("Build app")
            orch.approve_plan(start_result["run_id"])
            result = orch.approve_build(start_result["run_id"])
            assert result["state"] == "completed"

    def test_rejects_when_not_awaiting(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            start_result = orch.start("test")  # state=awaiting_plan, not awaiting_build
            result = orch.approve_build(start_result["run_id"])
            assert "error" in result


# ---------------------------------------------------------------------------
# BuildOrchestrator.get_status() and list_runs()
# ---------------------------------------------------------------------------

class TestStatusAndList:

    def test_get_status_returns_summary(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            start_result = orch.start("test")
            status = orch.get_status(start_result["run_id"])
            assert status["run_id"] == start_result["run_id"]
            assert "plan" in status
            assert "critic_scores" in status

    def test_get_status_unknown_run(self):
        orch = _fresh_orchestrator()
        result = orch.get_status("nonexistent")
        assert "error" in result

    def test_list_runs_returns_all(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            orch.start("App 1", solution_name="app1")
            orch.start("App 2", solution_name="app2")
            runs = orch.list_runs()
            assert len(runs) == 2

    def test_list_runs_empty(self):
        orch = _fresh_orchestrator()
        runs = orch.list_runs()
        assert runs == []


# ---------------------------------------------------------------------------
# _decompose()
# ---------------------------------------------------------------------------

class TestDecompose:

    def test_calls_planner_with_build_task_types(self):
        orch = _fresh_orchestrator()
        with patch("src.agents.planner.planner_agent") as mock_planner, \
             patch.object(orch, "_build_agent_context", return_value="agents list"):
            mock_planner.create_plan.return_value = MOCK_PLAN
            run = {"product_description": "test", "solution_name": "test"}
            result = orch._decompose(run)
            call_kwargs = mock_planner.create_plan.call_args[1]
            assert "BACKEND" in call_kwargs["override_task_types"]
            assert "AGENTIC" in call_kwargs["override_task_types"]

    def test_enriches_with_acceptance_criteria(self):
        orch = _fresh_orchestrator()
        plan = [{"step": 1, "task_type": "BACKEND", "description": "Build API", "payload": {}}]
        with patch("src.agents.planner.planner_agent") as mock_planner, \
             patch.object(orch, "_build_agent_context", return_value=""):
            mock_planner.create_plan.return_value = plan
            result = orch._decompose({"product_description": "test", "solution_name": "test"})
            assert "acceptance_criteria" in result[0]
            assert len(result[0]["acceptance_criteria"]) > 0

    def test_enriches_with_agent_role(self):
        orch = _fresh_orchestrator()
        plan = [{"step": 1, "task_type": "FRONTEND", "description": "Build UI", "payload": {}}]
        with patch("src.agents.planner.planner_agent") as mock_planner, \
             patch.object(orch, "_build_agent_context", return_value=""):
            mock_planner.create_plan.return_value = plan
            result = orch._decompose({"product_description": "test", "solution_name": "test"})
            assert result[0]["agent_role"] == "developer"

    def test_enriches_with_empty_depends_on(self):
        orch = _fresh_orchestrator()
        plan = [{"step": 1, "task_type": "CONFIG", "description": "Setup", "payload": {}}]
        with patch("src.agents.planner.planner_agent") as mock_planner, \
             patch.object(orch, "_build_agent_context", return_value=""):
            mock_planner.create_plan.return_value = plan
            result = orch._decompose({"product_description": "test", "solution_name": "test"})
            assert result[0]["depends_on"] == []

    def test_preserves_llm_provided_criteria(self):
        """If the LLM already provided acceptance_criteria, don't override."""
        orch = _fresh_orchestrator()
        plan = [{"step": 1, "task_type": "BACKEND", "description": "Build API", "payload": {},
                 "acceptance_criteria": ["Custom criteria"]}]
        with patch("src.agents.planner.planner_agent") as mock_planner, \
             patch.object(orch, "_build_agent_context", return_value=""):
            mock_planner.create_plan.return_value = plan
            result = orch._decompose({"product_description": "test", "solution_name": "test"})
            assert result[0]["acceptance_criteria"] == ["Custom criteria"]


# ---------------------------------------------------------------------------
# _build_agent_context()
# ---------------------------------------------------------------------------

class TestBuildAgentContext:

    def test_includes_framework_agents(self):
        orch = _fresh_orchestrator()
        with patch("src.core.project_loader.project_config") as mock_pc:
            mock_pc.get_prompts.return_value = {"roles": {}}
            ctx = orch._build_agent_context()
            assert "developer" in ctx
            assert "analyst" in ctx
            assert "critic" in ctx

    def test_includes_agentic_patterns(self):
        orch = _fresh_orchestrator()
        with patch("src.core.project_loader.project_config") as mock_pc:
            mock_pc.get_prompts.return_value = {"roles": {}}
            ctx = orch._build_agent_context()
            assert "ReAct" in ctx
            assert "Single-Agent" in ctx
            assert "Coordinator" in ctx

    def test_includes_solution_roles(self):
        orch = _fresh_orchestrator()
        with patch("src.core.project_loader.project_config") as mock_pc:
            mock_pc.get_prompts.return_value = {
                "roles": {
                    "security_reviewer": {"name": "Security Reviewer", "description": "Reviews security"}
                }
            }
            ctx = orch._build_agent_context()
            assert "security_reviewer" in ctx
            assert "Security Reviewer" in ctx


# ---------------------------------------------------------------------------
# _compute_waves()
# ---------------------------------------------------------------------------

class TestComputeWaves:

    def test_correct_waves_from_dependencies(self):
        orch = _fresh_orchestrator()
        plan = [
            {"step": 1, "task_type": "DATABASE", "depends_on": []},
            {"step": 2, "task_type": "BACKEND", "depends_on": [1]},
            {"step": 3, "task_type": "FRONTEND", "depends_on": [2]},
            {"step": 4, "task_type": "TESTS", "depends_on": [2]},
        ]
        waves = orch._compute_waves(plan)
        assert len(waves) == 3  # Wave 1: DB, Wave 2: Backend, Wave 3: Frontend+Tests
        assert len(waves[0]) == 1  # DATABASE
        assert len(waves[1]) == 1  # BACKEND
        assert len(waves[2]) == 2  # FRONTEND + TESTS (parallel)

    def test_independent_tasks_in_one_wave(self):
        orch = _fresh_orchestrator()
        plan = [
            {"step": 1, "task_type": "BACKEND", "depends_on": []},
            {"step": 2, "task_type": "FRONTEND", "depends_on": []},
            {"step": 3, "task_type": "DOCS", "depends_on": []},
        ]
        waves = orch._compute_waves(plan)
        assert len(waves) == 1
        assert len(waves[0]) == 3

    def test_handles_circular_dependencies(self):
        orch = _fresh_orchestrator()
        plan = [
            {"step": 1, "task_type": "A", "depends_on": [2]},
            {"step": 2, "task_type": "B", "depends_on": [1]},
        ]
        waves = orch._compute_waves(plan)
        # Should force-execute rather than deadlock
        assert len(waves) >= 1
        total_tasks = sum(len(w) for w in waves)
        assert total_tasks == 2

    def test_empty_plan(self):
        orch = _fresh_orchestrator()
        waves = orch._compute_waves([])
        assert waves == []

    def test_single_task(self):
        orch = _fresh_orchestrator()
        plan = [{"step": 1, "task_type": "BACKEND", "depends_on": []}]
        waves = orch._compute_waves(plan)
        assert len(waves) == 1
        assert len(waves[0]) == 1


# ---------------------------------------------------------------------------
# _route_to_agent()
# ---------------------------------------------------------------------------

class TestRouteToAgent:

    def test_enriches_with_acceptance_criteria(self):
        orch = _fresh_orchestrator()
        task = {
            "description": "Build API",
            "acceptance_criteria": ["Has validation", "Returns JSON"],
        }
        mock_openswe = MagicMock()
        mock_openswe.build.return_value = MOCK_BUILD_RESULT
        orch._route_to_agent(task, "developer", mock_openswe, {"workspace_dir": ""})
        call_args = mock_openswe.build.call_args[1]
        assert "Has validation" in call_args["task"]["description"]


# ---------------------------------------------------------------------------
# _scaffold()
# ---------------------------------------------------------------------------

class TestScaffold:

    def test_creates_directory_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = os.path.join(tmpdir, "project")
            orch = _fresh_orchestrator()
            run = {
                "workspace_dir": workspace,
                "solution_name": "test_app",
                "product_description": "A test app",
                "plan": MOCK_PLAN,
                "created_at": "2024-01-01",
            }
            result = orch._scaffold(run)
            assert result["status"] == "completed"
            assert os.path.isdir(os.path.join(workspace, "src"))
            assert os.path.isdir(os.path.join(workspace, "tests"))
            assert os.path.isfile(os.path.join(workspace, "README.md"))
            assert os.path.isfile(os.path.join(workspace, "AGENTS.md"))

    def test_skips_when_no_workspace(self):
        orch = _fresh_orchestrator()
        result = orch._scaffold({"workspace_dir": ""})
        assert result["status"] == "skipped"


# ---------------------------------------------------------------------------
# Critic integration
# ---------------------------------------------------------------------------

class TestCriticIntegration:

    def test_critic_review_plan_calls_critic(self):
        orch = _fresh_orchestrator()
        with patch("src.agents.critic.critic_agent") as mock_critic:
            mock_critic.review_with_loop.return_value = MOCK_CRITIC_RESULT
            run = {"plan": MOCK_PLAN, "product_description": "test", "critic_threshold": 70}
            result = orch._critic_review_plan(run)
            mock_critic.review_with_loop.assert_called_once()
            assert result["final_score"] == 85

    def test_critic_review_code_handles_empty(self):
        orch = _fresh_orchestrator()
        run = {"agent_results": [], "product_description": "test", "critic_threshold": 70}
        with patch("src.agents.critic.critic_agent") as mock_critic:
            mock_critic.review_with_loop.return_value = MOCK_CRITIC_RESULT
            result = orch._critic_review_code(run)
            assert result["final_score"] == 100  # No code to review

    def test_finalize_stores_feedback(self):
        orch = _fresh_orchestrator()
        run = {
            "solution_name": "test", "product_description": "test",
            "plan": [], "critic_reports": [],
        }
        with patch("src.memory.vector_store.vector_memory") as mock_vm:
            orch._finalize(run, "Great build!")
            mock_vm.add_feedback.assert_called_once()


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

class TestModuleConstants:

    def test_build_task_types_includes_agentic(self):
        from src.integrations.build_orchestrator import BUILD_TASK_TYPES
        assert "AGENTIC" in BUILD_TASK_TYPES

    def test_agentic_patterns_populated(self):
        from src.integrations.build_orchestrator import AGENTIC_PATTERNS
        assert len(AGENTIC_PATTERNS) >= 10
        assert "react" in AGENTIC_PATTERNS
        assert "coordinator" in AGENTIC_PATTERNS
        assert "single_agent" in AGENTIC_PATTERNS

    def test_hitl_levels(self):
        from src.integrations.build_orchestrator import HITL_LEVELS
        assert "minimal" in HITL_LEVELS
        assert "standard" in HITL_LEVELS
        assert "strict" in HITL_LEVELS
        assert len(HITL_LEVELS["minimal"]) < len(HITL_LEVELS["strict"])

    def test_acceptance_criteria_covers_all_types(self):
        from src.integrations.build_orchestrator import (
            BUILD_TASK_TYPES, DEFAULT_ACCEPTANCE_CRITERIA,
        )
        for task_type in BUILD_TASK_TYPES:
            assert task_type in DEFAULT_ACCEPTANCE_CRITERIA, \
                f"Missing acceptance criteria for {task_type}"

    def test_task_type_to_agent_covers_all_types(self):
        from src.integrations.build_orchestrator import (
            BUILD_TASK_TYPES, TASK_TYPE_TO_AGENT,
        )
        for task_type in BUILD_TASK_TYPES:
            assert task_type in TASK_TYPE_TO_AGENT, \
                f"Missing agent mapping for {task_type}"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestBuildAPI:

    def test_post_build_start(self):
        client = _client()
        mock_orch = MagicMock()
        mock_orch.start.return_value = {
            "run_id": "test-123", "state": "awaiting_plan",
            "solution_name": "test", "plan": MOCK_PLAN,
            "task_count": 4, "critic_scores": [], "critic_reports": [],
            "agent_results": [], "integration_result": None,
            "error": None, "product_description": "test",
            "created_at": "", "updated_at": "",
            "state_description": "", "hitl_level": "standard",
            "hitl_gates": ["plan", "code", "final"],
        }
        with patch("src.interface.api._get_build_orchestrator", return_value=mock_orch):
            resp = client.post("/build/start", json={
                "product_description": "Build a hello world web app"
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["run_id"] == "test-123"

    def test_get_build_status(self):
        """GET /build/status/{run_id} returns status for known run."""
        import src.interface.api as api_mod
        orig = api_mod._get_build_orchestrator
        mock_orch = MagicMock()
        mock_orch.get_status.return_value = {
            "run_id": "test-123", "state": "awaiting_plan",
        }
        api_mod._get_build_orchestrator = lambda: mock_orch
        try:
            client = _client()
            resp = client.get("/build/status/test-123")
            assert resp.status_code == 200
            assert resp.json()["run_id"] == "test-123"
        finally:
            api_mod._get_build_orchestrator = orig

    def test_get_build_status_unknown(self):
        """GET /build/status/unknown returns 404."""
        import src.interface.api as api_mod
        orig = api_mod._get_build_orchestrator
        mock_orch = MagicMock()
        mock_orch.get_status.return_value = {"error": "Not found"}
        api_mod._get_build_orchestrator = lambda: mock_orch
        try:
            client = _client()
            resp = client.get("/build/status/unknown-id")
            assert resp.status_code == 404
        finally:
            api_mod._get_build_orchestrator = orig

    def test_post_build_approve_plan(self):
        client = _client()
        mock_orch = MagicMock()
        mock_orch.get_status.return_value = {"state": "awaiting_plan", "run_id": "test-123"}
        mock_orch.approve_plan.return_value = {
            "run_id": "test-123", "state": "awaiting_build",
            "solution_name": "test", "plan": [], "task_count": 0,
            "critic_scores": [], "critic_reports": [],
            "agent_results": [], "integration_result": None,
            "error": None, "product_description": "test",
            "created_at": "", "updated_at": "",
            "state_description": "", "hitl_level": "standard",
            "hitl_gates": [],
        }
        with patch("src.interface.api._get_build_orchestrator", return_value=mock_orch):
            resp = client.post("/build/approve/test-123", json={"approved": True})
            assert resp.status_code == 200

    def test_post_build_approve_not_awaiting(self):
        client = _client()
        mock_orch = MagicMock()
        mock_orch.get_status.return_value = {"state": "executing", "run_id": "test-123"}
        with patch("src.interface.api._get_build_orchestrator", return_value=mock_orch):
            resp = client.post("/build/approve/test-123", json={"approved": True})
            assert resp.status_code == 400

    def test_get_build_runs(self):
        client = _client()
        mock_orch = MagicMock()
        mock_orch.list_runs.return_value = [
            {"run_id": "a", "solution_name": "app1", "state": "completed",
             "created_at": "", "task_count": 3},
        ]
        with patch("src.interface.api._get_build_orchestrator", return_value=mock_orch):
            resp = client.get("/build/runs")
            assert resp.status_code == 200
            data = resp.json()
            assert data["count"] == 1

    def test_post_build_reject(self):
        import src.interface.api as api_mod
        orig = api_mod._get_build_orchestrator
        mock_orch = MagicMock()
        mock_orch.reject.return_value = {
            "run_id": "test-123", "state": "rejected",
            "state_description": "Build rejected by human",
            "solution_name": "test", "plan": [], "task_count": 0,
            "critic_scores": [], "critic_reports": [],
            "agent_results": [], "integration_result": None,
            "error": "Rejected: Not ready", "product_description": "test",
            "created_at": "", "updated_at": "",
            "hitl_level": "standard", "hitl_gates": [],
            "phase_durations": {},
        }
        api_mod._get_build_orchestrator = lambda: mock_orch
        try:
            client = _client()
            resp = client.post("/build/approve/test-123", json={
                "approved": False, "feedback": "Not ready"
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["state"] == "rejected"
        finally:
            api_mod._get_build_orchestrator = orig


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------

class TestStartEdgeCases:

    def test_very_long_product_description(self):
        """start() should handle extremely long descriptions without error."""
        orch = _fresh_orchestrator()
        long_desc = "Build a microservice that " + "handles requests " * 5000
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            result = orch.start(long_desc)
            assert result["state"] == "awaiting_plan"
            assert result["product_description"] == long_desc

    def test_special_characters_in_solution_name(self):
        """start() should accept solution names with special characters."""
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            result = orch.start("test", solution_name="my-app_v2.0 (beta)")
            assert result["solution_name"] == "my-app_v2.0 (beta)"

    def test_empty_product_description(self):
        """start() with empty description should still work (planner decides)."""
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=[]), \
             patch.object(orch, "_audit"):
            result = orch.start("")
            assert result["state"] == "failed"

    def test_decompose_exception_sets_failed(self):
        """start() handles _decompose raising an exception gracefully."""
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", side_effect=RuntimeError("Planner exploded")), \
             patch.object(orch, "_audit"):
            result = orch.start("Build something")
            assert result["state"] == "failed"
            assert "Planner exploded" in result["error"]


class TestApprovePlanEdgeCases:

    def test_rejected_plan_with_feedback(self):
        """approve_plan() when run is not awaiting includes feedback context."""
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=[]), \
             patch.object(orch, "_audit"):
            start_result = orch.start("test")  # state=failed
            result = orch.approve_plan(start_result["run_id"], feedback="Needs more detail")
            assert "error" in result


class TestApproveBuildEdgeCases:

    def test_approve_build_with_feedback_string(self):
        """approve_build() passes feedback to _finalize."""
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_scaffold", return_value={"status": "skipped"}), \
             patch.object(orch, "_execute_agents"), \
             patch.object(orch, "_critic_review_code", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_integrate", return_value={"status": "completed"}), \
             patch.object(orch, "_critic_review_integration", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_finalize") as mock_finalize, \
             patch.object(orch, "_audit"):
            start_result = orch.start("Build app")
            orch.approve_plan(start_result["run_id"])
            orch.approve_build(start_result["run_id"], feedback="Ship it!")
            mock_finalize.assert_called_once()
            assert mock_finalize.call_args[0][1] == "Ship it!"

    def test_approve_build_unknown_run(self):
        """approve_build() returns error for unknown run_id."""
        orch = _fresh_orchestrator()
        result = orch.approve_build("nonexistent-run-id")
        assert "error" in result


class TestDecomposeEdgeCases:

    def test_planner_raises_exception(self):
        """_decompose() returns empty list when planner raises."""
        orch = _fresh_orchestrator()
        with patch("src.agents.planner.planner_agent") as mock_planner, \
             patch.object(orch, "_build_agent_context", return_value=""):
            mock_planner.create_plan.side_effect = RuntimeError("LLM timeout")
            result = orch._decompose({"product_description": "test", "solution_name": "test"})
            assert result == []


class TestExecuteAgentsEdgeCases:

    def test_mixed_success_failure_results(self):
        """_execute_agents() records both successful and failed task results."""
        orch = _fresh_orchestrator()
        mock_openswe = MagicMock()
        success_result = {"status": "completed", "tier": "llm_react", "code": "x=1", "files_changed": ["a.py"]}
        failure_result = {"status": "error", "tier": "llm_react", "code": "", "files_changed": [], "error": "fail"}
        mock_openswe.build.side_effect = [success_result, failure_result]

        run = {
            "plan": [
                {"step": 1, "task_type": "BACKEND", "description": "Build API", "depends_on": [], "agent_role": "developer"},
                {"step": 2, "task_type": "FRONTEND", "description": "Build UI", "depends_on": [], "agent_role": "developer"},
            ],
            "agent_results": [],
            "workspace_dir": "",
        }
        with patch("src.integrations.openswe_runner.get_openswe_runner", return_value=mock_openswe):
            orch._execute_agents(run)
        assert len(run["agent_results"]) == 2
        assert run["agent_results"][0]["result"]["status"] == "completed"
        assert run["agent_results"][1]["result"]["status"] == "error"


class TestIntegrateEdgeCases:

    def test_no_agent_results(self):
        """_integrate() with empty agent_results returns zero counts."""
        orch = _fresh_orchestrator()
        result = orch._integrate({"agent_results": []})
        assert result["status"] == "completed"
        assert result["files_changed"] == []
        assert result["total_tasks"] == 0
        assert result["completed_tasks"] == 0

    def test_agent_results_with_errors(self):
        """_integrate() handles agent results that contain errors."""
        orch = _fresh_orchestrator()
        run = {
            "agent_results": [
                {"result": {"status": "error", "code": "", "files_changed": [], "error": "broke"}},
                {"result": {"status": "completed", "code": "print(1)", "files_changed": ["a.py"]}},
            ]
        }
        result = orch._integrate(run)
        assert result["total_tasks"] == 2
        assert result["completed_tasks"] == 1
        assert "a.py" in result["files_changed"]


class TestCriticReviewCodeEdgeCases:

    def test_agent_results_all_have_errors(self):
        """_critic_review_code() when all results have empty code returns score 100."""
        orch = _fresh_orchestrator()
        run = {
            "agent_results": [
                {"result": {"status": "error", "code": "", "files_changed": []}},
                {"result": {"status": "error", "code": "", "files_changed": []}},
            ],
            "product_description": "test",
            "critic_threshold": 70,
        }
        with patch("src.agents.critic.critic_agent") as mock_critic:
            result = orch._critic_review_code(run)
            assert result["final_score"] == 100
            mock_critic.review_with_loop.assert_not_called()


class TestGetStatusEdgeCases:

    def test_status_awaiting_plan(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            start = orch.start("test")
            status = orch.get_status(start["run_id"])
            assert status["state"] == "awaiting_plan"
            assert status["state_description"] == "Waiting for human approval of the plan"

    def test_status_failed(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=[]), \
             patch.object(orch, "_audit"):
            start = orch.start("test")
            status = orch.get_status(start["run_id"])
            assert status["state"] == "failed"
            assert status["state_description"] == "Build failed"

    def test_status_completed(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_scaffold", return_value={"status": "skipped"}), \
             patch.object(orch, "_execute_agents"), \
             patch.object(orch, "_critic_review_code", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_integrate", return_value={"status": "completed"}), \
             patch.object(orch, "_critic_review_integration", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_finalize"), \
             patch.object(orch, "_audit"):
            start = orch.start("test")
            orch.approve_plan(start["run_id"])
            orch.approve_build(start["run_id"])
            status = orch.get_status(start["run_id"])
            assert status["state"] == "completed"
            assert status["state_description"] == "Build complete"

    def test_status_awaiting_build(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_scaffold", return_value={"status": "skipped"}), \
             patch.object(orch, "_execute_agents"), \
             patch.object(orch, "_critic_review_code", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_integrate", return_value={"status": "completed"}), \
             patch.object(orch, "_critic_review_integration", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            start = orch.start("test")
            orch.approve_plan(start["run_id"])
            status = orch.get_status(start["run_id"])
            assert status["state"] == "awaiting_build"

    def test_status_executing(self):
        """get_status during execution shows executing state."""
        orch = _fresh_orchestrator()
        # Manually create a run in executing state
        run_id = "test-exec-id"
        run = {
            "run_id": run_id,
            "solution_name": "test",
            "state": "executing",
            "state_description": "",
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01",
            "product_description": "test",
            "hitl_level": "standard",
            "hitl_gates": [],
            "plan": [],
            "critic_reports": [],
            "agent_results": [],
            "integration_result": None,
            "error": None,
        }
        orch._runs[run_id] = run
        status = orch.get_status(run_id)
        assert status["state"] == "executing"
        assert status["state_description"] == "Running agent tasks"


class TestComputeWavesEdgeCases:

    def test_deeply_nested_chain(self):
        """_compute_waves() with a long dependency chain produces N waves."""
        orch = _fresh_orchestrator()
        chain_len = 10
        plan = [
            {"step": i, "task_type": "BACKEND", "depends_on": [i - 1] if i > 1 else []}
            for i in range(1, chain_len + 1)
        ]
        waves = orch._compute_waves(plan)
        assert len(waves) == chain_len
        for w in waves:
            assert len(w) == 1

    def test_diamond_dependency(self):
        """_compute_waves() handles diamond-shaped dependency correctly."""
        orch = _fresh_orchestrator()
        plan = [
            {"step": 1, "task_type": "CONFIG", "depends_on": []},
            {"step": 2, "task_type": "BACKEND", "depends_on": [1]},
            {"step": 3, "task_type": "FRONTEND", "depends_on": [1]},
            {"step": 4, "task_type": "TESTS", "depends_on": [2, 3]},
        ]
        waves = orch._compute_waves(plan)
        assert len(waves) == 3
        assert len(waves[0]) == 1  # CONFIG
        assert len(waves[1]) == 2  # BACKEND + FRONTEND
        assert len(waves[2]) == 1  # TESTS

    def test_missing_dependency_target(self):
        """_compute_waves() handles depends_on referencing non-existent step."""
        orch = _fresh_orchestrator()
        plan = [
            {"step": 1, "task_type": "BACKEND", "depends_on": [99]},
        ]
        waves = orch._compute_waves(plan)
        # Should force-execute since dep 99 never gets completed
        assert len(waves) >= 1
        total = sum(len(w) for w in waves)
        assert total == 1


class TestConcurrentStarts:

    def test_multiple_starts_independent(self):
        """Multiple start() calls create independent runs."""
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            r1 = orch.start("App 1", solution_name="app1")
            r2 = orch.start("App 2", solution_name="app2")
            r3 = orch.start("App 3", solution_name="app3")
            assert r1["run_id"] != r2["run_id"]
            assert r2["run_id"] != r3["run_id"]
            assert len(orch.list_runs()) == 3


class TestTaskTypeToAgentEdgeCases:

    def test_all_mapped_agents_are_valid_roles(self):
        """TASK_TYPE_TO_AGENT values should be recognized agent roles."""
        from src.integrations.build_orchestrator import TASK_TYPE_TO_AGENT, AGENT_ROLES_REGISTRY
        valid_roles = set(AGENT_ROLES_REGISTRY.keys())
        for task_type, role in TASK_TYPE_TO_AGENT.items():
            assert role in valid_roles, f"Role '{role}' for {task_type} is not a valid framework role"


# ---------------------------------------------------------------------------
# Domain detection tests
# ---------------------------------------------------------------------------

class TestDomainDetection:

    def test_empty_description(self):
        orch = _fresh_orchestrator()
        result = orch._detect_domain("")
        assert "General Software" in result

    def test_medical_device_keywords(self):
        orch = _fresh_orchestrator()
        result = orch._detect_domain("FDA 510(k) surgical device with IEC 62304")
        assert "medical_device" in result.lower() or "FIRMWARE" in result

    def test_no_matching_domain(self):
        orch = _fresh_orchestrator()
        result = orch._detect_domain("Build a simple web calculator")
        assert "General Software" in result

    def test_multiple_domains(self):
        orch = _fresh_orchestrator()
        result = orch._detect_domain("IoT medical sensor with BLE gateway and patient monitoring FDA IEC 62304")
        assert "FIRMWARE" in result
        assert "SAFETY" in result

    def test_automotive_iso26262(self):
        orch = _fresh_orchestrator()
        matched = orch._matched_domains("Build automotive ECU with ISO 26262 compliance")
        assert len(matched) >= 1

    def test_matched_domains_empty_string(self):
        orch = _fresh_orchestrator()
        matched = orch._matched_domains("")
        assert matched == []


# ---------------------------------------------------------------------------
# Adaptive router tests
# ---------------------------------------------------------------------------

class TestAdaptiveRouter:

    def test_cold_start_uses_defaults(self):
        from src.integrations.build_orchestrator import AdaptiveRouter, TASK_TYPE_TO_AGENT
        router = AdaptiveRouter()
        assert router.route("BACKEND") == TASK_TYPE_TO_AGENT["BACKEND"]

    def test_learns_after_observations(self):
        from src.integrations.build_orchestrator import AdaptiveRouter
        router = AdaptiveRouter()
        for _ in range(5):
            router.record("BACKEND", "devops_engineer", True, 0.95)
            router.record("BACKEND", "developer", True, 0.5)
        assert router.route("BACKEND") == "devops_engineer"

    def test_thread_safe(self):
        import threading
        from src.integrations.build_orchestrator import AdaptiveRouter
        router = AdaptiveRouter()
        errors = []
        def record_many():
            try:
                for _ in range(100):
                    router.record("TESTS", "qa_engineer", True, 0.8)
                    router.route("TESTS")
            except Exception as e:
                errors.append(e)
        threads = [threading.Thread(target=record_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


# ---------------------------------------------------------------------------
# Reject tests
# ---------------------------------------------------------------------------

class TestReject:

    def test_reject_sets_state(self):
        orch = _fresh_orchestrator()
        with patch.object(orch, "_decompose", return_value=MOCK_PLAN), \
             patch.object(orch, "_critic_review_plan", return_value=MOCK_CRITIC_RESULT), \
             patch.object(orch, "_audit"):
            result = orch.start("test")
            rejected = orch.reject(result["run_id"], "Not ready")
            assert rejected["state"] == "rejected"

    def test_reject_unknown_run(self):
        orch = _fresh_orchestrator()
        result = orch.reject("nonexistent")
        assert "error" in result

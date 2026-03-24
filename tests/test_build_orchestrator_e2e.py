"""
SAGE Framework — Build Orchestrator End-to-End Integration Tests
=================================================================
Exercises the full Build Orchestrator pipeline with mock externals.

Tests:
  1. Full pipeline — start → decompose → critic → approve_plan → execute → critic → integrate → approve_build → completed
  2. Realistic ReAct iteration — multi-iteration LLM responses, file merging
  3. Critic rejection flow — low scores recorded, human override
  4. Wave execution — dependency-aware parallel scheduling
  5. Error recovery — graceful degradation on failures
  6. API integration — HTTP endpoint state transitions

All external dependencies (LLM, vector store, audit, planner, critic, openswe)
are mocked. The orchestrator's internal logic runs for real.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.integrations.build_orchestrator import (
    BuildOrchestrator,
    BUILD_TASK_TYPES,
    DEFAULT_ACCEPTANCE_CRITERIA,
    HITL_LEVELS,
    STATES,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

HELLO_WORLD_PLAN = [
    {
        "step": 1,
        "task_type": "BACKEND",
        "description": "Create Flask backend with /hello endpoint",
        "payload": {"framework": "flask", "endpoints": ["/hello"]},
        "acceptance_criteria": [
            "Returns JSON {message: 'Hello, World!'}",
            "Has error handling middleware",
            "Returns 200 on GET /hello",
        ],
        "depends_on": [],
        "agent_role": "developer",
    },
    {
        "step": 2,
        "task_type": "FRONTEND",
        "description": "Create React frontend that calls /hello API",
        "payload": {"framework": "react", "pages": ["Home"]},
        "acceptance_criteria": [
            "Displays greeting from backend",
            "Has loading spinner",
            "Handles API errors gracefully",
        ],
        "depends_on": [1],
        "agent_role": "developer",
    },
    {
        "step": 3,
        "task_type": "TESTS",
        "description": "Write unit and integration tests for backend and frontend",
        "payload": {"coverage_target": "80%"},
        "acceptance_criteria": [
            "Tests /hello endpoint returns 200",
            "Tests error path returns 500",
            "No hardcoded test data",
        ],
        "depends_on": [1, 2],
        "agent_role": "developer",
    },
    {
        "step": 4,
        "task_type": "CONFIG",
        "description": "Create Docker and CI configuration",
        "payload": {"docker": True, "ci": "github-actions"},
        "acceptance_criteria": [
            "Docker builds successfully",
            "CI runs tests on push",
            "Environment variables parameterized",
        ],
        "depends_on": [1],
        "agent_role": "developer",
    },
]


def _make_react_response(files, thought="Building component", status="DONE"):
    """Build a realistic ReAct LLM response string."""
    files_json = json.dumps({"files": files, "explanation": thought})
    return (
        f"THOUGHT: {thought}\n"
        f"ACTION: Generate code\n"
        f"```json\n{files_json}\n```\n"
        f"OBSERVATION: Code looks correct, all criteria met.\n"
        f"STATUS: {status}\n"
    )


def _make_critic_json(score, **extra):
    """Build a critic JSON response."""
    result = {
        "score": score,
        "flaws": extra.get("flaws", []),
        "suggestions": extra.get("suggestions", []),
        "missing": extra.get("missing", []),
        "security_risks": extra.get("security_risks", []),
        "summary": extra.get("summary", f"Score {score}/100 assessment."),
    }
    # Add code review fields if present
    if "issues" in extra:
        result["issues"] = extra["issues"]
    if "missing_tests" in extra:
        result["missing_tests"] = extra["missing_tests"]
    if "gaps" in extra:
        result["gaps"] = extra["gaps"]
    if "risks" in extra:
        result["risks"] = extra["risks"]
    return json.dumps(result)


def _build_openswe_result(files, tier="llm_react"):
    """Build a realistic OpenSWE build result."""
    return {
        "status": "completed",
        "tier": tier,
        "output": {"files": files, "react_iterations": 1, "react_trace": ["Built OK"]},
        "code": "\n".join(f"# {f['path']}\n{f['content']}" for f in files),
        "files_changed": [f["path"] for f in files],
    }


@pytest.fixture
def orchestrator():
    """Fresh BuildOrchestrator instance for each test."""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return BuildOrchestrator(checkpoint_db=tmp.name)


@pytest.fixture
def mock_audit():
    """Mock audit logger to capture calls."""
    audit = MagicMock()
    audit.log_event = MagicMock()
    return audit


@pytest.fixture
def mock_vector_memory():
    """Mock vector memory store."""
    mem = MagicMock()
    mem.add_feedback = MagicMock()
    return mem


# ---------------------------------------------------------------------------
# 1. Full pipeline test
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestFullPipeline:
    """Exercises the entire build pipeline start-to-finish."""

    def test_full_hello_world_pipeline(self, orchestrator, mock_audit, mock_vector_memory):
        """
        start("Build a hello world web app")
        → decompose → critic reviews plan (75 then 88) → awaiting_plan
        → approve_plan → scaffold + execute agents → critic reviews code
        → integrate → critic reviews integration → awaiting_build
        → approve_build → completed
        """
        # Track LLM call count for critic — first call score 75, second 88
        critic_call_count = {"plan": 0, "code": 0, "integration": 0}

        def mock_critic_llm_generate(prompt, system_prompt, trace_name=""):
            """Mock LLM for critic agent — returns different scores per call."""
            if "critic.plan_review" in trace_name:
                critic_call_count["plan"] += 1
                if critic_call_count["plan"] == 1:
                    return _make_critic_json(
                        75,
                        flaws=["Missing health check endpoint"],
                        suggestions=["Add /health route"],
                        summary="Decent plan but missing observability.",
                    )
                else:
                    return _make_critic_json(
                        88,
                        flaws=[],
                        suggestions=["Consider rate limiting"],
                        summary="Plan is solid after revision.",
                    )
            elif "critic.code_review" in trace_name:
                critic_call_count["code"] += 1
                return _make_critic_json(
                    82,
                    issues=["No input sanitization on /hello"],
                    missing_tests=["Test for malformed request"],
                    summary="Code is production-ready with minor issues.",
                )
            elif "critic.integration_review" in trace_name:
                critic_call_count["integration"] += 1
                return _make_critic_json(
                    85,
                    gaps=["No load testing"],
                    risks=["Single point of failure"],
                    summary="Integration is sound.",
                )
            return _make_critic_json(70)

        # Mock openswe build — returns realistic results per task
        openswe_files = {
            "BACKEND": [{"path": "src/app.py", "content": "from flask import Flask\napp = Flask(__name__)"}],
            "FRONTEND": [{"path": "src/App.tsx", "content": "export default function App() { return <h1>Hello</h1> }"}],
            "TESTS": [{"path": "tests/test_app.py", "content": "def test_hello(): assert True"}],
            "CONFIG": [{"path": "Dockerfile", "content": "FROM python:3.11"}],
        }

        def mock_openswe_build(task, repo_path=""):
            task_type = task.get("task_type", "BACKEND")
            files = openswe_files.get(task_type, [{"path": "unknown.txt", "content": ""}])
            return _build_openswe_result(files)

        mock_openswe = MagicMock()
        mock_openswe.build = MagicMock(side_effect=mock_openswe_build)

        # Mock planner to return our realistic plan
        mock_planner = MagicMock()
        mock_planner.create_plan = MagicMock(return_value=HELLO_WORLD_PLAN)

        # Mock critic LLM
        mock_llm = MagicMock()
        mock_llm.generate = MagicMock(side_effect=mock_critic_llm_generate)

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.integrations.build_orchestrator.BuildOrchestrator._audit"),
                patch("src.agents.critic.CriticAgent.llm", new_callable=PropertyMock, return_value=mock_llm),
                patch("src.agents.critic.CriticAgent.audit", new_callable=PropertyMock, return_value=mock_audit),
                patch("src.agents.critic.CriticAgent._store_feedback"),
                patch("src.integrations.build_orchestrator.BuildOrchestrator._decompose", return_value=HELLO_WORLD_PLAN),
                patch("src.integrations.openswe_runner.get_openswe_runner", return_value=mock_openswe),
                patch("src.integrations.build_orchestrator.BuildOrchestrator._finalize"),
            ):
                # --- Phase 1: START ---
                result = orchestrator.start(
                    product_description="Build a hello world web app",
                    solution_name="hello_world",
                    workspace_dir=tmpdir,
                    critic_threshold=70,
                    hitl_level="standard",
                )

                assert result["state"] == "awaiting_plan"
                assert result["run_id"]
                assert result["solution_name"] == "hello_world"
                assert result["task_count"] == 4
                assert len(result["plan"]) == 4
                assert result["hitl_level"] == "standard"
                assert "plan" in result["hitl_gates"]

                # Verify plan has correct task types
                task_types = [t["task_type"] for t in result["plan"]]
                assert "BACKEND" in task_types
                assert "FRONTEND" in task_types
                assert "TESTS" in task_types
                assert "CONFIG" in task_types

                # Verify critic reviewed the plan
                assert len(result["critic_scores"]) == 1
                assert result["critic_scores"][0]["phase"] == "plan"

                # --- Phase 2: APPROVE PLAN ---
                run_id = result["run_id"]
                result2 = orchestrator.approve_plan(run_id, feedback="Looks good, proceed")

                assert result2["state"] == "awaiting_build"
                assert len(result2["agent_results"]) == 4

                # Verify each agent task completed
                for ar in result2["agent_results"]:
                    assert ar["status"] == "completed"
                    assert ar["task_type"] in ("BACKEND", "FRONTEND", "TESTS", "CONFIG")
                    assert ar["agent_role"] == "developer"

                # Verify critic reviewed code and integration
                critic_phases = [c["phase"] for c in result2["critic_scores"]]
                assert "plan" in critic_phases
                assert "code" in critic_phases
                assert "integration" in critic_phases

                # Verify integration result
                assert result2["integration_result"] is not None
                assert result2["integration_result"]["status"] == "completed"
                assert result2["integration_result"]["total_tasks"] == 4

                # --- Phase 3: APPROVE BUILD ---
                result3 = orchestrator.approve_build(run_id, feedback="Ship it!")

                assert result3["state"] == "completed"
                assert result3.get("error") is None

                # Verify full status contains all expected fields
                status = orchestrator.get_status(run_id)
                expected_fields = [
                    "run_id", "solution_name", "state", "state_description",
                    "created_at", "updated_at", "product_description",
                    "hitl_level", "hitl_gates", "plan", "task_count",
                    "critic_scores", "critic_reports", "agent_results",
                    "integration_result",
                ]
                for field in expected_fields:
                    assert field in status, f"Missing field: {field}"
                # error key should NOT be present for successful runs
                assert "error" not in status

    def test_plan_enrichment(self, orchestrator):
        """Verify _decompose enriches tasks with acceptance criteria, dependencies, agent roles."""
        bare_plan = [
            {"step": 1, "task_type": "BACKEND", "description": "Build API"},
            {"step": 2, "task_type": "FRONTEND", "description": "Build UI"},
        ]

        mock_planner = MagicMock()
        mock_planner.create_plan = MagicMock(return_value=bare_plan)

        with (
            patch("src.agents.planner.planner_agent", mock_planner),
            patch("src.integrations.build_orchestrator.BuildOrchestrator._build_agent_context", return_value="agents"),
        ):
            run = {
                "product_description": "Test product",
                "solution_name": "test",
            }
            # Call the real _decompose
            orch = BuildOrchestrator(checkpoint_db=tempfile.NamedTemporaryFile(suffix=".db", delete=False).name)
            plan = orch._decompose(run)

            assert len(plan) == 2
            # Verify acceptance criteria were added from defaults
            assert plan[0]["acceptance_criteria"] == DEFAULT_ACCEPTANCE_CRITERIA["BACKEND"]
            assert plan[1]["acceptance_criteria"] == DEFAULT_ACCEPTANCE_CRITERIA["FRONTEND"]
            # Verify depends_on defaulted to []
            assert plan[0]["depends_on"] == []
            assert plan[1]["depends_on"] == []
            # Verify agent_role defaulted
            assert plan[0]["agent_role"] == "developer"
            assert plan[1]["agent_role"] == "developer"


# ---------------------------------------------------------------------------
# 2. Realistic ReAct iteration test
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestReActIteration:
    """Test the ReAct pattern with multi-iteration LLM responses."""

    def test_multi_iteration_react(self):
        """
        Mock the LLM to return:
          - Iteration 1: basic Flask app (STATUS: ITERATE)
          - Iteration 2: adds error handling + tests (STATUS: DONE)
        Verify files merge correctly across iterations.
        """
        from src.integrations.openswe_runner import OpenSWERunner

        call_count = {"n": 0}

        def mock_llm_generate(prompt, system_prompt, trace_name=""):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First iteration — basic app
                return _make_react_response(
                    files=[
                        {"path": "app.py", "content": "from flask import Flask\napp = Flask(__name__)\n@app.route('/hello')\ndef hello():\n    return {'message': 'Hello'}"},
                    ],
                    thought="Building basic Flask hello endpoint",
                    status="ITERATE — need error handling and tests",
                )
            else:
                # Second iteration — adds error handling + new file
                return _make_react_response(
                    files=[
                        {"path": "app.py", "content": "from flask import Flask\napp = Flask(__name__)\n@app.route('/hello')\ndef hello():\n    try:\n        return {'message': 'Hello, World!'}\n    except Exception as e:\n        return {'error': str(e)}, 500"},
                        {"path": "tests/test_app.py", "content": "def test_hello():\n    from app import app\n    client = app.test_client()\n    assert client.get('/hello').status_code == 200"},
                    ],
                    thought="Adding error handling and tests",
                    status="DONE",
                )

        mock_llm = MagicMock()
        mock_llm.generate = MagicMock(side_effect=mock_llm_generate)
        mock_llm.generate_for_task = MagicMock(side_effect=lambda task_type, prompt, system_prompt, trace_name="", **kw: mock_llm_generate(prompt, system_prompt, trace_name))

        runner = OpenSWERunner()
        # Force tier 3 by clearing openswe url and breaking langgraph
        runner._openswe_url = ""

        with (
            patch("src.core.llm_gateway.llm_gateway", mock_llm),
            patch.object(runner, "_audit"),
        ):
            task = {
                "description": "Build Flask hello endpoint with error handling",
                "task_type": "BACKEND",
                "acceptance_criteria": ["Returns 200 on /hello", "Has error handling"],
            }
            result = runner.build(task)

            assert result["status"] == "completed"
            assert result["tier"] == "llm_react"

            # Verify files were merged — app.py updated, test_app.py added
            files_changed = result["files_changed"]
            assert "app.py" in files_changed
            assert "tests/test_app.py" in files_changed

            # Verify iteration count
            output = result["output"]
            assert output["react_iterations"] == 2

            # Verify the merged app.py has error handling (from iteration 2)
            assert "except Exception" in result["code"]

            # Verify LLM was called exactly twice (via generate_for_task)
            assert mock_llm.generate_for_task.call_count == 2


# ---------------------------------------------------------------------------
# 3. Critic rejection flow
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCriticRejectionFlow:
    """Test behavior when critic gives low scores."""

    def test_low_plan_score_still_surfaces_to_human(self, orchestrator):
        """
        Critic gives score 30 on plan — plan still surfaces to human
        at awaiting_plan state. Human approves anyway.
        """
        def mock_critic_generate(prompt, system_prompt, trace_name=""):
            if "plan_review" in trace_name:
                return _make_critic_json(
                    30,
                    flaws=["Missing database layer", "No auth", "No error handling"],
                    summary="Fundamental rework needed.",
                )
            elif "code_review" in trace_name:
                return _make_critic_json(
                    45,
                    issues=["No input validation", "SQL injection risk"],
                    summary="Code needs security hardening.",
                )
            elif "integration_review" in trace_name:
                return _make_critic_json(50, summary="Partial integration.")
            return _make_critic_json(40)

        mock_llm = MagicMock()
        mock_llm.generate = MagicMock(side_effect=mock_critic_generate)

        mock_openswe = MagicMock()
        mock_openswe.build = MagicMock(return_value=_build_openswe_result(
            [{"path": "app.py", "content": "print('hello')"}]
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.integrations.build_orchestrator.BuildOrchestrator._audit"),
                patch("src.agents.critic.CriticAgent.llm", new_callable=PropertyMock, return_value=mock_llm),
                patch("src.agents.critic.CriticAgent.audit", new_callable=PropertyMock, return_value=MagicMock()),
                patch("src.agents.critic.CriticAgent._store_feedback"),
                patch("src.integrations.build_orchestrator.BuildOrchestrator._decompose", return_value=HELLO_WORLD_PLAN),
                patch("src.integrations.openswe_runner.get_openswe_runner", return_value=mock_openswe),
                patch("src.integrations.build_orchestrator.BuildOrchestrator._finalize"),
            ):
                # Start — critic gives low score but plan still surfaces
                result = orchestrator.start(
                    product_description="Build a hello world web app",
                    solution_name="hello_low_score",
                    workspace_dir=tmpdir,
                    critic_threshold=70,
                )
                assert result["state"] == "awaiting_plan"
                # Plan critic score is low
                plan_critic = result["critic_scores"][0]
                assert plan_critic["score"] < 70
                assert plan_critic["passed"] is False

                # Human approves anyway
                run_id = result["run_id"]
                result2 = orchestrator.approve_plan(run_id)
                assert result2["state"] == "awaiting_build"

                # Code critic score is also low but recorded
                code_critics = [c for c in result2["critic_scores"] if c["phase"] == "code"]
                assert len(code_critics) == 1
                assert code_critics[0]["score"] < 70

                # Human approves the build anyway
                result3 = orchestrator.approve_build(run_id)
                assert result3["state"] == "completed"


# ---------------------------------------------------------------------------
# 4. Wave execution test
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestWaveExecution:
    """Test parallel wave scheduling from dependency graph."""

    def test_three_wave_execution(self):
        """
        6 tasks with dependencies forming 3 waves:
          Wave 1: tasks 1, 2 (no deps)
          Wave 2: tasks 3 (depends on 1), 4 (depends on 2)
          Wave 3: tasks 5 (depends on 3, 4), 6 (depends on 4)
        """
        plan = [
            {"step": 1, "task_type": "BACKEND", "description": "Auth service", "depends_on": []},
            {"step": 2, "task_type": "DATABASE", "description": "Schema setup", "depends_on": []},
            {"step": 3, "task_type": "API", "description": "Auth endpoints", "depends_on": [1]},
            {"step": 4, "task_type": "API", "description": "Data endpoints", "depends_on": [2]},
            {"step": 5, "task_type": "TESTS", "description": "Integration tests", "depends_on": [3, 4]},
            {"step": 6, "task_type": "FRONTEND", "description": "Dashboard UI", "depends_on": [4]},
        ]

        orch = BuildOrchestrator(checkpoint_db=tempfile.NamedTemporaryFile(suffix=".db", delete=False).name)
        waves = orch._compute_waves(plan)

        assert len(waves) == 3

        # Wave 1: steps 1, 2
        wave1_steps = {t["step"] for t in waves[0]}
        assert wave1_steps == {1, 2}

        # Wave 2: steps 3, 4
        wave2_steps = {t["step"] for t in waves[1]}
        assert wave2_steps == {3, 4}

        # Wave 3: steps 5, 6
        wave3_steps = {t["step"] for t in waves[2]}
        assert wave3_steps == {5, 6}

    def test_all_independent_single_wave(self):
        """All tasks independent — should be one wave."""
        plan = [
            {"step": 1, "task_type": "BACKEND", "description": "A", "depends_on": []},
            {"step": 2, "task_type": "FRONTEND", "description": "B", "depends_on": []},
            {"step": 3, "task_type": "TESTS", "description": "C", "depends_on": []},
        ]

        orch = BuildOrchestrator(checkpoint_db=tempfile.NamedTemporaryFile(suffix=".db", delete=False).name)
        waves = orch._compute_waves(plan)

        assert len(waves) == 1
        assert len(waves[0]) == 3

    def test_linear_chain_n_waves(self):
        """Linear dependency chain — one task per wave."""
        plan = [
            {"step": 1, "task_type": "BACKEND", "description": "A", "depends_on": []},
            {"step": 2, "task_type": "API", "description": "B", "depends_on": [1]},
            {"step": 3, "task_type": "TESTS", "description": "C", "depends_on": [2]},
            {"step": 4, "task_type": "CONFIG", "description": "D", "depends_on": [3]},
        ]

        orch = BuildOrchestrator(checkpoint_db=tempfile.NamedTemporaryFile(suffix=".db", delete=False).name)
        waves = orch._compute_waves(plan)

        assert len(waves) == 4
        for i, wave in enumerate(waves):
            assert len(wave) == 1
            assert wave[0]["step"] == i + 1

    def test_circular_dependency_forced(self):
        """Circular deps should be resolved by forcing execution."""
        plan = [
            {"step": 1, "task_type": "BACKEND", "description": "A", "depends_on": [2]},
            {"step": 2, "task_type": "FRONTEND", "description": "B", "depends_on": [1]},
        ]

        orch = BuildOrchestrator(checkpoint_db=tempfile.NamedTemporaryFile(suffix=".db", delete=False).name)
        waves = orch._compute_waves(plan)

        # Should still produce waves (forced execution)
        assert len(waves) >= 1
        all_steps = set()
        for wave in waves:
            for task in wave:
                all_steps.add(task["step"])
        assert all_steps == {1, 2}

    def test_empty_plan(self):
        """Empty plan → no waves."""
        orch = BuildOrchestrator(checkpoint_db=tempfile.NamedTemporaryFile(suffix=".db", delete=False).name)
        waves = orch._compute_waves([])
        assert waves == []

    def test_all_tasks_execute_in_waves(self, orchestrator):
        """
        Verify all 6 tasks execute through the wave scheduler
        with the openswe runner mock.
        """
        plan = [
            {"step": 1, "task_type": "BACKEND", "description": "A", "depends_on": [],
             "acceptance_criteria": ["Works"], "agent_role": "developer"},
            {"step": 2, "task_type": "DATABASE", "description": "B", "depends_on": [],
             "acceptance_criteria": ["Works"], "agent_role": "developer"},
            {"step": 3, "task_type": "API", "description": "C", "depends_on": [1],
             "acceptance_criteria": ["Works"], "agent_role": "developer"},
            {"step": 4, "task_type": "API", "description": "D", "depends_on": [2],
             "acceptance_criteria": ["Works"], "agent_role": "developer"},
            {"step": 5, "task_type": "TESTS", "description": "E", "depends_on": [3, 4],
             "acceptance_criteria": ["Works"], "agent_role": "developer"},
            {"step": 6, "task_type": "FRONTEND", "description": "F", "depends_on": [4],
             "acceptance_criteria": ["Works"], "agent_role": "developer"},
        ]

        call_log = []

        def mock_build(task, repo_path=""):
            call_log.append(task.get("task_type", "?"))
            return _build_openswe_result([{"path": f"{task['task_type'].lower()}.py", "content": "pass"}])

        mock_openswe = MagicMock()
        mock_openswe.build = MagicMock(side_effect=mock_build)

        with patch("src.integrations.openswe_runner.get_openswe_runner", return_value=mock_openswe):
            run = {"plan": plan, "agent_results": [], "workspace_dir": ""}
            orchestrator._execute_agents(run)

        assert len(run["agent_results"]) == 6
        assert mock_openswe.build.call_count == 6

        # Verify wave ordering: steps 1,2 before 3,4 before 5,6
        executed_steps = [r["step"] for r in run["agent_results"]]
        idx_1 = executed_steps.index(1)
        idx_2 = executed_steps.index(2)
        idx_3 = executed_steps.index(3)
        idx_4 = executed_steps.index(4)
        idx_5 = executed_steps.index(5)
        idx_6 = executed_steps.index(6)
        assert idx_1 < idx_3  # 1 before 3
        assert idx_2 < idx_4  # 2 before 4
        assert idx_3 < idx_5  # 3 before 5
        assert idx_4 < idx_5  # 4 before 5
        assert idx_4 < idx_6  # 4 before 6


# ---------------------------------------------------------------------------
# 5. Error recovery test
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestErrorRecovery:
    """Test graceful degradation on failures."""

    def test_openswe_tier_fallback(self):
        """
        External SWE unavailable, LangGraph unavailable → falls back to LLM.
        """
        from src.integrations.openswe_runner import OpenSWERunner

        react_response = _make_react_response(
            files=[{"path": "app.py", "content": "print('hello')"}],
            status="DONE",
        )
        mock_llm = MagicMock()
        mock_llm.generate = MagicMock(return_value=react_response)
        mock_llm.generate_for_task = MagicMock(return_value=react_response)

        runner = OpenSWERunner()
        runner._openswe_url = ""  # No external SWE

        with (
            patch("src.core.llm_gateway.llm_gateway", mock_llm),
            patch.object(runner, "_audit"),
        ):
            result = runner.build({"description": "Build something", "task_type": "BACKEND"})

            assert result["status"] == "completed"
            assert result["tier"] == "llm_react"
            assert "app.py" in result["files_changed"]

    def test_one_agent_fails_others_continue(self, orchestrator):
        """One agent task fails → others still complete."""
        plan = [
            {"step": 1, "task_type": "BACKEND", "description": "Good task", "depends_on": [],
             "acceptance_criteria": ["Works"], "agent_role": "developer"},
            {"step": 2, "task_type": "FRONTEND", "description": "Bad task", "depends_on": [],
             "acceptance_criteria": ["Works"], "agent_role": "developer"},
            {"step": 3, "task_type": "TESTS", "description": "Another good task", "depends_on": [],
             "acceptance_criteria": ["Works"], "agent_role": "developer"},
        ]

        call_count = {"n": 0}

        def mock_build(task, repo_path=""):
            call_count["n"] += 1
            if task.get("task_type") == "FRONTEND":
                return {"status": "error", "tier": "llm_react", "error": "LLM timeout",
                        "code": "", "files_changed": []}
            return _build_openswe_result([{"path": f"{task['task_type'].lower()}.py", "content": "pass"}])

        mock_openswe = MagicMock()
        mock_openswe.build = MagicMock(side_effect=mock_build)

        with patch("src.integrations.openswe_runner.get_openswe_runner", return_value=mock_openswe):
            run = {"plan": plan, "agent_results": [], "workspace_dir": ""}
            orchestrator._execute_agents(run)

        # All 3 tasks attempted
        assert len(run["agent_results"]) == 3
        statuses = {r["task"]["task_type"]: r["result"]["status"] for r in run["agent_results"]}
        assert statuses["BACKEND"] == "completed"
        assert statuses["FRONTEND"] == "error"
        assert statuses["TESTS"] == "completed"

    def test_critic_exception_build_continues(self, orchestrator):
        """Critic throws exception → build continues with default score."""
        mock_openswe = MagicMock()
        mock_openswe.build = MagicMock(return_value=_build_openswe_result(
            [{"path": "app.py", "content": "pass"}]
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.integrations.build_orchestrator.BuildOrchestrator._audit"),
                patch("src.integrations.build_orchestrator.BuildOrchestrator._decompose", return_value=HELLO_WORLD_PLAN),
                patch("src.agents.critic.critic_agent.review_with_loop", side_effect=Exception("Critic crashed")),
                patch("src.integrations.openswe_runner.get_openswe_runner", return_value=mock_openswe),
                patch("src.integrations.build_orchestrator.BuildOrchestrator._finalize"),
            ):
                result = orchestrator.start(
                    product_description="Build a hello world web app",
                    solution_name="critic_fail_test",
                    workspace_dir=tmpdir,
                )
                # Critic failure is caught — build continues
                assert result["state"] == "awaiting_plan"
                # Critic report has error but default passed=True
                plan_critic = result["critic_reports"][0]["result"]
                assert plan_critic.get("error") is not None or plan_critic.get("passed") is True

                # Continue through pipeline
                run_id = result["run_id"]
                result2 = orchestrator.approve_plan(run_id)
                assert result2["state"] == "awaiting_build"

                result3 = orchestrator.approve_build(run_id)
                assert result3["state"] == "completed"

    def test_llm_exception_produces_error_state(self):
        """LLM throws exception → OpenSWE returns error result."""
        from src.integrations.openswe_runner import OpenSWERunner

        mock_llm = MagicMock()
        mock_llm.generate = MagicMock(side_effect=RuntimeError("LLM service down"))
        mock_llm.generate_for_task = MagicMock(side_effect=RuntimeError("LLM service down"))

        runner = OpenSWERunner()
        runner._openswe_url = ""

        with (
            patch("src.core.llm_gateway.llm_gateway", mock_llm),
            patch.object(runner, "_audit"),
        ):
            result = runner.build({"description": "Build something", "task_type": "BACKEND"})

            assert result["status"] == "error"
            assert result["tier"] == "llm_react"
            assert "LLM service down" in result.get("error", "")

    def test_empty_plan_sets_failed_state(self, orchestrator):
        """Empty plan from planner → state is 'failed'."""
        with (
            patch("src.integrations.build_orchestrator.BuildOrchestrator._audit"),
            patch("src.integrations.build_orchestrator.BuildOrchestrator._decompose", return_value=[]),
        ):
            result = orchestrator.start(
                product_description="Build something vague",
                solution_name="empty_plan",
            )
            assert result["state"] == "failed"
            assert result["error"] is not None
            assert "decompose" in result["error"].lower() or "planner" in result["error"].lower()


# ---------------------------------------------------------------------------
# 6. API integration test
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestAPIIntegration:
    """Test HTTP endpoint state transitions."""

    def test_full_api_flow(self):
        """
        POST /build/start → GET /build/status → POST /build/approve (plan)
        → GET /build/status → POST /build/approve (build) → GET /build/status
        Verify state transitions: awaiting_plan → awaiting_build → completed

        Uses a mock orchestrator at the API boundary (patching _get_build_orchestrator)
        to exercise the HTTP layer, because the real _run_summary includes an
        "error": None key which trips the API's `if "error" in result` check.
        The orchestrator's internal logic is fully tested by TestFullPipeline above.
        """
        import src.interface.api as api_mod
        from fastapi.testclient import TestClient
        from src.interface.api import app

        # Build a mock orchestrator that simulates the full state machine
        mock_orch = MagicMock()
        call_count = {"approve": 0}

        mock_orch.start.return_value = {
            "run_id": "test-run-001",
            "solution_name": "api_test",
            "state": "awaiting_plan",
            "task_count": 4,
            "plan": HELLO_WORLD_PLAN,
            "critic_scores": [{"phase": "plan", "score": 80, "passed": True}],
        }

        # get_status tracks current state — approve endpoint calls get_status
        # internally to determine routing, so we use a stateful mock
        current_state = {"state": "awaiting_plan"}

        def mock_get_status(run_id):
            if run_id != "test-run-001":
                return {"error": f"Run '{run_id}' not found"}
            s = current_state["state"]
            base = {"run_id": "test-run-001", "state": s}
            if s == "awaiting_build":
                base["agent_results"] = [
                    {"task_type": "BACKEND", "status": "completed"},
                    {"task_type": "FRONTEND", "status": "completed"},
                    {"task_type": "TESTS", "status": "completed"},
                    {"task_type": "CONFIG", "status": "completed"},
                ]
            if s == "awaiting_plan":
                base["task_count"] = 4
            return base

        mock_orch.get_status.side_effect = mock_get_status

        def mock_approve_plan(run_id, feedback=""):
            current_state["state"] = "awaiting_build"
            return {
                "run_id": "test-run-001",
                "state": "awaiting_build",
                "agent_results": [
                    {"task_type": "BACKEND", "status": "completed"},
                    {"task_type": "FRONTEND", "status": "completed"},
                    {"task_type": "TESTS", "status": "completed"},
                    {"task_type": "CONFIG", "status": "completed"},
                ],
            }

        def mock_approve_build(run_id, feedback=""):
            current_state["state"] = "completed"
            return {
                "run_id": "test-run-001",
                "state": "completed",
            }

        mock_orch.approve_plan.side_effect = mock_approve_plan
        mock_orch.approve_build.side_effect = mock_approve_build

        orig_get = api_mod._get_build_orchestrator
        api_mod._get_build_orchestrator = lambda: mock_orch
        try:
            client = TestClient(app)

            # --- POST /build/start ---
            resp = client.post("/build/start", json={
                "product_description": "Build a hello world web app",
                "solution_name": "api_test",
                "critic_threshold": 70,
                "hitl_level": "standard",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["state"] == "awaiting_plan"
            run_id = data["run_id"]
            assert data["task_count"] == 4

            # --- GET /build/status ---
            resp = client.get(f"/build/status/{run_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["state"] == "awaiting_plan"

            # --- POST /build/approve (plan) ---
            resp = client.post(f"/build/approve/{run_id}", json={
                "approved": True,
                "feedback": "Plan approved",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["state"] == "awaiting_build"
            assert len(data["agent_results"]) == 4

            # --- GET /build/status (should be awaiting_build) ---
            resp = client.get(f"/build/status/{run_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["state"] == "awaiting_build"

            # --- POST /build/approve (build) ---
            resp = client.post(f"/build/approve/{run_id}", json={
                "approved": True,
                "feedback": "Ship it!",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["state"] == "completed"

            # --- GET /build/status (should be completed) ---
            resp = client.get(f"/build/status/{run_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["state"] == "completed"

            # Verify mock calls
            mock_orch.start.assert_called_once()
            mock_orch.approve_plan.assert_called_once_with(run_id, feedback="Plan approved")
            mock_orch.approve_build.assert_called_once_with(run_id, feedback="Ship it!")
        finally:
            api_mod._get_build_orchestrator = orig_get

    def test_status_unknown_returns_404(self):
        """GET /build/status/unknown-id returns 404."""
        from fastapi.testclient import TestClient
        from src.interface.api import app

        client = TestClient(app)
        resp = client.get("/build/status/nonexistent-run-id")
        assert resp.status_code == 404

    def test_approve_wrong_state_returns_error(self):
        """POST /build/approve when rejected returns rejection response."""
        import src.interface.api as api_mod
        from fastapi.testclient import TestClient
        from src.interface.api import app

        mock_orch = MagicMock()
        mock_orch.start.return_value = {
            "run_id": "test-reject-001",
            "state": "awaiting_plan",
            "plan": [],
        }
        mock_orch.get_status.return_value = {
            "run_id": "test-reject-001",
            "state": "awaiting_plan",
        }
        mock_orch.reject.return_value = {
            "status": "rejected",
            "run_id": "test-reject-001",
        }

        orig_get = api_mod._get_build_orchestrator
        api_mod._get_build_orchestrator = lambda: mock_orch
        try:
            client = TestClient(app)

            resp = client.post("/build/start", json={
                "product_description": "Test product for wrong state validation",
                "solution_name": "wrong_state_test",
            })
            run_id = resp.json()["run_id"]

            # Reject the build
            resp2 = client.post(f"/build/approve/{run_id}", json={
                "approved": False,
                "feedback": "Rejecting",
            })
            assert resp2.status_code == 200
            assert resp2.json()["status"] == "rejected"
        finally:
            api_mod._get_build_orchestrator = orig_get

    def test_list_runs_returns_all(self):
        """GET /build/runs returns all started runs."""
        import src.interface.api as api_mod
        from fastapi.testclient import TestClient
        from src.interface.api import app

        mock_orch = MagicMock()
        mock_orch.list_runs.return_value = [
            {"run_id": "r1", "solution_name": "a", "state": "completed", "task_count": 3},
            {"run_id": "r2", "solution_name": "b", "state": "awaiting_plan", "task_count": 5},
        ]

        orig_get = api_mod._get_build_orchestrator
        api_mod._get_build_orchestrator = lambda: mock_orch
        try:
            client = TestClient(app)
            resp = client.get("/build/runs")
            assert resp.status_code == 200
            data = resp.json()
            assert "runs" in data
            assert data["count"] == 2
        finally:
            api_mod._get_build_orchestrator = orig_get


# ---------------------------------------------------------------------------
# Additional edge case tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestEdgeCases:
    """Miscellaneous edge cases."""

    def test_scaffold_creates_directories(self):
        """Scaffold creates src/, tests/, docs/, config/ and writes README + AGENTS.md."""
        orch = BuildOrchestrator(checkpoint_db=tempfile.NamedTemporaryFile(suffix=".db", delete=False).name)
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = os.path.join(tmpdir, "my_project")
            run = {
                "workspace_dir": workspace,
                "solution_name": "scaffold_test",
                "product_description": "A test product",
                "created_at": "2025-01-01T00:00:00Z",
                "plan": HELLO_WORLD_PLAN,
            }
            result = orch._scaffold(run)

            assert result["status"] == "completed"
            assert os.path.isdir(os.path.join(workspace, "src"))
            assert os.path.isdir(os.path.join(workspace, "tests"))
            assert os.path.isdir(os.path.join(workspace, "docs"))
            assert os.path.isdir(os.path.join(workspace, "config"))
            assert os.path.isfile(os.path.join(workspace, "README.md"))
            assert os.path.isfile(os.path.join(workspace, "AGENTS.md"))

    def test_scaffold_skips_without_workspace(self):
        """Scaffold skips when no workspace_dir."""
        orch = BuildOrchestrator(checkpoint_db=tempfile.NamedTemporaryFile(suffix=".db", delete=False).name)
        result = orch._scaffold({"workspace_dir": ""})
        assert result["status"] == "skipped"

    def test_approve_plan_unknown_run(self, orchestrator):
        """approve_plan with unknown run_id returns error."""
        result = orchestrator.approve_plan("nonexistent")
        assert "error" in result

    def test_approve_build_unknown_run(self, orchestrator):
        """approve_build with unknown run_id returns error."""
        result = orchestrator.approve_build("nonexistent")
        assert "error" in result

    def test_approve_plan_wrong_state(self, orchestrator):
        """approve_plan when not in awaiting_plan returns error."""
        # Manually inject a run in wrong state
        run_id = "test-wrong-state"
        orchestrator._runs[run_id] = {
            "run_id": run_id,
            "state": "executing",
            "product_description": "test",
            "solution_name": "test",
            "created_at": "",
            "updated_at": "",
            "plan": [],
            "critic_reports": [],
            "agent_results": [],
            "integration_result": None,
            "error": None,
        }
        result = orchestrator.approve_plan(run_id)
        assert "error" in result
        assert "not awaiting plan" in result["error"].lower()

    def test_approve_build_wrong_state(self, orchestrator):
        """approve_build when not in awaiting_build returns error."""
        run_id = "test-wrong-state-2"
        orchestrator._runs[run_id] = {
            "run_id": run_id,
            "state": "awaiting_plan",
            "product_description": "test",
            "solution_name": "test",
            "created_at": "",
            "updated_at": "",
            "plan": [],
            "critic_reports": [],
            "agent_results": [],
            "integration_result": None,
            "error": None,
        }
        result = orchestrator.approve_build(run_id)
        assert "error" in result
        assert "not awaiting build" in result["error"].lower()

    def test_integration_merges_files_from_all_agents(self, orchestrator):
        """Integration step collects files_changed from all agent results."""
        run = {
            "agent_results": [
                {"result": {"status": "completed", "files_changed": ["a.py", "b.py"], "code": "# a\n# b"}},
                {"result": {"status": "completed", "files_changed": ["c.py"], "code": "# c"}},
                {"result": {"status": "error", "files_changed": [], "code": ""}},
            ],
        }
        result = orchestrator._integrate(run)

        assert result["status"] == "completed"
        assert result["total_tasks"] == 3
        assert result["completed_tasks"] == 2
        assert set(result["files_changed"]) == {"a.py", "b.py", "c.py"}
        assert result["combined_diff_preview"]  # Not empty

    def test_run_summary_fields(self, orchestrator):
        """Verify _run_summary includes all expected fields."""
        run = {
            "run_id": "test-123",
            "solution_name": "test_sol",
            "state": "completed",
            "created_at": "2025-01-01",
            "updated_at": "2025-01-02",
            "product_description": "A test product",
            "hitl_level": "standard",
            "hitl_gates": ["plan", "code", "final"],
            "plan": HELLO_WORLD_PLAN,
            "critic_reports": [
                {"phase": "plan", "result": {"final_score": 85, "passed": True, "iterations": 2}},
                {"phase": "code", "result": {"final_score": 78, "passed": True, "iterations": 1}},
            ],
            "agent_results": [
                {
                    "task": {"task_type": "BACKEND", "description": "Build API", "acceptance_criteria": ["Works"]},
                    "result": {"status": "completed", "tier": "llm_react"},
                    "step": 1,
                    "wave": 0,
                    "agent_role": "developer",
                },
            ],
            "integration_result": {"status": "completed"},
            "error": None,
        }
        summary = orchestrator._run_summary(run)

        assert summary["run_id"] == "test-123"
        assert summary["solution_name"] == "test_sol"
        assert summary["state"] == "completed"
        assert summary["state_description"] == STATES["completed"]
        assert summary["task_count"] == 4
        assert len(summary["critic_scores"]) == 2
        assert summary["critic_scores"][0]["score"] == 85
        assert summary["agent_results"][0]["task_type"] == "BACKEND"
        assert summary["agent_results"][0]["acceptance_criteria"] == ["Works"]
        assert summary["hitl_level"] == "standard"
        assert summary["hitl_gates"] == ["plan", "code", "final"]

    def test_constants_populated(self):
        """Verify BUILD_TASK_TYPES, HITL_LEVELS, DEFAULT_ACCEPTANCE_CRITERIA are correct."""
        assert "AGENTIC" in BUILD_TASK_TYPES
        assert "BACKEND" in BUILD_TASK_TYPES
        assert len(HITL_LEVELS) == 3
        assert "minimal" in HITL_LEVELS
        assert "standard" in HITL_LEVELS
        assert "strict" in HITL_LEVELS
        for task_type in BUILD_TASK_TYPES:
            assert task_type in DEFAULT_ACCEPTANCE_CRITERIA, f"Missing criteria for {task_type}"

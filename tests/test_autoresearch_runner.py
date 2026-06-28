"""
SAGE Framework — AutoResearch Runner TDD Tests
=================================================
Tests for the autoresearch_runner.py BaseRunner implementation.

The AutoResearchRunner wraps the AutoResearchEngine as a proper BaseRunner
so Agent Gym can train research_engineer/ml_researcher roles.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _mock_llm_response():
    return json.dumps({
        "description": "Increase depth to 12",
        "hypothesis": "Deeper model captures more",
        "changes": [],
        "expected_effect": "Lower val_bpb",
    })


# ===========================================================================
# Group 1: BaseRunner Contract
# ===========================================================================

class TestBaseRunnerContract:
    """AutoResearchRunner must implement all BaseRunner abstract methods."""

    def test_is_base_runner(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        from src.integrations.base_runner import BaseRunner
        runner = AutoResearchRunner()
        assert isinstance(runner, BaseRunner)

    def test_name_is_autoresearch(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        runner = AutoResearchRunner()
        assert runner.name == "autoresearch"

    def test_roles_include_research_engineer(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        runner = AutoResearchRunner()
        assert "research_engineer" in runner.roles
        assert "ml_researcher" in runner.roles

    def test_has_execute(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        runner = AutoResearchRunner()
        assert callable(getattr(runner, "execute", None))

    def test_has_verify(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        runner = AutoResearchRunner()
        assert callable(getattr(runner, "verify", None))

    def test_has_get_exercises(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        runner = AutoResearchRunner()
        assert callable(getattr(runner, "get_exercises", None))

    def test_has_grade_exercise(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        runner = AutoResearchRunner()
        assert callable(getattr(runner, "grade_exercise", None))


# ===========================================================================
# Group 2: Execute
# ===========================================================================

class TestExecute:
    """Execute wraps AutoResearchEngine.run_experiment."""

    def test_execute_returns_run_result(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        from src.integrations.base_runner import RunResult
        runner = AutoResearchRunner()
        task = {
            "description": "Optimize learning rate",
            "task_type": "hyperparameter_search",
            "payload": {
                "workspace": "/tmp/test",
                "metric_name": "val_loss",
                "run_command": "python train.py",
            },
        }
        with patch("src.core.llm_gateway.llm_gateway.generate", return_value=_mock_llm_response()), \
             patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="val_loss: 2.80", stderr="")):
            result = runner.execute(task, "/tmp/test")
        assert isinstance(result, RunResult)
        assert result.runner == "autoresearch"

    def test_execute_error_returns_error_status(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        runner = AutoResearchRunner()
        task = {"description": "Test", "payload": {}}
        with patch("src.core.auto_research.AutoResearchEngine.run_experiment", side_effect=Exception("boom")):
            result = runner.execute(task, "/tmp/test")
        assert result.status == "error"


# ===========================================================================
# Group 3: Verify
# ===========================================================================

class TestVerify:
    """Verify checks experiment results."""

    def test_verify_completed(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        from src.integrations.base_runner import RunResult, VerificationReport
        runner = AutoResearchRunner()
        result = RunResult(
            run_id="test", status="completed", runner="autoresearch", tier="direct",
            metrics={"decision": "keep", "metric_value": 2.80, "baseline": 2.90},
        )
        report = runner.verify(result, {"description": "test"})
        assert isinstance(report, VerificationReport)
        assert report.score > 0

    def test_verify_error_gives_zero(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        from src.integrations.base_runner import RunResult
        runner = AutoResearchRunner()
        result = RunResult(
            run_id="test", status="error", runner="autoresearch", tier="direct",
        )
        report = runner.verify(result, {"description": "test"})
        assert report.passed is False
        assert report.score == 0.0


# ===========================================================================
# Group 4: Exercises
# ===========================================================================

class TestExercises:
    """Get exercises from the central catalog."""

    def test_get_exercises_returns_list(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        runner = AutoResearchRunner()
        exercises = runner.get_exercises("beginner")
        assert isinstance(exercises, list)
        assert len(exercises) > 0

    def test_exercises_have_correct_domain(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        runner = AutoResearchRunner()
        exercises = runner.get_exercises("intermediate")
        for ex in exercises:
            assert ex.role in ("research_engineer", "ml_researcher")

    def test_all_difficulties_available(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        runner = AutoResearchRunner()
        for diff in ["beginner", "intermediate", "advanced", "expert"]:
            exercises = runner.get_exercises(diff)
            assert len(exercises) > 0, f"No exercises for {diff}"


# ===========================================================================
# Group 5: Grading
# ===========================================================================

class TestGrading:
    """Grade exercise attempts."""

    def test_grade_returns_score(self):
        from src.integrations.autoresearch_runner import AutoResearchRunner
        from src.integrations.base_runner import RunResult, Exercise, ExerciseScore
        runner = AutoResearchRunner()
        exercise = Exercise(
            id="test-ex", role="research_engineer", task_type="hyperparameter_search",
            difficulty="beginner", description="Grid search LR",
            acceptance_criteria=["Grid search runs", "Best rate found"],
            expected_artifacts=["results.json"],
        )
        result = RunResult(
            run_id="test", status="completed", runner="autoresearch", tier="direct",
            output="Experiment complete. val_loss: 2.80. Decision: keep.",
            metrics={"decision": "keep", "metric_value": 2.80},
        )
        with patch("src.core.llm_gateway.llm_gateway.generate", return_value=json.dumps({"score": 75, "feedback": "good", "hints": []})):
            score = runner.grade_exercise(exercise, result)
        assert isinstance(score, ExerciseScore)
        assert score.score > 0


# ===========================================================================
# Group 6: Registration
# ===========================================================================

class TestRegistration:
    """Runner should auto-register on import."""

    def test_registered_in_runner_list(self):
        from src.integrations.base_runner import get_runner_by_name
        runner = get_runner_by_name("autoresearch")
        assert runner is not None
        assert runner.name == "autoresearch"

    def test_role_lookup_works(self):
        from src.integrations.base_runner import get_runner_for_role
        for role in ["research_engineer", "ml_researcher"]:
            runner = get_runner_for_role(role)
            assert runner is not None, f"No runner for role: {role}"
            assert runner.name == "autoresearch"

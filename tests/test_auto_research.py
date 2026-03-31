"""
SAGE Framework — AutoResearch Engine TDD Tests
=================================================
Tests written FIRST (TDD) for the Karpathy-inspired autonomous research engine.

Inspired by: https://github.com/karpathy/autoresearch

Features tested:
  1. Experiment loop (modify → run → measure → keep/discard)
  2. Git-based experiment tracking (branch, commit, reset)
  3. Fixed-budget execution (wall-clock constrained)
  4. Metric extraction from experiment output
  5. Results logging (TSV-style structured log)
  6. Continuous training mode (never-stop principle)
  7. Integration with Agent Gym and Meta-Optimizer
  8. Experiment history and analytics
  9. Crash recovery (detect crash, attempt fix, log and move on)
 10. Research program loading (Markdown-as-skill)
"""

import json
import os
import tempfile
import time
from unittest.mock import MagicMock, patch, call

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_engine(db_path=None):
    """Create an AutoResearchEngine with a temp database."""
    from src.core.auto_research import AutoResearchEngine
    if db_path is None:
        db_path = os.path.join(tempfile.mkdtemp(), "auto_research.db")
    return AutoResearchEngine(db_path=db_path)


def _mock_experiment_result(metric=2.85, status="completed", crashed=False):
    """Create a mock experiment run result."""
    return {
        "status": "crashed" if crashed else status,
        "metric_value": metric,
        "metric_name": "val_bpb",
        "output": f"Training complete. val_bpb: {metric}" if not crashed else "RuntimeError: CUDA OOM",
        "duration_s": 280.0,
        "memory_gb": 42.5,
        "commit_hash": "abc1234",
        "files_changed": ["train.py"],
    }


def _mock_llm_code_change():
    """Mock LLM response proposing a code change."""
    return json.dumps({
        "description": "Increase model depth from 8 to 12 layers",
        "hypothesis": "Deeper model should capture more complex patterns",
        "changes": [
            {
                "file": "train.py",
                "search": "DEPTH = 8",
                "replace": "DEPTH = 12",
            }
        ],
        "expected_effect": "Lower val_bpb by ~0.05",
    })


def _mock_llm_ctx(response_text=None):
    if response_text is None:
        response_text = _mock_llm_code_change()
    return patch("src.core.llm_gateway.llm_gateway.generate", return_value=response_text)


def _mock_subprocess_ctx(returncode=0, stdout="val_bpb: 2.80"):
    mock_result = MagicMock(returncode=returncode, stdout=stdout, stderr="")
    return patch("subprocess.run", return_value=mock_result)


# ===========================================================================
# Group 1: Experiment Loop
# ===========================================================================

class TestExperimentLoop:
    """Core experiment loop: modify → run → measure → keep/discard."""

    def test_run_experiment_returns_result(self):
        engine = _fresh_engine()
        with _mock_llm_ctx(), \
             patch.object(engine, "_execute_experiment", return_value=_mock_experiment_result(2.80)), \
             patch.object(engine, "_git_commit", return_value="abc1234"), \
             patch.object(engine, "_git_reset"):
            result = engine.run_experiment(
                workspace="/tmp/test",
                metric_name="val_bpb",
                run_command="uv run train.py",
            )
            assert isinstance(result, dict)
            assert "status" in result
            assert "metric_value" in result

    def test_keep_on_improvement(self):
        """Experiment with better metric should be kept."""
        engine = _fresh_engine()
        engine._baseline_metric = 2.90
        with _mock_llm_ctx(), \
             patch.object(engine, "_execute_experiment", return_value=_mock_experiment_result(2.80)), \
             patch.object(engine, "_git_commit", return_value="abc1234"), \
             patch.object(engine, "_git_reset") as mock_reset:
            result = engine.run_experiment(
                workspace="/tmp/test",
                metric_name="val_bpb",
                run_command="uv run train.py",
            )
            assert result["decision"] == "keep"
            mock_reset.assert_not_called()

    def test_discard_on_regression(self):
        """Experiment with worse metric should be discarded."""
        engine = _fresh_engine()
        engine._baseline_metric = 2.80
        with _mock_llm_ctx(), \
             patch.object(engine, "_execute_experiment", return_value=_mock_experiment_result(2.95)), \
             patch.object(engine, "_git_commit", return_value="abc1234"), \
             patch.object(engine, "_git_reset") as mock_reset:
            result = engine.run_experiment(
                workspace="/tmp/test",
                metric_name="val_bpb",
                run_command="uv run train.py",
            )
            assert result["decision"] == "discard"
            mock_reset.assert_called_once()

    def test_discard_on_equal(self):
        """No improvement = discard (avoid complexity for no gain)."""
        engine = _fresh_engine()
        engine._baseline_metric = 2.85
        with _mock_llm_ctx(), \
             patch.object(engine, "_execute_experiment", return_value=_mock_experiment_result(2.85)), \
             patch.object(engine, "_git_commit", return_value="abc1234"), \
             patch.object(engine, "_git_reset") as mock_reset:
            result = engine.run_experiment(
                workspace="/tmp/test",
                metric_name="val_bpb",
                run_command="uv run train.py",
            )
            assert result["decision"] == "discard"

    def test_baseline_updates_on_keep(self):
        """After keeping, baseline should update to new metric."""
        engine = _fresh_engine()
        engine._baseline_metric = 2.90
        with _mock_llm_ctx(), \
             patch.object(engine, "_execute_experiment", return_value=_mock_experiment_result(2.75)), \
             patch.object(engine, "_git_commit", return_value="abc1234"), \
             patch.object(engine, "_git_reset"):
            engine.run_experiment(
                workspace="/tmp/test",
                metric_name="val_bpb",
                run_command="uv run train.py",
            )
            assert engine._baseline_metric == 2.75


# ===========================================================================
# Group 2: Git-Based Experiment Tracking
# ===========================================================================

class TestGitTracking:
    """Git branch, commit, and reset for experiment management."""

    def test_create_experiment_branch(self):
        engine = _fresh_engine()
        with _mock_subprocess_ctx():
            branch = engine._create_branch("/tmp/test", "experiment-tag")
            assert "autoresearch" in branch

    def test_git_commit_returns_hash(self):
        engine = _fresh_engine()
        with _mock_subprocess_ctx(stdout="abc1234def"):
            commit_hash = engine._git_commit("/tmp/test", "Increase depth to 12")
            assert isinstance(commit_hash, str)
            assert len(commit_hash) > 0

    def test_git_reset_discards_changes(self):
        engine = _fresh_engine()
        with _mock_subprocess_ctx() as mock_run:
            engine._git_reset("/tmp/test")
            called_args = str(mock_run.call_args_list)
            assert "reset" in called_args

    def test_apply_code_changes(self):
        """Apply LLM-proposed changes to files."""
        engine = _fresh_engine()
        changes = [
            {"file": "train.py", "search": "DEPTH = 8", "replace": "DEPTH = 12"}
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# Model config\nDEPTH = 8\nWIDTH = 512\n")
            f.flush()
            changes[0]["file"] = f.name
            success = engine._apply_changes(changes, os.path.dirname(f.name))
            assert success is True
            with open(f.name) as check:
                content = check.read()
                assert "DEPTH = 12" in content
            os.unlink(f.name)


# ===========================================================================
# Group 3: Fixed-Budget Execution
# ===========================================================================

class TestFixedBudgetExecution:
    """Experiments run with wall-clock time constraint."""

    def test_budget_default_is_300_seconds(self):
        engine = _fresh_engine()
        assert engine._default_budget_s == 300

    def test_budget_configurable(self):
        engine = _fresh_engine()
        engine._default_budget_s = 600
        assert engine._default_budget_s == 600

    def test_execution_respects_timeout(self):
        engine = _fresh_engine()
        with _mock_subprocess_ctx() as mock_run:
            engine._execute_experiment(
                workspace="/tmp/test",
                run_command="uv run train.py",
                budget_s=300,
            )
            # subprocess.run should be called with timeout
            call_kwargs = mock_run.call_args
            assert call_kwargs is not None

    def test_timeout_returns_crash_status(self):
        """Experiment exceeding budget should be marked as crashed."""
        engine = _fresh_engine()
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 300)):
            result = engine._execute_experiment(
                workspace="/tmp/test",
                run_command="uv run train.py",
                budget_s=300,
            )
            assert result["status"] == "crashed"
            assert "timeout" in result.get("error", "").lower()


# ===========================================================================
# Group 4: Metric Extraction
# ===========================================================================

class TestMetricExtraction:
    """Extract metrics from experiment output."""

    def test_extract_val_bpb(self):
        engine = _fresh_engine()
        output = "step 1000 | loss 3.45 | val_bpb: 2.847 | lr 0.001"
        metric = engine._extract_metric(output, "val_bpb")
        assert abs(metric - 2.847) < 0.001

    def test_extract_custom_metric(self):
        engine = _fresh_engine()
        output = "Epoch 10 | accuracy: 0.952 | loss: 0.123"
        metric = engine._extract_metric(output, "accuracy")
        assert abs(metric - 0.952) < 0.001

    def test_missing_metric_returns_none(self):
        engine = _fresh_engine()
        output = "Training started..."
        metric = engine._extract_metric(output, "val_bpb")
        assert metric is None

    def test_extract_last_occurrence(self):
        """If metric appears multiple times, use the last (final) value."""
        engine = _fresh_engine()
        output = "step 100 | val_bpb: 3.50\nstep 200 | val_bpb: 3.20\nstep 300 | val_bpb: 2.85"
        metric = engine._extract_metric(output, "val_bpb")
        assert abs(metric - 2.85) < 0.001

    def test_metric_direction_lower_is_better(self):
        engine = _fresh_engine()
        assert engine._is_improvement(2.80, 2.90, "lower") is True
        assert engine._is_improvement(2.95, 2.90, "lower") is False

    def test_metric_direction_higher_is_better(self):
        engine = _fresh_engine()
        assert engine._is_improvement(0.95, 0.90, "higher") is True
        assert engine._is_improvement(0.85, 0.90, "higher") is False


# ===========================================================================
# Group 5: Results Logging
# ===========================================================================

class TestResultsLogging:
    """Structured experiment results logging."""

    def test_log_experiment_result(self):
        engine = _fresh_engine()
        engine.log_result({
            "experiment_id": "exp-001",
            "description": "Increase depth",
            "metric_value": 2.80,
            "baseline": 2.90,
            "decision": "keep",
            "commit_hash": "abc1234",
            "duration_s": 280,
            "status": "completed",
        })
        results = engine.get_results()
        assert len(results) >= 1

    def test_results_ordered_by_time(self):
        engine = _fresh_engine()
        for i in range(3):
            engine.log_result({
                "experiment_id": f"exp-{i:03d}",
                "description": f"Experiment {i}",
                "metric_value": 2.90 - i * 0.05,
                "decision": "keep" if i > 0 else "discard",
                "status": "completed",
            })
        results = engine.get_results()
        assert len(results) == 3

    def test_results_persist_across_restarts(self):
        db_path = os.path.join(tempfile.mkdtemp(), "ar.db")
        e1 = _fresh_engine(db_path)
        e1.log_result({
            "experiment_id": "exp-persist",
            "description": "Test persistence",
            "metric_value": 2.75,
            "decision": "keep",
            "status": "completed",
        })
        e2 = _fresh_engine(db_path)
        results = e2.get_results()
        assert any(r.get("experiment_id") == "exp-persist" for r in results)

    def test_get_best_result(self):
        engine = _fresh_engine()
        for val in [2.90, 2.75, 2.85]:
            engine.log_result({
                "experiment_id": f"exp-{val}",
                "metric_value": val,
                "decision": "keep",
                "status": "completed",
            })
        best = engine.get_best_result(direction="lower")
        assert best["metric_value"] == 2.75


# ===========================================================================
# Group 6: Continuous Training Mode
# ===========================================================================

class TestContinuousMode:
    """Never-stop principle: run experiments until manually stopped."""

    def test_run_session_with_max_experiments(self):
        """Session runs N experiments and returns all results."""
        engine = _fresh_engine()
        with _mock_llm_ctx(), \
             patch.object(engine, "_execute_experiment", return_value=_mock_experiment_result(2.80)), \
             patch.object(engine, "_git_commit", return_value="abc1234"), \
             patch.object(engine, "_git_reset"), \
             patch.object(engine, "_create_branch", return_value="autoresearch/test"), \
             patch.object(engine, "_run_baseline", return_value=2.90), \
             patch.object(engine, "_apply_changes", return_value=True):
            session = engine.run_session(
                workspace="/tmp/test",
                metric_name="val_bpb",
                run_command="uv run train.py",
                max_experiments=3,
            )
            assert isinstance(session, dict)
            assert session["total_experiments"] == 3

    def test_session_tracks_kept_and_discarded(self):
        engine = _fresh_engine()
        results = [
            _mock_experiment_result(2.80),  # keep (better than 2.90)
            _mock_experiment_result(2.95),  # discard (worse than 2.80)
            _mock_experiment_result(2.70),  # keep (better than 2.80)
        ]
        call_idx = [0]
        def mock_execute(*a, **kw):
            r = results[min(call_idx[0], len(results)-1)]
            call_idx[0] += 1
            return r

        with _mock_llm_ctx(), \
             patch.object(engine, "_execute_experiment", side_effect=mock_execute), \
             patch.object(engine, "_git_commit", return_value="abc1234"), \
             patch.object(engine, "_git_reset"), \
             patch.object(engine, "_create_branch", return_value="autoresearch/test"), \
             patch.object(engine, "_run_baseline", return_value=2.90), \
             patch.object(engine, "_apply_changes", return_value=True):
            session = engine.run_session(
                workspace="/tmp/test",
                metric_name="val_bpb",
                run_command="uv run train.py",
                max_experiments=3,
            )
            assert session["kept"] >= 1
            assert session["discarded"] >= 1

    def test_session_updates_baseline_progressively(self):
        engine = _fresh_engine()
        improvements = [2.85, 2.80, 2.75]
        call_idx = [0]
        baselines_seen = []

        original_run = engine.run_experiment
        def track_baseline(*a, **kw):
            baselines_seen.append(engine._baseline_metric)
            result = _mock_experiment_result(improvements[min(call_idx[0], len(improvements)-1)])
            call_idx[0] += 1
            return result

        with _mock_llm_ctx(), \
             patch.object(engine, "_execute_experiment", side_effect=track_baseline), \
             patch.object(engine, "_git_commit", return_value="abc"), \
             patch.object(engine, "_git_reset"), \
             patch.object(engine, "_create_branch", return_value="autoresearch/test"), \
             patch.object(engine, "_run_baseline", return_value=2.90), \
             patch.object(engine, "_apply_changes", return_value=True):
            engine.run_session(
                workspace="/tmp/test",
                metric_name="val_bpb",
                run_command="uv run train.py",
                max_experiments=3,
            )
            # Baseline should have improved over time
            assert engine._baseline_metric < 2.90


# ===========================================================================
# Group 7: Crash Recovery
# ===========================================================================

class TestCrashRecovery:
    """Handle experiment crashes gracefully."""

    def test_crash_logged_but_loop_continues(self):
        engine = _fresh_engine()
        results = [
            _mock_experiment_result(crashed=True),
            _mock_experiment_result(2.80),
        ]
        call_idx = [0]
        def mock_execute(*a, **kw):
            r = results[min(call_idx[0], len(results)-1)]
            call_idx[0] += 1
            return r

        with _mock_llm_ctx(), \
             patch.object(engine, "_execute_experiment", side_effect=mock_execute), \
             patch.object(engine, "_git_commit", return_value="abc"), \
             patch.object(engine, "_git_reset"), \
             patch.object(engine, "_create_branch", return_value="autoresearch/test"), \
             patch.object(engine, "_run_baseline", return_value=2.90), \
             patch.object(engine, "_apply_changes", return_value=True):
            session = engine.run_session(
                workspace="/tmp/test",
                metric_name="val_bpb",
                run_command="uv run train.py",
                max_experiments=2,
            )
            assert session["crashed"] >= 1
            assert session["total_experiments"] == 2

    def test_crash_triggers_git_reset(self):
        engine = _fresh_engine()
        with _mock_llm_ctx(), \
             patch.object(engine, "_execute_experiment", return_value=_mock_experiment_result(crashed=True)), \
             patch.object(engine, "_git_commit", return_value="abc"), \
             patch.object(engine, "_git_reset") as mock_reset, \
             patch.object(engine, "_apply_changes", return_value=True):
            engine.run_experiment(
                workspace="/tmp/test",
                metric_name="val_bpb",
                run_command="uv run train.py",
            )
            mock_reset.assert_called()


# ===========================================================================
# Group 8: Research Program Loading
# ===========================================================================

class TestResearchProgram:
    """Load research instructions from program.md (Markdown-as-skill)."""

    def test_load_program_md(self):
        engine = _fresh_engine()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Research Program\n\nModify train.py to improve val_bpb.\n")
            f.flush()
            program = engine.load_program(f.name)
            assert isinstance(program, str)
            assert "val_bpb" in program
            os.unlink(f.name)

    def test_program_injected_into_llm_prompt(self):
        engine = _fresh_engine()
        engine._program = "Focus on architecture changes. Do not change the optimizer."
        prompt = engine._build_experiment_prompt(
            workspace="/tmp/test",
            baseline=2.90,
            history=[],
        )
        assert "architecture" in prompt.lower()
        assert "optimizer" in prompt.lower()

    def test_missing_program_uses_default(self):
        engine = _fresh_engine()
        program = engine.load_program("/nonexistent/program.md")
        assert isinstance(program, str)
        assert len(program) > 0  # Default instructions


# ===========================================================================
# Group 9: Statistics & Analytics
# ===========================================================================

class TestAnalytics:
    """Experiment analytics and reporting."""

    def test_stats_returns_dict(self):
        engine = _fresh_engine()
        stats = engine.stats()
        assert isinstance(stats, dict)
        assert "total_experiments" in stats

    def test_stats_with_experiments(self):
        engine = _fresh_engine()
        for i in range(5):
            engine.log_result({
                "experiment_id": f"exp-{i}",
                "metric_value": 2.90 - i * 0.03,
                "decision": "keep" if i % 2 == 0 else "discard",
                "status": "completed",
            })
        stats = engine.stats()
        assert stats["total_experiments"] == 5
        assert stats["kept"] >= 1
        assert stats["discarded"] >= 1

    def test_improvement_over_time(self):
        engine = _fresh_engine()
        for i in range(5):
            engine.log_result({
                "experiment_id": f"exp-{i}",
                "metric_value": 2.90 - i * 0.05,
                "decision": "keep",
                "status": "completed",
                "baseline": 2.90,
            })
        stats = engine.stats()
        assert "best_metric" in stats
        assert stats["best_metric"] < 2.90

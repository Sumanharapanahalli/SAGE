"""
SAGE Framework — Meta-Optimization Loop TDD Tests
====================================================
Tests written FIRST (TDD) for the harness evolution engine.

Inspired by Stanford IRIS Lab's Meta-Harness methodology:
  - An outer loop evolves the agent harness (prompts, tools, strategies)
  - Uses full execution traces (not just scores) to propose improvements
  - Each iteration produces a candidate harness, evaluated on task set
  - Access to raw traces is critical (50% vs 34.6% with scores-only)

SAGE integration:
  - Execution traces come from audit logs + Agent Gym sessions
  - Harness proposals modify system prompts, tool schemas, or runner config
  - Evaluation uses Agent Gym exercise scoring
  - History persisted in SQLite for cross-session learning

Features tested:
  1. Trace collection from Agent Gym sessions
  2. Harness proposal generation via LLM
  3. Proposal evaluation on exercise set
  4. Iteration history and persistence
  5. Integration with Agent Gym training loop
  6. Convergence detection
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_optimizer(db_path=None):
    """Create a MetaOptimizer with a temp database."""
    from src.core.meta_optimizer import MetaOptimizer
    if db_path is None:
        db_path = os.path.join(tempfile.mkdtemp(), "meta_opt.db")
    return MetaOptimizer(db_path=db_path)


def _mock_training_session(score=75, passed=True):
    """Create a mock Agent Gym training session dict."""
    return {
        "session_id": "sess-001",
        "agent_role": "developer",
        "runner_name": "openswe",
        "exercise_id": "swe-i01",
        "difficulty": "intermediate",
        "status": "completed",
        "grade": {"score": score, "passed": passed},
        "critic_reviews": {"primary": {"score": 70}},
        "attempt_result": {
            "status": "completed",
            "output": "def hello():\n    return 'world'",
            "commands_executed": 3,
        },
        "reflection": "Could have added error handling",
        "improvement_plan": ["Add try/except", "Add type hints"],
    }


def _mock_execution_trace():
    """Create a mock execution trace (the key ingredient for meta-optimization)."""
    return {
        "session_id": "sess-001",
        "role": "developer",
        "runner": "openswe",
        "turns": [
            {"role": "system", "content": "You are a senior software engineer..."},
            {"role": "user", "content": "Build a REST API for user management"},
            {"role": "assistant", "content": "THOUGHT: I need to create a Flask app..."},
            {"role": "user", "content": "Output: app.py created successfully"},
            {"role": "assistant", "content": "THOUGHT: Now I need tests..."},
        ],
        "final_score": 75,
        "passed": True,
        "duration_s": 45.2,
        "failure_points": [],
    }


def _mock_harness_proposal():
    """Create a mock harness improvement proposal."""
    return {
        "proposal_id": "prop-001",
        "target": "system_prompt",
        "changes": [
            {
                "component": "system_prompt",
                "before": "You are a senior software engineer.",
                "after": "You are a senior software engineer. Always start by reading existing code before making changes.",
                "rationale": "Agents frequently modify code without reading it first, causing regressions.",
            }
        ],
        "expected_improvement": "Reduce regression rate by ~15%",
        "confidence": 0.7,
    }


def _mock_llm_ctx(response_text=None):
    if response_text is None:
        response_text = json.dumps(_mock_harness_proposal())
    return patch("src.core.llm_gateway.llm_gateway.generate", return_value=response_text)


# ===========================================================================
# Group 1: Trace Collection
# ===========================================================================

class TestTraceCollection:
    """Collecting execution traces from Agent Gym sessions."""

    def test_collect_traces_from_sessions(self):
        optimizer = _fresh_optimizer()
        sessions = [_mock_training_session(score=60), _mock_training_session(score=85)]
        traces = optimizer.collect_traces(sessions)
        assert isinstance(traces, list)
        assert len(traces) == 2

    def test_trace_includes_full_output(self):
        """Traces must include the full agent output, not just scores."""
        optimizer = _fresh_optimizer()
        session = _mock_training_session()
        session["attempt_result"]["output"] = "full execution output here"
        traces = optimizer.collect_traces([session])
        assert any("full execution output" in str(t) for t in traces)

    def test_trace_includes_score(self):
        optimizer = _fresh_optimizer()
        traces = optimizer.collect_traces([_mock_training_session(score=42)])
        assert any(t.get("score") == 42 for t in traces if isinstance(t, dict))

    def test_trace_includes_failure_info(self):
        """Failed sessions must include what went wrong."""
        optimizer = _fresh_optimizer()
        session = _mock_training_session(score=20, passed=False)
        session["reflection"] = "Failed because of missing dependency"
        traces = optimizer.collect_traces([session])
        trace = traces[0]
        assert "reflection" in trace or "failure" in str(trace).lower()

    def test_empty_sessions_returns_empty(self):
        optimizer = _fresh_optimizer()
        traces = optimizer.collect_traces([])
        assert traces == []


# ===========================================================================
# Group 2: Harness Proposal Generation
# ===========================================================================

class TestHarnessProposal:
    """LLM generates improvement proposals from execution traces."""

    def test_propose_returns_proposal_dict(self):
        optimizer = _fresh_optimizer()
        traces = [_mock_execution_trace()]
        with _mock_llm_ctx():
            proposal = optimizer.propose_improvement(traces, runner_name="openswe")
            assert isinstance(proposal, dict)
            assert "proposal_id" in proposal or "changes" in proposal

    def test_proposal_includes_changes(self):
        optimizer = _fresh_optimizer()
        with _mock_llm_ctx():
            proposal = optimizer.propose_improvement(
                [_mock_execution_trace()], runner_name="openswe"
            )
            assert "changes" in proposal
            assert len(proposal["changes"]) > 0

    def test_proposal_includes_rationale(self):
        optimizer = _fresh_optimizer()
        with _mock_llm_ctx():
            proposal = optimizer.propose_improvement(
                [_mock_execution_trace()], runner_name="openswe"
            )
            changes = proposal.get("changes", [])
            assert any("rationale" in c for c in changes)

    def test_proposal_targets_valid_component(self):
        """Proposals can target: system_prompt, tool_schema, strategy, config."""
        optimizer = _fresh_optimizer()
        valid_targets = {"system_prompt", "tool_schema", "strategy", "config"}
        with _mock_llm_ctx():
            proposal = optimizer.propose_improvement(
                [_mock_execution_trace()], runner_name="openswe"
            )
            target = proposal.get("target", "")
            assert target in valid_targets

    def test_proposal_from_low_score_traces(self):
        """Low-scoring traces should produce more aggressive proposals."""
        optimizer = _fresh_optimizer()
        low_trace = _mock_execution_trace()
        low_trace["final_score"] = 20
        low_trace["failure_points"] = ["timeout", "wrong_output"]
        with _mock_llm_ctx():
            proposal = optimizer.propose_improvement([low_trace], runner_name="openswe")
            assert isinstance(proposal, dict)

    def test_llm_failure_returns_empty_proposal(self):
        optimizer = _fresh_optimizer()
        with patch("src.core.llm_gateway.llm_gateway.generate", side_effect=Exception("LLM down")):
            proposal = optimizer.propose_improvement(
                [_mock_execution_trace()], runner_name="openswe"
            )
            assert proposal.get("changes", []) == [] or proposal.get("error") is not None


# ===========================================================================
# Group 3: Proposal Evaluation
# ===========================================================================

class TestProposalEvaluation:
    """Evaluate harness proposals against exercise sets."""

    def test_evaluate_returns_score(self):
        optimizer = _fresh_optimizer()
        proposal = _mock_harness_proposal()
        with patch.object(optimizer, "_run_evaluation_sessions", return_value=[
            {"score": 80, "passed": True},
            {"score": 75, "passed": True},
        ]):
            result = optimizer.evaluate_proposal(proposal, runner_name="openswe")
            assert "score" in result
            assert isinstance(result["score"], (int, float))

    def test_evaluate_compares_baseline(self):
        """Evaluation must compare against baseline (without proposal)."""
        optimizer = _fresh_optimizer()
        proposal = _mock_harness_proposal()
        with patch.object(optimizer, "_run_evaluation_sessions", return_value=[
            {"score": 85, "passed": True},
        ]):
            result = optimizer.evaluate_proposal(
                proposal, runner_name="openswe", baseline_score=70.0
            )
            assert "improvement" in result or "delta" in result

    def test_evaluate_negative_improvement(self):
        """Proposals that hurt performance should be flagged."""
        optimizer = _fresh_optimizer()
        proposal = _mock_harness_proposal()
        with patch.object(optimizer, "_run_evaluation_sessions", return_value=[
            {"score": 40, "passed": False},
        ]):
            result = optimizer.evaluate_proposal(
                proposal, runner_name="openswe", baseline_score=70.0
            )
            delta = result.get("improvement", result.get("delta", 0))
            assert delta < 0

    def test_evaluate_returns_session_details(self):
        optimizer = _fresh_optimizer()
        proposal = _mock_harness_proposal()
        with patch.object(optimizer, "_run_evaluation_sessions", return_value=[
            {"score": 90, "passed": True, "exercise_id": "swe-i01"},
        ]):
            result = optimizer.evaluate_proposal(proposal, runner_name="openswe")
            assert "sessions" in result or "details" in result


# ===========================================================================
# Group 4: Iteration History & Persistence
# ===========================================================================

class TestIterationHistory:
    """Meta-optimization iterations persisted in SQLite."""

    def test_save_iteration(self):
        optimizer = _fresh_optimizer()
        iteration = {
            "iteration_id": "iter-001",
            "runner_name": "openswe",
            "proposal": _mock_harness_proposal(),
            "evaluation": {"score": 82.5, "improvement": 12.5},
            "accepted": True,
        }
        optimizer.save_iteration(iteration)
        history = optimizer.get_history(runner_name="openswe")
        assert len(history) >= 1

    def test_history_ordered_by_iteration(self):
        optimizer = _fresh_optimizer()
        for i in range(3):
            optimizer.save_iteration({
                "iteration_id": f"iter-{i:03d}",
                "runner_name": "openswe",
                "proposal": _mock_harness_proposal(),
                "evaluation": {"score": 70 + i * 5},
                "accepted": i == 2,
            })
        history = optimizer.get_history(runner_name="openswe")
        assert len(history) == 3

    def test_history_survives_restart(self):
        """Persistence must survive optimizer re-creation."""
        db_path = os.path.join(tempfile.mkdtemp(), "meta_opt.db")
        opt1 = _fresh_optimizer(db_path)
        opt1.save_iteration({
            "iteration_id": "iter-persist",
            "runner_name": "openswe",
            "proposal": _mock_harness_proposal(),
            "evaluation": {"score": 90},
            "accepted": True,
        })

        opt2 = _fresh_optimizer(db_path)
        history = opt2.get_history(runner_name="openswe")
        assert len(history) >= 1
        assert any(h.get("iteration_id") == "iter-persist" for h in history)

    def test_get_best_iteration(self):
        optimizer = _fresh_optimizer()
        for i, score in enumerate([60, 90, 75]):
            optimizer.save_iteration({
                "iteration_id": f"iter-{i:03d}",
                "runner_name": "openswe",
                "proposal": _mock_harness_proposal(),
                "evaluation": {"score": score},
                "accepted": score > 80,
            })
        best = optimizer.get_best_iteration(runner_name="openswe")
        assert best is not None
        assert best["evaluation"]["score"] == 90

    def test_history_filter_by_runner(self):
        optimizer = _fresh_optimizer()
        optimizer.save_iteration({
            "iteration_id": "iter-swe",
            "runner_name": "openswe",
            "proposal": _mock_harness_proposal(),
            "evaluation": {"score": 80},
            "accepted": True,
        })
        optimizer.save_iteration({
            "iteration_id": "iter-fw",
            "runner_name": "openfw",
            "proposal": _mock_harness_proposal(),
            "evaluation": {"score": 70},
            "accepted": True,
        })
        swe_history = optimizer.get_history(runner_name="openswe")
        fw_history = optimizer.get_history(runner_name="openfw")
        assert all(h.get("runner_name") == "openswe" for h in swe_history)
        assert all(h.get("runner_name") == "openfw" for h in fw_history)


# ===========================================================================
# Group 5: Full Optimization Loop
# ===========================================================================

class TestOptimizationLoop:
    """End-to-end meta-optimization iteration."""

    def test_run_iteration_returns_result(self):
        optimizer = _fresh_optimizer()
        with patch.object(optimizer, "collect_traces", return_value=[_mock_execution_trace()]), \
             _mock_llm_ctx(), \
             patch.object(optimizer, "evaluate_proposal", return_value={
                 "score": 85, "improvement": 15, "sessions": [],
             }):
            result = optimizer.run_iteration(runner_name="openswe")
            assert isinstance(result, dict)
            assert "iteration_id" in result
            assert "evaluation" in result

    def test_iteration_saved_to_history(self):
        optimizer = _fresh_optimizer()
        with patch.object(optimizer, "collect_traces", return_value=[_mock_execution_trace()]), \
             _mock_llm_ctx(), \
             patch.object(optimizer, "evaluate_proposal", return_value={
                 "score": 85, "improvement": 15, "sessions": [],
             }):
            optimizer.run_iteration(runner_name="openswe")
            history = optimizer.get_history(runner_name="openswe")
            assert len(history) >= 1

    def test_accepted_proposal_applied(self):
        """Proposals with positive improvement should be marked accepted."""
        optimizer = _fresh_optimizer()
        with patch.object(optimizer, "collect_traces", return_value=[_mock_execution_trace()]), \
             _mock_llm_ctx(), \
             patch.object(optimizer, "evaluate_proposal", return_value={
                 "score": 90, "improvement": 20, "sessions": [],
             }):
            result = optimizer.run_iteration(runner_name="openswe")
            assert result.get("accepted") is True

    def test_rejected_proposal_not_applied(self):
        """Proposals with negative improvement should be rejected."""
        optimizer = _fresh_optimizer()
        with patch.object(optimizer, "collect_traces", return_value=[_mock_execution_trace()]), \
             _mock_llm_ctx(), \
             patch.object(optimizer, "evaluate_proposal", return_value={
                 "score": 50, "improvement": -20, "sessions": [],
             }):
            result = optimizer.run_iteration(runner_name="openswe")
            assert result.get("accepted") is False


# ===========================================================================
# Group 6: Convergence Detection
# ===========================================================================

class TestConvergence:
    """Detect when optimization has plateaued."""

    def test_detect_convergence_after_flat_iterations(self):
        optimizer = _fresh_optimizer()
        # Simulate 5 iterations with < 1% improvement
        for i in range(5):
            optimizer.save_iteration({
                "iteration_id": f"iter-{i:03d}",
                "runner_name": "openswe",
                "proposal": _mock_harness_proposal(),
                "evaluation": {"score": 80.0 + i * 0.1},
                "accepted": True,
            })
        converged = optimizer.check_convergence(runner_name="openswe")
        assert converged is True

    def test_not_converged_with_improving_scores(self):
        optimizer = _fresh_optimizer()
        for i in range(5):
            optimizer.save_iteration({
                "iteration_id": f"iter-{i:03d}",
                "runner_name": "openswe",
                "proposal": _mock_harness_proposal(),
                "evaluation": {"score": 60.0 + i * 5},
                "accepted": True,
            })
        converged = optimizer.check_convergence(runner_name="openswe")
        assert converged is False

    def test_not_converged_with_few_iterations(self):
        """Need minimum iterations before declaring convergence."""
        optimizer = _fresh_optimizer()
        optimizer.save_iteration({
            "iteration_id": "iter-000",
            "runner_name": "openswe",
            "proposal": _mock_harness_proposal(),
            "evaluation": {"score": 80},
            "accepted": True,
        })
        converged = optimizer.check_convergence(runner_name="openswe")
        assert converged is False


# ===========================================================================
# Group 7: Statistics & Analytics
# ===========================================================================

class TestAnalytics:
    """Meta-optimizer analytics and reporting."""

    def test_stats_returns_dict(self):
        optimizer = _fresh_optimizer()
        stats = optimizer.stats()
        assert isinstance(stats, dict)
        assert "total_iterations" in stats

    def test_stats_per_runner(self):
        optimizer = _fresh_optimizer()
        optimizer.save_iteration({
            "iteration_id": "iter-001",
            "runner_name": "openswe",
            "proposal": _mock_harness_proposal(),
            "evaluation": {"score": 80},
            "accepted": True,
        })
        stats = optimizer.stats(runner_name="openswe")
        assert stats["total_iterations"] >= 1

    def test_improvement_trend(self):
        optimizer = _fresh_optimizer()
        for i in range(5):
            optimizer.save_iteration({
                "iteration_id": f"iter-{i:03d}",
                "runner_name": "openswe",
                "proposal": _mock_harness_proposal(),
                "evaluation": {"score": 60 + i * 5},
                "accepted": True,
            })
        stats = optimizer.stats(runner_name="openswe")
        assert "trend" in stats or "improvement_rate" in stats

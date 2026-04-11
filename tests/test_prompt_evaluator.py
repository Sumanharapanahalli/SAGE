# tests/test_prompt_evaluator.py
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from src.core.evolution.prompt_evaluator import PromptEvaluator, AgentSuccessEvaluator, CriticQualityEvaluator
from src.core.evolution.candidate import Candidate


def test_prompt_evaluator_creation():
    evaluator = PromptEvaluator()
    assert evaluator.name == "prompt_ensemble"


def test_agent_success_evaluator():
    """Test evaluator that scores based on agent success rate from audit logs."""
    evaluator = AgentSuccessEvaluator()
    assert evaluator.name == "agent_success"

    candidate = Candidate(
        id="test", content="You are helpful", candidate_type="prompt",
        fitness=0.0, parent_ids=[], generation=1,
        metadata={"role_id": "analyst"}, created_at=datetime.now(timezone.utc)
    )

    # Mock audit log query
    mock_stats = {"total_tasks": 10, "successful_tasks": 8, "success_rate": 0.8}
    with patch.object(evaluator, '_get_agent_stats', return_value=mock_stats):
        import asyncio
        result = asyncio.run(evaluator.evaluate(candidate))

    assert result["score"] == 0.8  # Success rate maps to score
    assert "success_rate" in result


def test_critic_quality_evaluator():
    """Test evaluator that uses CriticAgent to score prompt quality."""
    import asyncio

    evaluator = CriticQualityEvaluator()
    assert evaluator.name == "critic_quality"

    candidate = Candidate(
        id="test", content="You are a helpful assistant", candidate_type="prompt",
        fitness=0.0, parent_ids=[], generation=1,
        metadata={}, created_at=datetime.now(timezone.utc)
    )

    # Mock CriticAgent response
    mock_critique = {
        "score": 7,  # Out of 10
        "flaws": ["Too generic"],
        "suggestions": ["Be more specific"],
        "summary": "Decent but could be more specific"
    }

    with patch.object(evaluator, '_call_critic_agent', new=AsyncMock(return_value=mock_critique)):
        result = asyncio.run(evaluator.evaluate(candidate))

    assert result["score"] == 0.7  # 7/10 → 0.7
    assert "critic_score" in result


def test_prompt_evaluator_ensemble():
    """Test that PromptEvaluator combines multiple evaluation strategies."""
    import asyncio

    candidate = Candidate(
        id="test", content="You are a data analyst. Analyze carefully.",
        candidate_type="prompt", fitness=0.0, parent_ids=[], generation=1,
        metadata={"role_id": "analyst"}, created_at=datetime.now(timezone.utc)
    )

    evaluator = PromptEvaluator()

    # Mock individual evaluator results
    with patch.object(evaluator.success_evaluator, 'evaluate', new=AsyncMock(return_value={"score": 0.8, "details": "80% success"})):
        with patch.object(evaluator.critic_evaluator, 'evaluate', new=AsyncMock(return_value={"score": 0.7, "details": "Good quality"})):
            result = asyncio.run(evaluator.evaluate(candidate))

    # Should be weighted combination (weights defined in evaluator)
    assert "fitness" in result  # EnsembleEvaluator returns "fitness", not "score"
    assert 0.0 <= result["fitness"] <= 1.0
    assert "breakdown" in result


def test_evaluator_handles_missing_role():
    """Test that evaluators gracefully handle candidates without role_id."""
    import asyncio

    candidate = Candidate(
        id="test", content="Generic prompt", candidate_type="prompt",
        fitness=0.0, parent_ids=[], generation=1,
        metadata={}, created_at=datetime.now(timezone.utc)  # No role_id
    )

    evaluator = AgentSuccessEvaluator()

    # Should not crash, should return low score for unknown role
    result = asyncio.run(evaluator.evaluate(candidate))
    assert "score" in result
    assert result["score"] >= 0.0
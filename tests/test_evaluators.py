"""
Tests for base Evaluator interface and EnsembleEvaluator.

Tests the abstract base Evaluator class and the EnsembleEvaluator that
combines multiple evaluators with weighted scoring.
"""

import asyncio
import pytest
from datetime import datetime, timezone

from src.core.evolution.evaluators import Evaluator, EnsembleEvaluator
from src.core.evolution.candidate import Candidate


class MockEvaluator(Evaluator):
    """Test evaluator that returns fixed scores."""

    def __init__(self, name: str, fixed_score: float):
        super().__init__(name)
        self.fixed_score = fixed_score

    async def evaluate(self, candidate: Candidate) -> dict:
        return {
            "score": self.fixed_score,
            "details": f"Mock evaluation by {self.name}"
        }


def test_base_evaluator():
    """Test that base Evaluator can be subclassed and has name attribute."""
    evaluator = MockEvaluator("test_eval", 0.8)
    assert evaluator.name == "test_eval"


def test_ensemble_evaluator_creation():
    """Test EnsembleEvaluator initialization with multiple evaluators."""
    eval1 = MockEvaluator("eval1", 0.7)
    eval2 = MockEvaluator("eval2", 0.9)

    ensemble = EnsembleEvaluator([
        (eval1, 0.6),  # weight 0.6
        (eval2, 0.4),  # weight 0.4
    ])

    assert len(ensemble.evaluators) == 2
    assert ensemble.weights == [0.6, 0.4]


@pytest.mark.asyncio
async def test_ensemble_evaluate():
    """Test that ensemble combines scores with weights correctly."""
    eval1 = MockEvaluator("eval1", 0.8)  # score 0.8
    eval2 = MockEvaluator("eval2", 0.6)  # score 0.6

    ensemble = EnsembleEvaluator([
        (eval1, 0.7),  # weight 0.7
        (eval2, 0.3),  # weight 0.3
    ])

    candidate = Candidate(
        id="test",
        content="test content",
        candidate_type="prompt",
        fitness=0.0,  # Will be updated
        parent_ids=[],
        generation=1,
        metadata={},
        created_at=datetime.now(timezone.utc)
    )

    # Run ensemble evaluation
    result = await ensemble.evaluate(candidate)

    # Expected: 0.8 * 0.7 + 0.6 * 0.3 = 0.56 + 0.18 = 0.74
    assert abs(result["fitness"] - 0.74) < 0.001
    assert "eval1" in result["breakdown"]
    assert "eval2" in result["breakdown"]


def test_ensemble_weight_normalization():
    """Test that weights are normalized to sum to 1.0."""
    eval1 = MockEvaluator("eval1", 0.5)
    eval2 = MockEvaluator("eval2", 0.5)

    # Weights that don't sum to 1
    ensemble = EnsembleEvaluator([
        (eval1, 3.0),
        (eval2, 2.0),
    ])

    # Should be normalized to [0.6, 0.4]
    assert abs(ensemble.weights[0] - 0.6) < 0.001
    assert abs(ensemble.weights[1] - 0.4) < 0.001


@pytest.mark.asyncio
async def test_ensemble_with_invalid_score():
    """Test that ensemble clamps invalid scores to [0.0, 1.0]."""

    class BadEvaluator(Evaluator):
        async def evaluate(self, candidate: Candidate) -> dict:
            return {"score": 1.5, "details": "Invalid score > 1.0"}

    eval_bad = BadEvaluator("bad_eval")
    eval_good = MockEvaluator("good_eval", 0.8)

    ensemble = EnsembleEvaluator([
        (eval_bad, 0.5),
        (eval_good, 0.5),
    ])

    candidate = Candidate(
        id="test",
        content="test",
        candidate_type="code",
        fitness=0.0,
        parent_ids=[],
        generation=1,
        metadata={},
        created_at=datetime.now(timezone.utc)
    )

    result = await ensemble.evaluate(candidate)

    # Bad score should be clamped to 1.0
    # Expected: 1.0 * 0.5 + 0.8 * 0.5 = 0.5 + 0.4 = 0.9
    assert abs(result["fitness"] - 0.9) < 0.001


@pytest.mark.asyncio
async def test_ensemble_with_evaluator_error():
    """Test that ensemble handles evaluator exceptions gracefully."""

    class ErrorEvaluator(Evaluator):
        async def evaluate(self, candidate: Candidate) -> dict:
            raise ValueError("Test error")

    eval_error = ErrorEvaluator("error_eval")
    eval_good = MockEvaluator("good_eval", 0.8)

    ensemble = EnsembleEvaluator([
        (eval_error, 0.4),
        (eval_good, 0.6),
    ])

    candidate = Candidate(
        id="test",
        content="test",
        candidate_type="build_plan",
        fitness=0.0,
        parent_ids=[],
        generation=1,
        metadata={},
        created_at=datetime.now(timezone.utc)
    )

    result = await ensemble.evaluate(candidate)

    # Failed evaluator should be treated as 0.0
    # Expected: 0.0 * 0.4 + 0.8 * 0.6 = 0.0 + 0.48 = 0.48
    assert abs(result["fitness"] - 0.48) < 0.001
    assert "error" in result["breakdown"]["error_eval"]


def test_ensemble_empty_evaluators():
    """Test that ensemble rejects zero total weight."""
    eval1 = MockEvaluator("eval1", 0.5)

    # All zero weights
    with pytest.raises(ValueError, match="Total weight cannot be zero"):
        EnsembleEvaluator([
            (eval1, 0.0),
        ])


def test_ensemble_single_evaluator():
    """Test ensemble with a single evaluator."""
    eval1 = MockEvaluator("eval1", 0.75)

    ensemble = EnsembleEvaluator([
        (eval1, 1.0),
    ])

    assert len(ensemble.evaluators) == 1
    assert ensemble.weights == [1.0]


@pytest.mark.asyncio
async def test_ensemble_single_evaluator_evaluate():
    """Test evaluation with single evaluator in ensemble."""
    eval1 = MockEvaluator("eval1", 0.75)

    ensemble = EnsembleEvaluator([
        (eval1, 1.0),
    ])

    candidate = Candidate(
        id="test",
        content="test",
        candidate_type="prompt",
        fitness=0.0,
        parent_ids=[],
        generation=1,
        metadata={},
        created_at=datetime.now(timezone.utc)
    )

    result = await ensemble.evaluate(candidate)

    # With single evaluator at weight 1.0, fitness should equal its score
    assert abs(result["fitness"] - 0.75) < 0.001

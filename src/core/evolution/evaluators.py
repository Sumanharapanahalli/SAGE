"""
Base Evaluator interface and EnsembleEvaluator for combining multiple evaluation metrics.

Evaluators score candidates on different dimensions (e.g., test pass rate, code quality,
task completion). The EnsembleEvaluator combines multiple evaluators with configurable
weights to produce a composite fitness score.

Based on AlphaEvolve paper: multiple evaluation dimensions are combined with learned weights
to optimize for solution quality.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from .candidate import Candidate

logger = logging.getLogger(__name__)


class Evaluator(ABC):
    """
    Base interface for candidate evaluation.

    Evaluators score candidates on different dimensions (e.g., test pass rate,
    code quality, task completion). The EnsembleEvaluator combines multiple
    evaluators with configurable weights.

    Subclasses must implement the async evaluate() method, which receives a Candidate
    and returns a dict with scoring details including a "score" key in [0.0, 1.0].
    """

    def __init__(self, name: str):
        """
        Initialize an evaluator.

        Args:
            name: Human-readable name for this evaluator (e.g., "test_coverage", "code_quality")
        """
        self.name = name

    @abstractmethod
    async def evaluate(self, candidate: Candidate) -> dict:
        """
        Evaluate a candidate and return scoring details.

        Args:
            candidate: The Candidate to evaluate

        Returns:
            dict with keys:
            - "score": float in [0.0, 1.0] representing evaluation result
            - "details": str with evaluation explanation
            - (optional) other metrics specific to this evaluator
        """
        pass


class EnsembleEvaluator:
    """
    Combines multiple evaluators with weighted scoring.

    Final fitness = sum(evaluator_score * weight) for all evaluators.
    Weights are normalized to sum to 1.0 during initialization.

    This allows composing different evaluation dimensions (e.g., 60% test pass rate,
    40% code quality) into a single fitness score for evolutionary selection.
    """

    def __init__(self, evaluator_weights: list[tuple[Evaluator, float]]):
        """
        Initialize ensemble with multiple evaluators and their weights.

        Args:
            evaluator_weights: List of (evaluator, weight) tuples

        Raises:
            ValueError: If total weight is zero
        """
        self.evaluators = [ev for ev, _ in evaluator_weights]
        raw_weights = [weight for _, weight in evaluator_weights]

        # Normalize weights to sum to 1.0
        total_weight = sum(raw_weights)
        if total_weight == 0:
            raise ValueError("Total weight cannot be zero")

        self.weights = [w / total_weight for w in raw_weights]

        logger.info(f"EnsembleEvaluator initialized with {len(self.evaluators)} evaluators")
        for i, (evaluator, weight) in enumerate(zip(self.evaluators, self.weights)):
            logger.debug(f"  {evaluator.name}: weight={weight:.3f}")

    async def evaluate(self, candidate: Candidate) -> dict:
        """
        Run all evaluators and compute weighted fitness score.

        Args:
            candidate: The Candidate to evaluate

        Returns:
            dict with keys:
            - "fitness": float in [0.0, 1.0] (weighted average of evaluator scores)
            - "breakdown": dict mapping evaluator names to their individual results
        """
        breakdown = {}
        total_score = 0.0

        for evaluator, weight in zip(self.evaluators, self.weights):
            try:
                result = await evaluator.evaluate(candidate)
                score = result.get("score", 0.0)

                # Validate score is in valid range [0.0, 1.0]
                if not (0.0 <= score <= 1.0):
                    logger.warning(
                        f"{evaluator.name} returned invalid score {score}, clamping to [0,1]"
                    )
                    score = max(0.0, min(1.0, score))

                breakdown[evaluator.name] = result
                total_score += score * weight

                logger.debug(
                    f"{evaluator.name}: score={score:.3f}, weight={weight:.3f}, "
                    f"contribution={score * weight:.3f}"
                )

            except Exception as e:
                logger.error(f"Evaluator {evaluator.name} failed: {e}")
                breakdown[evaluator.name] = {"score": 0.0, "error": str(e)}

        return {
            "fitness": total_score,
            "breakdown": breakdown
        }

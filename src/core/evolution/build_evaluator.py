# src/core/evolution/build_evaluator.py
"""
Build plan evaluation system for evolved build plan candidates.

Evaluators score build plans on different dimensions:
- IntegrationTestEvaluator: runs integration tests on build plans (weight: 0.3)
- BuildCriticEvaluator: uses CriticAgent to score build architecture (weight: 0.3)
- CohesionEvaluator: evaluates build plan organization and cohesion (weight: 0.2)
- ResourceEfficiencyEvaluator: measures resource usage efficiency (weight: 0.2)

The BuildEvaluator combines these into a composite fitness score.

Based on AlphaEvolve paper: multiple evaluation dimensions are combined with learned
weights to optimize for solution quality.
"""

from __future__ import annotations

import logging
import json
import ast
from typing import Dict, Any, Optional
from abc import abstractmethod

from .candidate import Candidate
from .evaluators import Evaluator, EnsembleEvaluator

logger = logging.getLogger(__name__)


class IntegrationTestEvaluator(Evaluator):
    """
    Evaluates build plans by running integration tests.

    Simulates BuildOrchestrator execution and scores based on the phase success rate.
    """

    def __init__(self):
        super().__init__("integration_test")

    async def evaluate(self, candidate: Candidate) -> dict:
        """Score based on integration test execution success rate."""
        build_plan = self._parse_build_plan(candidate.content)
        test_result = self._run_integration_tests(build_plan)

        success_rate = test_result.get("success_rate", 0.0)
        phases_completed = test_result.get("phases_completed", 0)

        return {
            "score": success_rate,
            "details": {
                "phases_completed": phases_completed,
                "phases_total": test_result.get("phases_total", 0),
                "duration": test_result.get("total_duration", 0.0)
            },
            "phases_completed": phases_completed,
            "success_rate": success_rate
        }

    def _parse_build_plan(self, content: str) -> Dict[str, Any]:
        """
        Parse build plan from string content (JSON or dict string format).

        Args:
            content: Build plan as string (JSON or dict representation)

        Returns:
            Parsed build plan dictionary
        """
        content = content.strip()

        # Try JSON parsing first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try Python dict literal parsing
        try:
            return ast.literal_eval(content)
        except (ValueError, SyntaxError):
            pass

        # Fallback: return empty structure
        logger.warning(f"Could not parse build plan content, returning empty structure")
        return {"phases": []}

    def _run_integration_tests(self, build_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run integration tests on the build plan using BuildOrchestrator.

        This is a placeholder that simulates BuildOrchestrator execution.
        In production, this would instantiate and call the actual BuildOrchestrator.

        Args:
            build_plan: The build plan to test

        Returns:
            dict with test results including success_rate, phases_completed, etc.
        """
        # Placeholder implementation: simulate successful execution
        # In production, this would call BuildOrchestrator.execute_plan()
        phases = build_plan.get("phases", [])
        phases_total = len(phases)

        # Simulate successful execution of all phases
        phases_completed = phases_total
        success_rate = 1.0 if phases_completed == phases_total else phases_completed / max(phases_total, 1)

        return {
            "phases_completed": phases_completed,
            "phases_total": phases_total,
            "success_rate": success_rate,
            "total_duration": 0.0,  # Placeholder
            "resource_usage": {"cpu": 0.0, "memory": 0.0}  # Placeholder
        }


class BuildCriticEvaluator(Evaluator):
    """
    Evaluates build plans using CriticAgent to assess architecture quality.

    Scores build plans on architectural soundness, phase ordering, and dependency management.
    """

    def __init__(self):
        super().__init__("build_critic")

    async def evaluate(self, candidate: Candidate) -> dict:
        """Score build plan architecture quality using CriticAgent."""
        build_plan = self._parse_build_plan(candidate.content)
        architecture_score = self._score_architecture(build_plan)

        return {
            "score": architecture_score,
            "details": {
                "architecture_score": architecture_score,
                "components": self._count_components(build_plan)
            },
            "architecture_score": architecture_score
        }

    def _parse_build_plan(self, content: str) -> Dict[str, Any]:
        """Parse build plan from string content."""
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(content)
            except (ValueError, SyntaxError):
                return {"phases": []}

    def _score_architecture(self, build_plan: Dict[str, Any]) -> float:
        """
        Score the architectural quality of the build plan.

        Evaluates phase ordering, dependency management, and parallelism.

        Args:
            build_plan: The build plan to score

        Returns:
            Architecture score in [0.0, 1.0]
        """
        phases = build_plan.get("phases", [])
        if not phases:
            return 0.0

        score = 1.0

        # Penalize for missing phase names
        for phase in phases:
            if "name" not in phase or not phase.get("name"):
                score -= 0.1

        # Check for reasonable phase count (1-10 phases is good)
        if len(phases) > 10:
            score -= 0.1
        elif len(phases) == 0:
            score = 0.0

        # Reward for proper dependencies
        dependencies = build_plan.get("dependencies", {})
        if dependencies:
            score += 0.1

        # Clamp to valid range
        return max(0.0, min(1.0, score))

    def _count_components(self, build_plan: Dict[str, Any]) -> int:
        """Count the number of phases (components) in the build plan."""
        return len(build_plan.get("phases", []))


class CohesionEvaluator(Evaluator):
    """
    Evaluates build plan cohesion and organization.

    Measures how well-structured the build plan is, including phase organization,
    agent grouping, and dependency clarity.
    """

    def __init__(self):
        super().__init__("cohesion")

    async def evaluate(self, candidate: Candidate) -> dict:
        """Score build plan cohesion and organization."""
        build_plan = self._parse_build_plan(candidate.content)
        cohesion_score = self._calculate_cohesion(build_plan)
        metrics = self._extract_metrics(build_plan)

        return {
            "score": cohesion_score,
            "details": {
                "cohesion_metrics": metrics,
                "phase_count": len(build_plan.get("phases", [])),
                "has_dependencies": bool(build_plan.get("dependencies"))
            },
            "cohesion_metrics": metrics
        }

    def _parse_build_plan(self, content: str) -> Dict[str, Any]:
        """Parse build plan from string content."""
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(content)
            except (ValueError, SyntaxError):
                return {"phases": []}

    def _calculate_cohesion(self, build_plan: Dict[str, Any]) -> float:
        """
        Calculate cohesion score for the build plan.

        Evaluates organization, structure, and logical flow.

        Args:
            build_plan: The build plan to evaluate

        Returns:
            Cohesion score in [0.0, 1.0]
        """
        score = 0.8  # Start with good baseline

        phases = build_plan.get("phases", [])
        if not phases:
            return 0.0

        # Reward for having dependencies defined
        dependencies = build_plan.get("dependencies", {})
        if dependencies:
            score = 0.9
        else:
            score = 0.7

        # Penalize for duplicate phase names
        phase_names = [p.get("name") for p in phases if p.get("name")]
        if len(phase_names) != len(set(phase_names)):
            score -= 0.2

        # Reward for well-distributed agents across phases
        total_agents = sum(len(p.get("agents", [])) for p in phases)
        if total_agents > 0 and len(phases) > 0:
            avg_agents = total_agents / len(phases)
            if 1.0 <= avg_agents <= 5.0:
                score += 0.05

        return max(0.0, min(1.0, score))

    def _extract_metrics(self, build_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Extract detailed cohesion metrics from build plan."""
        phases = build_plan.get("phases", [])
        return {
            "phase_count": len(phases),
            "total_agents": sum(len(p.get("agents", [])) for p in phases),
            "has_parallel_phases": any(p.get("parallel", False) for p in phases),
            "dependency_count": len(build_plan.get("dependencies", {}))
        }


class ResourceEfficiencyEvaluator(Evaluator):
    """
    Evaluates build plan resource usage efficiency.

    Scores based on estimated duration, parallelism, and resource cost efficiency.
    """

    def __init__(self):
        super().__init__("resource_efficiency")

    async def evaluate(self, candidate: Candidate) -> dict:
        """Score build plan resource efficiency."""
        build_plan = self._parse_build_plan(candidate.content)
        efficiency_score = self._calculate_efficiency(build_plan)

        return {
            "score": efficiency_score,
            "details": {
                "efficiency_score": efficiency_score,
                "resource_profile": self._profile_resources(build_plan)
            }
        }

    def _parse_build_plan(self, content: str) -> Dict[str, Any]:
        """Parse build plan from string content."""
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(content)
            except (ValueError, SyntaxError):
                return {"phases": []}

    def _calculate_efficiency(self, build_plan: Dict[str, Any]) -> float:
        """
        Calculate resource efficiency score.

        Penalizes for excessive parallelism or high resource usage.

        Args:
            build_plan: The build plan to evaluate

        Returns:
            Efficiency score in [0.0, 1.0]
        """
        score = 0.8  # Start with reasonable baseline

        phases = build_plan.get("phases", [])
        if not phases:
            return 0.0

        # Count total agents across all phases
        total_agents = sum(len(p.get("agents", [])) for p in phases)

        # Penalize for excessive parallel agents (>5 per phase is inefficient)
        for phase in phases:
            if phase.get("parallel", False):
                agent_count = len(phase.get("agents", []))
                if agent_count > 10:
                    score -= 0.2
                elif agent_count > 5:
                    score -= 0.1

        # Consider estimated duration if provided
        estimated_duration = build_plan.get("estimated_duration", 0)
        if estimated_duration > 600:  # >10 minutes
            score -= 0.1

        # Consider estimated cost if provided
        estimated_cost = build_plan.get("estimated_cost", 0)
        if estimated_cost > 2.0:  # High cost
            score -= 0.2

        return max(0.0, min(1.0, score))

    def _profile_resources(self, build_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Profile resource usage of the build plan."""
        phases = build_plan.get("phases", [])
        total_agents = sum(len(p.get("agents", [])) for p in phases)
        parallel_phases = sum(1 for p in phases if p.get("parallel", False))

        return {
            "total_agents": total_agents,
            "parallel_phases": parallel_phases,
            "estimated_duration": build_plan.get("estimated_duration", 0),
            "estimated_cost": build_plan.get("estimated_cost", 0)
        }


class BuildEvaluator:
    """
    Ensemble evaluator combining multiple build plan evaluation strategies.

    Weights:
    - IntegrationTestEvaluator: 0.3
    - BuildCriticEvaluator: 0.3
    - CohesionEvaluator: 0.2
    - ResourceEfficiencyEvaluator: 0.2

    The ensemble produces a composite fitness score combining all dimensions.
    """

    def __init__(self):
        """Initialize BuildEvaluator with all sub-evaluators and ensemble."""
        self.integration_evaluator = IntegrationTestEvaluator()
        self.critic_evaluator = BuildCriticEvaluator()
        self.cohesion_evaluator = CohesionEvaluator()
        self.efficiency_evaluator = ResourceEfficiencyEvaluator()

        # Create ensemble with specified weights
        evaluator_weights = [
            (self.integration_evaluator, 0.3),
            (self.critic_evaluator, 0.3),
            (self.cohesion_evaluator, 0.2),
            (self.efficiency_evaluator, 0.2),
        ]

        self.ensemble = EnsembleEvaluator(evaluator_weights)

    async def evaluate(self, candidate: Candidate) -> dict:
        """
        Evaluate a build plan candidate using all evaluators.

        Args:
            candidate: The build plan Candidate to evaluate

        Returns:
            dict with keys:
            - "fitness": float in [0.0, 1.0] (weighted ensemble score)
            - "breakdown": dict mapping evaluator names to their results
        """
        result = await self.ensemble.evaluate(candidate)
        return result

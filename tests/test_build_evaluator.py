# tests/test_build_evaluator.py
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from src.core.evolution.build_evaluator import (
    BuildEvaluator, IntegrationTestEvaluator,
    CohesionEvaluator, ResourceEfficiencyEvaluator
)
from src.core.evolution.candidate import Candidate


def test_integration_test_evaluator():
    """Test evaluator that runs integration tests on build plans."""
    import asyncio

    evaluator = IntegrationTestEvaluator()
    assert evaluator.name == "integration_test"

    # Mock build plan
    build_plan = {
        "phases": [
            {"name": "setup", "agents": ["planner"], "parallel": False},
            {"name": "implementation", "agents": ["coder", "developer"], "parallel": True},
            {"name": "testing", "agents": ["critic"], "parallel": False}
        ],
        "dependencies": {"implementation": ["setup"], "testing": ["implementation"]}
    }

    candidate = Candidate(
        id="build-test", content=str(build_plan), candidate_type="build_plan",
        fitness=0.0, parent_ids=[], generation=1,
        metadata={"solution": "test_solution"}, created_at=datetime.now(timezone.utc)
    )

    # Mock integration test results
    mock_test_result = {
        "phases_completed": 3,
        "phases_total": 3,
        "success_rate": 1.0,
        "total_duration": 120.5,
        "resource_usage": {"cpu": 0.8, "memory": 0.6}
    }

    with patch.object(evaluator, '_run_integration_tests', return_value=mock_test_result):
        result = asyncio.run(evaluator.evaluate(candidate))

    assert result["score"] == 1.0  # All phases completed successfully
    assert result["phases_completed"] == 3


def test_cohesion_evaluator():
    """Test evaluator that measures build plan cohesion and organization."""
    import asyncio

    evaluator = CohesionEvaluator()

    # Well-structured build plan
    good_plan = {
        "phases": [
            {"name": "planning", "agents": ["planner"], "parallel": False},
            {"name": "implementation", "agents": ["coder", "developer"], "parallel": True},
            {"name": "review", "agents": ["critic"], "parallel": False}
        ],
        "dependencies": {"implementation": ["planning"], "review": ["implementation"]}
    }

    candidate = Candidate(
        id="test", content=str(good_plan), candidate_type="build_plan",
        fitness=0.0, parent_ids=[], generation=1,
        metadata={}, created_at=datetime.now(timezone.utc)
    )

    result = asyncio.run(evaluator.evaluate(candidate))

    assert "score" in result
    assert 0.0 <= result["score"] <= 1.0
    assert "cohesion_metrics" in result.get("details", {})


def test_resource_efficiency_evaluator():
    """Test evaluator that measures resource usage efficiency."""
    import asyncio

    evaluator = ResourceEfficiencyEvaluator()

    # Resource-heavy build plan
    heavy_plan = {
        "phases": [
            {"name": "heavy", "agents": ["coder"] * 10, "parallel": True},  # Lots of parallel agents
        ],
        "estimated_duration": 300,  # 5 minutes
        "estimated_cost": 2.50
    }

    candidate = Candidate(
        id="test", content=str(heavy_plan), candidate_type="build_plan",
        fitness=0.0, parent_ids=[], generation=1,
        metadata={}, created_at=datetime.now(timezone.utc)
    )

    result = asyncio.run(evaluator.evaluate(candidate))

    # Heavy resource usage should get lower efficiency score
    assert "score" in result
    assert result["score"] <= 0.7  # Should be penalized for inefficiency


def test_build_evaluator_ensemble():
    """Test that BuildEvaluator combines integration, cohesion, and efficiency scores."""
    import asyncio

    build_plan = {
        "phases": [{"name": "test", "agents": ["planner"], "parallel": False}]
    }

    candidate = Candidate(
        id="test", content=str(build_plan), candidate_type="build_plan",
        fitness=0.0, parent_ids=[], generation=1,
        metadata={}, created_at=datetime.now(timezone.utc)
    )

    evaluator = BuildEvaluator()

    # Mock individual evaluator results per spec weights:
    # Integration test pass rate: 0.3, Critic architecture score: 0.3,
    # Cohesion metrics: 0.2, Build time/resources: 0.2
    with patch.object(evaluator.integration_evaluator, 'evaluate', new=AsyncMock(return_value={"score": 0.9})):
        with patch.object(evaluator.cohesion_evaluator, 'evaluate', new=AsyncMock(return_value={"score": 0.8})):
            with patch.object(evaluator.efficiency_evaluator, 'evaluate', new=AsyncMock(return_value={"score": 0.7})):
                # Need to mock critic evaluator too
                with patch.object(evaluator.critic_evaluator, 'evaluate', new=AsyncMock(return_value={"score": 0.85})):
                    result = asyncio.run(evaluator.evaluate(candidate))

    # Should be weighted combination: 0.9*0.3 + 0.85*0.3 + 0.8*0.2 + 0.7*0.2 = 0.27 + 0.255 + 0.16 + 0.14 = 0.825
    assert abs(result["fitness"] - 0.825) < 0.01


def test_build_plan_parsing():
    """Test that evaluators can parse different build plan formats."""
    evaluator = IntegrationTestEvaluator()

    # JSON string format
    json_plan = '{"phases": [{"name": "test", "agents": ["planner"]}]}'
    parsed = evaluator._parse_build_plan(json_plan)
    assert "phases" in parsed
    assert len(parsed["phases"]) == 1

    # Dict format (already parsed)
    dict_plan = {"phases": [{"name": "test2", "agents": ["coder"]}]}
    parsed2 = evaluator._parse_build_plan(str(dict_plan))
    assert "phases" in parsed2


def test_integration_test_execution():
    """Test actual integration test execution simulation."""
    with patch('src.integrations.build_orchestrator.BuildOrchestrator') as mock_orchestrator:
        # Mock successful build execution
        mock_instance = MagicMock()
        mock_instance.execute_plan.return_value = {
            "success": True,
            "phases_completed": 2,
            "total_phases": 2,
            "duration": 45.0,
            "errors": []
        }
        mock_orchestrator.return_value = mock_instance

        evaluator = IntegrationTestEvaluator()

        build_plan = {
            "phases": [
                {"name": "phase1", "agents": ["planner"]},
                {"name": "phase2", "agents": ["coder"]}
            ]
        }
        result = evaluator._run_integration_tests(build_plan)

        assert result["success_rate"] == 1.0
        assert result["phases_completed"] == 2

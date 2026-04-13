from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from src.core.evolution.build_evolver import BuildEvolver
from src.core.evolution.candidate import Candidate


def test_build_evolver_creation():
    evolver = BuildEvolver(mutation_rate=0.6, crossover_rate=0.4)
    assert evolver.mutation_rate == 0.6
    assert evolver.crossover_rate == 0.4


def test_build_mutation_strategies():
    """Test build-specific mutation strategies."""
    evolver = BuildEvolver()
    strategies = evolver.get_mutation_strategies()

    assert len(strategies) >= 4
    assert "optimize_parallelization" in strategies
    assert "improve_dependencies" in strategies
    assert "reduce_build_time" in strategies
    assert "enhance_error_handling" in strategies


def test_build_plan_crossover():
    """Test combining two parent build plans."""
    import asyncio

    parent1 = Candidate(
        id="p1", content='{"phases": [{"name": "setup", "agents": ["planner"]}]}',
        candidate_type="build_plan", fitness=0.7, parent_ids=[], generation=1,
        metadata={}, created_at=datetime.now(timezone.utc)
    )

    parent2 = Candidate(
        id="p2", content='{"phases": [{"name": "test", "agents": ["critic"], "parallel": true}]}',
        candidate_type="build_plan", fitness=0.8, parent_ids=[], generation=1,
        metadata={}, created_at=datetime.now(timezone.utc)
    )

    evolver = BuildEvolver()

    # Mock SDK subagent call
    mock_result = '{"phases": [{"name": "setup", "agents": ["planner"]}, {"name": "test", "agents": ["critic"], "parallel": true}]}'
    with patch.object(evolver, '_call_build_mutation_subagent', new=AsyncMock(return_value=mock_result)):
        child = asyncio.run(evolver.crossover(parent1, parent2))

    assert child.candidate_type == "build_plan"
    assert child.generation == 2
    assert len(child.parent_ids) == 2


def test_build_plan_mutation():
    """Test mutating a build plan with specific strategy."""
    import asyncio

    parent = Candidate(
        id="parent",
        content='{"phases": [{"name": "build", "agents": ["coder"], "parallel": false}]}',
        candidate_type="build_plan", fitness=0.6, parent_ids=[], generation=1,
        metadata={}, created_at=datetime.now(timezone.utc)
    )

    evolver = BuildEvolver()

    # Mock improved build plan
    mock_result = '{"phases": [{"name": "build", "agents": ["coder", "developer"], "parallel": true}], "dependencies": {}}'
    with patch.object(evolver, '_call_build_mutation_subagent', new=AsyncMock(return_value=mock_result)):
        mutant = asyncio.run(evolver.mutate(parent, strategy="optimize_parallelization"))

    assert mutant.generation == 2
    assert mutant.metadata["mutation_strategy"] == "optimize_parallelization"


def test_build_plan_validation():
    """Test that mutations produce valid build plans."""
    evolver = BuildEvolver()

    # Valid build plan
    valid_plan = {
        "phases": [
            {"name": "setup", "agents": ["planner"]},
            {"name": "build", "agents": ["coder"]}
        ]
    }

    validation = evolver._validate_build_plan(valid_plan)
    assert validation["valid"] == True
    assert validation["errors"] == []

    # Invalid build plan (missing required fields)
    invalid_plan = {"invalid": "structure"}

    validation2 = evolver._validate_build_plan(invalid_plan)
    assert validation2["valid"] == False
    assert len(validation2["errors"]) > 0


def test_dependency_optimization():
    """Test that build plans can be optimized for dependencies."""
    evolver = BuildEvolver()

    # Build plan with sub-optimal dependencies
    plan = {
        "phases": [
            {"name": "test", "agents": ["critic"]},
            {"name": "build", "agents": ["coder"]},
            {"name": "plan", "agents": ["planner"]}
        ]
    }

    optimized = evolver._optimize_dependencies(plan)

    # Should suggest logical ordering
    assert "dependencies" in optimized
    assert len(optimized["phases"]) == 3


def test_parallelization_analysis():
    """Test analysis of parallelization opportunities."""
    evolver = BuildEvolver()

    plan = {
        "phases": [
            {"name": "setup", "agents": ["planner"], "parallel": False},
            {"name": "build", "agents": ["coder", "developer"], "parallel": False}  # Could be parallel
        ]
    }

    analysis = evolver._analyze_parallelization(plan)

    assert "parallelizable_phases" in analysis
    assert "parallel_opportunities" in analysis

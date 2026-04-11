"""
Tests for PromptEvolver mutation engine.

Tests cover:
- Evolver initialization with mutation/crossover rates
- Mutation strategy availability and selection
- Crossover (combining two parent prompts)
- Mutation (improving single prompt with specific strategy)
- Reproduction weight selection based on configured rates
"""

from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from src.core.evolution.prompt_evolver import PromptEvolver
from src.core.evolution.candidate import Candidate


def test_prompt_evolver_creation():
    """Test basic PromptEvolver initialization."""
    evolver = PromptEvolver(mutation_rate=0.3, crossover_rate=0.7)
    assert evolver.mutation_rate == 0.3
    assert evolver.crossover_rate == 0.7


def test_mutation_strategies():
    """Test that evolver has multiple mutation strategies."""
    evolver = PromptEvolver()
    strategies = evolver.get_mutation_strategies()

    # Should have at least a few different approaches
    assert len(strategies) >= 3
    assert "enhance_specificity" in strategies
    assert "improve_clarity" in strategies
    assert "add_constraints" in strategies


def test_crossover_prompt_creation():
    """Test combining two parent prompts."""
    import asyncio

    parent1 = Candidate(
        id="p1", content="You are a helpful analyst. Be thorough.",
        candidate_type="prompt", fitness=0.8, parent_ids=[], generation=1,
        metadata={}, created_at=datetime.now(timezone.utc)
    )

    parent2 = Candidate(
        id="p2", content="You are a data expert. Provide clear insights.",
        candidate_type="prompt", fitness=0.9, parent_ids=[], generation=1,
        metadata={}, created_at=datetime.now(timezone.utc)
    )

    evolver = PromptEvolver()

    # Mock SDK subagent call
    mock_result = "You are a helpful data analyst. Be thorough and provide clear insights."
    with patch.object(evolver, '_call_mutation_subagent', new=AsyncMock(return_value=mock_result)):
        child = asyncio.run(evolver.crossover(parent1, parent2))

    assert child.content == mock_result
    assert child.generation == 2  # Next generation
    assert len(child.parent_ids) == 2
    assert "p1" in child.parent_ids
    assert "p2" in child.parent_ids


def test_mutate_prompt():
    """Test mutating a single prompt."""
    import asyncio

    parent = Candidate(
        id="parent", content="You are an analyst. Analyze data.",
        candidate_type="prompt", fitness=0.7, parent_ids=[], generation=1,
        metadata={"role_id": "analyst"}, created_at=datetime.now(timezone.utc)
    )

    evolver = PromptEvolver()

    # Mock SDK subagent call
    mock_result = "You are a senior data analyst. Carefully analyze data and provide actionable insights."
    with patch.object(evolver, '_call_mutation_subagent', new=AsyncMock(return_value=mock_result)):
        mutant = asyncio.run(evolver.mutate(parent, strategy="enhance_specificity"))

    assert mutant.content == mock_result
    assert mutant.generation == 2
    assert len(mutant.parent_ids) == 1
    assert mutant.parent_ids[0] == "parent"
    assert mutant.metadata["mutation_strategy"] == "enhance_specificity"


def test_reproduction_weights():
    """Test that reproduction chooses crossover vs mutation based on rates."""
    evolver = PromptEvolver(mutation_rate=1.0, crossover_rate=0.0)  # 100% mutation
    assert evolver.should_crossover() == False

    evolver2 = PromptEvolver(mutation_rate=0.0, crossover_rate=1.0)  # 100% crossover
    assert evolver2.should_crossover() == True

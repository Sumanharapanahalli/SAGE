"""Tests for CodeEvolver mutation engine."""

from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from src.core.evolution.code_evolver import CodeEvolver
from src.core.evolution.candidate import Candidate


def test_code_evolver_creation():
    evolver = CodeEvolver(mutation_rate=0.7, crossover_rate=0.3)
    assert evolver.mutation_rate == 0.7
    assert evolver.crossover_rate == 0.3


def test_code_mutation_strategies():
    """Test that evolver has code-specific mutation strategies."""
    evolver = CodeEvolver()
    strategies = evolver.get_mutation_strategies()

    assert len(strategies) >= 8
    assert "optimize_performance" in strategies
    assert "improve_readability" in strategies
    assert "add_error_handling" in strategies
    assert "reduce_complexity" in strategies
    assert "add_type_hints" in strategies
    assert "optimize_imports" in strategies
    assert "refactor_functions" in strategies
    assert "improve_docstrings" in strategies


def test_code_crossover():
    """Test combining two parent code implementations."""
    import asyncio

    parent1 = Candidate(
        id="p1", content="def sort_list(items):\n    return sorted(items)",
        candidate_type="code", fitness=0.8, parent_ids=[], generation=1,
        metadata={"file_path": "utils.py"}, created_at=datetime.now(timezone.utc)
    )

    parent2 = Candidate(
        id="p2", content="def sort_list(items):\n    items.sort()\n    return items",
        candidate_type="code", fitness=0.9, parent_ids=[], generation=1,
        metadata={"file_path": "utils.py"}, created_at=datetime.now(timezone.utc)
    )

    evolver = CodeEvolver()

    # Mock SDK subagent call
    mock_result = "def sort_list(items):\n    return sorted(items, key=str.lower)"
    with patch.object(evolver, '_call_code_mutation_subagent', new=AsyncMock(return_value=mock_result)):
        child = asyncio.run(evolver.crossover(parent1, parent2))

    assert child.content == mock_result
    assert child.generation == 2
    assert len(child.parent_ids) == 2
    assert child.candidate_type == "code"


def test_code_mutation():
    """Test mutating code with specific strategy."""
    import asyncio

    parent = Candidate(
        id="parent", content="def calculate(x):\n    return x * 2",
        candidate_type="code", fitness=0.7, parent_ids=[], generation=1,
        metadata={"file_path": "calc.py"}, created_at=datetime.now(timezone.utc)
    )

    evolver = CodeEvolver()

    # Mock SDK subagent call
    mock_result = "def calculate(x: float) -> float:\n    \"\"\"Double the input value.\"\"\"\n    return x * 2.0"
    with patch.object(evolver, '_call_code_mutation_subagent', new=AsyncMock(return_value=mock_result)):
        mutant = asyncio.run(evolver.mutate(parent, strategy="improve_readability"))

    assert mock_result in mutant.content
    assert mutant.generation == 2
    assert mutant.metadata["mutation_strategy"] == "improve_readability"


def test_api_preservation():
    """Test that mutations preserve function signatures and API contracts."""
    evolver = CodeEvolver()

    original_code = """
def process_data(input_list: list, threshold: float = 0.5) -> dict:
    return {"processed": len(input_list), "threshold": threshold}
"""

    api_info = evolver._extract_api_info(original_code)

    assert "process_data" in api_info["functions"]
    func_info = api_info["functions"]["process_data"]
    assert func_info["args"] == ["input_list", "threshold"]
    assert func_info["return_type"] == "dict"


def test_mutation_preserves_tests():
    """Test that code mutations don't break existing test patterns."""
    import asyncio

    parent = Candidate(
        id="test", content="def add(a, b):\n    return a + b",
        candidate_type="code", fitness=0.5, parent_ids=[], generation=1,
        metadata={"test_pattern": "assert add(2, 3) == 5"}, created_at=datetime.now(timezone.utc)
    )

    evolver = CodeEvolver()

    # Mock mutation that preserves the API
    mock_result = "def add(a, b):\n    \"\"\"Add two numbers.\"\"\"\n    result = a + b\n    return result"
    with patch.object(evolver, '_call_code_mutation_subagent', new=AsyncMock(return_value=mock_result)):
        mutant = asyncio.run(evolver.mutate(parent))

    # Should preserve function name and signature
    assert "def add(a, b):" in mutant.content
    assert mutant.metadata.get("test_pattern") == parent.metadata.get("test_pattern")

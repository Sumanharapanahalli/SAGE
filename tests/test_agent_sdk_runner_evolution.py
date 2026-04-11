# tests/test_agent_sdk_runner_evolution.py
from unittest.mock import AsyncMock, patch
import tempfile
import os

from src.core.agent_sdk_runner import get_agent_sdk_runner
from src.core.evolution.orchestrator import EvolutionOrchestrator
from src.core.evolution.program_db import ProgramDatabase


def test_agent_sdk_runner_has_evolution_method():
    """Test that AgentSDKRunner has run_with_evolution method."""
    runner = get_agent_sdk_runner()
    assert hasattr(runner, "run_with_evolution")


def test_run_with_evolution_calls_orchestrator():
    """Test that run_with_evolution properly delegates to EvolutionOrchestrator."""
    import asyncio

    runner = get_agent_sdk_runner()

    # Mock the orchestrator
    mock_orchestrator = AsyncMock()
    mock_orchestrator.evolve_prompt.return_value = {
        "best_candidate": {"content": "Evolved prompt"},
        "generation": 3,
        "fitness": 0.92
    }

    with patch('src.core.evolution.orchestrator.EvolutionOrchestrator', return_value=mock_orchestrator), \
         patch('src.core.evolution.program_db.get_evolution_db_path', return_value='/tmp/test.db'), \
         patch('src.core.evolution.program_db.ProgramDatabase'):
        result = asyncio.run(runner.run_with_evolution(
            role_id="analyst",
            task="test task",
            evolver_type="prompt",
            config={"generations": 3, "population": 8}
        ))

    assert "best_candidate" in result
    mock_orchestrator.evolve_prompt.assert_called_once()


def test_evolution_config_validation():
    """Test that evolution config is validated."""
    import asyncio

    runner = get_agent_sdk_runner()

    # Invalid evolver type should raise
    with patch('src.core.evolution.orchestrator.EvolutionOrchestrator'), \
         patch('src.core.evolution.program_db.get_evolution_db_path', return_value='/tmp/test.db'), \
         patch('src.core.evolution.program_db.ProgramDatabase'):
        try:
            asyncio.run(runner.run_with_evolution(
                role_id="test",
                task="test",
                evolver_type="invalid",  # Invalid type
                config={}
            ))
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


def test_evolution_requires_prompt_candidate_type():
    """Test that prompt evolution only works with prompt candidate type."""
    import asyncio

    runner = get_agent_sdk_runner()

    # Should work for prompt type
    with patch('src.core.evolution.orchestrator.EvolutionOrchestrator') as mock_orch_class, \
         patch('src.core.evolution.program_db.get_evolution_db_path', return_value='/tmp/test.db'), \
         patch('src.core.evolution.program_db.ProgramDatabase'):
        mock_orch = AsyncMock()
        mock_orch_class.return_value = mock_orch
        mock_orch.evolve_prompt.return_value = {"result": "success"}

        result = asyncio.run(runner.run_with_evolution(
            role_id="test",
            task="test",
            evolver_type="prompt",
            config={"generations": 2}
        ))

        mock_orch.evolve_prompt.assert_called_once()
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


def test_prompt_evolution_works():
    """Test that prompt evolution executes successfully."""
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


def test_code_evolution_not_implemented():
    """Test that code evolution raises NotImplementedError."""
    import asyncio

    runner = get_agent_sdk_runner()

    with patch('src.core.evolution.orchestrator.EvolutionOrchestrator'), \
         patch('src.core.evolution.program_db.get_evolution_db_path', return_value='/tmp/test.db'), \
         patch('src.core.evolution.program_db.ProgramDatabase'):
        try:
            asyncio.run(runner.run_with_evolution(
                role_id="test",
                task="test task",
                evolver_type="code",  # Should raise NotImplementedError
                config={}
            ))
            assert False, "Should have raised NotImplementedError"
        except NotImplementedError as e:
            assert "code" in str(e)


def test_build_evolution_not_implemented():
    """Test that build evolution raises NotImplementedError."""
    import asyncio

    runner = get_agent_sdk_runner()

    with patch('src.core.evolution.orchestrator.EvolutionOrchestrator'), \
         patch('src.core.evolution.program_db.get_evolution_db_path', return_value='/tmp/test.db'), \
         patch('src.core.evolution.program_db.ProgramDatabase'):
        try:
            asyncio.run(runner.run_with_evolution(
                role_id="test",
                task="test task",
                evolver_type="build",  # Should raise NotImplementedError
                config={}
            ))
            assert False, "Should have raised NotImplementedError"
        except NotImplementedError as e:
            assert "build" in str(e)


def test_environment_variable_extraction():
    """Test that SAGE_PROJECT environment variable is extracted correctly."""
    import asyncio

    runner = get_agent_sdk_runner()

    # Test with SAGE_PROJECT set
    with patch.dict(os.environ, {"SAGE_PROJECT": "test_solution"}):
        with patch('src.core.evolution.orchestrator.EvolutionOrchestrator') as mock_orch_class, \
             patch('src.core.evolution.program_db.get_evolution_db_path', return_value='/tmp/test.db'), \
             patch('src.core.evolution.program_db.ProgramDatabase'):
            mock_orch = AsyncMock()
            mock_orch_class.return_value = mock_orch
            mock_orch.evolve_prompt.return_value = {"result": "success"}

            asyncio.run(runner.run_with_evolution(
                role_id="test",
                task="test",
                evolver_type="prompt",
                config={}
            ))

            # Verify orchestrator was created with correct solution name
            mock_orch_class.assert_called_once()
            args, kwargs = mock_orch_class.call_args
            assert kwargs["solution_name"] == "test_solution"


def test_environment_variable_default_fallback():
    """Test that missing SAGE_PROJECT defaults to 'default'."""
    import asyncio

    runner = get_agent_sdk_runner()

    # Test without SAGE_PROJECT set (remove if exists)
    env_without_sage = {k: v for k, v in os.environ.items() if k != "SAGE_PROJECT"}
    with patch.dict(os.environ, env_without_sage, clear=True):
        with patch('src.core.evolution.orchestrator.EvolutionOrchestrator') as mock_orch_class, \
             patch('src.core.evolution.program_db.get_evolution_db_path', return_value='/tmp/test.db'), \
             patch('src.core.evolution.program_db.ProgramDatabase'):
            mock_orch = AsyncMock()
            mock_orch_class.return_value = mock_orch
            mock_orch.evolve_prompt.return_value = {"result": "success"}

            asyncio.run(runner.run_with_evolution(
                role_id="test",
                task="test",
                evolver_type="prompt",
                config={}
            ))

            # Verify orchestrator was created with default solution name
            mock_orch_class.assert_called_once()
            args, kwargs = mock_orch_class.call_args
            assert kwargs["solution_name"] == "default"
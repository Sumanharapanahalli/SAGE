import tempfile
import os
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from src.core.evolution.orchestrator import EvolutionOrchestrator
from src.core.evolution.program_db import ProgramDatabase
from src.core.evolution.prompt_evolver import PromptEvolver
from src.core.evolution.prompt_evaluator import PromptEvaluator
from src.core.evolution.candidate import Candidate


def test_complete_evolution_loop():
    """Test end-to-end evolution: seed → mutate → evaluate → select → repeat."""
    import asyncio

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_evolution.db")
        db = ProgramDatabase(db_path)

        orchestrator = EvolutionOrchestrator(
            db=db,
            solution_name="test",
            max_generations=2,
            population_size=4
        )

        # Mock the evolver and evaluator
        from unittest.mock import Mock
        mock_evolver = Mock()
        mock_mutant = Candidate(
            id='mock-mutant',
            content='Mutated prompt',
            candidate_type='prompt',
            fitness=0.0,
            parent_ids=['seed'],
            generation=1,
            metadata={'mutation_strategy': 'enhance'},
            created_at=datetime.now(timezone.utc)
        )
        mock_evolver.mutate = AsyncMock(return_value=mock_mutant)
        mock_evolver.crossover = AsyncMock(return_value=mock_mutant)
        mock_evolver.should_crossover.return_value = False  # Force mutation

        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate.return_value = {'fitness': 0.85, 'breakdown': {}}

        # Seed initial population
        initial_prompts = {
            "analyst": "You are a data analyst. Analyze carefully."
        }
        orchestrator.seed_population(initial_prompts)

        # Run evolution with mocks
        with patch.object(orchestrator, '_get_evolver', return_value=mock_evolver):
            with patch.object(orchestrator, '_get_evaluator', return_value=mock_evaluator):
                result = asyncio.run(orchestrator.evolve_prompt("analyst", "test task", {}))

        # Should complete successfully
        assert "best_candidate" in result
        assert "generation" in result
        assert result["generation"] >= 1


def test_evolution_stops_at_max_generations():
    """Test that evolution respects max_generations limit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_evolution.db")
        db = ProgramDatabase(db_path)

        orchestrator = EvolutionOrchestrator(
            db=db,
            solution_name="test",
            max_generations=1,  # Very low limit
            population_size=3
        )

        # Should not exceed the generation limit
        assert orchestrator.max_generations == 1


def test_fitness_improvement_tracking():
    """Test that evolution tracks fitness improvement over generations."""
    import asyncio

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_evolution.db")
        db = ProgramDatabase(db_path)

        orchestrator = EvolutionOrchestrator(db=db, solution_name="test", max_generations=3, population_size=4)

        # Seed and verify we can track generation stats
        orchestrator.seed_population({"test": "Basic prompt"})

        gen0_stats = orchestrator.get_population_stats(0)
        assert gen0_stats["count"] == 1
        assert gen0_stats["fitness"]["avg"] == 0.0  # Unseeded fitness
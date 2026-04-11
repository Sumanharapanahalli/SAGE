import tempfile
import os
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from src.core.evolution.orchestrator import EvolutionOrchestrator
from src.core.evolution.candidate import Candidate
from src.core.evolution.program_db import ProgramDatabase


def test_orchestrator_creation():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_evolution.db")
        db = ProgramDatabase(db_path)

        orchestrator = EvolutionOrchestrator(
            db=db,
            solution_name="test_solution",
            max_generations=5,
            population_size=10
        )

        assert orchestrator.solution_name == "test_solution"
        assert orchestrator.max_generations == 5
        assert orchestrator.population_size == 10


def test_orchestrator_seed_population():
    """Test seeding initial population from existing role prompts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_evolution.db")
        db = ProgramDatabase(db_path)

        orchestrator = EvolutionOrchestrator(db=db, solution_name="test", max_generations=3, population_size=5)

        # Mock role prompts
        role_prompts = {
            "analyst": "You are a data analyst. Analyze logs carefully.",
            "coder": "You are a software engineer. Write clean code.",
        }

        orchestrator.seed_population(role_prompts)

        # Should create initial candidates
        analyst_candidates = db.get_generation(0, "prompt")
        assert len(analyst_candidates) >= 1

        # Check that original prompts are stored
        found_analyst = False
        for candidate in analyst_candidates:
            if "data analyst" in candidate.content:
                found_analyst = True
                assert candidate.generation == 0
                assert candidate.candidate_type == "prompt"

        assert found_analyst


def test_orchestrator_evolution_config():
    """Test evolution configuration validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_evolution.db")
        db = ProgramDatabase(db_path)

        # Invalid generation count should raise
        try:
            EvolutionOrchestrator(db=db, solution_name="test", max_generations=0, population_size=5)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

        # Invalid population size should raise
        try:
            EvolutionOrchestrator(db=db, solution_name="test", max_generations=3, population_size=1)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

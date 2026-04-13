"""
Integration tests for code and build evolution within the AgentSDKRunner.

Tests the complete pipeline from AgentSDKRunner.run_with_evolution
through EvolutionOrchestrator to CodeEvolver/BuildEvolver.
"""

import pytest
import tempfile
import os
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from src.core.evolution.program_db import ProgramDatabase, get_evolution_db_path
from src.core.evolution.candidate import Candidate
from src.core.agent_sdk_runner import get_agent_sdk_runner


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        db_path = tmp.name

    db = ProgramDatabase(db_path)
    yield db

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def mock_project_config():
    """Mock project configuration with test roles."""
    config = {
        "prompts": {
            "roles": {
                "test_role": {
                    "name": "Test Role",
                    "system_prompt": "You are a test assistant.",
                    "description": "Test role for evolution"
                }
            }
        },
        "project_name": "test_evolution",
        "modules": ["core"]
    }

    with patch('src.core.project_loader.project_config') as mock:
        mock.get_prompts.return_value = config["prompts"]
        mock.get_project_data.return_value = config
        yield mock


@pytest.fixture
def sample_code():
    """Sample Python code for evolution testing."""
    return '''def calculate_fibonacci(n):
    """Calculate the nth Fibonacci number."""
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

def main():
    result = calculate_fibonacci(10)
    print(f"Fibonacci(10) = {result}")

if __name__ == "__main__":
    main()
'''


@pytest.fixture
def sample_build_plan():
    """Sample build plan for evolution testing."""
    return {
        "name": "python_app",
        "steps": [
            {"name": "install_deps", "command": "pip install -r requirements.txt"},
            {"name": "run_tests", "command": "python -m pytest"},
            {"name": "build", "command": "python setup.py build"}
        ],
        "environment": {
            "python_version": "3.9",
            "dependencies": ["pytest", "setuptools"]
        }
    }


class TestCodeEvolutionIntegration:
    """Test code evolution through AgentSDKRunner."""

    @pytest.mark.asyncio
    async def test_code_evolution_complete_flow(self, temp_db, mock_project_config, sample_code):
        """Test complete code evolution flow through AgentSDKRunner."""
        # Setup environment
        os.environ["SAGE_PROJECT"] = "test_evolution"

        # Mock the database path to use our temp database
        with patch('src.core.evolution.program_db.get_evolution_db_path', return_value=temp_db.db_path):
            runner = get_agent_sdk_runner()

            # Mock evaluation results for code evolution
            with patch('src.core.evolution.code_evaluator.CodeEvaluator.evaluate') as mock_eval:
                mock_eval.return_value = {
                    "fitness": 0.85,
                    "breakdown": {
                        "correctness": 0.9,
                        "performance": 0.8,
                        "readability": 0.85,
                        "maintainability": 0.85
                    }
                }

                # Mock code evolution methods
                with patch('src.core.evolution.code_evolver.CodeEvolver.mutate') as mock_mutate, \
                     patch('src.core.evolution.code_evolver.CodeEvolver.crossover') as mock_crossover:

                    # Mock mutated candidate
                    mock_mutate.return_value = Candidate(
                        id="mutated-123",
                        content=sample_code.replace("calculate_fibonacci", "fib_calc"),
                        candidate_type="code",
                        fitness=0.0,
                        parent_ids=["parent-123"],
                        generation=1,
                        metadata={"mutation_type": "refactor_function_name"},
                        created_at=datetime.now(timezone.utc)
                    )

                    # Configure evolution parameters
                    config = {
                        "generations": 2,
                        "population": 5,
                        "code_file": "test_module.py",
                        "target_metrics": ["correctness", "performance"]
                    }

                    # Run code evolution
                    result = await runner.run_with_evolution(
                        role_id="test_role",
                        task="Optimize this Python code for better performance",
                        evolver_type="code",
                        config=config,
                        context={"code": sample_code}
                    )

                    # Verify results
                    assert result["status"] == "success"
                    assert result["evolver_type"] == "code"
                    assert "best_candidate" in result
                    assert result["best_candidate"]["candidate_type"] == "code"
                    assert result["best_candidate"]["fitness"] > 0


class TestBuildEvolutionIntegration:
    """Test build plan evolution through AgentSDKRunner."""

    @pytest.mark.asyncio
    async def test_build_evolution_complete_flow(self, temp_db, mock_project_config, sample_build_plan):
        """Test complete build plan evolution flow through AgentSDKRunner."""
        # Setup environment
        os.environ["SAGE_PROJECT"] = "test_evolution"

        # Mock the database path to use our temp database
        with patch('src.core.evolution.program_db.get_evolution_db_path', return_value=temp_db.db_path):
            runner = get_agent_sdk_runner()

            # Mock evaluation results for build evolution
            with patch('src.core.evolution.build_evaluator.BuildEvaluator.evaluate') as mock_eval:
                mock_eval.return_value = {
                    "fitness": 0.78,
                    "breakdown": {
                        "efficiency": 0.8,
                        "reliability": 0.75,
                        "maintainability": 0.8
                    }
                }

                # Mock build evolution methods
                with patch('src.core.evolution.build_evolver.BuildEvolver.mutate') as mock_mutate, \
                     patch('src.core.evolution.build_evolver.BuildEvolver.crossover') as mock_crossover:

                    # Mock mutated candidate
                    optimized_plan = sample_build_plan.copy()
                    optimized_plan["steps"].insert(1, {"name": "cache_deps", "command": "pip install --cache-dir .pip-cache -r requirements.txt"})

                    mock_mutate.return_value = Candidate(
                        id="build-mutated-123",
                        content=json.dumps(optimized_plan),
                        candidate_type="build_plan",
                        fitness=0.0,
                        parent_ids=["build-parent-123"],
                        generation=1,
                        metadata={"mutation_type": "add_caching"},
                        created_at=datetime.now(timezone.utc)
                    )

                    # Configure evolution parameters
                    config = {
                        "generations": 2,
                        "population": 4,
                        "build_file": "build.yaml",
                        "target_metrics": ["efficiency", "reliability"]
                    }

                    # Run build evolution
                    result = await runner.run_with_evolution(
                        role_id="test_role",
                        task="Optimize this build plan for better efficiency",
                        evolver_type="build",
                        config=config,
                        context={"build_plan": sample_build_plan}
                    )

                    # Verify results
                    assert result["status"] == "success"
                    assert result["evolver_type"] == "build"
                    assert "best_candidate" in result
                    assert result["best_candidate"]["candidate_type"] == "build_plan"
                    assert result["best_candidate"]["fitness"] > 0


class TestEvolutionOrchestrator:
    """Test the evolution orchestrator methods directly."""

    @pytest.mark.asyncio
    async def test_evolve_code_method(self, temp_db):
        """Test EvolutionOrchestrator.evolve_code method."""
        from src.core.evolution.orchestrator import EvolutionOrchestrator

        orchestrator = EvolutionOrchestrator(
            db=temp_db,
            solution_name="test_solution",
            max_generations=2,
            population_size=3
        )

        # Mock evaluator and evolver
        with patch('src.core.evolution.code_evaluator.CodeEvaluator.evaluate') as mock_eval, \
             patch('src.core.evolution.code_evolver.CodeEvolver.mutate') as mock_mutate:

            mock_eval.return_value = {"fitness": 0.8, "breakdown": {"correctness": 0.8}}
            mock_mutate.return_value = Candidate(
                id="test-code-123",
                content="def optimized_func(): pass",
                candidate_type="code",
                fitness=0.0,
                parent_ids=[],
                generation=1,
                metadata={},
                created_at=datetime.now(timezone.utc)
            )

            code_content = "def original_func(): pass"
            result = await orchestrator.evolve_code("test_file.py", code_content, {})

            assert "best_candidate" in result
            assert result["best_candidate"]["candidate_type"] == "code"

    @pytest.mark.asyncio
    async def test_evolve_build_plan_method(self, temp_db):
        """Test EvolutionOrchestrator.evolve_build_plan method."""
        from src.core.evolution.orchestrator import EvolutionOrchestrator

        orchestrator = EvolutionOrchestrator(
            db=temp_db,
            solution_name="test_solution",
            max_generations=2,
            population_size=3
        )

        # Mock evaluator and evolver
        with patch('src.core.evolution.build_evaluator.BuildEvaluator.evaluate') as mock_eval, \
             patch('src.core.evolution.build_evolver.BuildEvolver.mutate') as mock_mutate:

            mock_eval.return_value = {"fitness": 0.75, "breakdown": {"efficiency": 0.75}}
            mock_mutate.return_value = Candidate(
                id="test-build-123",
                content=json.dumps({"steps": [{"name": "optimized_step"}]}),
                candidate_type="build_plan",
                fitness=0.0,
                parent_ids=[],
                generation=1,
                metadata={},
                created_at=datetime.now(timezone.utc)
            )

            build_plan = {"steps": [{"name": "original_step"}]}
            result = await orchestrator.evolve_build_plan("build.yaml", build_plan, {})

            assert "best_candidate" in result
            assert result["best_candidate"]["candidate_type"] == "build_plan"


class TestPackageExports:
    """Test that all components are properly exported."""

    def test_code_evolver_import(self):
        """Test CodeEvolver can be imported from package."""
        from src.core.evolution import CodeEvolver
        assert CodeEvolver is not None

    def test_code_evaluator_import(self):
        """Test CodeEvaluator can be imported from package."""
        from src.core.evolution import CodeEvaluator
        assert CodeEvaluator is not None

    def test_build_evolver_import(self):
        """Test BuildEvolver can be imported from package."""
        from src.core.evolution import BuildEvolver
        assert BuildEvolver is not None

    def test_build_evaluator_import(self):
        """Test BuildEvaluator can be imported from package."""
        from src.core.evolution import BuildEvaluator
        assert BuildEvaluator is not None
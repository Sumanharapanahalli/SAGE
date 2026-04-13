from __future__ import annotations

import logging
import random
import uuid
import sqlite3
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .program_db import ProgramDatabase
from .candidate import Candidate
from src.core.db import get_connection

logger = logging.getLogger(__name__)


class EvolutionOrchestrator:
    """
    Main control loop for evolutionary improvement.

    Coordinates prompt/code/build evolution cycles:
    1. Seed initial population from existing configs
    2. For each generation: mutate → evaluate → select
    3. Two-gate HITL: Goal alignment before, Result approval after
    4. Store lineage and fitness progression in ProgramDatabase
    """

    def __init__(
        self,
        db: ProgramDatabase,
        solution_name: str,
        max_generations: int,
        population_size: int
    ):
        if max_generations <= 0:
            raise ValueError("max_generations must be positive")
        if population_size < 2:
            raise ValueError("population_size must be at least 2")

        self.db = db
        self.solution_name = solution_name
        self.max_generations = max_generations
        self.population_size = population_size

        logger.info(f"EvolutionOrchestrator initialized: {solution_name}, {max_generations} gen, pop {population_size}")

    def seed_population(self, role_prompts: Dict[str, str]) -> None:
        """
        Seed generation 0 with existing role prompts.

        Each role prompt becomes a Candidate with fitness=0.0 (uneval).
        This provides the starting genetic material for evolution.
        """
        for role_id, prompt_text in role_prompts.items():
            candidate = Candidate(
                id=f"seed-{role_id}-{uuid.uuid4().hex[:8]}",
                content=prompt_text,
                candidate_type="prompt",
                fitness=0.0,  # Unevaluated
                parent_ids=[],  # No parents (seed)
                generation=0,
                metadata={
                    "role_id": role_id,
                    "source": "seed",
                    "solution": self.solution_name
                },
                created_at=datetime.now(timezone.utc)
            )

            self.db.store(candidate)
            logger.debug(f"Seeded {role_id}: {prompt_text[:50]}...")

        logger.info(f"Seeded generation 0 with {len(role_prompts)} role prompts")

    def get_current_generation(self) -> int:
        """Get the highest generation number in the database."""
        try:
            conn = get_connection(self.db.db_path)
            max_gen = conn.execute("SELECT MAX(generation) FROM candidates").fetchone()[0]
            conn.close()
            return max_gen if max_gen is not None else -1
        except Exception:
            return -1

    def get_population_stats(self, generation: int) -> Dict[str, Any]:
        """Get statistics for a generation (fitness distribution, count, etc)."""
        candidates = self.db.get_generation(generation, "prompt")

        if not candidates:
            return {"count": 0, "fitness": {"min": 0, "max": 0, "avg": 0}}

        fitnesses = [c.fitness for c in candidates]
        return {
            "count": len(candidates),
            "fitness": {
                "min": min(fitnesses),
                "max": max(fitnesses),
                "avg": sum(fitnesses) / len(fitnesses)
            }
        }

    async def evolve_prompt(self, role_id: str, task: str, context: dict) -> dict:
        """
        Run complete prompt evolution cycle for a role.

        1. Ensure seeded population exists for this role
        2. For each generation: evaluate → select → reproduce → mutate
        3. Track fitness progression and lineage
        4. Return best candidate from final generation
        """
        from .prompt_evolver import PromptEvolver
        from .prompt_evaluator import PromptEvaluator

        logger.info(f"Starting prompt evolution for {role_id}: {self.max_generations} generations, pop {self.population_size}")

        evolver = self._get_evolver()
        evaluator = self._get_evaluator()

        # Get current generation (for resuming evolution runs)
        current_gen = self.get_current_generation()

        # Track fitness progression
        fitness_history = []

        for generation in range(current_gen + 1, self.max_generations + 1):
            logger.info(f"Generation {generation}/{self.max_generations}")

            # Get current population
            candidates = self.db.get_generation(generation - 1, "prompt")
            if not candidates:
                logger.error(f"No candidates found for generation {generation - 1}")
                break

            # Evaluate unevaluated candidates
            for candidate in candidates:
                if candidate.fitness == 0.0:  # Unevaluated
                    eval_result = await evaluator.evaluate(candidate)
                    candidate.fitness = eval_result["fitness"]
                    candidate.metadata.update(eval_result.get("breakdown", {}))
                    self.db.store(candidate)  # Update with fitness

            # Track generation fitness
            gen_stats = self.get_population_stats(generation - 1)
            fitness_history.append(gen_stats)
            logger.info(f"Generation {generation - 1} fitness: avg={gen_stats['fitness']['avg']:.3f}, max={gen_stats['fitness']['max']:.3f}")

            # Stop if we've reached max generations
            if generation >= self.max_generations:
                break

            # Select parents via tournament selection
            # Use smaller tournament size if we have few candidates
            available_candidates = len(candidates)
            tournament_size = min(3, max(1, available_candidates))
            num_parents = max(1, self.population_size // 2)

            parents = self.db.tournament_select(
                tournament_size=tournament_size,
                num_winners=num_parents,
                candidate_type="prompt",
                generation=generation - 1
            )

            if len(parents) < 1:
                logger.warning(f"No parents available for reproduction")
                break

            # Generate next generation
            next_generation_candidates = []

            for i in range(self.population_size):
                if evolver.should_crossover() and len(parents) >= 2:
                    # Crossover
                    parent1, parent2 = random.sample(parents, 2)
                    child = await evolver.crossover(parent1, parent2)
                else:
                    # Mutation
                    parent = random.choice(parents)
                    child = await evolver.mutate(parent)

                child.generation = generation
                next_generation_candidates.append(child)

            # Store new generation
            for candidate in next_generation_candidates:
                self.db.store(candidate)

            logger.info(f"Created generation {generation} with {len(next_generation_candidates)} candidates")

        # Find and return best candidate from final generation
        final_generation = self.get_current_generation()
        final_candidates = self.db.get_generation(final_generation, "prompt")

        if not final_candidates:
            logger.error("No candidates in final generation")
            return {"error": "Evolution failed - no final candidates"}

        # Best candidate has highest fitness
        best_candidate = max(final_candidates, key=lambda c: c.fitness)

        # Calculate improvement from seed
        seed_candidates = self.db.get_generation(0, "prompt")
        seed_fitness = max(c.fitness for c in seed_candidates) if seed_candidates else 0.0
        improvement = best_candidate.fitness - seed_fitness

        result = {
            "best_candidate": {
                "id": best_candidate.id,
                "content": best_candidate.content,
                "fitness": best_candidate.fitness,
                "generation": best_candidate.generation,
                "metadata": best_candidate.metadata
            },
            "generation": final_generation,
            "total_candidates": len(final_candidates),
            "improvement": improvement,
            "fitness_history": fitness_history,
            "role_id": role_id
        }

        logger.info(f"Evolution complete: best fitness {best_candidate.fitness:.3f} (improvement: +{improvement:.3f})")
        return result

    async def evolve_code(self, file_path: str, code_content: str, context: dict) -> dict:
        """
        Run complete code evolution cycle for a source file.

        1. Ensure seeded population exists for this code file
        2. For each generation: evaluate → select → reproduce → mutate
        3. Track fitness progression and lineage
        4. Return best candidate from final generation
        """
        from .code_evolver import CodeEvolver
        from .code_evaluator import CodeEvaluator

        logger.info(f"Starting code evolution for {file_path}: {self.max_generations} generations, pop {self.population_size}")

        evolver = self._get_code_evolver()
        evaluator = self._get_code_evaluator()

        # Seed initial population with the provided code
        seed_candidate = Candidate(
            id=f"seed-{file_path}-{uuid.uuid4().hex[:8]}",
            content=code_content,
            candidate_type="code",
            fitness=0.0,
            parent_ids=[],
            generation=0,
            metadata={
                "file_path": file_path,
                "source": "seed",
                "solution": self.solution_name
            },
            created_at=datetime.now(timezone.utc)
        )
        self.db.store(seed_candidate)
        logger.debug(f"Seeded code: {file_path}")

        # Get current generation (for resuming evolution runs)
        current_gen = self.get_current_generation()

        # Track fitness progression
        fitness_history = []

        for generation in range(current_gen + 1, self.max_generations + 1):
            logger.info(f"Generation {generation}/{self.max_generations}")

            # Get current population
            candidates = self.db.get_generation(generation - 1, "code")
            if not candidates:
                logger.error(f"No candidates found for generation {generation - 1}")
                break

            # Evaluate unevaluated candidates
            for candidate in candidates:
                if candidate.fitness == 0.0:  # Unevaluated
                    eval_result = await evaluator.evaluate(candidate)
                    candidate.fitness = eval_result["fitness"]
                    candidate.metadata.update(eval_result.get("breakdown", {}))
                    self.db.store(candidate)  # Update with fitness

            # Track generation fitness
            gen_stats = self.get_population_stats(generation - 1)
            fitness_history.append(gen_stats)
            logger.info(f"Generation {generation - 1} fitness: avg={gen_stats['fitness']['avg']:.3f}, max={gen_stats['fitness']['max']:.3f}")

            # Stop if we've reached max generations
            if generation >= self.max_generations:
                break

            # Select parents via tournament selection
            available_candidates = len(candidates)
            tournament_size = min(3, max(1, available_candidates))
            num_parents = max(1, self.population_size // 2)

            parents = self.db.tournament_select(
                tournament_size=tournament_size,
                num_winners=num_parents,
                candidate_type="code",
                generation=generation - 1
            )

            if len(parents) < 1:
                logger.warning(f"No parents available for reproduction")
                break

            # Generate next generation
            next_generation_candidates = []

            for i in range(self.population_size):
                if evolver.should_crossover() and len(parents) >= 2:
                    # Crossover
                    parent1, parent2 = random.sample(parents, 2)
                    child = await evolver.crossover(parent1, parent2)
                else:
                    # Mutation
                    parent = random.choice(parents)
                    child = await evolver.mutate(parent)

                child.generation = generation
                next_generation_candidates.append(child)

            # Store new generation
            for candidate in next_generation_candidates:
                self.db.store(candidate)

            logger.info(f"Created generation {generation} with {len(next_generation_candidates)} candidates")

        # Find and return best candidate from final generation
        final_generation = self.get_current_generation()
        final_candidates = self.db.get_generation(final_generation, "code")

        if not final_candidates:
            logger.error("No candidates in final generation")
            return {"error": "Evolution failed - no final candidates"}

        # Best candidate has highest fitness
        best_candidate = max(final_candidates, key=lambda c: c.fitness)

        # Calculate improvement from seed
        seed_candidates = self.db.get_generation(0, "code")
        seed_fitness = max(c.fitness for c in seed_candidates) if seed_candidates else 0.0
        improvement = best_candidate.fitness - seed_fitness

        result = {
            "best_candidate": {
                "id": best_candidate.id,
                "content": best_candidate.content,
                "fitness": best_candidate.fitness,
                "generation": best_candidate.generation,
                "metadata": best_candidate.metadata,
                "candidate_type": best_candidate.candidate_type
            },
            "generation": final_generation,
            "total_candidates": len(final_candidates),
            "improvement": improvement,
            "fitness_history": fitness_history,
            "file_path": file_path,
            "evolver_type": "code",
            "status": "success"
        }

        logger.info(f"Code evolution complete: best fitness {best_candidate.fitness:.3f} (improvement: +{improvement:.3f})")
        return result

    async def evolve_build_plan(self, plan_path: str, build_plan: dict, context: dict) -> dict:
        """
        Run complete build plan evolution cycle for a build configuration.

        1. Ensure seeded population exists for this build plan
        2. For each generation: evaluate → select → reproduce → mutate
        3. Track fitness progression and lineage
        4. Return best candidate from final generation
        """
        from .build_evolver import BuildEvolver
        from .build_evaluator import BuildEvaluator

        logger.info(f"Starting build plan evolution for {plan_path}: {self.max_generations} generations, pop {self.population_size}")

        evolver = self._get_build_evolver()
        evaluator = self._get_build_evaluator()

        # Seed initial population with the provided build plan (serialize to JSON)
        seed_candidate = Candidate(
            id=f"seed-{plan_path}-{uuid.uuid4().hex[:8]}",
            content=json.dumps(build_plan),
            candidate_type="build_plan",
            fitness=0.0,
            parent_ids=[],
            generation=0,
            metadata={
                "plan_path": plan_path,
                "source": "seed",
                "solution": self.solution_name
            },
            created_at=datetime.now(timezone.utc)
        )
        self.db.store(seed_candidate)
        logger.debug(f"Seeded build plan: {plan_path}")

        # Get current generation (for resuming evolution runs)
        current_gen = self.get_current_generation()

        # Track fitness progression
        fitness_history = []

        for generation in range(current_gen + 1, self.max_generations + 1):
            logger.info(f"Generation {generation}/{self.max_generations}")

            # Get current population
            candidates = self.db.get_generation(generation - 1, "build_plan")
            if not candidates:
                logger.error(f"No candidates found for generation {generation - 1}")
                break

            # Evaluate unevaluated candidates
            for candidate in candidates:
                if candidate.fitness == 0.0:  # Unevaluated
                    eval_result = await evaluator.evaluate(candidate)
                    candidate.fitness = eval_result["fitness"]
                    candidate.metadata.update(eval_result.get("breakdown", {}))
                    self.db.store(candidate)  # Update with fitness

            # Track generation fitness
            gen_stats = self.get_population_stats(generation - 1)
            fitness_history.append(gen_stats)
            logger.info(f"Generation {generation - 1} fitness: avg={gen_stats['fitness']['avg']:.3f}, max={gen_stats['fitness']['max']:.3f}")

            # Stop if we've reached max generations
            if generation >= self.max_generations:
                break

            # Select parents via tournament selection
            available_candidates = len(candidates)
            tournament_size = min(3, max(1, available_candidates))
            num_parents = max(1, self.population_size // 2)

            parents = self.db.tournament_select(
                tournament_size=tournament_size,
                num_winners=num_parents,
                candidate_type="build_plan",
                generation=generation - 1
            )

            if len(parents) < 1:
                logger.warning(f"No parents available for reproduction")
                break

            # Generate next generation
            next_generation_candidates = []

            for i in range(self.population_size):
                if evolver.should_crossover() and len(parents) >= 2:
                    # Crossover
                    parent1, parent2 = random.sample(parents, 2)
                    child = await evolver.crossover(parent1, parent2)
                else:
                    # Mutation
                    parent = random.choice(parents)
                    child = await evolver.mutate(parent)

                child.generation = generation
                next_generation_candidates.append(child)

            # Store new generation
            for candidate in next_generation_candidates:
                self.db.store(candidate)

            logger.info(f"Created generation {generation} with {len(next_generation_candidates)} candidates")

        # Find and return best candidate from final generation
        final_generation = self.get_current_generation()
        final_candidates = self.db.get_generation(final_generation, "build_plan")

        if not final_candidates:
            logger.error("No candidates in final generation")
            return {"error": "Evolution failed - no final candidates"}

        # Best candidate has highest fitness
        best_candidate = max(final_candidates, key=lambda c: c.fitness)

        # Calculate improvement from seed
        seed_candidates = self.db.get_generation(0, "build_plan")
        seed_fitness = max(c.fitness for c in seed_candidates) if seed_candidates else 0.0
        improvement = best_candidate.fitness - seed_fitness

        # Parse build plan content back to dict for the result
        best_content = json.loads(best_candidate.content) if best_candidate.candidate_type == "build_plan" else best_candidate.content

        result = {
            "best_candidate": {
                "id": best_candidate.id,
                "content": best_content,
                "fitness": best_candidate.fitness,
                "generation": best_candidate.generation,
                "metadata": best_candidate.metadata,
                "candidate_type": best_candidate.candidate_type
            },
            "generation": final_generation,
            "total_candidates": len(final_candidates),
            "improvement": improvement,
            "fitness_history": fitness_history,
            "plan_path": plan_path,
            "evolver_type": "build",
            "status": "success"
        }

        logger.info(f"Build plan evolution complete: best fitness {best_candidate.fitness:.3f} (improvement: +{improvement:.3f})")
        return result

    def _get_evolver(self) -> 'PromptEvolver':
        """Get PromptEvolver instance (factory method for testing)."""
        from .prompt_evolver import PromptEvolver
        return PromptEvolver()

    def _get_evaluator(self) -> 'PromptEvaluator':
        """Get PromptEvaluator instance (factory method for testing)."""
        from .prompt_evaluator import PromptEvaluator
        return PromptEvaluator()

    def _get_code_evolver(self) -> 'CodeEvolver':
        """Get CodeEvolver instance (factory method for testing)."""
        from .code_evolver import CodeEvolver
        return CodeEvolver()

    def _get_code_evaluator(self) -> 'CodeEvaluator':
        """Get CodeEvaluator instance (factory method for testing)."""
        from .code_evaluator import CodeEvaluator
        return CodeEvaluator()

    def _get_build_evolver(self) -> 'BuildEvolver':
        """Get BuildEvolver instance (factory method for testing)."""
        from .build_evolver import BuildEvolver
        return BuildEvolver()

    def _get_build_evaluator(self) -> 'BuildEvaluator':
        """Get BuildEvaluator instance (factory method for testing)."""
        from .build_evaluator import BuildEvaluator
        return BuildEvaluator()

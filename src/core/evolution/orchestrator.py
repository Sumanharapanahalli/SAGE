from __future__ import annotations

import logging
import uuid
import sqlite3
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

from __future__ import annotations

import logging
import os
import random
import sqlite3
from typing import Optional

from src.core.db import get_connection
from src.modules.path_validator import get_safe_sage_dir, safe_mkdir
from .candidate import Candidate

logger = logging.getLogger(__name__)


def get_evolution_db_path() -> str:
    """
    Resolve the evolution DB path to the active solution's .sage/ directory.

    Path: <solution_dir>/.sage/evolution.db

    Mirrors audit_logger._resolve_db_path() pattern for consistency.
    Each solution gets its own evolution database for complete isolation.

    SECURITY: Project name is validated to prevent path traversal attacks.
    Resolved path is verified to stay within solutions directory.
    """
    project = os.environ.get("SAGE_PROJECT", "").strip().lower()
    solutions_dir = os.environ.get(
        "SAGE_SOLUTIONS_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "solutions"),
    )

    if project:
        # Safely construct and validate the .sage directory path
        sage_dir, err = get_safe_sage_dir(project, solutions_dir)
        if err:
            logger.error(f"Invalid project name '{project}': {err}")
            raise ValueError(f"Invalid project name: {err}")

        # Safely create the directory
        success, err = safe_mkdir(sage_dir)
        if not success:
            logger.error(f"Failed to create .sage directory: {err}")
            raise OSError(f"Failed to create .sage directory: {err}")

        db_path = os.path.join(sage_dir, "evolution.db")
        logger.debug(f"Using project evolution DB: {db_path}")
        return db_path

    # Framework fallback — no solution active
    framework_sage = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        ".sage",
    )
    success, err = safe_mkdir(framework_sage)
    if not success:
        logger.error(f"Failed to create framework .sage directory: {err}")
        raise OSError(f"Failed to create framework .sage directory: {err}")

    db_path = os.path.join(framework_sage, "evolution.db")
    logger.debug(f"Using framework evolution DB: {db_path}")
    return db_path


class ProgramDatabase:
    """
    SQLite-backed storage for evolutionary candidates.

    Per-solution isolation: each solution gets its own evolution.db.
    Supports lineage tracking, fitness-based queries, and tournament selection.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_evolution_db_path()
        self._init_schema()

    def _init_schema(self):
        """Create candidates table if not exists."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = get_connection(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    candidate_type TEXT NOT NULL,
                    fitness REAL NOT NULL,
                    parent_ids TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # Index for common queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_generation ON candidates(generation, candidate_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fitness ON candidates(fitness DESC)")

            conn.commit()
            logger.debug(f"ProgramDatabase initialized at {self.db_path}")
        finally:
            conn.close()

    def store(self, candidate: Candidate) -> None:
        """Store a candidate in the database."""
        conn = get_connection(self.db_path)
        try:
            data = candidate.to_dict()

            conn.execute("""
                INSERT OR REPLACE INTO candidates
                (id, content, candidate_type, fitness, parent_ids, generation, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["id"], data["content"], data["candidate_type"], data["fitness"],
                data["parent_ids"], data["generation"], data["metadata"], data["created_at"]
            ))

            conn.commit()
            logger.debug(f"Stored candidate {candidate.id} (fitness={candidate.fitness})")
        finally:
            conn.close()

    def get_by_id(self, candidate_id: str) -> Optional[Candidate]:
        """Retrieve candidate by ID."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM candidates WHERE id = ?",
                (candidate_id,)
            ).fetchone()

            if row:
                return Candidate.from_dict(dict(row))
            return None
        finally:
            conn.close()

    def get_generation(self, generation: int, candidate_type: str) -> list[Candidate]:
        """Get all candidates from a specific generation and type."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM candidates WHERE generation = ? AND candidate_type = ? ORDER BY fitness DESC",
                (generation, candidate_type)
            ).fetchall()

            return [Candidate.from_dict(dict(row)) for row in rows]
        finally:
            conn.close()

    def get_top_candidates(self, limit: int, candidate_type: str) -> list[Candidate]:
        """Get top N candidates by fitness for a given type."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM candidates WHERE candidate_type = ? ORDER BY fitness DESC LIMIT ?",
                (candidate_type, limit)
            ).fetchall()

            return [Candidate.from_dict(dict(row)) for row in rows]
        finally:
            conn.close()

    def tournament_select(
        self,
        tournament_size: int,
        num_winners: int,
        candidate_type: str,
        generation: Optional[int] = None
    ) -> list[Candidate]:
        """
        Tournament selection for parent sampling.

        Biases toward high fitness while preserving diversity.
        Each tournament picks random candidates and selects the fittest.
        """
        # Get candidate pool
        if generation is not None:
            pool = self.get_generation(generation, candidate_type)
        else:
            pool = self.get_all_by_type(candidate_type)

        if len(pool) < tournament_size:
            logger.warning(f"Pool size {len(pool)} < tournament size {tournament_size}")
            return pool[:num_winners]

        winners = []
        for _ in range(num_winners):
            # Sample tournament contestants
            contestants = random.sample(pool, min(tournament_size, len(pool)))

            # Select winner (highest fitness)
            winner = max(contestants, key=lambda c: c.fitness)
            winners.append(winner)

            # Remove winner from pool to ensure diversity
            pool = [c for c in pool if c.id != winner.id]

            if len(pool) < tournament_size:
                break

        return winners

    def get_all_by_type(self, candidate_type: str) -> list[Candidate]:
        """Get all candidates of a given type (for tournament selection pool)."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM candidates WHERE candidate_type = ? ORDER BY fitness DESC",
                (candidate_type,)
            ).fetchall()

            return [Candidate.from_dict(dict(row)) for row in rows]
        finally:
            conn.close()

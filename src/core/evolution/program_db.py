from __future__ import annotations

import logging
import os
import sqlite3
from typing import Optional

from .candidate import Candidate

logger = logging.getLogger(__name__)


class ProgramDatabase:
    """
    SQLite-backed storage for evolutionary candidates.

    Per-solution isolation: each solution gets its own evolution.db.
    Supports lineage tracking, fitness-based queries, and tournament selection.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self):
        """Create candidates table if not exists."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
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
        conn.close()
        logger.debug(f"ProgramDatabase initialized at {self.db_path}")

    def store(self, candidate: Candidate) -> None:
        """Store a candidate in the database."""
        conn = sqlite3.connect(self.db_path)
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
        conn.close()
        logger.debug(f"Stored candidate {candidate.id} (fitness={candidate.fitness})")

    def get_by_id(self, candidate_id: str) -> Optional[Candidate]:
        """Retrieve candidate by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT * FROM candidates WHERE id = ?",
            (candidate_id,)
        ).fetchone()

        conn.close()

        if row:
            return Candidate.from_dict(dict(row))
        return None

    def get_generation(self, generation: int, candidate_type: str) -> list[Candidate]:
        """Get all candidates from a specific generation and type."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT * FROM candidates WHERE generation = ? AND candidate_type = ? ORDER BY fitness DESC",
            (generation, candidate_type)
        ).fetchall()

        conn.close()
        return [Candidate.from_dict(dict(row)) for row in rows]

    def get_top_candidates(self, limit: int, candidate_type: str) -> list[Candidate]:
        """Get top N candidates by fitness for a given type."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT * FROM candidates WHERE candidate_type = ? ORDER BY fitness DESC LIMIT ?",
            (candidate_type, limit)
        ).fetchall()

        conn.close()
        return [Candidate.from_dict(dict(row)) for row in rows]

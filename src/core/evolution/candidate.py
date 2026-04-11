from __future__ import annotations

import json
from datetime import datetime
from typing import Literal
from dataclasses import dataclass


@dataclass
class Candidate:
    """
    Evolutionary candidate (prompt, code, or build plan) with fitness and lineage.

    Based on AlphaEvolve paper: each candidate has measurable fitness,
    parent lineage for tracking mutations, and metadata for evaluation breakdown.
    """

    id: str
    content: str
    candidate_type: Literal["prompt", "code", "build_plan"]
    fitness: float
    parent_ids: list[str]
    generation: int
    metadata: dict
    created_at: datetime

    def __post_init__(self):
        """Validate fitness and candidate_type constraints."""
        if not (0.0 <= self.fitness <= 1.0):
            raise ValueError(f"Fitness must be in [0.0, 1.0], got {self.fitness}")

        valid_types = {"prompt", "code", "build_plan"}
        if self.candidate_type not in valid_types:
            raise ValueError(f"candidate_type must be one of {valid_types}, got {self.candidate_type}")

    def to_dict(self) -> dict:
        """Convert to dict for SQLite storage."""
        return {
            "id": self.id,
            "content": self.content,
            "candidate_type": self.candidate_type,
            "fitness": self.fitness,
            "parent_ids": ",".join(self.parent_ids),
            "generation": self.generation,
            "metadata": json.dumps(self.metadata),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Candidate:
        """Restore from SQLite dict representation."""
        return cls(
            id=data["id"],
            content=data["content"],
            candidate_type=data["candidate_type"],
            fitness=data["fitness"],
            parent_ids=data["parent_ids"].split(",") if data["parent_ids"] else [],
            generation=data["generation"],
            metadata=json.loads(data["metadata"]) if data["metadata"] != "{}" else {},
            created_at=datetime.fromisoformat(data["created_at"]),
        )

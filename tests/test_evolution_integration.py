"""
End-to-end integration tests for the SAGE evolution framework.

Tests the complete workflow: candidate storage → evaluation → tournament selection.
Verifies that evolution components work together as an integrated system.
"""

import asyncio
import os
import tempfile
from datetime import datetime, timezone

from src.core.evolution import Candidate, ProgramDatabase, Evaluator, EnsembleEvaluator


class LengthEvaluator(Evaluator):
    """Simple evaluator for integration testing based on content length."""

    def __init__(self, name: str, base_score: float):
        super().__init__(name)
        self.base_score = base_score

    async def evaluate(self, candidate: Candidate) -> dict:
        # Score based on content length (simple heuristic)
        length_bonus = min(0.2, len(candidate.content) / 100)
        score = min(1.0, self.base_score + length_bonus)

        return {
            "score": score,
            "details": f"Length-based evaluation: {len(candidate.content)} chars"
        }


def test_end_to_end_evolution_workflow():
    """Test complete workflow: store candidates, evaluate with ensemble, tournament select."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_evolution.db")
        db = ProgramDatabase(db_path)

        # Create ensemble evaluator
        eval1 = LengthEvaluator("length", 0.5)
        eval2 = LengthEvaluator("quality", 0.7)
        ensemble = EnsembleEvaluator([
            (eval1, 0.6),
            (eval2, 0.4)
        ])

        # Store initial generation
        candidates = []
        for i in range(5):
            content = f"prompt content {i}" + " extra" * i  # Varying lengths
            candidate = Candidate(
                id=f"gen0-{i}",
                content=content,
                candidate_type="prompt",
                fitness=0.0,  # Will be updated by evaluation
                parent_ids=[],
                generation=0,
                metadata={},
                created_at=datetime.now(timezone.utc)
            )
            candidates.append(candidate)
            db.store(candidate)

        # Evaluate all candidates and update fitness
        async def evaluate_all():
            for candidate in candidates:
                result = await ensemble.evaluate(candidate)
                candidate.fitness = result["fitness"]
                candidate.metadata["evaluation"] = result["breakdown"]
                db.store(candidate)  # Update with new fitness

        asyncio.run(evaluate_all())

        # Tournament selection for parents
        parents = db.tournament_select(
            tournament_size=3,
            num_winners=2,
            candidate_type="prompt"
        )

        assert len(parents) == 2
        assert all(p.fitness > 0 for p in parents)

        # Verify database state
        generation_0 = db.get_generation(0, "prompt")
        assert len(generation_0) == 5

        top_candidates = db.get_top_candidates(2, "prompt")
        assert len(top_candidates) == 2
        assert top_candidates[0].fitness >= top_candidates[1].fitness


def test_package_imports():
    """Test that all core evolution classes are importable from package root."""
    from src.core.evolution import Candidate, ProgramDatabase, Evaluator, EnsembleEvaluator

    # Should not raise ImportError
    assert Candidate is not None
    assert ProgramDatabase is not None
    assert Evaluator is not None
    assert EnsembleEvaluator is not None

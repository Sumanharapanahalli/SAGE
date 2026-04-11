import os
import tempfile
from datetime import datetime, timezone

from src.core.evolution.program_db import ProgramDatabase
from src.core.evolution.candidate import Candidate


def test_program_db_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_evolution.db")
        db = ProgramDatabase(db_path)
        assert os.path.exists(db_path)


def test_store_candidate():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_evolution.db")
        db = ProgramDatabase(db_path)

        candidate = Candidate(
            id="test-1",
            content="test prompt",
            candidate_type="prompt",
            fitness=0.7,
            parent_ids=["parent-1"],
            generation=2,
            metadata={"score": 0.7},
            created_at=datetime.now(timezone.utc)
        )

        db.store(candidate)
        retrieved = db.get_by_id("test-1")
        assert retrieved is not None
        assert retrieved.fitness == 0.7
        assert retrieved.candidate_type == "prompt"


def test_get_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_evolution.db")
        db = ProgramDatabase(db_path)

        # Store candidates from different generations
        for i in range(3):
            candidate = Candidate(
                id=f"gen1-{i}",
                content=f"prompt {i}",
                candidate_type="prompt",
                fitness=0.5 + i * 0.1,
                parent_ids=[],
                generation=1,
                metadata={},
                created_at=datetime.now(timezone.utc)
            )
            db.store(candidate)

        gen1_candidates = db.get_generation(1, candidate_type="prompt")
        assert len(gen1_candidates) == 3
        assert all(c.generation == 1 for c in gen1_candidates)


def test_get_top_candidates():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_evolution.db")
        db = ProgramDatabase(db_path)

        # Store candidates with different fitness scores
        fitnesses = [0.9, 0.7, 0.8, 0.6]
        for i, fitness in enumerate(fitnesses):
            candidate = Candidate(
                id=f"cand-{i}",
                content=f"content {i}",
                candidate_type="code",
                fitness=fitness,
                parent_ids=[],
                generation=1,
                metadata={},
                created_at=datetime.now(timezone.utc)
            )
            db.store(candidate)

        top2 = db.get_top_candidates(2, candidate_type="code")
        assert len(top2) == 2
        assert top2[0].fitness == 0.9  # Highest first
        assert top2[1].fitness == 0.8  # Second highest


def test_tournament_selection():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_evolution.db")
        db = ProgramDatabase(db_path)

        # Store candidates with varying fitness
        fitnesses = [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]
        for i, fitness in enumerate(fitnesses):
            candidate = Candidate(
                id=f"cand-{i}",
                content=f"content {i}",
                candidate_type="prompt",
                fitness=fitness,
                parent_ids=[],
                generation=1,
                metadata={},
                created_at=datetime.now(timezone.utc)
            )
            db.store(candidate)

        # Tournament selection should bias toward higher fitness
        selected = db.tournament_select(tournament_size=3, num_winners=2, candidate_type="prompt")
        assert len(selected) == 2
        assert all(isinstance(c, Candidate) for c in selected)

        # Run multiple tournaments and verify bias toward high fitness
        high_fitness_selected = 0
        for _ in range(20):
            winners = db.tournament_select(tournament_size=3, num_winners=1, candidate_type="prompt")
            if winners[0].fitness >= 0.7:  # Top half
                high_fitness_selected += 1

        # Should select high-fitness candidates more often (not guaranteed but likely)
        assert high_fitness_selected >= 10  # At least half the time


def test_tournament_selection_diversity():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_evolution.db")
        db = ProgramDatabase(db_path)

        # Store identical fitness candidates
        for i in range(5):
            candidate = Candidate(
                id=f"same-{i}",
                content=f"diverse content {i}",
                candidate_type="code",
                fitness=0.8,  # All same fitness
                parent_ids=[],
                generation=1,
                metadata={},
                created_at=datetime.now(timezone.utc)
            )
            db.store(candidate)

        # Should still return different candidates (diversity preserved)
        selected = db.tournament_select(tournament_size=3, num_winners=3, candidate_type="code")
        assert len(selected) == 3
        ids = [c.id for c in selected]
        assert len(set(ids)) == 3  # All different IDs

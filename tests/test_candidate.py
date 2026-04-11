from datetime import datetime, timezone
from src.core.evolution.candidate import Candidate


def test_candidate_creation():
    candidate = Candidate(
        id="test-123",
        content="def hello(): return 'world'",
        candidate_type="code",
        fitness=0.85,
        parent_ids=["parent-1", "parent-2"],
        generation=3,
        metadata={"mutation": "crossover", "test_score": 0.9},
        created_at=datetime.now(timezone.utc)
    )
    assert candidate.id == "test-123"
    assert candidate.fitness == 0.85
    assert len(candidate.parent_ids) == 2


def test_candidate_fitness_validation():
    # Should raise ValueError for fitness outside [0.0, 1.0]
    try:
        Candidate(
            id="bad", content="test", candidate_type="prompt",
            fitness=1.5, parent_ids=[], generation=1,
            metadata={}, created_at=datetime.now(timezone.utc)
        )
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_candidate_type_validation():
    # Should raise ValueError for invalid candidate_type
    try:
        Candidate(
            id="bad", content="test", candidate_type="invalid",
            fitness=0.5, parent_ids=[], generation=1,
            metadata={}, created_at=datetime.now(timezone.utc)
        )
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

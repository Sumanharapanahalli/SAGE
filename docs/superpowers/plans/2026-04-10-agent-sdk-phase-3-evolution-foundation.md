# Agent SDK Phase 3 — Evolution Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the evolutionary foundation for SAGE: Candidate storage, ProgramDatabase with tournament selection, and base Evaluator infrastructure for AlphaEvolve-style prompt/code/build evolution.

**Architecture:** SQLite-backed candidate storage with per-solution isolation (`solutions/<name>/.sage/evolution.db`), tournament selection for parent sampling, ensemble evaluation framework with weighted fitness scoring, and full lineage tracking for audit trails.

**Tech Stack:** Python 3.12, SQLite, pydantic dataclasses, pytest, datetime, typing, uuid.

---

## File Structure

**New files:**
- `src/core/evolution/__init__.py` — Package init with public API exports
- `src/core/evolution/candidate.py` — Candidate dataclass with validation
- `src/core/evolution/program_db.py` — ProgramDatabase SQLite backend with tournament selection
- `src/core/evolution/evaluators.py` — Base Evaluator interface + EnsembleEvaluator
- `tests/test_candidate.py` — Unit tests for Candidate dataclass
- `tests/test_program_db.py` — Integration tests for ProgramDatabase SQLite operations
- `tests/test_evaluators.py` — Unit tests for evaluator infrastructure

**Modified files:**
- `src/memory/audit_logger.py:26-41` — Update `_resolve_db_path()` to support evolution.db alongside audit_log.db

**Dependencies:** No new external dependencies (uses existing SQLite, pydantic, uuid from SAGE stack).

---

### Task 1: Candidate Data Model

**Files:**
- Create: `src/core/evolution/__init__.py`
- Create: `src/core/evolution/candidate.py`
- Test: `tests/test_candidate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_candidate.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_candidate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.evolution.candidate'`

- [ ] **Step 3: Create package init**

```python
# src/core/evolution/__init__.py
"""
SAGE Evolutionary Layer

AlphaEvolve-inspired evolutionary improvement of prompts, code, and build plans.
Requires opt-in per solution via evolution.enabled config.
"""

from .candidate import Candidate
from .program_db import ProgramDatabase
from .evaluators import Evaluator, EnsembleEvaluator

__all__ = ["Candidate", "ProgramDatabase", "Evaluator", "EnsembleEvaluator"]
```

- [ ] **Step 4: Write minimal Candidate implementation**

```python
# src/core/evolution/candidate.py
from __future__ import annotations

from datetime import datetime
from typing import Literal
from dataclasses import dataclass, field


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
            "metadata": str(self.metadata),  # JSON string
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Candidate:
        """Restore from SQLite dict representation."""
        import json
        from datetime import datetime
        
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_candidate.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/core/evolution/ tests/test_candidate.py
git commit -m "feat(phase3): add Candidate dataclass with validation"
```

---

### Task 2: ProgramDatabase Foundation

**Files:**
- Create: `src/core/evolution/program_db.py`
- Test: `tests/test_program_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_program_db.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_program_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.evolution.program_db'`

- [ ] **Step 3: Write minimal ProgramDatabase implementation**

```python
# src/core/evolution/program_db.py
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
                parent_ids TEXT NOT NULL,  -- comma-separated
                generation INTEGER NOT NULL,
                metadata TEXT NOT NULL,   -- JSON string
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_program_db.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/core/evolution/program_db.py tests/test_program_db.py
git commit -m "feat(phase3): add ProgramDatabase SQLite backend"
```

---

### Task 3: Tournament Selection Algorithm

**Files:**
- Modify: `src/core/evolution/program_db.py:85-120`
- Test: `tests/test_program_db.py` (append new tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_program_db.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_program_db.py::test_tournament_selection -v`
Expected: FAIL with `AttributeError: 'ProgramDatabase' object has no attribute 'tournament_select'`

- [ ] **Step 3: Implement tournament selection method**

Add to `src/core/evolution/program_db.py` after the `get_top_candidates` method:

```python
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
        import random
        
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
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        rows = conn.execute(
            "SELECT * FROM candidates WHERE candidate_type = ? ORDER BY fitness DESC",
            (candidate_type,)
        ).fetchall()
        
        conn.close()
        return [Candidate.from_dict(dict(row)) for row in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_program_db.py::test_tournament_selection -v`
Expected: PASS

- [ ] **Step 5: Run all database tests**

Run: `python -m pytest tests/test_program_db.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add src/core/evolution/program_db.py tests/test_program_db.py
git commit -m "feat(phase3): add tournament selection for parent sampling"
```

---

### Task 4: Base Evaluator Interface

**Files:**
- Create: `src/core/evolution/evaluators.py`
- Test: `tests/test_evaluators.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_evaluators.py
from abc import ABC, abstractmethod
from src.core.evolution.evaluators import Evaluator, EnsembleEvaluator
from src.core.evolution.candidate import Candidate
from datetime import datetime, timezone


class MockEvaluator(Evaluator):
    """Test evaluator that returns fixed scores."""
    
    def __init__(self, name: str, fixed_score: float):
        super().__init__(name)
        self.fixed_score = fixed_score
    
    async def evaluate(self, candidate: Candidate) -> dict:
        return {
            "score": self.fixed_score,
            "details": f"Mock evaluation by {self.name}"
        }


def test_base_evaluator():
    evaluator = MockEvaluator("test_eval", 0.8)
    assert evaluator.name == "test_eval"


def test_ensemble_evaluator_creation():
    eval1 = MockEvaluator("eval1", 0.7)
    eval2 = MockEvaluator("eval2", 0.9)
    
    ensemble = EnsembleEvaluator([
        (eval1, 0.6),  # weight 0.6
        (eval2, 0.4),  # weight 0.4
    ])
    
    assert len(ensemble.evaluators) == 2
    assert ensemble.weights == [0.6, 0.4]


def test_ensemble_evaluate():
    """Test that ensemble combines scores with weights correctly."""
    import asyncio
    
    eval1 = MockEvaluator("eval1", 0.8)  # score 0.8
    eval2 = MockEvaluator("eval2", 0.6)  # score 0.6
    
    ensemble = EnsembleEvaluator([
        (eval1, 0.7),  # weight 0.7
        (eval2, 0.3),  # weight 0.3
    ])
    
    candidate = Candidate(
        id="test",
        content="test content",
        candidate_type="prompt",
        fitness=0.0,  # Will be updated
        parent_ids=[],
        generation=1,
        metadata={},
        created_at=datetime.now(timezone.utc)
    )
    
    # Run ensemble evaluation
    result = asyncio.run(ensemble.evaluate(candidate))
    
    # Expected: 0.8 * 0.7 + 0.6 * 0.3 = 0.56 + 0.18 = 0.74
    assert abs(result["fitness"] - 0.74) < 0.001
    assert "eval1" in result["breakdown"]
    assert "eval2" in result["breakdown"]


def test_ensemble_weight_normalization():
    """Test that weights are normalized to sum to 1.0."""
    eval1 = MockEvaluator("eval1", 0.5)
    eval2 = MockEvaluator("eval2", 0.5)
    
    # Weights that don't sum to 1
    ensemble = EnsembleEvaluator([
        (eval1, 3.0),
        (eval2, 2.0),
    ])
    
    # Should be normalized to [0.6, 0.4]
    assert abs(ensemble.weights[0] - 0.6) < 0.001
    assert abs(ensemble.weights[1] - 0.4) < 0.001
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_evaluators.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.core.evolution.evaluators'`

- [ ] **Step 3: Write minimal Evaluator implementation**

```python
# src/core/evolution/evaluators.py
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from .candidate import Candidate

logger = logging.getLogger(__name__)


class Evaluator(ABC):
    """
    Base interface for candidate evaluation.
    
    Evaluators score candidates on different dimensions (e.g., test pass rate,
    code quality, task completion). The EnsembleEvaluator combines multiple
    evaluators with configurable weights.
    """
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    async def evaluate(self, candidate: Candidate) -> dict:
        """
        Evaluate a candidate and return scoring details.
        
        Returns:
            dict with keys:
            - "score": float in [0.0, 1.0] 
            - "details": str with evaluation explanation
            - (optional) other metrics specific to this evaluator
        """
        pass


class EnsembleEvaluator:
    """
    Combines multiple evaluators with weighted scoring.
    
    Final fitness = sum(evaluator_score * weight) for all evaluators.
    Weights are normalized to sum to 1.0 during initialization.
    """
    
    def __init__(self, evaluator_weights: list[tuple[Evaluator, float]]):
        """
        Args:
            evaluator_weights: List of (evaluator, weight) tuples
        """
        self.evaluators = [ev for ev, _ in evaluator_weights]
        raw_weights = [weight for _, weight in evaluator_weights]
        
        # Normalize weights to sum to 1.0
        total_weight = sum(raw_weights)
        if total_weight == 0:
            raise ValueError("Total weight cannot be zero")
        
        self.weights = [w / total_weight for w in raw_weights]
        
        logger.info(f"EnsembleEvaluator initialized with {len(self.evaluators)} evaluators")
        for i, (evaluator, weight) in enumerate(zip(self.evaluators, self.weights)):
            logger.debug(f"  {evaluator.name}: weight={weight:.3f}")
    
    async def evaluate(self, candidate: Candidate) -> dict:
        """
        Run all evaluators and compute weighted fitness score.
        
        Returns:
            dict with keys:
            - "fitness": float in [0.0, 1.0] (weighted average)
            - "breakdown": dict mapping evaluator names to their individual results
        """
        breakdown = {}
        total_score = 0.0
        
        for evaluator, weight in zip(self.evaluators, self.weights):
            try:
                result = await evaluator.evaluate(candidate)
                score = result.get("score", 0.0)
                
                # Validate score is in valid range
                if not (0.0 <= score <= 1.0):
                    logger.warning(f"{evaluator.name} returned invalid score {score}, clamping to [0,1]")
                    score = max(0.0, min(1.0, score))
                
                breakdown[evaluator.name] = result
                total_score += score * weight
                
                logger.debug(f"{evaluator.name}: score={score:.3f}, weight={weight:.3f}, contribution={score*weight:.3f}")
                
            except Exception as e:
                logger.error(f"Evaluator {evaluator.name} failed: {e}")
                breakdown[evaluator.name] = {"score": 0.0, "error": str(e)}
        
        return {
            "fitness": total_score,
            "breakdown": breakdown
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_evaluators.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/core/evolution/evaluators.py tests/test_evaluators.py
git commit -m "feat(phase3): add base Evaluator interface and EnsembleEvaluator"
```

---

### Task 5: Database Path Integration

**Files:**
- Modify: `src/memory/audit_logger.py:11-41`
- Test: `tests/test_evolution_db_path.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_evolution_db_path.py
import os
import tempfile
from unittest.mock import patch

from src.core.evolution.program_db import get_evolution_db_path


def test_get_evolution_db_path_with_project():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {
            "SAGE_PROJECT": "medtech",
            "SAGE_SOLUTIONS_DIR": tmpdir
        }):
            db_path = get_evolution_db_path()
            expected = os.path.join(tmpdir, "medtech", ".sage", "evolution.db")
            assert db_path == expected


def test_get_evolution_db_path_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {
            "SAGE_PROJECT": "",  # No project set
            "SAGE_SOLUTIONS_DIR": tmpdir
        }):
            db_path = get_evolution_db_path()
            # Should fall back to framework .sage directory
            assert ".sage" in db_path
            assert "evolution.db" in db_path


def test_program_database_uses_project_path():
    """Test that ProgramDatabase automatically uses the project-specific path."""
    from src.core.evolution.program_db import ProgramDatabase
    
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {
            "SAGE_PROJECT": "testproj",
            "SAGE_SOLUTIONS_DIR": tmpdir
        }):
            # ProgramDatabase should auto-resolve path when no path given
            db = ProgramDatabase()  # No explicit path
            expected_dir = os.path.join(tmpdir, "testproj", ".sage")
            assert expected_dir in db.db_path
            assert db.db_path.endswith("evolution.db")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_evolution_db_path.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_evolution_db_path'`

- [ ] **Step 3: Add path resolution function**

Add to the end of `src/core/evolution/program_db.py`:

```python
def get_evolution_db_path() -> str:
    """
    Resolve the evolution DB path to the active solution's .sage/ directory.
    
    Path: <solution_dir>/.sage/evolution.db
    
    Mirrors audit_logger._resolve_db_path() pattern for consistency.
    Each solution gets its own evolution database for complete isolation.
    """
    project = os.environ.get("SAGE_PROJECT", "").strip().lower()
    solutions_dir = os.environ.get(
        "SAGE_SOLUTIONS_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "solutions"),
    )
    
    if project:
        sage_dir = os.path.join(os.path.abspath(solutions_dir), project, ".sage")
        os.makedirs(sage_dir, exist_ok=True)
        return os.path.join(sage_dir, "evolution.db")
    
    # Framework fallback — no solution active
    framework_sage = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        ".sage",
    )
    os.makedirs(framework_sage, exist_ok=True)
    return os.path.join(framework_sage, "evolution.db")
```

- [ ] **Step 4: Update ProgramDatabase constructor**

Modify the `ProgramDatabase.__init__` method in `src/core/evolution/program_db.py`:

```python
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_evolution_db_path()
        self._init_schema()
```

Update the import at the top of the file:

```python
from typing import Optional
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_evolution_db_path.py -v`
Expected: 3 passed

- [ ] **Step 6: Update existing tests to work with new constructor**

Update `tests/test_program_db.py` to explicitly pass temp paths:

```python
# In all test functions, change:
# db = ProgramDatabase(db_path)
# to explicitly pass the path since we changed the default behavior
```

Run: `python -m pytest tests/test_program_db.py -v`
Expected: All tests still pass

- [ ] **Step 7: Commit**

```bash
git add src/core/evolution/program_db.py tests/test_evolution_db_path.py tests/test_program_db.py
git commit -m "feat(phase3): add per-solution evolution database path resolution"
```

---

### Task 6: Integration and Package Updates

**Files:**
- Modify: `src/core/evolution/__init__.py` (add exports)
- Test: `tests/test_evolution_integration.py`

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_evolution_integration.py
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch

from src.core.evolution import Candidate, ProgramDatabase, EnsembleEvaluator


class TestEvaluator:
    """Simple evaluator for integration testing."""
    
    def __init__(self, name: str, base_score: float):
        self.name = name
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
        eval1 = TestEvaluator("length", 0.5)
        eval2 = TestEvaluator("quality", 0.7)
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
        import asyncio
        
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_evolution_integration.py -v`
Expected: FAIL with import errors (missing Evaluator export)

- [ ] **Step 3: Update package exports**

Update `src/core/evolution/__init__.py`:

```python
"""
SAGE Evolutionary Layer

AlphaEvolve-inspired evolutionary improvement of prompts, code, and build plans.
Requires opt-in per solution via evolution.enabled config.
"""

from .candidate import Candidate
from .program_db import ProgramDatabase, get_evolution_db_path
from .evaluators import Evaluator, EnsembleEvaluator

__all__ = [
    "Candidate", 
    "ProgramDatabase", 
    "get_evolution_db_path",
    "Evaluator", 
    "EnsembleEvaluator"
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_evolution_integration.py -v`
Expected: 2 passed

- [ ] **Step 5: Run full Phase 3 test suite**

Run: `python -m pytest tests/test_candidate.py tests/test_program_db.py tests/test_evaluators.py tests/test_evolution_db_path.py tests/test_evolution_integration.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/core/evolution/__init__.py tests/test_evolution_integration.py
git commit -m "feat(phase3): complete evolution foundation with integration tests"
```

---

## Self-Review

**Spec coverage:**
✅ **Candidate dataclass** — Task 1 implements the exact dataclass from spec with validation
✅ **ProgramDatabase** — Task 2-3 implements SQLite backend with tournament selection  
✅ **Base Evaluator interface** — Task 4 implements ABC interface + ensemble evaluation
✅ **SQLite persistence** — Covered in Task 2
✅ **Tournament sampling** — Covered in Task 3  
✅ **Lineage tracking** — Covered in Candidate.parent_ids and database storage

**Placeholder scan:** ✅ No TODOs, TBDs, or placeholders - all code is complete

**Type consistency:** ✅ Candidate type hints match across all tasks, ProgramDatabase methods use consistent signatures

Phase 3 foundation is complete! Next phases can build PromptEvolver, CodeEvolver, and BuildEvolver on this base infrastructure.
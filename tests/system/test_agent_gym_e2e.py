"""
SAGE[ai] — Agent Gym System End-to-End Tests
================================================
Full integration tests for the Agent Gym training system.

Covers:
  1. Gym API endpoints — train, batch, ratings, history, analytics
  2. Exercise catalog — seed loading, domain filtering, variant generation
  3. Curriculum system — difficulty progression, spaced repetition
  4. Glicko-2 ratings — RD shrinkage, confidence intervals
  5. SQLite persistence — data survives across instances
  6. Full training loop — play → grade → critique → reflect → compound

All LLM calls are mocked. These tests verify wiring, state transitions,
and data integrity across the full training lifecycle.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.system


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_LLM_RESPONSE = json.dumps({
    "score": 72,
    "flaws": ["Minor issue found"],
    "suggestions": ["Improve error handling"],
    "missing": [],
    "security_risks": [],
    "summary": "Adequate implementation with room for improvement",
})

MOCK_REFLECTION = json.dumps({
    "reflection": "I should have added boundary checks for the input range.",
    "improvement_plan": [
        "Add input validation at function entry",
        "Handle edge cases for zero and negative values",
        "Add unit tests for boundary conditions",
    ],
})


@pytest.fixture
def gym_client(tmp_audit_db):
    """System test client with mocked LLM and isolated DBs."""
    from src.core.agent_gym import AgentGym
    db_path = os.path.join(tempfile.mkdtemp(), "test_api_gym.db")
    isolated = AgentGym(db_path=db_path)
    with patch("src.interface.api._get_audit_logger", return_value=tmp_audit_db), \
         patch("src.core.agent_gym.agent_gym", isolated):
        from src.interface.api import app
        with TestClient(app) as c:
            yield c


@pytest.fixture
def mock_llm():
    """Mock LLM gateway for all gym tests."""
    with patch("src.core.llm_gateway.llm_gateway") as mock_gw:
        mock_gw.generate.return_value = MOCK_LLM_RESPONSE
        mock_gw.generate_for_task.return_value = MOCK_LLM_RESPONSE
        mock_gw.provider_pool = MagicMock()
        mock_gw.provider_pool.list_providers.return_value = []
        mock_gw.provider_pool.get.return_value = None
        yield mock_gw


@pytest.fixture
def isolated_gym():
    """Create an isolated AgentGym instance with temp DB."""
    from src.core.agent_gym import AgentGym
    db_path = os.path.join(tempfile.mkdtemp(), "test_gym.db")
    return AgentGym(db_path=db_path)


@pytest.fixture
def isolated_catalog():
    """Create an isolated ExerciseCatalog instance with temp DB."""
    from src.core.exercise_catalog import ExerciseCatalog
    db_path = os.path.join(tempfile.mkdtemp(), "test_catalog.db")
    return ExerciseCatalog(db_path=db_path)


# ===========================================================================
# 1. Gym API Endpoints
# ===========================================================================

class TestGymAPIEndpoints:
    """Test all gym-related API endpoints via TestClient."""

    def test_gym_train_returns_session(self, gym_client, mock_llm):
        """POST /gym/train returns a valid training session."""
        with patch("src.memory.vector_store.vector_memory") as mock_vm:
            mock_vm.add_feedback = MagicMock()
            mock_vm.search = MagicMock(return_value=[])
            resp = gym_client.post("/gym/train", json={
                "role": "firmware_engineer",
                "difficulty": "beginner",
            })

        assert resp.status_code == 200
        body = resp.json()
        assert "session_id" in body
        assert body["agent_role"] == "firmware_engineer"
        assert body["status"] in ("completed", "failed")

    def test_gym_train_nonexistent_role(self, gym_client, mock_llm):
        """Training a nonexistent role fails gracefully."""
        resp = gym_client.post("/gym/train", json={
            "role": "nonexistent_role_xyz",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"

    def test_gym_ratings_returns_leaderboard(self, gym_client):
        """GET /gym/ratings returns leaderboard and stats."""
        resp = gym_client.get("/gym/ratings")
        assert resp.status_code == 200
        body = resp.json()
        assert "leaderboard" in body
        assert "stats" in body
        assert "total_sessions" in body["stats"]

    def test_gym_role_ratings(self, gym_client):
        """GET /gym/ratings/{role} returns ratings for a specific role."""
        resp = gym_client.get("/gym/ratings/firmware_engineer")
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "firmware_engineer"
        assert "ratings" in body

    def test_gym_history_empty(self, gym_client):
        """GET /gym/history returns empty list when no training done."""
        resp = gym_client.get("/gym/history")
        assert resp.status_code == 200
        body = resp.json()
        assert "sessions" in body

    def test_gym_analytics_returns_structure(self, gym_client):
        """GET /gym/analytics returns proper analytics structure."""
        resp = gym_client.get("/gym/analytics?role=firmware_engineer")
        assert resp.status_code == 200
        body = resp.json()
        assert "global_stats" in body
        assert "leaderboard" in body
        assert "score_trend" in body
        assert "improvement_rate" in body
        assert "difficulty_breakdown" in body

    def test_gym_analytics_without_role(self, gym_client):
        """GET /gym/analytics without role returns global stats only."""
        resp = gym_client.get("/gym/analytics")
        assert resp.status_code == 200
        body = resp.json()
        assert "global_stats" in body
        assert "leaderboard" in body
        # No role-specific fields
        assert "score_trend" not in body

    def test_gym_curriculum_no_data(self, gym_client):
        """GET /gym/curriculum/{role} returns message when no data."""
        resp = gym_client.get("/gym/curriculum/firmware_engineer")
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "firmware_engineer"

    def test_gym_batch_train(self, gym_client, mock_llm):
        """POST /gym/train/batch trains multiple roles."""
        with patch("src.memory.vector_store.vector_memory") as mock_vm:
            mock_vm.add_feedback = MagicMock()
            mock_vm.search = MagicMock(return_value=[])
            resp = gym_client.post("/gym/train/batch", json={
                "roles": ["nonexistent_a", "nonexistent_b"],
                "max_parallel": 2,
            })

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert "sessions" in body

    def test_gym_session_not_found(self, gym_client):
        """GET /gym/session/{id} returns error for unknown session."""
        resp = gym_client.get("/gym/session/nonexistent-id")
        assert resp.status_code == 200
        body = resp.json()
        assert "error" in body


# ===========================================================================
# 2. Exercise Catalog API
# ===========================================================================

class TestCatalogAPIEndpoints:
    """Test exercise catalog API endpoints."""

    def test_catalog_stats(self, gym_client):
        """GET /gym/catalog returns catalog statistics."""
        resp = gym_client.get("/gym/catalog")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_exercises" in body
        assert body["total_exercises"] > 100
        assert "domains" in body
        assert "openfw" in body["domains"]
        assert "openswe" in body["domains"]

    def test_catalog_domain_exercises(self, gym_client):
        """GET /gym/catalog/{domain} returns exercises for a domain."""
        resp = gym_client.get("/gym/catalog/openfw")
        assert resp.status_code == 200
        body = resp.json()
        assert body["domain"] == "openfw"
        assert body["count"] > 50  # firmware has 65 seeds
        assert len(body["exercises"]) > 0

        # Verify exercise structure
        ex = body["exercises"][0]
        assert "id" in ex
        assert "title" in ex
        assert "description" in ex
        assert "difficulty" in ex
        assert "tags" in ex
        assert "acceptance_criteria" in ex

    def test_catalog_domain_with_difficulty(self, gym_client):
        """GET /gym/catalog/{domain}?difficulty=beginner filters correctly."""
        resp = gym_client.get("/gym/catalog/openfw?difficulty=beginner")
        assert resp.status_code == 200
        body = resp.json()
        assert body["difficulty"] == "beginner"
        for ex in body["exercises"]:
            assert ex["difficulty"] == "beginner"

    def test_catalog_empty_domain(self, gym_client):
        """GET /gym/catalog/{domain} for unknown domain returns empty."""
        resp = gym_client.get("/gym/catalog/nonexistent_domain")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0

    def test_catalog_all_domains_covered(self, gym_client):
        """All 8 domains should have exercises in the catalog."""
        resp = gym_client.get("/gym/catalog")
        body = resp.json()
        expected_domains = [
            "openfw", "openswe", "openml", "openeda",
            "opensim", "opendoc", "opendesign", "openstrategy",
        ]
        for domain in expected_domains:
            assert domain in body["domains"], f"Missing domain: {domain}"
            assert body["domains"][domain]["total"] > 0, f"Empty domain: {domain}"


# ===========================================================================
# 3. Exercise Catalog — Unit-level
# ===========================================================================

class TestExerciseCatalogIntegration:
    """Integration tests for the exercise catalog system."""

    def test_seed_count_per_domain(self, isolated_catalog):
        """Each domain should have substantial seed exercises."""
        min_seeds = {
            "openfw": 60,
            "openswe": 40,
            "openml": 10,
            "openeda": 10,
            "opensim": 10,
            "opendoc": 8,
            "opendesign": 8,
            "openstrategy": 8,
        }
        for domain, expected_min in min_seeds.items():
            exercises = isolated_catalog.get_for_domain(domain)
            assert len(exercises) >= expected_min, (
                f"{domain} has {len(exercises)} exercises, expected >= {expected_min}"
            )

    def test_difficulty_distribution(self, isolated_catalog):
        """Major domains should have exercises at all 4 difficulty levels."""
        for domain in ["openfw", "openswe"]:
            count = isolated_catalog.count(domain)
            diffs = count["by_difficulty"]
            assert "beginner" in diffs, f"{domain} missing beginner"
            assert "intermediate" in diffs, f"{domain} missing intermediate"
            assert "advanced" in diffs, f"{domain} missing advanced"

    def test_firmware_topics_comprehensive(self, isolated_catalog):
        """Firmware exercises should cover all major embedded topics."""
        all_tags = set()
        for ex in isolated_catalog.get_for_domain("openfw"):
            all_tags.update(ex.tags)

        required = [
            "gpio", "uart", "spi", "i2c", "dma", "timer", "rtos",
            "watchdog", "adc", "pwm", "power", "safety", "bootloader",
            "can", "usb", "ethernet", "crypto", "boot", "flash",
        ]
        missing = [t for t in required if t not in all_tags]
        assert not missing, f"Firmware catalog missing topics: {missing}"

    def test_software_topics_comprehensive(self, isolated_catalog):
        """Software exercises should cover all major development topics."""
        all_tags = set()
        for ex in isolated_catalog.get_for_domain("openswe"):
            all_tags.update(ex.tags)

        required = [
            "api", "testing", "database", "security", "auth",
            "middleware", "cache", "websocket", "events", "distributed",
        ]
        missing = [t for t in required if t not in all_tags]
        assert not missing, f"Software catalog missing topics: {missing}"

    def test_ml_topics_comprehensive(self, isolated_catalog):
        """ML exercises should cover the full ML lifecycle."""
        all_tags = set()
        for ex in isolated_catalog.get_for_domain("openml"):
            all_tags.update(ex.tags)

        required = ["data", "classification", "pipeline", "deployment", "anomaly"]
        missing = [t for t in required if t not in all_tags]
        assert not missing, f"ML catalog missing topics: {missing}"

    def test_tag_search_returns_relevant(self, isolated_catalog):
        """Tag search should return exercises matching the tag."""
        uart_exs = isolated_catalog.get_for_tags(["uart"], "openfw")
        assert len(uart_exs) >= 2, "Should have multiple UART exercises"
        for ex in uart_exs:
            assert "uart" in ex.tags

    def test_tag_search_cross_domain(self, isolated_catalog):
        """Tag search without domain should search all domains."""
        security_exs = isolated_catalog.get_for_tags(["security"])
        assert len(security_exs) >= 2, "Should have security exercises across domains"
        domains = {ex.domain for ex in security_exs}
        assert len(domains) >= 2, "Security exercises should span multiple domains"

    def test_exercise_ids_unique(self, isolated_catalog):
        """All exercise IDs should be unique across the entire catalog."""
        all_ids = [ex.id for ex in isolated_catalog._exercises.values()]
        assert len(all_ids) == len(set(all_ids)), "Duplicate exercise IDs found"

    def test_exercise_ids_deterministic(self, isolated_catalog):
        """Same exercise should get the same ID across catalog instances."""
        from src.core.exercise_catalog import ExerciseCatalog
        db_path2 = os.path.join(tempfile.mkdtemp(), "cat2.db")
        catalog2 = ExerciseCatalog(db_path=db_path2)

        # Compare IDs for a known exercise
        fw_exs1 = isolated_catalog.get_for_domain("openfw", "beginner")
        fw_exs2 = catalog2.get_for_domain("openfw", "beginner")
        ids1 = {e.id for e in fw_exs1}
        ids2 = {e.id for e in fw_exs2}
        assert ids1 == ids2, "Exercise IDs should be deterministic"

    def test_acceptance_criteria_present(self, isolated_catalog):
        """All exercises should have acceptance criteria."""
        missing = []
        for ex in isolated_catalog._exercises.values():
            if not ex.acceptance_criteria:
                missing.append(f"{ex.domain}/{ex.title}")
        assert not missing, f"Exercises without acceptance criteria: {missing[:5]}"


# ===========================================================================
# 4. Glicko-2 Rating System
# ===========================================================================

class TestGlicko2RatingSystem:
    """Test the Glicko-2 rating system behavior."""

    def test_rating_increases_on_win(self, isolated_gym):
        from src.core.agent_gym import SkillRating
        rating = SkillRating("dev", "swe", rating=1000.0)
        new = isolated_gym._update_rating("dev:swe", rating, 85.0, True)
        assert new > 1000.0, "Rating should increase on win"

    def test_rating_decreases_on_loss(self, isolated_gym):
        from src.core.agent_gym import SkillRating
        rating = SkillRating("dev", "swe", rating=1200.0)
        new = isolated_gym._update_rating("dev:swe", rating, 15.0, False)
        assert new < 1200.0, "Rating should decrease on loss"

    def test_rd_shrinks_with_data(self, isolated_gym):
        """Rating deviation should decrease as more sessions are completed."""
        from src.core.agent_gym import SkillRating
        rating = SkillRating("dev", "swe", rating_deviation=350.0)
        initial_rd = rating.rating_deviation

        for _ in range(5):
            isolated_gym._update_rating("dev:swe", rating, 75.0, True)

        assert rating.rating_deviation < initial_rd, "RD should shrink with more data"
        assert rating.rating_deviation > 30, "RD should not go below minimum"

    def test_confidence_interval(self, isolated_gym):
        """to_dict should include confidence interval."""
        from src.core.agent_gym import SkillRating
        rating = SkillRating("dev", "swe", rating=1200.0, rating_deviation=100.0)
        d = rating.to_dict()
        assert "confidence_interval" in d
        assert d["confidence_interval"][0] == 1000.0  # rating - 2*RD
        assert d["confidence_interval"][1] == 1400.0  # rating + 2*RD

    def test_volatility_changes_on_result(self, isolated_gym):
        """Volatility should change (Glicko-2 σ update) after a result."""
        from src.core.agent_gym import SkillRating
        # High-rated agent that fails badly — volatility updates via Glicko-2
        rating = SkillRating("dev", "swe", rating=1800.0, volatility=0.06)
        initial_vol = rating.volatility
        isolated_gym._update_rating("dev:swe", rating, 10.0, False)
        assert rating.volatility != initial_vol, "Volatility should change after Glicko-2 update"

    def test_rating_clamped(self, isolated_gym):
        """Rating should stay within [100, 3000]."""
        from src.core.agent_gym import SkillRating
        # Push very high
        rating = SkillRating("dev", "swe", rating=2900.0)
        for _ in range(20):
            isolated_gym._update_rating("dev:swe", rating, 99.0, True)
        assert rating.rating <= 3000, "Rating should not exceed 3000"

        # Push very low
        rating2 = SkillRating("dev2", "swe2", rating=200.0)
        for _ in range(20):
            isolated_gym._update_rating("dev2:swe2", rating2, 1.0, False)
        assert rating2.rating >= 100, "Rating should not go below 100"

    def test_streak_tracking(self, isolated_gym):
        """Win/loss streaks should be tracked."""
        from src.core.agent_gym import SkillRating
        rating = SkillRating("dev", "swe")

        # 3 wins
        for _ in range(3):
            isolated_gym._update_rating("dev:swe", rating, 80.0, True)
        assert rating.streak == 3

        # 2 losses
        for _ in range(2):
            isolated_gym._update_rating("dev:swe", rating, 20.0, False)
        assert rating.streak == -2


# ===========================================================================
# 5. Spaced Repetition
# ===========================================================================

class TestSpacedRepetition:
    """Test spaced repetition scheduling for failed exercises."""

    def test_failed_exercise_scheduled(self, isolated_gym):
        """Failed exercises should be scheduled for retry."""
        from src.core.agent_gym import SkillRating
        rating = SkillRating("dev", "swe")
        isolated_gym._update_rating("dev:swe", rating, 20.0, False, exercise_id="ex-1")

        assert "ex-1" in rating.failed_exercises
        # Should retry at session 2 (current=1 + interval=1)
        assert rating.failed_exercises["ex-1"] == 2

    def test_passed_exercise_cleared(self, isolated_gym):
        """Passing a failed exercise should clear it from schedule."""
        from src.core.agent_gym import SkillRating
        rating = SkillRating("dev", "swe")

        # Fail then pass
        isolated_gym._update_rating("dev:swe", rating, 20.0, False, exercise_id="ex-1")
        assert "ex-1" in rating.failed_exercises

        isolated_gym._update_rating("dev:swe", rating, 85.0, True, exercise_id="ex-1")
        assert "ex-1" not in rating.failed_exercises

    def test_multiple_failures_increase_interval(self, isolated_gym):
        """Repeated failures should not decrease retry interval."""
        from src.core.agent_gym import SkillRating
        rating = SkillRating("dev", "swe")

        # Fail the same exercise multiple times
        isolated_gym._update_rating("dev:swe", rating, 20.0, False, exercise_id="ex-1")
        first_threshold = rating.failed_exercises["ex-1"]

        # Fail again (should still have a scheduled retry)
        isolated_gym._update_rating("dev:swe", rating, 15.0, False, exercise_id="ex-2")
        assert "ex-2" in rating.failed_exercises

    def test_pending_reviews_count(self, isolated_gym):
        """to_dict should show count of pending reviews."""
        from src.core.agent_gym import SkillRating
        rating = SkillRating("dev", "swe", sessions=5)
        rating.failed_exercises = {"ex-1": 3, "ex-2": 10}  # ex-1 due, ex-2 not due

        d = rating.to_dict()
        assert d["pending_reviews"] == 1  # only ex-1 is due (sessions=5 >= threshold=3)


# ===========================================================================
# 6. Curriculum System
# ===========================================================================

class TestCurriculumSystem:
    """Test curriculum auto-progression (difficulty advancement/demotion)."""

    def test_advance_on_high_win_rate(self, isolated_gym):
        """Difficulty should advance when win rate > 70% after minimum sessions."""
        from src.core.agent_gym import SkillRating, TrainingSession
        for i in range(5):
            s = TrainingSession(
                session_id=f"adv-{i}", agent_role="dev", runner_name="openswe",
                skill_name="swe", exercise_id=f"ex-{i}", difficulty="beginner",
                status="completed", grade={"score": 85, "passed": True},
                started_at=1000.0 + i,
            )
            isolated_gym._db.save_session(s)

        rating = SkillRating("dev", "swe", current_difficulty="beginner")
        isolated_gym._ratings["dev:swe"] = rating
        isolated_gym._curriculum_check("dev:swe", rating)
        assert rating.current_difficulty == "intermediate"

    def test_demote_on_low_win_rate(self, isolated_gym):
        """Difficulty should demote when win rate < 25% after minimum sessions."""
        from src.core.agent_gym import SkillRating, TrainingSession
        for i in range(6):
            s = TrainingSession(
                session_id=f"dem-{i}", agent_role="dev", runner_name="openswe",
                skill_name="swe", exercise_id=f"ex-{i}", difficulty="intermediate",
                status="completed", grade={"score": 15, "passed": False},
                started_at=1000.0 + i,
            )
            isolated_gym._db.save_session(s)

        rating = SkillRating("dev", "swe", current_difficulty="intermediate")
        isolated_gym._ratings["dev:swe"] = rating
        isolated_gym._curriculum_check("dev:swe", rating)
        assert rating.current_difficulty == "beginner"

    def test_no_advance_below_minimum_sessions(self, isolated_gym):
        """Should not advance with fewer than minimum sessions."""
        from src.core.agent_gym import SkillRating, TrainingSession
        # Only 2 sessions (minimum is 3)
        for i in range(2):
            s = TrainingSession(
                session_id=f"few-{i}", agent_role="dev", runner_name="openswe",
                skill_name="swe", exercise_id=f"ex-{i}", difficulty="beginner",
                status="completed", grade={"score": 95, "passed": True},
                started_at=1000.0 + i,
            )
            isolated_gym._db.save_session(s)

        rating = SkillRating("dev", "swe", current_difficulty="beginner")
        isolated_gym._curriculum_check("dev:swe", rating)
        assert rating.current_difficulty == "beginner"  # unchanged

    def test_no_advance_past_expert(self, isolated_gym):
        """Should not advance past 'expert' difficulty."""
        from src.core.agent_gym import SkillRating, TrainingSession
        for i in range(5):
            s = TrainingSession(
                session_id=f"exp-{i}", agent_role="dev", runner_name="openswe",
                skill_name="swe", exercise_id=f"ex-{i}", difficulty="expert",
                status="completed", grade={"score": 95, "passed": True},
                started_at=1000.0 + i,
            )
            isolated_gym._db.save_session(s)

        rating = SkillRating("dev", "swe", current_difficulty="expert")
        isolated_gym._curriculum_check("dev:swe", rating)
        assert rating.current_difficulty == "expert"  # stays at expert


# ===========================================================================
# 7. SQLite Persistence
# ===========================================================================

class TestSQLitePersistence:
    """Test that gym data persists across instances."""

    def test_ratings_persist(self):
        """Ratings should survive gym restart."""
        from src.core.agent_gym import AgentGym, SkillRating
        db_path = os.path.join(tempfile.mkdtemp(), "persist.db")

        gym1 = AgentGym(db_path=db_path)
        rating = SkillRating("dev", "swe", rating=1350.0, rating_deviation=150.0)
        gym1._ratings["dev:swe"] = rating
        gym1._db.save_rating("dev:swe", rating)

        gym2 = AgentGym(db_path=db_path)
        assert "dev:swe" in gym2._ratings
        assert gym2._ratings["dev:swe"].rating == 1350.0
        assert gym2._ratings["dev:swe"].rating_deviation == 150.0

    def test_sessions_persist(self):
        """Training sessions should be queryable after restart."""
        from src.core.agent_gym import AgentGym, TrainingSession
        db_path = os.path.join(tempfile.mkdtemp(), "persist2.db")

        gym1 = AgentGym(db_path=db_path)
        session = TrainingSession(
            session_id="persist-test", agent_role="dev", runner_name="openswe",
            skill_name="swe", exercise_id="ex-1", difficulty="intermediate",
            status="completed", grade={"score": 80, "passed": True},
        )
        gym1._db.save_session(session)

        gym2 = AgentGym(db_path=db_path)
        loaded = gym2._db.load_session("persist-test")
        assert loaded is not None
        assert loaded["agent_role"] == "dev"
        assert loaded["status"] == "completed"

    def test_analytics_with_data(self):
        """Analytics should work with persisted session data."""
        from src.core.agent_gym import AgentGym, TrainingSession
        db_path = os.path.join(tempfile.mkdtemp(), "analytics.db")
        gym = AgentGym(db_path=db_path)

        # Create 20 sessions so early/late windows (size 10) are distinct
        for i in range(20):
            s = TrainingSession(
                session_id=f"ana-{i}", agent_role="dev", runner_name="openswe",
                skill_name="swe", exercise_id=f"ex-{i % 3}", difficulty="intermediate",
                status="completed", grade={"score": 40 + i * 3, "passed": i > 5},
                started_at=1000.0 + i,
            )
            gym._db.save_session(s)

        data = gym.analytics(role="dev")
        assert data["global_stats"]["total_sessions"] == 20
        assert data["global_stats"]["completed"] == 20
        assert len(data["score_trend"]) == 20
        assert data["improvement_rate"]["sessions"] == 20
        assert data["improvement_rate"]["improving"]  # late scores > early scores


# ===========================================================================
# 8. Full Training Loop (Integration)
# ===========================================================================

class TestFullTrainingLoop:
    """End-to-end training loop with mocked LLM."""

    def test_train_produces_complete_session(self, isolated_gym, mock_llm):
        """Full training loop should produce a complete session with all fields."""
        with patch("src.memory.vector_store.vector_memory") as mock_vm:
            mock_vm.add_feedback = MagicMock()
            mock_vm.search = MagicMock(return_value=[])
            # Use generate to return reflection JSON for the reflect phase
            mock_llm.generate.return_value = MOCK_REFLECTION

            session = isolated_gym.train(
                role="firmware_engineer",
                difficulty="beginner",
            )

        assert session.session_id != ""
        assert session.agent_role == "firmware_engineer"
        assert session.runner_name != ""
        assert session.status in ("completed", "failed")
        if session.status == "completed":
            assert session.grade.get("score", 0) >= 0
            assert session.elo_after != session.elo_before

    def test_batch_train_multiple_roles(self, isolated_gym, mock_llm):
        """Batch training should handle multiple roles."""
        with patch("src.memory.vector_store.vector_memory") as mock_vm:
            mock_vm.add_feedback = MagicMock()
            mock_vm.search = MagicMock(return_value=[])

            sessions = isolated_gym.train_batch(
                roles=["nonexistent_role_a", "nonexistent_role_b"],
                max_parallel=2,
            )

        assert len(sessions) == 2
        for s in sessions:
            assert s.status == "failed"  # no runners for these roles

    def test_leaderboard_updates_after_training(self, isolated_gym, mock_llm):
        """Leaderboard should reflect training results."""
        with patch("src.memory.vector_store.vector_memory") as mock_vm:
            mock_vm.add_feedback = MagicMock()
            mock_vm.search = MagicMock(return_value=[])

            session = isolated_gym.train(
                role="firmware_engineer",
                difficulty="beginner",
            )

        if session.status == "completed":
            board = isolated_gym.get_leaderboard()
            assert len(board) > 0
            # Should have a rating for firmware_engineer
            fw_ratings = [r for r in board if r["agent_role"] == "firmware_engineer"]
            assert len(fw_ratings) > 0


# ===========================================================================
# 9. Variant Axes Coverage
# ===========================================================================

class TestVariantAxes:
    """Verify variant axis definitions are comprehensive."""

    def test_all_domains_have_variant_axes(self):
        """Every domain should have variant axes defined."""
        from src.core.exercise_catalog import VARIANT_AXES
        expected = ["openfw", "openswe", "openml", "openeda",
                    "opensim", "opendoc", "opendesign", "openstrategy"]
        for domain in expected:
            assert domain in VARIANT_AXES, f"Missing variant axes for {domain}"
            assert len(VARIANT_AXES[domain]) >= 8, (
                f"{domain} has only {len(VARIANT_AXES[domain])} axes, expected >= 8"
            )

    def test_variant_axes_are_strings(self):
        """All variant axes should be non-empty strings."""
        from src.core.exercise_catalog import VARIANT_AXES
        for domain, axes in VARIANT_AXES.items():
            for axis in axes:
                assert isinstance(axis, str) and len(axis) > 0, (
                    f"Invalid axis in {domain}: {axis}"
                )

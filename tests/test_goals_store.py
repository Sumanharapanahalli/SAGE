"""Tests for goals/OKR persistence store."""
import pytest

from src.stores.goals_store import GoalsStore


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "test_goals.db")
    return GoalsStore(db_path)


class TestGoalsStore:
    def test_create_objective(self, store: GoalsStore):
        obj = store.create(
            user_id="user1",
            solution="default",
            title="Ship v1",
            quarter="Q1-2025",
            status="on_track",
            owner="AI Team",
            key_results=[
                {"title": "Pass all tests", "current": 0, "target": 100, "unit": "tests"},
            ],
        )
        assert obj["id"]
        assert obj["title"] == "Ship v1"
        assert obj["quarter"] == "Q1-2025"
        assert len(obj["key_results"]) == 1
        assert obj["key_results"][0]["title"] == "Pass all tests"

    def test_list_objectives(self, store: GoalsStore):
        store.create("user1", "default", "Obj A", "Q1-2025", "on_track", "Team", [])
        store.create("user1", "default", "Obj B", "Q1-2025", "at_risk", "Team", [])
        store.create("user2", "default", "Obj C", "Q1-2025", "on_track", "Team", [])

        results = store.list("user1", "default")
        assert len(results) == 2

    def test_list_by_quarter(self, store: GoalsStore):
        store.create("user1", "default", "Q1 Obj", "Q1-2025", "on_track", "Team", [])
        store.create("user1", "default", "Q2 Obj", "Q2-2025", "on_track", "Team", [])

        results = store.list("user1", "default", quarter="Q1-2025")
        assert len(results) == 1
        assert results[0]["title"] == "Q1 Obj"

    def test_get_objective(self, store: GoalsStore):
        obj = store.create("user1", "default", "Test", "Q1-2025", "on_track", "Team", [])
        fetched = store.get(obj["id"])
        assert fetched is not None
        assert fetched["title"] == "Test"

    def test_update_objective(self, store: GoalsStore):
        obj = store.create("user1", "default", "Old Title", "Q1-2025", "on_track", "Team", [])
        updated = store.update(obj["id"], title="New Title", status="at_risk")
        assert updated["title"] == "New Title"
        assert updated["status"] == "at_risk"

    def test_update_key_results(self, store: GoalsStore):
        krs = [{"title": "KR1", "current": 0, "target": 10, "unit": "tasks"}]
        obj = store.create("user1", "default", "Test", "Q1-2025", "on_track", "Team", krs)
        updated_krs = [{"title": "KR1", "current": 5, "target": 10, "unit": "tasks"}]
        updated = store.update(obj["id"], key_results=updated_krs)
        assert updated["key_results"][0]["current"] == 5

    def test_delete_objective(self, store: GoalsStore):
        obj = store.create("user1", "default", "Test", "Q1-2025", "on_track", "Team", [])
        assert store.delete(obj["id"]) is True
        assert store.get(obj["id"]) is None

    def test_delete_nonexistent(self, store: GoalsStore):
        assert store.delete("nonexistent") is False

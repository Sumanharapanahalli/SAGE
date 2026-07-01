from pathlib import Path

import pytest

from handlers import goals
from rpc import RpcError


@pytest.fixture
def store(tmp_path: Path):
    from src.stores.goals_store import GoalsStore

    return GoalsStore(str(tmp_path / "goals.db"))


@pytest.fixture(autouse=True)
def inject(store):
    goals._store = store
    yield
    goals._store = None


# ---------- goals.create ----------


def test_create_goal_returns_row():
    result = goals.create({
        "title": "Ship desktop parity",
        "quarter": "2026-Q3",
        "owner": "harish",
        "status": "on_track",
        "key_results": [{"text": "Ship Goals page", "done": False}],
    })
    assert result["title"] == "Ship desktop parity"
    assert result["quarter"] == "2026-Q3"
    assert result["owner"] == "harish"
    assert result["status"] == "on_track"
    assert result["key_results"] == [{"text": "Ship Goals page", "done": False}]
    assert result["user_id"] == "desktop-operator"
    assert result["solution"] == ""
    assert len(result["id"]) == 36


def test_create_goal_defaults_status_owner_key_results():
    result = goals.create({"title": "t", "quarter": "2026-Q3"})
    assert result["status"] == "on_track"
    assert result["owner"] == ""
    assert result["key_results"] == []


def test_create_goal_honours_explicit_user_id_and_solution():
    result = goals.create({
        "title": "t", "quarter": "2026-Q3",
        "user_id": "alice", "solution": "medtech",
    })
    assert result["user_id"] == "alice"
    assert result["solution"] == "medtech"


def test_create_goal_missing_title_raises_invalid_params():
    with pytest.raises(RpcError) as exc:
        goals.create({"quarter": "2026-Q3"})
    assert exc.value.code == -32602


def test_create_goal_missing_quarter_raises_invalid_params():
    with pytest.raises(RpcError) as exc:
        goals.create({"title": "t"})
    assert exc.value.code == -32602


# ---------- goals.list ----------


def test_list_goals_empty_returns_empty_list():
    assert goals.list({}) == []


def test_create_then_list_round_trip_with_default_operator():
    """The defaults create() and list() fall back to (user_id, solution)
    MUST agree — GoalsStore.list() is an exact-equality WHERE clause, not
    an optional filter, so a mismatch here silently returns []."""
    created = goals.create({"title": "Round trip", "quarter": "2026-Q3"})
    result = goals.list({})
    assert [g["id"] for g in result] == [created["id"]]


def test_list_goals_filters_by_quarter():
    goals.create({"title": "a", "quarter": "2026-Q3"})
    goals.create({"title": "b", "quarter": "2026-Q4"})
    result = goals.list({"quarter": "2026-Q4"})
    assert len(result) == 1
    assert result[0]["title"] == "b"


def test_list_goals_filters_by_explicit_user_id_and_solution():
    goals.create({"title": "a", "quarter": "2026-Q3", "user_id": "alice", "solution": "medtech"})
    goals.create({"title": "b", "quarter": "2026-Q3"})  # defaults
    result = goals.list({"user_id": "alice", "solution": "medtech"})
    assert len(result) == 1
    assert result[0]["title"] == "a"
    result_default = goals.list({})
    assert len(result_default) == 1
    assert result_default[0]["title"] == "b"


def test_store_unavailable_raises_sage_import_error():
    goals._store = None
    with pytest.raises(RpcError) as exc:
        goals.list({})
    assert exc.value.code == -32010


# ---------- goals.get ----------


def test_get_goal_found():
    created = goals.create({"title": "t", "quarter": "2026-Q3"})
    result = goals.get({"goal_id": created["id"]})
    assert result["id"] == created["id"]


def test_get_goal_not_found_raises_invalid_params():
    with pytest.raises(RpcError) as exc:
        goals.get({"goal_id": "nope"})
    assert exc.value.code == -32602


def test_get_goal_missing_id_raises_invalid_params():
    with pytest.raises(RpcError) as exc:
        goals.get({})
    assert exc.value.code == -32602


# ---------- goals.update ----------


def test_update_goal_partial_fields_only():
    created = goals.create({
        "title": "t", "quarter": "2026-Q3", "owner": "harish", "status": "on_track",
    })
    updated = goals.update({"goal_id": created["id"], "status": "at_risk"})
    assert updated["status"] == "at_risk"
    # Untouched fields survive the partial update.
    assert updated["title"] == "t"
    assert updated["owner"] == "harish"


def test_update_goal_not_found_raises_invalid_params():
    with pytest.raises(RpcError) as exc:
        goals.update({"goal_id": "nope", "status": "at_risk"})
    assert exc.value.code == -32602


def test_update_goal_missing_id_raises_invalid_params():
    with pytest.raises(RpcError) as exc:
        goals.update({"status": "at_risk"})
    assert exc.value.code == -32602


# ---------- goals.delete ----------


def test_delete_goal_found():
    created = goals.create({"title": "t", "quarter": "2026-Q3"})
    result = goals.delete({"goal_id": created["id"]})
    assert result == {"deleted": True}
    assert goals._store.get(created["id"]) is None


def test_delete_goal_not_found_raises_invalid_params():
    with pytest.raises(RpcError) as exc:
        goals.delete({"goal_id": "nope"})
    assert exc.value.code == -32602


def test_delete_goal_missing_id_raises_invalid_params():
    with pytest.raises(RpcError) as exc:
        goals.delete({})
    assert exc.value.code == -32602

"""Tests for the durable queue reader (queue.list_all / queue.subtasks).

Uses a REAL TaskQueue against a temp db_path so the schema under test is the
framework's, not a hand-rolled copy — if queue_manager migrates a column,
these tests see it.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from handlers import queuedb
from rpc import RpcError


@pytest.fixture
def dbs(tmp_path, monkeypatch):
    """A real queue.db + a feature_requests audit_log.db, wired like app.py."""
    from src.core.feature_request_store import FeatureRequestStore
    from src.core.queue_manager import TaskQueue

    queue_db = tmp_path / "queue.db"
    feature_db = tmp_path / "audit_log.db"

    q = TaskQueue(db_path=str(queue_db))
    FeatureRequestStore(str(feature_db)).init_schema()

    monkeypatch.setattr(queuedb, "_db_path", str(queue_db))
    monkeypatch.setattr(queuedb, "_feature_db_path", str(feature_db))
    return {"queue": q, "queue_db": str(queue_db), "feature_db": str(feature_db)}


def _set_status(db_path: str, task_id: str, status: str, error: str | None = None):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE task_queue SET status=?, error=? WHERE task_id=?",
        (status, error, task_id),
    )
    conn.commit()
    conn.close()


# ── wiring ────────────────────────────────────────────────────────────────


def test_list_all_errors_when_not_wired(monkeypatch):
    monkeypatch.setattr(queuedb, "_db_path", None)
    with pytest.raises(RpcError):
        queuedb.list_all({})


def test_list_all_on_a_never_written_queue_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(queuedb, "_db_path", str(tmp_path / "absent.db"))
    monkeypatch.setattr(queuedb, "_feature_db_path", None)
    out = queuedb.list_all({})
    assert out["tasks"] == []
    assert out["counts"]["total"] == 0


# ── list_all ──────────────────────────────────────────────────────────────


def test_list_all_returns_full_payload_source_and_error(dbs):
    q = dbs["queue"]
    tid = q.submit("ANALYZE_LOG", {"log_entry": "boom"}, source="solution")
    _set_status(dbs["queue_db"], tid, "failed", error="LLM timeout")

    out = queuedb.list_all({})
    task = next(t for t in out["tasks"] if t["task_id"] == tid)
    assert task["payload"] == {"log_entry": "boom"}  # decoded, not raw JSON text
    assert task["source"] == "solution"
    assert task["status"] == "failed"
    assert task["error"] == "LLM timeout"
    assert "plan_trace_id" in task


def test_list_all_returns_completed_history_the_in_memory_handler_cannot(dbs):
    """The whole point of this handler: history survives.

    handlers/queue.py reads TaskQueue._tasks, which only rehydrates
    pending/in_progress rows — a completed task is invisible there.
    """
    q = dbs["queue"]
    tid = q.submit("DEVELOP", {"spec": "x"})
    _set_status(dbs["queue_db"], tid, "completed")

    from src.core.queue_manager import TaskQueue

    fresh = TaskQueue(db_path=dbs["queue_db"])  # simulates a restart
    assert not [t for t in fresh.get_all_tasks() if t["task_id"] == tid]

    out = queuedb.list_all({})
    assert any(t["task_id"] == tid for t in out["tasks"])


def test_list_all_filters_by_status(dbs):
    q = dbs["queue"]
    pending = q.submit("ANALYZE_LOG", {})
    done = q.submit("DEVELOP", {})
    _set_status(dbs["queue_db"], done, "completed")

    out = queuedb.list_all({"status": "completed"})
    ids = [t["task_id"] for t in out["tasks"]]
    assert ids == [done]
    assert pending not in ids


def test_list_all_filters_by_source(dbs):
    q = dbs["queue"]
    sage = q.submit("PLAN", {}, source="sage")
    q.submit("PLAN", {}, source="solution")

    out = queuedb.list_all({"source": "sage"})
    assert [t["task_id"] for t in out["tasks"]] == [sage]


def test_counts_span_the_whole_table_even_when_filtered(dbs):
    q = dbs["queue"]
    q.submit("ANALYZE_LOG", {})
    done = q.submit("DEVELOP", {})
    failed = q.submit("REVIEW", {})
    _set_status(dbs["queue_db"], done, "completed")
    _set_status(dbs["queue_db"], failed, "failed")

    out = queuedb.list_all({"status": "failed"})
    assert len(out["tasks"]) == 1
    assert out["counts"] == {
        "pending": 1,
        "in_progress": 0,
        "completed": 1,
        "failed": 1,
        "blocked": 0,
        "cancelled": 0,
        "total": 3,
    }


def test_list_all_joins_feature_title_and_scope(dbs):
    from src.core.feature_request_store import FeatureRequestStore

    store = FeatureRequestStore(dbs["feature_db"])
    fr = store.submit(title="Add voice pack", description="d", scope="sage")
    fr_id = fr.id
    trace = "trace-abc"
    conn = sqlite3.connect(dbs["feature_db"])
    conn.execute(
        "UPDATE feature_requests SET plan_trace_id=? WHERE id=?", (trace, fr_id)
    )
    conn.commit()
    conn.close()

    tid = dbs["queue"].submit("DEVELOP", {}, plan_trace_id=trace)

    out = queuedb.list_all({})
    task = next(t for t in out["tasks"] if t["task_id"] == tid)
    assert task["feature_title"] == "Add voice pack"
    assert task["feature_scope"] == "sage"


def test_list_all_leaves_feature_fields_null_without_a_plan_trace(dbs):
    tid = dbs["queue"].submit("ANALYZE_LOG", {})
    out = queuedb.list_all({})
    task = next(t for t in out["tasks"] if t["task_id"] == tid)
    assert task["feature_title"] is None
    assert task["feature_scope"] is None


def test_list_all_survives_a_missing_feature_db(dbs, monkeypatch, tmp_path):
    monkeypatch.setattr(queuedb, "_feature_db_path", str(tmp_path / "nope.db"))
    dbs["queue"].submit("ANALYZE_LOG", {})
    out = queuedb.list_all({})
    assert out["tasks"][0]["feature_title"] is None
    # ATTACH must not fabricate the store.
    assert not (tmp_path / "nope.db").exists()


def test_list_all_honours_limit_and_rejects_a_bad_one(dbs):
    for _ in range(3):
        dbs["queue"].submit("ANALYZE_LOG", {})
    assert len(queuedb.list_all({"limit": 2})["tasks"]) == 2
    with pytest.raises(RpcError):
        queuedb.list_all({"limit": 0})
    with pytest.raises(RpcError):
        queuedb.list_all({"limit": "50"})


def test_list_all_decodes_a_corrupt_payload_to_an_empty_object(dbs):
    tid = dbs["queue"].submit("ANALYZE_LOG", {})
    conn = sqlite3.connect(dbs["queue_db"])
    conn.execute("UPDATE task_queue SET payload='{not json' WHERE task_id=?", (tid,))
    conn.commit()
    conn.close()
    out = queuedb.list_all({})
    assert out["tasks"][0]["payload"] == {}


# ── subtasks ──────────────────────────────────────────────────────────────


def test_subtasks_returns_children_by_parent_task_id(dbs):
    q = dbs["queue"]
    parent = q.submit("PLAN", {})
    child = q.submit(
        "DEVELOP",
        {},
        metadata={"parent_task_id": parent, "wave": 1},
    )
    q.submit("DEVELOP", {})  # unrelated

    out = queuedb.subtasks({"task_id": parent})
    assert out["task_id"] == parent
    assert len(out["subtasks"]) == 1
    st = out["subtasks"][0]
    assert st["task_id"] == child
    assert st["wave"] == 1
    assert st["task_type"] == "DEVELOP"


def test_subtasks_finds_children_of_a_completed_parent(dbs):
    q = dbs["queue"]
    parent = q.submit("PLAN", {})
    child = q.submit("DEVELOP", {}, metadata={"parent_task_id": parent})
    _set_status(dbs["queue_db"], parent, "completed")
    _set_status(dbs["queue_db"], child, "completed", error=None)

    out = queuedb.subtasks({"task_id": parent})
    assert [s["task_id"] for s in out["subtasks"]] == [child]


def test_subtasks_returns_empty_for_a_leaf_task(dbs):
    tid = dbs["queue"].submit("ANALYZE_LOG", {})
    assert queuedb.subtasks({"task_id": tid})["subtasks"] == []


def test_subtasks_requires_a_task_id(dbs):
    with pytest.raises(RpcError):
        queuedb.subtasks({})
    with pytest.raises(RpcError):
        queuedb.subtasks({"task_id": ""})


def test_subtask_depends_on_round_trips(dbs):
    q = dbs["queue"]
    parent = q.submit("PLAN", {})
    first = q.submit("DEVELOP", {}, metadata={"parent_task_id": parent, "wave": 0})
    q.submit(
        "TEST",
        {},
        depends_on=[first],
        metadata={"parent_task_id": parent, "wave": 1},
    )
    out = queuedb.subtasks({"task_id": parent})
    second = [s for s in out["subtasks"] if s["task_type"] == "TEST"][0]
    assert second["depends_on"] == [first]
    assert json.dumps(out)  # JSON-transportable

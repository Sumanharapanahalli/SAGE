"""Tests for the activity handler (the live triage feed).

The point of this handler over audit.list is that "show me everything that
FAILED" must work — errors are matched across event_type, action_type, the
status column AND the free text of output_content. These tests pin that.
"""
from __future__ import annotations

import json
import sqlite3
import uuid

import pytest

from handlers import activity
from rpc import RpcError

SCHEMA = """
CREATE TABLE compliance_audit_log (
    id TEXT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    trace_id TEXT,
    event_type TEXT,
    status TEXT DEFAULT 'OK',
    actor TEXT NOT NULL,
    action_type TEXT NOT NULL,
    input_context TEXT,
    output_content TEXT,
    metadata JSON,
    verification_signature TEXT,
    approved_by TEXT,
    approver_role TEXT,
    approver_email TEXT,
    approver_provider TEXT
)
"""


class _FakeLogger:
    def __init__(self, db_path: str):
        self.db_path = db_path


def _insert(db_path, **kw):
    row = {
        "id": kw.get("id", str(uuid.uuid4())),
        "timestamp": kw.get("timestamp", "2026-07-11T10:00:00"),
        "trace_id": kw.get("trace_id"),
        "event_type": kw.get("event_type"),
        "status": kw.get("status", "OK"),
        "actor": kw.get("actor", "AI_Agent"),
        "action_type": kw.get("action_type", "ANALYSIS"),
        "input_context": kw.get("input_context"),
        "output_content": kw.get("output_content"),
        "metadata": json.dumps(kw.get("metadata", {})),
    }
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO compliance_audit_log
           (id, timestamp, trace_id, event_type, status, actor, action_type,
            input_context, output_content, metadata)
           VALUES (:id, :timestamp, :trace_id, :event_type, :status, :actor,
                   :action_type, :input_context, :output_content, :metadata)""",
        row,
    )
    conn.commit()
    conn.close()
    return row["id"]


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "audit_log.db")
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    monkeypatch.setattr(activity, "_logger", _FakeLogger(path))
    return path


# --- wiring ---------------------------------------------------------------

def test_list_requires_a_wired_logger(monkeypatch):
    monkeypatch.setattr(activity, "_logger", None)
    with pytest.raises(RpcError):
        activity.list_events({})


# --- shape ----------------------------------------------------------------

def test_list_returns_full_rows_not_just_four_columns(db):
    _insert(
        db,
        event_type="TASK_COMPLETED",
        action_type="ANALYSIS",
        output_content="Analysis finished cleanly",
        metadata={"task_type": "log_analysis", "trace_id": "tr-1"},
    )
    out = activity.list_events({})
    assert out["total"] == 1
    e = out["events"][0]
    # audit.list's table only surfaced timestamp/actor/action_type/trace —
    # the feed needs the rest to build a human-readable label.
    assert e["event_type"] == "TASK_COMPLETED"
    assert e["output_content"] == "Analysis finished cleanly"
    assert e["metadata"]["task_type"] == "log_analysis"
    assert e["category"] == "tasks"


def test_trace_id_falls_back_to_metadata_blob(db):
    _insert(db, event_type="PROPOSAL", metadata={"trace_id": "tr-meta"})
    out = activity.list_events({})
    assert out["events"][0]["trace_id"] == "tr-meta"


def test_malformed_metadata_does_not_blow_up(db):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO compliance_audit_log (id, timestamp, actor, action_type, metadata)"
        " VALUES ('x', '2026-07-11T10:00:00', 'AI_Agent', 'ANALYSIS', 'not-json')"
    )
    conn.commit()
    conn.close()
    out = activity.list_events({})
    assert out["events"][0]["metadata"] == {}


# --- error triage (the whole reason this handler exists) ------------------

def test_errors_category_matches_on_event_type(db):
    _insert(db, event_type="LLM_ERROR", action_type="GENERATE")
    _insert(db, event_type="TASK_COMPLETED", action_type="ANALYSIS")
    out = activity.list_events({"category": "errors"})
    assert out["total"] == 1
    assert out["events"][0]["event_type"] == "LLM_ERROR"


def test_errors_category_matches_on_output_text_alone(db):
    # The killer case: type looks routine, only the free text says it failed.
    # An exact action_type dropdown cannot express this at all.
    _insert(
        db,
        event_type="ANALYSIS",
        action_type="ANALYSIS",
        output_content="Traceback: connection error contacting provider",
    )
    out = activity.list_events({"category": "errors"})
    assert out["total"] == 1


def test_errors_category_matches_on_status_column(db):
    _insert(db, event_type="ACCESS", action_type="ACCESS", status="ERROR")
    out = activity.list_events({"category": "errors"})
    assert out["total"] == 1


def test_errors_category_matches_failed_in_output_text(db):
    _insert(db, event_type="BUILD", action_type="BUILD",
            output_content="Stage 3 failed")
    out = activity.list_events({"category": "errors"})
    assert out["total"] == 1


def test_error_precedence_beats_proposal(db):
    # classifyEvent checks errors FIRST — a failed proposal triages as an error.
    _insert(db, event_type="PROPOSAL_APPROVED", action_type="APPROVAL",
            output_content="apply failed: patch did not apply")
    assert activity.list_events({"category": "errors"})["total"] == 1
    assert activity.list_events({"category": "proposals"})["total"] == 0


# --- other categories -----------------------------------------------------

def test_proposals_category(db):
    _insert(db, event_type="PROPOSAL_APPROVED", action_type="APPROVAL",
            metadata={"decided_by": "harish"})
    _insert(db, event_type="PROPOSAL_REJECTED", action_type="REJECTION")
    _insert(db, event_type="TASK_SUBMITTED", action_type="TASK")
    out = activity.list_events({"category": "proposals"})
    assert out["total"] == 2
    assert all(e["category"] == "proposals" for e in out["events"])


def test_llm_category(db):
    _insert(db, event_type="LLM_CALL", action_type="GENERATION",
            metadata={"model": "gemini-2.0", "tokens": 812})
    _insert(db, event_type="TASK_SUBMITTED", action_type="TASK")
    out = activity.list_events({"category": "llm"})
    assert out["total"] == 1
    assert out["events"][0]["metadata"]["model"] == "gemini-2.0"


def test_tasks_category_absorbs_the_unclassified_fallback(db):
    # Neither proposal, nor llm, nor error, nor task keyword -> tasks (fallback).
    _insert(db, event_type="ACCESS", action_type="ACCESS")
    out = activity.list_events({"category": "tasks"})
    assert out["total"] == 1
    assert out["events"][0]["category"] == "tasks"


def test_categories_partition_the_event_set(db):
    _insert(db, event_type="LLM_ERROR", action_type="GENERATE")
    _insert(db, event_type="PROPOSAL_APPROVED", action_type="APPROVAL")
    _insert(db, event_type="TASK_COMPLETED", action_type="TASK")
    _insert(db, event_type="LLM_CALL", action_type="GENERATION")
    _insert(db, event_type="ACCESS", action_type="ACCESS")

    total = activity.list_events({})["total"]
    counts = {c: activity.list_events({"category": c})["total"]
              for c in activity.CATEGORIES}
    # Every event lands in exactly one bucket — SQL predicates and the Python
    # classifier must agree, or the pill counts lie.
    assert sum(counts.values()) == total == 5
    for cat in activity.CATEGORIES:
        for e in activity.list_events({"category": cat})["events"]:
            assert e["category"] == cat


def test_all_category_is_a_noop_filter(db):
    _insert(db, event_type="LLM_ERROR", action_type="GENERATE")
    _insert(db, event_type="TASK_COMPLETED", action_type="TASK")
    assert activity.list_events({"category": "all"})["total"] == 2


def test_unknown_category_rejected(db):
    with pytest.raises(RpcError):
        activity.list_events({"category": "not-a-category"})


# --- free-text search -----------------------------------------------------

def test_query_matches_actor(db):
    _insert(db, actor="Human_Engineer", event_type="APPROVAL")
    _insert(db, actor="AI_Agent", event_type="TASK")
    out = activity.list_events({"query": "human"})
    assert out["total"] == 1
    assert out["events"][0]["actor"] == "Human_Engineer"


def test_query_matches_output_content_case_insensitively(db):
    _insert(db, event_type="TASK", output_content="Firmware CRC mismatch on boot")
    _insert(db, event_type="TASK", output_content="all good")
    out = activity.list_events({"query": "crc mismatch"})
    assert out["total"] == 1


def test_query_and_category_compose(db):
    _insert(db, event_type="LLM_ERROR", actor="AI_Agent",
            output_content="timeout talking to ollama")
    _insert(db, event_type="LLM_ERROR", actor="AI_Agent",
            output_content="rate limited by gemini")
    out = activity.list_events({"category": "errors", "query": "ollama"})
    assert out["total"] == 1


# --- pagination -----------------------------------------------------------

def test_total_reflects_the_filter_not_the_whole_table(db):
    for i in range(7):
        _insert(db, event_type="LLM_ERROR", timestamp=f"2026-07-11T10:0{i}:00")
    for i in range(3):
        _insert(db, event_type="TASK_COMPLETED", timestamp=f"2026-07-11T11:0{i}:00")
    out = activity.list_events({"category": "errors", "limit": 2})
    # Filtering happens in SQL, so the count is the count of MATCHES — not of
    # the page, and not of the table.
    assert out["total"] == 7
    assert len(out["events"]) == 2


def test_newest_first(db):
    _insert(db, event_type="TASK", timestamp="2026-07-11T10:00:00", output_content="old")
    _insert(db, event_type="TASK", timestamp="2026-07-11T12:00:00", output_content="new")
    out = activity.list_events({})
    assert out["events"][0]["output_content"] == "new"


def test_offset_pages_through(db):
    for i in range(5):
        _insert(db, event_type="TASK", timestamp=f"2026-07-11T10:0{i}:00",
                output_content=f"e{i}")
    first = activity.list_events({"limit": 2, "offset": 0})["events"]
    second = activity.list_events({"limit": 2, "offset": 2})["events"]
    assert {e["id"] for e in first}.isdisjoint({e["id"] for e in second})


def test_limit_is_clamped(db):
    assert activity.list_events({"limit": 99999})["limit"] == activity.MAX_LIMIT
    assert activity.list_events({"limit": 0})["limit"] == 1
    assert activity.list_events({"offset": -5})["offset"] == 0


def test_non_integer_limit_rejected(db):
    with pytest.raises(RpcError):
        activity.list_events({"limit": "many"})

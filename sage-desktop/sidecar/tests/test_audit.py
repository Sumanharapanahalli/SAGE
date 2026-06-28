"""Tests for the audit handler.

The audit handler reads the compliance_audit_log SQLite table directly
via raw SQL (no ORM) to keep the handler fast and independent of any
AuditLogger instance configuration.
"""
from __future__ import annotations

import pytest

from handlers import audit


@pytest.fixture
def logger(tmp_path, monkeypatch):
    """Fresh AuditLogger backed by a temp SQLite DB, injected into handler."""
    from src.memory.audit_logger import AuditLogger

    db = tmp_path / "audit.db"
    lg = AuditLogger(db_path=str(db))
    monkeypatch.setattr(audit, "_logger", lg)
    return lg


def _seed(logger, n=5, action_type="PROPOSAL", trace_prefix="t"):
    for i in range(n):
        logger.log_event(
            actor="AI_Agent",
            action_type=action_type,
            input_context=f"input {i}",
            output_content=f"output {i}",
            metadata={"trace_id": f"{trace_prefix}-{i}", "i": i},
        )


# ---------- list ----------

def test_list_returns_empty_when_no_events(logger):
    out = audit.list_events({"limit": 50, "offset": 0})
    assert out["total"] == 0
    assert out["events"] == []


def test_list_returns_events_newest_first(logger):
    _seed(logger, n=3)
    out = audit.list_events({"limit": 50, "offset": 0})
    assert out["total"] == 3
    assert len(out["events"]) == 3
    # Newest first — last-seeded should be first
    assert out["events"][0]["input_context"] == "input 2"
    assert out["events"][2]["input_context"] == "input 0"


def test_list_honours_limit_and_offset(logger):
    _seed(logger, n=10)
    page1 = audit.list_events({"limit": 4, "offset": 0})
    page2 = audit.list_events({"limit": 4, "offset": 4})

    assert page1["total"] == 10
    assert len(page1["events"]) == 4
    assert len(page2["events"]) == 4
    # No overlap
    ids1 = {e["id"] for e in page1["events"]}
    ids2 = {e["id"] for e in page2["events"]}
    assert ids1.isdisjoint(ids2)


def test_list_filters_by_action_type(logger):
    _seed(logger, n=3, action_type="PROPOSAL", trace_prefix="p")
    _seed(logger, n=2, action_type="APPROVAL", trace_prefix="a")
    out = audit.list_events({"limit": 50, "offset": 0, "action_type": "APPROVAL"})
    assert out["total"] == 2
    assert all(e["action_type"] == "APPROVAL" for e in out["events"])


def test_list_filters_by_trace_id(logger):
    _seed(logger, n=5, trace_prefix="x")
    out = audit.list_events({"limit": 50, "offset": 0, "trace_id": "x-2"})
    assert out["total"] == 1
    assert out["events"][0]["trace_id"] == "x-2"


def test_list_returns_parsed_metadata_json(logger):
    _seed(logger, n=1)
    out = audit.list_events({"limit": 50, "offset": 0})
    row = out["events"][0]
    assert isinstance(row["metadata"], dict)
    assert row["metadata"]["i"] == 0


# ---------- get_by_trace ----------

def test_get_by_trace_returns_all_events_for_one_trace(logger):
    logger.log_event(
        actor="AI_Agent", action_type="PROPOSAL",
        input_context="i", output_content="o",
        metadata={"trace_id": "shared"},
    )
    logger.log_event(
        actor="Human_Engineer", action_type="APPROVAL",
        input_context="i", output_content="o",
        metadata={"trace_id": "shared"},
    )
    logger.log_event(
        actor="AI_Agent", action_type="PROPOSAL",
        input_context="i", output_content="o",
        metadata={"trace_id": "other"},
    )

    out = audit.get_by_trace({"trace_id": "shared"})
    assert len(out["events"]) == 2
    assert all(e["trace_id"] == "shared" for e in out["events"])


def test_get_by_trace_returns_empty_for_unknown_trace(logger):
    out = audit.get_by_trace({"trace_id": "does-not-exist"})
    assert out["events"] == []


def test_get_by_trace_requires_trace_id(logger):
    from rpc import RpcError
    with pytest.raises(RpcError):
        audit.get_by_trace({})


# ---------- stats ----------

def test_stats_returns_counts_by_action_type(logger):
    _seed(logger, n=3, action_type="PROPOSAL", trace_prefix="p")
    _seed(logger, n=2, action_type="APPROVAL", trace_prefix="a")
    _seed(logger, n=1, action_type="REJECTION", trace_prefix="r")

    out = audit.stats({})
    assert out["total"] == 6
    counts = out["by_action_type"]
    assert counts["PROPOSAL"] == 3
    assert counts["APPROVAL"] == 2
    assert counts["REJECTION"] == 1


def test_stats_on_empty_db_returns_zero(logger):
    out = audit.stats({})
    assert out["total"] == 0
    assert out["by_action_type"] == {}

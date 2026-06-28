"""
Tests for agent-to-agent communication auditing.

Every inter-agent communication must land in the formal, per-solution
compliance_audit_log so the /audit trace view is complete (regulatory control:
"trace each communication between agents"). The audit DB is solution-scoped by
construction (each solution has its own .sage/audit_log.db), so these records
are automatically per-solution.
"""
import json
import sqlite3
import tempfile
import os

import pytest

from src.memory.audit_logger import AuditLogger
from src.modules.event_bus import EventBus
from src.core.agent_comms_audit import (
    AGENT_COMM_EVENT,
    AGENT_COMM_ACTION,
    log_agent_communication,
    publish_agent_communication,
    attach_audit_bridge,
)


@pytest.fixture
def logger():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    lg = AuditLogger(db_path=path)
    yield lg
    try:
        os.remove(path)
    except OSError:
        pass


def _rows(logger, action_type=AGENT_COMM_ACTION):
    conn = sqlite3.connect(logger.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM compliance_audit_log WHERE action_type = ? "
            "ORDER BY timestamp ASC, rowid ASC",
            (action_type,),
        ).fetchall()
    finally:
        conn.close()


class TestDirectLogging:
    def test_writes_one_agent_communication_entry(self, logger):
        log_agent_communication(
            logger,
            from_agent="planner",
            to_agent="openswe",
            message="Implement the login endpoint",
            trace_id="trace-1",
        )
        rows = _rows(logger)
        assert len(rows) == 1
        r = rows[0]
        assert r["action_type"] == AGENT_COMM_ACTION
        assert r["actor"] == "planner"
        assert "login endpoint" in r["input_context"]
        meta = json.loads(r["metadata"])
        assert meta["to_agent"] == "openswe"
        assert meta["trace_id"] == "trace-1"
        assert meta["kind"] == "message"

    def test_kind_is_recorded(self, logger):
        log_agent_communication(
            logger, from_agent="orchestrator", to_agent="critic",
            message="review this", trace_id="t", kind="handoff",
        )
        meta = json.loads(_rows(logger)[0]["metadata"])
        assert meta["kind"] == "handoff"


class TestBusBridge:
    def test_published_communication_is_audited(self, logger):
        bus = EventBus()
        attach_audit_bridge(bus, logger)
        publish_agent_communication(
            bus, from_agent="monitor", to_agent="analyst",
            message="anomaly detected", trace_id="trace-9",
        )
        rows = _rows(logger)
        assert len(rows) == 1
        assert rows[0]["actor"] == "monitor"
        assert json.loads(rows[0]["metadata"])["to_agent"] == "analyst"

    def test_non_comm_events_are_not_audited(self, logger):
        bus = EventBus()
        attach_audit_bridge(bus, logger)
        bus.publish("some.other.event", {"foo": "bar"})
        assert _rows(logger) == []

    def test_bridge_returns_handler_count(self, logger):
        bus = EventBus()
        attach_audit_bridge(bus, logger)
        called = publish_agent_communication(
            bus, from_agent="a", to_agent="b", message="hi",
        )
        # at least the audit bridge handled it
        assert called >= 1


class TestPerTraceRetrieval:
    def test_all_messages_for_a_trace_are_recoverable(self, logger):
        for i in range(3):
            log_agent_communication(
                logger, from_agent=f"a{i}", to_agent="hub",
                message=f"m{i}", trace_id="shared",
            )
        log_agent_communication(
            logger, from_agent="x", to_agent="y", message="other",
            trace_id="different",
        )
        conn = sqlite3.connect(logger.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM compliance_audit_log "
                "WHERE json_extract(metadata, '$.trace_id') = ? "
                "ORDER BY timestamp ASC, rowid ASC",
                ("shared",),
            ).fetchall()
        finally:
            conn.close()
        assert len(rows) == 3
        assert [json.loads(r["metadata"])["trace_id"] for r in rows] == ["shared"] * 3

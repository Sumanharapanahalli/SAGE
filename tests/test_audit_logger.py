"""
SAGE[ai] - Unit tests for AuditLogger (src/memory/audit_logger.py)

Verifies ISO 13485 compliance: schema correctness, UUID generation,
persistence, metadata storage, timestamp format, and append-only behavior.
"""

import json
import re
import sqlite3
from datetime import datetime

import pytest


pytestmark = pytest.mark.unit

# UUID v4 pattern
UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _query_all(db_path):
    """Helper: query all rows from compliance_audit_log."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM compliance_audit_log ORDER BY timestamp ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_db_initialized_with_correct_schema(tmp_audit_db):
    """The compliance_audit_log table must exist with all required columns."""
    conn = sqlite3.connect(tmp_audit_db.db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(compliance_audit_log)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()

    required_columns = {"id", "timestamp", "actor", "action_type", "input_context", "output_content", "metadata"}
    missing = required_columns - columns
    assert not missing, f"Missing columns in audit table: {missing}"


def test_log_event_returns_uuid(tmp_audit_db):
    """log_event() must return a string that is a valid UUID v4."""
    event_id = tmp_audit_db.log_event(
        actor="TestActor",
        action_type="TEST_ACTION",
        input_context="test input",
        output_content="test output",
    )
    assert isinstance(event_id, str), "log_event() must return a string."
    assert UUID4_PATTERN.match(event_id), f"Returned ID is not a valid UUID v4: {event_id!r}"


def test_log_event_persists_to_db(tmp_audit_db):
    """After log_event(), a row must exist with the correct actor and action_type."""
    event_id = tmp_audit_db.log_event(
        actor="AnalystAgent",
        action_type="ANALYSIS_PROPOSAL",
        input_context="ERROR: sensor timeout",
        output_content='{"severity": "HIGH"}',
    )
    rows = _query_all(tmp_audit_db.db_path)
    assert len(rows) == 1, f"Expected 1 row, found {len(rows)}."
    row = rows[0]
    assert row["id"] == event_id
    assert row["actor"] == "AnalystAgent"
    assert row["action_type"] == "ANALYSIS_PROPOSAL"


def test_log_event_all_fields_stored(tmp_audit_db):
    """All fields passed to log_event() must be stored correctly in the database."""
    metadata = {"trace_id": "abc-123", "source": "test"}
    event_id = tmp_audit_db.log_event(
        actor="DeveloperAgent",
        action_type="MR_REVIEW",
        input_context="project=1 mr_iid=7",
        output_content='{"approved": true}',
        metadata=metadata,
    )
    rows = _query_all(tmp_audit_db.db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["actor"] == "DeveloperAgent"
    assert row["action_type"] == "MR_REVIEW"
    assert row["input_context"] == "project=1 mr_iid=7"
    assert row["output_content"] == '{"approved": true}'
    assert row["timestamp"] is not None
    # Metadata stored as JSON string
    stored_metadata = json.loads(row["metadata"])
    assert stored_metadata["trace_id"] == "abc-123"
    assert stored_metadata["source"] == "test"


def test_multiple_events_stored(tmp_audit_db):
    """Logging 10 events must result in exactly 10 rows in the database."""
    for i in range(10):
        tmp_audit_db.log_event(
            actor="TestActor",
            action_type=f"ACTION_{i}",
            input_context=f"input {i}",
            output_content=f"output {i}",
        )
    conn = sqlite3.connect(tmp_audit_db.db_path)
    count = conn.execute("SELECT COUNT(*) FROM compliance_audit_log").fetchone()[0]
    conn.close()
    assert count == 10, f"Expected 10 rows, found {count}."


def test_metadata_stored_as_json(tmp_audit_db):
    """Metadata dict must be stored as valid JSON and be retrievable with correct content."""
    metadata = {"key": "value", "number": 42, "flag": True}
    tmp_audit_db.log_event(
        actor="TestActor",
        action_type="TEST_ACTION",
        input_context="input",
        output_content="output",
        metadata=metadata,
    )
    rows = _query_all(tmp_audit_db.db_path)
    stored_metadata_str = rows[0]["metadata"]
    # Must be valid JSON
    parsed = json.loads(stored_metadata_str)
    assert parsed["key"] == "value"
    assert parsed["number"] == 42
    assert parsed["flag"] is True


def test_log_event_with_none_metadata(tmp_audit_db):
    """log_event() with metadata=None must not raise an exception and must store the row."""
    try:
        event_id = tmp_audit_db.log_event(
            actor="TestActor",
            action_type="TEST_ACTION",
            input_context="input",
            output_content="output",
            metadata=None,
        )
    except Exception as exc:
        pytest.fail(f"log_event() raised an exception with metadata=None: {exc}")
    rows = _query_all(tmp_audit_db.db_path)
    assert len(rows) == 1, "Row must be stored even with metadata=None."
    assert rows[0]["id"] == event_id


def test_timestamp_format(tmp_audit_db):
    """The stored timestamp must be parseable as an ISO 8601 datetime."""
    tmp_audit_db.log_event(
        actor="TestActor",
        action_type="TEST_ACTION",
        input_context="input",
        output_content="output",
    )
    rows = _query_all(tmp_audit_db.db_path)
    ts_str = rows[0]["timestamp"]
    assert ts_str is not None, "Timestamp must not be None."
    try:
        dt = datetime.fromisoformat(ts_str)
    except ValueError as exc:
        pytest.fail(f"Timestamp '{ts_str}' is not a valid ISO datetime: {exc}")
    assert dt.year >= 2020, f"Timestamp year {dt.year} seems unreasonably old."


def test_audit_log_is_append_only(tmp_audit_db):
    """Logging two events must result in both being present — no overwrite."""
    id1 = tmp_audit_db.log_event(
        actor="Agent1", action_type="ACTION_A", input_context="in1", output_content="out1"
    )
    id2 = tmp_audit_db.log_event(
        actor="Agent2", action_type="ACTION_B", input_context="in2", output_content="out2"
    )
    rows = _query_all(tmp_audit_db.db_path)
    assert len(rows) == 2, f"Expected 2 rows (append-only), found {len(rows)}."
    ids = {row["id"] for row in rows}
    assert id1 in ids, "First event ID must still be in the database."
    assert id2 in ids, "Second event ID must still be in the database."


def test_trace_id_is_unique_per_event(tmp_audit_db):
    """Each call to log_event() must produce a distinct UUID."""
    ids = set()
    for _ in range(5):
        event_id = tmp_audit_db.log_event(
            actor="TestActor",
            action_type="TEST_ACTION",
            input_context="input",
            output_content="output",
        )
        ids.add(event_id)
    assert len(ids) == 5, f"Expected 5 unique IDs, got {len(ids)}: {ids}"

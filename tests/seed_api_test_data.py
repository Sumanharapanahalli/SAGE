"""
tests/seed_api_test_data.py — Idempotent test dataset seeder for the SAGE API.

Schema covered:
  compliance_audit_log — 10 seed events (ANALYSIS, PROPOSAL, APPROVAL, REJECTION)
  chat_messages        — 8 seed messages (2 sessions, user + assistant turns)

Idempotency guarantee:
  Every INSERT uses INSERT OR IGNORE keyed on the stable ``id`` column (PRIMARY KEY).
  Re-running this script produces no duplicate rows and no errors.

Data validation on ingestion:
  All rows are validated by _validate_record() before any SQL is executed.
  Invalid rows are logged and skipped — the rest of the seed proceeds.

Usage (from repo root):
  python -m tests.seed_api_test_data [--teardown] [--db /path/to/db]

  Or from pytest conftest via:
    from tests.seed_api_test_data import seed_all, teardown_all
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("seed_api_test_data")

# ---------------------------------------------------------------------------
# Validation primitives (no external imports — usable standalone)
# ---------------------------------------------------------------------------

@dataclass
class _Check:
    rule: str
    passed: bool
    message: str
    severity: str = "error"   # "critical" | "error" | "warning"


def _require_fields(record: dict, required: list[str]) -> list[_Check]:
    results = []
    for f in required:
        present = record.get(f) is not None and record.get(f) != ""
        results.append(_Check(
            rule=f"required:{f}",
            passed=present,
            message=f"Field '{f}' is required." if not present else "ok",
            severity="critical",
        ))
    return results


def _enum_check(record: dict, field: str, allowed: list[str]) -> _Check:
    val = record.get(field)
    ok = val in allowed
    return _Check(
        rule=f"enum:{field}",
        passed=ok,
        message=f"'{field}' must be one of {allowed}, got {val!r}." if not ok else "ok",
    )


def _json_valid(record: dict, field: str) -> _Check:
    val = record.get(field)
    if val is None:
        return _Check(rule=f"json:{field}", passed=True, message="ok")
    try:
        json.loads(val)
        return _Check(rule=f"json:{field}", passed=True, message="ok")
    except (TypeError, json.JSONDecodeError) as exc:
        return _Check(
            rule=f"json:{field}",
            passed=False,
            message=f"'{field}' must be valid JSON: {exc}",
        )


_PROPOSAL_ACTION_TYPES = [
    "yaml_edit", "code_diff", "implementation_plan",
    "knowledge_add", "knowledge_delete", "agent_hire",
]
_PROPOSAL_RISK_CLASSES = [
    "INFORMATIONAL", "EPHEMERAL", "STATEFUL", "EXTERNAL", "DESTRUCTIVE",
]
_PROPOSAL_STATUSES = ["pending", "approved", "rejected", "expired"]


def _validate_record(table: str, record: dict) -> list[_Check]:
    """Return all validation checks for *record* destined for *table*."""
    checks: list[_Check] = []

    if table == "proposals":
        checks += _require_fields(record, ["trace_id", "created_at", "action_type",
                                           "risk_class", "proposed_by", "description",
                                           "payload"])
        checks.append(_enum_check(record, "action_type", _PROPOSAL_ACTION_TYPES))
        checks.append(_enum_check(record, "risk_class",  _PROPOSAL_RISK_CLASSES))
        if record.get("status"):
            checks.append(_enum_check(record, "status", _PROPOSAL_STATUSES))
        checks.append(_json_valid(record, "payload"))

    elif table == "compliance_audit_log":
        checks += _require_fields(record, ["id", "actor", "action_type"])
        checks.append(_enum_check(
            record, "action_type",
            ["ANALYSIS", "PROPOSAL", "APPROVAL", "REJECTION", "ACCESS", "EXECUTION"],
        ))
        if record.get("event_type"):
            checks.append(_enum_check(
                record, "event_type",
                ["ACCESS", "ANALYSIS", "PROPOSAL", "APPROVAL", "REJECTION", "EXECUTION"],
            ))
        if record.get("status"):
            checks.append(_enum_check(record, "status", ["OK", "DENIED", "ERROR"]))
        checks.append(_json_valid(record, "metadata"))

    elif table == "chat_messages":
        checks += _require_fields(record, ["id", "user_id", "session_id", "solution", "role", "content", "created_at"])
        checks.append(_enum_check(record, "role", ["user", "assistant"]))
        if record.get("message_type"):
            checks.append(_enum_check(record, "message_type", ["user", "assistant", "system"]))

    return checks


def _is_valid(table: str, record: dict, row_label: str) -> bool:
    checks = _validate_record(table, record)
    blocking = [c for c in checks if not c.passed and c.severity in ("error", "critical")]
    if blocking:
        for c in blocking:
            logger.warning("SKIP %s [%s] — %s (%s)", table, row_label, c.message, c.rule)
        return False
    for w in [c for c in checks if not c.passed and c.severity == "warning"]:
        logger.warning("WARN %s [%s] — %s (%s)", table, row_label, w.message, w.rule)
    return True


# ---------------------------------------------------------------------------
# Stable test-row UUIDs (fixed so INSERT OR IGNORE is idempotent)
# ---------------------------------------------------------------------------
# Naming convention: actor starts with "test_" so teardown can target them
# without touching production rows.

_TS = "2026-03-28T10:00:00+00:00"   # fixed timestamp — tests must not rely on clock


SEED_AUDIT_EVENTS: list[dict[str, Any]] = [
    # ── Full proposal lifecycle: ANALYSIS → PROPOSAL → APPROVAL ──────────
    {
        "id":             "00000000-0001-4000-8000-000000000001",
        "timestamp":      _TS,
        "trace_id":       "trace-lifecycle-001",
        "event_type":     "ANALYSIS",
        "status":         "OK",
        "actor":          "test_AI_Agent",
        "action_type":    "ANALYSIS",
        "input_context":  "ERROR [uart_driver.c:142] UART1 RX buffer overflow",
        "output_content": json.dumps({
            "severity": "HIGH",
            "root_cause_hypothesis": "UART1 RX buffer too small (256 bytes)",
            "recommended_action":    "Increase buffer to 512 bytes",
        }),
        "metadata":       json.dumps({"solution": "medtech_team", "test_marker": True}),
    },
    {
        "id":             "00000000-0001-4000-8000-000000000002",
        "timestamp":      _TS,
        "trace_id":       "trace-lifecycle-001",
        "event_type":     "PROPOSAL",
        "status":         "OK",
        "actor":          "test_AI_Agent",
        "action_type":    "PROPOSAL",
        "input_context":  "Increase UART1 RX buffer from 256 to 512 bytes",
        "output_content": json.dumps({
            "proposal_type": "code_diff",
            "diff":          "+#define UART_BUF_SIZE 512\n-#define UART_BUF_SIZE 256",
        }),
        "metadata":       json.dumps({"solution": "medtech_team", "test_marker": True}),
    },
    {
        "id":             "00000000-0001-4000-8000-000000000003",
        "timestamp":      _TS,
        "trace_id":       "trace-lifecycle-001",
        "event_type":     "APPROVAL",
        "status":         "OK",
        "actor":          "test_Human_Engineer",
        "action_type":    "APPROVAL",
        "input_context":  "Approved code_diff for uart_driver.c",
        "output_content": "approved",
        "metadata":       json.dumps({"solution": "medtech_team", "test_marker": True}),
        "approved_by":    "alice_test",
        "approver_role":  "firmware_engineer",
        "approver_email": "alice@test.example",
        "approver_provider": "oidc",
    },
    # ── Rejected proposal lifecycle: ANALYSIS → PROPOSAL → REJECTION ─────
    {
        "id":             "00000000-0002-4000-8000-000000000001",
        "timestamp":      _TS,
        "trace_id":       "trace-lifecycle-002",
        "event_type":     "ANALYSIS",
        "status":         "OK",
        "actor":          "test_AI_Agent",
        "action_type":    "ANALYSIS",
        "input_context":  "WARNING [i2c_bus.c:205] I2C1 bus stuck LOW",
        "output_content": json.dumps({
            "severity": "MEDIUM",
            "root_cause_hypothesis": "I2C bus contention from two peripheral devices",
            "recommended_action":    "Add pull-up resistors and bus reset sequence",
        }),
        "metadata":       json.dumps({"solution": "medtech_team", "test_marker": True}),
    },
    {
        "id":             "00000000-0002-4000-8000-000000000002",
        "timestamp":      _TS,
        "trace_id":       "trace-lifecycle-002",
        "event_type":     "PROPOSAL",
        "status":         "OK",
        "actor":          "test_AI_Agent",
        "action_type":    "PROPOSAL",
        "input_context":  "Add I2C bus recovery sequence to i2c_bus.c",
        "output_content": json.dumps({
            "proposal_type": "implementation_plan",
            "steps":         ["Add HAL_I2C_DeInit()", "Add 10ms delay", "Re-init I2C"],
        }),
        "metadata":       json.dumps({"solution": "medtech_team", "test_marker": True}),
    },
    {
        "id":             "00000000-0002-4000-8000-000000000003",
        "timestamp":      _TS,
        "trace_id":       "trace-lifecycle-002",
        "event_type":     "REJECTION",
        "status":         "DENIED",
        "actor":          "test_Human_Engineer",
        "action_type":    "REJECTION",
        "input_context":  "Rejected implementation_plan — hardware fix preferred",
        "output_content": "rejected: requires hardware change, not software workaround",
        "metadata":       json.dumps({"solution": "medtech_team", "test_marker": True}),
        "approved_by":    "bob_test",
        "approver_role":  "hardware_engineer",
        "approver_email": "bob@test.example",
        "approver_provider": "api_key",
    },
    # ── Standalone ANALYSIS event (no follow-up proposal) ────────────────
    {
        "id":             "00000000-0003-4000-8000-000000000001",
        "timestamp":      _TS,
        "trace_id":       "trace-standalone-003",
        "event_type":     "ANALYSIS",
        "status":         "OK",
        "actor":          "test_AI_Agent",
        "action_type":    "ANALYSIS",
        "input_context":  "CRITICAL [watchdog.c:88] Watchdog timeout expired",
        "output_content": json.dumps({
            "severity": "CRITICAL",
            "root_cause_hypothesis": "SENSOR_POLL task exceeded time budget",
            "recommended_action":    "Profile SENSOR_POLL; reduce polling frequency",
        }),
        "metadata":       json.dumps({"solution": "medtech_team", "test_marker": True}),
    },
    # ── ACCESS audit event ────────────────────────────────────────────────
    {
        "id":             "00000000-0004-4000-8000-000000000001",
        "timestamp":      _TS,
        "trace_id":       "trace-access-004",
        "event_type":     "ACCESS",
        "status":         "OK",
        "actor":          "test_Human_Engineer",
        "action_type":    "ACCESS",
        "input_context":  "GET /audit",
        "output_content": "200 OK — 7 audit records returned",
        "metadata":       json.dumps({"solution": "medtech_team", "test_marker": True}),
    },
    # ── Error event ───────────────────────────────────────────────────────
    {
        "id":             "00000000-0005-4000-8000-000000000001",
        "timestamp":      _TS,
        "trace_id":       "trace-error-005",
        "event_type":     "ANALYSIS",
        "status":         "ERROR",
        "actor":          "test_AI_Agent",
        "action_type":    "ANALYSIS",
        "input_context":  "POST /analyze — LLM provider timeout",
        "output_content": "LLM gateway timed out after 30s",
        "metadata":       json.dumps({"solution": "medtech_team", "test_marker": True}),
    },
    # ── Anonymous approval (approver_provider = anonymous) ────────────────
    {
        "id":             "00000000-0006-4000-8000-000000000001",
        "timestamp":      _TS,
        "trace_id":       "trace-anon-006",
        "event_type":     "APPROVAL",
        "status":         "OK",
        "actor":          "test_Human_Engineer",
        "action_type":    "APPROVAL",
        "input_context":  "Approved yaml_edit for project.yaml",
        "output_content": "approved",
        "metadata":       json.dumps({"solution": "starter", "test_marker": True}),
        "approved_by":    None,
        "approver_role":  None,
        "approver_email": None,
        "approver_provider": "anonymous",
    },
]


SEED_CHAT_MESSAGES: list[dict[str, Any]] = [
    # ── Session 1 — firmware analysis chat ───────────────────────────────
    {
        "id":           "cc000000-0001-4000-8000-000000000001",
        "user_id":      "test_alice",
        "session_id":   "test_session_001",
        "solution":     "medtech_team",
        "role":         "user",
        "content":      "What caused the UART overflow?",
        "page_context": "analyst",
        "created_at":   "2026-03-28T10:01:00+00:00",
        "message_type": "user",
        "metadata":     json.dumps({"test_marker": True}),
    },
    {
        "id":           "cc000000-0001-4000-8000-000000000002",
        "user_id":      "test_alice",
        "session_id":   "test_session_001",
        "solution":     "medtech_team",
        "role":         "assistant",
        "content":      "The UART1 RX buffer (256 bytes) was overwhelmed during burst reception.",
        "page_context": "analyst",
        "created_at":   "2026-03-28T10:01:05+00:00",
        "message_type": "assistant",
        "metadata":     json.dumps({"test_marker": True, "trace_id": "trace-lifecycle-001"}),
    },
    {
        "id":           "cc000000-0001-4000-8000-000000000003",
        "user_id":      "test_alice",
        "session_id":   "test_session_001",
        "solution":     "medtech_team",
        "role":         "user",
        "content":      "Can you suggest a fix?",
        "page_context": "analyst",
        "created_at":   "2026-03-28T10:01:30+00:00",
        "message_type": "user",
        "metadata":     json.dumps({"test_marker": True}),
    },
    {
        "id":           "cc000000-0001-4000-8000-000000000004",
        "user_id":      "test_alice",
        "session_id":   "test_session_001",
        "solution":     "medtech_team",
        "role":         "assistant",
        "content":      "Increase UART_BUF_SIZE from 256 to 512 in uart_driver.h. I've raised a proposal.",
        "page_context": "analyst",
        "created_at":   "2026-03-28T10:01:35+00:00",
        "message_type": "assistant",
        "metadata":     json.dumps({"test_marker": True, "trace_id": "trace-lifecycle-001"}),
    },
    # ── Session 2 — different user / solution (starter) ──────────────────
    {
        "id":           "cc000000-0002-4000-8000-000000000001",
        "user_id":      "test_bob",
        "session_id":   "test_session_002",
        "solution":     "starter",
        "role":         "user",
        "content":      "List pending proposals",
        "page_context": "approvals",
        "created_at":   "2026-03-28T11:00:00+00:00",
        "message_type": "user",
        "metadata":     json.dumps({"test_marker": True}),
    },
    {
        "id":           "cc000000-0002-4000-8000-000000000002",
        "user_id":      "test_bob",
        "session_id":   "test_session_002",
        "solution":     "starter",
        "role":         "assistant",
        "content":      "There are currently 2 pending proposals awaiting your review.",
        "page_context": "approvals",
        "created_at":   "2026-03-28T11:00:03+00:00",
        "message_type": "assistant",
        "metadata":     json.dumps({"test_marker": True}),
    },
    {
        "id":           "cc000000-0002-4000-8000-000000000003",
        "user_id":      "test_bob",
        "session_id":   "test_session_002",
        "solution":     "starter",
        "role":         "user",
        "content":      "Approve trace-lifecycle-001",
        "page_context": "approvals",
        "created_at":   "2026-03-28T11:00:20+00:00",
        "message_type": "user",
        "metadata":     json.dumps({"test_marker": True}),
    },
    {
        "id":           "cc000000-0002-4000-8000-000000000004",
        "user_id":      "test_bob",
        "session_id":   "test_session_002",
        "solution":     "starter",
        "role":         "assistant",
        "content":      "Proposal trace-lifecycle-001 approved. Audit entry recorded.",
        "page_context": "approvals",
        "created_at":   "2026-03-28T11:00:22+00:00",
        "message_type": "assistant",
        "metadata":     json.dumps({"test_marker": True, "trace_id": "trace-lifecycle-001"}),
    },
]


_TS_FUTURE = "2026-04-28T10:00:00+00:00"   # still pending / not expired
_TS_PAST   = "2026-02-01T00:00:00+00:00"   # expired proposals


SEED_PROPOSALS: list[dict[str, Any]] = [
    # ── 001: Pending yaml_edit — STATEFUL, reversible ─────────────────────
    {
        "trace_id":     "test-proposal-001",
        "created_at":   _TS,
        "action_type":  "yaml_edit",
        "risk_class":   "STATEFUL",
        "reversible":   1,
        "proposed_by":  "test_AI_Agent",
        "description":  "Update medtech_team/project.yaml to add new module 'firmware_monitor'",
        "payload":      json.dumps({
            "file":    "solutions/medtech_team/project.yaml",
            "field":   "active_modules",
            "change":  "append 'firmware_monitor'",
        }),
        "status":       "pending",
        "decided_by":   None,
        "decided_at":   None,
        "feedback":     None,
        "expires_at":   _TS_FUTURE,
        "required_role": None,
        "approved_by":  "",
        "approver_role": "",
        "approver_email": "",
    },
    # ── 002: Pending code_diff — EXTERNAL, requires firmware_engineer ──────
    {
        "trace_id":     "test-proposal-002",
        "created_at":   _TS,
        "action_type":  "code_diff",
        "risk_class":   "EXTERNAL",
        "reversible":   1,
        "proposed_by":  "test_AI_Agent",
        "description":  "Increase UART1 RX buffer from 256 to 512 bytes in uart_driver.h",
        "payload":      json.dumps({
            "file":  "src/drivers/uart_driver.h",
            "diff":  "+#define UART_BUF_SIZE 512\n-#define UART_BUF_SIZE 256",
        }),
        "status":       "pending",
        "decided_by":   None,
        "decided_at":   None,
        "feedback":     None,
        "expires_at":   _TS_FUTURE,
        "required_role": "firmware_engineer",
        "approved_by":  "",
        "approver_role": "",
        "approver_email": "",
    },
    # ── 003: Approved implementation_plan ─────────────────────────────────
    {
        "trace_id":     "test-proposal-003",
        "created_at":   _TS,
        "action_type":  "implementation_plan",
        "risk_class":   "STATEFUL",
        "reversible":   1,
        "proposed_by":  "test_AI_Agent",
        "description":  "Add I2C bus recovery sequence to i2c_bus.c",
        "payload":      json.dumps({
            "steps": [
                "Add HAL_I2C_DeInit()",
                "Add 10 ms delay",
                "Re-init I2C peripheral",
            ],
        }),
        "status":       "approved",
        "decided_by":   "carol_test",
        "decided_at":   _TS,
        "feedback":     "Approved — matches IEC 62304 change control procedure",
        "expires_at":   _TS_FUTURE,
        "required_role": None,
        "approved_by":  "carol_test",
        "approver_role": "firmware_engineer",
        "approver_email": "carol@test.example",
    },
    # ── 004: Rejected knowledge_add ───────────────────────────────────────
    {
        "trace_id":     "test-proposal-004",
        "created_at":   _TS,
        "action_type":  "knowledge_add",
        "risk_class":   "EPHEMERAL",
        "reversible":   1,
        "proposed_by":  "test_AI_Agent",
        "description":  "Add watchdog configuration note to knowledge base",
        "payload":      json.dumps({
            "content": "Watchdog timeout should be set to 500 ms per IEC 62304 §8.1.3",
            "tags":    ["watchdog", "safety", "iec62304"],
        }),
        "status":       "rejected",
        "decided_by":   "dave_test",
        "decided_at":   _TS,
        "feedback":     "Rejected — needs traceability reference before adding to KB",
        "expires_at":   _TS_FUTURE,
        "required_role": None,
        "approved_by":  "dave_test",
        "approver_role": "safety_engineer",
        "approver_email": "dave@test.example",
    },
    # ── 005: Expired agent_hire — expires_at in the past ──────────────────
    {
        "trace_id":     "test-proposal-005",
        "created_at":   _TS_PAST,
        "action_type":  "agent_hire",
        "risk_class":   "EXTERNAL",
        "reversible":   0,
        "proposed_by":  "test_AI_Agent",
        "description":  "Hire a regulatory_specialist agent for FDA 510(k) submission review",
        "payload":      json.dumps({
            "role":       "regulatory_specialist",
            "runner":     "opendoc",
            "solution":   "medtech_team",
            "rationale":  "510(k) submission deadline requires specialist review",
        }),
        "status":       "expired",
        "decided_by":   None,
        "decided_at":   None,
        "feedback":     None,
        "expires_at":   _TS_PAST,
        "required_role": "regulatory_specialist",
        "approved_by":  "",
        "approver_role": "",
        "approver_email": "",
    },
]


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------

class ApiTestDataSeeder:
    """
    Idempotent seeder for the SAGE API's SQLite database.
    Safe to call multiple times — produces identical DB state on every run.

    compliance_audit_log: INSERT OR IGNORE keyed on id (PRIMARY KEY)
    chat_messages:        INSERT OR IGNORE keyed on id (PRIMARY KEY)
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self.stats: dict[str, dict[str, int]] = {}

    # ── public API ──────────────────────────────────────────────────────────

    def seed_all(self) -> dict[str, dict[str, int]]:
        """Seed all tables. Returns per-table stats."""
        logger.info("=== seed_all started (db=%s) ===", self._db_path)
        self._ensure_schema()
        self._seed_audit_events()
        self._seed_chat_messages()
        self._seed_proposals()
        logger.info("=== seed_all complete — stats: %s ===", self.stats)
        return self.stats

    def teardown_all(self) -> None:
        """Remove only test rows (actor/user_id/proposed_by LIKE 'test_%')."""
        logger.info("=== teardown_all started ===")
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "DELETE FROM chat_messages WHERE user_id LIKE 'test_%'"
            )
            conn.execute(
                "DELETE FROM compliance_audit_log WHERE actor LIKE 'test_%'"
            )
            conn.execute(
                "DELETE FROM proposals WHERE proposed_by LIKE 'test_%'"
            )
            conn.commit()
        finally:
            conn.close()
        logger.info("=== teardown_all complete ===")

    # ── private helpers ─────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist (mirrors AuditLogger._initialize_db)."""
        conn = self._connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS compliance_audit_log (
                    id                  TEXT PRIMARY KEY,
                    timestamp           DATETIME DEFAULT CURRENT_TIMESTAMP,
                    trace_id            TEXT,
                    event_type          TEXT,
                    status              TEXT DEFAULT 'OK',
                    actor               TEXT NOT NULL,
                    action_type         TEXT NOT NULL,
                    input_context       TEXT,
                    output_content      TEXT,
                    metadata            JSON,
                    verification_signature TEXT,
                    approved_by         TEXT,
                    approver_role       TEXT,
                    approver_email      TEXT,
                    approver_provider   TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id           TEXT PRIMARY KEY,
                    user_id      TEXT NOT NULL,
                    session_id   TEXT NOT NULL,
                    solution     TEXT NOT NULL,
                    role         TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content      TEXT NOT NULL,
                    page_context TEXT,
                    created_at   TEXT NOT NULL,
                    message_type TEXT DEFAULT 'user',
                    metadata     TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proposals (
                    trace_id        TEXT PRIMARY KEY,
                    created_at      TEXT NOT NULL,
                    action_type     TEXT NOT NULL,
                    risk_class      TEXT NOT NULL,
                    reversible      INTEGER NOT NULL,
                    proposed_by     TEXT NOT NULL,
                    description     TEXT NOT NULL,
                    payload         TEXT NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    decided_by      TEXT,
                    decided_at      TEXT,
                    feedback        TEXT,
                    expires_at      TEXT,
                    required_role   TEXT,
                    approved_by     TEXT DEFAULT '',
                    approver_role   TEXT DEFAULT '',
                    approver_email  TEXT DEFAULT ''
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def _seed_audit_events(self) -> None:
        inserted = 0
        skipped_validation = 0
        conn = self._connect()
        try:
            for row in SEED_AUDIT_EVENTS:
                if not _is_valid("compliance_audit_log", row, row["id"]):
                    skipped_validation += 1
                    continue
                cur = conn.execute("""
                    INSERT OR IGNORE INTO compliance_audit_log
                        (id, timestamp, trace_id, event_type, status,
                         actor, action_type, input_context, output_content, metadata,
                         approved_by, approver_role, approver_email, approver_provider)
                    VALUES
                        (:id, :timestamp, :trace_id, :event_type, :status,
                         :actor, :action_type, :input_context, :output_content, :metadata,
                         :approved_by, :approver_role, :approver_email, :approver_provider)
                """, {
                    "id":               row["id"],
                    "timestamp":        row.get("timestamp"),
                    "trace_id":         row.get("trace_id"),
                    "event_type":       row.get("event_type"),
                    "status":           row.get("status", "OK"),
                    "actor":            row["actor"],
                    "action_type":      row["action_type"],
                    "input_context":    row.get("input_context"),
                    "output_content":   row.get("output_content"),
                    "metadata":         row.get("metadata"),
                    "approved_by":      row.get("approved_by"),
                    "approver_role":    row.get("approver_role"),
                    "approver_email":   row.get("approver_email"),
                    "approver_provider": row.get("approver_provider"),
                })
                inserted += cur.rowcount
            conn.commit()
        finally:
            conn.close()
        self.stats["compliance_audit_log"] = {
            "attempted": len(SEED_AUDIT_EVENTS),
            "inserted": inserted,
            "skipped_validation": skipped_validation,
        }
        logger.info("compliance_audit_log: inserted=%d  skipped_validation=%d", inserted, skipped_validation)

    def _seed_chat_messages(self) -> None:
        inserted = 0
        skipped_validation = 0
        conn = self._connect()
        try:
            for row in SEED_CHAT_MESSAGES:
                if not _is_valid("chat_messages", row, row["id"]):
                    skipped_validation += 1
                    continue
                cur = conn.execute("""
                    INSERT OR IGNORE INTO chat_messages
                        (id, user_id, session_id, solution, role, content,
                         page_context, created_at, message_type, metadata)
                    VALUES
                        (:id, :user_id, :session_id, :solution, :role, :content,
                         :page_context, :created_at, :message_type, :metadata)
                """, {
                    "id":           row["id"],
                    "user_id":      row["user_id"],
                    "session_id":   row["session_id"],
                    "solution":     row["solution"],
                    "role":         row["role"],
                    "content":      row["content"],
                    "page_context": row.get("page_context"),
                    "created_at":   row["created_at"],
                    "message_type": row.get("message_type", "user"),
                    "metadata":     row.get("metadata"),
                })
                inserted += cur.rowcount
            conn.commit()
        finally:
            conn.close()
        self.stats["chat_messages"] = {
            "attempted": len(SEED_CHAT_MESSAGES),
            "inserted": inserted,
            "skipped_validation": skipped_validation,
        }
        logger.info("chat_messages: inserted=%d  skipped_validation=%d", inserted, skipped_validation)

    def _seed_proposals(self) -> None:
        inserted = 0
        skipped_validation = 0
        conn = self._connect()
        try:
            for row in SEED_PROPOSALS:
                if not _is_valid("proposals", row, row["trace_id"]):
                    skipped_validation += 1
                    continue
                cur = conn.execute("""
                    INSERT OR IGNORE INTO proposals
                        (trace_id, created_at, action_type, risk_class, reversible,
                         proposed_by, description, payload, status,
                         decided_by, decided_at, feedback,
                         expires_at, required_role,
                         approved_by, approver_role, approver_email)
                    VALUES
                        (:trace_id, :created_at, :action_type, :risk_class, :reversible,
                         :proposed_by, :description, :payload, :status,
                         :decided_by, :decided_at, :feedback,
                         :expires_at, :required_role,
                         :approved_by, :approver_role, :approver_email)
                """, {
                    "trace_id":      row["trace_id"],
                    "created_at":    row["created_at"],
                    "action_type":   row["action_type"],
                    "risk_class":    row["risk_class"],
                    "reversible":    row["reversible"],
                    "proposed_by":   row["proposed_by"],
                    "description":   row["description"],
                    "payload":       row["payload"],
                    "status":        row.get("status", "pending"),
                    "decided_by":    row.get("decided_by"),
                    "decided_at":    row.get("decided_at"),
                    "feedback":      row.get("feedback"),
                    "expires_at":    row.get("expires_at"),
                    "required_role": row.get("required_role"),
                    "approved_by":   row.get("approved_by", ""),
                    "approver_role": row.get("approver_role", ""),
                    "approver_email": row.get("approver_email", ""),
                })
                inserted += cur.rowcount
            conn.commit()
        finally:
            conn.close()
        self.stats["proposals"] = {
            "attempted": len(SEED_PROPOSALS),
            "inserted": inserted,
            "skipped_validation": skipped_validation,
        }
        logger.info("proposals: inserted=%d  skipped_validation=%d", inserted, skipped_validation)


# ---------------------------------------------------------------------------
# Pytest-compatible fixture helpers
# ---------------------------------------------------------------------------

def seed_all(db_path: str) -> dict[str, dict[str, int]]:
    """Idempotent seed; returns stats dict. Call from pytest fixtures."""
    seeder = ApiTestDataSeeder(db_path)
    return seeder.seed_all()


def teardown_all(db_path: str) -> None:
    """Remove all test rows. Call from pytest fixture teardown."""
    seeder = ApiTestDataSeeder(db_path)
    seeder.teardown_all()


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed / teardown SAGE API test data")
    parser.add_argument("--db", default=None, help="Path to SQLite DB (default: .sage/audit_log.db)")
    parser.add_argument("--teardown", action="store_true", help="Remove test rows instead of seeding")
    args = parser.parse_args()

    if args.db:
        db_path = args.db
    else:
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
        from src.memory.audit_logger import DB_PATH as _DEFAULT_DB
        db_path = _DEFAULT_DB

    seeder = ApiTestDataSeeder(db_path)
    if args.teardown:
        seeder.teardown_all()
    else:
        stats = seeder.seed_all()
        print("\nSeed complete:")
        for table, counts in stats.items():
            print(f"  {table:<30} {counts}")

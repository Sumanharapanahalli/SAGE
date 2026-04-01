"""
tests/test_api_seed_validation.py — Unit tests for seed_api_test_data validation
logic and idempotency guarantees (no live DB required).

Coverage:
  - _validate_record() for compliance_audit_log and chat_messages
  - _is_valid() severity routing (critical/error blocks; warning passes through)
  - ApiTestDataSeeder.seed_all() idempotency via an in-memory SQLite database
  - ApiTestDataSeeder.teardown_all() removes only test rows
  - All SEED_* constants contain zero invalid rows (schema contract)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import tempfile
import os

import pytest

from tests.seed_api_test_data import (
    SEED_AUDIT_EVENTS,
    SEED_CHAT_MESSAGES,
    SEED_PROPOSALS,
    ApiTestDataSeeder,
    _Check,
    _is_valid,
    _validate_record,
    seed_all,
    teardown_all,
)


# =============================================================================
# Helpers
# =============================================================================

def _checks_passed(checks: list[_Check]) -> bool:
    return all(c.passed for c in checks)


def _blocking_failures(checks: list[_Check]) -> list[_Check]:
    return [c for c in checks if not c.passed and c.severity in ("error", "critical")]


# =============================================================================
# _validate_record — compliance_audit_log
# =============================================================================

class TestValidateAuditLog:
    TABLE = "compliance_audit_log"

    def _row(self, **overrides):
        base = {
            "id":          "00000000-ffff-4000-8000-000000000001",
            "actor":       "test_AI_Agent",
            "action_type": "ANALYSIS",
        }
        base.update(overrides)
        return base

    def test_minimal_valid_row(self):
        assert _checks_passed(_validate_record(self.TABLE, self._row()))

    def test_missing_id_is_critical(self):
        row = self._row()
        del row["id"]
        assert _blocking_failures(_validate_record(self.TABLE, row))

    def test_missing_actor_is_critical(self):
        row = self._row()
        del row["actor"]
        assert _blocking_failures(_validate_record(self.TABLE, row))

    def test_missing_action_type_is_critical(self):
        row = self._row()
        del row["action_type"]
        assert _blocking_failures(_validate_record(self.TABLE, row))

    def test_invalid_action_type_enum(self):
        blocks = _blocking_failures(
            _validate_record(self.TABLE, self._row(action_type="UNKNOWN"))
        )
        assert any("enum:action_type" in c.rule for c in blocks)

    @pytest.mark.parametrize("action_type", [
        "ANALYSIS", "PROPOSAL", "APPROVAL", "REJECTION", "ACCESS", "EXECUTION"
    ])
    def test_all_allowed_action_types(self, action_type):
        assert _checks_passed(_validate_record(self.TABLE, self._row(action_type=action_type)))

    def test_invalid_event_type_enum(self):
        blocks = _blocking_failures(
            _validate_record(self.TABLE, self._row(event_type="DELETED"))
        )
        assert any("enum:event_type" in c.rule for c in blocks)

    @pytest.mark.parametrize("event_type", [
        "ACCESS", "ANALYSIS", "PROPOSAL", "APPROVAL", "REJECTION", "EXECUTION"
    ])
    def test_all_allowed_event_types(self, event_type):
        assert _checks_passed(_validate_record(self.TABLE, self._row(event_type=event_type)))

    def test_invalid_status_enum(self):
        blocks = _blocking_failures(
            _validate_record(self.TABLE, self._row(status="PENDING"))
        )
        assert any("enum:status" in c.rule for c in blocks)

    @pytest.mark.parametrize("status", ["OK", "DENIED", "ERROR"])
    def test_all_allowed_statuses(self, status):
        assert _checks_passed(_validate_record(self.TABLE, self._row(status=status)))

    def test_valid_json_metadata(self):
        row = self._row(metadata=json.dumps({"solution": "medtech_team", "test_marker": True}))
        assert _checks_passed(_validate_record(self.TABLE, row))

    def test_invalid_json_metadata_fails(self):
        blocks = _blocking_failures(
            _validate_record(self.TABLE, self._row(metadata="{not: valid json}"))
        )
        assert any("json:metadata" in c.rule for c in blocks)

    def test_null_metadata_allowed(self):
        """metadata is nullable — None should not trigger a JSON check failure."""
        assert _checks_passed(_validate_record(self.TABLE, self._row(metadata=None)))


# =============================================================================
# _validate_record — chat_messages
# =============================================================================

class TestValidateChatMessages:
    TABLE = "chat_messages"

    def _row(self, **overrides):
        base = {
            "id":         "cc000000-ffff-4000-8000-000000000001",
            "user_id":    "test_alice",
            "session_id": "test_session_001",
            "solution":   "medtech_team",
            "role":       "user",
            "content":    "Hello",
            "created_at": "2026-03-28T10:00:00+00:00",
        }
        base.update(overrides)
        return base

    def test_valid_user_turn(self):
        assert _checks_passed(_validate_record(self.TABLE, self._row()))

    def test_valid_assistant_turn(self):
        assert _checks_passed(_validate_record(self.TABLE, self._row(role="assistant")))

    def test_missing_id_is_critical(self):
        row = self._row()
        del row["id"]
        assert _blocking_failures(_validate_record(self.TABLE, row))

    def test_missing_user_id_is_critical(self):
        row = self._row()
        del row["user_id"]
        assert _blocking_failures(_validate_record(self.TABLE, row))

    def test_missing_session_id_is_critical(self):
        row = self._row()
        del row["session_id"]
        assert _blocking_failures(_validate_record(self.TABLE, row))

    def test_missing_solution_is_critical(self):
        row = self._row()
        del row["solution"]
        assert _blocking_failures(_validate_record(self.TABLE, row))

    def test_missing_content_is_critical(self):
        row = self._row()
        del row["content"]
        assert _blocking_failures(_validate_record(self.TABLE, row))

    def test_missing_created_at_is_critical(self):
        row = self._row()
        del row["created_at"]
        assert _blocking_failures(_validate_record(self.TABLE, row))

    def test_invalid_role_enum(self):
        blocks = _blocking_failures(
            _validate_record(self.TABLE, self._row(role="system"))
        )
        assert any("enum:role" in c.rule for c in blocks)

    @pytest.mark.parametrize("role", ["user", "assistant"])
    def test_allowed_roles(self, role):
        assert _checks_passed(_validate_record(self.TABLE, self._row(role=role)))

    def test_invalid_message_type_enum(self):
        blocks = _blocking_failures(
            _validate_record(self.TABLE, self._row(message_type="unknown"))
        )
        assert any("enum:message_type" in c.rule for c in blocks)

    @pytest.mark.parametrize("message_type", ["user", "assistant", "system"])
    def test_allowed_message_types(self, message_type):
        assert _checks_passed(_validate_record(self.TABLE, self._row(message_type=message_type)))


# =============================================================================
# _is_valid — severity routing
# =============================================================================

class TestIsValid:
    def test_valid_audit_row_returns_true(self):
        row = {
            "id": "00000000-ffff-4000-8000-000000000001",
            "actor": "test_AI_Agent",
            "action_type": "ANALYSIS",
        }
        assert _is_valid("compliance_audit_log", row, row["id"]) is True

    def test_critical_failure_blocks_insert(self):
        # Missing required 'id' field
        row = {"actor": "test_AI_Agent", "action_type": "ANALYSIS"}
        assert _is_valid("compliance_audit_log", row, "missing-id") is False

    def test_enum_failure_blocks_insert(self):
        row = {
            "id": "00000000-ffff-4000-8000-000000000001",
            "actor": "test_AI_Agent",
            "action_type": "INVALID_TYPE",
        }
        assert _is_valid("compliance_audit_log", row, row["id"]) is False

    def test_invalid_json_metadata_blocks_insert(self):
        row = {
            "id": "00000000-ffff-4000-8000-000000000001",
            "actor": "test_AI_Agent",
            "action_type": "ANALYSIS",
            "metadata": "not-json",
        }
        assert _is_valid("compliance_audit_log", row, row["id"]) is False

    def test_valid_chat_message_returns_true(self):
        row = {
            "id":         "cc000000-ffff-4000-8000-000000000001",
            "user_id":    "test_alice",
            "session_id": "test_session_x",
            "solution":   "starter",
            "role":       "user",
            "content":    "ping",
            "created_at": "2026-03-28T10:00:00+00:00",
        }
        assert _is_valid("chat_messages", row, row["id"]) is True


# =============================================================================
# Seed constants — schema contract: zero invalid rows in the shipped seeds
# =============================================================================

class TestSeedConstantsAreValid:
    def test_all_audit_events_pass_validation(self):
        """Every row in SEED_AUDIT_EVENTS must pass _is_valid() without skips."""
        for row in SEED_AUDIT_EVENTS:
            result = _is_valid("compliance_audit_log", row, row["id"])
            assert result, f"SEED_AUDIT_EVENTS row {row['id']} failed validation"

    def test_all_chat_messages_pass_validation(self):
        """Every row in SEED_CHAT_MESSAGES must pass _is_valid() without skips."""
        for row in SEED_CHAT_MESSAGES:
            result = _is_valid("chat_messages", row, row["id"])
            assert result, f"SEED_CHAT_MESSAGES row {row['id']} failed validation"

    def test_audit_event_ids_are_unique(self):
        ids = [r["id"] for r in SEED_AUDIT_EVENTS]
        assert len(ids) == len(set(ids)), "Duplicate IDs in SEED_AUDIT_EVENTS"

    def test_chat_message_ids_are_unique(self):
        ids = [r["id"] for r in SEED_CHAT_MESSAGES]
        assert len(ids) == len(set(ids)), "Duplicate IDs in SEED_CHAT_MESSAGES"

    def test_audit_events_test_marker_present(self):
        """All seed rows must carry {"test_marker": true} in metadata."""
        for row in SEED_AUDIT_EVENTS:
            meta = json.loads(row.get("metadata") or "{}")
            assert meta.get("test_marker") is True, (
                f"Row {row['id']} missing test_marker in metadata"
            )

    def test_chat_messages_test_marker_present(self):
        for row in SEED_CHAT_MESSAGES:
            meta = json.loads(row.get("metadata") or "{}")
            assert meta.get("test_marker") is True, (
                f"Row {row['id']} missing test_marker in metadata"
            )


# =============================================================================
# ApiTestDataSeeder — idempotency via in-memory SQLite
# =============================================================================

@pytest.fixture()
def tmp_db(tmp_path):
    """Return path to a fresh temporary SQLite database."""
    return str(tmp_path / "test_audit.db")


class TestApiTestDataSeederIdempotency:
    def test_seed_all_returns_stats_for_all_tables(self, tmp_db):
        seeder = ApiTestDataSeeder(tmp_db)
        stats = seeder.seed_all()
        assert set(stats.keys()) == {"compliance_audit_log", "chat_messages", "proposals"}

    def test_seed_all_inserts_expected_row_counts(self, tmp_db):
        seeder = ApiTestDataSeeder(tmp_db)
        stats = seeder.seed_all()
        assert stats["compliance_audit_log"]["inserted"] == len(SEED_AUDIT_EVENTS)
        assert stats["chat_messages"]["inserted"] == len(SEED_CHAT_MESSAGES)
        assert stats["proposals"]["inserted"] == len(SEED_PROPOSALS)

    def test_seed_all_no_validation_skips(self, tmp_db):
        seeder = ApiTestDataSeeder(tmp_db)
        stats = seeder.seed_all()
        for table, counts in stats.items():
            assert counts["skipped_validation"] == 0, (
                f"{table}: expected 0 validation skips, got {counts}"
            )

    def test_seed_all_is_idempotent(self, tmp_db):
        """Running seed_all() twice must not produce duplicate rows."""
        seeder = ApiTestDataSeeder(tmp_db)
        seeder.seed_all()
        stats2 = seeder.seed_all()   # second run

        # INSERT OR IGNORE — second run must insert 0 new rows
        assert stats2["compliance_audit_log"]["inserted"] == 0, (
            "Second seed_all() inserted rows into compliance_audit_log — not idempotent"
        )
        assert stats2["chat_messages"]["inserted"] == 0, (
            "Second seed_all() inserted rows into chat_messages — not idempotent"
        )
        assert stats2["proposals"]["inserted"] == 0, (
            "Second seed_all() inserted rows into proposals — not idempotent"
        )

    def test_final_row_counts_after_double_seed(self, tmp_db):
        """Row counts in the DB must equal seed constants after two seed runs."""
        seeder = ApiTestDataSeeder(tmp_db)
        seeder.seed_all()
        seeder.seed_all()

        conn = sqlite3.connect(tmp_db)
        audit_count = conn.execute(
            "SELECT COUNT(*) FROM compliance_audit_log WHERE actor LIKE 'test_%'"
        ).fetchone()[0]
        chat_count = conn.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE user_id LIKE 'test_%'"
        ).fetchone()[0]
        proposal_count = conn.execute(
            "SELECT COUNT(*) FROM proposals WHERE proposed_by LIKE 'test_%'"
        ).fetchone()[0]
        conn.close()

        assert audit_count == len(SEED_AUDIT_EVENTS)
        assert chat_count == len(SEED_CHAT_MESSAGES)
        assert proposal_count == len(SEED_PROPOSALS)

    def test_teardown_removes_only_test_rows(self, tmp_db):
        """teardown_all() must delete rows with test_ actor/user_id and nothing else."""
        seeder = ApiTestDataSeeder(tmp_db)
        seeder.seed_all()

        # Insert a non-test row directly
        conn = sqlite3.connect(tmp_db)
        conn.execute("""
            INSERT INTO compliance_audit_log (id, actor, action_type, metadata)
            VALUES ('prod-row-001', 'real_engineer', 'APPROVAL',
                    '{"test_marker": false}')
        """)
        conn.commit()
        conn.close()

        seeder.teardown_all()

        conn = sqlite3.connect(tmp_db)
        test_audit = conn.execute(
            "SELECT COUNT(*) FROM compliance_audit_log WHERE actor LIKE 'test_%'"
        ).fetchone()[0]
        test_chat = conn.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE user_id LIKE 'test_%'"
        ).fetchone()[0]
        test_proposals = conn.execute(
            "SELECT COUNT(*) FROM proposals WHERE proposed_by LIKE 'test_%'"
        ).fetchone()[0]
        prod_row = conn.execute(
            "SELECT COUNT(*) FROM compliance_audit_log WHERE id = 'prod-row-001'"
        ).fetchone()[0]
        conn.close()

        assert test_audit == 0, "teardown_all() left test audit rows"
        assert test_chat == 0, "teardown_all() left test chat rows"
        assert test_proposals == 0, "teardown_all() left test proposal rows"
        assert prod_row == 1, "teardown_all() deleted non-test row"

    def test_teardown_then_reseed_is_idempotent(self, tmp_db):
        """teardown + reseed cycle must produce a clean slate each time."""
        seeder = ApiTestDataSeeder(tmp_db)
        for _ in range(3):
            seeder.seed_all()
            seeder.teardown_all()

        # After final teardown, table must be empty of test rows
        conn = sqlite3.connect(tmp_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM compliance_audit_log WHERE actor LIKE 'test_%'"
        ).fetchone()[0]
        conn.close()
        assert count == 0


# =============================================================================
# Module-level helper functions
# =============================================================================

class TestModuleLevelHelpers:
    def test_seed_all_helper_returns_stats(self, tmp_db):
        stats = seed_all(tmp_db)
        assert "compliance_audit_log" in stats
        assert "chat_messages" in stats

    def test_teardown_all_helper_clears_test_rows(self, tmp_db):
        seed_all(tmp_db)
        teardown_all(tmp_db)
        conn = sqlite3.connect(tmp_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM compliance_audit_log WHERE actor LIKE 'test_%'"
        ).fetchone()[0]
        conn.close()
        assert count == 0


# =============================================================================
# Trace-group coherence (mirrors verify_api_seed_idempotency.sql checks in Python)
# =============================================================================

class TestTraceGroupCoherence:
    @pytest.fixture(autouse=True)
    def _seeded_db(self, tmp_db):
        seed_all(tmp_db)
        self.conn = sqlite3.connect(tmp_db)
        yield
        self.conn.close()

    def _events_for_trace(self, trace_id: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT action_type FROM compliance_audit_log WHERE trace_id = ?",
            (trace_id,),
        ).fetchall()
        return [r[0] for r in rows]

    def test_lifecycle_001_has_analysis_proposal_approval(self):
        events = self._events_for_trace("trace-lifecycle-001")
        assert "ANALYSIS" in events
        assert "PROPOSAL" in events
        assert "APPROVAL" in events

    def test_lifecycle_002_has_analysis_proposal_rejection(self):
        events = self._events_for_trace("trace-lifecycle-002")
        assert "ANALYSIS" in events
        assert "PROPOSAL" in events
        assert "REJECTION" in events

    def test_standalone_003_has_only_analysis(self):
        events = self._events_for_trace("trace-standalone-003")
        assert events == ["ANALYSIS"]

    def test_access_004_has_access_event(self):
        events = self._events_for_trace("trace-access-004")
        assert "ACCESS" in events

    def test_error_005_has_error_status(self):
        row = self.conn.execute(
            "SELECT status FROM compliance_audit_log WHERE trace_id = 'trace-error-005'"
        ).fetchone()
        assert row is not None and row[0] == "ERROR"

    def test_anon_006_has_anonymous_provider(self):
        row = self.conn.execute(
            "SELECT approver_provider FROM compliance_audit_log WHERE trace_id = 'trace-anon-006'"
        ).fetchone()
        assert row is not None and row[0] == "anonymous"

    def test_approval_rows_have_approver_provider(self):
        rows = self.conn.execute(
            "SELECT id, approver_provider FROM compliance_audit_log "
            "WHERE actor LIKE 'test_%' AND action_type = 'APPROVAL'"
        ).fetchall()
        for row_id, provider in rows:
            assert provider is not None, f"APPROVAL row {row_id} missing approver_provider"

    def test_rejection_rows_have_approver_provider(self):
        rows = self.conn.execute(
            "SELECT id, approver_provider FROM compliance_audit_log "
            "WHERE actor LIKE 'test_%' AND action_type = 'REJECTION'"
        ).fetchall()
        for row_id, provider in rows:
            assert provider is not None, f"REJECTION row {row_id} missing approver_provider"


# =============================================================================
# Chat session coherence
# =============================================================================

class TestChatSessionCoherence:
    @pytest.fixture(autouse=True)
    def _seeded_db(self, tmp_db):
        seed_all(tmp_db)
        self.conn = sqlite3.connect(tmp_db)
        yield
        self.conn.close()

    def test_session_001_has_four_messages(self):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE session_id = 'test_session_001'"
        ).fetchone()[0]
        assert count == 4

    def test_session_002_has_four_messages(self):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE session_id = 'test_session_002'"
        ).fetchone()[0]
        assert count == 4

    def test_each_session_has_user_and_assistant_turns(self):
        for session_id in ("test_session_001", "test_session_002"):
            roles = {
                r[0] for r in self.conn.execute(
                    "SELECT DISTINCT role FROM chat_messages WHERE session_id = ?",
                    (session_id,),
                ).fetchall()
            }
            assert "user" in roles, f"{session_id} missing user turn"
            assert "assistant" in roles, f"{session_id} missing assistant turn"

    def test_messages_have_valid_roles(self):
        invalid = self.conn.execute(
            "SELECT id, role FROM chat_messages "
            "WHERE user_id LIKE 'test_%' AND role NOT IN ('user', 'assistant')"
        ).fetchall()
        assert invalid == [], f"Chat messages with invalid roles: {invalid}"


# =============================================================================
# _validate_record — proposals
# =============================================================================

class TestValidateProposals:
    TABLE = "proposals"

    def _row(self, **overrides):
        base = {
            "trace_id":    "test-proposal-x",
            "created_at":  "2026-03-28T10:00:00+00:00",
            "action_type": "yaml_edit",
            "risk_class":  "STATEFUL",
            "reversible":  1,
            "proposed_by": "test_AI_Agent",
            "description": "Test proposal",
            "payload":     json.dumps({"file": "project.yaml"}),
            "status":      "pending",
        }
        base.update(overrides)
        return base

    def test_minimal_valid_row(self):
        assert _checks_passed(_validate_record(self.TABLE, self._row()))

    def test_missing_trace_id_is_critical(self):
        row = self._row()
        del row["trace_id"]
        assert _blocking_failures(_validate_record(self.TABLE, row))

    def test_missing_proposed_by_is_critical(self):
        row = self._row()
        del row["proposed_by"]
        assert _blocking_failures(_validate_record(self.TABLE, row))

    def test_missing_payload_is_critical(self):
        row = self._row()
        del row["payload"]
        assert _blocking_failures(_validate_record(self.TABLE, row))

    def test_invalid_action_type_enum(self):
        blocks = _blocking_failures(
            _validate_record(self.TABLE, self._row(action_type="UNKNOWN"))
        )
        assert any("enum:action_type" in c.rule for c in blocks)

    @pytest.mark.parametrize("action_type", [
        "yaml_edit", "code_diff", "implementation_plan",
        "knowledge_add", "knowledge_delete", "agent_hire",
    ])
    def test_all_allowed_action_types(self, action_type):
        assert _checks_passed(_validate_record(self.TABLE, self._row(action_type=action_type)))

    def test_invalid_risk_class_enum(self):
        blocks = _blocking_failures(
            _validate_record(self.TABLE, self._row(risk_class="UNKNOWN"))
        )
        assert any("enum:risk_class" in c.rule for c in blocks)

    @pytest.mark.parametrize("risk_class", [
        "INFORMATIONAL", "EPHEMERAL", "STATEFUL", "EXTERNAL", "DESTRUCTIVE",
    ])
    def test_all_allowed_risk_classes(self, risk_class):
        assert _checks_passed(_validate_record(self.TABLE, self._row(risk_class=risk_class)))

    @pytest.mark.parametrize("status", ["pending", "approved", "rejected", "expired"])
    def test_all_allowed_statuses(self, status):
        assert _checks_passed(_validate_record(self.TABLE, self._row(status=status)))

    def test_invalid_status_enum(self):
        blocks = _blocking_failures(
            _validate_record(self.TABLE, self._row(status="UNKNOWN"))
        )
        assert any("enum:status" in c.rule for c in blocks)

    def test_invalid_json_payload_fails(self):
        blocks = _blocking_failures(
            _validate_record(self.TABLE, self._row(payload="{not valid json}"))
        )
        assert any("json:payload" in c.rule for c in blocks)

    def test_null_payload_treated_as_valid_json(self):
        """payload=None skips JSON check (nullable path in _json_valid)."""
        row = self._row()
        row["payload"] = None
        # missing payload triggers required check but not json check
        # (payload IS required — this row should fail required, not json)
        checks = _validate_record(self.TABLE, row)
        json_checks = [c for c in checks if "json:payload" in c.rule]
        assert all(c.passed for c in json_checks), "json check should pass when payload is None"


# =============================================================================
# Seed constants — proposals schema contract
# =============================================================================

class TestSeedProposalsAreValid:
    def test_all_proposals_pass_validation(self):
        for row in SEED_PROPOSALS:
            result = _is_valid("proposals", row, row["trace_id"])
            assert result, f"SEED_PROPOSALS row {row['trace_id']} failed validation"

    def test_proposal_trace_ids_are_unique(self):
        ids = [r["trace_id"] for r in SEED_PROPOSALS]
        assert len(ids) == len(set(ids)), "Duplicate trace_ids in SEED_PROPOSALS"

    def test_payload_fields_are_valid_json(self):
        for row in SEED_PROPOSALS:
            try:
                json.loads(row["payload"])
            except (TypeError, json.JSONDecodeError) as exc:
                pytest.fail(f"SEED_PROPOSALS row {row['trace_id']} has invalid payload JSON: {exc}")

    def test_approved_rows_have_decided_by(self):
        for row in SEED_PROPOSALS:
            if row.get("status") == "approved":
                assert row.get("decided_by"), (
                    f"Approved proposal {row['trace_id']} missing decided_by"
                )

    def test_rejected_rows_have_feedback(self):
        for row in SEED_PROPOSALS:
            if row.get("status") == "rejected":
                assert row.get("feedback"), (
                    f"Rejected proposal {row['trace_id']} missing feedback"
                )

    def test_expired_rows_have_past_expires_at(self):
        for row in SEED_PROPOSALS:
            if row.get("status") == "expired":
                assert row.get("expires_at"), (
                    f"Expired proposal {row['trace_id']} missing expires_at"
                )
                # expires_at must be in the past relative to seed timestamp
                assert row["expires_at"] < row["created_at"] or row["expires_at"] <= "2026-03-28T10:00:00+00:00", (
                    f"Expired proposal {row['trace_id']} has future expires_at"
                )

    def test_all_risk_classes_represented(self):
        risk_classes = {r["risk_class"] for r in SEED_PROPOSALS}
        assert "STATEFUL" in risk_classes
        assert "EXTERNAL" in risk_classes
        assert "EPHEMERAL" in risk_classes

    def test_all_statuses_represented(self):
        statuses = {r["status"] for r in SEED_PROPOSALS}
        assert statuses == {"pending", "approved", "rejected", "expired"}


# =============================================================================
# Proposal group coherence (seeded via in-memory SQLite)
# =============================================================================

class TestProposalGroupCoherence:
    @pytest.fixture(autouse=True)
    def _seeded_db(self, tmp_db):
        seed_all(tmp_db)
        self.conn = sqlite3.connect(tmp_db)
        yield
        self.conn.close()

    def _proposal(self, trace_id: str):
        return self.conn.execute(
            "SELECT * FROM proposals WHERE trace_id = ?", (trace_id,)
        ).fetchone()

    def test_pending_yaml_edit_exists(self):
        row = self._proposal("test-proposal-001")
        assert row is not None
        assert row[8] == "pending"    # status column index
        assert row[2] == "yaml_edit"  # action_type

    def test_pending_code_diff_has_required_role(self):
        row = self._proposal("test-proposal-002")
        assert row is not None
        assert row[2] == "code_diff"
        # required_role is column 13
        assert row[13] == "firmware_engineer"

    def test_approved_proposal_has_decided_by(self):
        row = self._proposal("test-proposal-003")
        assert row is not None
        assert row[8] == "approved"
        assert row[9] == "carol_test"   # decided_by

    def test_rejected_proposal_has_feedback(self):
        row = self._proposal("test-proposal-004")
        assert row is not None
        assert row[8] == "rejected"
        assert row[11] is not None and row[11] != ""  # feedback

    def test_expired_proposal_has_past_expires_at(self):
        row = self._proposal("test-proposal-005")
        assert row is not None
        assert row[8] == "expired"
        expires_at = row[12]
        assert expires_at is not None
        assert expires_at <= "2026-03-28T10:00:00+00:00"

    def test_proposals_count(self):
        count = self.conn.execute(
            "SELECT COUNT(*) FROM proposals WHERE proposed_by LIKE 'test_%'"
        ).fetchone()[0]
        assert count == len(SEED_PROPOSALS)

    def test_pending_proposals_have_no_decided_at(self):
        rows = self.conn.execute(
            "SELECT trace_id, decided_at FROM proposals "
            "WHERE proposed_by LIKE 'test_%' AND status = 'pending'"
        ).fetchall()
        for trace_id, decided_at in rows:
            assert decided_at is None, f"Pending proposal {trace_id} should not have decided_at"

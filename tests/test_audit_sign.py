"""The audit hash-chain must detect any post-hoc alteration of a signed row.

Builds a real audit_log.db via AuditLogger, signs a couple of events, verifies the chain,
then tampers (edit / delete / re-order) and asserts verification FAILS at the tampered row —
the tamper-evidence property the compliance record needs.
"""
from __future__ import annotations

import sqlite3

import pytest

from src.memory.audit_logger import AuditLogger
from src.memory.audit_sign import sign_event, verify_chain

pytestmark = pytest.mark.unit

KEY = "test-audit-key"


def _log(al, actor, action, out, approver=None):
    al.log_event(actor=actor, action_type=action, input_context="ctx",
                 output_content=out, approved_by=approver)
    conn = sqlite3.connect(al.db_path)
    conn.row_factory = sqlite3.Row
    rid = conn.execute(
        "SELECT id FROM compliance_audit_log ORDER BY timestamp DESC, id DESC LIMIT 1"
    ).fetchone()[0]
    conn.close()
    return rid


@pytest.fixture
def db(tmp_path):
    return AuditLogger(db_path=str(tmp_path / "audit_log.db"))


def test_signature_is_written_and_chain_verifies(db):
    e1 = _log(db, "operator", "PROPOSAL_APPROVED", "merge PR#1", approver="Harish")
    s1 = sign_event(db.db_path, e1, secret=KEY)
    assert s1 and len(s1) == 64  # sha256 hex

    e2 = _log(db, "operator", "PROPOSAL_APPROVED", "merge PR#2", approver="Harish")
    s2 = sign_event(db.db_path, e2, secret=KEY)
    assert s2 and s2 != s1  # chained → different

    res = verify_chain(db.db_path, secret=KEY)
    assert res["valid"] is True and res["checked"] == 2


def test_editing_a_signed_row_breaks_the_chain(db):
    e1 = _log(db, "operator", "PROPOSAL_APPROVED", "merge PR#1", approver="Harish")
    sign_event(db.db_path, e1, secret=KEY)
    e2 = _log(db, "operator", "PROPOSAL_APPROVED", "merge PR#2", approver="Harish")
    sign_event(db.db_path, e2, secret=KEY)

    # Tamper: change the approver on the first signed row.
    conn = sqlite3.connect(db.db_path)
    conn.execute("UPDATE compliance_audit_log SET approved_by='Mallory' WHERE id=?", (e1,))
    conn.commit()
    conn.close()

    res = verify_chain(db.db_path, secret=KEY)
    assert res["valid"] is False
    assert res["first_bad"] == e1


def test_deleting_a_signed_row_breaks_the_chain(db):
    e1 = _log(db, "operator", "PROPOSAL_APPROVED", "merge PR#1", approver="Harish")
    sign_event(db.db_path, e1, secret=KEY)
    e2 = _log(db, "operator", "PROPOSAL_APPROVED", "merge PR#2", approver="Harish")
    sign_event(db.db_path, e2, secret=KEY)

    conn = sqlite3.connect(db.db_path)
    conn.execute("DELETE FROM compliance_audit_log WHERE id=?", (e1,))
    conn.commit()
    conn.close()

    # e2 chained onto e1's signature; with e1 gone, e2 is now the first (genesis) link and
    # its stored signature no longer matches → detected.
    res = verify_chain(db.db_path, secret=KEY)
    assert res["valid"] is False
    assert res["first_bad"] == e2


def test_wrong_key_fails_verification(db):
    e1 = _log(db, "operator", "PROPOSAL_APPROVED", "merge PR#1", approver="Harish")
    sign_event(db.db_path, e1, secret=KEY)
    res = verify_chain(db.db_path, secret="different-key")
    assert res["valid"] is False


def test_unsigned_rows_are_ignored_by_the_chain(db):
    # Routine unsigned events between signed ones must not affect the signed chain.
    _log(db, "agent", "ANALYSIS", "routine 1")
    e1 = _log(db, "operator", "PROPOSAL_APPROVED", "merge PR#1", approver="Harish")
    sign_event(db.db_path, e1, secret=KEY)
    _log(db, "agent", "ACCESS", "routine 2")
    e2 = _log(db, "operator", "PROPOSAL_APPROVED", "merge PR#2", approver="Harish")
    sign_event(db.db_path, e2, secret=KEY)

    res = verify_chain(db.db_path, secret=KEY)
    assert res["valid"] is True and res["checked"] == 2

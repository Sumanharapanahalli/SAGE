"""Tamper-evident signing for the compliance audit log.

The audit log is SAGE's regulatory record, but `verification_signature` has always been a
NULL placeholder (audit_logger.py never writes it). For the Merge-Gate Governance model a
merge-to-main is a signed, reviewable release event, so this module fills that column with an
HMAC-SHA256 signature chained to the previous signed row — a hash chain. Editing, deleting,
or re-ordering any signed row after the fact breaks every signature from that point on, which
is exactly the property a regulated auditor needs (21 CFR Part 11 §11.10: detect record
alteration).

Scope note: signed rows form their OWN chain. The log holds many unsigned rows (access,
analysis, routine proposals); those are untouched. Only compliance-significant events — a
merge, an approval — are signed, and they chain to each other regardless of the unsigned rows
between them.

Key management: the HMAC key comes from `SAGE_AUDIT_KEY` if set, else a per-solution key file
`<db_dir>/audit_hmac.key` generated once with `os.urandom(32)`. The local key already gives
tamper-evidence against anyone who edits the DB without the key. A production regulated
deployment SHOULD supply `SAGE_AUDIT_KEY` from an HSM/KMS rather than the local file — that is
a deployment decision, documented, not a code gap.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("AuditSign")

_GENESIS = "SAGE-AUDIT-CHAIN-GENESIS"

# The immutable identity of an event, in a FIXED order. Any change to any of these fields
# after signing must break the signature — so the canonical form covers exactly the columns
# an auditor cares about, and nothing volatile.
_SIGNED_FIELDS = (
    "id", "timestamp", "actor", "action_type",
    "input_context", "output_content", "metadata",
    "approved_by", "approver_role", "approver_email", "approver_provider",
)


def _resolve_key(db_path: str) -> bytes:
    """Env override wins; otherwise a per-solution key file created once beside the db."""
    env = os.environ.get("SAGE_AUDIT_KEY")
    if env:
        return env.encode("utf-8")
    key_file = Path(db_path).parent / "audit_hmac.key"
    if key_file.exists():
        return key_file.read_bytes()
    key = os.urandom(32)
    try:
        key_file.write_bytes(key)
        # Best-effort tighten perms; harmless if the platform ignores it.
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
        logger.info("generated audit HMAC key at %s", key_file)
    except OSError as e:  # noqa: BLE001
        logger.warning("could not persist audit key (%s); using an ephemeral key — "
                       "the chain will not verify across processes", e)
    return key


def _canonical(row: dict) -> str:
    """Deterministic serialization of the signed fields. json.dumps escapes every value, so
    no field content can forge a separator or collide with another field."""
    return json.dumps([("" if row.get(f) is None else str(row.get(f))) for f in _SIGNED_FIELDS],
                      ensure_ascii=False, separators=(",", ":"))


def _compute(key: bytes, prev_sig: str, row: dict) -> str:
    msg = (prev_sig or _GENESIS).encode("utf-8") + b"|" + _canonical(row).encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def _connect(db_path: str):
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _latest_signed_sig(conn) -> str:
    """The signature of the most-recently-signed row — the link this new row chains onto."""
    cur = conn.execute(
        "SELECT verification_signature FROM compliance_audit_log "
        "WHERE verification_signature IS NOT NULL AND verification_signature != '' "
        "ORDER BY timestamp DESC, id DESC LIMIT 1"
    )
    r = cur.fetchone()
    return r[0] if r else ""


def sign_event(db_path: str, event_id: str, secret: Optional[str] = None) -> Optional[str]:
    """Sign a single already-written audit row, chaining it to the previous signed row.

    Returns the signature hex, or None if the row does not exist. Call serially (the merge
    gate does): two concurrent signers could both read the same `prev`, forking the chain.
    """
    key = secret.encode("utf-8") if secret else _resolve_key(db_path)
    conn = _connect(db_path)
    try:
        cur = conn.execute("SELECT * FROM compliance_audit_log WHERE id = ?", (event_id,))
        row = cur.fetchone()
        if row is None:
            logger.warning("sign_event: no audit row %s", event_id)
            return None
        row = dict(row)
        prev = _latest_signed_sig(conn)
        sig = _compute(key, prev, row)
        conn.execute(
            "UPDATE compliance_audit_log SET verification_signature = ? WHERE id = ?",
            (sig, event_id),
        )
        conn.commit()
        logger.info("signed audit event %s (chained to %s)", event_id, (prev or "GENESIS")[:12])
        return sig
    finally:
        conn.close()


def verify_chain(db_path: str, secret: Optional[str] = None) -> dict:
    """Recompute every signed row's signature in chain order.

    Returns {"valid": bool, "checked": int, "first_bad": <event_id>|None, "reason": str}.
    A broken link means a signed row was altered, deleted, or re-ordered after signing.
    """
    key = secret.encode("utf-8") if secret else _resolve_key(db_path)
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "SELECT * FROM compliance_audit_log "
            "WHERE verification_signature IS NOT NULL AND verification_signature != '' "
            "ORDER BY timestamp ASC, id ASC"
        )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    prev = ""
    for row in rows:
        expected = _compute(key, prev, row)
        if not hmac.compare_digest(expected, row.get("verification_signature", "")):
            return {"valid": False, "checked": len(rows), "first_bad": row["id"],
                    "reason": "signature mismatch — row altered, deleted, or re-ordered "
                              "after signing (or a different key)"}
        prev = row["verification_signature"]
    return {"valid": True, "checked": len(rows), "first_bad": None, "reason": "ok"}

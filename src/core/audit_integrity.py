"""
Cryptographic Audit Log Integrity
==================================
HMAC-based hash chain for 21 CFR Part 11 and IEC 62304 compliance.

Each audit entry gets an HMAC computed over its content + the previous entry's
HMAC, forming an unbroken chain. Any tampering (insertion, deletion, modification)
breaks the chain and is detectable by verify_chain().

This is a companion to audit_logger.py — it adds integrity verification on top
of the existing audit log without modifying the core logging flow.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from src.core.db import get_connection

logger = logging.getLogger(__name__)

# Default HMAC key — in production, set SAGE_AUDIT_HMAC_KEY env var
_DEFAULT_KEY = "sage-audit-integrity-default-key"


def _get_hmac_key() -> bytes:
    """Get the HMAC signing key from environment or default."""
    key = os.environ.get("SAGE_AUDIT_HMAC_KEY", _DEFAULT_KEY)
    return key.encode("utf-8")


def compute_hmac(data: str, previous_hmac: str = "") -> str:
    """Compute HMAC-SHA256 over data + previous chain HMAC."""
    key = _get_hmac_key()
    message = f"{previous_hmac}:{data}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


class AuditIntegrityManager:
    """
    Manages cryptographic hash chain for the audit log.

    Storage: adds an `integrity_chain` table alongside the existing
    compliance_audit_log table in the same database.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = get_connection(self.db_path, row_factory=None)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS integrity_chain (
                sequence_num INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_event_id TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                previous_hmac TEXT NOT NULL DEFAULT '',
                chain_hmac TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chain_event ON integrity_chain(audit_event_id)"
        )
        conn.commit()
        conn.close()

    def get_last_hmac(self) -> str:
        """Get the HMAC of the last entry in the chain."""
        conn = get_connection(self.db_path, row_factory=None)
        row = conn.execute(
            "SELECT chain_hmac FROM integrity_chain ORDER BY sequence_num DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return row[0] if row else ""

    def append_entry(self, audit_event_id: str, event_data: dict) -> dict:
        """
        Append a new entry to the integrity chain.

        Args:
            audit_event_id: ID of the audit log entry being chained
            event_data: dict of the audit event content to hash

        Returns:
            dict with sequence_num, chain_hmac
        """
        content_hash = hashlib.sha256(
            json.dumps(event_data, sort_keys=True).encode("utf-8")
        ).hexdigest()

        previous_hmac = self.get_last_hmac()
        chain_hmac = compute_hmac(content_hash, previous_hmac)
        now = datetime.now(timezone.utc).isoformat()

        conn = get_connection(self.db_path, row_factory=None)
        cursor = conn.execute(
            """INSERT INTO integrity_chain
               (audit_event_id, event_timestamp, content_hash, previous_hmac, chain_hmac, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (audit_event_id, now, content_hash, previous_hmac, chain_hmac, now),
        )
        sequence_num = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info("Integrity chain entry #%d for event %s", sequence_num, audit_event_id)
        return {"sequence_num": sequence_num, "chain_hmac": chain_hmac}

    def verify_chain(self) -> dict:
        """
        Verify the entire hash chain for tampering.

        Returns:
            dict with:
              - valid: bool
              - total_entries: int
              - verified_entries: int
              - first_broken_at: Optional[int] — sequence_num where chain breaks
              - details: str
        """
        conn = get_connection(self.db_path, row_factory=None)
        rows = conn.execute(
            "SELECT sequence_num, audit_event_id, content_hash, previous_hmac, chain_hmac "
            "FROM integrity_chain ORDER BY sequence_num ASC"
        ).fetchall()
        conn.close()

        if not rows:
            return {
                "valid": True,
                "total_entries": 0,
                "verified_entries": 0,
                "first_broken_at": None,
                "details": "No entries in chain",
            }

        expected_previous = ""
        verified = 0

        for row in rows:
            seq_num, event_id, content_hash, prev_hmac, stored_hmac = row

            # Check previous_hmac matches what we expect
            if prev_hmac != expected_previous:
                return {
                    "valid": False,
                    "total_entries": len(rows),
                    "verified_entries": verified,
                    "first_broken_at": seq_num,
                    "details": f"Previous HMAC mismatch at sequence {seq_num} (event {event_id})",
                }

            # Recompute HMAC and verify
            expected_hmac = compute_hmac(content_hash, prev_hmac)
            if expected_hmac != stored_hmac:
                return {
                    "valid": False,
                    "total_entries": len(rows),
                    "verified_entries": verified,
                    "first_broken_at": seq_num,
                    "details": f"HMAC verification failed at sequence {seq_num} (event {event_id})",
                }

            expected_previous = stored_hmac
            verified += 1

        return {
            "valid": True,
            "total_entries": len(rows),
            "verified_entries": verified,
            "first_broken_at": None,
            "details": f"All {verified} entries verified successfully",
        }

    def get_chain_status(self) -> dict:
        """Get summary of the integrity chain."""
        conn = get_connection(self.db_path, row_factory=None)
        count = conn.execute("SELECT COUNT(*) FROM integrity_chain").fetchone()[0]
        first = conn.execute(
            "SELECT created_at FROM integrity_chain ORDER BY sequence_num ASC LIMIT 1"
        ).fetchone()
        last = conn.execute(
            "SELECT created_at FROM integrity_chain ORDER BY sequence_num DESC LIMIT 1"
        ).fetchone()
        conn.close()

        return {
            "total_entries": count,
            "first_entry_at": first[0] if first else None,
            "last_entry_at": last[0] if last else None,
            "chain_active": count > 0,
        }

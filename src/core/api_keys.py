"""
SAGE API Key management.

Key format: sk-sage-{32 random hex chars}
Only SHA-256 hash stored — plain key shown once and discarded.
Table: api_keys in the same data/audit_log.db as audit log and proposals.
"""

import hashlib
import logging
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.auth import UserIdentity

logger = logging.getLogger(__name__)

_PREFIX = "sk-sage-"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _db_path() -> str:
    from src.memory.audit_logger import audit_logger
    return audit_logger.db_path


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id          TEXT PRIMARY KEY,
            key_hash    TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL,
            solution    TEXT NOT NULL,
            role        TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            revoked     INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_api_key(name: str, email: str, solution: str, role: str) -> tuple[str, str]:
    """
    Generate a new API key.

    Returns (plain_key, key_id). The plain key is shown once — only its
    SHA-256 hash is persisted.
    """
    _ensure_table()
    plain_key = _PREFIX + secrets.token_hex(32)
    key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
    key_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    conn = _get_conn()
    conn.execute(
        """INSERT INTO api_keys (id, key_hash, name, email, solution, role, created_at, revoked)
           VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
        (key_id, key_hash, name, email, solution, role, created_at),
    )
    conn.commit()
    conn.close()
    logger.info("API key created: id=%s name=%s email=%s solution=%s role=%s", key_id, name, email, solution, role)
    return plain_key, key_id


def verify_api_key(plain_key: str) -> Optional["UserIdentity"]:
    """
    Look up a plain key by its SHA-256 hash.
    Returns a UserIdentity on success, None if not found or revoked.
    """
    from src.core.auth import UserIdentity  # local import to avoid circular
    _ensure_table()
    key_hash = hashlib.sha256(plain_key.encode()).hexdigest()
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM api_keys WHERE key_hash=? AND revoked=0",
        (key_hash,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return UserIdentity(
        sub=row["id"],
        email=row["email"],
        name=row["name"],
        role=row["role"],
        provider="api_key",
    )


def revoke_api_key(key_id: str, revoked_by: str) -> bool:
    """Mark a key as revoked. Returns True if a row was updated."""
    _ensure_table()
    conn = _get_conn()
    cur = conn.execute(
        "UPDATE api_keys SET revoked=1 WHERE id=? AND revoked=0",
        (key_id,),
    )
    conn.commit()
    conn.close()
    updated = cur.rowcount > 0
    if updated:
        logger.info("API key revoked: id=%s by=%s", key_id, revoked_by)
    return updated


def list_api_keys(solution: str) -> list[dict]:
    """Return all API keys for a given solution (hashes excluded)."""
    _ensure_table()
    conn = _get_conn()
    rows = conn.execute(
        """SELECT id, name, email, solution, role, created_at, revoked
           FROM api_keys WHERE solution=? ORDER BY created_at DESC""",
        (solution,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

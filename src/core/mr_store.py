"""
SAGE Merge-Gate Governance — Merge Request Store
================================================

Per-solution SQLite record of Merge Requests (MRs) for the Merge-Gate
Governance feature. Each MR tracks a work item through its lifecycle:

    coding → gating → review → reworking → approved → merged
                                                    ↘ failed

Follows the framework store convention: a short-lived ``sqlite3`` connection
per call (via :func:`src.core.db.get_connection`), ``CREATE TABLE IF NOT
EXISTS`` in ``__init__``, uuid ids, and UTC ISO timestamps.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.core.db import get_connection

logger = logging.getLogger(__name__)


# Valid states, in order:
MR_STATES = ["coding", "gating", "review", "reworking", "approved", "merged", "failed"]

# Fields that callers may mutate via ``update``. Deliberately excludes
# id / work_item / branch / created_at (immutable) and updated_at (auto-bumped).
# `branch` is updatable so the caller can set it to the worktree's actual branch name
# (`proposal/<mr_id[:8]>`, derived from the id that create() generates) after creation.
_UPDATABLE_FIELDS = {"branch", "state", "pr_number", "pr_url", "evidence", "merged_sha", "error"}


class MRStore:
    """SQLite-backed registry of Merge Requests for one solution.

    Thread-safe enough for SQLite — every method opens and closes its own
    short-lived connection.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # Schema init
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS merge_requests (
                    id          TEXT PRIMARY KEY,
                    work_item   TEXT,
                    branch      TEXT,
                    state       TEXT,
                    pr_number   INTEGER,
                    pr_url      TEXT,
                    evidence    TEXT DEFAULT '{}',
                    merged_sha  TEXT,
                    error       TEXT,
                    created_at  TEXT,
                    updated_at  TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()
        logger.debug("MRStore table ready at %s", self.db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _row_to_dict(self, row) -> dict:
        return {
            "id": row["id"],
            "work_item": row["work_item"],
            "branch": row["branch"],
            "state": row["state"],
            "pr_number": row["pr_number"],
            "pr_url": row["pr_url"],
            "evidence": json.loads(row["evidence"] or "{}"),
            "merged_sha": row["merged_sha"],
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, work_item: str, branch: str) -> str:
        """Insert a new MR in state ``coding``; return the generated mr_id."""
        mr_id = uuid.uuid4().hex
        now = self._now()
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                """INSERT INTO merge_requests
                   (id, work_item, branch, state, pr_number, pr_url,
                    evidence, merged_sha, error, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (mr_id, work_item, branch, "coding", None, None,
                 "{}", None, None, now, now),
            )
            conn.commit()
        finally:
            conn.close()
        logger.info("MR created: %s [%s] on %s", mr_id, work_item, branch)
        return mr_id

    def get(self, mr_id: str) -> Optional[dict]:
        """Full row as a dict (evidence parsed to dict); None if not found."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM merge_requests WHERE id = ?", (mr_id,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def list(self, state: str = "") -> list[dict]:
        """All MRs (newest first), optionally filtered by ``state``."""
        conn = get_connection(self.db_path)
        try:
            if state:
                rows = conn.execute(
                    """SELECT * FROM merge_requests
                       WHERE state = ?
                       ORDER BY created_at DESC, rowid DESC""",
                    (state,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM merge_requests
                       ORDER BY created_at DESC, rowid DESC"""
                ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def update(self, mr_id: str, **fields) -> None:
        """Update any of state / pr_number / pr_url / evidence / merged_sha /
        error, always bumping ``updated_at``.

        Raises ``ValueError`` on an unknown field name (guards against a typo
        silently no-oping) or an invalid ``state`` value.
        """
        # Validate everything BEFORE touching the database, so a rejected
        # call never partially writes or bumps updated_at.
        for key in fields:
            if key not in _UPDATABLE_FIELDS:
                raise ValueError(f"Unknown MR field: {key!r}")
        if "state" in fields and fields["state"] not in MR_STATES:
            raise ValueError(f"Invalid MR state: {fields['state']!r}")

        sets = []
        params: list = []
        for key, value in fields.items():
            if key == "evidence":
                sets.append("evidence = ?")
                params.append(json.dumps(value))
            else:
                sets.append(f"{key} = ?")
                params.append(value)

        sets.append("updated_at = ?")
        params.append(self._now())
        params.append(mr_id)

        conn = get_connection(self.db_path)
        try:
            conn.execute(
                f"UPDATE merge_requests SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            conn.commit()
        finally:
            conn.close()

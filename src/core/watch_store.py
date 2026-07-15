"""
SAGE Merge-Gate Governance — Watcher State Store
================================================

Durable state for the admin watcher — the piece that makes reacting to a PR
comment survive logoff, crash, and reboot. Without it, a restarted watcher
cannot tell a comment it already handled from a new one, and would either
re-rework the same comment forever or drop it.

Three concerns, all in a per-solution ``.sage/watch.db``:

* **handled_comments** — every ``(mr_id, comment_id)`` the watcher has already
  acted on. This is what makes reacting IDEMPOTENT: a restarted watcher re-reads
  this table and never reworks the same comment twice.
* **watch_cursor** — per-MR bookkeeping: rework count and the last review
  decision acted on, so the watcher resumes exactly where it stopped.
* **watch_lease** — which process currently owns the watch on an MR, so the Pi
  daemon and a desktop watcher never double-act (single-writer). Leases expire,
  so a crashed owner never wedges an MR forever.

Follows the framework store convention (see :mod:`src.core.mr_store`): a
short-lived ``sqlite3`` connection per call via :func:`src.core.db.get_connection`,
``CREATE TABLE IF NOT EXISTS`` in ``__init__``, and UTC ISO timestamps.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.core.db import get_connection

logger = logging.getLogger(__name__)


class WatchStore:
    """SQLite-backed durable state for one solution's MR watcher.

    Thread- and process-safe enough for SQLite — every method opens and closes
    its own short-lived WAL connection.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS handled_comments (
                    mr_id       TEXT,
                    comment_id  TEXT,
                    handled_at  TEXT,
                    PRIMARY KEY (mr_id, comment_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS watch_cursor (
                    mr_id         TEXT PRIMARY KEY,
                    rework_count  INTEGER DEFAULT 0,
                    last_decision TEXT DEFAULT '',
                    updated_at    TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS watch_lease (
                    mr_id      TEXT PRIMARY KEY,
                    owner      TEXT,
                    expires_at TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()
        logger.debug("WatchStore tables ready at %s", self.db_path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Idempotent comment handling
    # ------------------------------------------------------------------

    def handled(self, mr_id: str, comment_id: str) -> bool:
        """True if ``(mr_id, comment_id)`` has already been acted on."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM handled_comments WHERE mr_id = ? AND comment_id = ?",
                (mr_id, str(comment_id)),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def mark_handled(self, mr_id: str, comment_id: str) -> None:
        """Record ``(mr_id, comment_id)`` as handled. Idempotent (INSERT OR IGNORE)."""
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO handled_comments (mr_id, comment_id, handled_at) "
                "VALUES (?, ?, ?)",
                (mr_id, str(comment_id), self._now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Per-MR cursor
    # ------------------------------------------------------------------

    def get_cursor(self, mr_id: str) -> dict:
        """Return ``{rework_count, last_decision}`` for an MR (defaults if unseen)."""
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT rework_count, last_decision FROM watch_cursor WHERE mr_id = ?",
                (mr_id,),
            ).fetchone()
            if row is None:
                return {"rework_count": 0, "last_decision": ""}
            return {
                "rework_count": row["rework_count"] or 0,
                "last_decision": row["last_decision"] or "",
            }
        finally:
            conn.close()

    def bump_rework(self, mr_id: str) -> int:
        """Increment and return the MR's rework count."""
        current = self.get_cursor(mr_id)["rework_count"]
        new = current + 1
        self._upsert_cursor(mr_id, rework_count=new)
        return new

    def set_decision(self, mr_id: str, decision: str) -> None:
        """Record the last review decision the watcher acted on."""
        self._upsert_cursor(mr_id, last_decision=decision or "")

    def _upsert_cursor(self, mr_id: str, **fields) -> None:
        cur = self.get_cursor(mr_id)
        rework_count = fields.get("rework_count", cur["rework_count"])
        last_decision = fields.get("last_decision", cur["last_decision"])
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO watch_cursor (mr_id, rework_count, last_decision, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(mr_id) DO UPDATE SET
                    rework_count = excluded.rework_count,
                    last_decision = excluded.last_decision,
                    updated_at = excluded.updated_at
                """,
                (mr_id, rework_count, last_decision, self._now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Single-writer lease
    # ------------------------------------------------------------------

    def acquire(self, mr_id: str, owner: str, ttl_seconds: int = 900) -> bool:
        """Acquire the watch lease on ``mr_id`` for ``owner``.

        Succeeds if the MR is unleased, already owned by ``owner``, or the
        current lease has expired. Returns False if another live owner holds it.
        A short-lived connection with WAL + busy_timeout serialises the
        check-and-set enough for the two-process (Pi daemon + desktop) case.
        """
        now = self._now()
        expires = (now + timedelta(seconds=int(ttl_seconds))).isoformat()
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT owner, expires_at FROM watch_lease WHERE mr_id = ?", (mr_id,)
            ).fetchone()
            if row is not None:
                held_by = row["owner"]
                still_live = self._is_future(row["expires_at"], now)
                if held_by != owner and still_live:
                    return False  # another live owner holds it
            conn.execute(
                """
                INSERT INTO watch_lease (mr_id, owner, expires_at) VALUES (?, ?, ?)
                ON CONFLICT(mr_id) DO UPDATE SET
                    owner = excluded.owner, expires_at = excluded.expires_at
                """,
                (mr_id, owner, expires),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def release(self, mr_id: str, owner: str) -> None:
        """Release the lease if (and only if) ``owner`` holds it."""
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "DELETE FROM watch_lease WHERE mr_id = ? AND owner = ?", (mr_id, owner)
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _is_future(iso_ts: Optional[str], now: datetime) -> bool:
        if not iso_ts:
            return False
        try:
            return datetime.fromisoformat(iso_ts) > now
        except (ValueError, TypeError):
            return False

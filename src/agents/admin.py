"""
SAGE[ai] — Admin Agent (per-solution housekeeping)
==================================================

Keeps a solution's `.sage/audit_log.db` tidy without ever weakening the
compliance record:

  - prune **expired / rejected** proposals older than a retention window
    (and transition pending proposals past their `expires_at` to `expired`)
  - prune **completed / failed** tasks older than a retention window
  - VACUUM the SQLite DB to reclaim space
  - report counts + DB size

Hard invariant — the audit trail is a compliance asset (see the constitution,
"the audit trail is never weakened for convenience"): this agent **never**
deletes or rewrites `compliance_audit_log` rows. Its only mutating statements
target the `proposals` and `task_queue` tables.

Ethic — agents propose, humans dispose: every destructive operation defaults to
`dry_run=True`, returning a plan of what *would* change. Pass `dry_run=False`
to apply it (e.g. after a human approves the plan).

Scope — the agent is per-solution: with no explicit `db_path` it resolves the
active solution's `<solution>/.sage/audit_log.db` (same path the audit logger,
proposal store, and task queue use), so housekeeping is naturally scoped to one
solution at a time.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("AdminAgent")

# Tables the agent is allowed to mutate. compliance_audit_log is deliberately
# absent — it is read-only to housekeeping, forever.
_MUTABLE_TABLES = ("proposals", "task_queue")
_AUDIT_TABLE = "compliance_audit_log"

# Proposal statuses that are "done" and therefore prunable once old enough.
_PRUNABLE_PROPOSAL_STATUSES = ("expired", "rejected")
# Task statuses that are terminal and therefore prunable once old enough.
_PRUNABLE_TASK_STATUSES = ("completed", "failed")


def _now_iso(now: Optional[datetime]) -> str:
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _cutoff_iso(now: Optional[datetime], retention_days: int) -> str:
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt - timedelta(days=retention_days)).isoformat()


class AdminAgent:
    """Per-solution housekeeping agent. See module docstring."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Resolve the active solution's audit DB (same resolution the audit
            # logger uses), so housekeeping is scoped to the current solution.
            from src.memory.audit_logger import AuditLogger
            db_path = AuditLogger().db_path
        self.db_path = db_path
        self.logger = logging.getLogger("AdminAgent")

    # ------------------------------------------------------------------ utils
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _table_exists(self, conn: sqlite3.Connection, name: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        return row is not None

    def _counts_by_status(self, conn: sqlite3.Connection, table: str) -> dict:
        if not self._table_exists(conn, table):
            return {}
        out: dict = {}
        for r in conn.execute(f"SELECT status, COUNT(*) AS c FROM {table} GROUP BY status"):
            out[r["status"]] = r["c"]
        return out

    # ----------------------------------------------------------------- report
    def report(self) -> dict:
        """Read-only snapshot of the solution's housekeeping state. Safe anytime."""
        conn = self._connect()
        try:
            audit = 0
            if self._table_exists(conn, _AUDIT_TABLE):
                audit = conn.execute(f"SELECT COUNT(*) FROM {_AUDIT_TABLE}").fetchone()[0]
            proposals = self._counts_by_status(conn, "proposals")
            tasks = self._counts_by_status(conn, "task_queue")
        finally:
            conn.close()
        try:
            size = os.path.getsize(self.db_path)
        except OSError:
            size = 0
        return {
            "db_path": self.db_path,
            "audit_entries": audit,
            "proposals": proposals,
            "tasks": tasks,
            "db_size_bytes": size,
        }

    # ------------------------------------------------------- prune proposals
    def prune_expired_proposals(self, *, retention_days: int = 90,
                                now: Optional[datetime] = None,
                                dry_run: bool = True) -> dict:
        """Expire stale pending proposals, then delete old expired/rejected ones.

        Never touches pending (live) or approved proposals younger than the
        window, and never touches the audit log.
        """
        now_iso = _now_iso(now)
        cutoff = _cutoff_iso(now, retention_days)
        conn = self._connect()
        try:
            if not self._table_exists(conn, "proposals"):
                return {"dry_run": dry_run, "expired": 0, "pruned": 0}

            # 1. pending proposals past their expires_at → expired
            expire_q = ("status='pending' AND expires_at IS NOT NULL "
                        "AND expires_at < ?")
            would_expire = conn.execute(
                f"SELECT COUNT(*) FROM proposals WHERE {expire_q}", (now_iso,)
            ).fetchone()[0]

            placeholders = ",".join("?" for _ in _PRUNABLE_PROPOSAL_STATUSES)
            if dry_run:
                # In preview, the soon-to-expire ones are still pending, so the
                # prune count reflects only already-terminal old proposals.
                would_prune = conn.execute(
                    f"SELECT COUNT(*) FROM proposals "
                    f"WHERE status IN ({placeholders}) AND created_at < ?",
                    (*_PRUNABLE_PROPOSAL_STATUSES, cutoff),
                ).fetchone()[0]
                return {"dry_run": True, "expired": would_expire, "pruned": would_prune}

            conn.execute(f"UPDATE proposals SET status='expired' WHERE {expire_q}", (now_iso,))
            pruned = conn.execute(
                f"DELETE FROM proposals "
                f"WHERE status IN ({placeholders}) AND created_at < ?",
                (*_PRUNABLE_PROPOSAL_STATUSES, cutoff),
            ).rowcount
            conn.commit()
            self.logger.info("housekeeping: expired %d, pruned %d proposals",
                             would_expire, pruned)
            return {"dry_run": False, "expired": would_expire, "pruned": pruned}
        finally:
            conn.close()

    # ------------------------------------------------------------ prune tasks
    def prune_finished_tasks(self, *, retention_days: int = 30,
                             now: Optional[datetime] = None,
                             dry_run: bool = True) -> dict:
        """Delete completed/failed tasks older than the window. Keeps active tasks."""
        cutoff = _cutoff_iso(now, retention_days)
        conn = self._connect()
        try:
            if not self._table_exists(conn, "task_queue"):
                return {"dry_run": dry_run, "pruned": 0}
            placeholders = ",".join("?" for _ in _PRUNABLE_TASK_STATUSES)
            where = (f"status IN ({placeholders}) "
                     f"AND completed_at IS NOT NULL AND completed_at < ?")
            args = (*_PRUNABLE_TASK_STATUSES, cutoff)
            if dry_run:
                n = conn.execute(
                    f"SELECT COUNT(*) FROM task_queue WHERE {where}", args
                ).fetchone()[0]
                return {"dry_run": True, "pruned": n}
            n = conn.execute(f"DELETE FROM task_queue WHERE {where}", args).rowcount
            conn.commit()
            self.logger.info("housekeeping: pruned %d finished tasks", n)
            return {"dry_run": False, "pruned": n}
        finally:
            conn.close()

    # ---------------------------------------------------------------- vacuum
    def vacuum(self) -> dict:
        """VACUUM the DB to reclaim space. Non-destructive (no rows lost)."""
        try:
            before = os.path.getsize(self.db_path)
        except OSError:
            before = 0
        conn = self._connect()
        try:
            conn.execute("VACUUM")
            conn.commit()
        finally:
            conn.close()
        try:
            after = os.path.getsize(self.db_path)
        except OSError:
            after = 0
        return {"before_bytes": before, "after_bytes": after,
                "reclaimed_bytes": max(0, before - after)}

    # ------------------------------------------------------------- orchestrate
    def run_housekeeping(self, *, now: Optional[datetime] = None,
                         dry_run: bool = True,
                         proposal_retention_days: int = 90,
                         task_retention_days: int = 30) -> dict:
        """Run the full housekeeping pass. dry_run=True (default) only reports.

        The audit log is never modified by any step.
        """
        proposals = self.prune_expired_proposals(
            retention_days=proposal_retention_days, now=now, dry_run=dry_run)
        tasks = self.prune_finished_tasks(
            retention_days=task_retention_days, now=now, dry_run=dry_run)
        vacuum = None if dry_run else self.vacuum()
        return {
            "dry_run": dry_run,
            "proposals": proposals,
            "tasks": tasks,
            "vacuum": vacuum,
            "report": self.report(),
        }


def _main():
    """CLI: `SAGE_PROJECT=<solution> python -m src.agents.admin [--apply]`.

    Defaults to a dry-run report (what *would* be cleaned). Pass --apply to act.
    """
    import argparse
    import json

    p = argparse.ArgumentParser(
        description="SAGE per-solution housekeeping (prune expired proposals + old "
                    "finished tasks, vacuum, report). Never touches the audit log.")
    p.add_argument("--project", help="Solution name (else SAGE_PROJECT env / active solution)")
    p.add_argument("--apply", action="store_true",
                   help="Apply housekeeping (default: dry-run report only)")
    p.add_argument("--proposal-retention-days", type=int, default=90)
    p.add_argument("--task-retention-days", type=int, default=30)
    args = p.parse_args()
    if args.project:
        os.environ["SAGE_PROJECT"] = args.project
    agent = AdminAgent()
    result = agent.run_housekeeping(
        dry_run=not args.apply,
        proposal_retention_days=args.proposal_retention_days,
        task_retention_days=args.task_retention_days)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _main()

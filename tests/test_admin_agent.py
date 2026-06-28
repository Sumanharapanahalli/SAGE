"""
Tests for the per-solution housekeeping AdminAgent.

The admin agent maintains a solution's `.sage/audit_log.db`: it prunes expired
proposals and old finished tasks, VACUUMs the DB, and reports stats. The
non-negotiable invariant: it NEVER deletes compliance_audit_log rows (the audit
trail is a compliance asset). Destructive operations are dry-run by default
(agents propose, humans dispose).
"""
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from src.agents.admin import AdminAgent


def _iso(dt):
    return dt.replace(tzinfo=timezone.utc).isoformat()


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE compliance_audit_log (
            id TEXT PRIMARY KEY, timestamp TEXT, actor TEXT, action_type TEXT,
            input_context TEXT, output_content TEXT, metadata TEXT
        );
        CREATE TABLE proposals (
            trace_id TEXT PRIMARY KEY, created_at TEXT, action_type TEXT,
            risk_class TEXT, reversible INTEGER, proposed_by TEXT, description TEXT,
            payload TEXT, status TEXT DEFAULT 'pending', decided_by TEXT,
            decided_at TEXT, feedback TEXT, expires_at TEXT, required_role TEXT
        );
        CREATE TABLE task_queue (
            task_id TEXT PRIMARY KEY, task_type TEXT, payload TEXT, priority INTEGER,
            status TEXT DEFAULT 'pending', created_at TEXT, started_at TEXT,
            completed_at TEXT, result TEXT, error TEXT
        );
        """
    )
    conn.commit()
    conn.close()
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


def _seed(path, now):
    old = now - timedelta(days=200)
    recent = now - timedelta(days=2)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    # audit: 3 rows that must always survive
    for i in range(3):
        c.execute("INSERT INTO compliance_audit_log VALUES (?,?,?,?,?,?,?)",
                  (f"a{i}", _iso(old), "system", "APPROVAL", "", "", "{}"))
    # proposals: pending(live), approved(keep), rejected(old→prune), expired(old→prune),
    #            pending-but-past-expiry(→expire), rejected(recent→keep)
    props = [
        ("p_pending", _iso(recent), "pending",  None),
        ("p_approved", _iso(old),   "approved", None),
        ("p_rejected_old", _iso(old), "rejected", None),
        ("p_expired_old", _iso(old), "expired",  None),
        ("p_pending_stale", _iso(old), "pending", _iso(old)),   # past expires_at
        ("p_rejected_recent", _iso(recent), "rejected", None),
    ]
    for tid, created, status, expires in props:
        c.execute(
            "INSERT INTO proposals (trace_id, created_at, action_type, risk_class, "
            "reversible, proposed_by, description, payload, status, expires_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (tid, created, "yaml_edit", "STATEFUL", 1, "agent", "d", "{}", status, expires),
        )
    # tasks: completed(old→prune), failed(old→prune), completed(recent→keep),
    #        pending(keep), running(keep)
    tasks = [
        ("t_done_old", "completed", _iso(old)),
        ("t_fail_old", "failed",    _iso(old)),
        ("t_done_recent", "completed", _iso(recent)),
        ("t_pending", "pending",  None),
        ("t_running", "running",  None),
    ]
    for tid, status, completed in tasks:
        c.execute(
            "INSERT INTO task_queue (task_id, task_type, payload, priority, status, "
            "created_at, completed_at) VALUES (?,?,?,?,?,?,?)",
            (tid, "ANALYZE", "{}", 5, status, _iso(old), completed),
        )
    conn.commit()
    conn.close()


def _count(path, table, where=""):
    conn = sqlite3.connect(path)
    try:
        q = f"SELECT COUNT(*) FROM {table}" + (f" WHERE {where}" if where else "")
        return conn.execute(q).fetchone()[0]
    finally:
        conn.close()


class TestReport:
    def test_report_counts(self, db):
        now = datetime(2026, 6, 28)
        _seed(db, now)
        rep = AdminAgent(db_path=db).report()
        assert rep["audit_entries"] == 3
        assert rep["proposals"]["pending"] == 2  # p_pending + p_pending_stale
        assert rep["proposals"]["rejected"] == 2
        assert rep["tasks"]["completed"] == 2
        assert rep["db_size_bytes"] > 0


class TestPruneProposals:
    def test_dry_run_changes_nothing(self, db):
        now = datetime(2026, 6, 28)
        _seed(db, now)
        before = _count(db, "proposals")
        out = AdminAgent(db_path=db).prune_expired_proposals(now=now, dry_run=True)
        assert out["dry_run"] is True
        assert _count(db, "proposals") == before  # nothing deleted
        assert out["pruned"] >= 2  # p_rejected_old + p_expired_old would go

    def test_execute_prunes_old_decided_keeps_live(self, db):
        now = datetime(2026, 6, 28)
        _seed(db, now)
        out = AdminAgent(db_path=db).prune_expired_proposals(
            now=now, retention_days=90, dry_run=False)
        assert out["dry_run"] is False
        # pending past expiry transitioned to expired
        assert out["expired"] == 1
        # old rejected + old expired pruned (the stale pending becomes expired, recent kept)
        assert _count(db, "proposals", "trace_id='p_rejected_old'") == 0
        assert _count(db, "proposals", "trace_id='p_expired_old'") == 0
        # live ones survive
        assert _count(db, "proposals", "trace_id='p_pending'") == 1
        assert _count(db, "proposals", "trace_id='p_approved'") == 1
        assert _count(db, "proposals", "trace_id='p_rejected_recent'") == 1


class TestPruneTasks:
    def test_execute_prunes_old_finished_keeps_active(self, db):
        now = datetime(2026, 6, 28)
        _seed(db, now)
        out = AdminAgent(db_path=db).prune_finished_tasks(
            now=now, retention_days=30, dry_run=False)
        assert out["pruned"] == 2  # t_done_old + t_fail_old
        assert _count(db, "task_queue", "task_id='t_done_recent'") == 1
        assert _count(db, "task_queue", "task_id='t_pending'") == 1
        assert _count(db, "task_queue", "task_id='t_running'") == 1


class TestAuditIsSacred:
    def test_housekeeping_never_touches_audit_log(self, db):
        now = datetime(2026, 6, 28)
        _seed(db, now)
        audit_before = _count(db, "compliance_audit_log")
        AdminAgent(db_path=db).run_housekeeping(now=now, dry_run=False)
        assert _count(db, "compliance_audit_log") == audit_before == 3


class TestVacuum:
    def test_vacuum_reports_sizes(self, db):
        now = datetime(2026, 6, 28)
        _seed(db, now)
        out = AdminAgent(db_path=db).vacuum()
        assert out["before_bytes"] > 0
        assert out["after_bytes"] > 0


class TestOrchestration:
    def test_run_housekeeping_dry_run_is_safe(self, db):
        now = datetime(2026, 6, 28)
        _seed(db, now)
        p_before = _count(db, "proposals")
        t_before = _count(db, "task_queue")
        out = AdminAgent(db_path=db).run_housekeeping(now=now, dry_run=True)
        assert out["dry_run"] is True
        assert _count(db, "proposals") == p_before
        assert _count(db, "task_queue") == t_before
        assert "proposals" in out and "tasks" in out and "report" in out

"""
Change Control Workflow Engine
===============================
Version-tracked change requests with impact assessment and multi-role approval.

Required by:
  - IEC 62304 §6.1 (Software Problem Resolution)
  - ISO 13485 §7.3.9 (Design and Development Changes)
  - 21 CFR 820.30(i) (Design Changes)
  - ISO 26262 §8.7 (Change Management)

Each change request flows through:
  DRAFT → SUBMITTED → IMPACT_ASSESSED → APPROVED/REJECTED → IMPLEMENTED → VERIFIED → CLOSED
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from src.core.db import get_connection

logger = logging.getLogger(__name__)


class ChangeStatus(Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IMPACT_ASSESSED = "impact_assessed"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    CLOSED = "closed"


class ChangePriority(Enum):
    CRITICAL = "critical"   # Safety/regulatory issue — immediate action
    HIGH = "high"           # Significant defect or compliance gap
    MEDIUM = "medium"       # Enhancement or non-critical fix
    LOW = "low"             # Cosmetic or minor improvement


class ChangeCategory(Enum):
    CORRECTIVE = "corrective"     # Fix a defect
    PREVENTIVE = "preventive"     # Prevent a potential issue
    ADAPTIVE = "adaptive"         # Adapt to external change (regulation, dependency)
    PERFECTIVE = "perfective"     # Improve performance/maintainability


@dataclass
class ImpactAssessment:
    """Impact assessment for a change request."""
    affected_requirements: List[str] = field(default_factory=list)
    affected_components: List[str] = field(default_factory=list)
    affected_tests: List[str] = field(default_factory=list)
    risk_impact: str = ""          # none, low, medium, high
    regulatory_impact: str = ""    # none, documentation_update, resubmission
    safety_impact: str = ""        # none, review_required, revalidation
    effort_estimate: str = ""      # hours or story points
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ChangeApproval:
    """Individual approval/rejection for a change request."""
    approver: str
    role: str
    decision: str          # approved, rejected, needs_info
    comments: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


class ChangeControlManager:
    """
    Manages change requests with full traceability.

    Storage: SQLite in the solution's .sage/ directory.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = self._default_db_path()
        self.db_path = db_path
        self._init_db()

    @staticmethod
    def _default_db_path() -> str:
        project = os.environ.get("SAGE_PROJECT", "").strip().lower()
        solutions_dir = os.environ.get(
            "SAGE_SOLUTIONS_DIR",
            os.path.join(os.path.dirname(__file__), "..", "..", "solutions"),
        )
        if project:
            sage_dir = os.path.join(os.path.abspath(solutions_dir), project, ".sage")
        else:
            sage_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                ".sage",
            )
        os.makedirs(sage_dir, exist_ok=True)
        return os.path.join(sage_dir, "change_control.db")

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = get_connection(self.db_path, row_factory=None)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS change_requests (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                requester TEXT NOT NULL,
                impact_assessment TEXT DEFAULT '{}',
                approvals TEXT DEFAULT '[]',
                affected_items TEXT DEFAULT '[]',
                resolution TEXT DEFAULT '',
                version_before TEXT DEFAULT '',
                version_after TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT DEFAULT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS change_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                change_request_id TEXT NOT NULL,
                from_status TEXT NOT NULL,
                to_status TEXT NOT NULL,
                changed_by TEXT NOT NULL,
                comments TEXT DEFAULT '',
                timestamp TEXT NOT NULL,
                FOREIGN KEY (change_request_id) REFERENCES change_requests(id)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_change_history ON change_history(change_request_id)"
        )
        conn.commit()
        conn.close()

    def create_request(
        self,
        title: str,
        description: str,
        category: str,
        priority: str,
        requester: str,
        affected_items: List[str] = None,
    ) -> dict:
        """Create a new change request."""
        cr_id = f"CR-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc).isoformat()

        # Validate enums
        ChangeCategory(category)
        ChangePriority(priority)

        conn = get_connection(self.db_path, row_factory=None)
        conn.execute(
            """INSERT INTO change_requests
               (id, title, description, category, priority, status, requester,
                affected_items, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cr_id, title, description, category, priority, "draft", requester,
             json.dumps(affected_items or []), now, now),
        )
        conn.execute(
            """INSERT INTO change_history
               (change_request_id, from_status, to_status, changed_by, comments, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (cr_id, "", "draft", requester, "Change request created", now),
        )
        conn.commit()
        conn.close()

        logger.info("Created change request %s: %s", cr_id, title)
        return {"id": cr_id, "status": "draft", "created_at": now}

    def get_request(self, cr_id: str) -> Optional[dict]:
        """Get a change request by ID."""
        conn = get_connection(self.db_path, row_factory=None)
        row = conn.execute("SELECT * FROM change_requests WHERE id = ?", (cr_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row[0], "title": row[1], "description": row[2],
            "category": row[3], "priority": row[4], "status": row[5],
            "requester": row[6],
            "impact_assessment": json.loads(row[7]) if row[7] else {},
            "approvals": json.loads(row[8]) if row[8] else [],
            "affected_items": json.loads(row[9]) if row[9] else [],
            "resolution": row[10], "version_before": row[11], "version_after": row[12],
            "created_at": row[13], "updated_at": row[14], "closed_at": row[15],
        }

    def list_requests(self, status: Optional[str] = None) -> List[dict]:
        """List change requests, optionally filtered by status."""
        conn = get_connection(self.db_path, row_factory=None)
        if status:
            rows = conn.execute(
                "SELECT id, title, category, priority, status, requester, created_at, updated_at "
                "FROM change_requests WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, category, priority, status, requester, created_at, updated_at "
                "FROM change_requests ORDER BY created_at DESC"
            ).fetchall()
        conn.close()
        return [
            {"id": r[0], "title": r[1], "category": r[2], "priority": r[3],
             "status": r[4], "requester": r[5], "created_at": r[6], "updated_at": r[7]}
            for r in rows
        ]

    def update_status(self, cr_id: str, new_status: str, changed_by: str, comments: str = "") -> dict:
        """Transition a change request to a new status."""
        ChangeStatus(new_status)  # validate

        request = self.get_request(cr_id)
        if not request:
            raise ValueError(f"Change request {cr_id} not found")

        old_status = request["status"]
        now = datetime.now(timezone.utc).isoformat()

        conn = get_connection(self.db_path, row_factory=None)
        updates = {"status": new_status, "updated_at": now}
        if new_status == "closed":
            updates["closed_at"] = now

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE change_requests SET {set_clause} WHERE id = ?",
            (*updates.values(), cr_id),
        )
        conn.execute(
            """INSERT INTO change_history
               (change_request_id, from_status, to_status, changed_by, comments, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (cr_id, old_status, new_status, changed_by, comments, now),
        )
        conn.commit()
        conn.close()

        logger.info("CR %s: %s → %s by %s", cr_id, old_status, new_status, changed_by)
        return {"id": cr_id, "old_status": old_status, "new_status": new_status}

    def add_impact_assessment(self, cr_id: str, assessment: dict) -> dict:
        """Add or update impact assessment for a change request."""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection(self.db_path, row_factory=None)
        conn.execute(
            "UPDATE change_requests SET impact_assessment = ?, status = 'impact_assessed', updated_at = ? WHERE id = ?",
            (json.dumps(assessment), now, cr_id),
        )
        conn.commit()
        conn.close()
        return {"id": cr_id, "status": "impact_assessed"}

    def add_approval(self, cr_id: str, approver: str, role: str, decision: str, comments: str = "") -> dict:
        """Add an approval decision to a change request."""
        request = self.get_request(cr_id)
        if not request:
            raise ValueError(f"Change request {cr_id} not found")

        approval = ChangeApproval(
            approver=approver, role=role, decision=decision, comments=comments,
        )
        approvals = request.get("approvals", [])
        approvals.append(approval.to_dict())

        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection(self.db_path, row_factory=None)
        conn.execute(
            "UPDATE change_requests SET approvals = ?, updated_at = ? WHERE id = ?",
            (json.dumps(approvals), now, cr_id),
        )
        conn.commit()
        conn.close()

        return {"id": cr_id, "approval": approval.to_dict()}

    def get_history(self, cr_id: str) -> List[dict]:
        """Get full status history for a change request."""
        conn = get_connection(self.db_path, row_factory=None)
        rows = conn.execute(
            "SELECT from_status, to_status, changed_by, comments, timestamp "
            "FROM change_history WHERE change_request_id = ? ORDER BY timestamp ASC",
            (cr_id,),
        ).fetchall()
        conn.close()
        return [
            {"from_status": r[0], "to_status": r[1], "changed_by": r[2],
             "comments": r[3], "timestamp": r[4]}
            for r in rows
        ]

    def get_metrics(self) -> dict:
        """Get change control metrics for compliance reporting."""
        conn = get_connection(self.db_path, row_factory=None)
        total = conn.execute("SELECT COUNT(*) FROM change_requests").fetchone()[0]
        by_status = {}
        for row in conn.execute(
            "SELECT status, COUNT(*) FROM change_requests GROUP BY status"
        ).fetchall():
            by_status[row[0]] = row[1]
        by_priority = {}
        for row in conn.execute(
            "SELECT priority, COUNT(*) FROM change_requests GROUP BY priority"
        ).fetchall():
            by_priority[row[0]] = row[1]
        conn.close()

        return {
            "total_requests": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "open_requests": total - by_status.get("closed", 0),
        }

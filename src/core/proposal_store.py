"""
SAGE ProposalStore — Centralised pending action registry.

Every AI-initiated write or execute action must go through this store.
No action executes without a human approval via POST /approve/{trace_id}.

Risk classes (lowest to highest):
  INFORMATIONAL — read-only, no gate needed
  EPHEMERAL     — low-risk, undo available; expires in 5 min
  STATEFUL      — medium risk, manual rollback; expires in 24 h
  EXTERNAL      — high risk, hard to reverse; expires in 72 h
  DESTRUCTIVE   — irreversible; never expires, requires explicit human note
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RiskClass(str, Enum):
    INFORMATIONAL = "INFORMATIONAL"
    EPHEMERAL     = "EPHEMERAL"
    STATEFUL      = "STATEFUL"
    EXTERNAL      = "EXTERNAL"
    DESTRUCTIVE   = "DESTRUCTIVE"


# Expiry window per risk class (None = never expires)
_EXPIRY_MINUTES: dict[RiskClass, Optional[int]] = {
    RiskClass.INFORMATIONAL: 60,          # 1 h
    RiskClass.EPHEMERAL:     60 * 8,      # 8 h — full working day
    RiskClass.STATEFUL:      60 * 24 * 7, # 7 days
    RiskClass.EXTERNAL:      60 * 24 * 14,# 14 days
    RiskClass.DESTRUCTIVE:   None,        # never expires
}


# ---------------------------------------------------------------------------
# Proposal model
# ---------------------------------------------------------------------------

class Proposal(BaseModel):
    trace_id:    str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at:  str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action_type: str                        # "yaml_edit" | "knowledge_add" | "llm_switch" | ...
    risk_class:  RiskClass
    reversible:  bool
    proposed_by: str = "system"             # "AnalystAgent" | "user:admin" | "OnboardingWizard"
    description: str                        # Human-readable summary
    payload:     dict                       # The actual action data
    status:        str = "pending"          # pending | approved | rejected | expired
    decided_by:    Optional[str]  = None
    decided_at:    Optional[str]  = None
    feedback:      Optional[str]  = None    # Rejection reason or approval note
    expires_at:    Optional[str]  = None    # ISO timestamp, None = never
    required_role: Optional[str]  = None    # Role required to approve (RBAC)
    # Named-approvals identity (T1-001) — populated when auth is enabled
    approved_by:      str = ""
    approver_role:    str = ""
    approver_email:   str = ""


# ---------------------------------------------------------------------------
# ProposalStore
# ---------------------------------------------------------------------------

class ProposalStore:
    """
    SQLite-backed registry for all pending SAGE proposals.
    Thread-safe — uses a single connection per call.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_table()

    # ------------------------------------------------------------------
    # Schema init
    # ------------------------------------------------------------------

    def _init_table(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                trace_id        TEXT PRIMARY KEY,
                created_at      TEXT NOT NULL,
                action_type     TEXT NOT NULL,
                risk_class      TEXT NOT NULL,
                reversible      INTEGER NOT NULL,
                proposed_by     TEXT NOT NULL,
                description     TEXT NOT NULL,
                payload         TEXT NOT NULL,   -- JSON
                status          TEXT NOT NULL DEFAULT 'pending',
                decided_by      TEXT,
                decided_at      TEXT,
                feedback        TEXT,
                expires_at      TEXT,
                required_role   TEXT,
                approved_by     TEXT DEFAULT '',
                approver_role   TEXT DEFAULT '',
                approver_email  TEXT DEFAULT ''
            )
        """)
        conn.commit()
        # Idempotent migrations for pre-existing databases
        _new_cols = [
            ("expires_at",     "TEXT"),
            ("required_role",  "TEXT"),
            ("approved_by",    "TEXT DEFAULT ''"),
            ("approver_role",  "TEXT DEFAULT ''"),
            ("approver_email", "TEXT DEFAULT ''"),
        ]
        for col, defn in _new_cols:
            try:
                conn.execute(f"ALTER TABLE proposals ADD COLUMN {col} {defn}")
                conn.commit()
            except Exception:
                pass  # column already exists
        conn.close()
        logger.debug("ProposalStore table ready at %s", self.db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_proposal(self, row: sqlite3.Row) -> Proposal:
        keys = row.keys()
        return Proposal(
            trace_id       = row["trace_id"],
            created_at     = row["created_at"],
            action_type    = row["action_type"],
            risk_class     = RiskClass(row["risk_class"]),
            reversible     = bool(row["reversible"]),
            proposed_by    = row["proposed_by"],
            description    = row["description"],
            payload        = json.loads(row["payload"]),
            status         = row["status"],
            decided_by     = row["decided_by"],
            decided_at     = row["decided_at"],
            feedback       = row["feedback"],
            expires_at     = row["expires_at"],
            required_role  = row["required_role"] if "required_role" in keys else None,
            approved_by    = row["approved_by"]    if "approved_by"    in keys else "",
            approver_role  = row["approver_role"]  if "approver_role"  in keys else "",
            approver_email = row["approver_email"] if "approver_email" in keys else "",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(
        self,
        action_type: str,
        risk_class: RiskClass,
        payload: dict,
        description: str,
        reversible: bool = True,
        proposed_by: str = "system",
        required_role: Optional[str] = None,
    ) -> Proposal:
        """Create and persist a new pending proposal."""
        expiry_mins = _EXPIRY_MINUTES.get(risk_class)
        if expiry_mins is not None:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(minutes=expiry_mins)
            ).isoformat()
        else:
            expires_at = None

        proposal = Proposal(
            action_type   = action_type,
            risk_class    = risk_class,
            reversible    = reversible,
            proposed_by   = proposed_by,
            description   = description,
            payload       = payload,
            expires_at    = expires_at,
            required_role = required_role,
        )

        conn = self._conn()
        conn.execute(
            """INSERT INTO proposals
               (trace_id, created_at, action_type, risk_class, reversible,
                proposed_by, description, payload, status, expires_at, required_role)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                proposal.trace_id, proposal.created_at, proposal.action_type,
                proposal.risk_class.value, int(proposal.reversible),
                proposal.proposed_by, proposal.description,
                json.dumps(proposal.payload), proposal.status,
                proposal.expires_at, proposal.required_role,
            ),
        )
        conn.commit()
        conn.close()
        logger.info(
            "Proposal created: %s [%s] %s",
            proposal.trace_id, proposal.risk_class.value, proposal.description,
        )
        return proposal

    def get(self, trace_id: str) -> Optional[Proposal]:
        """Retrieve a proposal by trace_id. Returns None if not found."""
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM proposals WHERE trace_id=?", (trace_id,)
        ).fetchone()
        conn.close()
        return self._row_to_proposal(row) if row else None

    def get_pending(self) -> list[Proposal]:
        """Return all proposals with status=pending that have not expired."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        rows = conn.execute(
            """SELECT * FROM proposals
               WHERE status='pending'
               AND (expires_at IS NULL OR expires_at > ?)
               ORDER BY created_at DESC""",
            (now,),
        ).fetchall()
        conn.close()
        return [self._row_to_proposal(r) for r in rows]

    def approve(
        self,
        trace_id: str,
        decided_by: str = "human",
        feedback: str = "",
        user=None,  # Optional[UserIdentity] — passed when auth is enabled
    ) -> Proposal:
        """Mark a proposal as approved. Raises ValueError if not found or not pending."""
        proposal = self.get(trace_id)
        if not proposal:
            raise ValueError(f"Proposal '{trace_id}' not found.")
        if proposal.status != "pending":
            raise ValueError(f"Proposal '{trace_id}' is already {proposal.status}.")

        decided_at     = datetime.now(timezone.utc).isoformat()
        approved_by    = user.name  if user else decided_by
        approver_role  = user.role  if user else ""
        approver_email = user.email if user else ""

        conn = self._conn()
        conn.execute(
            """UPDATE proposals
               SET status='approved', decided_by=?, decided_at=?, feedback=?,
                   approved_by=?, approver_role=?, approver_email=?
               WHERE trace_id=?""",
            (decided_by, decided_at, feedback or None,
             approved_by, approver_role, approver_email, trace_id),
        )
        conn.commit()
        conn.close()
        proposal.status        = "approved"
        proposal.decided_by    = decided_by
        proposal.decided_at    = decided_at
        proposal.feedback      = feedback or None
        proposal.approved_by   = approved_by
        proposal.approver_role = approver_role
        proposal.approver_email = approver_email
        logger.info("Proposal approved: %s by %s", trace_id, decided_by)
        return proposal

    def reject(
        self,
        trace_id: str,
        decided_by: str = "human",
        feedback: str = "",
        user=None,  # Optional[UserIdentity] — passed when auth is enabled
    ) -> Proposal:
        """Mark a proposal as rejected with optional feedback."""
        proposal = self.get(trace_id)
        if not proposal:
            raise ValueError(f"Proposal '{trace_id}' not found.")
        if proposal.status != "pending":
            raise ValueError(f"Proposal '{trace_id}' is already {proposal.status}.")

        decided_at     = datetime.now(timezone.utc).isoformat()
        approved_by    = user.name  if user else decided_by
        approver_role  = user.role  if user else ""
        approver_email = user.email if user else ""

        conn = self._conn()
        conn.execute(
            """UPDATE proposals
               SET status='rejected', decided_by=?, decided_at=?, feedback=?,
                   approved_by=?, approver_role=?, approver_email=?
               WHERE trace_id=?""",
            (decided_by, decided_at, feedback or None,
             approved_by, approver_role, approver_email, trace_id),
        )
        conn.commit()
        conn.close()
        proposal.status        = "rejected"
        proposal.decided_by    = decided_by
        proposal.decided_at    = decided_at
        proposal.feedback      = feedback or None
        proposal.approved_by   = approved_by
        proposal.approver_role = approver_role
        proposal.approver_email = approver_email
        logger.info("Proposal rejected: %s by %s — %s", trace_id, decided_by, feedback)
        return proposal

    def await_decision(self, trace_id: str, timeout_seconds: float = 300.0) -> Optional[Proposal]:
        """Block until the proposal is approved or rejected, or timeout elapses.

        Polls the underlying store at 50ms intervals. Returns the final
        Proposal object on decision, or None if the timeout is reached
        before a decision is recorded.

        Args:
            trace_id: Proposal to wait on.
            timeout_seconds: Maximum wait time. Default 5 minutes.

        Returns:
            Proposal with status in {"approved", "rejected"}, or None on timeout.
        """
        import time as _time

        poll_interval = 0.05  # 50 ms
        deadline = _time.monotonic() + timeout_seconds

        while _time.monotonic() < deadline:
            proposal = self.get(trace_id)
            if proposal is not None and proposal.status in ("approved", "rejected"):
                return proposal
            _time.sleep(poll_interval)

        return None

    def expire_old(self):
        """Mark all pending expired proposals as 'expired'. Call from background job."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        cur = conn.execute(
            """UPDATE proposals SET status='expired'
               WHERE status='pending' AND expires_at IS NOT NULL AND expires_at <= ?""",
            (now,),
        )
        count = cur.rowcount
        conn.commit()
        conn.close()
        if count:
            logger.info("Expired %d proposals.", count)
        return count


# ---------------------------------------------------------------------------
# Lazy singleton (resolved at first use, like audit_logger)
# ---------------------------------------------------------------------------

_proposal_store: Optional[ProposalStore] = None


def get_proposal_store() -> ProposalStore:
    """Return the global ProposalStore, initialising it on first call."""
    global _proposal_store
    if _proposal_store is None:
        from src.memory.audit_logger import audit_logger
        _proposal_store = ProposalStore(audit_logger.db_path)
    return _proposal_store

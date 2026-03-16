"""
SAGE Role-Based Access Control.

Role hierarchy (lowest to highest):
  VIEWER < OPERATOR < APPROVER < ADMIN

Roles are stored per (email, solution) in the api_keys SQLite database.
"""

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.auth import UserIdentity

logger = logging.getLogger(__name__)

# Role rank — higher = more privileges
_ROLE_RANK = {
    "viewer":   0,
    "operator": 1,
    "approver": 2,
    "admin":    3,
}


class Role(str, Enum):
    VIEWER   = "viewer"
    OPERATOR = "operator"
    APPROVER = "approver"
    ADMIN    = "admin"


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
        CREATE TABLE IF NOT EXISTS user_roles (
            id          TEXT PRIMARY KEY,
            email       TEXT NOT NULL,
            solution    TEXT NOT NULL,
            role        TEXT NOT NULL,
            granted_by  TEXT NOT NULL,
            granted_at  TEXT NOT NULL,
            UNIQUE(email, solution)
        )
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_user_role(email: str, solution: str) -> Role:
    """Return the user's role for a solution. Defaults to VIEWER."""
    _ensure_table()
    conn = _get_conn()
    row = conn.execute(
        "SELECT role FROM user_roles WHERE email=? AND solution=?",
        (email, solution),
    ).fetchone()
    conn.close()
    if row is None:
        return Role.VIEWER
    return Role(row["role"])


def assign_role(email: str, solution: str, role: Role, granted_by: str):
    """Insert or update a user's role for a solution."""
    _ensure_table()
    row_id = str(uuid.uuid4())
    granted_at = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    conn.execute(
        """INSERT INTO user_roles (id, email, solution, role, granted_by, granted_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(email, solution) DO UPDATE SET
               role=excluded.role,
               granted_by=excluded.granted_by,
               granted_at=excluded.granted_at""",
        (row_id, email, solution, role.value, granted_by, granted_at),
    )
    conn.commit()
    conn.close()
    logger.info("Role assigned: email=%s solution=%s role=%s by=%s", email, solution, role.value, granted_by)


def list_roles(solution: str) -> list[dict]:
    """Return all role assignments for a solution."""
    _ensure_table()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, email, solution, role, granted_by, granted_at FROM user_roles WHERE solution=? ORDER BY granted_at DESC",
        (solution,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# FastAPI dependency factory
# ---------------------------------------------------------------------------

def require_role(minimum_role: Role):
    """
    FastAPI dependency factory.
    Returns a dependency that raises HTTP 403 if the authenticated user's
    role is below minimum_role.

    When auth is disabled the anonymous user is granted ADMIN (full access).
    """
    from fastapi import Depends, HTTPException
    from src.core.auth import get_current_user  # avoid circular at module level

    async def _check(user=Depends(get_current_user)) -> "UserIdentity":
        user_rank = _ROLE_RANK.get(user.role, 0)
        min_rank  = _ROLE_RANK.get(minimum_role.value, 0)
        if user_rank < min_rank:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{minimum_role.value}' required. Your role: '{user.role}'.",
            )
        return user

    return _check

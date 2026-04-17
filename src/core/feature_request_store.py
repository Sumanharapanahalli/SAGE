"""SQLite-backed feature request store (Solution + SAGE scoped backlogs).

Extracted from src/interface/api.py so the desktop sidecar can reuse the
exact same schema without importing FastAPI. Column names and semantics
are preserved verbatim — existing rows continue to load.
"""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FeatureRequest:
    id: str
    module_id: str
    module_name: str
    title: str
    description: str
    priority: str
    status: str
    requested_by: str
    scope: str
    created_at: str
    updated_at: str
    reviewer_note: str
    plan_trace_id: str

    def to_dict(self) -> dict:
        return asdict(self)


class FeatureRequestStore:
    _VALID_PRIORITIES = {"low", "medium", "high", "critical"}
    _VALID_SCOPES = {"solution", "sage"}
    _VALID_ACTIONS = {
        "approve": "approved",
        "reject": "rejected",
        "complete": "completed",
    }

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feature_requests (
                    id           TEXT PRIMARY KEY,
                    module_id    TEXT NOT NULL,
                    module_name  TEXT NOT NULL,
                    title        TEXT NOT NULL,
                    description  TEXT NOT NULL,
                    priority     TEXT DEFAULT 'medium',
                    status       TEXT DEFAULT 'pending',
                    requested_by TEXT DEFAULT 'anonymous',
                    scope        TEXT DEFAULT 'solution',
                    created_at   TEXT,
                    updated_at   TEXT,
                    reviewer_note TEXT,
                    plan_trace_id TEXT
                )
                """
            )
            try:
                conn.execute(
                    "ALTER TABLE feature_requests ADD COLUMN scope TEXT DEFAULT 'solution'"
                )
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def submit(
        self,
        *,
        title: str,
        description: str,
        module_id: str = "general",
        module_name: str = "General",
        priority: str = "medium",
        requested_by: str = "anonymous",
        scope: str = "solution",
    ) -> FeatureRequest:
        if not title or not title.strip():
            raise ValueError("title must be non-empty")
        if priority not in self._VALID_PRIORITIES:
            raise ValueError(
                f"priority must be one of {sorted(self._VALID_PRIORITIES)}"
            )
        if scope not in self._VALID_SCOPES:
            raise ValueError(f"scope must be one of {sorted(self._VALID_SCOPES)}")

        now = _now_iso()
        fr = FeatureRequest(
            id=str(uuid.uuid4()),
            module_id=module_id,
            module_name=module_name,
            title=title,
            description=description,
            priority=priority,
            status="pending",
            requested_by=requested_by,
            scope=scope,
            created_at=now,
            updated_at=now,
            reviewer_note="",
            plan_trace_id="",
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO feature_requests
                  (id, module_id, module_name, title, description, priority,
                   status, requested_by, scope, created_at, updated_at,
                   reviewer_note, plan_trace_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fr.id, fr.module_id, fr.module_name, fr.title, fr.description,
                    fr.priority, fr.status, fr.requested_by, fr.scope,
                    fr.created_at, fr.updated_at, fr.reviewer_note, fr.plan_trace_id,
                ),
            )
            conn.commit()
        return fr

    def list(
        self,
        *,
        status: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> List[FeatureRequest]:
        sql = "SELECT * FROM feature_requests WHERE 1=1"
        args: list = []
        if status:
            sql += " AND status=?"
            args.append(status)
        if scope:
            sql += " AND scope=?"
            args.append(scope)
        sql += " ORDER BY created_at DESC"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, args).fetchall()
        return [self._row_to_fr(r) for r in rows]

    def get(self, feature_id: str) -> Optional[FeatureRequest]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM feature_requests WHERE id=?", (feature_id,)
            ).fetchone()
        return self._row_to_fr(row) if row else None

    def update(
        self, feature_id: str, *, action: str, reviewer_note: str = ""
    ) -> FeatureRequest:
        if action not in self._VALID_ACTIONS:
            raise ValueError(
                f"action must be one of {sorted(self._VALID_ACTIONS.keys())}"
            )
        new_status = self._VALID_ACTIONS[action]
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE feature_requests
                   SET status=?, reviewer_note=?, updated_at=?
                 WHERE id=?
                """,
                (new_status, reviewer_note, _now_iso(), feature_id),
            )
            if cur.rowcount == 0:
                raise KeyError(feature_id)
            conn.commit()
        fetched = self.get(feature_id)
        assert fetched is not None
        return fetched

    @staticmethod
    def _row_to_fr(row) -> FeatureRequest:
        return FeatureRequest(
            id=row["id"],
            module_id=row["module_id"],
            module_name=row["module_name"],
            title=row["title"],
            description=row["description"],
            priority=row["priority"] or "medium",
            status=row["status"] or "pending",
            requested_by=row["requested_by"] or "anonymous",
            scope=row["scope"] or "solution",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
            reviewer_note=row["reviewer_note"] or "",
            plan_trace_id=row["plan_trace_id"] or "",
        )

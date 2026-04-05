"""
Goals / OKR Persistence Store
==============================

SQLite-backed store for objectives and key results.
Key results are stored as a JSON array within the objective row.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.core.db import get_connection

logger = logging.getLogger(__name__)


class GoalsStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = get_connection(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS objectives (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    solution TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL,
                    quarter TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'on_track',
                    owner TEXT NOT NULL DEFAULT '',
                    key_results TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_objectives_user_solution
                ON objectives(user_id, solution)
            """)
            conn.commit()
        finally:
            conn.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _row_to_dict(self, row) -> dict:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "solution": row["solution"],
            "title": row["title"],
            "quarter": row["quarter"],
            "status": row["status"],
            "owner": row["owner"],
            "key_results": json.loads(row["key_results"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create(
        self,
        user_id: str,
        solution: str,
        title: str,
        quarter: str,
        status: str,
        owner: str,
        key_results: list,
    ) -> dict:
        obj_id = str(uuid.uuid4())
        now = self._now()
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                """INSERT INTO objectives
                   (id, user_id, solution, title, quarter, status, owner, key_results, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (obj_id, user_id, solution, title, quarter, status, owner,
                 json.dumps(key_results), now, now),
            )
            conn.commit()
            return self.get(obj_id)  # type: ignore
        finally:
            conn.close()

    def list(
        self, user_id: str, solution: str, *, quarter: Optional[str] = None
    ) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            if quarter:
                rows = conn.execute(
                    """SELECT * FROM objectives
                       WHERE user_id = ? AND solution = ? AND quarter = ?
                       ORDER BY created_at DESC""",
                    (user_id, solution, quarter),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM objectives
                       WHERE user_id = ? AND solution = ?
                       ORDER BY created_at DESC""",
                    (user_id, solution),
                ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def get(self, obj_id: str) -> Optional[dict]:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM objectives WHERE id = ?", (obj_id,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def update(self, obj_id: str, **kwargs) -> Optional[dict]:
        allowed = {"title", "quarter", "status", "owner", "key_results"}
        sets = []
        params: list = []
        for k, v in kwargs.items():
            if k not in allowed or v is None:
                continue
            if k == "key_results":
                sets.append("key_results = ?")
                params.append(json.dumps(v))
            else:
                sets.append(f"{k} = ?")
                params.append(v)
        if not sets:
            return self.get(obj_id)
        sets.append("updated_at = ?")
        params.append(self._now())
        params.append(obj_id)
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                f"UPDATE objectives SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            conn.commit()
            return self.get(obj_id)
        finally:
            conn.close()

    def delete(self, obj_id: str) -> bool:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute(
                "DELETE FROM objectives WHERE id = ?", (obj_id,)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

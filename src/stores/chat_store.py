"""
Chat Conversation Persistence Store
====================================

SQLite-backed store for chat conversations. Each conversation belongs to a
user+solution pair and stores messages as a JSON blob.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.core.db import get_connection

logger = logging.getLogger(__name__)


class ChatStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = get_connection(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    solution TEXT NOT NULL DEFAULT '',
                    role_id TEXT NOT NULL DEFAULT '',
                    role_name TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT 'New conversation',
                    messages TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_user_solution
                ON chat_conversations(user_id, solution)
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
            "role_id": row["role_id"],
            "role_name": row["role_name"],
            "title": row["title"],
            "messages": json.loads(row["messages"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create(
        self,
        user_id: str,
        solution: str,
        role_id: str,
        role_name: str,
        messages: list,
    ) -> dict:
        conv_id = str(uuid.uuid4())
        now = self._now()
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                """INSERT INTO chat_conversations
                   (id, user_id, solution, role_id, role_name, title, messages, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (conv_id, user_id, solution, role_id, role_name,
                 "New conversation", json.dumps(messages), now, now),
            )
            conn.commit()
            return self.get(conv_id)  # type: ignore
        finally:
            conn.close()

    def list(self, user_id: str, solution: str) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                """SELECT * FROM chat_conversations
                   WHERE user_id = ? AND solution = ?
                   ORDER BY updated_at DESC""",
                (user_id, solution),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def get(self, conv_id: str) -> Optional[dict]:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM chat_conversations WHERE id = ?", (conv_id,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def update(
        self,
        conv_id: str,
        *,
        title: Optional[str] = None,
        messages: Optional[list] = None,
    ) -> Optional[dict]:
        sets = []
        params: list = []
        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if messages is not None:
            sets.append("messages = ?")
            params.append(json.dumps(messages))
        if not sets:
            return self.get(conv_id)
        sets.append("updated_at = ?")
        params.append(self._now())
        params.append(conv_id)
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                f"UPDATE chat_conversations SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            conn.commit()
            return self.get(conv_id)
        finally:
            conn.close()

    def delete(self, conv_id: str) -> bool:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute(
                "DELETE FROM chat_conversations WHERE id = ?", (conv_id,)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def delete_all(self, user_id: str, solution: str) -> int:
        conn = get_connection(self.db_path)
        try:
            cur = conn.execute(
                "DELETE FROM chat_conversations WHERE user_id = ? AND solution = ?",
                (user_id, solution),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

"""
services/user_store.py — Thread-safe in-memory user store with persistence.

Production replacement: swap get_user / create_user to hit the PostgreSQL
users table via SQLAlchemy (the ORM models already exist in db/models.py).
"""
from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

from passlib.context import CryptContext

logger = logging.getLogger(__name__)

_PWD_CTX = CryptContext(schemes=["bcrypt"], deprecated="auto")

_DB_PATH = Path(".sage/users.db")


class UserStore:
    """
    Simple SQLite-backed user store.
    Supports create, lookup by user_id or email, and password verification.
    """

    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self._db = db_path
        self._init_db()
        self._ensure_default_admin()

    def _init_db(self) -> None:
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id    TEXT PRIMARY KEY,
                    name       TEXT NOT NULL,
                    email      TEXT NOT NULL UNIQUE,
                    email_hash TEXT NOT NULL,
                    phone      TEXT,
                    role       TEXT NOT NULL DEFAULT 'caregiver',
                    password_hash TEXT NOT NULL,
                    is_active  INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email_hash)")
            conn.commit()

    def _ensure_default_admin(self) -> None:
        """Create a default admin account if no users exist."""
        with sqlite3.connect(self._db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            self.create_user(
                name="System Admin",
                email="admin@falldetection.local",
                password="admin1234",
                role="admin",
                phone=None,
            )
            logger.info("UserStore: default admin created (email=admin@falldetection.local)")

    def create_user(
        self,
        name: str,
        email: str,
        password: str,
        role: str = "caregiver",
        phone: Optional[str] = None,
    ) -> dict:
        user_id = str(uuid.uuid4())
        email_hash = hashlib.sha256(email.lower().encode()).hexdigest()
        password_hash = _PWD_CTX.hash(password)
        now = time.time()
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                "INSERT INTO users (user_id, name, email, email_hash, phone, role, password_hash, is_active, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (user_id, name, email, email_hash, phone, role, password_hash, now),
            )
            conn.commit()
        logger.info("UserStore: created user_id=%s role=%s", user_id, role)
        return self.get_user(user_id)

    def get_user(self, user_id: str) -> Optional[dict]:
        with sqlite3.connect(self._db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[dict]:
        email_hash = hashlib.sha256(email.lower().encode()).hexdigest()
        with sqlite3.connect(self._db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM users WHERE email_hash = ?", (email_hash,)
            ).fetchone()
        return dict(row) if row else None

    def verify_password(self, email: str, password: str) -> Optional[dict]:
        user = self.get_user_by_email(email)
        if not user:
            return None
        if not _PWD_CTX.verify(password, user["password_hash"]):
            return None
        return user

    def list_users(self, role: Optional[str] = None) -> list[dict]:
        with sqlite3.connect(self._db) as conn:
            conn.row_factory = sqlite3.Row
            if role:
                rows = conn.execute(
                    "SELECT * FROM users WHERE role = ? AND is_active = 1", (role,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM users WHERE is_active = 1"
                ).fetchall()
        return [dict(r) for r in rows]

    def deactivate_user(self, user_id: str) -> bool:
        with sqlite3.connect(self._db) as conn:
            cur = conn.execute(
                "UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,)
            )
            conn.commit()
        return cur.rowcount > 0


_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    global _store
    if _store is None:
        _store = UserStore()
    return _store

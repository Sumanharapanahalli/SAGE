import sqlite3
import json
import time
import logging
import os
import uuid
from datetime import datetime, timezone


def _resolve_db_path() -> str:
    """
    Resolve the audit DB path to the active solution's .sage/ directory.

    Path: <solution_dir>/.sage/audit_log.db

    Each solution has its own completely isolated DB — proposals, audit trail,
    feature requests, API keys, and cost records never mix between solutions.
    Falls back to <framework_root>/.sage/audit_log.db when no project is set,
    so the framework itself never writes into a solution's data directory.

    The .sage/ directory mirrors the .claude/ convention: it is runtime state
    that lives with the solution, is auto-created on first use, and must be
    gitignored in every solution repository.
    """
    project = os.environ.get("SAGE_PROJECT", "").strip().lower()
    solutions_dir = os.environ.get(
        "SAGE_SOLUTIONS_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "solutions"),
    )
    if project:
        sage_dir = os.path.join(os.path.abspath(solutions_dir), project, ".sage")
        os.makedirs(sage_dir, exist_ok=True)
        return os.path.join(sage_dir, "audit_log.db")
    # Framework fallback — no solution active
    framework_sage = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".sage",
    )
    os.makedirs(framework_sage, exist_ok=True)
    return os.path.join(framework_sage, "audit_log.db")


DB_PATH = _resolve_db_path()

class AuditLogger:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.logger = logging.getLogger("AuditLogger")
        self._initialize_db()

    def _initialize_db(self):
        """Create the Audit Table if not exists. ISO 13485 requires traceability."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Schema: Immutable log of interactions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS compliance_audit_log (
                id TEXT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                actor TEXT NOT NULL,         -- 'AI_Agent', 'Human_Engineer', 'System_Trigger'
                action_type TEXT NOT NULL,   -- 'ANALYSIS', 'PROPOSAL', 'APPROVAL', 'REJECTION'
                input_context TEXT,          -- The prompt or data triggering the action
                output_content TEXT,         -- The AI's response or System's result
                metadata JSON,               -- JSON blob for extra tags (TraceID, GitHash)
                verification_signature TEXT, -- Placeholder for digital signature
                approved_by TEXT,            -- Identity that approved/rejected (named approvals)
                approver_role TEXT,          -- RBAC role of the approver
                approver_email TEXT,         -- Email of the approver
                approver_provider TEXT       -- Auth provider: "oidc" | "api_key" | "anonymous"
            )
        ''')
        conn.commit()

        # Idempotent migrations for databases created before named-approvals feature
        _identity_columns = [
            ("approved_by",        "TEXT"),
            ("approver_role",      "TEXT"),
            ("approver_email",     "TEXT"),
            ("approver_provider",  "TEXT"),
        ]
        for col_name, col_type in _identity_columns:
            try:
                conn.execute(f"ALTER TABLE compliance_audit_log ADD COLUMN {col_name} {col_type}")
                conn.commit()
                self.logger.info("Migrated compliance_audit_log: added column %s", col_name)
            except Exception:
                pass  # column already exists

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id         TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL,
                session_id TEXT NOT NULL,
                solution   TEXT NOT NULL,
                role       TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content    TEXT NOT NULL,
                page_context TEXT,
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()

        # chat_messages — add message_type and metadata columns (migration)
        for col_def in [
            "ALTER TABLE chat_messages ADD COLUMN message_type TEXT DEFAULT 'user'",
            "ALTER TABLE chat_messages ADD COLUMN metadata TEXT",
        ]:
            try:
                cursor.execute(col_def)
            except Exception:
                pass  # column already exists
        conn.commit()

        conn.close()

    def save_chat_message(
        self,
        user_id: str,
        session_id: str,
        solution: str,
        role: str,
        content: str,
        page_context: str = None,
        message_type: str = "user",
        metadata: dict = None,
    ) -> str:
        """Persist a chat message (user or assistant turn)."""
        msg_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        meta_str = json.dumps(metadata) if metadata else None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """INSERT INTO chat_messages
                   (id, user_id, session_id, solution, role, content, page_context, created_at,
                    message_type, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (msg_id, user_id, session_id, solution, role, content, page_context, created_at,
                 message_type, meta_str),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self.logger.error("Failed to save chat message: %s", exc)
        return msg_id

    def get_chat_history(
        self,
        user_id: str,
        session_id: str,
        solution: str,
        limit: int = 10,
    ) -> list:
        """Return the last N messages for a user+session+solution (oldest first)."""
        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                """SELECT role, content FROM chat_messages
                   WHERE user_id = ? AND session_id = ? AND solution = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, session_id, solution, limit),
            ).fetchall()
            conn.close()
            return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
        except Exception as exc:
            self.logger.error("Failed to get chat history: %s", exc)
            return []

    def clear_chat_history(self, user_id: str, solution: str) -> int:
        """Delete all chat messages for a user+solution. Returns rows deleted."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.execute(
                "DELETE FROM chat_messages WHERE user_id = ? AND solution = ?",
                (user_id, solution),
            )
            count = cur.rowcount
            conn.commit()
            conn.close()
            return count
        except Exception as exc:
            self.logger.error("Failed to clear chat history: %s", exc)
            return 0

    def log_event(
        self,
        actor: str,
        action_type: str,
        input_context: str,
        output_content: str,
        metadata: dict = None,
        # Named-approval identity fields (optional — populated when auth is enabled)
        approved_by: str = None,
        approver_role: str = None,
        approver_email: str = None,
        approver_provider: str = None,
    ):
        """
        Log an event to the persistent audit trail.

        The optional approved_by / approver_* kwargs capture the identity of
        the human who approved or rejected a proposal (T1-001 Named Approvals).
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata) if metadata else "{}"

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO compliance_audit_log
                    (id, timestamp, actor, action_type, input_context, output_content,
                     metadata, approved_by, approver_role, approver_email, approver_provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    event_id, timestamp, actor, action_type,
                    input_context, output_content, metadata_json,
                    approved_by, approver_role, approver_email, approver_provider,
                ),
            )
            conn.commit()
            conn.close()
            self.logger.info("Audit Logged: %s by %s (ID: %s)", action_type, actor, event_id)
            return event_id
        except Exception as e:
            self.logger.critical("FAILED TO WRITE AUDIT LOG: %s", e)
            # In a medical device, failure to log might mean we must STOP the system.
            raise e

# Global Access Point
audit_logger = AuditLogger()

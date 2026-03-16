import sqlite3
import json
import time
import logging
import os
import uuid
from datetime import datetime, timezone


def _resolve_db_path() -> str:
    """
    Resolve audit DB path to the active solution's data directory.
    Path: solutions/<project>/data/audit_log.db
    Falls back to framework-level data/ if no project is set.
    """
    project = os.environ.get("SAGE_PROJECT", "").strip().lower()
    solutions_dir = os.environ.get(
        "SAGE_SOLUTIONS_DIR",
        os.path.join(os.path.dirname(__file__), "..", "..", "solutions"),
    )
    if project:
        return os.path.join(os.path.abspath(solutions_dir), project, "data", "audit_log.db")
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "audit_log.db",
    )


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

        conn.close()

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

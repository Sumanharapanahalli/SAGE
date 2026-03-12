import sqlite3
import json
import time
import logging
import os
import uuid
from datetime import datetime, timezone

# Load config path (simplified for now)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "audit_log.db")

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
                verification_signature TEXT  -- Placeholder for digital signature
            )
        ''')
        conn.commit()
        conn.close()

    def log_event(self, actor: str, action_type: str, input_context: str, output_content: str, metadata: dict = None):
        """
        Log an event to the persistent audit trail.
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata) if metadata else "{}"
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO compliance_audit_log (id, timestamp, actor, action_type, input_context, output_content, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (event_id, timestamp, actor, action_type, input_context, output_content, metadata_json))
            conn.commit()
            conn.close()
            self.logger.info(f"Audit Logged: {action_type} by {actor} (ID: {event_id})")
            return event_id
        except Exception as e:
            self.logger.critical(f"FAILED TO WRITE AUDIT LOG: {e}")
            # In a medical device, failure to log might mean we must STOP the system.
            raise e

# Global Access Point
audit_logger = AuditLogger()

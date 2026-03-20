# tests/test_chat_audit.py  (new file — do NOT add to test_audit_logger.py)

def test_chat_message_type_and_metadata_columns():
    """save_chat_message accepts message_type and metadata without error."""
    import tempfile, os
    from src.memory.audit_logger import AuditLogger
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        al = AuditLogger(db_path=db_path)
        msg_id = al.save_chat_message(
            user_id="u1", session_id="s1", solution="test",
            role="assistant", content="Hello",
            message_type="action_proposed",
            metadata={"action": "approve_proposal", "trace_id": "abc"},
        )
        assert msg_id is not None
        # Verify columns exist by reading back
        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT message_type, metadata FROM chat_messages WHERE id=?", (msg_id,)
        ).fetchone()
        conn.close()
        assert row[0] == "action_proposed"
        assert "approve_proposal" in row[1]
    finally:
        os.unlink(db_path)

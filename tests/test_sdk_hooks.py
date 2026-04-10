"""Tests for SDK compliance hooks."""
import pytest
import sqlite3
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.unit


async def test_destructive_op_hook_blocks_rm_rf():
    from src.core.sdk_hooks import destructive_op_hook

    input_data = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "rm -rf /"},
    }
    result = await destructive_op_hook(input_data, "tool-1", {})

    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "destructive" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()


async def test_destructive_op_hook_blocks_force_push():
    from src.core.sdk_hooks import destructive_op_hook

    input_data = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git push --force origin main"},
    }
    result = await destructive_op_hook(input_data, "tool-1", {})

    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


async def test_destructive_op_hook_allows_safe_command():
    from src.core.sdk_hooks import destructive_op_hook

    input_data = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tests/"},
    }
    result = await destructive_op_hook(input_data, "tool-1", {})

    assert result == {}


async def test_budget_check_hook_denies_when_over_limit():
    from src.core.sdk_hooks import budget_check_hook

    with patch("src.core.sdk_hooks.check_budget") as mock_check:
        mock_check.return_value = (False, 150.0)

        input_data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "x.py"},
            "tenant": "test-tenant",
            "solution": "test-solution",
        }
        result = await budget_check_hook(input_data, "tool-1", {})

        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "budget" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()


async def test_budget_check_hook_allows_when_within_limit():
    from src.core.sdk_hooks import budget_check_hook

    with patch("src.core.sdk_hooks.check_budget") as mock_check:
        mock_check.return_value = (True, 10.0)

        input_data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "x.py"},
            "tenant": "test-tenant",
            "solution": "test-solution",
        }
        result = await budget_check_hook(input_data, "tool-1", {})

        assert result == {}


async def test_audit_logger_hook_records_tool_use(tmp_audit_db):
    from src.core.sdk_hooks import audit_logger_hook

    input_data = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": "src/foo.py"},
        "tool_response": {"success": True},
        "session_id": "sess-1",
    }
    context = {"trace_id": "trace-abc"}

    # Patch module-level audit_logger so the hook writes to the tmp DB
    with patch("src.core.sdk_hooks.audit_logger", tmp_audit_db):
        await audit_logger_hook(input_data, "tool-1", context)

    conn = sqlite3.connect(tmp_audit_db.db_path)
    rows = conn.execute(
        "SELECT actor, action_type FROM compliance_audit_log"
    ).fetchall()
    conn.close()

    assert len(rows) >= 1
    assert any("Edit" in r[1] for r in rows)


async def test_change_tracker_hook_records_write():
    from src.core.sdk_hooks import change_tracker_hook
    from src.core.sdk_change_tracker import sdk_change_tracker

    sdk_change_tracker.clear_session("sess-ct-1")
    input_data = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": "new.py"},
        "session_id": "sess-ct-1",
    }

    await change_tracker_hook(input_data, "tool-1", {})

    changes = sdk_change_tracker.get_session_changes("sess-ct-1")
    assert "new.py" in changes.created

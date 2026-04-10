"""Tests for SDKChangeTracker — accumulates file changes per session for Gate 2."""
import pytest

pytestmark = pytest.mark.unit


def test_empty_session_returns_no_changes():
    from src.core.sdk_change_tracker import SDKChangeTracker

    tracker = SDKChangeTracker()
    changes = tracker.get_session_changes("session-1")

    assert changes.created == []
    assert changes.modified == []
    assert changes.deleted == []
    assert changes.bash_commands == []


def test_record_write_adds_to_created():
    from src.core.sdk_change_tracker import SDKChangeTracker

    tracker = SDKChangeTracker()
    tracker.record("session-1", "Write", {"file_path": "new.py"})

    changes = tracker.get_session_changes("session-1")
    assert "new.py" in changes.created
    assert changes.modified == []


def test_record_edit_adds_to_modified():
    from src.core.sdk_change_tracker import SDKChangeTracker

    tracker = SDKChangeTracker()
    tracker.record("session-1", "Edit", {"file_path": "existing.py"})

    changes = tracker.get_session_changes("session-1")
    assert "existing.py" in changes.modified
    assert changes.created == []


def test_record_bash_adds_to_commands():
    from src.core.sdk_change_tracker import SDKChangeTracker

    tracker = SDKChangeTracker()
    tracker.record("session-1", "Bash", {"command": "pytest tests/"})

    changes = tracker.get_session_changes("session-1")
    assert "pytest tests/" in changes.bash_commands


def test_sessions_are_isolated():
    from src.core.sdk_change_tracker import SDKChangeTracker

    tracker = SDKChangeTracker()
    tracker.record("session-1", "Write", {"file_path": "a.py"})
    tracker.record("session-2", "Write", {"file_path": "b.py"})

    s1 = tracker.get_session_changes("session-1")
    s2 = tracker.get_session_changes("session-2")

    assert "a.py" in s1.created and "b.py" not in s1.created
    assert "b.py" in s2.created and "a.py" not in s2.created


def test_clear_session_removes_changes():
    from src.core.sdk_change_tracker import SDKChangeTracker

    tracker = SDKChangeTracker()
    tracker.record("session-1", "Write", {"file_path": "new.py"})
    tracker.clear_session("session-1")

    changes = tracker.get_session_changes("session-1")
    assert changes.created == []

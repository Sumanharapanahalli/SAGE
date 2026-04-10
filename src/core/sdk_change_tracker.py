"""Session-scoped file change accumulator for Gate 2 result approval.

Hooks record every Write/Edit/Delete/Bash invocation into this tracker.
At Stop-hook time, the Gate 2 result approval proposal reads the full
session changes and presents them to the human for approval.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List


logger = logging.getLogger(__name__)


@dataclass
class SessionChanges:
    """Accumulated changes for a single SDK session."""

    created: List[str] = field(default_factory=list)
    modified: List[str] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)
    bash_commands: List[str] = field(default_factory=list)


class SDKChangeTracker:
    """Thread-safe per-session change accumulator.

    Singleton-style via module-level `sdk_change_tracker` instance.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionChanges] = {}
        self._lock = threading.Lock()

    def record(self, session_id: str, tool_name: str, tool_input: dict) -> None:
        """Record a tool invocation under the given session."""
        with self._lock:
            changes = self._sessions.setdefault(session_id, SessionChanges())

            if tool_name == "Write":
                file_path = tool_input.get("file_path", "")
                if file_path:
                    changes.created.append(file_path)
            elif tool_name == "Edit":
                file_path = tool_input.get("file_path", "")
                if file_path:
                    changes.modified.append(file_path)
            elif tool_name == "Bash":
                command = tool_input.get("command", "")
                if command:
                    changes.bash_commands.append(command)
            else:
                logger.debug("SDKChangeTracker: ignoring tool=%s", tool_name)

    def get_session_changes(self, session_id: str) -> SessionChanges:
        """Return accumulated changes for a session (empty if unknown)."""
        with self._lock:
            return self._sessions.get(session_id, SessionChanges())

    def clear_session(self, session_id: str) -> None:
        """Remove a session's changes (call after Gate 2 decision is recorded)."""
        with self._lock:
            self._sessions.pop(session_id, None)


sdk_change_tracker = SDKChangeTracker()

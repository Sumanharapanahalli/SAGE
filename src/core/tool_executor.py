"""
SAGE Tool Executor — Agent Tool Use During Execution
=====================================================

Allows agents to call tools (file read, git diff, test runner, web search)
during task execution. Implements ReAct (Reason-Act-Observe) pattern.

Tools are registered with name, description, and callable. Agents request
tool calls via structured output; the executor runs them and feeds results
back into the agent's context.

Pattern: ReAct (Yao et al.) — Reason + Act + Observe loop
"""

import logging
import os
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    """A tool that agents can invoke."""
    name: str
    description: str
    handler: Callable[..., str]
    requires_approval: bool = False  # HITL gate for dangerous tools
    timeout: int = 30               # seconds


@dataclass
class ToolCall:
    """Record of a tool invocation."""
    tool_name: str
    arguments: dict
    result: str = ""
    error: str = ""
    duration_ms: int = 0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result[:500] if self.result else "",
            "error": self.error,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


class ToolExecutor:
    """Registry and executor for agent tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._call_history: list[ToolCall] = []
        self._lock = threading.Lock()
        self._register_builtins()

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def list_tools(self) -> list[dict]:
        """List available tools with descriptions."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "requires_approval": t.requires_approval,
            }
            for t in self._tools.values()
        ]

    def get_tool_descriptions(self) -> str:
        """Format tool descriptions for LLM prompt injection."""
        lines = ["Available tools:"]
        for t in self._tools.values():
            lines.append(f"  - {t.name}: {t.description}")
        return "\n".join(lines)

    def execute(self, tool_name: str, arguments: dict = None) -> ToolCall:
        """
        Execute a tool by name.
        Returns ToolCall with result or error.
        """
        arguments = arguments or {}
        call = ToolCall(tool_name=tool_name, arguments=arguments)

        tool = self._tools.get(tool_name)
        if not tool:
            call.error = f"Unknown tool: {tool_name}"
            with self._lock:
                self._call_history.append(call)
            return call

        if tool.requires_approval:
            call.error = "Tool requires HITL approval"
            with self._lock:
                self._call_history.append(call)
            return call

        import time
        start = time.monotonic()
        try:
            result = tool.handler(**arguments)
            call.result = str(result)
        except Exception as exc:
            call.error = str(exc)
            logger.warning("Tool %s error: %s", tool_name, exc)
        call.duration_ms = int((time.monotonic() - start) * 1000)

        with self._lock:
            self._call_history.append(call)

        self._emit("tool.executed", {
            "tool_name": tool_name,
            "success": not call.error,
            "duration_ms": call.duration_ms,
        })

        return call

    def execute_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        """
        Execute multiple tool calls from agent output.
        Each: {tool: str, arguments: dict}
        Returns list of {tool, result, error}.
        """
        results = []
        for tc in tool_calls:
            call = self.execute(tc.get("tool", ""), tc.get("arguments", {}))
            results.append(call.to_dict())
        return results

    def get_history(self, limit: int = 50) -> list[dict]:
        """Get recent tool call history."""
        with self._lock:
            return [c.to_dict() for c in self._call_history[-limit:]]

    def get_stats(self) -> dict:
        """Return tool executor statistics."""
        with self._lock:
            total = len(self._call_history)
            errors = sum(1 for c in self._call_history if c.error)
            tool_counts = {}
            for c in self._call_history:
                tool_counts[c.tool_name] = tool_counts.get(c.tool_name, 0) + 1
        return {
            "registered_tools": len(self._tools),
            "total_calls": total,
            "error_count": errors,
            "success_rate": round((total - errors) / total, 3) if total else 0,
            "tool_usage": tool_counts,
        }

    # ── Built-in tools ────────────────────────────────────────────────

    def _register_builtins(self) -> None:
        """Register default tools."""
        self.register(Tool(
            name="file_read",
            description="Read a file's contents. Args: {path: str, max_lines: int}",
            handler=self._tool_file_read,
        ))
        self.register(Tool(
            name="file_list",
            description="List files in a directory. Args: {path: str, pattern: str}",
            handler=self._tool_file_list,
        ))
        self.register(Tool(
            name="shell_run",
            description="Run a shell command (read-only). Args: {command: str}",
            handler=self._tool_shell_run,
            requires_approval=True,  # dangerous — needs HITL
        ))
        self.register(Tool(
            name="git_diff",
            description="Show git diff for working directory. Args: {path: str}",
            handler=self._tool_git_diff,
        ))
        self.register(Tool(
            name="git_log",
            description="Show recent git commits. Args: {path: str, count: int}",
            handler=self._tool_git_log,
        ))
        self.register(Tool(
            name="search_code",
            description="Search for a pattern in codebase. Args: {pattern: str, path: str}",
            handler=self._tool_search_code,
        ))
        self.register(Tool(
            name="run_tests",
            description="Run pytest for a specific test file. Args: {test_path: str}",
            handler=self._tool_run_tests,
            requires_approval=True,  # can have side effects
        ))

    @staticmethod
    def _tool_file_read(path: str, max_lines: int = 100) -> str:
        if not os.path.isfile(path):
            return f"File not found: {path}"
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[:max_lines]
        return "".join(lines)

    @staticmethod
    def _tool_file_list(path: str = ".", pattern: str = "*") -> str:
        import glob as g
        full_pattern = os.path.join(path, pattern)
        matches = g.glob(full_pattern)
        return "\n".join(sorted(matches)[:50])

    @staticmethod
    def _tool_shell_run(command: str) -> str:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30,
        )
        output = result.stdout + result.stderr
        return output[:2000]

    @staticmethod
    def _tool_git_diff(path: str = ".") -> str:
        result = subprocess.run(
            ["git", "diff", "--stat"], cwd=path,
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout[:2000] if result.stdout else "No changes"

    @staticmethod
    def _tool_git_log(path: str = ".", count: int = 5) -> str:
        result = subprocess.run(
            ["git", "log", f"--oneline", f"-{count}"], cwd=path,
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout[:1000]

    @staticmethod
    def _tool_search_code(pattern: str, path: str = ".") -> str:
        try:
            result = subprocess.run(
                ["grep", "-rn", "--include=*.py", pattern, path],
                capture_output=True, text=True, timeout=15,
            )
            return result.stdout[:2000] if result.stdout else "No matches"
        except Exception:
            return "Search failed"

    @staticmethod
    def _tool_run_tests(test_path: str) -> str:
        result = subprocess.run(
            ["python", "-m", "pytest", test_path, "-q", "--tb=short"],
            capture_output=True, text=True, timeout=120,
        )
        return (result.stdout + result.stderr)[:2000]

    @staticmethod
    def _emit(event_type: str, data: dict) -> None:
        try:
            from src.core.event_bus import get_event_bus
            get_event_bus().publish(event_type, data, source="tool_executor")
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────

_tool_executor: Optional[ToolExecutor] = None
_te_lock = threading.Lock()


def get_tool_executor() -> ToolExecutor:
    global _tool_executor
    if _tool_executor is None:
        with _te_lock:
            if _tool_executor is None:
                _tool_executor = ToolExecutor()
    return _tool_executor

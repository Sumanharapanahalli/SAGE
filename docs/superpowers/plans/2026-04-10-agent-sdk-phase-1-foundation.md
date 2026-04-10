# Agent SDK Phase 1 — Foundation: Bridge + Hooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational `AgentSDKRunner` bridge layer, compliance hooks, and two-gate HITL model — the prerequisite for all subsequent phases (agent migration, evolutionary layer, regulatory primitives).

**Architecture:** `AgentSDKRunner` is a singleton bridge between SAGE agents and the Claude Agent SDK. It detects SDK availability at runtime, translates SAGE role definitions into SDK `AgentDefinition` objects, wires SAGE's existing compliance infrastructure (proposal store, audit logger, cost tracker) into SDK hook callbacks, and falls back to the current `LLMGateway` path when the SDK is unavailable. No existing agent code is modified in Phase 1 — migration happens in Phase 2.

**Tech Stack:** Python 3.12, `claude-agent-sdk` (optional import with `try/except ImportError`), pytest with existing `tmp_audit_db`/`mock_llm_gateway` fixtures, SQLite via existing audit logger.

**Parent spec:** `docs/superpowers/specs/2026-04-10-agent-sdk-evolutionary-integration-design.md`

**Scope of Phase 1:** Foundation only. After this plan:
- `AgentSDKRunner` exists and has `is_sdk_available()` + `run()` methods
- SDK hook functions exist: budget check, PII filter, destructive op, audit logger, change tracker, result approval
- Two-gate HITL model (Gate 1 goal alignment + Gate 2 result approval) is implemented
- Graceful fallback to `llm_gateway.generate()` is verified
- `requirements.txt` lists `claude-agent-sdk` as optional
- `LLMGateway.sdk_available` property added
- No agents are migrated (that's Phase 2)

---

## File Structure

**New files (Phase 1):**
- `src/core/agent_sdk_runner.py` — `AgentSDKRunner` singleton, detection, role translation, `run()` with fallback, Gate 1/Gate 2 orchestration
- `src/core/sdk_hooks.py` — Hook callback functions wired to SAGE compliance primitives
- `src/core/sdk_change_tracker.py` — In-memory per-session file change accumulator used by Gate 2
- `tests/test_agent_sdk_runner.py` — Runner unit tests (detection, fallback, role translation, both gates)
- `tests/test_sdk_hooks.py` — Hook unit tests (budget, PII, destructive op, audit, change tracker)
- `tests/test_sdk_change_tracker.py` — Change tracker unit tests

**Modified files (Phase 1):**
- `src/core/llm_gateway.py` — Add `sdk_available` read-only property (detects if `claude_agent_sdk` is importable AND current provider is `claude-code`)
- `requirements.txt` — Add `claude-agent-sdk` on its own line with a comment marking it optional
- `src/core/proposal_store.py` — Add `await_decision(trace_id, timeout_seconds)` helper method (or module-level function) for async-style waiting used by both gates

**Why these files:** Each file has one responsibility. `agent_sdk_runner.py` is the orchestrator. `sdk_hooks.py` is a pure collection of hook callbacks (stateless functions). `sdk_change_tracker.py` is a stateful singleton — isolating it keeps the hook module stateless and testable. Splitting makes each file fit in ~300 lines max.

---

## Task 1: Add `sdk_available` property to `LLMGateway`

**Files:**
- Modify: `src/core/llm_gateway.py`
- Test: `tests/test_llm_gateway_sdk_detection.py` (create new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_llm_gateway_sdk_detection.py`:

```python
"""Tests for LLMGateway.sdk_available property."""
import pytest
from unittest.mock import patch

pytestmark = pytest.mark.unit


def test_sdk_available_false_when_package_missing():
    """Returns False when claude_agent_sdk import fails."""
    from src.core.llm_gateway import llm_gateway

    with patch.dict("sys.modules", {"claude_agent_sdk": None}):
        # Force re-check by clearing any cached state
        assert llm_gateway.sdk_available is False


def test_sdk_available_false_when_provider_not_claude_code():
    """Returns False when active provider is not claude-code."""
    from src.core.llm_gateway import llm_gateway

    with patch.object(llm_gateway, "_current_provider_name", "gemini"):
        assert llm_gateway.sdk_available is False


def test_sdk_available_true_when_package_and_provider_match():
    """Returns True when claude_agent_sdk importable AND provider is claude-code."""
    from src.core.llm_gateway import llm_gateway

    # Fake a claude_agent_sdk module in sys.modules
    import types
    fake_sdk = types.ModuleType("claude_agent_sdk")
    with patch.dict("sys.modules", {"claude_agent_sdk": fake_sdk}):
        with patch.object(llm_gateway, "_current_provider_name", "claude-code"):
            assert llm_gateway.sdk_available is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_llm_gateway_sdk_detection.py -v`
Expected: FAIL — `AttributeError: 'LLMGateway' object has no attribute 'sdk_available'`

- [ ] **Step 3: Implement the property**

Open `src/core/llm_gateway.py`. Find the `LLMGateway` class. Add near the top of the class (after `__init__`):

```python
    @property
    def sdk_available(self) -> bool:
        """True when claude_agent_sdk is installed AND active provider is claude-code.

        Used by AgentSDKRunner for graceful fallback detection.
        """
        try:
            import claude_agent_sdk  # noqa: F401
        except ImportError:
            return False

        provider_name = getattr(self, "_current_provider_name", None)
        if provider_name is None:
            # Derive from provider class name if attribute not set
            provider_name = type(self.provider).__name__.lower()
            if "claudecode" in provider_name:
                provider_name = "claude-code"

        return provider_name == "claude-code"
```

If `_current_provider_name` doesn't exist yet, also add this line in `__init__` after `self.provider = ...`:

```python
        self._current_provider_name: str = getattr(self, "_current_provider_name", "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_llm_gateway_sdk_detection.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `.venv/Scripts/python -m pytest tests/ -m unit -v --tb=short`
Expected: All previously-passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/core/llm_gateway.py tests/test_llm_gateway_sdk_detection.py
git commit -m "feat(llm_gateway): add sdk_available property for Agent SDK detection

Adds read-only property that returns True when claude_agent_sdk is
installed AND the active provider is claude-code. Used by AgentSDKRunner
for graceful fallback."
```

---

## Task 2: Add `claude-agent-sdk` to requirements (optional)

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the dependency line**

Open `requirements.txt`. At the end of the file add:

```
# Claude Agent SDK (optional - enables SDK features when Claude Code is active provider)
# Falls back gracefully when not installed. See src/core/agent_sdk_runner.py
claude-agent-sdk>=0.1.0
```

- [ ] **Step 2: Verify the file is still parseable**

Run: `.venv/Scripts/python -m pip install --dry-run -r requirements.txt 2>&1 | head -20`
Expected: No syntax errors. Package listed in resolver output.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore(deps): add claude-agent-sdk as optional dependency"
```

---

## Task 3: Create `SDKChangeTracker` for Gate 2 accumulation

**Files:**
- Create: `src/core/sdk_change_tracker.py`
- Test: `tests/test_sdk_change_tracker.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sdk_change_tracker.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_sdk_change_tracker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.sdk_change_tracker'`

- [ ] **Step 3: Implement `SDKChangeTracker`**

Create `src/core/sdk_change_tracker.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_sdk_change_tracker.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/core/sdk_change_tracker.py tests/test_sdk_change_tracker.py
git commit -m "feat(sdk): add SDKChangeTracker for Gate 2 result approval

Session-scoped accumulator that records Write/Edit/Bash tool calls during
SDK execution. Gate 2 reads the full session changes at Stop-hook time
to present the outcome to the human for approval."
```

---

## Task 4: Add `await_decision` helper to ProposalStore

**Files:**
- Modify: `src/core/proposal_store.py`
- Test: `tests/test_proposal_store_await_decision.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_proposal_store_await_decision.py`:

```python
"""Tests for ProposalStore.await_decision blocking helper."""
import threading
import time
import pytest

pytestmark = pytest.mark.unit


def test_await_decision_returns_on_approve(tmp_audit_db):
    """await_decision returns approved status when approve() is called."""
    from src.core.proposal_store import get_proposal_store
    from src.core.risk_classifier import RiskClass

    store = get_proposal_store()
    proposal = store.create(
        action_type="test_action",
        risk_class=RiskClass.LOW,
        payload={"foo": "bar"},
        description="test",
        proposed_by="test",
    )

    def approve_after_delay():
        time.sleep(0.1)
        store.approve(proposal.trace_id, decided_by="tester", feedback="ok")

    threading.Thread(target=approve_after_delay, daemon=True).start()

    decision = store.await_decision(proposal.trace_id, timeout_seconds=2.0)

    assert decision is not None
    assert decision.status == "approved"
    assert decision.feedback == "ok"


def test_await_decision_returns_on_reject(tmp_audit_db):
    from src.core.proposal_store import get_proposal_store
    from src.core.risk_classifier import RiskClass

    store = get_proposal_store()
    proposal = store.create(
        action_type="test_action",
        risk_class=RiskClass.LOW,
        payload={"foo": "bar"},
        description="test",
        proposed_by="test",
    )

    def reject_after_delay():
        time.sleep(0.1)
        store.reject(proposal.trace_id, decided_by="tester", feedback="nope")

    threading.Thread(target=reject_after_delay, daemon=True).start()

    decision = store.await_decision(proposal.trace_id, timeout_seconds=2.0)

    assert decision is not None
    assert decision.status == "rejected"
    assert decision.feedback == "nope"


def test_await_decision_returns_none_on_timeout(tmp_audit_db):
    from src.core.proposal_store import get_proposal_store
    from src.core.risk_classifier import RiskClass

    store = get_proposal_store()
    proposal = store.create(
        action_type="test_action",
        risk_class=RiskClass.LOW,
        payload={"foo": "bar"},
        description="test",
        proposed_by="test",
    )

    decision = store.await_decision(proposal.trace_id, timeout_seconds=0.2)

    assert decision is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_proposal_store_await_decision.py -v`
Expected: FAIL — `AttributeError: 'ProposalStore' object has no attribute 'await_decision'`

- [ ] **Step 3: Implement `await_decision`**

Open `src/core/proposal_store.py`. Find the `ProposalStore` class. Add this method (place it right after `reject()`):

```python
    def await_decision(self, trace_id: str, timeout_seconds: float = 300.0):
        """Block until the proposal is approved or rejected, or timeout elapses.

        Polls the underlying store at 50ms intervals. Returns the final
        Proposal object on decision, or None if the timeout is reached
        before a decision is recorded.

        Args:
            trace_id: Proposal to wait on.
            timeout_seconds: Maximum wait time. Default 5 minutes.

        Returns:
            Proposal with status in {"approved", "rejected"}, or None on timeout.
        """
        import time

        poll_interval = 0.05  # 50 ms
        deadline = time.monotonic() + timeout_seconds

        while time.monotonic() < deadline:
            proposal = self.get(trace_id)
            if proposal is not None and proposal.status in ("approved", "rejected"):
                return proposal
            time.sleep(poll_interval)

        return None
```

If `ProposalStore.get()` does not exist, also add a minimal getter:

```python
    def get(self, trace_id: str):
        """Fetch a proposal by trace_id. Returns None if not found."""
        with self._lock:  # if the class uses a lock; omit if not
            return self._proposals.get(trace_id)  # adjust to actual storage attr
```

(Check the existing class for the storage attribute name — it may be `self._proposals`, `self._store`, or a SQLite cursor. Use whatever the existing `approve()` / `reject()` methods use to look up proposals.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_proposal_store_await_decision.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `.venv/Scripts/python -m pytest tests/ -m unit -v --tb=short`
Expected: All previously-passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/core/proposal_store.py tests/test_proposal_store_await_decision.py
git commit -m "feat(proposal_store): add await_decision blocking helper

Polls proposal status until approved, rejected, or timeout. Used by
AgentSDKRunner Gate 1 (goal alignment) and Gate 2 (result approval)
to block execution until a human decision is recorded."
```

---

## Task 5: Implement SDK hook functions (budget, PII, destructive, audit)

**Files:**
- Create: `src/core/sdk_hooks.py`
- Test: `tests/test_sdk_hooks.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sdk_hooks.py`:

```python
"""Tests for SDK compliance hooks."""
import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_destructive_op_hook_blocks_force_push():
    from src.core.sdk_hooks import destructive_op_hook

    input_data = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git push --force origin main"},
    }
    result = await destructive_op_hook(input_data, "tool-1", {})

    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.asyncio
async def test_destructive_op_hook_allows_safe_command():
    from src.core.sdk_hooks import destructive_op_hook

    input_data = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tests/"},
    }
    result = await destructive_op_hook(input_data, "tool-1", {})

    assert result == {}


@pytest.mark.asyncio
async def test_budget_check_hook_denies_when_over_limit():
    from src.core.sdk_hooks import budget_check_hook

    with patch("src.core.sdk_hooks.check_budget") as mock_check:
        mock_check.return_value = (False, 150.0)  # (within_budget=False, current=150)

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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_audit_logger_hook_records_tool_use(tmp_audit_db):
    from src.core.sdk_hooks import audit_logger_hook
    import sqlite3

    input_data = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": "src/foo.py"},
        "tool_response": {"success": True},
        "session_id": "sess-1",
    }
    context = {"trace_id": "trace-abc"}

    await audit_logger_hook(input_data, "tool-1", context)

    conn = sqlite3.connect(tmp_audit_db.db_path)
    rows = conn.execute(
        "SELECT actor, action_type, input_context FROM compliance_audit_log "
        "WHERE trace_id = ?",
        ("trace-abc",),
    ).fetchall()
    conn.close()

    assert len(rows) >= 1
    assert any("Edit" in r[1] for r in rows)


@pytest.mark.asyncio
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_sdk_hooks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.sdk_hooks'`

- [ ] **Step 3: Implement the hook functions**

Create `src/core/sdk_hooks.py`:

```python
"""Claude Agent SDK hook callbacks wired to SAGE compliance infrastructure.

Each hook is an async function matching the SDK's HookCallback signature:

    async def hook(input_data: dict, tool_use_id: str, context: dict) -> dict

Hooks return an empty dict to allow the operation, or a dict containing
`hookSpecificOutput.permissionDecision == "deny"` to block it.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict

from src.core.cost_tracker import check_budget
from src.core.sdk_change_tracker import sdk_change_tracker
from src.memory.audit_logger import audit_logger


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Destructive op hook — hard blocks irreversible commands
# ---------------------------------------------------------------------------

_DESTRUCTIVE_PATTERNS = [
    re.compile(r"\brm\s+-rf?\s+/", re.IGNORECASE),
    re.compile(r"\brm\s+-rf?\s+~", re.IGNORECASE),
    re.compile(r"\bgit\s+push\s+.*--force\b", re.IGNORECASE),
    re.compile(r"\bgit\s+push\s+.*-f\b", re.IGNORECASE),
    re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=.*of=/dev/", re.IGNORECASE),
]


async def destructive_op_hook(
    input_data: Dict[str, Any],
    tool_use_id: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Hard-block destructive operations regardless of HITL state."""
    if input_data.get("tool_name") != "Bash":
        return {}

    command = input_data.get("tool_input", {}).get("command", "")
    for pattern in _DESTRUCTIVE_PATTERNS:
        if pattern.search(command):
            logger.warning(
                "destructive_op_hook blocked command: %s (pattern=%s)",
                command,
                pattern.pattern,
            )
            return {
                "hookSpecificOutput": {
                    "hookEventName": input_data.get("hook_event_name", "PreToolUse"),
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Blocked destructive operation matching pattern: {pattern.pattern}"
                    ),
                }
            }
    return {}


# ---------------------------------------------------------------------------
# Budget check hook — hard blocks when tenant/solution budget exceeded
# ---------------------------------------------------------------------------


async def budget_check_hook(
    input_data: Dict[str, Any],
    tool_use_id: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Deny tool use when the tenant/solution budget is exhausted."""
    tenant = input_data.get("tenant") or context.get("tenant", "default")
    solution = input_data.get("solution") or context.get("solution", "default")

    try:
        within_budget, current_spend = check_budget(tenant, solution)
    except Exception as exc:
        logger.error("budget_check_hook failed to query budget: %s", exc)
        return {}  # fail-open on transient errors; cost_tracker logs separately

    if not within_budget:
        logger.warning(
            "budget_check_hook deny: tenant=%s solution=%s current=%.2f",
            tenant,
            solution,
            current_spend,
        )
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data.get("hook_event_name", "PreToolUse"),
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Budget exceeded for {tenant}/{solution} "
                    f"(current spend: ${current_spend:.2f})"
                ),
            }
        }
    return {}


# ---------------------------------------------------------------------------
# PII filter hook — delegates to existing pii_filter.py
# ---------------------------------------------------------------------------


async def pii_filter_hook(
    input_data: Dict[str, Any],
    tool_use_id: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Scrub PII from tool inputs before execution.

    Uses the existing SAGE pii_filter module when available; otherwise allow.
    """
    try:
        from src.core.pii_filter import scrub_pii  # type: ignore
    except ImportError:
        return {}

    tool_input = input_data.get("tool_input", {})
    scrubbed = {}
    for key, value in tool_input.items():
        if isinstance(value, str):
            scrubbed[key] = scrub_pii(value)
        else:
            scrubbed[key] = value

    if scrubbed != tool_input:
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data.get("hook_event_name", "PreToolUse"),
                "permissionDecision": "allow",
                "updatedInput": scrubbed,
            }
        }
    return {}


# ---------------------------------------------------------------------------
# Audit logger hook — records every PostToolUse event
# ---------------------------------------------------------------------------


async def audit_logger_hook(
    input_data: Dict[str, Any],
    tool_use_id: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Write every SDK tool call to the compliance audit log."""
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})
    tool_response = input_data.get("tool_response", {})
    trace_id = context.get("trace_id") or input_data.get("session_id", "sdk-unknown")

    try:
        audit_logger.log_event(
            actor="AgentSDK",
            action_type=f"SDK_TOOL_{tool_name}",
            input_context=str(tool_input)[:4000],
            output_content=str(tool_response)[:4000],
            metadata={
                "tool_use_id": tool_use_id,
                "hook_event_name": input_data.get("hook_event_name"),
                "session_id": input_data.get("session_id"),
                "trace_id": trace_id,
            },
        )
    except Exception as exc:
        logger.error("audit_logger_hook failed: %s", exc)

    return {}


# ---------------------------------------------------------------------------
# Change tracker hook — accumulates file changes for Gate 2
# ---------------------------------------------------------------------------


async def change_tracker_hook(
    input_data: Dict[str, Any],
    tool_use_id: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Record Write/Edit/Bash tool use into the session change tracker."""
    session_id = input_data.get("session_id", "sdk-unknown")
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    sdk_change_tracker.record(session_id, tool_name, tool_input)
    return {}
```

- [ ] **Step 4: Install pytest-asyncio if missing**

Run: `.venv/Scripts/python -m pip show pytest-asyncio 2>&1 | head -1`

If not installed:
Run: `.venv/Scripts/python -m pip install pytest-asyncio`

Then add to `requirements.txt`:

```
pytest-asyncio>=0.21.0
```

- [ ] **Step 5: Configure pytest-asyncio**

Check if `pytest.ini` or `pyproject.toml` has `asyncio_mode`. If not, add to `pytest.ini` (or create if absent):

```ini
[pytest]
asyncio_mode = auto
markers =
    unit: fast unit tests
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_sdk_hooks.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 7: Run full test suite to check for regressions**

Run: `.venv/Scripts/python -m pytest tests/ -m unit -v --tb=short`
Expected: All previously-passing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add src/core/sdk_hooks.py tests/test_sdk_hooks.py requirements.txt pytest.ini
git commit -m "feat(sdk): add compliance hook callbacks for Agent SDK

Adds PreToolUse hooks (destructive_op, budget_check, pii_filter) and
PostToolUse hooks (audit_logger, change_tracker). All hooks wire into
existing SAGE compliance infrastructure — no new state is introduced
beyond the session-scoped change tracker."
```

---

## Task 6: Create `AgentSDKRunner` — detection + role translation

**Files:**
- Create: `src/core/agent_sdk_runner.py`
- Test: `tests/test_agent_sdk_runner.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_sdk_runner.py`:

```python
"""Tests for AgentSDKRunner — the bridge between SAGE agents and Claude Agent SDK."""
import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.unit


def test_is_sdk_available_false_without_sdk():
    """When claude_agent_sdk is not importable, is_sdk_available returns False."""
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    with patch.object(runner, "_llm_gateway") as mock_gw:
        mock_gw.sdk_available = False
        assert runner.is_sdk_available() is False


def test_is_sdk_available_true_when_gateway_reports_available():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    with patch.object(runner, "_llm_gateway") as mock_gw:
        mock_gw.sdk_available = True
        assert runner.is_sdk_available() is True


def test_resolve_tools_uses_per_role_sdk_tools_when_present():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    role_config = {
        "name": "Marketing Strategist",
        "system_prompt": "...",
        "sdk_tools": ["Read", "WebSearch"],
    }
    tools = runner._resolve_tools(role_config, task_type=None)
    assert tools == ["Read", "WebSearch"]


def test_resolve_tools_falls_back_to_task_type_mapping():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    role_config = {"name": "Analyst", "system_prompt": "..."}
    tools = runner._resolve_tools(role_config, task_type="analysis")
    assert set(tools) == {"Read", "Grep", "Glob"}


def test_resolve_tools_code_generation_includes_bash():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    role_config = {"name": "Coder", "system_prompt": "..."}
    tools = runner._resolve_tools(role_config, task_type="code_generation")
    assert "Bash" in tools
    assert "Edit" in tools
    assert "Write" in tools


def test_resolve_tools_unknown_task_type_returns_empty():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    role_config = {"name": "Unknown", "system_prompt": "..."}
    tools = runner._resolve_tools(role_config, task_type="unknown_task")
    assert tools == []


def test_build_agent_definition_uses_role_prompt_and_tools():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    role_config = {
        "name": "Security Analyst",
        "description": "Reviews code for security issues",
        "system_prompt": "You are a security expert.",
        "sdk_tools": ["Read", "Grep"],
    }
    agent_def = runner._build_agent_definition("security_analyst", role_config)

    assert agent_def["description"] == "Reviews code for security issues"
    assert agent_def["prompt"] == "You are a security expert."
    assert agent_def["tools"] == ["Read", "Grep"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_agent_sdk_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.agent_sdk_runner'`

- [ ] **Step 3: Implement detection + role translation**

Create `src/core/agent_sdk_runner.py`:

```python
"""Bridge layer between SAGE agents and the Claude Agent SDK.

When the SDK is available (claude_agent_sdk installed AND provider is
claude-code), this runner translates SAGE role definitions into SDK
AgentDefinition objects, wires compliance hooks, and executes via the
SDK's built-in tool loop. Otherwise it falls back to the existing
LLMGateway.generate() path — no behavior change for non-SDK providers.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# Task type → default SDK tool set (used when role has no sdk_tools field)
_TASK_TYPE_TOOLS: Dict[str, List[str]] = {
    "analysis": ["Read", "Grep", "Glob"],
    "review": ["Read", "Grep", "Glob"],
    "code_review": ["Read", "Edit", "Write", "Grep", "Glob"],
    "implementation": ["Read", "Edit", "Write", "Grep", "Glob"],
    "code_generation": ["Read", "Edit", "Write", "Bash", "Grep", "Glob"],
    "testing": ["Read", "Edit", "Write", "Bash", "Grep", "Glob"],
    "research": ["Read", "Grep", "Glob", "WebSearch", "WebFetch"],
    "investigation": ["Read", "Grep", "Glob", "WebSearch", "WebFetch"],
    "planning": ["Read", "Grep", "Glob", "Agent"],
    "decomposition": ["Read", "Grep", "Glob", "Agent"],
}


class AgentSDKRunner:
    """Singleton bridge between SAGE agents and the Agent SDK."""

    _instance: Optional["AgentSDKRunner"] = None

    def __new__(cls) -> "AgentSDKRunner":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        from src.core.llm_gateway import llm_gateway
        self._llm_gateway = llm_gateway
        self._initialized = True

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def is_sdk_available(self) -> bool:
        """True when the gateway reports SDK is available."""
        return bool(getattr(self._llm_gateway, "sdk_available", False))

    # ------------------------------------------------------------------
    # Role translation
    # ------------------------------------------------------------------

    def _resolve_tools(
        self,
        role_config: Dict[str, Any],
        task_type: Optional[str],
    ) -> List[str]:
        """Determine SDK tool set for a role.

        Resolution order:
          1. Per-role `sdk_tools` field in role_config
          2. Task-type default mapping
          3. Empty list (role has no SDK tools)
        """
        per_role = role_config.get("sdk_tools")
        if isinstance(per_role, list):
            return list(per_role)

        if task_type and task_type in _TASK_TYPE_TOOLS:
            return list(_TASK_TYPE_TOOLS[task_type])

        return []

    def _build_agent_definition(
        self,
        role_id: str,
        role_config: Dict[str, Any],
        task_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build an SDK AgentDefinition-compatible dict from a SAGE role."""
        return {
            "description": role_config.get("description", role_config.get("name", role_id)),
            "prompt": role_config.get("system_prompt", ""),
            "tools": self._resolve_tools(role_config, task_type),
        }


# Module-level singleton (lazy to avoid circular imports)
_runner: Optional[AgentSDKRunner] = None


def get_agent_sdk_runner() -> AgentSDKRunner:
    global _runner
    if _runner is None:
        _runner = AgentSDKRunner()
    return _runner
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_agent_sdk_runner.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/core/agent_sdk_runner.py tests/test_agent_sdk_runner.py
git commit -m "feat(sdk): add AgentSDKRunner detection and role translation

Bridge layer that detects SDK availability and translates SAGE role
definitions into SDK AgentDefinition dicts. Resolves tool sets via
per-role sdk_tools override or task-type default mapping. No execution
yet — that lands in the next task."
```

---

## Task 7: Add `run()` with graceful fallback to LLMGateway

**Files:**
- Modify: `src/core/agent_sdk_runner.py`
- Test: `tests/test_agent_sdk_runner.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_agent_sdk_runner.py`:

```python
@pytest.mark.asyncio
async def test_run_falls_back_to_gateway_when_sdk_unavailable():
    """When SDK is unavailable, run() delegates to LLMGateway.generate()."""
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()

    fake_gateway = MagicMock()
    fake_gateway.sdk_available = False
    fake_gateway.generate.return_value = '{"summary": "ok", "analysis": "done"}'

    fake_role = {
        "name": "Analyst",
        "system_prompt": "You analyze.",
    }

    with patch.object(runner, "_llm_gateway", fake_gateway), \
         patch.object(runner, "_load_role") as mock_load:
        mock_load.return_value = fake_role

        result = await runner.run(
            role_id="analyst",
            task="analyze the logs",
            context={"task_type": "analysis"},
        )

    assert fake_gateway.generate.called
    call_args = fake_gateway.generate.call_args
    assert "analyze the logs" in call_args[0][0] or "analyze the logs" in str(call_args)
    assert result["status"] in ("fallback_gateway", "success")
    assert result["role_id"] == "analyst"


@pytest.mark.asyncio
async def test_run_returns_error_for_unknown_role():
    from src.core.agent_sdk_runner import AgentSDKRunner

    runner = AgentSDKRunner()
    with patch.object(runner, "_load_role") as mock_load:
        mock_load.return_value = None  # unknown role

        result = await runner.run(
            role_id="does_not_exist",
            task="anything",
            context={},
        )

    assert result["status"] == "error"
    assert "unknown" in result["error"].lower() or "not found" in result["error"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_agent_sdk_runner.py -v`
Expected: FAIL — `AttributeError: 'AgentSDKRunner' object has no attribute 'run'`

- [ ] **Step 3: Implement `run()` + `_load_role()` + fallback**

Open `src/core/agent_sdk_runner.py`. Add these methods to the `AgentSDKRunner` class (after `_build_agent_definition`):

```python
    def _load_role(self, role_id: str) -> Optional[Dict[str, Any]]:
        """Look up a role definition in the active project config."""
        from src.core.project_loader import project_config
        roles = project_config.get_prompts().get("roles", {})
        return roles.get(role_id)

    async def run(
        self,
        role_id: str,
        task: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a SAGE agent role. Dispatches to SDK when available, else fallback.

        Args:
            role_id: Role key in solution prompts.yaml (e.g. "security_analyst").
            task: The task text for the agent.
            context: Optional context — may include `task_type`, `trace_id`, `actor`.

        Returns:
            Dict with keys: role_id, status, result (or error), trace_id.
        """
        role_config = self._load_role(role_id)
        if role_config is None:
            return {
                "role_id": role_id,
                "status": "error",
                "error": f"Unknown role: {role_id}",
            }

        if not self.is_sdk_available():
            return await self._run_via_gateway(role_id, role_config, task, context)

        return await self._run_via_sdk(role_id, role_config, task, context)

    async def _run_via_gateway(
        self,
        role_id: str,
        role_config: Dict[str, Any],
        task: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fallback path — uses existing LLMGateway.generate() directly."""
        system_prompt = role_config.get("system_prompt", "You are a helpful assistant.")
        trace_id = context.get("trace_id", "")
        agent_name = context.get("actor", f"role:{role_id}")

        try:
            response_text = self._llm_gateway.generate(
                prompt=task,
                system_prompt=system_prompt,
                trace_name=f"agent_sdk_runner_fallback_{role_id}",
                trace_id=trace_id,
                agent_name=agent_name,
            )
            return {
                "role_id": role_id,
                "role_name": role_config.get("name", role_id),
                "status": "fallback_gateway",
                "result": response_text,
                "trace_id": trace_id,
            }
        except Exception as exc:
            logger.exception("AgentSDKRunner gateway fallback failed for role=%s", role_id)
            return {
                "role_id": role_id,
                "status": "error",
                "error": str(exc),
                "trace_id": trace_id,
            }

    async def _run_via_sdk(
        self,
        role_id: str,
        role_config: Dict[str, Any],
        task: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """SDK execution path — stub in Task 7, Gate 1/2 wiring lands in Task 8."""
        # Lazy import so the module loads without claude_agent_sdk installed
        try:
            from claude_agent_sdk import query, ClaudeAgentOptions  # type: ignore
        except ImportError:
            logger.warning("claude_agent_sdk import failed at runtime; falling back")
            return await self._run_via_gateway(role_id, role_config, task, context)

        agent_def = self._build_agent_definition(
            role_id, role_config, task_type=context.get("task_type")
        )

        trace_id = context.get("trace_id", "")
        messages_collected: List[str] = []

        try:
            options = ClaudeAgentOptions(
                system_prompt=agent_def["prompt"],
                allowed_tools=agent_def["tools"],
                permission_mode="acceptEdits",
            )
            async for message in query(prompt=task, options=options):
                # Collect result text; Gate 1/2 wiring comes in Task 8
                if hasattr(message, "result"):
                    messages_collected.append(str(message.result))

            return {
                "role_id": role_id,
                "role_name": role_config.get("name", role_id),
                "status": "success",
                "result": "\n".join(messages_collected) if messages_collected else "",
                "trace_id": trace_id,
            }
        except Exception as exc:
            logger.exception("AgentSDKRunner SDK path failed for role=%s", role_id)
            return {
                "role_id": role_id,
                "status": "error",
                "error": str(exc),
                "trace_id": trace_id,
            }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_agent_sdk_runner.py -v`
Expected: PASS (all 9 tests — 7 from Task 6 + 2 new)

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `.venv/Scripts/python -m pytest tests/ -m unit -v --tb=short`
Expected: All previously-passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/core/agent_sdk_runner.py tests/test_agent_sdk_runner.py
git commit -m "feat(sdk): implement AgentSDKRunner.run() with graceful fallback

When SDK is unavailable, run() delegates to LLMGateway.generate()
unchanged. When SDK is available, executes via the SDK query() loop
with permission_mode=acceptEdits. Gate 1/Gate 2 HITL wiring lands
in the next task."
```

---

## Task 8: Wire Gate 1 (Goal Alignment) into `AgentSDKRunner.run()`

**Files:**
- Modify: `src/core/agent_sdk_runner.py`
- Test: `tests/test_agent_sdk_runner.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_agent_sdk_runner.py`:

```python
@pytest.mark.asyncio
async def test_gate1_creates_goal_alignment_proposal(tmp_audit_db):
    """Gate 1: SDK path creates a goal_alignment proposal before execution."""
    from src.core.agent_sdk_runner import AgentSDKRunner
    from src.core.proposal_store import get_proposal_store

    runner = AgentSDKRunner()
    fake_gateway = MagicMock()
    fake_gateway.sdk_available = True

    fake_role = {
        "name": "Analyst",
        "system_prompt": "analyze",
        "sdk_tools": ["Read", "Grep"],
    }

    store = get_proposal_store()
    created_proposals = []
    original_create = store.create

    def tracking_create(*args, **kwargs):
        p = original_create(*args, **kwargs)
        created_proposals.append(p)
        return p

    with patch.object(runner, "_llm_gateway", fake_gateway), \
         patch.object(runner, "_load_role", return_value=fake_role), \
         patch.object(store, "create", side_effect=tracking_create), \
         patch.object(runner, "_run_sdk_query", return_value="result text"):

        # Pre-approve the Gate 1 proposal via a background thread
        import threading
        import time

        def approve_when_ready():
            for _ in range(50):
                if created_proposals:
                    time.sleep(0.05)
                    store.approve(created_proposals[0].trace_id, decided_by="test")
                    # And approve the Gate 2 proposal too
                    for _ in range(50):
                        if len(created_proposals) >= 2:
                            store.approve(created_proposals[1].trace_id, decided_by="test")
                            return
                        time.sleep(0.05)
                    return
                time.sleep(0.05)

        threading.Thread(target=approve_when_ready, daemon=True).start()

        result = await runner.run(
            role_id="analyst",
            task="look at the logs",
            context={"task_type": "analysis"},
        )

    gate1_proposals = [p for p in created_proposals if p.action_type == "goal_alignment"]
    assert len(gate1_proposals) == 1
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_gate1_rejection_aborts_execution(tmp_audit_db):
    """Gate 1 rejection prevents SDK execution from starting."""
    from src.core.agent_sdk_runner import AgentSDKRunner
    from src.core.proposal_store import get_proposal_store

    runner = AgentSDKRunner()
    fake_gateway = MagicMock()
    fake_gateway.sdk_available = True

    fake_role = {"name": "Analyst", "system_prompt": "analyze", "sdk_tools": ["Read"]}

    store = get_proposal_store()
    created_proposals = []
    original_create = store.create

    def tracking_create(*args, **kwargs):
        p = original_create(*args, **kwargs)
        created_proposals.append(p)
        return p

    sdk_query_called = MagicMock()

    with patch.object(runner, "_llm_gateway", fake_gateway), \
         patch.object(runner, "_load_role", return_value=fake_role), \
         patch.object(store, "create", side_effect=tracking_create), \
         patch.object(runner, "_run_sdk_query", side_effect=sdk_query_called):

        import threading
        import time

        def reject_when_ready():
            for _ in range(50):
                if created_proposals:
                    time.sleep(0.05)
                    store.reject(created_proposals[0].trace_id, decided_by="test",
                                 feedback="out of scope")
                    return
                time.sleep(0.05)

        threading.Thread(target=reject_when_ready, daemon=True).start()

        result = await runner.run(
            role_id="analyst",
            task="do something risky",
            context={"task_type": "analysis"},
        )

    assert result["status"] == "rejected_at_goal"
    assert "out of scope" in result.get("reason", "")
    sdk_query_called.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_agent_sdk_runner.py::test_gate1_creates_goal_alignment_proposal -v`
Expected: FAIL — `_run_sdk_query` not defined OR Gate 1 proposal not created

- [ ] **Step 3: Refactor `_run_via_sdk` to add Gate 1**

Open `src/core/agent_sdk_runner.py`. Replace the `_run_via_sdk` method with:

```python
    async def _run_via_sdk(
        self,
        role_id: str,
        role_config: Dict[str, Any],
        task: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """SDK execution path with Gate 1 (goal alignment) gating."""
        from src.core.proposal_store import get_proposal_store
        from src.core.risk_classifier import RiskClass
        import uuid

        trace_id = context.get("trace_id") or str(uuid.uuid4())
        store = get_proposal_store()

        agent_def = self._build_agent_definition(
            role_id, role_config, task_type=context.get("task_type")
        )

        # ---------------- Gate 1: Goal Alignment ----------------
        goal_proposal = store.create(
            action_type="goal_alignment",
            risk_class=RiskClass.MEDIUM,
            payload={
                "role_id": role_id,
                "role_name": role_config.get("name", role_id),
                "task": task,
                "intended_approach": agent_def["prompt"][:500],
                "tools_requested": agent_def["tools"],
                "task_type": context.get("task_type"),
            },
            description=f"Goal alignment for role={role_id}",
            proposed_by=context.get("actor", "agent_sdk_runner"),
        )

        gate1_timeout = float(context.get("gate1_timeout_seconds", 1800))
        decision = store.await_decision(goal_proposal.trace_id, timeout_seconds=gate1_timeout)

        if decision is None:
            return {
                "role_id": role_id,
                "status": "timeout_at_goal",
                "trace_id": trace_id,
                "proposal_id": goal_proposal.trace_id,
            }
        if decision.status == "rejected":
            return {
                "role_id": role_id,
                "status": "rejected_at_goal",
                "reason": decision.feedback,
                "trace_id": trace_id,
                "proposal_id": goal_proposal.trace_id,
            }

        # ---------------- SDK execution ----------------
        try:
            result_text = await self._run_sdk_query(
                agent_def=agent_def,
                task=task,
                trace_id=trace_id,
            )
        except Exception as exc:
            logger.exception("SDK query failed for role=%s", role_id)
            return {
                "role_id": role_id,
                "status": "error",
                "error": str(exc),
                "trace_id": trace_id,
            }

        return {
            "role_id": role_id,
            "role_name": role_config.get("name", role_id),
            "status": "success",
            "result": result_text,
            "trace_id": trace_id,
        }

    async def _run_sdk_query(
        self,
        agent_def: Dict[str, Any],
        task: str,
        trace_id: str,
    ) -> str:
        """Execute the SDK query loop. Extracted for testability."""
        from claude_agent_sdk import query, ClaudeAgentOptions  # type: ignore

        messages_collected: List[str] = []
        options = ClaudeAgentOptions(
            system_prompt=agent_def["prompt"],
            allowed_tools=agent_def["tools"],
            permission_mode="acceptEdits",
        )
        async for message in query(prompt=task, options=options):
            if hasattr(message, "result"):
                messages_collected.append(str(message.result))
        return "\n".join(messages_collected)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_agent_sdk_runner.py -v`
Expected: PASS (all 11 tests)

- [ ] **Step 5: Commit**

```bash
git add src/core/agent_sdk_runner.py tests/test_agent_sdk_runner.py
git commit -m "feat(sdk): wire Gate 1 (goal alignment) into AgentSDKRunner

Before SDK execution begins, runner creates a goal_alignment proposal
and blocks until the human approves or rejects it. Rejection aborts
execution immediately. Extracts _run_sdk_query helper for testability."
```

---

## Task 9: Wire Gate 2 (Result Approval) into `AgentSDKRunner.run()`

**Files:**
- Modify: `src/core/agent_sdk_runner.py`
- Test: `tests/test_agent_sdk_runner.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_agent_sdk_runner.py`:

```python
@pytest.mark.asyncio
async def test_gate2_creates_result_approval_proposal(tmp_audit_db):
    """Gate 2: after SDK execution, runner creates a result_approval proposal."""
    from src.core.agent_sdk_runner import AgentSDKRunner
    from src.core.proposal_store import get_proposal_store
    from src.core.sdk_change_tracker import sdk_change_tracker

    runner = AgentSDKRunner()
    fake_gateway = MagicMock()
    fake_gateway.sdk_available = True

    fake_role = {"name": "Coder", "system_prompt": "code", "sdk_tools": ["Edit"]}

    store = get_proposal_store()
    created_proposals = []
    original_create = store.create

    def tracking_create(*args, **kwargs):
        p = original_create(*args, **kwargs)
        created_proposals.append(p)
        return p

    async def fake_sdk_query(agent_def, task, trace_id):
        # Simulate the SDK modifying a file during execution
        sdk_change_tracker.record(trace_id, "Edit", {"file_path": "src/foo.py"})
        return "implemented"

    with patch.object(runner, "_llm_gateway", fake_gateway), \
         patch.object(runner, "_load_role", return_value=fake_role), \
         patch.object(store, "create", side_effect=tracking_create), \
         patch.object(runner, "_run_sdk_query", side_effect=fake_sdk_query):

        import threading
        import time

        def approve_all_when_ready():
            seen = set()
            for _ in range(100):
                for p in created_proposals:
                    if p.trace_id not in seen:
                        seen.add(p.trace_id)
                        time.sleep(0.05)
                        store.approve(p.trace_id, decided_by="test")
                if len(seen) >= 2:
                    return
                time.sleep(0.05)

        threading.Thread(target=approve_all_when_ready, daemon=True).start()

        result = await runner.run(
            role_id="coder",
            task="implement foo",
            context={"task_type": "implementation"},
        )

    gate2 = [p for p in created_proposals if p.action_type == "result_approval"]
    assert len(gate2) == 1
    assert "src/foo.py" in str(gate2[0].payload.get("files_modified", []))
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_gate2_rejection_marks_result_rejected(tmp_audit_db):
    """Gate 2 rejection returns status=rejected_at_result with the reason."""
    from src.core.agent_sdk_runner import AgentSDKRunner
    from src.core.proposal_store import get_proposal_store

    runner = AgentSDKRunner()
    fake_gateway = MagicMock()
    fake_gateway.sdk_available = True

    fake_role = {"name": "Coder", "system_prompt": "code", "sdk_tools": ["Edit"]}

    store = get_proposal_store()
    created_proposals = []
    original_create = store.create

    def tracking_create(*args, **kwargs):
        p = original_create(*args, **kwargs)
        created_proposals.append(p)
        return p

    async def fake_sdk_query(agent_def, task, trace_id):
        return "some result"

    with patch.object(runner, "_llm_gateway", fake_gateway), \
         patch.object(runner, "_load_role", return_value=fake_role), \
         patch.object(store, "create", side_effect=tracking_create), \
         patch.object(runner, "_run_sdk_query", side_effect=fake_sdk_query):

        import threading
        import time

        def decide_proposals():
            seen = set()
            for _ in range(100):
                for p in created_proposals:
                    if p.trace_id not in seen:
                        seen.add(p.trace_id)
                        time.sleep(0.05)
                        if p.action_type == "goal_alignment":
                            store.approve(p.trace_id, decided_by="test")
                        else:
                            store.reject(p.trace_id, decided_by="test", feedback="bad output")
                if len(seen) >= 2:
                    return
                time.sleep(0.05)

        threading.Thread(target=decide_proposals, daemon=True).start()

        result = await runner.run(
            role_id="coder",
            task="do it",
            context={"task_type": "implementation"},
        )

    assert result["status"] == "rejected_at_result"
    assert "bad output" in result.get("reason", "")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_agent_sdk_runner.py::test_gate2_creates_result_approval_proposal -v`
Expected: FAIL — Gate 2 proposal not created

- [ ] **Step 3: Add Gate 2 after SDK execution**

Open `src/core/agent_sdk_runner.py`. In `_run_via_sdk`, after the SDK execution `try/except` block and before the final `return {..., "status": "success", ...}`, insert the Gate 2 logic. Replace the tail of `_run_via_sdk` (the SDK execution + return) with:

```python
        # ---------------- SDK execution ----------------
        try:
            result_text = await self._run_sdk_query(
                agent_def=agent_def,
                task=task,
                trace_id=trace_id,
            )
        except Exception as exc:
            logger.exception("SDK query failed for role=%s", role_id)
            return {
                "role_id": role_id,
                "status": "error",
                "error": str(exc),
                "trace_id": trace_id,
            }

        # ---------------- Gate 2: Result Approval ----------------
        from src.core.sdk_change_tracker import sdk_change_tracker
        changes = sdk_change_tracker.get_session_changes(trace_id)

        result_proposal = store.create(
            action_type="result_approval",
            risk_class=RiskClass.MEDIUM,
            payload={
                "role_id": role_id,
                "task": task,
                "result_summary": result_text[:2000],
                "files_created": changes.created,
                "files_modified": changes.modified,
                "files_deleted": changes.deleted,
                "commands_run": changes.bash_commands,
            },
            description=f"Result approval for role={role_id}",
            proposed_by=context.get("actor", "agent_sdk_runner"),
        )

        gate2_timeout = float(context.get("gate2_timeout_seconds", 3600))
        result_decision = store.await_decision(
            result_proposal.trace_id, timeout_seconds=gate2_timeout
        )

        # Clear session tracker regardless of decision
        sdk_change_tracker.clear_session(trace_id)

        if result_decision is None:
            return {
                "role_id": role_id,
                "status": "timeout_at_result",
                "trace_id": trace_id,
                "proposal_id": result_proposal.trace_id,
            }
        if result_decision.status == "rejected":
            # Feed rejection into vector memory (compounding intelligence)
            try:
                from src.memory.vector_store import vector_memory
                vector_memory.add_feedback(
                    result_decision.feedback or "rejected",
                    metadata={"phase": "result_approval", "trace_id": trace_id,
                              "role_id": role_id},
                )
            except Exception:
                logger.debug("vector_memory feedback ingest skipped")

            return {
                "role_id": role_id,
                "status": "rejected_at_result",
                "reason": result_decision.feedback,
                "trace_id": trace_id,
                "proposal_id": result_proposal.trace_id,
            }

        return {
            "role_id": role_id,
            "role_name": role_config.get("name", role_id),
            "status": "success",
            "result": result_text,
            "trace_id": trace_id,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_agent_sdk_runner.py -v`
Expected: PASS (all 13 tests)

- [ ] **Step 5: Run full test suite**

Run: `.venv/Scripts/python -m pytest tests/ -m unit -v --tb=short`
Expected: All previously-passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/core/agent_sdk_runner.py tests/test_agent_sdk_runner.py
git commit -m "feat(sdk): wire Gate 2 (result approval) into AgentSDKRunner

After SDK execution, runner reads session changes from the change
tracker and creates a result_approval proposal with diffs, files
modified, and commands run. Rejection feeds vector memory for
compounding intelligence."
```

---

## Task 10: Update CLAUDE.md documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the Agent SDK section**

Open `CLAUDE.md`. In the "Documentation Directory" section, under "Feature Documentation", add:

```markdown
- **[Agent SDK Integration](.claude/docs/features/agent-sdk.md)** — Claude Agent SDK bridge, two-gate HITL, evolutionary layer
```

Then find the "Core Tech Stack" section and append this line:

```markdown
- **Agent SDK**: Optional Claude Agent SDK integration (`claude-agent-sdk`) — activates when Claude Code is the active provider, falls back gracefully otherwise
```

- [ ] **Step 2: Create the feature doc**

Create `.claude/docs/features/agent-sdk.md`:

```markdown
# Agent SDK Integration

SAGE can optionally leverage the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview)
for built-in tool execution (Read/Edit/Write/Bash/Grep/Glob/WebSearch/WebFetch),
subagent parallelism, and session continuity. This is an **opt-in augmentation**
that activates only when all three conditions are met:

1. The `claude-agent-sdk` package is installed
2. The active LLM provider is `claude-code`
3. The Claude Code CLI is authenticated

When any condition fails, SAGE falls back to the existing `LLMGateway.generate()`
path — zero behavior change for other providers.

## Architecture

`src/core/agent_sdk_runner.py` — `AgentSDKRunner` bridge layer
`src/core/sdk_hooks.py` — Compliance hook callbacks
`src/core/sdk_change_tracker.py` — Per-session file change accumulator

Agents call `AgentSDKRunner.run(role_id, task, context)`. The runner:

1. Loads the role from `prompts.yaml`
2. Detects SDK availability
3. If SDK unavailable → delegates to `LLMGateway.generate()` (fallback)
4. If SDK available → runs the two-gate HITL flow

## Two-Gate HITL Model

Phase 1 replaces per-tool-call HITL gates with two meaningful gates:

- **Gate 1: Goal Alignment** — Before execution, the runner creates a
  `goal_alignment` proposal with the role, task, intended approach, and
  tools requested. Human approves the *direction* before work begins.

- **Gate 2: Result Approval** — After SDK execution completes, the runner
  reads accumulated file changes from `SDKChangeTracker` and creates a
  `result_approval` proposal with a full diff, commands run, and result
  summary. Human approves the *outcome* before changes are finalized.

Between gates, the SDK runs with `permission_mode="acceptEdits"`. Observational
hooks (`audit_logger_hook`, `change_tracker_hook`) capture every action without
blocking. Hard-blocking hooks (`destructive_op_hook`, `budget_check_hook`)
still deny dangerous operations regardless of HITL state.

## Per-Role `sdk_tools` Field

Solutions can specify per-role SDK tool sets in `prompts.yaml`:

```yaml
roles:
  clinical_reviewer:
    name: "Clinical Reviewer"
    system_prompt: "..."
    sdk_tools: ["Read", "Grep", "WebSearch", "WebFetch"]
```

If `sdk_tools` is omitted, the runner falls back to a task-type default mapping
(see `_TASK_TYPE_TOOLS` in `agent_sdk_runner.py`).

## Related

- Parent spec: `docs/superpowers/specs/2026-04-10-agent-sdk-evolutionary-integration-design.md`
- Phase 1 plan: `docs/superpowers/plans/2026-04-10-agent-sdk-phase-1-foundation.md`
```

- [ ] **Step 3: Verify markdown is valid**

Run: `ls .claude/docs/features/agent-sdk.md && ls CLAUDE.md`
Expected: Both files exist.

- [ ] **Step 4: Run full test suite one final time**

Run: `.venv/Scripts/python -m pytest tests/ -m unit -v --tb=short`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md .claude/docs/features/agent-sdk.md
git commit -m "docs: add Agent SDK integration documentation

Documents Phase 1 scope: AgentSDKRunner bridge, SDK hooks, two-gate HITL
model, per-role sdk_tools field, and graceful fallback behavior. Links
to parent spec and Phase 1 plan."
```

---

## Phase 1 Completion Checklist

Before declaring Phase 1 complete, verify:

- [ ] `make test` passes (all unit tests green)
- [ ] `src/core/agent_sdk_runner.py` exists and exports `AgentSDKRunner` + `get_agent_sdk_runner()`
- [ ] `src/core/sdk_hooks.py` exists with 5 hook callbacks (`destructive_op_hook`, `budget_check_hook`, `pii_filter_hook`, `audit_logger_hook`, `change_tracker_hook`)
- [ ] `src/core/sdk_change_tracker.py` exists with `SDKChangeTracker` singleton
- [ ] `LLMGateway.sdk_available` property returns correct values
- [ ] `ProposalStore.await_decision()` blocks correctly and returns on approve/reject/timeout
- [ ] `requirements.txt` lists `claude-agent-sdk` (optional) and `pytest-asyncio`
- [ ] No existing agents have been modified (Phase 2 work)
- [ ] `CLAUDE.md` and `.claude/docs/features/agent-sdk.md` updated
- [ ] All commits follow conventional commit format
- [ ] Graceful fallback verified: when `claude_agent_sdk` is not installed, all tests pass and no imports break

---

## What's Next

**Phase 2** will migrate the 6 target agents (`UniversalAgent`, `CriticAgent`, `AnalystAgent`, `PlannerAgent`, `DeveloperAgent`, `CodingAgent`) to route through `AgentSDKRunner`. Each agent migration is its own task with:
- Write tests asserting fallback produces identical output to current implementation
- Replace direct `llm_gateway.generate()` calls with `agent_sdk_runner.run()`
- Verify HITL gates fire correctly
- Commit

Phases 3-6 (ProgramDatabase, Evolvers, Regulatory Primitives) have their own plans to be written when Phase 2 is complete.

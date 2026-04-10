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
# PII filter hook — delegates to existing scrub_text when available
# ---------------------------------------------------------------------------


async def pii_filter_hook(
    input_data: Dict[str, Any],
    tool_use_id: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Scrub PII from tool inputs before execution.

    Uses existing SAGE scrub_text() from src.core.pii_filter when available;
    otherwise allows the operation unchanged (graceful degradation).
    """
    try:
        from src.core.pii_filter import scrub_text  # type: ignore
    except ImportError:
        return {}

    pii_config = context.get("pii_config") or {"enabled": False}
    if not pii_config.get("enabled"):
        return {}

    tool_input = input_data.get("tool_input", {})
    scrubbed: Dict[str, Any] = {}
    changed = False
    for key, value in tool_input.items():
        if isinstance(value, str):
            scrubbed_value, _entities = scrub_text(value, pii_config)
            scrubbed[key] = scrubbed_value
            if scrubbed_value != value:
                changed = True
        else:
            scrubbed[key] = value

    if changed:
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

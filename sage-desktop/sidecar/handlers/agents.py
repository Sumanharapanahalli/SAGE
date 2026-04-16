"""Agents handler — enumerate agent roles and their audit-log activity.

The "source of truth" for agents in a solution is ``prompts.yaml``. The
core SAGE roles (analyst, developer, planner, monitor) live at the top
level; solution-specific custom roles live under ``prompts.roles``. This
handler unions them into a single flat list and annotates each with
activity stats from the audit log (event count, last active timestamp).
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from rpc import RpcError, RPC_INVALID_PARAMS, RPC_METHOD_NOT_FOUND

# Injected by __main__.py at startup.
_project = None  # type: Optional[object]
_logger = None  # type: Optional[object]

_CORE_ROLES = ("analyst", "developer", "planner", "monitor")


def _agent_definitions() -> dict[str, dict]:
    """Flatten prompts.yaml into {name: {description, system_prompt, kind}}.

    Kind is "core" for the hardcoded SAGE roles and "custom" for anything
    under ``roles:``. Unknown shapes fall back to an empty definition
    rather than raising — the UI should always be able to list something.
    """
    if _project is None:
        return {}
    try:
        prompts = _project.get_prompts() or {}
    except Exception:  # noqa: BLE001
        return {}

    out: dict[str, dict] = {}
    for name in _CORE_ROLES:
        block = prompts.get(name) or {}
        if not isinstance(block, dict):
            block = {}
        out[name] = {
            "name": name,
            "kind": "core",
            "description": block.get("description", ""),
            "system_prompt": block.get("system", ""),
        }
    roles = prompts.get("roles") or {}
    if isinstance(roles, dict):
        for role_name, role_block in roles.items():
            if not isinstance(role_block, dict):
                role_block = {}
            out[role_name] = {
                "name": role_name,
                "kind": "custom",
                "description": role_block.get("description", ""),
                "system_prompt": role_block.get("system", ""),
            }
    return out


def _activity_by_actor() -> dict[str, dict]:
    """Scan the audit log once, return {actor: {count, last_active}}."""
    if _logger is None:
        return {}
    conn = sqlite3.connect(_logger.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT actor, COUNT(*) AS c, MAX(timestamp) AS last
               FROM compliance_audit_log
               GROUP BY actor"""
        ).fetchall()
    finally:
        conn.close()
    return {r["actor"]: {"count": r["c"], "last_active": r["last"]} for r in rows}


# ---------- handlers ----------

def list_agents(params: dict) -> list[dict]:
    defs = _agent_definitions()
    if not defs:
        return []
    activity = _activity_by_actor()
    out = []
    for name, d in defs.items():
        stats = activity.get(name, {"count": 0, "last_active": None})
        out.append({
            **d,
            "event_count": stats["count"],
            "last_active": stats["last_active"],
        })
    return out


def get_agent(params: dict) -> dict:
    name = params.get("name")
    if not name or not isinstance(name, str):
        raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'name'")
    defs = _agent_definitions()
    if name not in defs:
        raise RpcError(RPC_METHOD_NOT_FOUND, f"agent not found: {name}")
    activity = _activity_by_actor().get(name, {"count": 0, "last_active": None})
    return {
        **defs[name],
        "event_count": activity["count"],
        "last_active": activity["last_active"],
    }

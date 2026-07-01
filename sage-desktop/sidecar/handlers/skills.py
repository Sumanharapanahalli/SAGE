"""Skills & Tools handler — exposes src.core.skill_loader.skill_registry
and src.integrations.mcp_registry.mcp_registry to the desktop.

Read-and-toggle only: list skills, see registry stats, toggle a skill's
visibility tier, hot-reload from disk, and browse MCP tools. Deliberately
out of scope for this pass: per-skill/role/runner lookups, search, and
`mcp.invoke` (arbitrary tool invocation) — those are separate follow-ups.

Visibility toggles and reload are framework control, not agent proposals
(matching the web API's `/skills/visibility` and `/skills/reload`
docstrings: "Framework control — no approval needed") — these handlers
call the registries directly rather than routing through ProposalStore.

Unlike most other handlers, skill_registry and mcp_registry are
module-level singletons (same shape as compliance.py) — there is no
store/instance to wire at startup, so these handlers import them
directly at call time rather than reading an injected module-level
variable.
"""
from __future__ import annotations

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

_VALID_VISIBILITIES = {"public", "private", "disabled"}


def list(params: dict) -> dict:  # noqa: A001 - matches web API's `list_skills` verb
    try:
        from src.core.skill_loader import skill_registry
        include_disabled = bool((params or {}).get("include_disabled", False))
        found = skill_registry.list_all(include_disabled=include_disabled)
        return {
            "skills": [s.to_dict() for s in found],
            "stats": skill_registry.stats(),
        }
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"skills.list failed: {e}") from e


def set_visibility(params: dict) -> dict:
    try:
        from src.core.skill_loader import skill_registry
        p = params or {}
        name = p.get("name")
        visibility = p.get("visibility")
        if not name or not isinstance(name, str):
            raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'name'")
        if visibility not in _VALID_VISIBILITIES:
            raise RpcError(RPC_INVALID_PARAMS, f"Invalid visibility: {visibility}")
        ok = skill_registry.set_visibility(name, visibility)
        if not ok:
            raise RpcError(RPC_INVALID_PARAMS, f"Skill '{name}' not found")
        return {"status": "updated", "name": name, "visibility": visibility}
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"skills.set_visibility failed: {e}") from e


def reload(params: dict) -> dict:  # noqa: A001 - matches web API's `reload_skills` verb
    try:
        from src.core.skill_loader import skill_registry
        count = skill_registry.reload()
        return {
            "status": "reloaded",
            "skills_loaded": count,
            "stats": skill_registry.stats(),
        }
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"skills.reload failed: {e}") from e


def mcp_tools(params: dict) -> dict:
    try:
        from src.integrations.mcp_registry import mcp_registry
        tools = mcp_registry.list_tools()
        return {"tools": tools, "count": len(tools)}
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"skills.mcp_tools failed: {e}") from e

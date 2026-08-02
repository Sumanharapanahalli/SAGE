"""Orchestrator handler — observability over the 9 intelligence modules.

Read-only by design, matching what ``web/src/pages/Orchestrator.tsx`` actually
consumes: every client function it imports is a fetch. The mutating routes on
the web router (``POST /orchestrator/spawn``, ``/tools/execute``, ``/budget``)
are deliberately not surfaced — driving the orchestrator from a dashboard is a
different feature from watching it, and each of those would need its own Law 1
answer. ``/orchestrator/events/stream`` is out of scope under the standing
streaming exclusion; ``events/history`` gives the same data by polling.

Two RPCs instead of the router's ~25 endpoints. ``/orchestrator/stats`` is
already an aggregate over all nine modules, and the six "recent list" endpoints
differ only in which singleton they call and what that reader is named — so
they collapse into one parameterised ``recent(module)``.

Every lookup degrades to an empty result rather than raising. These subsystems
are legitimately idle or absent on a desktop install, and one missing module
must not blank the whole page — the same choice monitor.* and scheduler.*
already make.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from rpc import RPC_INVALID_PARAMS, RpcError

logger = logging.getLogger("sidecar.orchestrator")

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50


def _event_bus():
    from src.core.event_bus import get_event_bus

    return get_event_bus()


def _budget():
    from src.core.budget_manager import get_budget_manager

    return get_budget_manager()


def _reflection():
    from src.core.reflection_engine import get_reflection_engine

    return get_reflection_engine()


def _plans():
    from src.core.plan_selector import get_plan_selector

    return get_plan_selector()


def _spawner():
    from src.core.agent_spawner import get_agent_spawner

    return get_agent_spawner()


def _tools():
    from src.core.tool_executor import get_tool_executor

    return get_tool_executor()


def _backtrack():
    from src.core.backtrack_planner import get_backtrack_planner

    return get_backtrack_planner()


def _consensus():
    from src.core.consensus_engine import get_consensus_engine

    return get_consensus_engine()


def _memory_planner():
    from src.core.memory_planner import get_memory_planner

    return get_memory_planner()


# The nine modules, keyed by the name the UI shows.
_MODULES: dict[str, Callable[[], Any]] = {
    "events": _event_bus,
    "budget": _budget,
    "reflection": _reflection,
    "plans": _plans,
    "spawns": _spawner,
    "tools": _tools,
    "backtrack": _backtrack,
    "consensus": _consensus,
    "memory_planner": _memory_planner,
}

# How to read each module's recent records. memory_planner and budget are
# absent on purpose: they expose stats only, with no per-record history.
_READERS: dict[str, str] = {
    "events": "get_history",
    "reflection": "list_recent",
    "plans": "list_recent",
    "spawns": "list_spawns",
    "tools": "get_history",
    "backtrack": "list_records",
    "consensus": "list_results",
}

# Indirection so tests can substitute the whole module set.
_resolver: Optional[Callable[[str], Any]] = None


def _resolve(name: str):
    if _resolver is not None:
        return _resolver(name)
    return _MODULES[name]()


def _limit(params: Any) -> int:
    raw = (params or {}).get("limit", _DEFAULT_LIMIT)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise RpcError(RPC_INVALID_PARAMS, "'limit' must be an integer")
    return max(1, min(raw, _MAX_LIMIT))


def stats(params: Any = None) -> dict:
    """Combined statistics for all nine modules.

    ``unavailable`` names the modules that could not be loaded, so the UI can
    say "not active" instead of rendering a confusing row of zeroes.
    """
    modules: dict[str, dict] = {}
    unavailable: list[str] = []

    for name in _MODULES:
        try:
            result = _resolve(name).get_stats()
            modules[name] = result if isinstance(result, dict) else {}
        except Exception:  # noqa: BLE001 — an idle subsystem is not an error
            logger.debug("orchestrator module %s unavailable", name, exc_info=True)
            modules[name] = {}
            unavailable.append(name)

    return {"modules": modules, "unavailable": unavailable}


def recent(params: Any) -> dict:
    """Recent records for one module."""
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")

    module = params.get("module")
    if not isinstance(module, str) or not module:
        raise RpcError(RPC_INVALID_PARAMS, "'module' is required")
    if module not in _MODULES:
        raise RpcError(RPC_INVALID_PARAMS, f"unknown module: {module}")
    if module not in _READERS:
        # Better than an empty list, which would read as "nothing happened".
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"module '{module}' exposes statistics only, no recent records",
        )

    limit = _limit(params)
    try:
        reader = getattr(_resolve(module), _READERS[module])
        items = reader(limit=limit)
    except Exception:  # noqa: BLE001
        logger.debug("orchestrator module %s unavailable", module, exc_info=True)
        return {"module": module, "items": [], "available": False}

    return {
        "module": module,
        "items": list(items or [])[:limit],
        "available": True,
    }

"""Queue status handlers — read-only view into the task queue."""
from __future__ import annotations

from typing import Any, Dict, List

from rpc import RpcError, RPC_INVALID_PARAMS

_queue = None
# The live parallel config lives on the ParallelTaskRunner, NOT the bare
# TaskQueue. Wired by app._wire_handlers to src.core.queue_manager.parallel_runner
# — the same object FastAPI reads at api.py:1716-1717.
_parallel_runner = None


def _empty_status() -> Dict[str, Any]:
    # Keys MUST match TaskStatus's values verbatim. get_queue_status() counts
    # with `if key in status`, so a key the framework never emits ("done") is
    # not a cosmetic mislabel — it silently drops every finished task and pins
    # the UI's Done tile to 0 forever.
    return {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "failed": 0,
        "blocked": 0,
        "cancelled": 0,
        "parallel_enabled": False,
        "max_workers": 0,
    }


def get_queue_status(_params: dict) -> Dict[str, Any]:
    if _queue is None:
        return _empty_status()
    tasks = _queue.get_all_tasks()
    status = _empty_status()
    for t in tasks:
        key = t.get("status")
        if key in status:
            status[key] += 1
    cfg = getattr(_parallel_runner, "config", None)
    if cfg is not None:
        status["parallel_enabled"] = bool(getattr(cfg, "parallel_enabled", False))
        status["max_workers"] = int(getattr(cfg, "max_workers", 0))
    return status


def list_queue_tasks(params: dict) -> List[dict]:
    if _queue is None:
        return []
    limit = params.get("limit", 50)
    if not isinstance(limit, int) or limit < 0:
        raise RpcError(RPC_INVALID_PARAMS, "limit must be a non-negative integer")
    tasks = _queue.get_all_tasks()
    status_filter = params.get("status")
    if status_filter:
        tasks = [t for t in tasks if t.get("status") == status_filter]
    return tasks[:limit]

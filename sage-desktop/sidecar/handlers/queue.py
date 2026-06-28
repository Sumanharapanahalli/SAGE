"""Queue status handlers — read-only view into the task queue."""
from __future__ import annotations

from typing import Any, Dict, List

from rpc import RpcError, RPC_INVALID_PARAMS

_queue = None


def _empty_status() -> Dict[str, Any]:
    return {
        "pending": 0,
        "in_progress": 0,
        "done": 0,
        "failed": 0,
        "blocked": 0,
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
    cfg = getattr(_queue, "_config", None)
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

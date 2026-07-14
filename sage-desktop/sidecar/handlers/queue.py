"""Queue handlers — status view plus operator cancel/retry.

``queue.cancel`` and ``queue.retry`` are FRAMEWORK CONTROL, not agent
proposals: they are the operator's own action on their own tooling, so per
Law 1 they execute immediately and never enter the proposal queue. They are
still audited — an operator killing a task is a real event in the compliance
record, even though it needs no approval.

Before this, the queue was read-only from the desktop: a wedged task could be
watched but never recovered.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from rpc import RpcError, RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR
from handlers import operator

logger = logging.getLogger("sidecar.queue")

_queue = None
# Wired by app._wire_handlers. Operator actions are signed like any other
# decision; a control op that leaves no trace is indistinguishable from a bug.
_logger: Optional[Any] = None  # AuditLogger

# Indirected so tests can substitute an identity without touching operator._path.
_operator = operator.current
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


# ---------- operator actions (framework control — immediate, no HITL) ----------

def _require_queue():
    if _queue is None:
        raise RpcError(RPC_SIDECAR_ERROR, "task queue is not wired (SAGE import failed)")
    return _queue


def _require_task_id(params: Any) -> str:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    task_id = params.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise RpcError(RPC_INVALID_PARAMS, "task_id is required")
    return task_id


def _audit(action_type: str, task_id: str, detail: str) -> None:
    """Record the operator's control action. Never raises — an audit failure
    must not lose an action the human already took."""
    if _logger is None:
        logger.error(
            "AUDIT GAP: no audit logger wired — %s on task %s was NOT recorded",
            action_type, task_id,
        )
        return
    ident = _operator()
    try:
        _logger.log_event(
            actor=ident["name"],
            action_type=action_type,
            input_context=f"task_id={task_id}",
            output_content=detail,
            metadata={"task_id": task_id, "tier": "framework_control"},
            approved_by=ident["name"],
            approver_role="operator",
            approver_email=ident["email"],
            approver_provider=ident["provider"],
        )
    except Exception as e:  # noqa: BLE001
        logger.error("audit log failed for %s on %s: %s", action_type, task_id, e)


def cancel_task(params: Any) -> Dict[str, Any]:
    """Cancel a queued/blocked/running task.

    Honest about what the framework can actually do. Cancel is a durable state
    transition, not an interrupt:
      * A *pending* / *blocked* task is genuinely stopped — the sidecar runs no
        TaskWorker, so nothing dispatches from this queue, and the CANCELLED
        status is persisted to queue.db (never restored on restart).
      * An *in_progress* task is recorded as cancelled but a worker thread
        already running it is NOT killed — the queue has no cooperative
        cancellation. ``was_running`` rides back in the response so the UI can
        say exactly that instead of implying a kill it did not perform.
    """
    q = _require_queue()
    task_id = _require_task_id(params)

    try:
        result = q.cancel_task(task_id)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"cancel_task failed: {e}") from e

    if not result.get("cancelled"):
        reason = result.get("reason")
        if reason == "not_found":
            raise RpcError(RPC_INVALID_PARAMS, f"Task '{task_id}' not found")
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"Task '{task_id}' is already {result.get('status')} — nothing to cancel",
        )

    _audit(
        "TASK_CANCELLED",
        task_id,
        "cancelled while running (worker not killed)"
        if result.get("was_running") else "cancelled before dispatch",
    )
    return result


def retry_task(params: Any) -> Dict[str, Any]:
    """Re-queue a failed/cancelled/blocked task immediately.

    Uses ``TaskQueue.requeue_task``, NOT ``retry_task`` — the latter is the
    worker's automatic retry and would silently no-op an operator's explicit
    request (it refuses permanent errors and exhausted retry budgets) while
    also sleeping an exponential backoff inside the serial dispatch loop.
    """
    q = _require_queue()
    task_id = _require_task_id(params)

    try:
        result = q.requeue_task(task_id)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"requeue_task failed: {e}") from e

    if not result.get("requeued"):
        reason = result.get("reason")
        if reason == "not_found":
            raise RpcError(RPC_INVALID_PARAMS, f"Task '{task_id}' not found")
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"Task '{task_id}' is {result.get('status')} — only failed, cancelled, "
            "or blocked tasks can be retried",
        )

    _audit("TASK_RETRIED", task_id, "re-queued by operator")
    return result

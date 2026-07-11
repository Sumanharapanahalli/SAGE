"""Background job runner for the sidecar.

Why this exists:

The sidecar's dispatch loop is strictly serial — ``for raw in stdin`` reads one
request, runs it to completion, writes one response. That is a deliberate,
good design for the RPC surface: no interleaving, no correlation bookkeeping.

But two of the framework's action types (``implementation_plan`` and
``code_diff``) are multi-minute LLM work. Running them inside the dispatch loop
would freeze every other RPC for the duration — every 5s status poll, every page
navigation, the whole UI. api.py solves this with ``asyncio.ensure_future`` on
its already-async event loop. The sidecar has no event loop, so it needs this.

Two properties worth stating, because they are easy to get wrong:

  * ``execute_approved_proposal`` and ``_revert_code_diff`` are ``async def``.
    A worker thread therefore owns its own event loop (``asyncio.run``) — the
    sidecar's main thread never blocks on one.

  * Jobs are process-local and in-memory. They do NOT survive a sidecar restart.
    That is acceptable here (the proposal's persisted status is the source of
    truth; the job record is only progress reporting) but it MUST NOT be relied
    on as durable state.

This module is the same machinery Chat, the Gym's batch training, and any
future streaming work will reuse — build it once, correctly.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from rpc import RpcError, RPC_INVALID_PARAMS

logger = logging.getLogger("sidecar.jobs")

_lock = threading.Lock()
_jobs: Dict[str, dict] = {}
_pool: Optional[ThreadPoolExecutor] = None

# Deliberately small. These are LLM-bound, and the framework's LLMGateway holds
# a single-lane inference lock anyway (SOUL.md: "Never remove the threading.Lock
# from LLMGateway. Single-lane inference is intentional."), so a wide pool would
# only queue up behind that lock while multiplying memory pressure.
_MAX_WORKERS = 2


def _get_pool() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(
            max_workers=_MAX_WORKERS, thread_name_prefix="sidecar-job"
        )
    return _pool


def reset() -> None:
    """Test hook: drop all job records. Does not cancel running work."""
    with _lock:
        _jobs.clear()


def submit(kind: str, coro, label: str = "") -> str:
    """Run an async coroutine on a worker thread. Returns a job_id immediately."""
    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "kind": kind,
            "label": label,
            "state": "queued",
            "result": None,
            "error": None,
        }

    def _run():
        with _lock:
            _jobs[job_id]["state"] = "running"
        try:
            # Each worker owns its event loop; the sidecar's main thread has none.
            result = asyncio.run(coro)
            with _lock:
                _jobs[job_id]["state"] = "succeeded"
                _jobs[job_id]["result"] = result
        except BaseException as e:  # noqa: BLE001
            # Broad by intent: a job that dies must be REPORTED, never allowed to
            # take down the sidecar or vanish silently leaving the UI spinning.
            logger.error("job %s (%s) failed: %s", job_id, kind, e)
            with _lock:
                _jobs[job_id]["state"] = "failed"
                _jobs[job_id]["error"] = str(e)

    _get_pool().submit(_run)
    return job_id


def run_now(coro, timeout: float = 120.0) -> dict:
    """Run a coroutine to completion on a worker and return its outcome.

    Used for the FAST action types, where the operator expects the result in the
    approve response rather than a job_id to poll. Still executed off the main
    thread so a hung executor cannot wedge the dispatch loop forever — it times
    out instead.
    """
    fut = _get_pool().submit(asyncio.run, coro)
    try:
        return {"state": "succeeded", "result": fut.result(timeout=timeout)}
    except TimeoutError:
        return {"state": "failed", "error": f"execution timed out after {timeout}s"}
    except BaseException as e:  # noqa: BLE001
        return {"state": "failed", "error": str(e)}


def status(job_id: str) -> dict:
    with _lock:
        job = _jobs.get(job_id)
    if job is None:
        raise RpcError(RPC_INVALID_PARAMS, f"unknown job_id '{job_id}'")
    return dict(job)


def list_jobs() -> list[dict]:
    with _lock:
        return [dict(j) for j in _jobs.values()]


# ---------- RPC handlers ----------

def rpc_status(params: dict) -> dict:
    job_id = params.get("job_id")
    if not job_id or not isinstance(job_id, str):
        raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'job_id'")
    return status(job_id)


def rpc_list(_params: dict) -> dict:
    return {"jobs": list_jobs()}

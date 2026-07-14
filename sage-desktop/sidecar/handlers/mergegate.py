"""Merge-Gate Governance RPCs — start an agent-driven MR, poll its state.

The human's two touchpoints: `mergegate.start(work_item)` kicks off an agent branch that
codes, passes the evidence gate, and opens a regulatory PR; then the human reviews/approves
that PR on GitHub. `mergegate.status` / `mergegate.list` surface progress. The heavy loop
runs on a background job (jobs.py), never on the NDJSON dispatch thread, so slow LLM/gate work
never freezes the app.

Distinct from the legacy `mr.py` (GitLab merge-request handler) — this is the per-MR HITL
governance model. Wired in _wire_handlers via mr_runner.build_default_runner(<solution>).
"""
from __future__ import annotations

import logging
from typing import Any

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

logger = logging.getLogger("mergegate")

# Injected by _wire_handlers: an (MRRunner, MRStore) pair for the active solution.
_runner: Any = None
_store: Any = None


def _require():
    if _runner is None or _store is None:
        raise RpcError(RPC_SIDECAR_ERROR,
                       "merge-gate is not available — no active solution is wired")
    return _runner, _store


def start(params: Any) -> dict:
    """Start a new MR for a work item. Returns immediately with the mr_id + job_id; the
    agent branch → evidence gate → PR loop runs in the background."""
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    work_item = (params.get("work_item") or "").strip()
    if not work_item:
        raise RpcError(RPC_INVALID_PARAMS, "'work_item' is required")
    runner, store = _require()

    mr_id = store.create(work_item, branch="")
    # Match the worktree manager's branch naming so the runner pushes the branch the
    # worktree actually checks out (worktree_manager: proposal/<id[:8]>).
    branch = f"proposal/{mr_id[:8]}"
    store.update(mr_id, branch=branch)

    import jobs

    async def _job():
        return runner.run(mr_id)

    job_id = jobs.submit("mergegate", _job(), label=f"MR: {work_item[:48]}")
    logger.info("merge-gate started MR %s (job %s): %s", mr_id, job_id, work_item[:60])
    return {"mr_id": mr_id, "job_id": job_id, "branch": branch,
            "state": "coding", "work_item": work_item}


def status(params: Any) -> dict:
    """Full record for one MR (state, PR url, evidence, merged sha)."""
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    mr_id = params.get("mr_id")
    if not mr_id:
        raise RpcError(RPC_INVALID_PARAMS, "'mr_id' is required")
    _, store = _require()
    row = store.get(mr_id)
    if row is None:
        raise RpcError(RPC_INVALID_PARAMS, f"unknown MR '{mr_id}'")
    return row


def list_mrs(params: Any) -> dict:
    """All MRs for the active solution, optionally filtered by state, newest first."""
    _, store = _require()
    state = params.get("state", "") if isinstance(params, dict) else ""
    return {"mrs": store.list(state=state)}

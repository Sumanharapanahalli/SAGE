"""Code handler — plan, approve, execute a generated script in a sandbox.

Wraps ``src.integrations.autogen_runner``. Distinct from Merge-Gate: Law 1a
governs *merging* agent-written code to main (agents own the branch, the human
approves the MR), whereas this governs *executing* a generated script here and
now. Its approval gate is enforced inside ``autogen_runner.execute()`` itself —
an unapproved run is refused by the runner, not merely hidden by the UI.

One addition over the web API: ``sandbox_status``. The runner falls back to a
LOCAL SUBPROCESS with no isolation when Docker is unavailable, and the web API
only reveals that in the execute result — i.e. after the code has already run
on the operator's machine. Exposing it up front lets the UI say so while the
operator is still deciding whether to approve.

The runner keeps runs in memory, so a sidecar restart loses pending plans.
That matches the web API's behaviour and is acceptable: an un-executed plan is
cheap to regenerate.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

logger = logging.getLogger("sidecar.code")

# Injected by app._wire_handlers; tests substitute a fake.
_runner: Optional[Any] = None
_docker_check: Optional[Any] = None


def _require_runner():
    if _runner is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "code runner is not wired (autogen_runner unavailable)",
        )
    return _runner


def _require_str(params: Any, key: str) -> str:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RpcError(RPC_INVALID_PARAMS, f"'{key}' is required")
    return value.strip()


def _unwrap(result: Any) -> dict:
    """The runner signals failure by returning {"error": ...} rather than
    raising, so every call has to be checked or errors pass silently."""
    if not isinstance(result, dict):
        raise RpcError(RPC_SIDECAR_ERROR, "code runner returned a non-dict result")
    error = result.get("error")
    if error:
        # Unknown run / not approved / no code block are all operator-visible
        # input errors, not sidecar faults.
        raise RpcError(RPC_INVALID_PARAMS, str(error))
    return result


def plan(params: Any) -> dict:
    """Generate a plan and its code block. Executes nothing."""
    task = _require_str(params, "task")
    trace_id = params.get("trace_id")
    if trace_id is not None and not isinstance(trace_id, str):
        raise RpcError(RPC_INVALID_PARAMS, "'trace_id' must be a string")

    try:
        result = _require_runner().plan(task, trace_id=trace_id)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"code planning failed: {e}") from e
    return _unwrap(result)


def approve(params: Any) -> dict:
    """Approve a plan, permitting execution. The human gate."""
    run_id = _require_str(params, "run_id")
    comment = params.get("comment") or ""
    if not isinstance(comment, str):
        raise RpcError(RPC_INVALID_PARAMS, "'comment' must be a string")

    return _unwrap(_require_runner().approve(run_id, comment))


def execute(params: Any) -> dict:
    """Run an APPROVED plan. The runner refuses anything else."""
    run_id = _require_str(params, "run_id")
    try:
        result = _require_runner().execute(run_id)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"code execution failed: {e}") from e
    return _unwrap(result)


def status(params: Any) -> dict:
    run_id = _require_str(params, "run_id")
    return _unwrap(_require_runner().get_status(run_id))


def sandbox_status(params: Any = None) -> dict:
    """Whether execution would be isolated — answered BEFORE approving.

    Docker present: `docker run --rm --network none`. Absent: a local
    subprocess on the operator's own machine, with no isolation at all. The web
    API surfaces this only in the execute result, by which point the code has
    already run.
    """
    check = _docker_check
    if check is None:
        from src.integrations.autogen_runner import _check_docker as check

    try:
        available = bool(check())
    except Exception:  # noqa: BLE001 — probing must never fail the call
        logger.warning("docker probe failed; assuming unavailable", exc_info=True)
        available = False

    if available:
        return {"docker_available": True, "sandbox": "docker", "isolated": True}
    return {
        "docker_available": False,
        "sandbox": "local_subprocess",
        "isolated": False,
        "warning": (
            "Docker is not available — approved code will run in a local "
            "subprocess on this machine, with no isolation."
        ),
    }

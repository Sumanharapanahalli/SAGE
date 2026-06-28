"""Handler for the build pipeline (``src.integrations.build_orchestrator``).

The orchestrator uses a return-dict-with-``error``-key convention instead
of exceptions. We translate those dicts to typed ``RpcError`` codes so
the UI gets the same ``DesktopError`` variants it already handles for
every other handler.

Error mapping:
    ``{"error": "... not found"}`` → ``RPC_INVALID_PARAMS``
    ``{"error": "Run is not awaiting approval..."}`` → ``RPC_INVALID_PARAMS``
    Python exception (e.g. decomposer failure) → ``RPC_SIDECAR_ERROR``
    Missing module var → ``RPC_SIDECAR_ERROR``
"""
from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

# Wired at startup by app._wire_handlers
_orch: Optional[Any] = None


def _require_orch() -> Any:
    if _orch is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "build_orchestrator is not wired (SAGE import failed)",
        )
    return _orch


def _require_dict(params: Any) -> dict:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    return params


def start(params: Any):
    p = _require_dict(params)
    description = p.get("product_description")
    if not isinstance(description, str) or not description.strip():
        raise RpcError(RPC_INVALID_PARAMS, "product_description is required")

    orch = _require_orch()
    try:
        result = orch.start(
            product_description=description,
            solution_name=p.get("solution_name") or "",
            repo_url=p.get("repo_url") or "",
            workspace_dir=p.get("workspace_dir") or "",
            critic_threshold=int(p.get("critic_threshold") or 70),
            hitl_level=p.get("hitl_level") or "standard",
        )
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"build_orchestrator.start failed: {e}") from e

    if isinstance(result, dict) and result.get("error"):
        raise RpcError(RPC_SIDECAR_ERROR, result["error"])
    return result


def list_runs(_params: Any):
    orch = _require_orch()
    try:
        return orch.list_runs()
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"build_orchestrator.list_runs failed: {e}") from e


def get(params: Any):
    p = _require_dict(params)
    run_id = p.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise RpcError(RPC_INVALID_PARAMS, "run_id is required")

    orch = _require_orch()
    try:
        result = orch.get_status(run_id)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"build_orchestrator.get_status failed: {e}") from e

    if isinstance(result, dict) and result.get("error"):
        raise RpcError(RPC_INVALID_PARAMS, result["error"])
    return result


def approve_stage(params: Any):
    """Unified approve/reject gate — routes to approve_plan, approve_build,
    or reject based on current state and ``approved`` flag.

    Mirrors the HTTP POST /build/approve/{run_id} behavior.
    """
    p = _require_dict(params)
    run_id = p.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise RpcError(RPC_INVALID_PARAMS, "run_id is required")
    approved = bool(p.get("approved"))
    feedback = p.get("feedback") or ""

    orch = _require_orch()

    if not approved:
        try:
            result = orch.reject(run_id, feedback)
        except Exception as e:  # noqa: BLE001
            raise RpcError(RPC_SIDECAR_ERROR, f"reject failed: {e}") from e
        if isinstance(result, dict) and result.get("error"):
            raise RpcError(RPC_INVALID_PARAMS, result["error"])
        return result

    # approved=True — pick the right routing from current state
    try:
        status = orch.get_status(run_id)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"get_status failed: {e}") from e
    if isinstance(status, dict) and status.get("error"):
        raise RpcError(RPC_INVALID_PARAMS, status["error"])

    state = (status or {}).get("state", "")
    if state == "awaiting_plan":
        try:
            result = orch.approve_plan(run_id, feedback=feedback)
        except Exception as e:  # noqa: BLE001
            raise RpcError(RPC_SIDECAR_ERROR, f"approve_plan failed: {e}") from e
    elif state == "awaiting_build":
        try:
            result = orch.approve_build(run_id, feedback=feedback)
        except Exception as e:  # noqa: BLE001
            raise RpcError(RPC_SIDECAR_ERROR, f"approve_build failed: {e}") from e
    else:
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"Run is not awaiting approval (state: {state})",
        )

    if isinstance(result, dict) and result.get("error"):
        raise RpcError(RPC_INVALID_PARAMS, result["error"])
    return result

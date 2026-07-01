"""Workflow handler — exposes src.integrations.langgraph_runner to desktop.

Ports the LangGraph workflow endpoints (Phase 3 of the web API):
    GET  /workflow/list          -> list_workflows
    POST /workflow/run           -> run
    POST /workflow/resume        -> resume
    GET  /workflow/status/{id}   -> status

Mermaid-diagram discovery (GET /workflows, GET /workflows/{solution}/{name})
is a separate, lower-value visualization feature and is deliberately not
ported here.

Like compliance_flags.py, langgraph_runner is a module-level *singleton
instance* — there is no store/instance to wire at startup, so these
handlers import it directly at call time rather than reading an injected
module-level variable.

langgraph_runner reports "unavailable" gracefully on its own (empty
workflow list, or an ``error`` key in run/resume/status results) whenever
orchestration.engine != "langgraph" or the langgraph package isn't
installed — it never raises for that case. We translate its
dict-with-"error"-key convention to a typed RpcError (mirrors
handlers.builds's translation of build_orchestrator's error dicts):

    ``{"error": "..."}`` from run/resume/status -> ``RPC_INVALID_PARAMS``
    Python exception -> ``RPC_SIDECAR_ERROR``
"""
from __future__ import annotations

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError


def list_workflows(params: dict) -> dict:
    try:
        from src.integrations.langgraph_runner import langgraph_runner
        workflows = langgraph_runner.list_workflows()
        return {"workflows": workflows, "count": len(workflows)}
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"workflow.list_workflows failed: {e}") from e


def run(params: dict) -> dict:
    workflow_name = params.get("workflow_name")
    if not workflow_name or not isinstance(workflow_name, str):
        raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'workflow_name'")
    initial_state = params.get("state", {})
    if not isinstance(initial_state, dict):
        raise RpcError(RPC_INVALID_PARAMS, "'state' must be an object")

    try:
        from src.integrations.langgraph_runner import langgraph_runner
        result = langgraph_runner.run(workflow_name, initial_state)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"workflow.run failed: {e}") from e

    if isinstance(result, dict) and result.get("error"):
        raise RpcError(RPC_INVALID_PARAMS, result["error"])
    return result


def resume(params: dict) -> dict:
    run_id = params.get("run_id")
    if not run_id or not isinstance(run_id, str):
        raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'run_id'")
    feedback = params.get("feedback", {})
    if not isinstance(feedback, dict):
        raise RpcError(RPC_INVALID_PARAMS, "'feedback' must be an object")

    try:
        from src.integrations.langgraph_runner import langgraph_runner
        result = langgraph_runner.resume(run_id, feedback)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"workflow.resume failed: {e}") from e

    if isinstance(result, dict) and result.get("error"):
        raise RpcError(RPC_INVALID_PARAMS, result["error"])
    return result


def status(params: dict) -> dict:
    run_id = params.get("run_id")
    if not run_id or not isinstance(run_id, str):
        raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'run_id'")

    try:
        from src.integrations.langgraph_runner import langgraph_runner
        result = langgraph_runner.get_status(run_id)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"workflow.status failed: {e}") from e

    if isinstance(result, dict) and result.get("error"):
        raise RpcError(RPC_INVALID_PARAMS, result["error"])
    return result

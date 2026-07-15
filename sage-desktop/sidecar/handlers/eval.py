"""Eval suite (Agent Gym) handlers — ports src.core.eval_runner.

    GET  /eval/suites   -> list_suites
    POST /eval/run      -> run
    GET  /eval/history  -> history

Scope note, genuine per-solution isolation: EvalRunner accepts a db_path
constructor arg (like TaskQueue / GoalsStore), so app._wire_handlers
injects one backed by THIS solution's ``.sage/eval_runs.db`` rather than
the framework-shared ``data/eval_results.db`` the web API's global
``eval_runner`` singleton uses — same pattern as Phase 5l (queue) / 5m
(goals).

Correctness note: EvalRunner.list_suites()/run() resolve the suites
directory via ``eval_runner._get_evals_dir()``, which reads the framework
*global* ``src.core.project_loader.project_config`` singleton — not an
injectable instance. That singleton is constructed at import time from
``SAGE_PROJECT``/auto-discovery, not this sidecar's ``--solution-name``.
app._wire_handlers must call ``project_config.reload(solution_name)`` (in
addition to constructing the locally-injected ``ProjectConfig`` used
elsewhere) or eval suite listing silently resolves the wrong solution's
``evals/`` directory.
"""

from __future__ import annotations

from rpc import RPC_INVALID_PARAMS, RPC_SAGE_IMPORT_ERROR, RPC_SIDECAR_ERROR, RpcError

_runner = None


def _require_runner():
    if _runner is None:
        raise RpcError(
            RPC_SAGE_IMPORT_ERROR,
            "eval runner unavailable",
            {"module": "src.core.eval_runner", "detail": "not initialised"},
        )
    return _runner


def list_suites(params: dict) -> dict:
    runner = _require_runner()
    try:
        suites = runner.list_suites()
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"eval.list_suites failed: {e}") from e
    return {"suites": suites, "count": len(suites)}


def run(params: dict) -> dict:
    runner = _require_runner()
    suite = params.get("suite") or None
    if suite is not None and not isinstance(suite, str):
        raise RpcError(RPC_INVALID_PARAMS, "'suite' must be a string")

    try:
        result = runner.run(suite=suite)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"eval.run failed: {e}") from e

    if isinstance(result, dict) and result.get("error"):
        raise RpcError(RPC_INVALID_PARAMS, result["error"])
    return result


def history(params: dict) -> dict:
    runner = _require_runner()
    suite = params.get("suite") or None
    limit = params.get("limit", 20)
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise RpcError(RPC_INVALID_PARAMS, "'limit' must be an integer")

    try:
        rows = runner.get_history(suite=suite, limit=limit)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"eval.history failed: {e}") from e
    return {"history": rows, "count": len(rows)}

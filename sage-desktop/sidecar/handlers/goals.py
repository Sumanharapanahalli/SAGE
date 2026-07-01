"""Goals / OKR persistence handlers.

Scope note: the web API (``src/interface/api.py``'s ``_get_goals_store()``)
resolves ``goals.db`` next to the shared audit_logger's db path — a
framework-shared location, not a per-solution one. This handler
deliberately diverges: ``goals.db`` is wired by ``app._wire_handlers``
inside THIS solution's own ``.sage/`` directory, matching every other
per-solution store on desktop (proposals.db, audit_log.db, queue.db). That
gives genuine per-solution isolation the web API's shared-file resolution
doesn't — the same kind of documented, deliberate divergence as
``org.py``'s ``SAGE_SOLUTIONS_DIR`` gap.

The desktop is a single-operator interface, so ``user_id`` defaults to
"desktop-operator" when the caller omits it (mirrors ``approvals.py``
defaulting ``decided_by`` to "human"). ``GoalsStore.list()`` filters on
exact (user_id, solution) equality — there is no "unset = match all"
branch — so ``create()`` and ``list()`` MUST default both fields
identically, or goals created via the default path become invisible to
the default list query.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SAGE_IMPORT_ERROR, RpcError

_store = None

_DEFAULT_USER_ID = "desktop-operator"
_DEFAULT_SOLUTION = ""

_UPDATABLE_FIELDS = ("title", "quarter", "status", "owner", "key_results")


def _require_store():
    if _store is None:
        raise RpcError(
            RPC_SAGE_IMPORT_ERROR,
            "goals store unavailable",
            {"module": "src.stores.goals_store", "detail": "not initialised"},
        )
    return _store


def _require_goal_id(params: dict) -> str:
    goal_id = params.get("goal_id")
    if not goal_id:
        raise RpcError(RPC_INVALID_PARAMS, "goal_id required")
    return goal_id


def _not_found(goal_id: str) -> RpcError:
    return RpcError(
        RPC_INVALID_PARAMS, f"goal not found: {goal_id}", {"goal_id": goal_id}
    )


def list(params: dict):  # noqa: A001 - mirrors org.py's builtin-shadowing precedent
    store = _require_store()
    user_id = params.get("user_id") or _DEFAULT_USER_ID
    solution = params.get("solution") or _DEFAULT_SOLUTION
    quarter: Optional[str] = params.get("quarter") or None
    return store.list(user_id, solution, quarter=quarter)


def create(params: dict) -> dict:
    store = _require_store()
    title = params.get("title")
    if not title:
        raise RpcError(RPC_INVALID_PARAMS, "title required")
    quarter = params.get("quarter")
    if not quarter:
        raise RpcError(RPC_INVALID_PARAMS, "quarter required")

    user_id = params.get("user_id") or _DEFAULT_USER_ID
    solution = params.get("solution") or _DEFAULT_SOLUTION
    status = params.get("status") or "on_track"
    owner = params.get("owner") or ""
    key_results = params.get("key_results")
    if key_results is None:
        key_results = []

    return store.create(user_id, solution, title, quarter, status, owner, key_results)


def get(params: dict) -> dict:  # noqa: A001
    store = _require_store()
    goal_id = _require_goal_id(params)
    goal = store.get(goal_id)
    if goal is None:
        raise _not_found(goal_id)
    return goal


def update(params: dict) -> dict:
    store = _require_store()
    goal_id = _require_goal_id(params)
    kwargs: Dict[str, Any] = {
        field: params[field] for field in _UPDATABLE_FIELDS if params.get(field) is not None
    }
    result = store.update(goal_id, **kwargs)
    if result is None:
        raise _not_found(goal_id)
    return result


def delete(params: dict) -> dict:  # noqa: A001
    store = _require_store()
    goal_id = _require_goal_id(params)
    if not store.delete(goal_id):
        raise _not_found(goal_id)
    return {"deleted": True}

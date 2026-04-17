"""Handler for Collective Intelligence (Phase 5a).

Proxies ``src.core.collective_memory.CollectiveMemory`` — the
git-backed cross-solution knowledge-sharing surface. Twelve RPC
methods cover learnings (list/get/search/publish/validate), help
requests (list/create/claim/respond/close), and maintenance
(sync/stats).

Law 1: operator-driven actions bypass the proposal queue; agent
``publish_learning`` still flows through ``collective_publish``
proposals when the framework is configured with
``require_approval=True`` (default).

Module-level ``_cm`` is wired at startup by ``app._wire_handlers``;
if the import or singleton construction fails, every handler
returns ``SidecarError`` with a typed message so the UI can render
a single disabled state.
"""
from __future__ import annotations

from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

_LIMIT_MAX = 500
_LIMIT_DEFAULT = 50
_SEARCH_LIMIT_MAX = 50
_SEARCH_LIMIT_DEFAULT = 10

_URGENCIES = {"low", "medium", "high", "critical"}
_STATUSES = {"open", "closed"}

_cm: Optional[Any] = None


def _require_cm() -> Any:
    if _cm is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "collective handlers are not wired (CollectiveMemory import or construction failed)",
        )
    return _cm


def _require_dict(params: Any) -> dict:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    return params


def _coerce_int(value: Any, name: str, default: int, lo: int, hi: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise RpcError(RPC_INVALID_PARAMS, f"'{name}' must be an integer")
    if value < lo or value > hi:
        raise RpcError(RPC_INVALID_PARAMS, f"'{name}' must be between {lo} and {hi}")
    return value


def _require_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RpcError(RPC_INVALID_PARAMS, f"'{name}' must be a non-empty string")
    return value


def _optional_str_list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise RpcError(RPC_INVALID_PARAMS, f"'{name}' must be a list of strings")
    return value


# ── RPC methods ──────────────────────────────────────────────────


def list_learnings(params: Any) -> dict:
    p = _require_dict(params)
    solution = p.get("solution")
    topic = p.get("topic")
    if solution is not None and not isinstance(solution, str):
        raise RpcError(RPC_INVALID_PARAMS, "'solution' must be a string")
    if topic is not None and not isinstance(topic, str):
        raise RpcError(RPC_INVALID_PARAMS, "'topic' must be a string")
    limit = _coerce_int(p.get("limit"), "limit", _LIMIT_DEFAULT, 1, _LIMIT_MAX)
    offset = _coerce_int(p.get("offset"), "offset", 0, 0, 10_000_000)

    cm = _require_cm()
    try:
        full = cm.list_learnings(
            solution=solution or None, topic=topic or None, limit=10_000_000, offset=0
        )
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"list_learnings failed: {e}") from e

    total = len(full)
    entries = full[offset: offset + limit]
    return {
        "entries": entries,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_learning(params: Any) -> dict:
    p = _require_dict(params)
    learning_id = _require_str(p.get("id"), "id")

    cm = _require_cm()
    try:
        result = cm.get_learning(learning_id)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"get_learning failed: {e}") from e

    return {"learning": result}

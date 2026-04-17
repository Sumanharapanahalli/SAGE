"""Handler for the Knowledge Browser.

Phase 5c — expose the active solution's ``VectorMemory`` (ChromaDB +
sentence-transformers, or keyword fallback in minimal mode) so operators
can browse, search, add, and delete entries without FastAPI.

Operator-driven add/delete bypass the proposal queue by the same
rationale as Phase 3b YAML authoring and Phase 5b Constitution: the
human typing in the editor is the human's own action, not an agent
proposal. Agent-proposed changes to the knowledge base continue to flow
through the existing STATEFUL/DESTRUCTIVE proposal kinds unchanged.

Module-level ``_vm`` and ``_solution_name`` are wired at startup by
``app._wire_handlers``; if ``VectorMemory`` import fails or no solution
is active, every handler returns ``SidecarError`` with a typed message
so the UI can render a single disabled state.
"""
from __future__ import annotations

from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

_LIMIT_MAX = 500
_LIMIT_DEFAULT = 50
_TOP_K_MAX = 50
_TOP_K_DEFAULT = 10

_vm: Optional[Any] = None
_solution_name: Optional[str] = None


def _require_vm() -> Any:
    if _vm is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "knowledge handlers are not wired (VectorMemory import failed or no solution active)",
        )
    return _vm


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
        raise RpcError(
            RPC_INVALID_PARAMS, f"'{name}' must be between {lo} and {hi}"
        )
    return value


def _collection_name(vm: Any) -> str:
    name_fn = getattr(vm, "collection_name", None)
    if callable(name_fn):
        try:
            return str(name_fn())
        except Exception:  # noqa: BLE001 — never crash stats
            pass
    getter = getattr(vm, "_get_collection_name", None)
    if callable(getter):
        try:
            return str(getter())
        except Exception:  # noqa: BLE001
            pass
    return "unknown"


def _total(vm: Any) -> int:
    total_fn = getattr(vm, "total", None)
    if callable(total_fn):
        try:
            return int(total_fn())
        except Exception:  # noqa: BLE001
            pass
    store = getattr(vm, "_vector_store", None)
    if store is not None and getattr(vm, "_ready", False):
        try:
            return int(store._collection.count())  # noqa: SLF001
        except Exception:  # noqa: BLE001
            pass
    fallback = getattr(vm, "_fallback_memory", None)
    if fallback is not None:
        try:
            return len(fallback)
        except Exception:  # noqa: BLE001
            pass
    return 0


def _backend_label(mode: str) -> str:
    # llamaindex is a superset of full for the UI's purposes — both mean
    # semantic search is available.
    return "full" if mode == "llamaindex" else mode


def _normalize_hit(item: Any) -> dict:
    if isinstance(item, str):
        return {"text": item}
    if isinstance(item, dict):
        hit = {"text": str(item.get("text", ""))}
        if "id" in item:
            hit["id"] = item["id"]
        if "score" in item:
            hit["score"] = item["score"]
        if "metadata" in item:
            hit["metadata"] = item["metadata"]
        return hit
    return {"text": str(item)}


# ── RPC methods ────────────────────────────────────────────────────────────

def list_entries(params: Any) -> dict:
    p = _require_dict(params)
    limit = _coerce_int(p.get("limit"), "limit", _LIMIT_DEFAULT, 1, _LIMIT_MAX)
    offset = _coerce_int(p.get("offset"), "offset", 0, 0, 10_000_000)

    vm = _require_vm()
    try:
        raw = vm.list_entries(limit=offset + limit)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"list_entries failed: {e}") from e

    entries = [
        {
            "id": str(r.get("id", "")),
            "text": str(r.get("text", "")),
            "metadata": r.get("metadata") or {},
        }
        for r in raw[offset : offset + limit]
    ]
    return {
        "entries": entries,
        "total": _total(vm),
        "limit": limit,
        "offset": offset,
    }


def search(params: Any) -> dict:
    p = _require_dict(params)
    query = p.get("query")
    if not isinstance(query, str) or not query.strip():
        raise RpcError(RPC_INVALID_PARAMS, "'query' must be a non-empty string")
    top_k = _coerce_int(p.get("top_k"), "top_k", _TOP_K_DEFAULT, 1, _TOP_K_MAX)

    vm = _require_vm()
    try:
        raw = vm.search(query, k=top_k)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"search failed: {e}") from e

    results = [_normalize_hit(item) for item in (raw or [])]
    return {"query": query, "results": results, "count": len(results)}


def add(params: Any) -> dict:
    p = _require_dict(params)
    text = p.get("text")
    if not isinstance(text, str):
        raise RpcError(RPC_INVALID_PARAMS, "'text' must be a string")
    if not text.strip():
        raise RpcError(RPC_INVALID_PARAMS, "'text' must be non-empty")
    metadata = p.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise RpcError(RPC_INVALID_PARAMS, "'metadata' must be an object")

    vm = _require_vm()
    try:
        entry_id = vm.add_entry(text, metadata=metadata)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"add_entry failed: {e}") from e

    return {"id": str(entry_id), "text": text, "metadata": metadata}


def delete(params: Any) -> dict:
    p = _require_dict(params)
    entry_id = p.get("id")
    if not isinstance(entry_id, str) or not entry_id.strip():
        raise RpcError(RPC_INVALID_PARAMS, "'id' must be a non-empty string")

    vm = _require_vm()
    try:
        deleted = bool(vm.delete_entry(entry_id))
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"delete_entry failed: {e}") from e

    return {"id": entry_id, "deleted": deleted}


def stats(params: Any) -> dict:
    if params is not None and not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    vm = _require_vm()
    mode = str(getattr(vm, "mode", "minimal"))
    return {
        "total": _total(vm),
        "collection": _collection_name(vm),
        "backend": _backend_label(mode),
        "solution": _solution_name or "unknown",
    }

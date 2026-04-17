"""Feature request (backlog) handlers."""
from __future__ import annotations

from typing import Any, Dict, Optional

from rpc import (
    RpcError,
    RPC_INVALID_PARAMS,
    RPC_SAGE_IMPORT_ERROR,
    RPC_FEATURE_REQUEST_NOT_FOUND,
)

_store = None


def _require_store():
    if _store is None:
        raise RpcError(
            RPC_SAGE_IMPORT_ERROR,
            "feature request store unavailable",
            {"module": "src.core.feature_request_store", "detail": "not initialised"},
        )
    return _store


def submit_feature_request(params: dict) -> dict:
    store = _require_store()
    title = params.get("title") or ""
    description = params.get("description") or ""
    kwargs: Dict[str, Any] = {
        "title": title,
        "description": description,
        "module_id": params.get("module_id", "general"),
        "module_name": params.get("module_name", "General"),
        "priority": params.get("priority", "medium"),
        "requested_by": params.get("requested_by", "anonymous"),
        "scope": params.get("scope", "solution"),
    }
    try:
        fr = store.submit(**kwargs)
    except ValueError as e:
        raise RpcError(RPC_INVALID_PARAMS, str(e)) from e
    return fr.to_dict()


def list_feature_requests(params: dict) -> list:
    store = _require_store()
    status: Optional[str] = params.get("status") or None
    scope: Optional[str] = params.get("scope") or None
    return [fr.to_dict() for fr in store.list(status=status, scope=scope)]


def update_feature_request(params: dict) -> dict:
    store = _require_store()
    fid = params.get("id")
    if not fid:
        raise RpcError(RPC_INVALID_PARAMS, "id required")
    action = params.get("action")
    if not action:
        raise RpcError(RPC_INVALID_PARAMS, "action required")
    note = params.get("reviewer_note", "")
    try:
        fr = store.update(fid, action=action, reviewer_note=note)
    except KeyError:
        raise RpcError(
            RPC_FEATURE_REQUEST_NOT_FOUND,
            f"feature request not found: {fid}",
            {"feature_id": fid},
        ) from None
    except ValueError as e:
        raise RpcError(RPC_INVALID_PARAMS, str(e)) from e
    return fr.to_dict()

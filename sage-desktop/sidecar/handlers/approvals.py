"""Approvals handler — wraps ProposalStore for the desktop UI.

Translates ProposalStore's generic ValueError into the domain-specific
RpcError subclasses from errors.py so the Rust side can render typed
banners ("already decided", "expired", "not found") instead of a single
opaque failure message.
"""
from __future__ import annotations

from typing import Optional

from rpc import RpcError, RPC_INVALID_PARAMS
from errors import ProposalNotFound, ProposalExpired, AlreadyDecided

# Injected by __main__.py at startup. Tests monkey-patch this.
_store = None  # type: Optional[object]


def _require_store():
    if _store is None:
        raise RpcError(RPC_INVALID_PARAMS, "proposal store not initialized")
    return _store


def _require_trace_id(params: dict) -> str:
    trace_id = params.get("trace_id")
    if not trace_id or not isinstance(trace_id, str):
        raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'trace_id'")
    return trace_id


def _translate_value_error(trace_id: str, err: ValueError, store) -> RpcError:
    """Map ProposalStore.approve/reject ValueError → typed RpcError.

    Messages from proposal_store are of the form:
      "Proposal 'X' not found."
      "Proposal 'X' is already approved."   (or rejected / expired)
    """
    msg = str(err)
    if "not found" in msg:
        return ProposalNotFound(trace_id)
    # Already-decided case — inspect the current status to pick the right error.
    current = store.get(trace_id)
    if current is not None:
        if current.status == "expired":
            return ProposalExpired(trace_id)
        return AlreadyDecided(trace_id, current.status)
    return ProposalNotFound(trace_id)


# ---------- handlers ----------

def list_pending(params: dict) -> list[dict]:
    store = _require_store()
    return [p.model_dump(mode="json") for p in store.get_pending()]


def get(params: dict) -> dict:
    store = _require_store()
    trace_id = _require_trace_id(params)
    p = store.get(trace_id)
    if p is None:
        raise ProposalNotFound(trace_id)
    return p.model_dump(mode="json")


def approve(params: dict) -> dict:
    store = _require_store()
    trace_id = _require_trace_id(params)
    decided_by = params.get("decided_by", "human")
    feedback = params.get("feedback", "")
    try:
        p = store.approve(trace_id, decided_by=decided_by, feedback=feedback)
    except ValueError as e:
        raise _translate_value_error(trace_id, e, store) from e
    return p.model_dump(mode="json")


def reject(params: dict) -> dict:
    store = _require_store()
    trace_id = _require_trace_id(params)
    decided_by = params.get("decided_by", "human")
    feedback = params.get("feedback", "")
    try:
        p = store.reject(trace_id, decided_by=decided_by, feedback=feedback)
    except ValueError as e:
        raise _translate_value_error(trace_id, e, store) from e
    return p.model_dump(mode="json")


def batch_approve(params: dict) -> dict:
    """Approve many proposals; per-item success/failure, never aborts.

    Phase 1 intentionally keeps this as a handler-level loop rather than a
    transaction — individual ValueErrors from the store are caught and
    reported per trace_id so a single bad id doesn't block the rest.
    """
    store = _require_store()
    trace_ids = params.get("trace_ids", [])
    if not isinstance(trace_ids, list):
        raise RpcError(RPC_INVALID_PARAMS, "'trace_ids' must be a list")
    decided_by = params.get("decided_by", "human")
    feedback = params.get("feedback", "")

    results = []
    for trace_id in trace_ids:
        if not isinstance(trace_id, str):
            results.append({
                "trace_id": trace_id,
                "ok": False,
                "error": {"code": RPC_INVALID_PARAMS, "message": "trace_id must be a string"},
            })
            continue
        try:
            p = store.approve(trace_id, decided_by=decided_by, feedback=feedback)
            results.append({"trace_id": trace_id, "ok": True, "proposal": p.model_dump(mode="json")})
        except ValueError as e:
            err = _translate_value_error(trace_id, e, store)
            results.append({
                "trace_id": trace_id,
                "ok": False,
                "error": {"code": err.code, "message": err.message, "data": err.data},
            })
    return {"results": results}

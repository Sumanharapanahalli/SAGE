"""Handler for the per-solution Constitution.

Phase 5b — Constitution authoring. Operator-driven edits bypass the
proposal queue by the same rationale as Phase 3b YAML authoring: the
human typing in the editor is the human's own action, not an agent
proposal. Agent-proposed constitution changes still flow through the
``yaml_edit`` proposal kind unchanged.

The concrete ``Constitution`` instance is wired at startup by
``app._wire_handlers``; if the import fails (e.g. missing deps) the
handlers degrade gracefully to typed ``SidecarError`` responses.
"""
from __future__ import annotations

from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

_ctx: Optional[Any] = None


def _require_ctx() -> Any:
    if _ctx is None:
        raise RpcError(
            RPC_SIDECAR_ERROR,
            "constitution handlers are not wired (Constitution import failed or no solution active)",
        )
    return _ctx


def _state_payload(c: Any) -> dict:
    return {
        "data": c.to_dict(),
        "stats": c.get_stats(),
        "preamble": c.build_prompt_preamble(),
        "history": c.get_version_history(),
        "errors": c.validate(),
    }


def get(params: Any) -> dict:
    if params is not None and not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    c = _require_ctx()
    c.reload()
    return _state_payload(c)


def update(params: Any) -> dict:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    data = params.get("data")
    if not isinstance(data, dict):
        raise RpcError(RPC_INVALID_PARAMS, "'data' must be an object")
    changed_by = params.get("changed_by") or "desktop"
    if not isinstance(changed_by, str):
        raise RpcError(RPC_INVALID_PARAMS, "'changed_by' must be a string")

    c = _require_ctx()
    # Replace the in-memory state, then validate before writing to disk.
    c._data = data  # noqa: SLF001 — sidecar is the one controlled writer
    errors = c.validate()
    if errors:
        # Reload on-disk state so in-memory doesn't drift past the rejected edit.
        c.reload()
        raise RpcError(
            RPC_INVALID_PARAMS,
            "constitution validation failed: " + "; ".join(errors),
            data={"errors": errors},
        )
    try:
        c.save(changed_by=changed_by)
    except OSError as e:
        c.reload()
        raise RpcError(RPC_SIDECAR_ERROR, f"failed to write constitution: {e}") from e

    return {
        "stats": c.get_stats(),
        "preamble": c.build_prompt_preamble(),
        "version": c.version,
        "path": c._path,  # noqa: SLF001
    }


def preamble(params: Any) -> dict:
    if params is not None and not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    c = _require_ctx()
    return {"preamble": c.build_prompt_preamble()}


def check_action(params: Any) -> dict:
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    desc = params.get("action_description")
    if not isinstance(desc, str) or not desc.strip():
        raise RpcError(
            RPC_INVALID_PARAMS, "'action_description' must be a non-empty string"
        )
    c = _require_ctx()
    return c.check_action(desc)

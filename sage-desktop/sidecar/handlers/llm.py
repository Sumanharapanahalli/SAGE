"""LLM handler — current provider info and runtime switch."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict

from rpc import (
    RpcError,
    RPC_INVALID_PARAMS,
    RPC_SAGE_IMPORT_ERROR,
    RPC_SIDECAR_ERROR,
)

_gateway = None


def _require_gateway():
    if _gateway is None:
        raise RpcError(
            RPC_SAGE_IMPORT_ERROR,
            "LLM gateway unavailable",
            {"module": "src.core.llm_gateway", "detail": "not initialised"},
        )
    return _gateway


def _current_model(gw) -> str:
    provider = getattr(gw, "provider", None)
    for attr in ("model", "model_name", "_model"):
        value = getattr(provider, attr, None)
        if isinstance(value, str) and value:
            return value
    return ""


def get_llm_info(_params: dict) -> dict:
    gw = _require_gateway()
    return {
        "provider_name": gw.get_provider_name(),
        "model": _current_model(gw),
        "available_providers": gw.list_providers(),
    }


@dataclass
class _SyntheticProposal:
    """Minimum shape for proposal_executor._execute_llm_switch."""

    payload: Dict[str, Any] = field(default_factory=dict)
    action_type: str = "llm_switch"
    trace_id: str = "desktop-switch"


async def _run_execute_llm_switch(proposal):
    from src.core.proposal_executor import _execute_llm_switch

    return await _execute_llm_switch(proposal)


def switch_llm(params: dict) -> dict:
    _require_gateway()
    provider = (params.get("provider") or "").strip()
    if not provider:
        raise RpcError(RPC_INVALID_PARAMS, "provider must be non-empty")

    proposal = _SyntheticProposal(
        payload={
            "provider": provider,
            "model": params.get("model"),
            "save_as_default": bool(params.get("save_as_default", False)),
            "claude_path": params.get("claude_path"),
        }
    )
    try:
        return asyncio.run(_run_execute_llm_switch(proposal))
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"llm switch failed: {e}") from e

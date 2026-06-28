"""Method-name → handler registry for the sidecar.

Handlers are plain functions that take the `params` dict and return any
JSON-serializable value. RpcError from a handler propagates unchanged;
anything else becomes an RPC_INTERNAL_ERROR so the wire stays clean.
"""
from __future__ import annotations

from typing import Callable, Dict, List

from rpc import (
    Request,
    RpcError,
    RPC_METHOD_NOT_FOUND,
    RPC_INTERNAL_ERROR,
)

Handler = Callable[[dict], object]


class Dispatcher:
    def __init__(self) -> None:
        self._handlers: Dict[str, Handler] = {}

    def register(self, method: str, handler: Handler) -> None:
        self._handlers[method] = handler

    def methods(self) -> List[str]:
        return list(self._handlers.keys())

    def dispatch(self, req: Request) -> object:
        handler = self._handlers.get(req.method)
        if handler is None:
            raise RpcError(RPC_METHOD_NOT_FOUND, f"method not found: {req.method}")
        try:
            return handler(req.params)
        except RpcError:
            raise
        except Exception as e:  # noqa: BLE001 — intentional catch-all
            raise RpcError(RPC_INTERNAL_ERROR, f"internal error: {e}") from e

"""Unit tests for the method dispatcher."""
from __future__ import annotations

import pytest

from dispatcher import Dispatcher
from rpc import (
    Request,
    RpcError,
    RPC_METHOD_NOT_FOUND,
    RPC_INVALID_PARAMS,
    RPC_INTERNAL_ERROR,
)


def test_dispatch_unknown_method_returns_method_not_found():
    d = Dispatcher()
    with pytest.raises(RpcError) as exc:
        d.dispatch(Request(id="1", method="nope", params={}))
    assert exc.value.code == RPC_METHOD_NOT_FOUND


def test_dispatch_calls_registered_handler_and_returns_result():
    d = Dispatcher()
    d.register("ping", lambda params: {"pong": True})
    assert d.dispatch(Request(id="1", method="ping", params={})) == {"pong": True}


def test_dispatch_passes_params_to_handler():
    d = Dispatcher()
    seen: dict = {}

    def handler(params: dict) -> str:
        seen.update(params)
        return "ok"

    d.register("echo", handler)
    d.dispatch(Request(id="1", method="echo", params={"a": 1, "b": 2}))
    assert seen == {"a": 1, "b": 2}


def test_dispatch_wraps_unexpected_exception_as_internal_error():
    d = Dispatcher()

    def boom(params: dict) -> None:
        raise ValueError("kaboom")

    d.register("boom", boom)
    with pytest.raises(RpcError) as exc:
        d.dispatch(Request(id="1", method="boom", params={}))
    assert exc.value.code == RPC_INTERNAL_ERROR
    assert "kaboom" in exc.value.message


def test_dispatch_propagates_rpc_error_unchanged():
    d = Dispatcher()

    def raises_rpc(params: dict) -> None:
        raise RpcError(RPC_INVALID_PARAMS, "bad field", {"field": "x"})

    d.register("bad", raises_rpc)
    with pytest.raises(RpcError) as exc:
        d.dispatch(Request(id="1", method="bad", params={}))
    assert exc.value.code == RPC_INVALID_PARAMS
    assert exc.value.data == {"field": "x"}


def test_register_twice_overwrites():
    d = Dispatcher()
    d.register("x", lambda p: 1)
    d.register("x", lambda p: 2)
    assert d.dispatch(Request(id="1", method="x", params={})) == 2


def test_methods_list_includes_registered():
    d = Dispatcher()
    d.register("a", lambda p: None)
    d.register("b", lambda p: None)
    assert set(d.methods()) == {"a", "b"}


def test_methods_empty_on_fresh_dispatcher():
    assert Dispatcher().methods() == []

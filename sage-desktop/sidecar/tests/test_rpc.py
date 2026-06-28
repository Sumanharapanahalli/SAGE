"""Unit tests for the JSON-RPC 2.0 / NDJSON framing layer."""
from __future__ import annotations

import io
import pytest

from rpc import (
    parse_request,
    build_response,
    build_error,
    RpcError,
    RPC_PARSE_ERROR,
    RPC_INVALID_REQUEST,
    RPC_INVALID_PARAMS,
    read_ndjson_requests,
    write_ndjson_response,
)


def test_parse_request_accepts_valid_jsonrpc_2_0():
    req = parse_request('{"jsonrpc":"2.0","id":"1","method":"handshake","params":{}}')
    assert req.id == "1"
    assert req.method == "handshake"
    assert req.params == {}


def test_parse_request_defaults_params_to_empty_dict():
    req = parse_request('{"jsonrpc":"2.0","id":"1","method":"ping"}')
    assert req.params == {}


def test_parse_request_rejects_wrong_version():
    with pytest.raises(RpcError) as exc:
        parse_request('{"jsonrpc":"1.0","id":"1","method":"x"}')
    assert exc.value.code == RPC_INVALID_REQUEST


def test_parse_request_rejects_missing_method():
    with pytest.raises(RpcError) as exc:
        parse_request('{"jsonrpc":"2.0","id":"1"}')
    assert exc.value.code == RPC_INVALID_REQUEST


def test_parse_request_rejects_missing_id():
    with pytest.raises(RpcError) as exc:
        parse_request('{"jsonrpc":"2.0","method":"x"}')
    assert exc.value.code == RPC_INVALID_REQUEST


def test_parse_request_rejects_non_object_params():
    with pytest.raises(RpcError) as exc:
        parse_request('{"jsonrpc":"2.0","id":"1","method":"x","params":[1,2]}')
    assert exc.value.code == RPC_INVALID_PARAMS


def test_parse_request_rejects_malformed_json():
    with pytest.raises(RpcError) as exc:
        parse_request("{not json")
    assert exc.value.code == RPC_PARSE_ERROR


def test_parse_request_rejects_non_object_request():
    with pytest.raises(RpcError) as exc:
        parse_request('"just a string"')
    assert exc.value.code == RPC_INVALID_REQUEST


def test_build_response_shape():
    resp = build_response(id="42", result={"ok": True})
    assert resp == {"jsonrpc": "2.0", "id": "42", "result": {"ok": True}}


def test_build_error_with_data():
    resp = build_error(id="42", code=-32000, message="boom", data={"detail": "x"})
    assert resp == {
        "jsonrpc": "2.0",
        "id": "42",
        "error": {"code": -32000, "message": "boom", "data": {"detail": "x"}},
    }


def test_build_error_without_data_omits_field():
    resp = build_error(id="42", code=-32000, message="boom")
    assert "data" not in resp["error"]


def test_build_error_with_null_id():
    """Framing errors emit an error with id=null per JSON-RPC 2.0."""
    resp = build_error(id=None, code=-32700, message="parse error")
    assert resp["id"] is None


def test_read_ndjson_requests_parses_multiple_lines():
    stream = io.StringIO(
        '{"jsonrpc":"2.0","id":"1","method":"a"}\n'
        '{"jsonrpc":"2.0","id":"2","method":"b"}\n'
    )
    reqs = list(read_ndjson_requests(stream))
    assert [r.id for r in reqs] == ["1", "2"]
    assert [r.method for r in reqs] == ["a", "b"]


def test_read_ndjson_requests_skips_blank_lines():
    stream = io.StringIO(
        '{"jsonrpc":"2.0","id":"1","method":"a"}\n'
        "\n"
        '{"jsonrpc":"2.0","id":"2","method":"b"}\n'
    )
    reqs = list(read_ndjson_requests(stream))
    assert len(reqs) == 2


def test_read_ndjson_requests_ignores_trailing_whitespace():
    stream = io.StringIO('{"jsonrpc":"2.0","id":"1","method":"a"}   \n')
    reqs = list(read_ndjson_requests(stream))
    assert len(reqs) == 1


def test_write_ndjson_response_appends_newline():
    out = io.StringIO()
    write_ndjson_response(out, {"jsonrpc": "2.0", "id": "1", "result": 42})
    assert out.getvalue() == '{"jsonrpc": "2.0", "id": "1", "result": 42}\n'


def test_write_ndjson_response_flushes():
    """Flush is important so NDJSON frames reach the Rust reader promptly."""
    class TrackedIO(io.StringIO):
        def __init__(self):
            super().__init__()
            self.flush_count = 0

        def flush(self):
            self.flush_count += 1
            super().flush()

    out = TrackedIO()
    write_ndjson_response(out, {"jsonrpc": "2.0", "id": "1", "result": None})
    assert out.flush_count >= 1

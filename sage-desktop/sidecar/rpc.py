"""JSON-RPC 2.0 over NDJSON framing for the SAGE desktop sidecar.

Pure-Python, no external deps. Framing is one JSON object per line on
stdin and stdout. Every request has an id (notifications are not
supported — keeps Rust correlation simple).

All public names are exported; SAGE-specific error codes are declared
here so the Python handlers and the Rust error mapper share the same
constants via the JSON-RPC wire.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Optional, TextIO

# ── JSON-RPC 2.0 standard codes ────────────────────────────────────────────
RPC_PARSE_ERROR = -32700
RPC_INVALID_REQUEST = -32600
RPC_METHOD_NOT_FOUND = -32601
RPC_INVALID_PARAMS = -32602
RPC_INTERNAL_ERROR = -32603

# ── SAGE-specific codes (per spec §6.1) ────────────────────────────────────
RPC_SIDECAR_ERROR = -32000
RPC_PROPOSAL_EXPIRED = -32001
RPC_RBAC_DENIED = -32002
RPC_PROPOSAL_NOT_FOUND = -32003
RPC_SOLUTION_UNAVAILABLE = -32004
RPC_ALREADY_DECIDED = -32005
RPC_SAGE_IMPORT_ERROR = -32010


class RpcError(Exception):
    """Raised to signal an RPC-level error with a machine-readable code."""

    def __init__(self, code: int, message: str, data: Optional[dict] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


@dataclass
class Request:
    id: str
    method: str
    params: dict


def parse_request(line: str) -> Request:
    """Parse one NDJSON line as a JSON-RPC 2.0 Request object.

    Raises RpcError(code=RPC_PARSE_ERROR) on bad JSON and
    RpcError(code=RPC_INVALID_REQUEST) on shape violations.
    """
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as e:
        raise RpcError(RPC_PARSE_ERROR, f"parse error: {e}") from e

    if not isinstance(obj, dict):
        raise RpcError(RPC_INVALID_REQUEST, "request must be a JSON object")
    if obj.get("jsonrpc") != "2.0":
        raise RpcError(RPC_INVALID_REQUEST, "jsonrpc must be '2.0'")
    method = obj.get("method")
    if not isinstance(method, str):
        raise RpcError(RPC_INVALID_REQUEST, "method required and must be a string")
    req_id = obj.get("id")
    if req_id is None:
        raise RpcError(RPC_INVALID_REQUEST, "id required (notifications not supported)")

    params = obj.get("params", {})
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")

    return Request(id=str(req_id), method=method, params=params)


def build_response(id: str, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def build_error(
    id: Optional[str], code: int, message: str, data: Optional[dict] = None
) -> dict:
    err: dict = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": err}


def read_ndjson_requests(stream: TextIO) -> Iterable[Request]:
    """Yield a Request object for every non-blank line on the stream.

    Exhausts on EOF. Parse errors propagate — the caller decides whether to
    emit an error frame with id=null and continue or abort.
    """
    for raw in stream:
        line = raw.strip()
        if not line:
            continue
        yield parse_request(line)


def write_ndjson_response(stream: TextIO, resp: dict) -> None:
    """Serialize a response dict + newline, then flush.

    Flushing is essential: without it, the Rust reader would block until
    the OS pipe buffer happens to be flushed.
    """
    stream.write(json.dumps(resp) + "\n")
    stream.flush()

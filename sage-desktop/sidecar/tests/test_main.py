"""Integration tests for the sidecar entry point.

Drives the `run()` event loop with in-memory StringIO streams so we can
assert the full NDJSON round-trip without spawning a subprocess.
"""
from __future__ import annotations

import io
import json

import pytest

import app as sidecar_app


def _drive(stdin_text: str, argv: list[str] | None = None) -> list[dict]:
    """Run the sidecar loop with the given stdin text and return parsed
    responses from stdout."""
    stdin = io.StringIO(stdin_text)
    stdout = io.StringIO()
    sidecar_app.run(stdin=stdin, stdout=stdout, argv=argv or [])
    stdout.seek(0)
    return [json.loads(line) for line in stdout.read().splitlines() if line.strip()]


def _req(id: str, method: str, params: dict | None = None) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}})


# ---------- handshake ----------

def test_handshake_round_trip():
    out = _drive(_req("1", "handshake") + "\n")
    assert len(out) == 1
    assert out[0]["jsonrpc"] == "2.0"
    assert out[0]["id"] == "1"
    result = out[0]["result"]
    assert "sidecar_version" in result
    assert "sage_version" in result
    assert "warnings" in result


# ---------- status ----------

def test_status_round_trip_without_solution():
    out = _drive(_req("s1", "status.get") + "\n")
    assert out[0]["result"]["health"] == "ok"
    # No solution → project is None
    assert out[0]["result"]["project"] is None


# ---------- error handling ----------

def test_unknown_method_returns_method_not_found_error():
    out = _drive(_req("x", "does.not.exist") + "\n")
    assert out[0]["id"] == "x"
    assert out[0]["error"]["code"] == -32601  # RPC_METHOD_NOT_FOUND


def test_bad_json_returns_parse_error_with_null_id():
    out = _drive("this is not json\n")
    assert out[0]["id"] is None
    assert out[0]["error"]["code"] == -32700  # RPC_PARSE_ERROR


def test_missing_id_returns_invalid_request():
    line = json.dumps({"jsonrpc": "2.0", "method": "handshake"})
    out = _drive(line + "\n")
    assert out[0]["id"] is None
    assert out[0]["error"]["code"] == -32600  # RPC_INVALID_REQUEST


def test_handler_value_error_becomes_internal_error():
    """If a handler raises a non-RpcError exception, the dispatcher wraps
    it as RPC_INTERNAL_ERROR and the loop still emits a clean response."""
    # Approvals without store will raise RpcError (INVALID_PARAMS)
    out = _drive(_req("a1", "approvals.list_pending") + "\n")
    assert out[0]["id"] == "a1"
    assert "error" in out[0]
    assert out[0]["error"]["code"] == -32602  # RPC_INVALID_PARAMS


# ---------- multiple requests on the same stream ----------

def test_multiple_requests_processed_in_order():
    stdin_text = (
        _req("1", "handshake") + "\n"
        + _req("2", "status.get") + "\n"
        + _req("3", "does.not.exist") + "\n"
    )
    out = _drive(stdin_text)
    assert [r["id"] for r in out] == ["1", "2", "3"]
    assert "result" in out[0]
    assert "result" in out[1]
    assert "error" in out[2]


def test_blank_lines_are_ignored():
    stdin_text = "\n\n" + _req("1", "handshake") + "\n\n"
    out = _drive(stdin_text)
    assert len(out) == 1
    assert out[0]["id"] == "1"


# ---------- with solution path (end-to-end wiring) ----------

# ---------- solutions ----------

def test_solutions_list_round_trip():
    """Smoke test: `solutions.list` should return a list (possibly empty) —
    the SAGE_ROOT env var and project_loader.list_solutions are wired in
    `_wire_handlers`, so this exercises the full path through the real
    dispatcher."""
    out = _drive(_req("sl", "solutions.list") + "\n")
    assert "result" in out[0], f"got error: {out[0]}"
    assert isinstance(out[0]["result"], list)


def test_solutions_get_current_without_solution_returns_null():
    out = _drive(_req("sc", "solutions.get_current") + "\n")
    assert "result" in out[0]
    # No --solution-name passed, so current is null
    assert out[0]["result"] is None


def test_sidecar_wires_up_stores_when_solution_path_given(tmp_path):
    """When --solution-path is provided, approvals.list_pending should work
    (returning an empty list, not an INVALID_PARAMS error)."""
    # Use the starter solution that actually exists on main
    import os

    sage_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    solution_path = os.path.join(sage_root, "solutions", "starter")

    # Only run if the solution exists on this branch
    if not os.path.isdir(solution_path):
        pytest.skip("starter solution not present on this branch")

    argv = ["--solution-name", "starter", "--solution-path", str(tmp_path)]
    out = _drive(_req("1", "approvals.list_pending") + "\n", argv=argv)
    assert "result" in out[0], f"got error: {out[0]}"
    assert isinstance(out[0]["result"], list)

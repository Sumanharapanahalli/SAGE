"""Tests for the Live Console (logs.tail) handler."""

from __future__ import annotations

import io
import logging
import sys

import pytest

from handlers import logs
from rpc import RPC_INVALID_PARAMS, RpcError


@pytest.fixture(autouse=True)
def clean_handler():
    logs.uninstall()
    root = logging.getLogger()
    prev_level = root.level
    root.setLevel(logging.INFO)
    yield
    root.setLevel(prev_level)
    logs.uninstall()


def _log(msg: str, level: int = logging.INFO, name: str = "src.test") -> None:
    logging.getLogger(name).log(level, msg)


def test_tail_is_empty_before_anything_is_logged():
    logs.install()
    out = logs.tail({})
    assert out["entries"] == []
    assert out["last_seq"] == 0
    assert out["installed"] is True


def test_tail_returns_records_logged_after_install():
    logs.install()
    _log("hello console")
    out = logs.tail({})
    assert len(out["entries"]) == 1
    e = out["entries"][0]
    assert e["message"] == "hello console"
    assert e["level"] == "INFO"
    assert e["name"] == "src.test"
    assert e["seq"] == 1
    assert e["ts"].startswith("20")
    assert out["last_seq"] == 1


def test_after_seq_cursor_returns_only_new_records():
    logs.install()
    _log("one")
    first = logs.tail({})
    assert first["last_seq"] == 1

    _log("two")
    _log("three")
    second = logs.tail({"after_seq": first["last_seq"]})
    assert [e["message"] for e in second["entries"]] == ["two", "three"]
    assert second["last_seq"] == 3

    # Idle poll: nothing new, cursor echoed back unchanged.
    third = logs.tail({"after_seq": second["last_seq"]})
    assert third["entries"] == []
    assert third["last_seq"] == 3


def test_limit_returns_the_most_recent_records():
    logs.install()
    for i in range(10):
        _log(f"msg-{i}")
    out = logs.tail({"limit": 3})
    assert [e["message"] for e in out["entries"]] == ["msg-7", "msg-8", "msg-9"]
    assert out["last_seq"] == 10


def test_buffer_is_bounded_and_drops_oldest():
    logs.install()
    for i in range(logs._MAXLEN + 25):
        _log(f"m{i}")
    out = logs.tail({"limit": logs._LIMIT_MAX})
    assert out["buffered"] == logs._MAXLEN
    assert len(out["entries"]) == logs._MAXLEN
    # Oldest 25 dropped; seq keeps counting so the cursor stays monotonic.
    assert out["entries"][0]["message"] == "m25"
    assert out["last_seq"] == logs._MAXLEN + 25


def test_exception_traceback_reaches_the_buffer():
    logs.install()
    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("src.agents.analyst").exception("analysis failed")
    out = logs.tail({})
    msg = out["entries"][-1]["message"]
    assert "analysis failed" in msg
    assert "ValueError: boom" in msg
    assert "Traceback" in msg
    assert out["entries"][-1]["level"] == "ERROR"


def test_levels_are_captured():
    logs.install()
    _log("w", level=logging.WARNING)
    _log("e", level=logging.ERROR)
    out = logs.tail({})
    assert [e["level"] for e in out["entries"]] == ["WARNING", "ERROR"]


def test_handler_never_writes_to_stdout():
    """stdout is the NDJSON RPC channel — a single stray byte corrupts it."""
    logs.install()
    captured = io.StringIO()
    real_stdout, sys.stdout = sys.stdout, captured
    try:
        _log("should not appear on stdout")
        logging.getLogger("src.test").error("nor should this")
        logs.tail({})
    finally:
        sys.stdout = real_stdout
    assert captured.getvalue() == ""


def test_install_is_idempotent():
    h1 = logs.install()
    h2 = logs.install()
    assert h1 is h2
    _log("once")
    out = logs.tail({})
    # Two attached handlers would buffer the record twice.
    assert len(out["entries"]) == 1


def test_uninstall_detaches_and_resets():
    logs.install()
    _log("before")
    logs.uninstall()
    _log("after")
    out = logs.tail({})
    assert out["entries"] == []
    assert out["installed"] is False


def test_tail_rejects_bad_params():
    logs.install()
    with pytest.raises(RpcError) as e1:
        logs.tail({"limit": 0})
    assert e1.value.code == RPC_INVALID_PARAMS

    with pytest.raises(RpcError):
        logs.tail({"limit": logs._LIMIT_MAX + 1})
    with pytest.raises(RpcError):
        logs.tail({"after_seq": -1})
    with pytest.raises(RpcError):
        logs.tail({"after_seq": "5"})
    with pytest.raises(RpcError):
        logs.tail([])


def test_tail_tolerates_none_params():
    logs.install()
    _log("x")
    out = logs.tail(None)
    assert len(out["entries"]) == 1


def test_logs_tail_is_registered():
    """An unregistered handler is dead code — the UI would get -32601."""
    import app

    d = app._build_dispatcher()
    assert "logs.tail" in d._handlers


def test_configure_logging_installs_the_buffer_handler():
    """Nothing else writes to the ring buffer — if app never installs the
    handler, /console renders an empty console forever."""
    import app

    logs.uninstall()
    assert logs.tail({})["installed"] is False
    app._configure_logging()
    assert logs.tail({})["installed"] is True


def test_logs_tail_round_trips_through_the_real_ndjson_dispatcher():
    """End-to-end over the actual event loop: a framework log record emitted
    into the root logger comes back out of the `logs.tail` RPC on stdout."""
    import json

    import app

    app._configure_logging()  # installs the DequeLogHandler (idempotent)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("src.agents.analyst").warning("gateway timeout")

    # limit=500: _wire_handlers itself logs, and the default limit (200) would
    # eventually push the seeded record out of the returned window.
    stdin = io.StringIO(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "logs.tail",
                "params": {"limit": 500},
            }
        )
        + "\n"
    )
    stdout = io.StringIO()
    assert app.run(stdin=stdin, stdout=stdout, argv=[]) == 0

    frame = json.loads(stdout.getvalue().strip())
    assert str(frame["id"]) == "7"  # rpc.py normalizes request ids to str
    assert "error" not in frame
    messages = [e["message"] for e in frame["result"]["entries"]]
    assert "gateway timeout" in messages
    assert frame["result"]["installed"] is True
    assert frame["result"]["last_seq"] >= 1

"""
SAGE[ai] - Unit tests for src/core/log_config.py

Structured logging configuration: JSON formatter toggled by SAGE_JSON_LOGS.
"""

import json
import logging

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# json_logs_enabled()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "true", "True", "yes", "on", "ON"])
def test_json_logs_enabled_true_for_truthy_values(monkeypatch, value):
    from src.core.log_config import json_logs_enabled

    monkeypatch.setenv("SAGE_JSON_LOGS", value)
    assert json_logs_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
def test_json_logs_enabled_false_for_falsy_values(monkeypatch, value):
    from src.core.log_config import json_logs_enabled

    monkeypatch.setenv("SAGE_JSON_LOGS", value)
    assert json_logs_enabled() is False


def test_json_logs_enabled_false_when_unset(monkeypatch):
    from src.core.log_config import json_logs_enabled

    monkeypatch.delenv("SAGE_JSON_LOGS", raising=False)
    assert json_logs_enabled() is False


# ---------------------------------------------------------------------------
# JsonFormatter
# ---------------------------------------------------------------------------


def _make_record(msg="hello", **extra):
    record = logging.LogRecord(
        name="TestLogger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for k, v in extra.items():
        setattr(record, k, v)
    return record


def test_json_formatter_outputs_valid_json_with_standard_fields():
    from src.core.log_config import JsonFormatter

    formatter = JsonFormatter()
    record = _make_record("test message")
    output = formatter.format(record)
    payload = json.loads(output)
    assert payload["message"] == "test message"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "TestLogger"
    assert "timestamp" in payload


def test_json_formatter_promotes_structured_fields():
    from src.core.log_config import JsonFormatter

    formatter = JsonFormatter()
    record = _make_record(
        "generation done",
        event="generation",
        provider="claude-code",
        duration_ms=123,
        task_id="t-1",
        status="completed",
    )
    payload = json.loads(formatter.format(record))
    assert payload["event"] == "generation"
    assert payload["provider"] == "claude-code"
    assert payload["duration_ms"] == 123
    assert payload["task_id"] == "t-1"
    assert payload["status"] == "completed"


def test_json_formatter_omits_absent_structured_fields():
    from src.core.log_config import JsonFormatter

    formatter = JsonFormatter()
    record = _make_record("no extras")
    payload = json.loads(formatter.format(record))
    for field in ("event", "provider", "duration_ms", "task_id", "status"):
        assert field not in payload


# ---------------------------------------------------------------------------
# build_formatter()
# ---------------------------------------------------------------------------


def test_build_formatter_returns_json_formatter_when_enabled(monkeypatch):
    from src.core.log_config import build_formatter, JsonFormatter

    monkeypatch.setenv("SAGE_JSON_LOGS", "1")
    assert isinstance(build_formatter(), JsonFormatter)


def test_build_formatter_returns_plain_formatter_when_disabled(monkeypatch):
    from src.core.log_config import build_formatter, JsonFormatter

    monkeypatch.delenv("SAGE_JSON_LOGS", raising=False)
    formatter = build_formatter()
    assert not isinstance(formatter, JsonFormatter)
    assert isinstance(formatter, logging.Formatter)


# ---------------------------------------------------------------------------
# configure_logging() — must be pytest-safe (opt-in, never called at import time)
# ---------------------------------------------------------------------------


def test_configure_logging_installs_exactly_one_sage_handler():
    from src.core.log_config import configure_logging, _SAGE_HANDLER_FLAG

    root = logging.getLogger()
    before = len(root.handlers)
    try:
        configure_logging()
        configure_logging()  # calling twice must not duplicate SAGE handlers
        sage_handlers = [
            h for h in root.handlers if getattr(h, _SAGE_HANDLER_FLAG, False)
        ]
        assert len(sage_handlers) == 1
    finally:
        # Clean up so we don't leak a handler into the rest of the test session.
        for h in root.handlers[:]:
            if getattr(h, "_sage_log_handler", False):
                root.removeHandler(h)
        assert len(root.handlers) == before


def test_configure_logging_preserves_non_sage_handlers():
    """A pre-existing (e.g. pytest caplog) handler must not be removed."""
    from src.core.log_config import configure_logging

    root = logging.getLogger()
    sentinel = logging.NullHandler()
    root.addHandler(sentinel)
    try:
        configure_logging()
        assert sentinel in root.handlers
    finally:
        root.removeHandler(sentinel)
        for h in root.handlers[:]:
            if getattr(h, "_sage_log_handler", False):
                root.removeHandler(h)


def test_log_config_module_does_not_configure_on_import():
    """Importing the module must be side-effect free — no auto handler install."""
    import importlib
    import src.core.log_config as lc

    importlib.reload(lc)
    root = logging.getLogger()
    sage_handlers = [
        h for h in root.handlers if getattr(h, lc._SAGE_HANDLER_FLAG, False)
    ]
    assert sage_handlers == [], (
        "log_config must not install a handler merely by being imported"
    )

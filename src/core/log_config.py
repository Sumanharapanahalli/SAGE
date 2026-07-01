"""
SAGE[ai] - Logging Configuration
================================
Central logging setup with an optional structured-JSON formatter.

A plain, human-readable formatter is the default. Set the environment
variable ``SAGE_JSON_LOGS=1`` (also accepts ``true``/``yes``/``on``) to emit
one JSON object per log record. Structured fields attached to a record via
``logger.info(msg, extra={...})`` are promoted to top-level JSON keys.

Canonical structured fields (any subset may be present on a record):
    event, provider, duration_ms, task_id, status

Usage:
    from src.core.log_config import configure_logging
    configure_logging()            # call once, early in process startup

Importing this module has NO side effects — it never installs a handler on
its own. Tests (and pytest's own log-capture handler) are therefore never
disrupted merely by importing it.
"""

from __future__ import annotations

import json
import logging
import os

# Canonical structured fields promoted to top-level keys in JSON output.
STRUCTURED_FIELDS = ("event", "provider", "duration_ms", "task_id", "status")

# LogRecord attributes that are always present on a record — used to detect the
# *extra=* fields a caller attached. Computed from a blank record so it stays
# correct across Python versions (e.g. the 3.12+ "taskName" attribute).
_RESERVED = set(logging.makeLogRecord({}).__dict__.keys()) | {"message", "asctime"}

# Accepted truthy spellings for the toggle env var.
_TRUTHY = ("1", "true", "yes", "on")

# Marker attribute so configure_logging() only ever removes handlers it itself
# installed — leaving pytest's log-capture handlers (and any others) untouched.
_SAGE_HANDLER_FLAG = "_sage_log_handler"


def json_logs_enabled() -> bool:
    """True when SAGE_JSON_LOGS is set to a truthy value (1/true/yes/on)."""
    return os.environ.get("SAGE_JSON_LOGS", "").strip().lower() in _TRUTHY


class JsonFormatter(logging.Formatter):
    """Render each LogRecord as a single-line JSON object.

    Standard fields (timestamp, level, logger, message) are always emitted.
    Canonical STRUCTURED_FIELDS are emitted when present on the record, and
    any other ``extra=`` keys are appended too. Exception / stack info is
    serialised into the JSON object rather than printed as a trailing blob.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Promote canonical structured fields when present.
        for field in STRUCTURED_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        # Include any other extra= attributes not already accounted for.
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in payload:
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def build_formatter() -> logging.Formatter:
    """Return the JSON formatter when SAGE_JSON_LOGS is enabled, else a plain one."""
    if json_logs_enabled():
        return JsonFormatter()
    return logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def configure_logging(level: int = logging.INFO, *, force: bool = True) -> None:
    """Install a single SAGE stream handler on the root logger.

    Honours ``SAGE_JSON_LOGS=1`` to switch the output format to structured JSON.
    Opt-in only — never called automatically by importing this or any other
    SAGE module. Call it once, early in process startup (e.g. app entrypoint).

    pytest-safe: with ``force=True`` only previously-installed SAGE handlers are
    removed before re-installing, so pytest's log-capture handlers (and any
    other third-party handlers) are preserved.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(build_formatter())
    setattr(handler, _SAGE_HANDLER_FLAG, True)

    root = logging.getLogger()
    if force:
        for existing in root.handlers[:]:
            if getattr(existing, _SAGE_HANDLER_FLAG, False):
                root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

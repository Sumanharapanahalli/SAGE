"""Structured logging setup using structlog.

Every log event automatically includes:
- timestamp (ISO-8601 UTC)
- level
- logger name
- job_id   (pulled from contextvars, empty string if not set)
- stage    (pulled from contextvars, empty string if not set)
- duration_ms (populated explicitly when timing a block)

Usage::

    from config.logging_config import get_logger, bind_job_context
    import structlog

    log = get_logger(__name__)

    # Bind job context for the duration of a request/task:
    bind_job_context(job_id="job-123", stage="ocr")
    log.info("ocr.started", pages=10)

    # Time a block:
    with TimedBlock(log, "ocr.completed") as t:
        ... # your work
    # Emits: {"event": "ocr.completed", "duration_ms": 123.4, ...}
"""
from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator

import structlog

# ContextVars shared across coroutines / threads within the same task.
_job_id_var: ContextVar[str] = ContextVar("job_id", default="")
_stage_var: ContextVar[str] = ContextVar("stage", default="")


def bind_job_context(*, job_id: str = "", stage: str = "") -> None:
    """Set job_id and stage for the current async/thread context."""
    _job_id_var.set(job_id)
    _stage_var.set(stage)


def _inject_context_vars(
    logger: Any, method: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Processor: inject job_id and stage from ContextVars."""
    event_dict.setdefault("job_id", _job_id_var.get())
    event_dict.setdefault("stage", _stage_var.get())
    return event_dict


def _ensure_duration_ms(
    logger: Any, method: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Processor: ensure duration_ms is always present (0 if not explicitly set)."""
    event_dict.setdefault("duration_ms", 0)
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog and stdlib logging for JSON output.

    Call once at application startup *after* settings are loaded.

    Args:
        log_level: One of DEBUG | INFO | WARNING | ERROR | CRITICAL.
    """
    # Shared processors applied to every log event.
    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _inject_context_vars,
        _ensure_duration_ms,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Remove any handlers added by libraries before ours.
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Quieten noisy third-party loggers.
    for noisy in ("boto3", "botocore", "urllib3", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to *name*."""
    return structlog.get_logger(name)  # type: ignore[return-value]


class TimedBlock:
    """Context manager that logs *event* with duration_ms on exit.

    Example::

        with TimedBlock(log, "table.detection", doc_id="abc") as t:
            result = detect_tables(image)
        # Emits: {"event": "table.detection", "duration_ms": 47.3, "doc_id": "abc"}
    """

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger,
        event: str,
        level: str = "info",
        **extra: Any,
    ) -> None:
        self._log = logger
        self._event = event
        self._level = level
        self._extra = extra
        self._start: float = 0.0

    def __enter__(self) -> "TimedBlock":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        duration_ms = round((time.perf_counter() - self._start) * 1000, 2)
        log_fn = getattr(self._log, self._level, self._log.info)
        log_fn(
            self._event,
            duration_ms=duration_ms,
            success=(exc_type is None),
            **self._extra,
        )


@contextmanager
def timed_stage(
    logger: structlog.stdlib.BoundLogger,
    stage: str,
    job_id: str = "",
    **extra: Any,
) -> Generator[None, None, None]:
    """Async/sync context manager: binds stage + job_id and times execution."""
    bind_job_context(job_id=job_id, stage=stage)
    with TimedBlock(logger, f"{stage}.done", **extra):
        yield
    # Reset stage after block completes.
    bind_job_context(job_id=job_id, stage="")

"""Live Console handler — a bounded, seq-numbered ring buffer of the sidecar's
own ``logging`` output, polled over NDJSON.

The web UI streams the same data over SSE (``api.py:_SSELogHandler`` +
``GET /logs/stream``). The sidecar protocol is strictly one-request /
one-response, so streaming is not available; polling ``logs.tail`` with a
cursor reproduces every control on the page (buffer, filter, pause, clear,
autoscroll) with zero protocol change.

Why this matters: the desktop operator has no terminal. Every framework
traceback (``logging.exception`` in ``app.run``'s catch-all, agent errors,
LLM gateway failures) currently goes to the sidecar's *stderr* — i.e. the
dev terminal — and the UI shows only a bare RPC error. This buffer is the
operator's only view of *why* something failed.

HARD CONSTRAINT: this handler must never write to **stdout**. stdout is the
NDJSON RPC channel and any stray byte corrupts the protocol. ``DequeLogHandler``
therefore has no stream at all (it only appends to an in-memory deque) and
``handleError`` is a no-op — the base class's default would write to
``sys.stderr``, which is safe, but a silent no-op keeps the guarantee local
and obvious. The stderr ``StreamHandler`` installed by ``app._configure_logging``
is untouched: this handler is *additive*.
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

from rpc import RPC_INVALID_PARAMS, RpcError

# Matches web's MAX_LINES — the deque drops oldest on overflow, so an idle
# operator who opens /console late sees the last 500 records, not nothing.
_MAXLEN = 500
_LIMIT_MAX = 500
_LIMIT_DEFAULT = 200

_buffer: deque = deque(maxlen=_MAXLEN)
_lock = threading.Lock()
_seq = 0
_handler: Optional["DequeLogHandler"] = None


class DequeLogHandler(logging.Handler):
    """Appends formatted records to the module-level ring buffer.

    Emits nothing to any stream. Records carry a monotonic ``seq`` so the
    UI can poll with an ``after_seq`` cursor and never miss or duplicate a
    line (short of the buffer wrapping, which drop-oldest makes explicit).
    """

    def emit(self, record: logging.LogRecord) -> None:
        global _seq
        try:
            # Formatter.format() appends exc_info/stack_info to the message,
            # so a `logging.exception(...)` traceback reaches the UI intact.
            # This is the whole point of the page.
            message = self.format(record)
        except Exception:  # noqa: BLE001 — a logging handler must never raise
            return
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        with _lock:
            _seq += 1
            _buffer.append(
                {
                    "seq": _seq,
                    "ts": ts,
                    "level": record.levelname,
                    "name": record.name,
                    "message": message,
                }
            )

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: D102
        return


def install(level: int = logging.DEBUG) -> "DequeLogHandler":
    """Attach the buffer handler to the ROOT logger. Idempotent.

    Called from ``app._wire_handlers`` so the buffer captures wiring-time
    warnings (``"VectorMemory unavailable: ..."`` etc.) — the operator's first
    and best signal that an optional dependency is missing.

    The handler level is DEBUG; the *root* logger's level (INFO, set by
    ``app._configure_logging``) is what actually gates records, so this
    handler sees exactly what the stderr handler sees.
    """
    global _handler
    if _handler is not None:
        return _handler
    h = DequeLogHandler()
    # Only "%(message)s": `name` is returned as its own field, so web's
    # "%(name)s — %(message)s" formatter duplicated it into every rendered line.
    h.setFormatter(logging.Formatter("%(message)s"))
    h.setLevel(level)
    logging.getLogger().addHandler(h)
    _handler = h
    return h


def uninstall() -> None:
    """Detach the handler and reset the buffer. Used by tests; safe if not installed."""
    global _handler, _seq
    if _handler is not None:
        logging.getLogger().removeHandler(_handler)
        _handler = None
    with _lock:
        _buffer.clear()
        _seq = 0


def _coerce_int(value: Any, name: str, default: int, lo: int, hi: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise RpcError(RPC_INVALID_PARAMS, f"'{name}' must be an integer")
    if value < lo or value > hi:
        raise RpcError(RPC_INVALID_PARAMS, f"'{name}' must be between {lo} and {hi}")
    return value


def tail(params: Any) -> dict:
    """Return buffered records newer than ``after_seq`` (most recent ``limit``).

    ``last_seq`` is the cursor the caller should send back next poll. When
    nothing new arrived it echoes ``after_seq``, so an idle poll is a no-op.
    """
    p = params if params is not None else {}
    if not isinstance(p, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")

    after_seq = _coerce_int(p.get("after_seq"), "after_seq", 0, 0, 2**63 - 1)
    limit = _coerce_int(p.get("limit"), "limit", _LIMIT_DEFAULT, 1, _LIMIT_MAX)

    with _lock:
        fresh = [e for e in _buffer if e["seq"] > after_seq]
        buffered = len(_buffer)
        installed = _handler is not None

    entries = fresh[-limit:]
    last_seq = entries[-1]["seq"] if entries else after_seq
    return {
        "entries": entries,
        "last_seq": last_seq,
        "buffered": buffered,
        "capacity": _MAXLEN,
        "installed": installed,
    }

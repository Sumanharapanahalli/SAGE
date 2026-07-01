"""
SAGE[ai] - Per-Request Correlation Context
===========================================

Holds the current request's UUID4 ``request_id`` in a context variable so it
can be read anywhere in the call chain (LLM gateway, audit logger, agents)
without threading it through every function signature.

The value is populated by ``RequestIDMiddleware`` in the FastAPI app. Outside
of an HTTP request (CLI, background tasks, tests) ``get_request_id()`` returns
an empty string, and callers may pass an explicit id instead.

Inbound ``X-Request-ID`` headers are reused ONLY when they are well-formed
UUID4 values; anything else is replaced with a freshly generated id so that we
never reflect arbitrary client-controlled strings into our response headers.
"""

from __future__ import annotations

import contextvars
import uuid

# Default "" — code paths with no active request (CLI, schedulers) read empty.
_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "sage_request_id", default=""
)


def new_request_id() -> str:
    """Generate a fresh UUID4 request id."""
    return str(uuid.uuid4())


def is_valid_request_id(value: str) -> bool:
    """Return True only for well-formed UUID4 strings."""
    if not value:
        return False
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return parsed.version == 4


def normalize_request_id(request_id: str = "") -> str:
    """
    Resolve an inbound/explicit request id to a safe canonical UUID4 string.

    Reuse the supplied value only when it is a valid UUID4 (normalized to the
    canonical lowercase form, which prevents header-reflection of arbitrary
    client input); otherwise generate a fresh UUID4.
    """
    candidate = (request_id or "").strip()
    if is_valid_request_id(candidate):
        return str(uuid.UUID(candidate))  # canonical lowercase representation
    return new_request_id()


def set_request_id(request_id: str = "") -> tuple[str, contextvars.Token]:
    """
    Resolve and set the current request id, generating/validating as needed.

    Returns a ``(resolved_id, token)`` tuple. The token must be handed back to
    ``reset_request_id()`` (typically in a ``finally`` block) so the previous
    context value is restored and no id leaks across reused worker contexts.
    """
    rid = normalize_request_id(request_id)
    token = _request_id_var.set(rid)
    return rid, token


def get_request_id() -> str:
    """Return the current request id, or '' when there is no active request."""
    return _request_id_var.get()


def reset_request_id(token: contextvars.Token | None = None) -> None:
    """
    Restore the previous context value using the token from ``set_request_id``.
    With no token, clears the id to '' (mainly for tests / worker reuse).
    """
    if token is not None:
        try:
            _request_id_var.reset(token)
            return
        except (ValueError, LookupError):
            pass  # token from a different context — fall through to clear
    _request_id_var.set("")

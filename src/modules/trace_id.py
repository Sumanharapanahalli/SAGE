"""
Nano-module: Trace ID
======================
UUID-based trace ID generation and validation.
Used for ISO 13485 / audit trail traceability.
Zero dependencies — pure Python.
"""
import re
import uuid

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)

def new() -> str:
    """Generate a new UUID4 trace ID."""
    return str(uuid.uuid4())

def is_valid(value: str) -> bool:
    """Return True if value is a well-formed UUID4 trace ID."""
    return bool(value and _UUID_RE.match(value))

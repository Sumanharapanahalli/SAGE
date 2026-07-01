"""
Nano-module: Task Payload Validator
=====================================
Validates task payloads against required field definitions.
Zero dependencies — pure Python.
"""
import re
from typing import Any

class ValidationError(ValueError):
    pass

# Maximum allowed length for a sanitized task description.
MAX_TASK_LENGTH = 4000

# Control characters in the range \x00-\x1f, excluding tab (\x09) and
# newline (\x0a). Null bytes (\x00) are covered by this range.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f]")


def sanitize_task_input(task: Any, max_length: int = MAX_TASK_LENGTH) -> str:
    """
    Sanitize a free-text task description. Pure function — no side effects,
    no framework coupling, deterministic for a given input.

    Null bytes and control characters are SILENTLY STRIPPED, not rejected —
    legitimate requests carrying stray control bytes (e.g. copy-paste
    artifacts) still succeed. The ONLY condition that raises (and therefore
    drives the caller's HTTP 422) is exceeding ``max_length``.

    Rules:
      - Coerce the value to ``str`` (``None`` becomes ``""``).
      - Strip null bytes and control characters (\\x00-\\x1f), keeping only
        tab (\\t, \\x09) and newline (\\n, \\x0a).
      - Enforce a maximum length of ``max_length`` characters (raises).

    Args:
        task: The raw task description (typically a string).
        max_length: Maximum allowed length after sanitization (default 4000).

    Returns:
        The sanitized task string.

    Raises:
        ValidationError: Only if the sanitized value exceeds ``max_length``
            characters.
    """
    text = "" if task is None else (task if isinstance(task, str) else str(task))
    cleaned = _CONTROL_CHARS.sub("", text)
    if len(cleaned) > max_length:
        raise ValidationError(
            f"task exceeds the maximum length of {max_length} characters "
            f"(got {len(cleaned)})."
        )
    return cleaned


def validate(payload: dict, required_fields: list[str]) -> None:
    """
    Raise ValidationError if any required_field is missing or empty.

    Args:
        payload: The task payload dict.
        required_fields: List of field names that must be present and non-empty.

    Raises:
        ValidationError: With a descriptive message listing missing fields.
    """
    missing = [f for f in required_fields if not payload.get(f)]
    if missing:
        raise ValidationError(f"Missing required payload fields: {', '.join(missing)}")

def coerce_str(payload: dict, key: str, default: str = "") -> str:
    """Return payload[key] as a string, or default if missing."""
    val = payload.get(key, default)
    return str(val) if val is not None else default

def coerce_int(payload: dict, key: str, default: int = 0) -> int:
    """Return payload[key] as int, or default if missing/non-numeric."""
    try:
        return int(payload.get(key, default))
    except (TypeError, ValueError):
        return default

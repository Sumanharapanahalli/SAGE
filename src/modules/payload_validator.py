"""
Nano-module: Task Payload Validator
=====================================
Validates task payloads against required field definitions.
Zero dependencies — pure Python.
"""
from typing import Any

class ValidationError(ValueError):
    pass

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

"""Data transformation engine — pure logic, no I/O."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any


class TransformationError(ValueError):
    """Raised when a transformation step fails."""


# ---------------------------------------------------------------------------
# Built-in transform operations
# ---------------------------------------------------------------------------

def _op_rename_keys(data: dict, params: dict) -> dict:
    """Rename top-level keys according to a mapping."""
    mapping: dict = params.get("mapping", {})
    if not isinstance(mapping, dict):
        raise TransformationError("rename_keys: 'mapping' must be an object")
    return {mapping.get(k, k): v for k, v in data.items()}


def _op_filter_keys(data: dict, params: dict) -> dict:
    """Keep only the specified keys."""
    keys: list = params.get("keys", [])
    if not isinstance(keys, list):
        raise TransformationError("filter_keys: 'keys' must be an array")
    return {k: v for k, v in data.items() if k in keys}


def _op_cast_types(data: dict, params: dict) -> dict:
    """Cast field values to target types (str, int, float, bool)."""
    casts: dict = params.get("casts", {})
    if not isinstance(casts, dict):
        raise TransformationError("cast_types: 'casts' must be an object")
    type_map = {"str": str, "int": int, "float": float, "bool": bool}
    result = dict(data)
    for field, target_type in casts.items():
        if field not in result:
            continue
        if target_type not in type_map:
            raise TransformationError(
                f"cast_types: unsupported type '{target_type}' for field '{field}'"
            )
        try:
            result[field] = type_map[target_type](result[field])
        except (ValueError, TypeError) as exc:
            raise TransformationError(
                f"cast_types: cannot cast '{field}' to {target_type}: {exc}"
            ) from exc
    return result


def _op_add_metadata(data: dict, params: dict) -> dict:
    """Inject computed metadata fields into the payload."""
    result = dict(data)
    if params.get("add_timestamp", False):
        result["_transformed_at"] = datetime.now(timezone.utc).isoformat()
    if params.get("add_checksum", False):
        payload_bytes = json.dumps(data, sort_keys=True, default=str).encode()
        result["_checksum"] = hashlib.sha256(payload_bytes).hexdigest()
    return result


def _op_flatten(data: dict, params: dict) -> dict:
    """Flatten one level of nested dicts using a separator."""
    sep: str = params.get("separator", "_")
    if not isinstance(sep, str) or not sep:
        raise TransformationError("flatten: 'separator' must be a non-empty string")
    result: dict = {}
    for key, value in data.items():
        if isinstance(value, dict):
            for sub_key, sub_val in value.items():
                result[f"{key}{sep}{sub_key}"] = sub_val
        else:
            result[key] = value
    return result


def _op_regex_replace(data: dict, params: dict) -> dict:
    """Apply regex substitution on string fields."""
    field: str = params.get("field", "")
    pattern: str = params.get("pattern", "")
    replacement: str = params.get("replacement", "")
    if not field:
        raise TransformationError("regex_replace: 'field' is required")
    if not pattern:
        raise TransformationError("regex_replace: 'pattern' is required")
    result = dict(data)
    if field in result and isinstance(result[field], str):
        try:
            result[field] = re.sub(pattern, replacement, result[field])
        except re.error as exc:
            raise TransformationError(f"regex_replace: invalid pattern: {exc}") from exc
    return result


_OPERATIONS: dict[str, Any] = {
    "rename_keys": _op_rename_keys,
    "filter_keys": _op_filter_keys,
    "cast_types": _op_cast_types,
    "add_metadata": _op_add_metadata,
    "flatten": _op_flatten,
    "regex_replace": _op_regex_replace,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def available_operations() -> list[str]:
    return sorted(_OPERATIONS.keys())


def apply_pipeline(
    data: dict,
    pipeline: list[dict],
) -> dict:
    """Execute a list of transform steps sequentially.

    Each step is ``{"operation": "<name>", "params": {...}}``.
    Returns the transformed dict or raises ``TransformationError``.
    """
    result = dict(data)
    for idx, step in enumerate(pipeline):
        op_name = step.get("operation", "")
        if not op_name:
            raise TransformationError(f"Step {idx}: 'operation' is required")
        if op_name not in _OPERATIONS:
            raise TransformationError(
                f"Step {idx}: unknown operation '{op_name}'. "
                f"Available: {available_operations()}"
            )
        params = step.get("params", {})
        if not isinstance(params, dict):
            raise TransformationError(f"Step {idx}: 'params' must be an object")
        result = _OPERATIONS[op_name](result, params)
    return result

"""
SAGE Framework — Structured Output Validator
==============================================
Validates agent outputs against schemas with auto-retry on parse failure.

Inspired by open-multi-agent's Zod validation pattern, adapted to Python
with Pydantic-style validation (without requiring Pydantic dependency in
the runner hot path).

Schemas are defined per output type. When an agent produces malformed output,
the validator provides clear error messages that can be fed back to the LLM
for a retry attempt.
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("OutputValidator")


# ---------------------------------------------------------------------------
# Output Schemas (lightweight — dict-based, no Pydantic dependency)
# ---------------------------------------------------------------------------

OUTPUT_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "code_generation": {
        "required_fields": ["files", "explanation"],
        "field_types": {
            "files": list,
            "explanation": str,
        },
        "nested_rules": {
            "files": {
                "item_required_fields": ["path", "content"],
                "item_field_types": {"path": str, "content": str},
            },
        },
    },
    "eda_design": {
        "required_fields": ["files"],
        "field_types": {
            "files": list,
            "components": (int, float),
            "layers": (int, float),
            "board_area_mm2": (int, float),
        },
        "nested_rules": {
            "files": {
                "item_required_fields": ["path", "content"],
                "item_field_types": {"path": str, "content": str},
            },
        },
    },
    "firmware": {
        "required_fields": ["files"],
        "field_types": {
            "files": list,
            "target_mcu": str,
            "binary_estimate_kb": (int, float),
            "ram_estimate_kb": (int, float),
        },
        "nested_rules": {
            "files": {
                "item_required_fields": ["path", "content"],
                "item_field_types": {"path": str, "content": str},
            },
        },
    },
}


def validate_agent_output(output: Any, output_type: str) -> Dict:
    """Validate an agent output against its schema.

    Args:
        output: The parsed output dict from the agent.
        output_type: Schema key (e.g., "code_generation", "eda_design").

    Returns:
        {"valid": True/False, "errors": [...], "output": <original or None>}
    """
    if not isinstance(output, dict):
        return {"valid": False, "errors": ["Output must be a JSON object"], "output": output}

    schema = OUTPUT_SCHEMAS.get(output_type)
    if not schema:
        # Unknown schema — pass through without validation
        return {"valid": True, "errors": [], "output": output}

    errors = []

    # Check required fields
    for field in schema.get("required_fields", []):
        if field not in output:
            errors.append(f"Missing required field: '{field}'")

    # Check field types (for fields that are present)
    for field, expected_type in schema.get("field_types", {}).items():
        if field in output:
            if not isinstance(output[field], expected_type):
                errors.append(
                    f"Field '{field}' must be {expected_type.__name__ if isinstance(expected_type, type) else str(expected_type)}, "
                    f"got {type(output[field]).__name__}"
                )

    # Check nested rules (e.g., items in a list)
    for field, rules in schema.get("nested_rules", {}).items():
        if field in output and isinstance(output[field], list):
            item_required = rules.get("item_required_fields", [])
            item_types = rules.get("item_field_types", {})
            for i, item in enumerate(output[field]):
                if not isinstance(item, dict):
                    errors.append(f"{field}[{i}] must be an object")
                    continue
                for req in item_required:
                    if req not in item:
                        errors.append(f"{field}[{i}] missing required field: '{req}'")
                for fld, ftype in item_types.items():
                    if fld in item and not isinstance(item[fld], ftype):
                        errors.append(f"{field}[{i}].{fld} must be {ftype.__name__}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "output": output,
    }


def parse_with_retry(
    generate_fn: Callable[[], str],
    output_type: str,
    max_retries: int = 2,
) -> Dict:
    """Parse LLM output as JSON and validate, retrying on failure.

    Args:
        generate_fn: Callable that returns a raw string from the LLM.
        output_type: Schema key for validation.
        max_retries: Maximum total attempts (default 2 = 1 initial + 1 retry).

    Returns:
        {"valid": True/False, "errors": [...], "output": <parsed dict or None>,
         "attempts": <number of attempts made>}
    """
    last_errors = []

    for attempt in range(max_retries):
        raw = generate_fn()

        # Try to extract JSON from response
        parsed = _extract_json(raw)
        if parsed is None:
            last_errors = [f"Attempt {attempt + 1}: Could not parse JSON from output"]
            logger.warning("Parse attempt %d failed: no valid JSON found", attempt + 1)
            continue

        # Validate against schema
        validation = validate_agent_output(parsed, output_type)
        if validation["valid"]:
            validation["attempts"] = attempt + 1
            return validation

        last_errors = validation["errors"]
        logger.warning(
            "Validation attempt %d failed: %s", attempt + 1, "; ".join(last_errors[:3])
        )

    return {
        "valid": False,
        "errors": last_errors,
        "output": None,
        "attempts": max_retries,
    }


def _extract_json(raw: str) -> Optional[Dict]:
    """Extract the first valid JSON object from a raw string."""
    # Try direct parse first
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try to find JSON within the string
    start = raw.find("{")
    if start < 0:
        return None

    # Try progressively shorter substrings from the last }
    for end in range(len(raw) - 1, start, -1):
        if raw[end] == "}":
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                continue

    return None

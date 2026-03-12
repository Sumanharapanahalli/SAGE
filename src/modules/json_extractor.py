"""
Nano-module: JSON Extractor
============================
Extracts clean JSON from LLM output that may contain markdown fences,
prose, or extra whitespace. Zero dependencies — pure Python.
"""
import json
import re
from typing import Any, Optional

def extract(text: str) -> Optional[Any]:
    """
    Extract and parse the first valid JSON object or array from text.
    Handles: ```json ... ```, raw JSON, JSON embedded in prose.
    Returns None if no valid JSON found.
    """
    if not text:
        return None
    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    # Try full string first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Try to find first {...} or [...]
    for pattern in (r'\{[\s\S]*\}', r'\[[\s\S]*\]'):
        match = re.search(pattern, cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    return None

def extract_or_default(text: str, default: Any) -> Any:
    """Like extract() but returns default instead of None on failure."""
    result = extract(text)
    return result if result is not None else default

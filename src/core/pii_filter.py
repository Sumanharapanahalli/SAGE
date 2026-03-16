"""
PII detection and redaction pipeline.

Uses presidio when available, falls back to regex-based detection when
presidio is not installed. Zero behaviour change when pii.enabled=false.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex fallback patterns (used when presidio is not installed)
# ---------------------------------------------------------------------------
_REGEX_PATTERNS: dict[str, re.Pattern] = {
    "EMAIL_ADDRESS": re.compile(
        r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
    ),
    "PHONE_NUMBER": re.compile(
        r'\b(?:\+?\d[\s\-.]?){7,15}\b'
    ),
    "US_SSN": re.compile(
        r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'
    ),
    "CREDIT_CARD": re.compile(
        r'\b(?:\d[ \-]?){13,19}\b'
    ),
}

# ---------------------------------------------------------------------------
# Try to import presidio — graceful degradation to regex if unavailable
# ---------------------------------------------------------------------------
_presidio_engine = None

try:
    from presidio_analyzer import AnalyzerEngine  # type: ignore
    _presidio_engine = AnalyzerEngine()
    logger.info("PII filter: presidio AnalyzerEngine loaded.")
except ImportError:
    logger.info(
        "presidio_analyzer not installed — PII filter will use regex fallback. "
        "Install with: pip install presidio-analyzer"
    )


def scrub_text(text: str, config: dict) -> tuple[str, list[str]]:
    """
    Detect and redact PII from text according to config.

    Returns:
        (scrubbed_text, list_of_detected_entity_types)

    When pii.enabled=false, returns (text, []) unchanged.
    """
    pii_cfg = config.get("pii", {})
    if not pii_cfg.get("enabled", False):
        return text, []

    mode = pii_cfg.get("mode", "redact")
    redaction_char = pii_cfg.get("redaction_char", "[REDACTED]")
    entity_types: list[str] = pii_cfg.get("entities", list(_REGEX_PATTERNS.keys()))

    detected_types: list[str] = []

    if _presidio_engine is not None:
        detected_types, scrubbed = _scrub_with_presidio(
            text, entity_types, redaction_char, mode
        )
    else:
        detected_types, scrubbed = _scrub_with_regex(
            text, entity_types, redaction_char, mode
        )

    return scrubbed, detected_types


def _scrub_with_presidio(
    text: str,
    entity_types: list[str],
    redaction_char: str,
    mode: str,
) -> tuple[list[str], str]:
    """Use presidio AnalyzerEngine for detection + span-based replacement."""
    try:
        results = _presidio_engine.analyze(
            text=text,
            entities=entity_types,
            language="en",
        )
    except Exception as exc:
        logger.warning("presidio analysis failed (falling back to regex): %s", exc)
        return _scrub_with_regex(text, entity_types, redaction_char, mode)

    if not results:
        return [], text

    detected = list({r.entity_type for r in results})

    if mode == "flag_only":
        return detected, text

    # Sort spans in reverse order so replacements don't shift offsets
    results_sorted = sorted(results, key=lambda r: r.start, reverse=True)
    scrubbed = text
    for result in results_sorted:
        replacement = redaction_char if mode == "redact" else f"[{result.entity_type}]"
        scrubbed = scrubbed[: result.start] + replacement + scrubbed[result.end :]

    return detected, scrubbed


def _scrub_with_regex(
    text: str,
    entity_types: list[str],
    redaction_char: str,
    mode: str,
) -> tuple[list[str], str]:
    """Regex-based fallback for entities covered by _REGEX_PATTERNS."""
    detected: list[str] = []
    scrubbed = text

    for entity_type in entity_types:
        pattern = _REGEX_PATTERNS.get(entity_type)
        if pattern is None:
            continue
        if pattern.search(scrubbed):
            detected.append(entity_type)
            if mode != "flag_only":
                replacement = redaction_char if mode == "redact" else f"[{entity_type}]"
                scrubbed = pattern.sub(replacement, scrubbed)

    return detected, scrubbed


def check_data_residency(provider: str, config: dict) -> bool:
    """
    Return True if the provider is allowed given data_residency config.

    When data_residency.enabled=false, always returns True.
    When region=eu, only providers listed in eu_providers are allowed.
    """
    dr_cfg = config.get("data_residency", {})
    if not dr_cfg.get("enabled", False):
        return True

    region = dr_cfg.get("region", "us").lower()

    if region == "eu":
        allowed_providers: list[str] = dr_cfg.get("eu_providers", ["ollama", "local"])
        # Normalise provider string for comparison (e.g. "ollama" from provider_name)
        provider_lower = provider.lower()
        return any(p.lower() in provider_lower for p in allowed_providers)

    # For "us" and "apac", no restriction implemented yet
    return True

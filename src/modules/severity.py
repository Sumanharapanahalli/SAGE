"""
Nano-module: Severity Classification
=====================================
Maps severity strings to numeric levels and provides comparison utilities.
Zero dependencies — pure Python.
"""
from enum import IntEnum

class Severity(IntEnum):
    UNKNOWN  = 0
    GREEN    = 1
    LOW      = 1
    INFO     = 1
    AMBER    = 2
    MEDIUM   = 2
    WARNING  = 2
    RED      = 3
    HIGH     = 3
    CRITICAL = 4

_ALIASES = {
    "unknown": Severity.UNKNOWN,
    "green":   Severity.GREEN,
    "low":     Severity.LOW,
    "info":    Severity.INFO,
    "amber":   Severity.AMBER,
    "medium":  Severity.MEDIUM,
    "warning": Severity.WARNING,
    "red":     Severity.RED,
    "high":    Severity.HIGH,
    "critical":Severity.CRITICAL,
}

def parse(value: str) -> Severity:
    """Parse a severity string (case-insensitive) to Severity enum."""
    return _ALIASES.get(value.lower().strip(), Severity.UNKNOWN)

def requires_action(value: str, threshold: str = "amber") -> bool:
    """Return True if severity >= threshold."""
    return parse(value) >= parse(threshold)

def badge_color(value: str) -> str:
    """Return a CSS color class for UI badges."""
    s = parse(value)
    if s >= Severity.CRITICAL: return "red"
    if s >= Severity.RED:      return "orange"
    if s >= Severity.AMBER:    return "yellow"
    if s >= Severity.GREEN:    return "green"
    return "gray"

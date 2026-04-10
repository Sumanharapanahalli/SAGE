"""
Regulatory compliance primitives for SAGE Agent SDK integration.

Opt-in extensions for medical device CDS and similar regulated domains.
Provides FDA classification, intended purpose validation, transparency
reporting, and automation bias controls.
"""

from .intended_purpose import IntendedPurpose, validate_intended_purpose

__all__ = [
    "IntendedPurpose",
    "validate_intended_purpose",
]

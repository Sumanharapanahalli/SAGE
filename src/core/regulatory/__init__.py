"""
Regulatory compliance primitives for SAGE Agent SDK integration.

Opt-in extensions for medical device CDS and similar regulated domains.
Provides FDA classification, intended purpose validation, transparency
reporting, and automation bias controls.
"""

from .intended_purpose import IntendedPurpose, validate_intended_purpose
from .fda_classifier import FDAClassifierAgent, apply_four_criterion_test
from .transparency_report import (
    TransparencyReport,
    validate_transparency_report,
    transparency_validator_hook,
    is_clinical_tool,
)

__all__ = [
    "IntendedPurpose",
    "validate_intended_purpose",
    "FDAClassifierAgent",
    "apply_four_criterion_test",
    "TransparencyReport",
    "validate_transparency_report",
    "transparency_validator_hook",
    "is_clinical_tool",
]

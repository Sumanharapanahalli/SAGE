"""Tests for IntendedPurpose schema and validator."""

import pytest
from pydantic import ValidationError
from src.core.regulatory.intended_purpose import IntendedPurpose, validate_intended_purpose


def test_intended_purpose_valid_config():
    """Test valid intended purpose configuration validates successfully."""
    config = {
        "function": "Triage support for emergency department prioritization",
        "performance_claims": {
            "sensitivity": 0.92,
            "specificity": 0.88,
            "confidence_interval": "95%"
        },
        "target_population": {
            "age_range": [18, 85],
            "exclusions": ["pregnancy", "pediatric"]
        },
        "boundary_conditions": [
            "Not for life-threatening time-critical decisions",
            "Requires physician verification"
        ],
        "user_group": "Board-certified ED physicians",
        "fda_classification": "Non-Device CDS",
        "mdr_class": "Class I"
    }

    purpose = IntendedPurpose(**config)
    assert purpose.function == "Triage support for emergency department prioritization"
    assert purpose.performance_claims.sensitivity == 0.92
    assert purpose.fda_classification == "Non-Device CDS"


def test_intended_purpose_invalid_sensitivity():
    """Test invalid sensitivity value raises ValidationError."""
    config = {
        "function": "Test function",
        "performance_claims": {
            "sensitivity": 1.5,  # Invalid: > 1.0
            "specificity": 0.88,
            "confidence_interval": "95%"
        },
        "target_population": {
            "age_range": [18, 85],
            "exclusions": []
        },
        "boundary_conditions": ["Test condition"],
        "user_group": "Test users",
        "fda_classification": "Non-Device CDS",
        "mdr_class": "Class I"
    }

    with pytest.raises(ValidationError) as exc_info:
        IntendedPurpose(**config)
    # Check that validation failed for sensitivity with bounds constraint
    error_str = str(exc_info.value)
    assert "sensitivity" in error_str
    assert ("1.5" in error_str or "less than or equal" in error_str)


def test_validate_intended_purpose_blocks_unsafe_task():
    """Test validator blocks task execution outside boundary conditions."""
    purpose = IntendedPurpose(
        function="ED triage support",
        performance_claims={
            "sensitivity": 0.92,
            "specificity": 0.88,
            "confidence_interval": "95%"
        },
        target_population={
            "age_range": [18, 85],
            "exclusions": ["pregnancy"]
        },
        boundary_conditions=[
            "Not for life-threatening time-critical decisions"
        ],
        user_group="ED physicians",
        fda_classification="Non-Device CDS",
        mdr_class="Class I"
    )

    # This should raise ValidationError for time-critical task
    with pytest.raises(ValidationError) as exc_info:
        validate_intended_purpose(purpose, task_type="emergency_code_blue")
    assert "Task type 'emergency_code_blue' violates boundary condition" in str(exc_info.value)

    # This should pass for non-critical task
    validate_intended_purpose(purpose, task_type="routine_triage")  # Should not raise

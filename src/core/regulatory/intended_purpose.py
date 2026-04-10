"""
Intended Purpose schema and validator for medical device CDS solutions.

Enforces FDA-compliant intended purpose declarations and validates
task execution against declared boundary conditions.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class PerformanceClaims(BaseModel):
    """Performance claims for the intended purpose."""

    sensitivity: float = Field(
        ..., ge=0.0, le=1.0, description="Sensitivity (0.0-1.0)"
    )
    specificity: float = Field(
        ..., ge=0.0, le=1.0, description="Specificity (0.0-1.0)"
    )
    confidence_interval: str = Field(..., description="Confidence interval (e.g., '95%')")

    @field_validator("sensitivity", "specificity")
    @classmethod
    def validate_performance_metrics(cls, v, info):
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"{info.field_name} must be between 0.0 and 1.0")
        return v


class TargetPopulation(BaseModel):
    """Target population characteristics."""

    age_range: List[int] = Field(..., description="Age range [min, max]")
    exclusions: List[str] = Field(
        default_factory=list, description="Population exclusions"
    )

    @field_validator("age_range")
    @classmethod
    def validate_age_range(cls, v):
        if len(v) != 2 or v[0] >= v[1] or v[0] < 0:
            raise ValueError("age_range must be [min_age, max_age] with valid ages")
        return v


class IntendedPurpose(BaseModel):
    """FDA-compliant intended purpose declaration."""

    function: str = Field(..., description="Primary function of the device/software")
    performance_claims: PerformanceClaims
    target_population: TargetPopulation
    boundary_conditions: List[str] = Field(
        ..., description="Usage limitations and constraints"
    )
    user_group: str = Field(..., description="Intended user group")
    fda_classification: str = Field(
        ..., description="FDA classification (Device CDS, Non-Device CDS)"
    )
    mdr_class: str = Field(..., description="MDR class (Class I, IIa, IIb, III)")
    predicate_device: Optional[str] = Field(
        None, description="510(k) predicate device if applicable"
    )

    @field_validator("fda_classification")
    @classmethod
    def validate_fda_classification(cls, v):
        valid_classifications = ["Device CDS", "Non-Device CDS"]
        if v not in valid_classifications:
            raise ValueError(
                f"fda_classification must be one of {valid_classifications}"
            )
        return v

    @field_validator("mdr_class")
    @classmethod
    def validate_mdr_class(cls, v):
        valid_classes = ["Class I", "Class IIa", "Class IIb", "Class III"]
        if v not in valid_classes:
            raise ValueError(f"mdr_class must be one of {valid_classes}")
        return v


def validate_intended_purpose(purpose: IntendedPurpose, task_type: str) -> None:
    """
    Validate task execution against intended purpose boundary conditions.

    Args:
        purpose: The intended purpose configuration
        task_type: Type of task being executed

    Raises:
        ValidationError: If task violates boundary conditions
    """
    from pydantic import ValidationError as PydanticValidationError

    # Time-critical task patterns that violate typical boundary conditions
    time_critical_patterns = [
        "emergency",
        "code_blue",
        "sepsis",
        "stroke",
        "cardiac_arrest",
        "life_threatening",
        "critical_care",
        "trauma",
        "resuscitation",
    ]

    # Check if task type suggests time-critical operation
    task_lower = task_type.lower()
    is_time_critical = any(pattern in task_lower for pattern in time_critical_patterns)

    if is_time_critical:
        # Check if boundary conditions prohibit time-critical decisions
        boundary_text = " ".join(purpose.boundary_conditions).lower()
        if any(
            phrase in boundary_text
            for phrase in ["not for life-threatening", "time-critical"]
        ):
            # Raise a validation error by attempting to validate an invalid IntendedPurpose
            # with a modified boundary_conditions that will fail in a custom validator
            class _ValidatorForError(IntendedPurpose):
                @field_validator("boundary_conditions")
                @classmethod
                def check_task_type(cls, v):
                    raise ValueError(
                        f"Task type '{task_type}' violates boundary condition: "
                        f"intended purpose prohibits time-critical decisions"
                    )

            try:
                _ValidatorForError(**purpose.model_dump())
            except Exception:
                # Re-raise as PydanticValidationError for consistency
                raise PydanticValidationError.from_exception_data(
                    title="IntendedPurpose",
                    line_errors=[
                        {
                            "type": "value_error",
                            "loc": ("boundary_conditions",),
                            "input": purpose.boundary_conditions,
                            "ctx": {
                                "error": f"Task type '{task_type}' violates boundary condition: "
                                f"intended purpose prohibits time-critical decisions"
                            },
                        }
                    ],
                )

    logger.info(f"Task type '{task_type}' validated against intended purpose")

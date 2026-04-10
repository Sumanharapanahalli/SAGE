"""
Transparency Report schema and validator hook for FDA 4-part transparency.

Enforces structured explainability for agent recommendations per FDA guidance:
- What inputs were used
- What sources were cited
- What logic chain was followed
- How confident the system is
- Whether user can independently verify
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TransparencyReport(BaseModel):
    """
    FDA-compliant transparency report for agent recommendations.

    Required for any agent output that could influence clinical decisions.
    Provides structured explainability and automation bias warnings.
    """

    inputs_used: List[str] = Field(
        ..., description="Data inputs used in analysis"
    )
    sources_cited: List[str] = Field(
        ..., description="Medical sources or guidelines cited"
    )
    logic_chain: List[str] = Field(
        ..., description="Step-by-step reasoning chain"
    )
    confidence: str = Field(
        ..., description="Confidence level: LOW, MEDIUM, HIGH"
    )
    user_verifiable: bool = Field(
        ..., description="Whether user can independently verify"
    )
    automation_bias_warning: Optional[str] = Field(
        None, description="Warning about automation bias"
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v):
        """Validate confidence level is one of allowed values."""
        valid_levels = ["LOW", "MEDIUM", "HIGH"]
        if v not in valid_levels:
            raise ValueError(f"confidence must be one of {valid_levels}")
        return v

    @field_validator("logic_chain")
    @classmethod
    def validate_logic_chain(cls, v):
        """Validate logic_chain contains at least 2 steps."""
        if len(v) < 2:
            raise ValueError("logic_chain must contain at least 2 steps")
        return v

    @field_validator("inputs_used")
    @classmethod
    def validate_inputs_used(cls, v):
        """Validate inputs_used is not empty."""
        if len(v) == 0:
            raise ValueError("inputs_used cannot be empty")
        return v


def validate_transparency_report(report_data: Dict[str, Any]) -> TransparencyReport:
    """
    Validate transparency report data against schema.

    Args:
        report_data: Raw transparency report data

    Returns:
        Validated TransparencyReport instance

    Raises:
        ValidationError: If report data is invalid
    """
    return TransparencyReport(**report_data)


# Clinical tools that require transparency reports
CLINICAL_TOOLS = {
    "clinical_analysis",
    "diagnosis_support",
    "treatment_recommendation",
    "sepsis_alert",
    "drug_interaction_check",
    "lab_interpretation",
    "imaging_analysis",
    "risk_assessment",
    "triage_support",
}

# Non-clinical tools that don't require transparency reports
NON_CLINICAL_TOOLS = {
    "Read",
    "Edit",
    "Write",
    "Bash",
    "Grep",
    "Glob",
    "WebSearch",
    "WebFetch",
    "Agent",
}


def is_clinical_tool(tool_name: str) -> bool:
    """
    Check if a tool requires transparency reporting.

    Args:
        tool_name: Name of the tool

    Returns:
        True if tool is clinical/decision-making, False otherwise
    """
    if tool_name in CLINICAL_TOOLS:
        return True
    if "clinical" in tool_name.lower() or "diagnosis" in tool_name.lower():
        return True
    return False


def transparency_validator_hook(
    tool_name: str, tool_args: Dict[str, Any], tool_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Post-tool-use hook that validates transparency reports.

    Enforced for clinical/medical tools that generate recommendations.
    Non-clinical tools (Read, Edit, Bash) are skipped.

    Args:
        tool_name: Name of the tool that was executed
        tool_args: Arguments passed to the tool
        tool_result: Result returned by the tool

    Returns:
        Original tool_result if validation passes

    Raises:
        ValidationError: If transparency report is missing or invalid
    """
    # Skip transparency validation for non-clinical tools
    if tool_name in NON_CLINICAL_TOOLS:
        return tool_result

    # Skip if not a clinical tool (framework tools, utilities, etc.)
    if not is_clinical_tool(tool_name):
        return tool_result

    # Clinical tools must include transparency report
    if "transparency_report" not in tool_result:
        from pydantic import ValidationError

        raise ValidationError.from_exception_data(
            title="TransparencyReport",
            line_errors=[
                {
                    "type": "value_error",
                    "loc": ("transparency_report",),
                    "input": tool_result,
                    "ctx": {
                        "error": f"Missing transparency_report in {tool_name} result. "
                        f"Clinical tools must provide structured explainability."
                    },
                }
            ],
        )

    # Validate the transparency report structure
    try:
        report = validate_transparency_report(tool_result["transparency_report"])
        logger.info(
            f"Transparency report validated for {tool_name}: {report.confidence} confidence"
        )
    except Exception as e:
        from pydantic import ValidationError

        raise ValidationError.from_exception_data(
            title="TransparencyReport",
            line_errors=[
                {
                    "type": "value_error",
                    "loc": ("transparency_report",),
                    "input": tool_result.get("transparency_report", {}),
                    "ctx": {"error": f"Invalid transparency_report in {tool_name} result: {str(e)}"},
                }
            ],
        )

    return tool_result

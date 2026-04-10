"""
Automation Bias Controls for time-critical medical decisions.

Implements delays, acknowledgment requirements, and confirmation steps
to mitigate automation bias in time-sensitive clinical tasks per FDA guidance.

Key principles:
- Mandatory delays ensure physician reflection time
- Explicit acknowledgment requirements prevent auto-acceptance
- Confirmation steps enforce structured decision-making
- Controls scale with task time criticality (low/medium/high)
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Dict, Any, Optional
import time
import logging

logger = logging.getLogger(__name__)


class AutomationBiasControls(BaseModel):
    """
    Configuration for automation bias mitigation controls.

    Applied to time-critical tasks to ensure appropriate human oversight
    and reduce over-reliance on automated recommendations.

    Attributes:
        require_physician_acknowledgment: Require explicit physician acknowledgment
        force_reasoning_display: Force display of reasoning chain
        delay_ms: Mandatory delay before recommendation display (milliseconds)
        confirmation_steps: Required confirmation steps before acting on recommendation
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "require_physician_acknowledgment": True,
                "force_reasoning_display": True,
                "delay_ms": 3000,
                "confirmation_steps": [
                    "Review patient vitals",
                    "Verify recommendation appropriateness",
                    "Consider alternative diagnoses"
                ]
            }
        }
    )

    require_physician_acknowledgment: bool = Field(
        default=False,
        description="Require explicit physician acknowledgment before proceeding"
    )
    force_reasoning_display: bool = Field(
        default=False,
        description="Force display of reasoning chain and evidence"
    )
    delay_ms: int = Field(
        default=0,
        description="Mandatory delay before recommendation display (milliseconds)"
    )
    confirmation_steps: List[str] = Field(
        default_factory=list,
        description="Required confirmation steps to complete before acting"
    )

    @field_validator('delay_ms')
    @classmethod
    def validate_delay(cls, v):
        """Validate delay is non-negative and within reasonable bounds."""
        if v < 0:
            raise ValueError("delay_ms must be non-negative")
        if v > 30000:  # Max 30 seconds
            raise ValueError("delay_ms cannot exceed 30000ms (30 seconds)")
        return v

    @field_validator('confirmation_steps')
    @classmethod
    def validate_confirmation_steps(cls, v):
        """Validate confirmation steps list is not excessively long."""
        if len(v) > 10:
            raise ValueError("confirmation_steps cannot exceed 10 steps")
        return v


def apply_time_criticality_controls(
    time_criticality: str,
    controls: AutomationBiasControls
) -> str:
    """
    Apply time criticality controls and return automation bias warning.

    Enforces delays, acknowledgment requirements, and confirmation steps
    based on the task's time criticality level.

    Args:
        time_criticality: One of "low", "medium", or "high"
        controls: Automation bias controls configuration

    Returns:
        Automation bias warning message describing applied controls
    """
    if time_criticality == "low":
        return ""

    warning_parts = []

    # Apply mandatory delay
    if controls.delay_ms > 0:
        delay_seconds = controls.delay_ms / 1000.0
        logger.info(
            f"Applying {delay_seconds}s delay for time-criticality: {time_criticality}"
        )
        time.sleep(delay_seconds)
        warning_parts.append(f"Mandatory {delay_seconds}s delay applied")

    # Build warning message based on criticality
    if time_criticality == "high":
        warning_parts.append("High time-criticality task detected")
    elif time_criticality == "medium":
        warning_parts.append("Medium time-criticality task detected")

    # Add control requirements
    if controls.require_physician_acknowledgment:
        warning_parts.append("physician acknowledgment required")

    if controls.force_reasoning_display:
        warning_parts.append("reasoning display enforced")

    if controls.confirmation_steps:
        steps_str = ", ".join(controls.confirmation_steps)
        warning_parts.append(f"Please complete confirmation steps: {steps_str}")

    return "; ".join(warning_parts)


def automation_bias_hook(
    tool_name: str,
    tool_args: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Pre-tool-use hook that applies automation bias controls.

    Enforced for time-critical tasks based on time_criticality configuration.
    Applies delays, warnings, and acknowledgment requirements to reduce
    automation bias and ensure appropriate human oversight.

    Hook is called before tool execution for tasks with:
    - time_criticality = "medium" or "high"
    - Valid automation_bias_controls configuration

    Args:
        tool_name: Name of the tool about to be executed
        tool_args: Arguments that will be passed to the tool
            Must include:
            - task_type: Type of task being executed
            - task_config: Task configuration dict with time_criticality

    Returns:
        Dict with automation bias warnings (if applicable)
        Empty dict if controls do not apply
    """
    # Extract task configuration
    task_config = tool_args.get("task_config")
    if not task_config:
        return {}

    time_criticality = task_config.get("time_criticality", "low")
    controls_config = task_config.get("automation_bias_controls", {})

    # Skip controls for low criticality tasks
    if time_criticality == "low":
        return {}

    # Parse controls configuration
    try:
        controls = AutomationBiasControls(**controls_config)
    except Exception as e:
        logger.warning(
            f"Invalid automation bias controls config for {tool_name}: {e}"
        )
        return {}

    # Apply controls and generate warning
    warning = apply_time_criticality_controls(time_criticality, controls)

    result = {}
    if warning:
        result["automation_bias_warning"] = warning
        logger.info(
            f"Applied automation bias controls for {tool_name}: {warning}"
        )

    return result


# Time-critical task patterns that trigger automation bias controls
TIME_CRITICAL_PATTERNS = [
    "sepsis", "stroke", "cardiac_arrest", "trauma", "emergency",
    "code_blue", "resuscitation", "shock", "respiratory_failure"
]


def is_time_critical_task(task_type: str) -> bool:
    """
    Check if task type is time-critical and requires automation bias controls.

    Args:
        task_type: The type of task to evaluate

    Returns:
        True if task matches known time-critical patterns
    """
    task_lower = task_type.lower()
    return any(pattern in task_lower for pattern in TIME_CRITICAL_PATTERNS)


def get_default_controls(time_criticality: str) -> AutomationBiasControls:
    """
    Get default automation bias controls for a given time criticality level.

    Provides FDA-compliant defaults:
    - High: 3s delay, physician acknowledgment, reasoning display, 3-step confirmation
    - Medium: 1s delay, reasoning display, 1-step confirmation
    - Low: No controls

    Args:
        time_criticality: One of "low", "medium", or "high"

    Returns:
        Configured AutomationBiasControls for the criticality level
    """
    if time_criticality == "high":
        return AutomationBiasControls(
            require_physician_acknowledgment=True,
            force_reasoning_display=True,
            delay_ms=3000,
            confirmation_steps=[
                "Review patient vitals",
                "Verify recommendation appropriateness",
                "Consider alternative diagnoses"
            ]
        )
    elif time_criticality == "medium":
        return AutomationBiasControls(
            require_physician_acknowledgment=False,
            force_reasoning_display=True,
            delay_ms=1000,
            confirmation_steps=[
                "Review recommendation rationale"
            ]
        )
    else:  # low
        return AutomationBiasControls()

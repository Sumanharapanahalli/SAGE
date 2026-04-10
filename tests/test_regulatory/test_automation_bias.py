"""
Tests for automation bias controls in time-critical medical decisions.

Verifies that mandatory delays, acknowledgment requirements, and confirmation
steps are properly enforced for high time-criticality tasks per FDA guidance.
"""

import pytest
import time
from unittest.mock import Mock, patch
from src.core.regulatory.automation_bias import (
    AutomationBiasControls, automation_bias_hook, apply_time_criticality_controls
)


def test_automation_bias_controls_valid():
    """Test valid automation bias controls configuration."""
    controls_data = {
        "require_physician_acknowledgment": True,
        "force_reasoning_display": True,
        "delay_ms": 3000,
        "confirmation_steps": [
            "Review patient history",
            "Verify vital signs",
            "Confirm recommendation appropriateness"
        ]
    }

    controls = AutomationBiasControls(**controls_data)
    assert controls.require_physician_acknowledgment is True
    assert controls.delay_ms == 3000
    assert len(controls.confirmation_steps) == 3


def test_automation_bias_controls_invalid_delay():
    """Test invalid delay value raises ValidationError."""
    controls_data = {
        "require_physician_acknowledgment": False,
        "force_reasoning_display": True,
        "delay_ms": -1000  # Invalid: negative delay
    }

    from pydantic import ValidationError
    with pytest.raises(ValidationError) as exc_info:
        AutomationBiasControls(**controls_data)
    assert "delay_ms must be non-negative" in str(exc_info.value)


def test_automation_bias_hook_high_criticality():
    """Test automation bias hook applies controls for high time-criticality tasks."""
    task_config = {
        "time_criticality": "high",
        "automation_bias_controls": {
            "require_physician_acknowledgment": True,
            "force_reasoning_display": True,
            "delay_ms": 2000
        }
    }

    tool_args = {
        "task_type": "sepsis_alert",
        "task_config": task_config
    }

    start_time = time.time()

    # Mock the delay mechanism for testing
    with patch('time.sleep') as mock_sleep:
        result = automation_bias_hook(
            tool_name="sepsis_alert",
            tool_args=tool_args
        )

        # Verify delay was applied
        mock_sleep.assert_called_once_with(2.0)  # 2000ms = 2.0s

    # Verify warning was added to result
    assert "automation_bias_warning" in result
    assert "High time-criticality task" in result["automation_bias_warning"]
    assert "physician acknowledgment required" in result["automation_bias_warning"]


def test_automation_bias_hook_low_criticality_skipped():
    """Test automation bias hook skips controls for low time-criticality tasks."""
    task_config = {
        "time_criticality": "low",
        "automation_bias_controls": {
            "require_physician_acknowledgment": False,
            "force_reasoning_display": False,
            "delay_ms": 0
        }
    }

    tool_args = {
        "task_type": "routine_report",
        "task_config": task_config
    }

    with patch('time.sleep') as mock_sleep:
        result = automation_bias_hook(
            tool_name="routine_report",
            tool_args=tool_args
        )

        # No delay should be applied for low criticality
        mock_sleep.assert_not_called()

    # No automation bias warning for low criticality
    assert "automation_bias_warning" not in result


def test_apply_time_criticality_controls():
    """Test time criticality controls application."""
    controls = AutomationBiasControls(
        require_physician_acknowledgment=True,
        force_reasoning_display=True,
        delay_ms=1500,
        confirmation_steps=["Step 1", "Step 2"]
    )

    with patch('time.sleep') as mock_sleep:
        warning = apply_time_criticality_controls("high", controls)

        mock_sleep.assert_called_once_with(1.5)  # 1500ms = 1.5s
        assert "physician acknowledgment required" in warning
        assert "Please complete confirmation steps" in warning


def test_automation_bias_hook_missing_config():
    """Test automation bias hook handles missing task config gracefully."""
    tool_args = {
        "task_type": "unknown_task"
        # Missing task_config
    }

    # Should not raise exception, just skip controls
    result = automation_bias_hook(
        tool_name="unknown_task",
        tool_args=tool_args
    )

    # Should return empty dict (no controls applied)
    assert result == {}

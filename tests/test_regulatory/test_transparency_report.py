"""Tests for Transparency Report schema and validator hook."""

import pytest
from pydantic import ValidationError
from src.core.regulatory.transparency_report import (
    TransparencyReport,
    transparency_validator_hook,
    validate_transparency_report,
)


def test_transparency_report_valid():
    """Test valid transparency report validates successfully."""
    report_data = {
        "inputs_used": ["vital_signs.json", "lab_results_2024.csv"],
        "sources_cited": ["NICE Guideline CG87", "UpToDate 2024"],
        "logic_chain": [
            "Analyzed vital signs: HR=110, BP=85/60, Temp=38.2°C",
            "Cross-referenced with sepsis criteria",
            "Calculated qSOFA score = 2",
            "Recommendation: Consider sepsis workup",
        ],
        "confidence": "HIGH",
        "user_verifiable": True,
        "automation_bias_warning": "Time-critical: verify before acting",
    }

    report = TransparencyReport(**report_data)
    assert report.confidence == "HIGH"
    assert len(report.logic_chain) == 4
    assert "sepsis" in report.logic_chain[1]
    assert report.user_verifiable is True


def test_transparency_report_invalid_confidence():
    """Test invalid confidence level raises ValidationError."""
    report_data = {
        "inputs_used": ["test_data.json"],
        "sources_cited": ["Test Source"],
        "logic_chain": ["Step 1", "Step 2"],
        "confidence": "EXTREME",  # Invalid confidence level
        "user_verifiable": True,
    }

    with pytest.raises(ValidationError) as exc_info:
        TransparencyReport(**report_data)
    assert "confidence must be one of" in str(exc_info.value)


def test_transparency_report_empty_logic_chain():
    """Test that logic_chain must have at least 2 steps."""
    report_data = {
        "inputs_used": ["test_data.json"],
        "sources_cited": ["Test Source"],
        "logic_chain": ["Only one step"],  # Invalid: only 1 step
        "confidence": "MEDIUM",
        "user_verifiable": True,
    }

    with pytest.raises(ValidationError) as exc_info:
        TransparencyReport(**report_data)
    assert "logic_chain must contain at least 2 steps" in str(exc_info.value)


def test_transparency_report_empty_inputs():
    """Test that inputs_used cannot be empty."""
    report_data = {
        "inputs_used": [],  # Invalid: empty
        "sources_cited": ["Test Source"],
        "logic_chain": ["Step 1", "Step 2"],
        "confidence": "MEDIUM",
        "user_verifiable": True,
    }

    with pytest.raises(ValidationError) as exc_info:
        TransparencyReport(**report_data)
    assert "inputs_used cannot be empty" in str(exc_info.value)


def test_transparency_validator_hook_success():
    """Test transparency validator hook passes valid transparency report."""
    mock_tool_result = {
        "content": "Analysis complete",
        "transparency_report": {
            "inputs_used": ["patient_data.json"],
            "sources_cited": ["Medical Journal 2024"],
            "logic_chain": [
                "Analyzed data",
                "Applied criteria",
                "Generated recommendation",
            ],
            "confidence": "MEDIUM",
            "user_verifiable": True,
            "automation_bias_warning": "Please verify recommendation",
        },
    }

    # Should not raise any exceptions
    result = transparency_validator_hook(
        tool_name="clinical_analysis",
        tool_args={"patient_id": "12345"},
        tool_result=mock_tool_result,
    )

    assert result == mock_tool_result  # Hook should return original result


def test_transparency_validator_hook_missing_report():
    """Test transparency validator hook rejects missing transparency report."""
    mock_tool_result = {
        "content": "Analysis complete"
        # Missing transparency_report
    }

    with pytest.raises(ValidationError) as exc_info:
        transparency_validator_hook(
            tool_name="clinical_analysis",
            tool_args={"patient_id": "12345"},
            tool_result=mock_tool_result,
        )
    assert "Missing transparency_report" in str(exc_info.value)


def test_transparency_validator_hook_skip_non_clinical():
    """Test transparency validator hook skips non-clinical tools."""
    mock_tool_result = {"content": "File read successfully"}

    # Should pass through without validation for non-clinical tools
    result = transparency_validator_hook(
        tool_name="Read",
        tool_args={"file_path": "/tmp/test.txt"},
        tool_result=mock_tool_result,
    )

    assert result == mock_tool_result


def test_transparency_validator_hook_skip_bash():
    """Test transparency validator hook skips Bash tool."""
    mock_tool_result = {"output": "command executed", "exit_code": 0}

    result = transparency_validator_hook(
        tool_name="Bash",
        tool_args={"command": "ls -la"},
        tool_result=mock_tool_result,
    )

    assert result == mock_tool_result


def test_transparency_report_with_minimal_fields():
    """Test transparency report with only required fields."""
    report_data = {
        "inputs_used": ["data.csv"],
        "sources_cited": ["Source A"],
        "logic_chain": ["Step 1", "Step 2"],
        "confidence": "LOW",
        "user_verifiable": False,
    }

    report = TransparencyReport(**report_data)
    assert report.confidence == "LOW"
    assert report.automation_bias_warning is None


def test_validate_transparency_report_function():
    """Test standalone validate_transparency_report function."""
    valid_data = {
        "inputs_used": ["test.json"],
        "sources_cited": ["Test Guideline"],
        "logic_chain": ["Analyze", "Verify"],
        "confidence": "MEDIUM",
        "user_verifiable": True,
    }

    report = validate_transparency_report(valid_data)
    assert isinstance(report, TransparencyReport)
    assert report.confidence == "MEDIUM"


def test_transparency_validator_hook_invalid_report_data():
    """Test transparency validator hook with invalid transparency_report data."""
    mock_tool_result = {
        "content": "Analysis complete",
        "transparency_report": {
            "inputs_used": [],  # Invalid: empty
            "sources_cited": ["Medical Journal 2024"],
            "logic_chain": ["Step 1", "Step 2"],
            "confidence": "MEDIUM",
            "user_verifiable": True,
        },
    }

    with pytest.raises(ValidationError) as exc_info:
        transparency_validator_hook(
            tool_name="clinical_analysis",
            tool_args={"patient_id": "12345"},
            tool_result=mock_tool_result,
        )
    assert "inputs_used cannot be empty" in str(exc_info.value)

"""
SAGE[ai] - Unit tests for AnalystAgent (src/agents/analyst.py)

Tests analysis, JSON parsing, audit logging, RAG context injection,
feedback learning, and edge cases.
"""

import json
import re
import sqlite3
from unittest.mock import MagicMock, patch

import pytest


pytestmark = pytest.mark.unit

UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

FIXED_ANALYSIS_JSON = json.dumps({
    "severity": "HIGH",
    "root_cause_hypothesis": "test hypothesis",
    "recommended_action": "test action",
})


def _query_audit(db_path, action_type=None):
    """Query audit log rows, optionally filtered by action_type."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if action_type:
        rows = conn.execute(
            "SELECT * FROM compliance_audit_log WHERE action_type = ?", (action_type,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM compliance_audit_log").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_analyze_log_returns_required_fields(tmp_audit_db):
    """analyze_log() must return a dict with keys: severity, root_cause_hypothesis, recommended_action, trace_id."""
    with patch("src.core.llm_gateway.LLMGateway.generate", return_value=FIXED_ANALYSIS_JSON), \
         patch("src.agents.analyst.audit_logger", tmp_audit_db), \
         patch("src.agents.analyst.vector_memory") as mock_vm:
        mock_vm.search.return_value = []
        mock_vm.add_feedback = MagicMock()
        from src.agents.analyst import AnalystAgent
        agent = AnalystAgent()
        result = agent.analyze_log("ERROR: timeout on sensor read")

    assert "severity" in result, "Result must contain 'severity'."
    assert "root_cause_hypothesis" in result, "Result must contain 'root_cause_hypothesis'."
    assert "recommended_action" in result, "Result must contain 'recommended_action'."
    assert "trace_id" in result, "Result must contain 'trace_id'."


def test_analyze_log_creates_audit_record(tmp_audit_db):
    """analyze_log() must create an ANALYSIS_PROPOSAL record in the audit database."""
    with patch("src.core.llm_gateway.LLMGateway.generate", return_value=FIXED_ANALYSIS_JSON), \
         patch("src.agents.analyst.audit_logger", tmp_audit_db), \
         patch("src.agents.analyst.vector_memory") as mock_vm:
        mock_vm.search.return_value = []
        from src.agents.analyst import AnalystAgent
        agent = AnalystAgent()
        agent.analyze_log("ERROR: i2c bus stuck LOW")

    rows = _query_audit(tmp_audit_db.db_path, action_type="ANALYSIS_PROPOSAL")
    assert len(rows) >= 1, "Expected at least 1 ANALYSIS_PROPOSAL record in audit log."


def test_analyze_log_trace_id_is_uuid(tmp_audit_db):
    """The trace_id in the result must be a valid UUID v4."""
    with patch("src.core.llm_gateway.LLMGateway.generate", return_value=FIXED_ANALYSIS_JSON), \
         patch("src.agents.analyst.audit_logger", tmp_audit_db), \
         patch("src.agents.analyst.vector_memory") as mock_vm:
        mock_vm.search.return_value = []
        from src.agents.analyst import AnalystAgent
        agent = AnalystAgent()
        result = agent.analyze_log("CRITICAL: watchdog timeout")

    trace_id = result.get("trace_id", "")
    assert UUID4_PATTERN.match(trace_id), f"trace_id '{trace_id}' is not a valid UUID v4."


def test_analyze_log_handles_json_parse_failure(tmp_audit_db):
    """When LLM returns non-JSON, analyze_log() must still return a dict with all required fields."""
    with patch("src.core.llm_gateway.LLMGateway.generate", return_value="not valid json at all"), \
         patch("src.agents.analyst.audit_logger", tmp_audit_db), \
         patch("src.agents.analyst.vector_memory") as mock_vm:
        mock_vm.search.return_value = []
        from src.agents.analyst import AnalystAgent
        agent = AnalystAgent()
        result = agent.analyze_log("ERROR: flash write failed")

    assert "severity" in result, "Fallback result must have 'severity'."
    assert "root_cause_hypothesis" in result, "Fallback result must have 'root_cause_hypothesis'."
    assert "recommended_action" in result, "Fallback result must have 'recommended_action'."
    assert "trace_id" in result, "Fallback result must have 'trace_id'."


def test_analyze_log_uses_rag_context(tmp_audit_db):
    """
    When vector memory has prior context, the LLM prompt must contain 'PAST CONTEXT'.
    """
    captured_prompts = []

    def capture_generate(prompt, system_prompt=""):
        captured_prompts.append(prompt)
        return FIXED_ANALYSIS_JSON

    with patch("src.core.llm_gateway.LLMGateway.generate", side_effect=capture_generate), \
         patch("src.agents.analyst.audit_logger", tmp_audit_db), \
         patch("src.agents.analyst.vector_memory") as mock_vm:
        mock_vm.search.return_value = ["Previous incident: UART timeout resolved by increasing buffer size."]
        from src.agents.analyst import AnalystAgent
        agent = AnalystAgent()
        agent.analyze_log("ERROR: UART timeout again")

    assert len(captured_prompts) >= 1, "LLM generate must be called."
    combined_prompt = " ".join(captured_prompts)
    assert "PAST CONTEXT" in combined_prompt, (
        f"Expected 'PAST CONTEXT' in LLM prompt, but got: {combined_prompt[:300]!r}"
    )


def test_learn_from_feedback_adds_to_memory(tmp_audit_db):
    """learn_from_feedback() must add a learning text to vector memory."""
    with patch("src.agents.analyst.audit_logger", tmp_audit_db), \
         patch("src.agents.analyst.vector_memory") as mock_vm:
        mock_vm.add_feedback = MagicMock()
        from src.agents.analyst import AnalystAgent
        agent = AnalystAgent()
        agent.learn_from_feedback(
            log_entry="ERROR: uart timeout",
            human_comment="Root cause is hardware fault in RX pin",
            original_analysis={"root_cause_hypothesis": "software bug", "recommended_action": "restart"},
        )
        # Verify add_feedback was called
        assert mock_vm.add_feedback.called, "vector_memory.add_feedback() must be called."
        call_args = mock_vm.add_feedback.call_args
        learning_text = call_args[0][0]  # First positional argument
        assert "uart timeout" in learning_text.lower() or "UART" in learning_text, (
            f"Learning text should reference the log entry. Got: {learning_text!r}"
        )


def test_learn_from_feedback_creates_audit_record(tmp_audit_db):
    """learn_from_feedback() must create a FEEDBACK_LEARNING record in the audit log."""
    with patch("src.agents.analyst.audit_logger", tmp_audit_db), \
         patch("src.agents.analyst.vector_memory") as mock_vm:
        mock_vm.add_feedback = MagicMock()
        from src.agents.analyst import AnalystAgent
        agent = AnalystAgent()
        agent.learn_from_feedback(
            log_entry="ERROR: sensor read timeout",
            human_comment="The sensor cable is loose",
            original_analysis={"root_cause_hypothesis": "firmware bug"},
        )

    rows = _query_audit(tmp_audit_db.db_path, action_type="FEEDBACK_LEARNING")
    assert len(rows) >= 1, "Expected at least 1 FEEDBACK_LEARNING record in audit log."
    assert rows[0]["actor"] == "Human_Engineer", (
        f"Expected actor 'Human_Engineer', got '{rows[0]['actor']}'."
    )


def test_analyze_log_with_empty_string(tmp_audit_db):
    """analyze_log('') must not raise an exception and must return a result dict."""
    with patch("src.core.llm_gateway.LLMGateway.generate", return_value=FIXED_ANALYSIS_JSON), \
         patch("src.agents.analyst.audit_logger", tmp_audit_db), \
         patch("src.agents.analyst.vector_memory") as mock_vm:
        mock_vm.search.return_value = []
        from src.agents.analyst import AnalystAgent
        agent = AnalystAgent()
        try:
            result = agent.analyze_log("")
        except Exception as exc:
            pytest.fail(f"analyze_log('') raised an exception: {exc}")
    assert isinstance(result, dict), f"Expected dict result, got {type(result)}: {result!r}"


def test_analyze_log_with_long_entry(tmp_audit_db):
    """analyze_log() with 10000-char input must not raise an exception."""
    long_entry = "x" * 10000
    with patch("src.core.llm_gateway.LLMGateway.generate", return_value=FIXED_ANALYSIS_JSON), \
         patch("src.agents.analyst.audit_logger", tmp_audit_db), \
         patch("src.agents.analyst.vector_memory") as mock_vm:
        mock_vm.search.return_value = []
        from src.agents.analyst import AnalystAgent
        agent = AnalystAgent()
        try:
            result = agent.analyze_log(long_entry)
        except Exception as exc:
            pytest.fail(f"analyze_log() raised an exception with 10000-char input: {exc}")
    assert isinstance(result, dict), "Expected dict result for long input."


def test_severity_values(tmp_audit_db):
    """Various severity strings from LLM (HIGH, MEDIUM, LOW, CRITICAL) must pass through unchanged."""
    for severity in ["HIGH", "MEDIUM", "LOW", "CRITICAL"]:
        llm_response = json.dumps({
            "severity": severity,
            "root_cause_hypothesis": f"hypothesis for {severity}",
            "recommended_action": f"action for {severity}",
        })
        with patch("src.core.llm_gateway.LLMGateway.generate", return_value=llm_response), \
             patch("src.agents.analyst.audit_logger", tmp_audit_db), \
             patch("src.agents.analyst.vector_memory") as mock_vm:
            mock_vm.search.return_value = []
            from src.agents.analyst import AnalystAgent
            agent = AnalystAgent()
            result = agent.analyze_log(f"ERROR: test for severity {severity}")
        assert result.get("severity") == severity, (
            f"Expected severity '{severity}', got '{result.get('severity')}'."
        )

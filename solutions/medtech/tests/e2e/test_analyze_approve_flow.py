"""
SAGE[ai] - End-to-End tests for Analyze → Approve / Reject flow

Tests the full API pipeline with mocked LLM but real AuditLogger and VectorMemory.
Uses FastAPI TestClient.
"""

import json
import sqlite3
import threading
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.e2e

FIXED_LLM_RESPONSE = json.dumps({
    "severity": "HIGH",
    "root_cause_hypothesis": "test hypothesis",
    "recommended_action": "test action",
})


@pytest.fixture
def e2e_client(tmp_path, tmp_audit_db):
    """
    E2E TestClient with:
    - Real AuditLogger backed by tmp SQLite
    - Real VectorMemory in fallback mode
    - Mocked LLM gateway
    """
    from src.interface import api
    api._pending_proposals.clear()

    with patch("src.interface.api._get_audit_logger", return_value=tmp_audit_db), \
         patch("src.agents.analyst.audit_logger", tmp_audit_db), \
         patch("src.agents.analyst.vector_memory") as mock_vm, \
         patch("src.core.llm_gateway.LLMGateway.generate", return_value=FIXED_LLM_RESPONSE):
        mock_vm.search.return_value = []
        mock_vm.add_feedback = MagicMock()

        from src.interface.api import app
        with TestClient(app) as client:
            yield client, tmp_audit_db, mock_vm

    api._pending_proposals.clear()


def _query_audit(db_path, action_type):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT * FROM compliance_audit_log WHERE action_type = ?", (action_type,)
    ).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_full_analyze_then_approve_flow(e2e_client):
    """
    Full flow: POST /analyze → get trace_id → POST /approve/{trace_id}
    Audit log must contain both ANALYSIS_PROPOSAL and APPROVAL records.
    """
    client, audit_db, _ = e2e_client
    # Step 1: Analyze
    resp = client.post("/analyze", json={"log_entry": "ERROR: uart buffer overflow detected"})
    assert resp.status_code == 200, f"Analyze failed: {resp.text}"
    trace_id = resp.json().get("trace_id")
    assert trace_id, "trace_id must be returned from /analyze."

    # Step 2: Approve
    resp2 = client.post(f"/approve/{trace_id}")
    assert resp2.status_code == 200, f"Approve failed: {resp2.text}"
    assert resp2.json().get("status") == "approved"

    # Verify audit trail
    proposals = _query_audit(audit_db.db_path, "ANALYSIS_PROPOSAL")
    approvals = _query_audit(audit_db.db_path, "APPROVAL")
    assert len(proposals) >= 1, "Must have at least 1 ANALYSIS_PROPOSAL record."
    assert len(approvals) >= 1, "Must have at least 1 APPROVAL record."


def test_full_analyze_then_reject_with_learning(e2e_client):
    """
    Full flow: POST /analyze → POST /reject/{trace_id} with feedback
    → Audit log must contain FEEDBACK_LEARNING record.
    """
    client, audit_db, mock_vm = e2e_client
    # Step 1: Analyze
    resp = client.post("/analyze", json={"log_entry": "ERROR: watchdog timeout"})
    assert resp.status_code == 200
    trace_id = resp.json()["trace_id"]

    # Step 2: Reject with feedback
    feedback = "Root cause is defective sensor cable, not software timeout."
    with patch("src.interface.api._get_analyst") as mock_get_analyst:
        mock_analyst = MagicMock()
        mock_analyst.learn_from_feedback = MagicMock(side_effect=lambda log_entry, human_comment, original_analysis: (
            audit_db.log_event(
                actor="Human_Engineer",
                action_type="FEEDBACK_LEARNING",
                input_context=json.dumps(original_analysis),
                output_content=human_comment,
            )
        ))
        mock_get_analyst.return_value = mock_analyst
        resp2 = client.post(f"/reject/{trace_id}", json={"feedback": feedback})

    assert resp2.status_code == 200, f"Reject failed: {resp2.text}"
    assert resp2.json().get("status") == "rejected"

    # Verify FEEDBACK_LEARNING in audit
    learnings = _query_audit(audit_db.db_path, "FEEDBACK_LEARNING")
    assert len(learnings) >= 1, "Must have at least 1 FEEDBACK_LEARNING record after rejection."


def test_analyze_proposal_not_in_pending_after_approve(e2e_client):
    """After approving a trace_id, trying to approve again must return 404."""
    client, _, _ = e2e_client
    resp = client.post("/analyze", json={"log_entry": "ERROR: flash write failure"})
    assert resp.status_code == 200
    trace_id = resp.json()["trace_id"]

    resp2 = client.post(f"/approve/{trace_id}")
    assert resp2.status_code == 200

    # Second approval must fail
    resp3 = client.post(f"/approve/{trace_id}")
    assert resp3.status_code == 404, f"Expected 404 on second approval, got {resp3.status_code}"


def test_analyze_proposal_not_in_pending_after_reject(e2e_client):
    """After rejecting a trace_id, trying to reject again must return 404."""
    client, _, _ = e2e_client
    resp = client.post("/analyze", json={"log_entry": "ERROR: i2c bus error"})
    assert resp.status_code == 200
    trace_id = resp.json()["trace_id"]

    with patch("src.interface.api._get_analyst") as mock_get_analyst:
        mock_analyst = MagicMock()
        mock_analyst.learn_from_feedback = MagicMock()
        mock_get_analyst.return_value = mock_analyst
        resp2 = client.post(f"/reject/{trace_id}", json={"feedback": "hardware issue"})

    assert resp2.status_code == 200

    # Second rejection must fail
    resp3 = client.post(f"/reject/{trace_id}", json={"feedback": "again"})
    assert resp3.status_code == 404, f"Expected 404 on second rejection, got {resp3.status_code}"


def test_multiple_concurrent_analyses(e2e_client):
    """Submit 5 analyze requests concurrently — all must return unique trace_ids and be logged."""
    client, audit_db, _ = e2e_client
    results = []
    errors = []

    def do_analyze(log_msg):
        try:
            resp = client.post("/analyze", json={"log_entry": log_msg})
            if resp.status_code == 200:
                results.append(resp.json().get("trace_id"))
            else:
                errors.append(f"HTTP {resp.status_code}: {resp.text}")
        except Exception as exc:
            errors.append(str(exc))

    threads = [
        threading.Thread(target=do_analyze, args=(f"ERROR: concurrent test {i}",))
        for i in range(5)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"Errors during concurrent analyses: {errors}"
    assert len(results) == 5, f"Expected 5 results, got {len(results)}"
    unique_ids = set(results)
    assert len(unique_ids) == 5, f"Expected 5 unique trace_ids, got {len(unique_ids)}: {unique_ids}"

    proposals = _query_audit(audit_db.db_path, "ANALYSIS_PROPOSAL")
    assert len(proposals) == 5, f"Expected 5 ANALYSIS_PROPOSAL records, got {len(proposals)}"

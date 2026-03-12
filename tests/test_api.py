"""
SAGE[ai] - Unit tests for FastAPI endpoints (src/interface/api.py)

Tests all HTTP endpoints: health, analyze, approve, reject, audit,
MR create/review, monitor status, and Teams webhook.
All agent calls are mocked.
"""

import json
import os
import re
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.unit

UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

MOCK_ANALYSIS = {
    "severity": "HIGH",
    "root_cause_hypothesis": "test hypothesis",
    "recommended_action": "test action",
    "trace_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
}

MOCK_REVIEW = {
    "summary": "Looks safe.",
    "issues": [],
    "suggestions": ["Add tests."],
    "approved": True,
    "trace_id": "11111111-2222-4333-8444-555555555555",
    "mr_iid": 7,
    "mr_title": "Fix UART buffer",
}

MOCK_MR_CREATED = {
    "mr_iid": 8,
    "mr_url": "https://gitlab.example.com/project/-/merge_requests/8",
    "mr_title": "Fix: buffer overflow",
    "source_branch": "sage-ai/45-buffer-fix",
    "target_branch": "main",
    "issue_iid": 45,
    "trace_id": "cccccccc-dddd-4eee-8fff-000000000000",
}


@pytest.fixture(autouse=True)
def clear_pending_proposals():
    """Clear the in-memory pending proposals store before each test."""
    from src.interface import api
    api._pending_proposals.clear()
    yield
    api._pending_proposals.clear()


@pytest.fixture
def client(tmp_audit_db):
    """TestClient with tmp_audit_db injected into the API."""
    with patch("src.interface.api._get_audit_logger", return_value=tmp_audit_db):
        from src.interface.api import app
        with TestClient(app) as c:
            yield c, tmp_audit_db


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


def test_health_returns_200(client):
    """GET /health must return HTTP 200."""
    c, _ = client
    with patch("src.interface.api._get_llm_gateway") as mock_llm:
        mock_llm.return_value.get_provider_name.return_value = "GeminiCLI (gemini-2.5-flash)"
        resp = c.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"


def test_health_contains_provider_info(client):
    """GET /health must include 'llm_provider' in the response body."""
    c, _ = client
    with patch("src.interface.api._get_llm_gateway") as mock_llm:
        mock_llm.return_value.get_provider_name.return_value = "GeminiCLI (gemini-2.5-flash)"
        resp = c.get("/health")
    data = resp.json()
    assert "llm_provider" in data, f"Expected 'llm_provider' in health response: {data}"


def test_health_shows_configured_integrations(client):
    """GET /health environment dict must show correct booleans for configured integrations."""
    c, _ = client
    env = {
        "GITLAB_URL": "https://gl.test.local",
        "TEAMS_INCOMING_WEBHOOK_URL": "https://teams.webhook.local/hook",
        "METABASE_URL": "https://metabase.local",
        "SPIRA_URL": "https://spira.local",
    }
    with patch.dict(os.environ, env), \
         patch("src.interface.api._get_llm_gateway") as mock_llm:
        mock_llm.return_value.get_provider_name.return_value = "GeminiCLI"
        resp = c.get("/health")
    data = resp.json()
    env_info = data.get("environment", {})
    assert env_info.get("gitlab_configured") is True
    assert env_info.get("teams_configured") is True
    assert env_info.get("metabase_configured") is True
    assert env_info.get("spira_configured") is True


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------


def test_analyze_returns_proposal(client):
    """POST /analyze with valid log_entry must return 200 with trace_id."""
    c, _ = client
    mock_analyst = MagicMock()
    mock_analyst.analyze_log.return_value = MOCK_ANALYSIS.copy()
    with patch("src.interface.api._get_analyst", return_value=mock_analyst):
        resp = c.post("/analyze", json={"log_entry": "ERROR timeout on sensor"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "trace_id" in data, f"Expected 'trace_id' in response: {data}"


def test_analyze_rejects_empty_log(client):
    """POST /analyze with empty log_entry must return 400."""
    c, _ = client
    resp = c.post("/analyze", json={"log_entry": ""})
    assert resp.status_code == 400, f"Expected 400 for empty log_entry, got {resp.status_code}"


def test_analyze_stores_pending_proposal(client):
    """After POST /analyze, the trace_id must be approvable."""
    c, audit_db = client
    mock_analyst = MagicMock()
    analysis = MOCK_ANALYSIS.copy()
    analysis["trace_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    mock_analyst.analyze_log.return_value = analysis
    with patch("src.interface.api._get_analyst", return_value=mock_analyst):
        resp = c.post("/analyze", json={"log_entry": "ERROR: uart overflow"})
    assert resp.status_code == 200
    trace_id = resp.json()["trace_id"]
    # Now approve it
    resp2 = c.post(f"/approve/{trace_id}")
    assert resp2.status_code == 200, f"Expected 200 on approve, got {resp2.status_code}: {resp2.text}"


# ---------------------------------------------------------------------------
# POST /approve/{trace_id}
# ---------------------------------------------------------------------------


def test_approve_valid_trace_id(client):
    """Approve a pending proposal — must return 200 with 'approved' status."""
    c, _ = client
    mock_analyst = MagicMock()
    analysis = MOCK_ANALYSIS.copy()
    analysis["trace_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-ffffffffffff"
    mock_analyst.analyze_log.return_value = analysis
    with patch("src.interface.api._get_analyst", return_value=mock_analyst):
        resp = c.post("/analyze", json={"log_entry": "ERROR: test"})
    trace_id = resp.json()["trace_id"]
    resp2 = c.post(f"/approve/{trace_id}")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data.get("status") == "approved"
    assert data.get("trace_id") == trace_id


def test_approve_invalid_trace_id(client):
    """Approving a non-existent trace_id must return 404."""
    c, _ = client
    resp = c.post("/approve/nonexistent-trace-id-does-not-exist")
    assert resp.status_code == 404, f"Expected 404 for unknown trace_id, got {resp.status_code}"


def test_approve_creates_audit_record(client):
    """After approval, an APPROVAL record must appear in the audit log."""
    c, audit_db = client
    mock_analyst = MagicMock()
    analysis = MOCK_ANALYSIS.copy()
    analysis["trace_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-111111111111"
    mock_analyst.analyze_log.return_value = analysis
    with patch("src.interface.api._get_analyst", return_value=mock_analyst):
        resp = c.post("/analyze", json={"log_entry": "ERROR: test"})
    trace_id = resp.json()["trace_id"]
    c.post(f"/approve/{trace_id}")
    # Query audit log
    conn = sqlite3.connect(audit_db.db_path)
    rows = conn.execute(
        "SELECT * FROM compliance_audit_log WHERE action_type = 'APPROVAL'"
    ).fetchall()
    conn.close()
    assert len(rows) >= 1, "Expected at least one APPROVAL record in the audit log."


def test_approve_removes_from_pending(client):
    """After approval, trying to approve the same trace_id again must return 404."""
    c, _ = client
    mock_analyst = MagicMock()
    analysis = MOCK_ANALYSIS.copy()
    analysis["trace_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-222222222222"
    mock_analyst.analyze_log.return_value = analysis
    with patch("src.interface.api._get_analyst", return_value=mock_analyst):
        resp = c.post("/analyze", json={"log_entry": "ERROR: once only"})
    trace_id = resp.json()["trace_id"]
    c.post(f"/approve/{trace_id}")
    # Second approval must fail
    resp2 = c.post(f"/approve/{trace_id}")
    assert resp2.status_code == 404, f"Expected 404 on second approve, got {resp2.status_code}"


# ---------------------------------------------------------------------------
# POST /reject/{trace_id}
# ---------------------------------------------------------------------------


def test_reject_valid_trace_id(client):
    """Reject a pending proposal with feedback — must return 200."""
    c, _ = client
    mock_analyst = MagicMock()
    analysis = MOCK_ANALYSIS.copy()
    analysis["trace_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-333333333333"
    mock_analyst.analyze_log.return_value = analysis
    mock_analyst.learn_from_feedback = MagicMock()
    with patch("src.interface.api._get_analyst", return_value=mock_analyst):
        resp = c.post("/analyze", json={"log_entry": "ERROR: test reject"})
    trace_id = resp.json()["trace_id"]
    with patch("src.interface.api._get_analyst", return_value=mock_analyst):
        resp2 = c.post(f"/reject/{trace_id}", json={"feedback": "Real cause is hardware fault."})
    assert resp2.status_code == 200, f"Expected 200 on reject, got {resp2.status_code}: {resp2.text}"
    data = resp2.json()
    assert data.get("status") == "rejected"


def test_reject_invalid_trace_id(client):
    """Rejecting a non-existent trace_id must return 404."""
    c, _ = client
    resp = c.post("/reject/nonexistent-trace-id", json={"feedback": "some feedback"})
    assert resp.status_code == 404


def test_reject_triggers_learning(client):
    """After rejection, analyst.learn_from_feedback must be called with the feedback text."""
    c, _ = client
    mock_analyst = MagicMock()
    analysis = MOCK_ANALYSIS.copy()
    analysis["trace_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-444444444444"
    mock_analyst.analyze_log.return_value = analysis
    mock_analyst.learn_from_feedback = MagicMock()
    with patch("src.interface.api._get_analyst", return_value=mock_analyst):
        resp = c.post("/analyze", json={"log_entry": "ERROR: should learn"})
    trace_id = resp.json()["trace_id"]
    feedback_text = "The actual root cause was a hardware short circuit."
    with patch("src.interface.api._get_analyst", return_value=mock_analyst):
        c.post(f"/reject/{trace_id}", json={"feedback": feedback_text})
    assert mock_analyst.learn_from_feedback.called, "learn_from_feedback() must be called on rejection."
    call_kwargs = mock_analyst.learn_from_feedback.call_args
    assert feedback_text in str(call_kwargs), (
        f"Feedback text must be passed to learn_from_feedback(). Call args: {call_kwargs}"
    )


# ---------------------------------------------------------------------------
# GET /audit
# ---------------------------------------------------------------------------


def test_audit_returns_entries(client):
    """GET /audit must return a response with 'entries' list."""
    c, audit_db = client
    audit_db.log_event("TestActor", "TEST_ACTION", "input", "output")
    resp = c.get("/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data, f"Expected 'entries' in audit response: {data}"
    assert len(data["entries"]) >= 1, "Audit log must have at least 1 entry."


def test_audit_pagination(client):
    """GET /audit with limit and offset params must work correctly."""
    c, audit_db = client
    for i in range(5):
        audit_db.log_event("TestActor", f"ACTION_{i}", f"input {i}", f"output {i}")
    # Request 2 with offset 0
    resp = c.get("/audit?limit=2&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["entries"]) <= 2, f"Expected at most 2 entries with limit=2, got {len(data['entries'])}"
    # Request 2 with offset 2
    resp2 = c.get("/audit?limit=2&offset=2")
    assert resp2.status_code == 200
    data2 = resp2.json()
    # Results at different offsets must be different records
    if data["entries"] and data2["entries"]:
        ids1 = {r["id"] for r in data["entries"]}
        ids2 = {r["id"] for r in data2["entries"]}
        assert ids1 != ids2, "Paginated results must differ."


def test_audit_max_limit_500(client):
    """GET /audit with limit=9999 must cap at 500 records returned."""
    c, audit_db = client
    resp = c.get("/audit?limit=9999")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("limit") == 500, f"Expected limit capped at 500, got {data.get('limit')}"


# ---------------------------------------------------------------------------
# POST /mr/create
# ---------------------------------------------------------------------------


def test_mr_create_valid_request(client):
    """POST /mr/create with valid body must return 200."""
    c, _ = client
    mock_dev = MagicMock()
    mock_dev.create_mr_from_issue.return_value = MOCK_MR_CREATED.copy()
    with patch("src.interface.api._get_developer", return_value=mock_dev):
        resp = c.post("/mr/create", json={"project_id": 123, "issue_iid": 45})
    assert resp.status_code == 200, f"Expected 200 for valid MR create, got {resp.status_code}: {resp.text}"


def test_mr_create_missing_fields(client):
    """POST /mr/create without project_id must return 422 (validation error)."""
    c, _ = client
    resp = c.post("/mr/create", json={"issue_iid": 45})
    assert resp.status_code == 422, f"Expected 422 for missing project_id, got {resp.status_code}"


def test_mr_create_propagates_error(client):
    """When developer agent returns error, POST /mr/create must return 500."""
    c, _ = client
    mock_dev = MagicMock()
    mock_dev.create_mr_from_issue.return_value = {"error": "GitLab unreachable"}
    with patch("src.interface.api._get_developer", return_value=mock_dev):
        resp = c.post("/mr/create", json={"project_id": 123, "issue_iid": 45})
    assert resp.status_code == 500, f"Expected 500 for agent error, got {resp.status_code}"


# ---------------------------------------------------------------------------
# POST /mr/review
# ---------------------------------------------------------------------------


def test_mr_review_valid_request(client):
    """POST /mr/review with valid body must return 200."""
    c, _ = client
    mock_dev = MagicMock()
    mock_dev.review_merge_request.return_value = MOCK_REVIEW.copy()
    with patch("src.interface.api._get_developer", return_value=mock_dev):
        resp = c.post("/mr/review", json={"project_id": 123, "mr_iid": 7})
    assert resp.status_code == 200, f"Expected 200 for valid MR review, got {resp.status_code}: {resp.text}"


def test_mr_review_returns_approved_flag(client):
    """POST /mr/review response must include 'approved' field."""
    c, _ = client
    mock_dev = MagicMock()
    review = MOCK_REVIEW.copy()
    review["approved"] = True
    mock_dev.review_merge_request.return_value = review
    with patch("src.interface.api._get_developer", return_value=mock_dev):
        resp = c.post("/mr/review", json={"project_id": 123, "mr_iid": 7})
    data = resp.json()
    assert "approved" in data, f"Expected 'approved' in review response: {data}"
    assert data["approved"] is True


# ---------------------------------------------------------------------------
# GET /monitor/status
# ---------------------------------------------------------------------------


def test_monitor_status_returns_dict(client):
    """GET /monitor/status must return 200 with a dict response."""
    c, _ = client
    mock_monitor = MagicMock()
    mock_monitor.get_status.return_value = {
        "running": False,
        "active_threads": [],
        "thread_count": 0,
        "seen_messages": 0,
        "seen_issues": 0,
    }
    with patch("src.interface.api._get_monitor", return_value=mock_monitor):
        resp = c.get("/monitor/status")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict), "Monitor status response must be a dict."
    assert "running" in data, "Monitor status must contain 'running' key."


# ---------------------------------------------------------------------------
# POST /webhook/teams
# ---------------------------------------------------------------------------


def test_teams_webhook_accepts_json(client):
    """POST /webhook/teams with valid JSON body must return 200."""
    c, _ = client
    payload = {"type": "message", "text": "ERROR sensor failure detected", "from": "AlertBot"}
    resp = c.post("/webhook/teams", json=payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


def test_teams_webhook_creates_audit_record(client):
    """POST /webhook/teams must create a WEBHOOK_RECEIVED audit record."""
    c, audit_db = client
    payload = {"type": "message", "text": "test webhook"}
    resp = c.post("/webhook/teams", json=payload)
    assert resp.status_code == 200
    conn = sqlite3.connect(audit_db.db_path)
    rows = conn.execute(
        "SELECT * FROM compliance_audit_log WHERE action_type = 'WEBHOOK_RECEIVED'"
    ).fetchall()
    conn.close()
    assert len(rows) >= 1, "Expected at least 1 WEBHOOK_RECEIVED record in the audit log."


def test_teams_webhook_rejects_invalid_json(client):
    """POST /webhook/teams with malformed body must return 400 or 422."""
    c, _ = client
    # Send raw bytes that are not valid JSON
    resp = c.post(
        "/webhook/teams",
        content=b"this is not json {{{",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code in (400, 422), (
        f"Expected 400 or 422 for invalid JSON, got {resp.status_code}"
    )

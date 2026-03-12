"""
SAGE[ai] - End-to-End tests for MR creation and review workflow

Tests the full API pipeline for merge request operations with mocked
GitLab HTTP calls and mocked LLM.
"""

import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.e2e


MR_DRAFT_JSON = json.dumps({
    "mr_title": "Fix: UART RX buffer too small",
    "mr_description": "Resolves #45\n\nIncreases buffer from 256 to 512 bytes.",
})

REVIEW_JSON = json.dumps({
    "summary": "Safe to merge — buffer size fix is correct.",
    "issues": [],
    "suggestions": ["Add test for overflow scenario."],
    "approved": True,
})

MOCK_ISSUE = {
    "id": 2001, "iid": 45,
    "title": "UART RX buffer too small",
    "description": "Device crashes when receiving >256 bytes on UART1.",
    "labels": ["bug", "sage-ai"],
}

MOCK_PROJECT = {
    "id": 123, "name": "FirmwareProject", "default_branch": "main",
}

MOCK_MR_CREATED = {
    "id": 3001, "iid": 8,
    "title": "Fix: UART RX buffer too small",
    "web_url": "https://gitlab.example.com/project/-/merge_requests/8",
    "source_branch": "sage-ai/45-uart-rx-buffer-too-small",
    "target_branch": "main",
}

MOCK_MR = {
    "id": 1001, "iid": 7,
    "title": "Fix UART buffer overflow",
    "description": "Increases UART1 RX buffer.",
    "source_branch": "sage-ai/7-fix-uart",
    "target_branch": "main",
    "author": {"name": "Jane Dev"},
    "web_url": "https://gitlab.example.com/project/-/merge_requests/7",
    "pipeline": {"id": 555, "status": "passed"},
}

MOCK_DIFFS = [
    {"old_path": "src/uart.c", "new_path": "src/uart.c",
     "diff": "@@ -10 +10 @@\n-256\n+512\n"},
]

MOCK_NOTE = {"id": 9001, "body": "SAGE[ai] review comment"}


def _query_audit(db_path, action_type):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT * FROM compliance_audit_log WHERE action_type = ?", (action_type,)
    ).fetchall()
    conn.close()
    return rows


def _make_response(status_code=200, json_data=None, raise_exc=None):
    resp = MagicMock()
    resp.status_code = status_code
    if raise_exc:
        resp.raise_for_status.side_effect = raise_exc
    else:
        resp.raise_for_status = MagicMock()
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


@pytest.fixture
def e2e_client(tmp_audit_db):
    """E2E TestClient with real AuditLogger and mocked LLM."""
    from src.interface import api
    api._pending_proposals.clear()

    with patch("src.interface.api._get_audit_logger", return_value=tmp_audit_db), \
         patch("src.agents.developer.developer_agent") as _, \
         patch("src.core.llm_gateway.LLMGateway.generate") as mock_llm:
        mock_llm.return_value = REVIEW_JSON

        from src.interface.api import app
        with TestClient(app) as client:
            yield client, tmp_audit_db, mock_llm

    api._pending_proposals.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_mr_from_issue_full_flow(e2e_client, tmp_audit_db):
    """
    POST /mr/create → verify MR created → verify MR_CREATED in audit log → verify trace_id returned.
    """
    client, audit_db, mock_llm = e2e_client
    mock_llm.return_value = MR_DRAFT_JSON

    issue_resp = _make_response(200, MOCK_ISSUE)
    project_resp = _make_response(200, MOCK_PROJECT)
    mr_resp = _make_response(201, MOCK_MR_CREATED)

    def get_side_effect(url, **kwargs):
        if "/issues/" in url:
            return issue_resp
        return project_resp

    with patch("requests.get", side_effect=get_side_effect), \
         patch("requests.post", return_value=mr_resp), \
         patch("src.interface.api._get_developer") as mock_get_dev:
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = audit_db
        agent.gitlab_url = "https://gitlab.example.com"
        agent._api_base = "https://gitlab.example.com/api/v4"
        mock_get_dev.return_value = agent

        resp = client.post("/mr/create", json={"project_id": 123, "issue_iid": 45})

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "trace_id" in data, f"Expected trace_id in response: {data}"
    assert "mr_url" in data, f"Expected mr_url in response: {data}"

    rows = _query_audit(audit_db.db_path, "MR_CREATED")
    assert len(rows) >= 1, "Expected MR_CREATED record in audit log."


def test_review_mr_posts_comment_flow(e2e_client, tmp_audit_db):
    """
    POST /mr/review → mock approve → mock add_mr_comment → verify MR_REVIEW + MR_COMMENT_ADDED in audit log.
    """
    client, audit_db, mock_llm = e2e_client
    mock_llm.return_value = REVIEW_JSON

    mr_resp = _make_response(200, MOCK_MR)
    diff_resp = _make_response(200, MOCK_DIFFS)
    note_resp = _make_response(201, MOCK_NOTE)

    def get_side_effect(url, **kwargs):
        if "/diffs" in url:
            return diff_resp
        return mr_resp

    with patch("requests.get", side_effect=get_side_effect), \
         patch("requests.post", return_value=note_resp), \
         patch("src.interface.api._get_developer") as mock_get_dev:
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = audit_db
        agent.gitlab_url = "https://gitlab.example.com"
        agent._api_base = "https://gitlab.example.com/api/v4"
        mock_get_dev.return_value = agent

        # Review the MR
        resp = client.post("/mr/review", json={"project_id": 123, "mr_iid": 7})

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    # Post a comment as follow-up
    with patch("requests.post", return_value=note_resp), \
         patch("src.interface.api._get_developer") as mock_get_dev2:
        agent2 = DeveloperAgent()
        agent2._audit_logger = audit_db
        agent2.gitlab_url = "https://gitlab.example.com"
        agent2._api_base = "https://gitlab.example.com/api/v4"
        mock_get_dev2.return_value = agent2
        agent2.add_mr_comment(project_id=123, mr_iid=7, comment="SAGE[ai] review: Approved for merge.")

    mr_reviews = _query_audit(audit_db.db_path, "MR_REVIEW")
    mr_comments = _query_audit(audit_db.db_path, "MR_COMMENT_ADDED")
    assert len(mr_reviews) >= 1, "Expected MR_REVIEW record in audit log."
    assert len(mr_comments) >= 1, "Expected MR_COMMENT_ADDED record in audit log."


def test_mr_create_failure_logged(e2e_client, tmp_audit_db):
    """
    When GitLab returns 403 on MR creation → MR_CREATE_FAILED in audit log → 500 from API.
    """
    import requests as req_module
    client, audit_db, mock_llm = e2e_client
    mock_llm.return_value = MR_DRAFT_JSON

    issue_resp = _make_response(200, MOCK_ISSUE)
    project_resp = _make_response(200, MOCK_PROJECT)
    forbidden_resp = _make_response(403, raise_exc=req_module.HTTPError("403 Forbidden"))

    def get_side_effect(url, **kwargs):
        if "/issues/" in url:
            return issue_resp
        return project_resp

    with patch("requests.get", side_effect=get_side_effect), \
         patch("requests.post", return_value=forbidden_resp), \
         patch("src.interface.api._get_developer") as mock_get_dev:
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = audit_db
        agent.gitlab_url = "https://gitlab.example.com"
        agent._api_base = "https://gitlab.example.com/api/v4"
        mock_get_dev.return_value = agent

        resp = client.post("/mr/create", json={"project_id": 123, "issue_iid": 45})

    assert resp.status_code == 500, f"Expected 500 on GitLab 403, got {resp.status_code}"

    rows = _query_audit(audit_db.db_path, "MR_CREATE_FAILED")
    assert len(rows) >= 1, "Expected MR_CREATE_FAILED record in audit log."

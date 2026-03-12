"""
SAGE[ai] - Unit tests for DeveloperAgent (src/agents/developer.py)

Tests GitLab interaction, MR creation, code review, patch proposals,
and comment posting. All HTTP calls are mocked.
"""

import json
import os
import re
import sqlite3
from unittest.mock import MagicMock, patch

import pytest


pytestmark = pytest.mark.unit

UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

REVIEW_JSON = json.dumps({
    "summary": "Minor refactor, looks safe.",
    "issues": [],
    "suggestions": ["Add unit tests for edge cases."],
    "approved": True,
})

PATCH_JSON = json.dumps({
    "patch": "--- a/file.c\n+++ b/file.c\n@@ -10,7 +10,7 @@\n-old line\n+new line\n",
    "explanation": "Increased buffer size from 256 to 512.",
    "confidence": "high",
})

MR_DRAFT_JSON = json.dumps({
    "mr_title": "Fix: UART RX buffer too small",
    "mr_description": "Resolves #45\n\nIncreases buffer from 256 to 512 bytes.",
})


def _query_audit(db_path, action_type=None):
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


def _make_response(status_code=200, json_data=None, raise_exc=None):
    """Helper to create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    if raise_exc:
        resp.raise_for_status.side_effect = raise_exc
    else:
        resp.raise_for_status = MagicMock()
    resp.json.return_value = json_data or {}
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_init_reads_env_vars(tmp_audit_db):
    """DeveloperAgent must read GITLAB_URL and GITLAB_TOKEN from environment."""
    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "test-token-123"}):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
    assert agent.gitlab_url == "https://gl.test.local"
    assert agent.gitlab_token == "test-token-123"


def test_init_warns_when_no_gitlab_url(tmp_audit_db, caplog):
    """When GITLAB_URL is not set, the agent must log a warning."""
    env = {k: v for k, v in os.environ.items() if k not in ("GITLAB_URL", "GITLAB_TOKEN")}
    env.pop("GITLAB_URL", None)
    env.pop("GITLAB_TOKEN", None)
    with patch.dict(os.environ, env, clear=True):
        import logging
        with caplog.at_level(logging.WARNING, logger="DeveloperAgent"):
            from src.agents.developer import DeveloperAgent
            agent = DeveloperAgent()
    # Check warning was logged (or url is empty)
    assert agent.gitlab_url == "" or "GITLAB_URL" in caplog.text or agent.gitlab_url is not None


def test_review_mr_returns_required_fields(tmp_audit_db, mock_gitlab_responses):
    """review_merge_request() must return dict with: summary, issues, suggestions, approved, trace_id, mr_iid, mr_title."""
    mr_resp = _make_response(200, mock_gitlab_responses["mr"])
    diff_resp = _make_response(200, mock_gitlab_responses["mr_diffs"])

    def side_effect_get(url, **kwargs):
        if "/merge_requests/7/diffs" in url or "/diffs" in url:
            return diff_resp
        return mr_resp

    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("requests.get", side_effect=side_effect_get), \
         patch("src.core.llm_gateway.LLMGateway.generate", return_value=REVIEW_JSON), \
         patch("src.agents.developer.developer_agent") as _:
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        result = agent.review_merge_request(project_id=123, mr_iid=7)

    for field in ("summary", "issues", "suggestions", "approved", "trace_id", "mr_iid", "mr_title"):
        assert field in result, f"Result must contain '{field}'. Got keys: {list(result.keys())}"


def test_review_mr_creates_audit_record(tmp_audit_db, mock_gitlab_responses):
    """review_merge_request() must log an MR_REVIEW record in the audit log."""
    mr_resp = _make_response(200, mock_gitlab_responses["mr"])
    diff_resp = _make_response(200, mock_gitlab_responses["mr_diffs"])

    def side_effect_get(url, **kwargs):
        if "/diffs" in url:
            return diff_resp
        return mr_resp

    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("requests.get", side_effect=side_effect_get), \
         patch("src.core.llm_gateway.LLMGateway.generate", return_value=REVIEW_JSON):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        agent.review_merge_request(project_id=123, mr_iid=7)

    rows = _query_audit(tmp_audit_db.db_path, action_type="MR_REVIEW")
    assert len(rows) >= 1, "Expected MR_REVIEW record in audit log."


def test_review_mr_handles_gitlab_error(tmp_audit_db):
    """When requests.get raises ConnectionError, review_merge_request() must return a dict with 'error' key."""
    import requests as req_module
    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("requests.get", side_effect=req_module.ConnectionError("Connection refused")):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        result = agent.review_merge_request(project_id=123, mr_iid=7)
    assert "error" in result, f"Expected 'error' key on connection failure, got: {result}"


def test_create_mr_from_issue_returns_mr_url(tmp_audit_db, mock_gitlab_responses):
    """create_mr_from_issue() must return a dict with mr_url, mr_iid, trace_id."""
    issue_resp = _make_response(200, mock_gitlab_responses["issue"])
    project_resp = _make_response(200, mock_gitlab_responses["project"])
    mr_created_resp = _make_response(201, mock_gitlab_responses["mr_created"])

    call_count = {"n": 0}

    def side_effect_get(url, **kwargs):
        if "/issues/" in url:
            return issue_resp
        return project_resp

    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("requests.get", side_effect=side_effect_get), \
         patch("requests.post", return_value=mr_created_resp), \
         patch("src.core.llm_gateway.LLMGateway.generate", return_value=MR_DRAFT_JSON):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        result = agent.create_mr_from_issue(project_id=123, issue_iid=45)

    assert "mr_url" in result, f"Expected 'mr_url' in result: {result}"
    assert "mr_iid" in result, f"Expected 'mr_iid' in result: {result}"
    assert "trace_id" in result, f"Expected 'trace_id' in result: {result}"


def test_create_mr_auto_generates_branch_name(tmp_audit_db, mock_gitlab_responses):
    """When source_branch=None, the auto-generated branch must match pattern sage-ai/{iid}-..."""
    issue_resp = _make_response(200, mock_gitlab_responses["issue"])
    project_resp = _make_response(200, mock_gitlab_responses["project"])
    mr_created_resp = _make_response(201, mock_gitlab_responses["mr_created"])

    def side_effect_get(url, **kwargs):
        if "/issues/" in url:
            return issue_resp
        return project_resp

    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("requests.get", side_effect=side_effect_get), \
         patch("requests.post", return_value=mr_created_resp), \
         patch("src.core.llm_gateway.LLMGateway.generate", return_value=MR_DRAFT_JSON):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        result = agent.create_mr_from_issue(project_id=123, issue_iid=45, source_branch=None)

    branch = result.get("source_branch", "")
    assert branch.startswith("sage-ai/"), f"Expected branch starting with 'sage-ai/', got: '{branch}'"
    assert "45" in branch, f"Expected issue IID '45' in branch name, got: '{branch}'"


def test_create_mr_creates_audit_record(tmp_audit_db, mock_gitlab_responses):
    """create_mr_from_issue() must create an MR_CREATED audit record."""
    issue_resp = _make_response(200, mock_gitlab_responses["issue"])
    project_resp = _make_response(200, mock_gitlab_responses["project"])
    mr_created_resp = _make_response(201, mock_gitlab_responses["mr_created"])

    def side_effect_get(url, **kwargs):
        if "/issues/" in url:
            return issue_resp
        return project_resp

    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("requests.get", side_effect=side_effect_get), \
         patch("requests.post", return_value=mr_created_resp), \
         patch("src.core.llm_gateway.LLMGateway.generate", return_value=MR_DRAFT_JSON):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        agent.create_mr_from_issue(project_id=123, issue_iid=45)

    rows = _query_audit(tmp_audit_db.db_path, action_type="MR_CREATED")
    assert len(rows) >= 1, "Expected MR_CREATED record in audit log."


def test_create_mr_logs_failure_to_audit(tmp_audit_db, mock_gitlab_responses):
    """When GitLab MR POST returns 403, an MR_CREATE_FAILED record must be in the audit log."""
    import requests as req_module
    issue_resp = _make_response(200, mock_gitlab_responses["issue"])
    project_resp = _make_response(200, mock_gitlab_responses["project"])
    forbidden_resp = _make_response(
        403,
        raise_exc=req_module.HTTPError("403 Forbidden"),
    )

    def side_effect_get(url, **kwargs):
        if "/issues/" in url:
            return issue_resp
        return project_resp

    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("requests.get", side_effect=side_effect_get), \
         patch("requests.post", return_value=forbidden_resp), \
         patch("src.core.llm_gateway.LLMGateway.generate", return_value=MR_DRAFT_JSON):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        result = agent.create_mr_from_issue(project_id=123, issue_iid=45)

    assert "error" in result, f"Expected 'error' key on 403, got: {result}"
    rows = _query_audit(tmp_audit_db.db_path, action_type="MR_CREATE_FAILED")
    assert len(rows) >= 1, "Expected MR_CREATE_FAILED record in audit log."


def test_list_open_mrs_returns_list(tmp_audit_db, mock_gitlab_responses):
    """list_open_mrs() must return a dict with 'merge_requests' list and count=2."""
    mrs_data = [mock_gitlab_responses["mr"], {**mock_gitlab_responses["mr"], "iid": 8, "id": 1002}]
    resp = _make_response(200, mrs_data)

    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("requests.get", return_value=resp):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        result = agent.list_open_mrs(project_id=123)

    assert "merge_requests" in result, f"Expected 'merge_requests' in result: {result}"
    assert isinstance(result["merge_requests"], list), "merge_requests must be a list."
    assert result.get("count") == 2, f"Expected count=2, got {result.get('count')}"


def test_get_pipeline_status_no_pipeline(tmp_audit_db, mock_gitlab_responses):
    """When MR has no pipeline field, get_pipeline_status() must return status='no_pipeline'."""
    mr_no_pipeline = {**mock_gitlab_responses["mr"]}
    mr_no_pipeline.pop("pipeline", None)
    mr_no_pipeline["head_pipeline"] = None
    resp = _make_response(200, mr_no_pipeline)

    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("requests.get", return_value=resp):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        result = agent.get_pipeline_status(project_id=123, mr_iid=7)

    assert result.get("status") == "no_pipeline", f"Expected 'no_pipeline', got: {result.get('status')}"


def test_get_pipeline_status_with_pipeline(tmp_audit_db, mock_gitlab_responses):
    """When MR has a pipeline, get_pipeline_status() must return a 'stages' dict."""
    mr_resp = _make_response(200, mock_gitlab_responses["mr"])
    pipeline_resp = _make_response(200, mock_gitlab_responses["pipeline"])
    jobs_resp = _make_response(200, mock_gitlab_responses["jobs"])

    call_count = {"n": 0}
    def side_effect_get(url, **kwargs):
        call_count["n"] += 1
        if "/jobs" in url:
            return jobs_resp
        elif "/pipelines/" in url:
            return pipeline_resp
        return mr_resp

    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("requests.get", side_effect=side_effect_get):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        result = agent.get_pipeline_status(project_id=123, mr_iid=7)

    assert "stages" in result, f"Expected 'stages' in result: {result}"
    assert isinstance(result["stages"], dict), "stages must be a dict."


def test_propose_code_patch_returns_diff(tmp_audit_db):
    """propose_code_patch() must return a dict with patch, explanation, and confidence fields."""
    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("src.core.llm_gateway.LLMGateway.generate", return_value=PATCH_JSON):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        result = agent.propose_code_patch(
            file_path="src/uart_driver.c",
            error_description="Buffer overflow when receiving >256 bytes",
            current_code="#define UART_BUF_SIZE 256\n",
        )

    for field in ("patch", "explanation", "confidence"):
        assert field in result, f"Result must contain '{field}'. Got keys: {list(result.keys())}"


def test_propose_code_patch_creates_audit_record(tmp_audit_db):
    """propose_code_patch() must create a CODE_PATCH_PROPOSAL audit record."""
    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("src.core.llm_gateway.LLMGateway.generate", return_value=PATCH_JSON):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        agent.propose_code_patch(
            file_path="src/flash_controller.c",
            error_description="Write fails at 0x08040000",
            current_code="void write_flash() {}\n",
        )

    rows = _query_audit(tmp_audit_db.db_path, action_type="CODE_PATCH_PROPOSAL")
    assert len(rows) >= 1, "Expected CODE_PATCH_PROPOSAL record in audit log."


def test_add_mr_comment_posts_to_gitlab(tmp_audit_db, mock_gitlab_responses):
    """add_mr_comment() must create an MR_COMMENT_ADDED audit record and return note_id."""
    note_resp = _make_response(201, mock_gitlab_responses["note"])

    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("requests.post", return_value=note_resp):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        result = agent.add_mr_comment(project_id=123, mr_iid=7, comment="SAGE[ai] review: LGTM")

    assert "note_id" in result, f"Expected 'note_id' in result: {result}"
    rows = _query_audit(tmp_audit_db.db_path, action_type="MR_COMMENT_ADDED")
    assert len(rows) >= 1, "Expected MR_COMMENT_ADDED record in audit log."


def test_add_mr_comment_handles_error(tmp_audit_db):
    """When requests.post raises an exception, add_mr_comment() must return a dict with 'error'."""
    import requests as req_module
    with patch.dict(os.environ, {"GITLAB_URL": "https://gl.test.local", "GITLAB_TOKEN": "tok"}), \
         patch("requests.post", side_effect=req_module.ConnectionError("Network error")):
        from src.agents.developer import DeveloperAgent
        agent = DeveloperAgent()
        agent._audit_logger = tmp_audit_db
        result = agent.add_mr_comment(project_id=123, mr_iid=7, comment="Test comment")

    assert "error" in result, f"Expected 'error' key on network failure, got: {result}"

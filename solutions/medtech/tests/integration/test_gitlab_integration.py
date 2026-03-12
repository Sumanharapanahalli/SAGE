"""
SAGE[ai] - GitLab Integration Tests

These tests connect to a REAL GitLab instance.
All tests are skipped if GITLAB_URL and GITLAB_TOKEN are not set.

Requires environment variables:
  GITLAB_URL       — e.g. https://gitlab.example.com
  GITLAB_TOKEN     — Personal access token with api scope
  GITLAB_PROJECT_ID — Numeric project ID to test against
  GITLAB_TEST_MR_IID — (optional) MR IID to use for pipeline/review tests
"""

import os

import pytest


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def require_gitlab():
    """Skip all tests in this module if GitLab credentials are not configured."""
    if not os.environ.get("GITLAB_URL") or not os.environ.get("GITLAB_TOKEN"):
        pytest.skip("GITLAB_URL and GITLAB_TOKEN not configured — skipping GitLab integration tests.")


@pytest.fixture(autouse=True)
def require_project_id():
    """Skip tests requiring a specific project if GITLAB_PROJECT_ID not set."""
    if not os.environ.get("GITLAB_PROJECT_ID"):
        pytest.skip("GITLAB_PROJECT_ID not configured — skipping GitLab project integration tests.")


def test_gitlab_connection():
    """Verify GitLab API is reachable and credentials are valid by listing projects."""
    from src.agents.developer import DeveloperAgent
    agent = DeveloperAgent()
    data, err = agent._gl_get("/projects", params={"membership": True, "per_page": 1})
    assert err is None, f"GitLab connection failed: {err}"
    assert data is not None, "Expected non-None response from GitLab /projects."
    assert isinstance(data, list), f"Expected list of projects, got: {type(data)}"


def test_list_open_mrs_live():
    """List open MRs for the configured project — verify response structure."""
    from src.agents.developer import DeveloperAgent
    agent = DeveloperAgent()
    project_id = int(os.environ["GITLAB_PROJECT_ID"])
    result = agent.list_open_mrs(project_id=project_id)
    assert "error" not in result, f"list_open_mrs() returned error: {result.get('error')}"
    assert "merge_requests" in result, f"Expected 'merge_requests' in result: {result}"
    assert "count" in result, "Expected 'count' in result."
    assert isinstance(result["merge_requests"], list)
    # If there are MRs, verify structure
    if result["count"] > 0:
        mr = result["merge_requests"][0]
        for field in ("iid", "title", "source_branch", "target_branch"):
            assert field in mr, f"Expected '{field}' in MR dict: {mr}"


def test_get_pipeline_status_live():
    """Get pipeline status for a real MR — skip if GITLAB_TEST_MR_IID not set."""
    mr_iid = os.environ.get("GITLAB_TEST_MR_IID")
    if not mr_iid:
        pytest.skip("GITLAB_TEST_MR_IID not set — skipping pipeline status test.")
    from src.agents.developer import DeveloperAgent
    agent = DeveloperAgent()
    project_id = int(os.environ["GITLAB_PROJECT_ID"])
    result = agent.get_pipeline_status(project_id=project_id, mr_iid=int(mr_iid))
    assert "error" not in result, f"get_pipeline_status() returned error: {result.get('error')}"
    assert "status" in result, f"Expected 'status' in result: {result}"
    # status values: no_pipeline, pending, running, passed, failed, canceled
    assert result["status"] in ("no_pipeline", "pending", "running", "passed", "failed", "canceled", "success", "unknown"), (
        f"Unexpected pipeline status: {result['status']}"
    )


def test_review_mr_produces_valid_output():
    """Review a real MR and verify all required JSON fields are present."""
    mr_iid = os.environ.get("GITLAB_TEST_MR_IID")
    if not mr_iid:
        pytest.skip("GITLAB_TEST_MR_IID not set — skipping live MR review test.")
    from src.agents.developer import DeveloperAgent
    agent = DeveloperAgent()
    project_id = int(os.environ["GITLAB_PROJECT_ID"])
    result = agent.review_merge_request(project_id=project_id, mr_iid=int(mr_iid))
    assert "error" not in result, f"review_merge_request() returned error: {result.get('error')}"
    for field in ("summary", "issues", "suggestions", "approved", "trace_id", "mr_iid", "mr_title"):
        assert field in result, f"Expected '{field}' in review result: {list(result.keys())}"

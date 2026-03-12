"""
SAGE[ai] - Metabase Integration Tests

These tests connect to a REAL Metabase instance.
All tests are skipped if Metabase credentials are not configured.

Requires environment variables:
  METABASE_URL      — e.g. https://metabase.example.com
  METABASE_USERNAME — Metabase login email
  METABASE_PASSWORD — Metabase login password
  METABASE_ERROR_QUESTION_ID — (optional) Question ID for error query tests
"""

import os

import pytest


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def require_metabase_credentials():
    """Skip all tests if Metabase credentials are not configured."""
    required = ["METABASE_URL", "METABASE_USERNAME", "METABASE_PASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        pytest.skip(f"Metabase credentials not configured (missing: {', '.join(missing)}) — skipping Metabase integration tests.")


def test_metabase_authentication():
    """Verify Metabase authentication works with configured credentials."""
    from mcp_servers.metabase_server import get_session_token
    result = get_session_token()
    assert result.get("token_obtained") is True, (
        f"Metabase authentication failed: {result.get('error')}"
    )
    assert "cached_until" in result, "Expected 'cached_until' in auth result."


def test_list_dashboards_live():
    """List all Metabase dashboards — verify response structure."""
    from mcp_servers.metabase_server import list_dashboards
    result = list_dashboards()
    assert "error" not in result, f"list_dashboards() returned error: {result.get('error')}"
    assert "dashboards" in result, f"Expected 'dashboards' in result: {result}"
    assert isinstance(result["dashboards"], list)


def test_get_question_results_live():
    """Query the error question and verify data structure."""
    question_id = os.environ.get("METABASE_ERROR_QUESTION_ID")
    if not question_id:
        pytest.skip("METABASE_ERROR_QUESTION_ID not set — skipping question results test.")
    from mcp_servers.metabase_server import get_question_results
    result = get_question_results(question_id=int(question_id))
    assert "error" not in result, f"get_question_results() returned error: {result.get('error')}"
    assert "row_count" in result, f"Expected 'row_count' in result: {result}"
    assert "rows" in result, f"Expected 'rows' in result: {result}"


def test_get_new_errors_live():
    """Run get_new_errors() — verify response structure regardless of whether there are errors."""
    if not os.environ.get("METABASE_ERROR_QUESTION_ID"):
        pytest.skip("METABASE_ERROR_QUESTION_ID not set — skipping new errors test.")
    from mcp_servers.metabase_server import get_new_errors
    result = get_new_errors(since_hours=24)
    assert "error" not in result, f"get_new_errors() returned error: {result.get('error')}"
    assert "new_errors" in result, f"Expected 'new_errors' in result: {result}"
    assert "has_new_errors" in result, "Expected 'has_new_errors' in result."
    assert "count" in result, "Expected 'count' in result."

"""
SAGE[ai] - Spira Integration Tests

These tests connect to a REAL SpiraTeam/SpiraTest instance.
All tests are skipped if Spira credentials are not configured.

Requires environment variables:
  SPIRA_URL        — e.g. https://spira.example.com
  SPIRA_USERNAME   — SpiraTeam username
  SPIRA_API_KEY    — SpiraTeam REST API key (from user profile)
  SPIRA_PROJECT_ID — Numeric project ID to test against
"""

import os

import pytest


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def require_spira_credentials():
    """Skip all tests if Spira credentials are not configured."""
    required = ["SPIRA_URL", "SPIRA_USERNAME", "SPIRA_API_KEY", "SPIRA_PROJECT_ID"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        pytest.skip(f"Spira credentials not configured (missing: {', '.join(missing)}) — skipping Spira integration tests.")


def test_spira_connection():
    """Verify Spira API is reachable and credentials work by fetching project info."""
    from mcp_servers.spira_server import get_project_info
    project_id = int(os.environ["SPIRA_PROJECT_ID"])
    result = get_project_info(project_id=project_id)
    assert "error" not in result, f"Spira connection failed: {result.get('error')}"
    assert result.get("project_id") == project_id, (
        f"Expected project_id={project_id}, got {result.get('project_id')}"
    )
    assert "name" in result, "Expected 'name' in project info result."


def test_list_incidents_live():
    """List incidents for the configured project — verify response structure."""
    from mcp_servers.spira_server import list_incidents
    project_id = int(os.environ["SPIRA_PROJECT_ID"])
    result = list_incidents(project_id=project_id)
    assert "error" not in result, f"list_incidents() returned error: {result.get('error')}"
    assert "incidents" in result, f"Expected 'incidents' in result: {result}"
    assert isinstance(result["incidents"], list)
    if result["count"] > 0:
        inc = result["incidents"][0]
        for field in ("incident_id", "name", "status_name"):
            assert field in inc, f"Expected '{field}' in incident dict: {inc}"


def test_list_requirements_live():
    """List requirements for the configured project — verify response structure."""
    from mcp_servers.spira_server import list_requirements
    project_id = int(os.environ["SPIRA_PROJECT_ID"])
    result = list_requirements(project_id=project_id)
    assert "error" not in result, f"list_requirements() returned error: {result.get('error')}"
    assert "requirements" in result, f"Expected 'requirements' in result: {result}"


def test_list_releases_live():
    """List releases for the configured project — verify response structure."""
    from mcp_servers.spira_server import list_releases
    project_id = int(os.environ["SPIRA_PROJECT_ID"])
    result = list_releases(project_id=project_id)
    assert "error" not in result, f"list_releases() returned error: {result.get('error')}"
    assert "releases" in result, f"Expected 'releases' in result: {result}"

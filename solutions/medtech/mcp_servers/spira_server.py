"""
SAGE[ai] - SpiraTeam/SpiraTest MCP Server
==========================================
FastMCP server for SpiraTeam REST API v7.
Exposes incident management, requirements, test runs, and project information.
"""

import logging
import os
from typing import Optional

import requests

from fastmcp import FastMCP

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

mcp = FastMCP("SAGE Spira Server")

# ---------------------------------------------------------------------------
# Config from environment variables
# ---------------------------------------------------------------------------
SPIRA_URL = os.environ.get("SPIRA_URL", "").rstrip("/")
SPIRA_USERNAME = os.environ.get("SPIRA_USERNAME", "")
SPIRA_API_KEY = os.environ.get("SPIRA_API_KEY", "")
SPIRA_PROJECT_ID = os.environ.get("SPIRA_PROJECT_ID", "")

if not SPIRA_URL:
    logger.warning("SPIRA_URL not set. Spira tools will return errors.")

SPIRA_API_BASE = f"{SPIRA_URL}/services/v7_0/RestService.svc" if SPIRA_URL else ""


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _spira_get(path: str, params: dict = None) -> tuple:
    """
    Makes an authenticated GET request to the Spira REST API.
    Returns (data, error_string). If successful, error_string is None.
    """
    if not SPIRA_URL:
        return None, "SPIRA_URL is not configured."
    if not SPIRA_USERNAME or not SPIRA_API_KEY:
        return None, "SPIRA_USERNAME or SPIRA_API_KEY not set."

    auth_params = {"username": SPIRA_USERNAME, "api-key": SPIRA_API_KEY}
    if params:
        auth_params.update(params)

    try:
        resp = requests.get(
            f"{SPIRA_API_BASE}{path}",
            params=auth_params,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json(), None
    except requests.RequestException as e:
        logger.error("Spira GET %s failed: %s", path, e)
        return None, str(e)


def _spira_post(path: str, body: dict) -> tuple:
    """
    Makes an authenticated POST request to the Spira REST API.
    Returns (data, error_string).
    """
    if not SPIRA_URL:
        return None, "SPIRA_URL is not configured."

    try:
        resp = requests.post(
            f"{SPIRA_API_BASE}{path}",
            params={"username": SPIRA_USERNAME, "api-key": SPIRA_API_KEY},
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json(), None
    except requests.RequestException as e:
        logger.error("Spira POST %s failed: %s", path, e)
        return None, str(e)


def _spira_put(path: str, body: dict) -> tuple:
    """
    Makes an authenticated PUT request to the Spira REST API.
    """
    if not SPIRA_URL:
        return None, "SPIRA_URL is not configured."

    try:
        resp = requests.put(
            f"{SPIRA_API_BASE}{path}",
            params={"username": SPIRA_USERNAME, "api-key": SPIRA_API_KEY},
            json=body,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        # PUT may return 200 with body or 204 with no body
        if resp.content:
            return resp.json(), None
        return {"status": "updated"}, None
    except requests.RequestException as e:
        logger.error("Spira PUT %s failed: %s", path, e)
        return None, str(e)


def _clean_incident(inc: dict) -> dict:
    """Extracts key fields from an incident record."""
    return {
        "incident_id": inc.get("IncidentId"),
        "name": inc.get("Name"),
        "description": inc.get("Description", ""),
        "status_id": inc.get("IncidentStatusId"),
        "status_name": inc.get("IncidentStatusName", ""),
        "type_id": inc.get("IncidentTypeId"),
        "type_name": inc.get("IncidentTypeName", ""),
        "priority_id": inc.get("PriorityId"),
        "priority_name": inc.get("PriorityName", ""),
        "severity_id": inc.get("SeverityId"),
        "severity_name": inc.get("SeverityName", ""),
        "opener_id": inc.get("OpenerId"),
        "opener_name": inc.get("OpenerName", ""),
        "owner_id": inc.get("OwnerId"),
        "owner_name": inc.get("OwnerName", ""),
        "creation_date": inc.get("CreationDate", ""),
        "last_update_date": inc.get("LastUpdateDate", ""),
        "closed_date": inc.get("ClosedDate", ""),
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_incidents(project_id: int, status_id: Optional[int] = None) -> dict:
    """
    Lists incidents (bugs/defects) for a project.

    Args:
        project_id: The Spira project ID
        status_id:  Optional status filter (e.g. 1=New, 2=Open, 3=Assigned)

    Returns:
        dict with 'incidents' list and 'count'.
    """
    params = {}
    if status_id is not None:
        params["status_id"] = status_id

    data, err = _spira_get(f"/projects/{project_id}/incidents", params)
    if err:
        return {"error": err, "project_id": project_id}

    incidents = [_clean_incident(i) for i in (data or [])]
    logger.info("Listed %d incidents for project %d", len(incidents), project_id)
    return {"incidents": incidents, "count": len(incidents), "project_id": project_id}


@mcp.tool()
def get_incident(project_id: int, incident_id: int) -> dict:
    """
    Gets detailed information about a single incident.

    Args:
        project_id:  The Spira project ID
        incident_id: The incident ID

    Returns:
        dict with full incident details.
    """
    data, err = _spira_get(f"/projects/{project_id}/incidents/{incident_id}")
    if err:
        return {"error": err, "incident_id": incident_id}

    if not data:
        return {"error": "Incident not found.", "incident_id": incident_id}

    result = _clean_incident(data)
    # Include custom properties if present
    if "CustomProperties" in data:
        result["custom_properties"] = data["CustomProperties"]
    logger.info("Fetched incident %d from project %d", incident_id, project_id)
    return result


@mcp.tool()
def create_incident(project_id: int, name: str, description: str, type_id: int = 1) -> dict:
    """
    Creates a new incident (bug/defect) in Spira.

    Args:
        project_id:  The Spira project ID
        name:        Short incident title
        description: Detailed description
        type_id:     Incident type ID (1=Bug by default)

    Returns:
        dict with the created incident's ID and details.
    """
    body = {
        "Name": name,
        "Description": description,
        "IncidentTypeId": type_id,
        "ProjectId": project_id,
    }
    data, err = _spira_post(f"/projects/{project_id}/incidents", body)
    if err:
        return {"error": err, "project_id": project_id}

    result = _clean_incident(data) if data else {"status": "created"}
    logger.info("Created incident '%s' in project %d (ID: %s)", name, project_id, result.get("incident_id"))
    return result


@mcp.tool()
def update_incident(project_id: int, incident_id: int, fields: dict) -> dict:
    """
    Updates fields on an existing incident.

    Args:
        project_id:  The Spira project ID
        incident_id: The incident to update
        fields:      Dict of fields to update (e.g. {"IncidentStatusId": 3, "OwnerId": 5})

    Returns:
        dict with update status.
    """
    # First get the current incident to merge changes
    data, err = _spira_get(f"/projects/{project_id}/incidents/{incident_id}")
    if err:
        return {"error": f"Could not fetch incident for update: {err}"}
    if not data:
        return {"error": f"Incident {incident_id} not found."}

    # Merge updated fields
    data.update(fields)
    data["IncidentId"] = incident_id
    data["ProjectId"] = project_id

    result, err = _spira_put(f"/projects/{project_id}/incidents/{incident_id}", data)
    if err:
        return {"error": err, "incident_id": incident_id}

    logger.info("Updated incident %d in project %d", incident_id, project_id)
    return {"status": "updated", "incident_id": incident_id, "project_id": project_id, "updated_fields": list(fields.keys())}


@mcp.tool()
def list_requirements(project_id: int) -> dict:
    """
    Lists all requirements for a project.

    Args:
        project_id: The Spira project ID

    Returns:
        dict with 'requirements' list.
    """
    data, err = _spira_get(f"/projects/{project_id}/requirements")
    if err:
        return {"error": err, "project_id": project_id}

    requirements = []
    for r in (data or []):
        requirements.append({
            "requirement_id": r.get("RequirementId"),
            "name": r.get("Name"),
            "description": r.get("Description", ""),
            "status_id": r.get("StatusId"),
            "status_name": r.get("StatusName", ""),
            "importance_id": r.get("ImportanceId"),
            "importance_name": r.get("ImportanceName", ""),
            "author_id": r.get("AuthorId"),
            "author_name": r.get("AuthorName", ""),
            "creation_date": r.get("CreationDate", ""),
        })

    logger.info("Listed %d requirements for project %d", len(requirements), project_id)
    return {"requirements": requirements, "count": len(requirements), "project_id": project_id}


@mcp.tool()
def get_test_runs(project_id: int, release_id: Optional[int] = None) -> dict:
    """
    Gets test run results for a project, optionally filtered by release.

    Args:
        project_id: The Spira project ID
        release_id: Optional release ID to filter by

    Returns:
        dict with 'test_runs' list and summary stats.
    """
    params = {}
    if release_id is not None:
        params["release_id"] = release_id

    data, err = _spira_get(f"/projects/{project_id}/test-runs", params)
    if err:
        return {"error": err, "project_id": project_id}

    runs = []
    for r in (data or []):
        runs.append({
            "test_run_id": r.get("TestRunId"),
            "name": r.get("Name"),
            "execution_status_id": r.get("ExecutionStatusId"),
            "execution_status_name": r.get("ExecutionStatusName", ""),
            "tester_id": r.get("TesterId"),
            "tester_name": r.get("TesterName", ""),
            "start_date": r.get("StartDate", ""),
            "end_date": r.get("EndDate", ""),
            "release_id": r.get("ReleaseId"),
            "release_name": r.get("ReleaseName", ""),
        })

    # Summary stats
    passed = sum(1 for r in runs if "pass" in r.get("execution_status_name", "").lower())
    failed = sum(1 for r in runs if "fail" in r.get("execution_status_name", "").lower())

    logger.info("Got %d test runs for project %d", len(runs), project_id)
    return {
        "test_runs": runs,
        "count": len(runs),
        "passed": passed,
        "failed": failed,
        "project_id": project_id,
    }


@mcp.tool()
def list_releases(project_id: int) -> dict:
    """
    Lists all releases/versions for a project.

    Args:
        project_id: The Spira project ID

    Returns:
        dict with 'releases' list.
    """
    data, err = _spira_get(f"/projects/{project_id}/releases")
    if err:
        return {"error": err, "project_id": project_id}

    releases = []
    for r in (data or []):
        releases.append({
            "release_id": r.get("ReleaseId"),
            "name": r.get("Name"),
            "version_number": r.get("VersionNumber", ""),
            "status_id": r.get("ReleaseStatusId"),
            "status_name": r.get("ReleaseStatusName", ""),
            "start_date": r.get("StartDate", ""),
            "end_date": r.get("EndDate", ""),
            "creator_id": r.get("CreatorId"),
            "creator_name": r.get("CreatorName", ""),
        })

    logger.info("Listed %d releases for project %d", len(releases), project_id)
    return {"releases": releases, "count": len(releases), "project_id": project_id}


@mcp.tool()
def get_project_info(project_id: int) -> dict:
    """
    Gets detailed information about a Spira project.

    Args:
        project_id: The project ID

    Returns:
        dict with project metadata.
    """
    data, err = _spira_get(f"/projects/{project_id}")
    if err:
        return {"error": err, "project_id": project_id}

    if not data:
        return {"error": "Project not found.", "project_id": project_id}

    return {
        "project_id": data.get("ProjectId"),
        "name": data.get("Name"),
        "description": data.get("Description", ""),
        "website": data.get("Website", ""),
        "creation_date": data.get("CreationDate", ""),
        "active": data.get("Active", True),
        "working_hours": data.get("WorkingHours"),
        "working_days": data.get("WorkingDays"),
    }


# ---------------------------------------------------------------------------
# Standalone test helper
# ---------------------------------------------------------------------------

def test_connection():
    """Quick standalone test — verifies Spira connection."""
    print("=== Spira Server Standalone Test ===")
    print(f"URL: {SPIRA_URL or '(not set)'}")
    print(f"Username: {SPIRA_USERNAME or '(not set)'}")
    print(f"API Key: {'****' + SPIRA_API_KEY[-4:] if len(SPIRA_API_KEY) > 4 else '(not set)'}")

    if SPIRA_PROJECT_ID:
        result = get_project_info(int(SPIRA_PROJECT_ID))
        if "error" not in result:
            print(f"Project '{result.get('name')}' accessible: OK")
        else:
            print(f"Connection ERROR: {result['error']}")
    else:
        print("SPIRA_PROJECT_ID not set — skipping project connectivity test.")
    print("=====================================")


if __name__ == "__main__":
    mcp.run()

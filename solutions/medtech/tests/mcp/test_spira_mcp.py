"""
SAGE[ai] - Unit tests for Spira MCP Server (mcp_servers/spira_server.py)

All HTTP calls are mocked. Tests verify incident management, CRUD operations,
requirement/test run listing, and auth parameter injection.
"""

import os
from unittest.mock import MagicMock, patch, call

import pytest


pytestmark = pytest.mark.unit


MOCK_INCIDENT = {
    "IncidentId": 101,
    "Name": "UART buffer overflow",
    "Description": "Buffer overflow at 0x20001000",
    "IncidentStatusId": 1,
    "IncidentStatusName": "New",
    "IncidentTypeId": 1,
    "IncidentTypeName": "Bug",
    "PriorityId": 2,
    "PriorityName": "High",
    "SeverityId": 2,
    "SeverityName": "High",
    "OpenerName": "Jane Dev",
    "OwnerId": None,
    "OwnerName": "",
    "OpenerId": 5,
    "CreationDate": "2024-01-15T08:00:00",
    "LastUpdateDate": "2024-01-15T09:00:00",
    "ClosedDate": None,
}


def _make_response(status_code=200, json_data=None, raise_exc=None):
    resp = MagicMock()
    resp.status_code = status_code
    if raise_exc:
        resp.raise_for_status.side_effect = raise_exc
    else:
        resp.raise_for_status = MagicMock()
    resp.json.return_value = json_data if json_data is not None else {}
    resp.content = b"response body"
    return resp


def _spira_env():
    return {
        "SPIRA_URL": "https://spira.test.local",
        "SPIRA_USERNAME": "testuser",
        "SPIRA_API_KEY": "{apikey}",
        "SPIRA_PROJECT_ID": "1",
    }


# ---------------------------------------------------------------------------
# list_incidents
# ---------------------------------------------------------------------------


def test_list_incidents_calls_correct_endpoint():
    """list_incidents() must call the /projects/{id}/incidents endpoint."""
    import mcp_servers.spira_server as srv
    resp = _make_response(200, [MOCK_INCIDENT])
    with patch.dict(os.environ, _spira_env()), \
         patch.object(srv, "SPIRA_URL", "https://spira.test.local"), \
         patch.object(srv, "SPIRA_USERNAME", "testuser"), \
         patch.object(srv, "SPIRA_API_KEY", "{apikey}"), \
         patch.object(srv, "SPIRA_API_BASE", "https://spira.test.local/services/v7_0/RestService.svc"), \
         patch("requests.get", return_value=resp) as mock_get:
        srv.list_incidents(project_id=1)
    called_url = mock_get.call_args[0][0]
    assert "/projects/1/incidents" in called_url, f"Expected /projects/1/incidents in URL: {called_url}"


def test_list_incidents_returns_list():
    """list_incidents() with 3 incidents must return count=3 and incidents list."""
    import mcp_servers.spira_server as srv
    resp = _make_response(200, [MOCK_INCIDENT, MOCK_INCIDENT, MOCK_INCIDENT])
    with patch.object(srv, "SPIRA_URL", "https://spira.test.local"), \
         patch.object(srv, "SPIRA_USERNAME", "testuser"), \
         patch.object(srv, "SPIRA_API_KEY", "{apikey}"), \
         patch.object(srv, "SPIRA_API_BASE", "https://spira.test.local/services/v7_0/RestService.svc"), \
         patch("requests.get", return_value=resp):
        result = srv.list_incidents(project_id=1)
    assert result.get("count") == 3, f"Expected count=3, got {result.get('count')}"
    assert "incidents" in result, f"Expected 'incidents' in result: {result}"
    assert isinstance(result["incidents"], list)


def test_list_incidents_filters_by_status():
    """list_incidents(status_id=2) must pass status_id in request params."""
    import mcp_servers.spira_server as srv
    resp = _make_response(200, [])
    with patch.object(srv, "SPIRA_URL", "https://spira.test.local"), \
         patch.object(srv, "SPIRA_USERNAME", "testuser"), \
         patch.object(srv, "SPIRA_API_KEY", "{apikey}"), \
         patch.object(srv, "SPIRA_API_BASE", "https://spira.test.local/services/v7_0/RestService.svc"), \
         patch("requests.get", return_value=resp) as mock_get:
        srv.list_incidents(project_id=1, status_id=2)
    call_kwargs = mock_get.call_args[1]
    params = call_kwargs.get("params", {})
    assert "status_id" in params, f"Expected status_id in params, got: {params}"
    assert params["status_id"] == 2


# ---------------------------------------------------------------------------
# get_incident
# ---------------------------------------------------------------------------


def test_get_incident_returns_incident():
    """get_incident() must return a dict with incident_id field."""
    import mcp_servers.spira_server as srv
    resp = _make_response(200, MOCK_INCIDENT)
    with patch.object(srv, "SPIRA_URL", "https://spira.test.local"), \
         patch.object(srv, "SPIRA_USERNAME", "testuser"), \
         patch.object(srv, "SPIRA_API_KEY", "{apikey}"), \
         patch.object(srv, "SPIRA_API_BASE", "https://spira.test.local/services/v7_0/RestService.svc"), \
         patch("requests.get", return_value=resp):
        result = srv.get_incident(project_id=1, incident_id=101)
    assert result.get("incident_id") == 101, f"Expected incident_id=101: {result}"


def test_get_incident_not_found():
    """get_incident() with 404 response must return error dict."""
    import mcp_servers.spira_server as srv
    import requests as req_module
    resp = _make_response(404, raise_exc=req_module.HTTPError("404 Not Found"))
    with patch.object(srv, "SPIRA_URL", "https://spira.test.local"), \
         patch.object(srv, "SPIRA_USERNAME", "testuser"), \
         patch.object(srv, "SPIRA_API_KEY", "{apikey}"), \
         patch.object(srv, "SPIRA_API_BASE", "https://spira.test.local/services/v7_0/RestService.svc"), \
         patch("requests.get", return_value=resp):
        result = srv.get_incident(project_id=1, incident_id=9999)
    assert "error" in result, f"Expected 'error' for 404, got: {result}"


# ---------------------------------------------------------------------------
# create_incident
# ---------------------------------------------------------------------------


def test_create_incident_posts_to_api():
    """create_incident() must POST with Name and Description fields in body."""
    import mcp_servers.spira_server as srv
    new_inc = {**MOCK_INCIDENT, "IncidentId": 999}
    resp = _make_response(201, new_inc)
    with patch.object(srv, "SPIRA_URL", "https://spira.test.local"), \
         patch.object(srv, "SPIRA_USERNAME", "testuser"), \
         patch.object(srv, "SPIRA_API_KEY", "{apikey}"), \
         patch.object(srv, "SPIRA_API_BASE", "https://spira.test.local/services/v7_0/RestService.svc"), \
         patch("requests.post", return_value=resp) as mock_post:
        srv.create_incident(project_id=1, name="Test Bug", description="Bug details")
    call_kwargs = mock_post.call_args[1]
    body = call_kwargs.get("json", {})
    assert "Name" in body, f"Expected 'Name' in POST body: {body}"
    assert "Description" in body, f"Expected 'Description' in POST body: {body}"


def test_create_incident_returns_id():
    """create_incident() must return a dict with incident_id."""
    import mcp_servers.spira_server as srv
    new_inc = {**MOCK_INCIDENT, "IncidentId": 999}
    resp = _make_response(201, new_inc)
    with patch.object(srv, "SPIRA_URL", "https://spira.test.local"), \
         patch.object(srv, "SPIRA_USERNAME", "testuser"), \
         patch.object(srv, "SPIRA_API_KEY", "{apikey}"), \
         patch.object(srv, "SPIRA_API_BASE", "https://spira.test.local/services/v7_0/RestService.svc"), \
         patch("requests.post", return_value=resp):
        result = srv.create_incident(project_id=1, name="Test Bug", description="Details")
    assert result.get("incident_id") == 999, f"Expected incident_id=999: {result}"


# ---------------------------------------------------------------------------
# update_incident
# ---------------------------------------------------------------------------


def test_update_incident_sends_put():
    """update_incident() must issue a PUT/GET sequence and return updated status."""
    import mcp_servers.spira_server as srv
    get_resp = _make_response(200, MOCK_INCIDENT)
    put_resp = _make_response(200, {**MOCK_INCIDENT, "IncidentStatusId": 3})
    with patch.object(srv, "SPIRA_URL", "https://spira.test.local"), \
         patch.object(srv, "SPIRA_USERNAME", "testuser"), \
         patch.object(srv, "SPIRA_API_KEY", "{apikey}"), \
         patch.object(srv, "SPIRA_API_BASE", "https://spira.test.local/services/v7_0/RestService.svc"), \
         patch("requests.get", return_value=get_resp), \
         patch("requests.put", return_value=put_resp):
        result = srv.update_incident(project_id=1, incident_id=101, fields={"IncidentStatusId": 3})
    assert "error" not in result, f"Unexpected error: {result.get('error')}"


# ---------------------------------------------------------------------------
# list_requirements
# ---------------------------------------------------------------------------


def test_list_requirements_returns_list():
    """list_requirements() must return a dict with 'requirements' list."""
    import mcp_servers.spira_server as srv
    req_data = [
        {"RequirementId": 1, "Name": "Req 1", "Description": "", "StatusId": 2, "StatusName": "Accepted",
         "ImportanceId": 1, "ImportanceName": "Critical", "AuthorId": 5, "AuthorName": "Dev",
         "CreationDate": "2024-01-01"},
    ]
    resp = _make_response(200, req_data)
    with patch.object(srv, "SPIRA_URL", "https://spira.test.local"), \
         patch.object(srv, "SPIRA_USERNAME", "testuser"), \
         patch.object(srv, "SPIRA_API_KEY", "{apikey}"), \
         patch.object(srv, "SPIRA_API_BASE", "https://spira.test.local/services/v7_0/RestService.svc"), \
         patch("requests.get", return_value=resp):
        result = srv.list_requirements(project_id=1)
    assert "requirements" in result, f"Expected 'requirements': {result}"
    assert result.get("count") >= 1


# ---------------------------------------------------------------------------
# get_test_runs
# ---------------------------------------------------------------------------


def test_get_test_runs_returns_runs():
    """get_test_runs() must return a dict with 'test_runs' list."""
    import mcp_servers.spira_server as srv
    run_data = [
        {"TestRunId": 1, "Name": "Smoke Test", "ExecutionStatusId": 2, "ExecutionStatusName": "Passed",
         "TesterId": 5, "TesterName": "QA", "StartDate": "", "EndDate": "", "ReleaseId": 1, "ReleaseName": "v1.0"},
    ]
    resp = _make_response(200, run_data)
    with patch.object(srv, "SPIRA_URL", "https://spira.test.local"), \
         patch.object(srv, "SPIRA_USERNAME", "testuser"), \
         patch.object(srv, "SPIRA_API_KEY", "{apikey}"), \
         patch.object(srv, "SPIRA_API_BASE", "https://spira.test.local/services/v7_0/RestService.svc"), \
         patch("requests.get", return_value=resp):
        result = srv.get_test_runs(project_id=1)
    assert "test_runs" in result, f"Expected 'test_runs': {result}"


# ---------------------------------------------------------------------------
# list_releases
# ---------------------------------------------------------------------------


def test_list_releases_returns_releases():
    """list_releases() must return a dict with 'releases' list."""
    import mcp_servers.spira_server as srv
    rel_data = [
        {"ReleaseId": 1, "Name": "v1.0.0", "VersionNumber": "1.0.0", "ReleaseStatusId": 3,
         "ReleaseStatusName": "Released", "StartDate": "", "EndDate": "", "CreatorId": 1, "CreatorName": "PM"},
    ]
    resp = _make_response(200, rel_data)
    with patch.object(srv, "SPIRA_URL", "https://spira.test.local"), \
         patch.object(srv, "SPIRA_USERNAME", "testuser"), \
         patch.object(srv, "SPIRA_API_KEY", "{apikey}"), \
         patch.object(srv, "SPIRA_API_BASE", "https://spira.test.local/services/v7_0/RestService.svc"), \
         patch("requests.get", return_value=resp):
        result = srv.list_releases(project_id=1)
    assert "releases" in result, f"Expected 'releases': {result}"


# ---------------------------------------------------------------------------
# get_project_info
# ---------------------------------------------------------------------------


def test_get_project_info_returns_project():
    """get_project_info() must return a dict with ProjectId."""
    import mcp_servers.spira_server as srv
    project_data = {
        "ProjectId": 1,
        "Name": "FirmwareProject",
        "Description": "Embedded firmware QMS project",
        "Website": "",
        "CreationDate": "2023-01-01",
        "Active": True,
        "WorkingHours": 8,
        "WorkingDays": 5,
    }
    resp = _make_response(200, project_data)
    with patch.object(srv, "SPIRA_URL", "https://spira.test.local"), \
         patch.object(srv, "SPIRA_USERNAME", "testuser"), \
         patch.object(srv, "SPIRA_API_KEY", "{apikey}"), \
         patch.object(srv, "SPIRA_API_BASE", "https://spira.test.local/services/v7_0/RestService.svc"), \
         patch("requests.get", return_value=resp):
        result = srv.get_project_info(project_id=1)
    assert result.get("project_id") == 1, f"Expected project_id=1: {result}"


# ---------------------------------------------------------------------------
# Auth params included in every request
# ---------------------------------------------------------------------------


def test_auth_params_included_in_every_request():
    """Every request to Spira API must include 'username' and 'api-key' params."""
    import mcp_servers.spira_server as srv
    resp = _make_response(200, [])
    with patch.object(srv, "SPIRA_URL", "https://spira.test.local"), \
         patch.object(srv, "SPIRA_USERNAME", "myuser"), \
         patch.object(srv, "SPIRA_API_KEY", "myapikey"), \
         patch.object(srv, "SPIRA_API_BASE", "https://spira.test.local/services/v7_0/RestService.svc"), \
         patch("requests.get", return_value=resp) as mock_get:
        srv.list_incidents(project_id=1)
    call_kwargs = mock_get.call_args[1]
    params = call_kwargs.get("params", {})
    assert "username" in params, f"Expected 'username' in params: {params}"
    assert "api-key" in params, f"Expected 'api-key' in params: {params}"
    assert params["username"] == "myuser"
    assert params["api-key"] == "myapikey"

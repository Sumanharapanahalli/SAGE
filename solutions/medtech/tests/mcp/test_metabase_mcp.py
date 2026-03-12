"""
SAGE[ai] - Unit tests for Metabase MCP Server (mcp_servers/metabase_server.py)

All HTTP calls are mocked. Tests verify authentication, data retrieval,
error filtering, and graceful degradation.
"""

import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest


pytestmark = pytest.mark.unit


def _make_response(status_code=200, json_data=None, raise_exc=None):
    resp = MagicMock()
    resp.status_code = status_code
    if raise_exc:
        resp.raise_for_status.side_effect = raise_exc
    else:
        resp.raise_for_status = MagicMock()
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


def _reset_session_cache():
    """Reset the module-level session token cache."""
    import mcp_servers.metabase_server as srv
    srv._session_cache["token"] = None
    srv._session_cache["expires_at"] = 0.0


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_get_session_token_posts_to_api():
    """_get_session_token_internal() must POST to /api/session and return the token."""
    _reset_session_cache()
    import mcp_servers.metabase_server as srv

    auth_resp = _make_response(200, {"id": "token123"})
    with patch.dict(os.environ, {
        "METABASE_URL": "https://metabase.test.local",
        "METABASE_USERNAME": "admin@test.com",
        "METABASE_PASSWORD": "secret",
    }), patch("requests.post", return_value=auth_resp) as mock_post, \
       patch.object(srv, "METABASE_URL", "https://metabase.test.local"), \
       patch.object(srv, "METABASE_USERNAME", "admin@test.com"), \
       patch.object(srv, "METABASE_PASSWORD", "secret"):
        token = srv._get_session_token_internal()

    assert token == "token123", f"Expected 'token123', got: {token!r}"
    assert mock_post.called, "requests.post must be called for authentication."


def test_get_session_token_handles_auth_failure():
    """When Metabase returns 401, _get_session_token_internal() must return None."""
    _reset_session_cache()
    import mcp_servers.metabase_server as srv
    import requests as req_module

    fail_resp = _make_response(401, raise_exc=req_module.HTTPError("401 Unauthorized"))
    with patch("requests.post", return_value=fail_resp), \
         patch.object(srv, "METABASE_URL", "https://metabase.test.local"), \
         patch.object(srv, "METABASE_USERNAME", "user"), \
         patch.object(srv, "METABASE_PASSWORD", "wrong"):
        token = srv._get_session_token_internal()

    assert token is None, f"Expected None on auth failure, got: {token!r}"
    _reset_session_cache()


# ---------------------------------------------------------------------------
# get_question_results
# ---------------------------------------------------------------------------


def test_get_question_results_calls_correct_endpoint():
    """get_question_results(42) must POST to /api/card/42/query/json."""
    _reset_session_cache()
    import mcp_servers.metabase_server as srv

    rows = [{"col1": "val1", "col2": "val2"}]
    data_resp = _make_response(200, rows)

    with patch.object(srv, "_get_session_token_internal", return_value="mock-token"), \
         patch.object(srv, "METABASE_URL", "https://metabase.test.local"), \
         patch("requests.post", return_value=data_resp) as mock_post:
        result = srv.get_question_results(question_id=42)

    called_url = mock_post.call_args[0][0]
    assert "/api/card/42/query/json" in called_url, (
        f"Expected '/api/card/42/query/json' in URL, got: {called_url!r}"
    )


def test_get_question_results_returns_data():
    """get_question_results() must return rows from the response."""
    _reset_session_cache()
    import mcp_servers.metabase_server as srv

    rows = [
        {"error_code": "E001", "message": "timeout"},
        {"error_code": "E002", "message": "overflow"},
    ]
    data_resp = _make_response(200, rows)

    with patch.object(srv, "_get_session_token_internal", return_value="mock-token"), \
         patch.object(srv, "METABASE_URL", "https://metabase.test.local"), \
         patch("requests.post", return_value=data_resp):
        result = srv.get_question_results(question_id=10)

    assert result.get("row_count") == 2, f"Expected row_count=2, got {result.get('row_count')}"
    assert "rows" in result, f"Expected 'rows' in result: {result}"


# ---------------------------------------------------------------------------
# list_dashboards
# ---------------------------------------------------------------------------


def test_list_dashboards_returns_list():
    """list_dashboards() must return a dict with 'dashboards' list."""
    _reset_session_cache()
    import mcp_servers.metabase_server as srv

    dashboards_data = [
        {"id": 1, "name": "Manufacturing Overview", "description": ""},
        {"id": 2, "name": "Error Trends", "description": "Daily error counts"},
    ]
    dash_resp = _make_response(200, dashboards_data)

    with patch.object(srv, "_get_session_token_internal", return_value="mock-token"), \
         patch.object(srv, "METABASE_URL", "https://metabase.test.local"), \
         patch("requests.get", return_value=dash_resp):
        result = srv.list_dashboards()

    assert "dashboards" in result, f"Expected 'dashboards' in result: {result}"
    assert result.get("count") == 2, f"Expected count=2, got {result.get('count')}"


# ---------------------------------------------------------------------------
# get_dashboard
# ---------------------------------------------------------------------------


def test_get_dashboard_returns_cards():
    """get_dashboard() must return a dict with 'cards' list."""
    _reset_session_cache()
    import mcp_servers.metabase_server as srv

    dashboard_data = {
        "id": 1,
        "name": "Manufacturing Overview",
        "description": "",
        "ordered_cards": [
            {"card": {"id": 10, "name": "Error Count", "display": "bar", "description": ""}},
            {"card": {"id": 11, "name": "Uptime", "display": "line", "description": ""}},
        ],
    }
    dash_resp = _make_response(200, dashboard_data)

    with patch.object(srv, "_get_session_token_internal", return_value="mock-token"), \
         patch.object(srv, "METABASE_URL", "https://metabase.test.local"), \
         patch("requests.get", return_value=dash_resp):
        result = srv.get_dashboard(dashboard_id=1)

    assert "cards" in result, f"Expected 'cards' in result: {result}"
    assert result.get("card_count") == 2


# ---------------------------------------------------------------------------
# search_errors
# ---------------------------------------------------------------------------


def test_search_errors_uses_configured_question_id():
    """search_errors() must query the question ID set in METABASE_ERROR_QUESTION_ID."""
    _reset_session_cache()
    import mcp_servers.metabase_server as srv

    rows = [{"error_code": "E001", "message": "timeout", "timestamp": "2024-01-15T10:00:00Z"}]
    data_resp = _make_response(200, rows)

    with patch.object(srv, "_get_session_token_internal", return_value="mock-token"), \
         patch.object(srv, "METABASE_URL", "https://metabase.test.local"), \
         patch.object(srv, "METABASE_ERROR_QUESTION_ID", "99"), \
         patch("requests.post", return_value=data_resp) as mock_post:
        result = srv.search_errors(since_hours=24)

    called_url = mock_post.call_args[0][0]
    assert "/api/card/99/" in called_url, (
        f"Expected question_id 99 in URL, got: {called_url!r}"
    )


def test_search_errors_filters_by_time():
    """search_errors() must filter rows to only those within since_hours window."""
    _reset_session_cache()
    import mcp_servers.metabase_server as srv

    now = datetime.now(timezone.utc)
    recent_ts = (now - timedelta(hours=0.5)).isoformat()
    old_ts = (now - timedelta(hours=48)).isoformat()

    rows = [
        {"error_code": "E001", "message": "recent error", "timestamp": recent_ts},
        {"error_code": "E002", "message": "old error", "timestamp": old_ts},
    ]
    data_resp = _make_response(200, rows)

    with patch.object(srv, "_get_session_token_internal", return_value="mock-token"), \
         patch.object(srv, "METABASE_URL", "https://metabase.test.local"), \
         patch.object(srv, "METABASE_ERROR_QUESTION_ID", "5"), \
         patch("requests.post", return_value=data_resp):
        result = srv.search_errors(since_hours=1)

    errors = result.get("errors", [])
    assert len(errors) == 1, f"Expected only 1 recent error filtered, got {len(errors)}: {errors}"
    assert errors[0]["message"] == "recent error"


# ---------------------------------------------------------------------------
# get_new_errors
# ---------------------------------------------------------------------------


def test_get_new_errors_returns_recent_only():
    """get_new_errors(since_hours=1) must return only rows within the last hour."""
    _reset_session_cache()
    import mcp_servers.metabase_server as srv

    now = datetime.now(timezone.utc)
    rows = [
        {"error_code": "E001", "message": "new error", "timestamp": (now - timedelta(minutes=30)).isoformat()},
        {"error_code": "E002", "message": "old error 1", "timestamp": (now - timedelta(hours=5)).isoformat()},
        {"error_code": "E003", "message": "old error 2", "timestamp": (now - timedelta(hours=10)).isoformat()},
    ]
    data_resp = _make_response(200, rows)

    with patch.object(srv, "_get_session_token_internal", return_value="mock-token"), \
         patch.object(srv, "METABASE_URL", "https://metabase.test.local"), \
         patch.object(srv, "METABASE_ERROR_QUESTION_ID", "5"), \
         patch("requests.post", return_value=data_resp):
        result = srv.get_new_errors(since_hours=1)

    assert result.get("count") == 1, f"Expected 1 new error, got {result.get('count')}"
    assert result.get("has_new_errors") is True


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_missing_env_vars_return_error():
    """When METABASE_URL is not set, tools must return an error dict."""
    _reset_session_cache()
    import mcp_servers.metabase_server as srv

    with patch.object(srv, "METABASE_URL", ""), \
         patch.object(srv, "METABASE_ERROR_QUESTION_ID", ""):
        result = srv.search_errors(since_hours=1)

    assert "error" in result, f"Expected 'error' when METABASE_URL not set: {result}"


def test_handles_metabase_connection_error():
    """When requests raises ConnectionError, get_question_results() must return graceful error dict."""
    _reset_session_cache()
    import mcp_servers.metabase_server as srv
    import requests as req_module

    with patch.object(srv, "_get_session_token_internal", return_value="mock-token"), \
         patch.object(srv, "METABASE_URL", "https://metabase.test.local"), \
         patch("requests.post", side_effect=req_module.ConnectionError("Connection refused")):
        result = srv.get_question_results(question_id=1)

    assert "error" in result, f"Expected 'error' on ConnectionError: {result}"

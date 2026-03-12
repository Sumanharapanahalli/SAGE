"""
SAGE[ai] - Metabase Analytics MCP Server
==========================================
FastMCP server for querying Metabase dashboards and error metrics.
Supports polling for new manufacturing errors detected in Metabase questions.
"""

import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

from fastmcp import FastMCP

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

mcp = FastMCP("SAGE Metabase Server")

# ---------------------------------------------------------------------------
# Config from environment variables
# ---------------------------------------------------------------------------
METABASE_URL = os.environ.get("METABASE_URL", "").rstrip("/")
METABASE_USERNAME = os.environ.get("METABASE_USERNAME", "")
METABASE_PASSWORD = os.environ.get("METABASE_PASSWORD", "")
METABASE_ERROR_QUESTION_ID = os.environ.get("METABASE_ERROR_QUESTION_ID", "")

if not METABASE_URL:
    logger.warning("METABASE_URL not set. Metabase tools will return errors.")

# Session token cache
_session_cache: dict = {"token": None, "expires_at": 0.0}


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _get_session_token_internal() -> Optional[str]:
    """
    Authenticates with Metabase and returns a session token.
    Caches the token for 10 minutes to avoid repeated logins.
    """
    now = time.time()
    if _session_cache["token"] and now < _session_cache["expires_at"]:
        return _session_cache["token"]

    if not METABASE_URL:
        logger.error("METABASE_URL is not configured.")
        return None
    if not METABASE_USERNAME or not METABASE_PASSWORD:
        logger.error("METABASE_USERNAME or METABASE_PASSWORD not set.")
        return None

    try:
        resp = requests.post(
            f"{METABASE_URL}/api/session",
            json={"username": METABASE_USERNAME, "password": METABASE_PASSWORD},
            timeout=15,
        )
        resp.raise_for_status()
        token = resp.json().get("id")
        if not token:
            logger.error("Metabase login response missing 'id' token field.")
            return None

        _session_cache["token"] = token
        _session_cache["expires_at"] = now + 600  # cache 10 minutes
        logger.info("Metabase session token obtained (cached 10 min).")
        return token

    except requests.RequestException as e:
        logger.error("Metabase authentication failed: %s", e)
        return None


def _metabase_headers() -> dict:
    token = _get_session_token_internal()
    if not token:
        return {}
    return {"X-Metabase-Session": token, "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_session_token() -> dict:
    """
    Authenticates with Metabase and returns the session token info.
    Useful for verifying credentials are working.

    Returns:
        dict with 'token_obtained' bool and optional 'error'.
    """
    token = _get_session_token_internal()
    if token:
        return {"token_obtained": True, "cached_until": datetime.fromtimestamp(_session_cache["expires_at"]).isoformat()}
    return {"token_obtained": False, "error": "Authentication failed. Check METABASE_URL, METABASE_USERNAME, METABASE_PASSWORD."}


@mcp.tool()
def get_question_results(question_id: int) -> dict:
    """
    Runs a Metabase question (saved question/query) and returns its results.

    Args:
        question_id: The numeric ID of the Metabase question/card

    Returns:
        dict with 'columns', 'rows', 'row_count', or 'error'.
    """
    headers = _metabase_headers()
    if not headers:
        return {"error": "Not authenticated. Check Metabase credentials."}

    try:
        resp = requests.post(
            f"{METABASE_URL}/api/card/{question_id}/query/json",
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, list):
            columns = list(data[0].keys()) if data else []
            return {
                "question_id": question_id,
                "columns": columns,
                "rows": data,
                "row_count": len(data),
            }
        # Handle wrapped format
        if "data" in data:
            cols = [c.get("display_name", c.get("name", "")) for c in data["data"].get("cols", [])]
            rows_raw = data["data"].get("rows", [])
            rows = [dict(zip(cols, row)) for row in rows_raw]
            return {
                "question_id": question_id,
                "columns": cols,
                "rows": rows,
                "row_count": len(rows),
            }

        return {"question_id": question_id, "raw": data}

    except requests.RequestException as e:
        logger.error("Failed to query Metabase question %d: %s", question_id, e)
        return {"error": str(e), "question_id": question_id}


@mcp.tool()
def list_dashboards() -> dict:
    """
    Lists all available Metabase dashboards.

    Returns:
        dict with 'dashboards' list (id, name, description).
    """
    headers = _metabase_headers()
    if not headers:
        return {"error": "Not authenticated."}

    try:
        resp = requests.get(f"{METABASE_URL}/api/dashboard", headers=headers, timeout=30)
        resp.raise_for_status()
        dashboards = resp.json()
        result = [
            {
                "id": d.get("id"),
                "name": d.get("name"),
                "description": d.get("description", ""),
                "creator": d.get("creator", {}).get("email", ""),
            }
            for d in dashboards
        ]
        logger.info("Listed %d dashboards", len(result))
        return {"dashboards": result, "count": len(result)}

    except requests.RequestException as e:
        logger.error("Failed to list dashboards: %s", e)
        return {"error": str(e)}


@mcp.tool()
def get_dashboard(dashboard_id: int) -> dict:
    """
    Gets all cards (questions/visualizations) from a Metabase dashboard.

    Args:
        dashboard_id: The dashboard's numeric ID

    Returns:
        dict with 'dashboard_name', 'cards' list.
    """
    headers = _metabase_headers()
    if not headers:
        return {"error": "Not authenticated."}

    try:
        resp = requests.get(f"{METABASE_URL}/api/dashboard/{dashboard_id}", headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        cards = []
        for dc in data.get("ordered_cards", []):
            card = dc.get("card", {})
            cards.append({
                "card_id": card.get("id"),
                "name": card.get("name"),
                "description": card.get("description", ""),
                "display": card.get("display"),
                "collection": card.get("collection", {}).get("name", ""),
            })

        return {
            "dashboard_id": dashboard_id,
            "dashboard_name": data.get("name"),
            "description": data.get("description", ""),
            "cards": cards,
            "card_count": len(cards),
        }

    except requests.RequestException as e:
        logger.error("Failed to get dashboard %d: %s", dashboard_id, e)
        return {"error": str(e), "dashboard_id": dashboard_id}


@mcp.tool()
def search_errors(since_hours: int = 24) -> dict:
    """
    Queries the configured error question for errors in the last N hours.
    Uses METABASE_ERROR_QUESTION_ID environment variable.

    Args:
        since_hours: How many hours back to look (default 24)

    Returns:
        dict with 'errors' list and 'count', or 'error'.
    """
    if not METABASE_ERROR_QUESTION_ID:
        return {"error": "METABASE_ERROR_QUESTION_ID environment variable not set."}

    try:
        qid = int(METABASE_ERROR_QUESTION_ID)
    except ValueError:
        return {"error": f"METABASE_ERROR_QUESTION_ID '{METABASE_ERROR_QUESTION_ID}' is not a valid integer."}

    result = get_question_results(qid)
    if "error" in result:
        return result

    rows = result.get("rows", [])
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    # Attempt to filter by timestamp field (heuristic: look for time/date-like keys)
    filtered = []
    time_keys = [k for k in (rows[0].keys() if rows else []) if any(t in k.lower() for t in ["time", "date", "timestamp", "created", "occurred"])]

    for row in rows:
        if time_keys:
            try:
                ts_str = str(row[time_keys[0]])
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts >= cutoff:
                    filtered.append(row)
            except Exception:
                filtered.append(row)  # Include if we can't parse timestamp
        else:
            filtered.append(row)  # No timestamp field, include all

    logger.info("search_errors: %d rows from question %d, %d within last %dh", len(rows), qid, len(filtered), since_hours)
    return {
        "question_id": qid,
        "since_hours": since_hours,
        "errors": filtered,
        "count": len(filtered),
        "total_in_question": len(rows),
    }


@mcp.tool()
def get_new_errors(since_hours: int = 1) -> dict:
    """
    Checks for new errors in the last N hours. Convenience wrapper for monitoring.

    Args:
        since_hours: How many hours back to check (default 1)

    Returns:
        dict with 'new_errors' list, 'count', and 'has_new_errors' bool.
    """
    result = search_errors(since_hours=since_hours)
    if "error" in result:
        return result

    errors = result.get("errors", [])
    return {
        "since_hours": since_hours,
        "new_errors": errors,
        "count": len(errors),
        "has_new_errors": len(errors) > 0,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Standalone test helper
# ---------------------------------------------------------------------------

def test_connection():
    """Quick standalone test — verifies Metabase connection."""
    print("=== Metabase Server Standalone Test ===")
    print(f"URL: {METABASE_URL or '(not set)'}")
    print(f"Username: {METABASE_USERNAME or '(not set)'}")

    result = get_session_token()
    if result.get("token_obtained"):
        print(f"Authentication: OK (cached until {result.get('cached_until')})")
        dashboards = list_dashboards()
        if "error" not in dashboards:
            print(f"Dashboards found: {dashboards['count']}")
        else:
            print(f"Dashboard list error: {dashboards['error']}")
    else:
        print(f"Authentication FAILED: {result.get('error')}")
    print("=======================================")


if __name__ == "__main__":
    mcp.run()

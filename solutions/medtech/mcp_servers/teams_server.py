"""
SAGE[ai] - Microsoft Teams MCP Server
========================================
FastMCP server for Microsoft Teams via Graph API (reading) and
incoming webhooks (sending). Uses MSAL for OAuth2 client credentials flow.
"""

import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import requests

from fastmcp import FastMCP

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

# --- Optional MSAL import (graceful degradation) ---
try:
    import msal
    MSAL_AVAILABLE = True
except ImportError:
    logger.warning("msal not installed. Teams read tools require it. Install: pip install msal")
    MSAL_AVAILABLE = False

mcp = FastMCP("SAGE Teams Server")

# ---------------------------------------------------------------------------
# Config from environment variables
# ---------------------------------------------------------------------------
TEAMS_TENANT_ID = os.environ.get("TEAMS_TENANT_ID", "")
TEAMS_CLIENT_ID = os.environ.get("TEAMS_CLIENT_ID", "")
TEAMS_CLIENT_SECRET = os.environ.get("TEAMS_CLIENT_SECRET", "")
TEAMS_TEAM_ID = os.environ.get("TEAMS_TEAM_ID", "")
TEAMS_CHANNEL_ID = os.environ.get("TEAMS_CHANNEL_ID", "")
TEAMS_INCOMING_WEBHOOK_URL = os.environ.get("TEAMS_INCOMING_WEBHOOK_URL", "")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Token cache
_token_cache: dict = {"token": None, "expires_at": 0.0}

# Default error keywords to look for in Teams messages
DEFAULT_ERROR_KEYWORDS = ["error", "failure", "fault", "exception", "critical", "alarm", "alert", "fail"]


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _get_access_token_internal() -> Optional[str]:
    """
    Acquires a Graph API access token via MSAL client credentials flow.
    Caches the token until near expiry.
    """
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    if not MSAL_AVAILABLE:
        logger.error("msal not installed.")
        return None

    if not all([TEAMS_TENANT_ID, TEAMS_CLIENT_ID, TEAMS_CLIENT_SECRET]):
        logger.error("TEAMS_TENANT_ID, TEAMS_CLIENT_ID, TEAMS_CLIENT_SECRET must all be set.")
        return None

    try:
        authority = f"https://login.microsoftonline.com/{TEAMS_TENANT_ID}"
        app = msal.ConfidentialClientApplication(
            TEAMS_CLIENT_ID,
            authority=authority,
            client_credential=TEAMS_CLIENT_SECRET,
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

        if "access_token" not in result:
            logger.error("MSAL token acquisition failed: %s", result.get("error_description", result.get("error")))
            return None

        token = result["access_token"]
        expires_in = result.get("expires_in", 3600)
        _token_cache["token"] = token
        _token_cache["expires_at"] = now + expires_in
        logger.info("Graph API token acquired (expires in %ds).", expires_in)
        return token

    except Exception as e:
        logger.error("MSAL token acquisition exception: %s", e)
        return None


def _graph_headers() -> dict:
    token = _get_access_token_internal()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _graph_get(path: str, params: dict = None) -> tuple:
    """Authenticated GET to Graph API. Returns (data, error_string)."""
    headers = _graph_headers()
    if not headers:
        return None, "Not authenticated. Check Teams credentials and MSAL configuration."

    try:
        resp = requests.get(f"{GRAPH_BASE}{path}", headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json(), None
    except requests.RequestException as e:
        logger.error("Graph GET %s failed: %s", path, e)
        return None, str(e)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_access_token() -> dict:
    """
    Acquires a Microsoft Graph API access token using MSAL client credentials.
    Useful for verifying authentication configuration.

    Returns:
        dict with 'token_obtained' bool and expiry info.
    """
    token = _get_access_token_internal()
    if token:
        expires_at = datetime.fromtimestamp(_token_cache["expires_at"]).isoformat()
        return {"token_obtained": True, "expires_at": expires_at}
    return {
        "token_obtained": False,
        "error": "Authentication failed. Check TEAMS_TENANT_ID, TEAMS_CLIENT_ID, TEAMS_CLIENT_SECRET.",
        "msal_available": MSAL_AVAILABLE,
    }


@mcp.tool()
def list_team_channels(team_id: str) -> dict:
    """
    Lists all channels in a Microsoft Teams team.

    Args:
        team_id: The Teams team ID (GUID)

    Returns:
        dict with 'channels' list (id, name, description).
    """
    data, err = _graph_get(f"/teams/{team_id}/channels")
    if err:
        return {"error": err, "team_id": team_id}

    channels = []
    for ch in data.get("value", []):
        channels.append({
            "id": ch.get("id"),
            "name": ch.get("displayName"),
            "description": ch.get("description", ""),
            "membership_type": ch.get("membershipType", "standard"),
        })

    logger.info("Listed %d channels for team %s", len(channels), team_id)
    return {"channels": channels, "count": len(channels), "team_id": team_id}


@mcp.tool()
def get_recent_messages(team_id: str, channel_id: str, top: int = 20) -> dict:
    """
    Gets the most recent messages from a Teams channel.

    Args:
        team_id:    Teams team ID
        channel_id: Channel ID
        top:        Maximum number of messages to return (default 20, max 50)

    Returns:
        dict with 'messages' list.
    """
    top = min(top, 50)
    data, err = _graph_get(
        f"/teams/{team_id}/channels/{channel_id}/messages",
        params={"$top": top},
    )
    if err:
        return {"error": err}

    messages = []
    for m in data.get("value", []):
        body = m.get("body", {})
        from_user = m.get("from", {})
        user_info = from_user.get("user", {}) or from_user.get("application", {})

        messages.append({
            "id": m.get("id"),
            "created_datetime": m.get("createdDateTime", ""),
            "last_modified": m.get("lastModifiedDateTime", ""),
            "from": user_info.get("displayName", "Unknown"),
            "content_type": body.get("contentType", "text"),
            "content": body.get("content", ""),
            "importance": m.get("importance", "normal"),
            "subject": m.get("subject", ""),
        })

    logger.info("Fetched %d messages from channel %s", len(messages), channel_id)
    return {"messages": messages, "count": len(messages), "team_id": team_id, "channel_id": channel_id}


@mcp.tool()
def get_messages_since(team_id: str, channel_id: str, since_minutes: int = 60) -> dict:
    """
    Gets messages from a Teams channel sent in the last N minutes.

    Args:
        team_id:        Teams team ID
        channel_id:     Channel ID
        since_minutes:  How many minutes back to retrieve (default 60)

    Returns:
        dict with 'messages' list filtered by recency.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    data, err = _graph_get(
        f"/teams/{team_id}/channels/{channel_id}/messages",
        params={"$top": 50, "$filter": f"createdDateTime ge {cutoff_str}"},
    )
    if err:
        # Graph may not support $filter on messages — fall back to top 50 and filter client-side
        logger.warning("Server-side filter failed (%s), falling back to client-side filter.", err)
        data, err2 = _graph_get(
            f"/teams/{team_id}/channels/{channel_id}/messages",
            params={"$top": 50},
        )
        if err2:
            return {"error": err2}

    messages = []
    for m in data.get("value", []):
        created = m.get("createdDateTime", "")
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if created_dt < cutoff:
                continue
        except Exception:
            pass  # Include if we can't parse

        body = m.get("body", {})
        from_user = m.get("from", {})
        user_info = from_user.get("user", {}) or from_user.get("application", {})
        messages.append({
            "id": m.get("id"),
            "created_datetime": created,
            "from": user_info.get("displayName", "Unknown"),
            "content": body.get("content", ""),
            "importance": m.get("importance", "normal"),
        })

    logger.info("Found %d messages in last %d minutes in channel %s", len(messages), since_minutes, channel_id)
    return {
        "messages": messages,
        "count": len(messages),
        "since_minutes": since_minutes,
        "since_datetime": cutoff_str,
    }


@mcp.tool()
def search_error_messages(team_id: str, channel_id: str, keywords: Optional[List[str]] = None) -> dict:
    """
    Fetches recent channel messages and filters for those containing error-related keywords.

    Args:
        team_id:    Teams team ID
        channel_id: Channel ID
        keywords:   List of keywords to search for (default: common error terms)

    Returns:
        dict with 'error_messages' list.
    """
    if keywords is None:
        keywords = DEFAULT_ERROR_KEYWORDS

    result = get_recent_messages(team_id, channel_id, top=50)
    if "error" in result:
        return result

    error_msgs = []
    keywords_lower = [k.lower() for k in keywords]

    for msg in result.get("messages", []):
        content_lower = msg.get("content", "").lower()
        matched_keywords = [k for k in keywords_lower if k in content_lower]
        if matched_keywords:
            msg["matched_keywords"] = matched_keywords
            error_msgs.append(msg)

    logger.info("Found %d error-related messages (keywords: %s)", len(error_msgs), keywords)
    return {
        "error_messages": error_msgs,
        "count": len(error_msgs),
        "keywords_searched": keywords,
        "team_id": team_id,
        "channel_id": channel_id,
    }


@mcp.tool()
def send_notification(webhook_url: str, title: str, message: str, color: str = "0078D7") -> dict:
    """
    Sends a notification to a Teams channel via an incoming webhook (Adaptive Card).

    Args:
        webhook_url: The Teams incoming webhook URL
        title:       Card title
        message:     Message body text
        color:       Hex accent color (default Microsoft blue: 0078D7)

    Returns:
        dict with 'status' or 'error'.
    """
    if not webhook_url:
        return {"error": "webhook_url is required."}

    card = _build_adaptive_card_internal(
        title=title,
        body_items=[{"type": "TextBlock", "text": message, "wrap": True}],
    )

    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": card,
            }
        ],
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        logger.info("Teams notification sent: '%s'", title)
        return {"status": "sent", "title": title}
    except requests.RequestException as e:
        logger.error("Failed to send Teams notification: %s", e)
        return {"error": str(e), "title": title}


@mcp.tool()
def send_alert(title: str, message: str, severity: str = "info") -> dict:
    """
    Sends an alert to the configured Teams webhook channel.
    Uses TEAMS_INCOMING_WEBHOOK_URL environment variable.

    Args:
        title:    Alert title
        message:  Alert message body
        severity: 'info', 'warning', 'error', 'critical'

    Returns:
        dict with 'status' or 'error'.
    """
    if not TEAMS_INCOMING_WEBHOOK_URL:
        return {"error": "TEAMS_INCOMING_WEBHOOK_URL environment variable not set."}

    severity_colors = {
        "info": "0078D7",      # Blue
        "warning": "FF8C00",   # Orange
        "error": "D13438",     # Red
        "critical": "8B0000",  # Dark Red
    }
    color = severity_colors.get(severity.lower(), "0078D7")

    severity_emoji = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "critical": "🚨",
    }
    icon = severity_emoji.get(severity.lower(), "")

    return send_notification(
        webhook_url=TEAMS_INCOMING_WEBHOOK_URL,
        title=f"{icon} [{severity.upper()}] {title}",
        message=message,
        color=color,
    )


# ---------------------------------------------------------------------------
# Internal Helpers (also exposed for testing)
# ---------------------------------------------------------------------------

def _build_adaptive_card_internal(title: str, body_items: list, actions: list = None) -> dict:
    """Builds a Teams Adaptive Card JSON structure."""
    body = [
        {
            "type": "TextBlock",
            "size": "Medium",
            "weight": "Bolder",
            "text": title,
            "wrap": True,
        }
    ] + body_items

    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body,
    }

    if actions:
        card["actions"] = actions

    return card


# ---------------------------------------------------------------------------
# Standalone test helper
# ---------------------------------------------------------------------------

def test_connection():
    """Quick standalone test — verifies Teams authentication."""
    print("=== Teams Server Standalone Test ===")
    print(f"Tenant ID: {TEAMS_TENANT_ID or '(not set)'}")
    print(f"Client ID: {TEAMS_CLIENT_ID or '(not set)'}")
    print(f"Webhook URL: {'(set)' if TEAMS_INCOMING_WEBHOOK_URL else '(not set)'}")
    print(f"MSAL available: {MSAL_AVAILABLE}")

    result = get_access_token()
    if result.get("token_obtained"):
        print(f"Graph API auth: OK (expires {result.get('expires_at')})")
        if TEAMS_TEAM_ID:
            channels = list_team_channels(TEAMS_TEAM_ID)
            if "error" not in channels:
                print(f"Channels in team: {channels['count']}")
    else:
        print(f"Graph API auth FAILED: {result.get('error')}")

    if TEAMS_INCOMING_WEBHOOK_URL:
        print("Testing webhook send...")
        r = send_alert("SAGE[ai] Test", "This is a connectivity test from SAGE[ai] MCP server.", "info")
        print(f"Webhook result: {r.get('status', r.get('error'))}")
    print("=====================================")


if __name__ == "__main__":
    mcp.run()

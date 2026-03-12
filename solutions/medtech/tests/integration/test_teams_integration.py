"""
SAGE[ai] - Microsoft Teams Integration Tests

These tests connect to a REAL Microsoft Teams instance via Graph API.
All tests are skipped if Teams credentials are not configured.

Requires environment variables:
  TEAMS_TENANT_ID        — Azure AD tenant GUID
  TEAMS_CLIENT_ID        — Azure AD app client ID
  TEAMS_CLIENT_SECRET    — Azure AD app client secret
  TEAMS_TEAM_ID          — Teams team GUID
  TEAMS_CHANNEL_ID       — Teams channel GUID
  TEAMS_INCOMING_WEBHOOK_URL — Teams incoming webhook URL (optional, for send tests)
"""

import os

import pytest


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def require_teams_credentials():
    """Skip all tests if Teams credentials are not configured."""
    required = ["TEAMS_TENANT_ID", "TEAMS_CLIENT_ID", "TEAMS_CLIENT_SECRET"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        pytest.skip(f"Teams credentials not configured (missing: {', '.join(missing)}) — skipping Teams integration tests.")


def test_teams_authentication():
    """Verify MSAL token acquisition works with configured credentials."""
    from mcp_servers.teams_server import get_access_token
    result = get_access_token()
    assert result.get("token_obtained") is True, (
        f"Teams authentication failed: {result.get('error')}"
    )
    assert "expires_at" in result, "Expected 'expires_at' in auth result."


def test_list_team_channels_live():
    """List channels in the configured team — verify response structure."""
    team_id = os.environ.get("TEAMS_TEAM_ID")
    if not team_id:
        pytest.skip("TEAMS_TEAM_ID not set — skipping channel list test.")
    from mcp_servers.teams_server import list_team_channels
    result = list_team_channels(team_id=team_id)
    assert "error" not in result, f"list_team_channels() returned error: {result.get('error')}"
    assert "channels" in result, f"Expected 'channels' in result: {result}"
    assert isinstance(result["channels"], list)
    if result["count"] > 0:
        ch = result["channels"][0]
        for field in ("id", "name"):
            assert field in ch, f"Expected '{field}' in channel dict: {ch}"


def test_get_recent_messages_live():
    """Fetch recent messages from the configured channel — verify structure."""
    team_id = os.environ.get("TEAMS_TEAM_ID")
    channel_id = os.environ.get("TEAMS_CHANNEL_ID")
    if not team_id or not channel_id:
        pytest.skip("TEAMS_TEAM_ID or TEAMS_CHANNEL_ID not set — skipping message fetch test.")
    from mcp_servers.teams_server import get_recent_messages
    result = get_recent_messages(team_id=team_id, channel_id=channel_id, top=5)
    assert "error" not in result, f"get_recent_messages() returned error: {result.get('error')}"
    assert "messages" in result, f"Expected 'messages' in result: {result}"
    assert isinstance(result["messages"], list)


def test_send_notification_via_webhook():
    """Send a test notification to the configured webhook — verify 200 status."""
    webhook_url = os.environ.get("TEAMS_INCOMING_WEBHOOK_URL")
    if not webhook_url:
        pytest.skip("TEAMS_INCOMING_WEBHOOK_URL not set — skipping webhook send test.")
    from mcp_servers.teams_server import send_notification
    result = send_notification(
        webhook_url=webhook_url,
        title="SAGE[ai] Integration Test",
        message="This is an automated integration test message from the SAGE[ai] test suite.",
    )
    assert result.get("status") == "sent", f"Webhook send failed: {result.get('error')}"

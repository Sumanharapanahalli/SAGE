"""
SAGE Framework — Slack Two-Way Approval
=========================================
Sends agent proposals to a Slack channel with Approve / Reject buttons.
Listens for button-click callbacks via POST /webhook/slack and routes
the decision back into the SAGE audit log and approval gate.

Configuration (environment variables):
  SLACK_BOT_TOKEN    — xoxb-... Bot OAuth token (required to send messages)
  SLACK_CHANNEL      — channel ID or name (default: #sage-approvals)
  SLACK_SIGNING_SECRET — for verifying request signatures from Slack

Graceful degradation:
  If SLACK_BOT_TOKEN is not set, send_proposal() logs a warning and returns
  a stub result — SAGE continues operating without Slack.
"""

import hashlib
import hmac
import json
import logging
import os
import time

logger = logging.getLogger("SlackApprover")

_HAS_SLACK = False
_slack_client = None

def _init_slack():
    """Lazy-init the Slack WebClient."""
    global _HAS_SLACK, _slack_client
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        return False
    try:
        from slack_sdk import WebClient
        _slack_client = WebClient(token=token)
        _HAS_SLACK = True
        logger.info("Slack WebClient initialised")
        return True
    except ImportError:
        logger.warning(
            "slack_sdk not installed — Slack integration unavailable. "
            "Install with: pip install slack-sdk"
        )
        return False


def _build_proposal_blocks(proposal: dict) -> list:
    """Build Slack Block Kit message for an agent proposal."""
    trace_id     = proposal.get("trace_id", "unknown")
    summary      = proposal.get("summary", "")[:2000]
    action_type  = proposal.get("action_type", "PROPOSE")
    actor        = proposal.get("actor", "SAGE Agent")

    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🤖 SAGE Proposal — {action_type}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Agent:*\n{actor}"},
                {"type": "mrkdwn", "text": f"*Trace ID:*\n`{trace_id}`"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Proposed Action:*\n{summary}"},
        },
        {"type": "divider"},
        {
            "type": "actions",
            "block_id": f"approval_{trace_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Approve"},
                    "style": "primary",
                    "action_id": "approve",
                    "value": json.dumps({"trace_id": trace_id, "decision": "approved"}),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject"},
                    "style": "danger",
                    "action_id": "reject",
                    "value": json.dumps({"trace_id": trace_id, "decision": "rejected"}),
                },
            ],
        },
    ]


def send_proposal(proposal: dict) -> dict:
    """
    Send a SAGE agent proposal to the configured Slack channel.

    Args:
        proposal: dict with trace_id, summary, action_type, actor.

    Returns:
        {"status": "sent", "channel": ..., "ts": ...}
        or {"status": "skipped", "reason": ...} when Slack is not configured.
    """
    if not _HAS_SLACK and not _init_slack():
        reason = (
            "SLACK_BOT_TOKEN not set" if not os.environ.get("SLACK_BOT_TOKEN")
            else "slack_sdk not installed"
        )
        logger.info("Slack proposal skipped: %s", reason)
        return {"status": "skipped", "reason": reason}

    channel = os.environ.get("SLACK_CHANNEL", "#sage-approvals")
    blocks  = _build_proposal_blocks(proposal)

    try:
        response = _slack_client.chat_postMessage(
            channel=channel,
            text=f"SAGE Proposal [{proposal.get('action_type', 'ACTION')}] — approval required",
            blocks=blocks,
        )
        logger.info("Proposal sent to Slack channel %s (ts: %s)", channel, response["ts"])
        return {
            "status":  "sent",
            "channel": response.get("channel"),
            "ts":      response.get("ts"),
        }
    except Exception as exc:
        logger.error("Slack send_proposal failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    """
    Verify Slack's X-Slack-Signature header to prevent spoofed callbacks.
    Returns True if valid, False otherwise.
    Skips verification when SLACK_SIGNING_SECRET is not set.
    """
    secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if not secret:
        return True   # no secret configured — accept all (dev mode)

    # Reject stale requests (> 5 minutes old)
    try:
        if abs(time.time() - float(timestamp)) > 300:
            logger.warning("Slack request timestamp too old — rejected")
            return False
    except (ValueError, TypeError):
        return False

    base = f"v0:{timestamp}:{body.decode('utf-8', errors='replace')}"
    computed = "v0=" + hmac.new(
        secret.encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


def parse_action_payload(payload_str: str) -> dict:
    """
    Parse a Slack interactive payload JSON string into a standardised dict.

    Returns:
        {
            trace_id: str,
            decision: "approved" | "rejected",
            user: str,
            action_ts: str,
        }
    """
    try:
        payload = json.loads(payload_str)
        actions = payload.get("actions", [{}])
        action  = actions[0] if actions else {}
        value   = json.loads(action.get("value", "{}"))
        user    = payload.get("user", {}).get("username", "unknown_user")
        return {
            "trace_id":  value.get("trace_id", ""),
            "decision":  value.get("decision", ""),
            "user":      user,
            "action_ts": payload.get("action_ts", ""),
        }
    except Exception as exc:
        logger.error("Failed to parse Slack action payload: %s", exc)
        return {}

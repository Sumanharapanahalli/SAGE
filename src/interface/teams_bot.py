"""
SAGE[ai] - Teams Bot Interface
================================
Sends structured notifications to Microsoft Teams via incoming webhooks.
Receives events via Microsoft Graph API subscriptions.

Uses adaptive cards for rich formatting and action buttons.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

import requests
import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "config.yaml",
)


def _load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


class TeamsBot:
    """
    Microsoft Teams notification bot using incoming webhooks.

    Sends adaptive cards for:
      - Analysis alerts (AI proposals)
      - MR creation notifications
      - Error alerts
      - Human approval requests (with action buttons)
    """

    def __init__(self):
        self.logger = logging.getLogger("TeamsBot")
        config = _load_config()
        teams_cfg = config.get("teams", {})

        self.webhook_url = os.environ.get(
            "TEAMS_INCOMING_WEBHOOK_URL",
            str(teams_cfg.get("webhook_url", "")).replace("${TEAMS_INCOMING_WEBHOOK_URL}", ""),
        )

        if not self.webhook_url:
            self.logger.warning("TEAMS_INCOMING_WEBHOOK_URL not set. Teams notifications will fail.")

    # -----------------------------------------------------------------------
    # Public Notification Methods
    # -----------------------------------------------------------------------

    def send_analysis_alert(self, analysis: dict) -> dict:
        """
        Sends an AI analysis proposal to the Teams channel.

        Args:
            analysis: Analysis dict from AnalystAgent (severity, root_cause_hypothesis,
                      recommended_action, trace_id)

        Returns:
            dict with 'status' or 'error'.
        """
        severity = analysis.get("severity", "UNKNOWN")
        root_cause = analysis.get("root_cause_hypothesis", "Unknown")
        action = analysis.get("recommended_action", "No action specified")
        trace_id = analysis.get("trace_id", "N/A")

        severity_colors = {
            "CRITICAL": "D13438",
            "HIGH": "FF8C00",
            "MEDIUM": "FFC300",
            "LOW": "28A745",
            "UNKNOWN": "6C757D",
        }
        color = severity_colors.get(severity.upper(), "6C757D")

        body_items = [
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Severity", "value": severity},
                    {"title": "Root Cause", "value": root_cause},
                    {"title": "Recommended Action", "value": action},
                    {"title": "Trace ID", "value": trace_id},
                    {"title": "Timestamp", "value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
                ],
            }
        ]

        card = self._build_adaptive_card(
            title=f"SAGE[ai] Analysis Alert — Severity: {severity}",
            body_items=body_items,
        )

        return self._post_to_webhook(card)

    def send_mr_created(self, mr_url: str, issue_title: str) -> dict:
        """
        Notifies the Teams channel that a merge request was created.

        Args:
            mr_url:      GitLab MR URL
            issue_title: Title of the source issue

        Returns:
            dict with 'status' or 'error'.
        """
        body_items = [
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Issue", "value": issue_title},
                    {"title": "MR URL", "value": mr_url},
                    {"title": "Created by", "value": "SAGE[ai] Developer Agent"},
                    {"title": "Timestamp", "value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
                ],
            }
        ]

        actions = [
            {
                "type": "Action.OpenUrl",
                "title": "View Merge Request",
                "url": mr_url,
            }
        ]

        card = self._build_adaptive_card(
            title="SAGE[ai] — Merge Request Created",
            body_items=body_items,
            actions=actions,
        )

        return self._post_to_webhook(card)

    def send_error_alert(self, error: str, severity: str = "error") -> dict:
        """
        Sends an error/system alert to the Teams channel.

        Args:
            error:    Error message text
            severity: 'info', 'warning', 'error', or 'critical'

        Returns:
            dict with 'status' or 'error'.
        """
        severity_colors = {
            "info": "0078D7",
            "warning": "FF8C00",
            "error": "D13438",
            "critical": "8B0000",
        }
        color = severity_colors.get(severity.lower(), "D13438")

        body_items = [
            {
                "type": "TextBlock",
                "text": error,
                "wrap": True,
                "color": "Attention" if severity in ("error", "critical") else "Default",
            },
            {
                "type": "TextBlock",
                "text": f"Reported at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                "isSubtle": True,
                "size": "Small",
            },
        ]

        card = self._build_adaptive_card(
            title=f"SAGE[ai] System Alert [{severity.upper()}]",
            body_items=body_items,
        )

        return self._post_to_webhook(card)

    def send_approval_request(self, trace_id: str, proposal: dict, callback_url: str) -> dict:
        """
        Sends an actionable approval request card to the Teams channel.
        Includes Approve/Reject action buttons pointing to the callback URL.

        Args:
            trace_id:     Unique trace ID for the proposal
            proposal:     The AI proposal dict (summary, recommended_action, etc.)
            callback_url: Base URL for approval API endpoint (e.g. 'http://localhost:8000')

        Returns:
            dict with 'status' or 'error'.
        """
        summary = proposal.get("summary", proposal.get("root_cause_hypothesis", "See details"))
        action = proposal.get("recommended_action", proposal.get("suggestions", ["See details"])[0] if proposal.get("suggestions") else "Manual review")

        body_items = [
            {
                "type": "TextBlock",
                "text": "SAGE[ai] requires human approval before proceeding.",
                "wrap": True,
                "weight": "Bolder",
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Trace ID", "value": trace_id},
                    {"title": "Summary", "value": summary},
                    {"title": "Proposed Action", "value": action},
                    {"title": "Requested at", "value": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")},
                ],
            },
            {
                "type": "TextBlock",
                "text": "Please review and approve or reject this proposal:",
                "wrap": True,
                "isSubtle": True,
            },
        ]

        actions = [
            {
                "type": "Action.OpenUrl",
                "title": "✅ Approve",
                "url": f"{callback_url}/approve/{trace_id}",
                "style": "positive",
            },
            {
                "type": "Action.OpenUrl",
                "title": "❌ Reject",
                "url": f"{callback_url}/reject/{trace_id}",
                "style": "destructive",
            },
        ]

        card = self._build_adaptive_card(
            title="SAGE[ai] — Approval Required",
            body_items=body_items,
            actions=actions,
        )

        return self._post_to_webhook(card)

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------

    def _build_adaptive_card(self, title: str, body_items: list, actions: list = None) -> dict:
        """
        Builds a Teams Adaptive Card JSON payload.

        Args:
            title:      Card header title
            body_items: List of adaptive card body element dicts
            actions:    Optional list of action button dicts

        Returns:
            Full message payload dict ready for posting to webhook.
        """
        card_body = [
            {
                "type": "TextBlock",
                "size": "Medium",
                "weight": "Bolder",
                "text": title,
                "wrap": True,
            }
        ] + body_items

        card_content = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": card_body,
        }

        if actions:
            card_content["actions"] = actions

        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": card_content,
                }
            ],
        }

    def _post_to_webhook(self, card: dict) -> dict:
        """
        HTTP POSTs an adaptive card payload to the configured Teams webhook URL.

        Args:
            card: Full message payload dict (as returned by _build_adaptive_card)

        Returns:
            dict with 'status' or 'error'.
        """
        if not self.webhook_url:
            return {"error": "TEAMS_INCOMING_WEBHOOK_URL not configured."}

        try:
            resp = requests.post(
                self.webhook_url,
                json=card,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            self.logger.info("Teams notification sent successfully (HTTP %d).", resp.status_code)
            return {"status": "sent", "http_status": resp.status_code}
        except requests.RequestException as e:
            self.logger.error("Teams webhook POST failed: %s", e)
            return {"error": str(e)}


# ---------------------------------------------------------------------------
# Global access point
# ---------------------------------------------------------------------------
teams_bot = TeamsBot()

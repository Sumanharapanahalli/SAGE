"""
SAGE Framework — Phase 2 n8n Webhook Tests
============================================
Tests for POST /webhook/n8n:
  - Valid payload routes to task queue
  - event_type mapping to SAGE task types
  - Missing event_type returns 400
  - HMAC signature validation (accept valid, reject tampered)
  - Source is audited
"""

import hashlib
import hmac as hmac_lib
import json
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def _client():
    from src.interface.api import app
    return TestClient(app, raise_server_exceptions=False)


def _mock_queue():
    q = MagicMock()
    q.submit.return_value = "task_abc123"
    return q


def _mock_audit():
    a = MagicMock()
    a.log_event.return_value = "event_xyz"
    return a


# ---------------------------------------------------------------------------
# Event routing tests
# ---------------------------------------------------------------------------

class TestN8nWebhookRouting:

    def test_log_alert_routes_to_analyze_log(self):
        """event_type 'log_alert' must route to ANALYZE_LOG task type."""
        with patch("src.interface.api._get_task_queue", return_value=_mock_queue()) as mock_q, \
             patch("src.interface.api._get_audit_logger", return_value=_mock_audit()):
            mock_q.return_value = _mock_queue()
            q = _mock_queue()
            with patch("src.interface.api._get_task_queue", return_value=q):
                resp = _client().post("/webhook/n8n", json={
                    "event_type": "log_alert",
                    "payload": {"log_entry": "Error: stack overflow"},
                    "source": "pagerduty",
                })
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_type"] == "ANALYZE_LOG"
        assert data["status"] == "queued"

    def test_code_review_routes_to_review_mr(self):
        """event_type 'code_review' must route to REVIEW_MR."""
        q = _mock_queue()
        with patch("src.interface.api._get_task_queue", return_value=q), \
             patch("src.interface.api._get_audit_logger", return_value=_mock_audit()):
            resp = _client().post("/webhook/n8n", json={
                "event_type": "code_review",
                "payload": {"project_id": "1", "mr_iid": 42},
                "source": "gitlab",
            })
        assert resp.status_code == 200
        assert resp.json()["task_type"] == "REVIEW_MR"

    def test_monitor_event_routes_to_monitor_check(self):
        """event_type 'monitor' must route to MONITOR_CHECK."""
        q = _mock_queue()
        with patch("src.interface.api._get_task_queue", return_value=q), \
             patch("src.interface.api._get_audit_logger", return_value=_mock_audit()):
            resp = _client().post("/webhook/n8n", json={
                "event_type": "monitor",
                "source": "cron",
            })
        assert resp.status_code == 200
        assert resp.json()["task_type"] == "MONITOR_CHECK"

    def test_unknown_event_type_uppercased_as_task_type(self):
        """Unknown event_type values should be uppercased and passed through."""
        q = _mock_queue()
        with patch("src.interface.api._get_task_queue", return_value=q), \
             patch("src.interface.api._get_audit_logger", return_value=_mock_audit()):
            resp = _client().post("/webhook/n8n", json={
                "event_type": "custom_analysis",
                "source": "my_system",
            })
        assert resp.status_code == 200
        assert resp.json()["task_type"] == "CUSTOM_ANALYSIS"

    def test_missing_event_type_returns_400(self):
        """Missing event_type must return 400 Bad Request."""
        resp = _client().post("/webhook/n8n", json={"payload": {}})
        assert resp.status_code == 400

    def test_task_id_returned_in_response(self):
        """Response must include the task_id assigned by the queue."""
        q = _mock_queue()
        q.submit.return_value = "task_unique_999"
        with patch("src.interface.api._get_task_queue", return_value=q), \
             patch("src.interface.api._get_audit_logger", return_value=_mock_audit()):
            resp = _client().post("/webhook/n8n", json={"event_type": "monitor"})
        assert resp.json()["task_id"] == "task_unique_999"

    def test_source_field_returned_in_response(self):
        """Source field passed in body must be echoed back in response."""
        q = _mock_queue()
        with patch("src.interface.api._get_task_queue", return_value=q), \
             patch("src.interface.api._get_audit_logger", return_value=_mock_audit()):
            resp = _client().post("/webhook/n8n", json={
                "event_type": "monitor",
                "source": "slack_alert",
            })
        assert resp.json()["source"] == "slack_alert"


# ---------------------------------------------------------------------------
# HMAC signature validation tests
# ---------------------------------------------------------------------------

class TestN8nHMAC:

    def _signed_request(self, body: dict, secret: str, tamper: bool = False) -> tuple:
        """Return (headers, raw_body) with a valid or tampered HMAC signature."""
        raw = json.dumps(body).encode()
        sig = "sha256=" + hmac_lib.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if tamper:
            sig = sig[:-4] + "XXXX"
        return {"X-SAGE-Signature": sig, "Content-Type": "application/json"}, raw

    def test_valid_signature_accepted(self):
        """Valid HMAC signature must be accepted (200)."""
        secret = "test_secret_key"
        body   = {"event_type": "monitor", "source": "n8n_test"}
        headers, raw = self._signed_request(body, secret)

        q = _mock_queue()
        env = {**os.environ, "N8N_WEBHOOK_SECRET": secret}
        with patch("src.interface.api._get_task_queue", return_value=q), \
             patch("src.interface.api._get_audit_logger", return_value=_mock_audit()), \
             patch.dict("os.environ", {"N8N_WEBHOOK_SECRET": secret}):
            resp = _client().post("/webhook/n8n", headers=headers, content=raw)
        assert resp.status_code == 200

    def test_tampered_signature_rejected(self):
        """Tampered HMAC signature must return 401."""
        secret = "test_secret_key"
        body   = {"event_type": "monitor"}
        headers, raw = self._signed_request(body, secret, tamper=True)

        with patch.dict("os.environ", {"N8N_WEBHOOK_SECRET": secret}):
            resp = _client().post("/webhook/n8n", headers=headers, content=raw)
        assert resp.status_code == 401

    def test_missing_signature_rejected_when_secret_set(self):
        """Missing X-SAGE-Signature header must return 401 when secret is configured."""
        with patch.dict("os.environ", {"N8N_WEBHOOK_SECRET": "some_secret"}):
            resp = _client().post(
                "/webhook/n8n",
                json={"event_type": "monitor"},
            )
        assert resp.status_code == 401

    def test_no_secret_no_validation(self):
        """When N8N_WEBHOOK_SECRET is not set, any request is accepted."""
        env = {k: v for k, v in os.environ.items() if k != "N8N_WEBHOOK_SECRET"}
        q = _mock_queue()
        with patch("src.interface.api._get_task_queue", return_value=q), \
             patch("src.interface.api._get_audit_logger", return_value=_mock_audit()), \
             patch.dict("os.environ", env, clear=True):
            resp = _client().post("/webhook/n8n", json={"event_type": "monitor"})
        assert resp.status_code == 200

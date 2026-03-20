# tests/test_onboarding_import_endpoints.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.interface.api import app

client = TestClient(app)


# ── PUT /org ──────────────────────────────────────────────────────────────────

def test_put_org_saves_mission():
    with patch("src.interface.api.reload_org_loader") as mock_reload:
        resp = client.put("/org", json={
            "name": "Acme Corp",
            "mission": "Make the world better",
            "vision": "A better world by 2040",
            "core_values": ["Integrity", "Speed"],
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "saved"
    assert "org" in data


def test_put_org_reloads_org_loader():
    with patch("src.interface.api.reload_org_loader") as mock_reload:
        client.put("/org", json={"mission": "Test mission"})
    mock_reload.assert_called_once()


def test_put_org_partial_update_accepted():
    """PUT /org with only mission field — should not error."""
    with patch("src.interface.api.reload_org_loader"):
        resp = client.put("/org", json={"mission": "Only mission"})
    assert resp.status_code == 200


def test_put_org_empty_body_accepted():
    """PUT /org with empty body — nothing to save, still 200."""
    with patch("src.interface.api.reload_org_loader"):
        resp = client.put("/org", json={})
    assert resp.status_code == 200

"""Tests for POST /knowledge/add — optional channel field with producer validation."""
from fastapi.testclient import TestClient
from src.interface.api import app

client = TestClient(app)


def test_knowledge_add_without_channel_unchanged():
    """Existing behaviour is unchanged when no channel is provided."""
    resp = client.post("/knowledge/add", json={"text": "some knowledge"})
    # Should NOT return 400 for channel reasons
    assert "not a producer" not in resp.json().get("detail", "")


def test_knowledge_add_unknown_channel_returns_400():
    resp = client.post("/knowledge/add", json={
        "text": "some knowledge",
        "channel": "nonexistent-channel-xyz",
    })
    assert resp.status_code == 400
    assert "not a producer" in resp.json().get("detail", "").lower()


def test_knowledge_add_valid_channel_does_not_return_400():
    from unittest.mock import patch, MagicMock
    mock_org = MagicMock()
    mock_org.get_producer_channel_name.return_value = "channel_hw_fw"
    mock_org.get_channel_db_path.return_value = None  # skip actual write
    with patch("src.core.org_loader.org_loader", mock_org):
        resp = client.post("/knowledge/add", json={
            "text": "sensor failure pattern discovered",
            "channel": "hw-fw",
        })
    # Should NOT return 400 for channel reasons
    assert resp.status_code != 400 or "not a producer" not in resp.json().get("detail", "")
    mock_org.get_producer_channel_name.assert_called_once()

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

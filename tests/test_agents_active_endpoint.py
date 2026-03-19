from fastapi.testclient import TestClient


def test_agents_active_returns_list():
    from src.interface.api import app
    client = TestClient(app)
    resp = client.get("/agents/active")
    assert resp.status_code == 200
    data = resp.json()
    assert "agents" in data
    assert isinstance(data["agents"], list)


def test_agents_active_schema():
    """Verify response schema: agents list and count field present and consistent."""
    from src.interface.api import app
    client = TestClient(app)
    resp = client.get("/agents/active")
    assert resp.status_code == 200
    data = resp.json()
    assert "agents" in data
    assert "count" in data
    assert isinstance(data["agents"], list)
    assert data["count"] == len(data["agents"])
    # Each entry must have the required fields
    for entry in data["agents"]:
        assert "task_id" in entry
        assert "task_type" in entry
        assert "status" in entry
        assert entry["status"] in ("in_progress", "pending")

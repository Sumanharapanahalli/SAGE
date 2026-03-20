"""Tests for GET /config/dev-users endpoint."""
import os
import pytest
from fastapi.testclient import TestClient


def test_dev_users_returns_list(monkeypatch, tmp_path):
    """Should return users from dev_users.yaml."""
    yaml_content = """
users:
  - id: alice
    name: Alice
    email: alice@example.com
    role: admin
    avatar_color: '#6366f1'
"""
    yaml_file = tmp_path / "dev_users.yaml"
    yaml_file.write_text(yaml_content)
    monkeypatch.setenv("SAGE_DEV_USERS_PATH", str(yaml_file))

    from src.interface.api import app
    client = TestClient(app)
    resp = client.get("/config/dev-users")
    assert resp.status_code == 200
    data = resp.json()
    assert "users" in data
    assert len(data["users"]) == 1
    assert data["users"][0]["id"] == "alice"
    assert data["users"][0]["role"] == "admin"


def test_dev_users_missing_file_returns_empty(monkeypatch, tmp_path):
    """Should return empty list when file doesn't exist."""
    monkeypatch.setenv("SAGE_DEV_USERS_PATH", str(tmp_path / "nonexistent.yaml"))

    from src.interface.api import app
    client = TestClient(app)
    resp = client.get("/config/dev-users")
    assert resp.status_code == 200
    assert resp.json() == {"users": []}

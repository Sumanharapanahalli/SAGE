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


# ── POST /onboarding/scan-folder ──────────────────────────────────────────────
import tempfile, os as _os


def test_scan_folder_nonexistent_returns_400():
    resp = client.post("/onboarding/scan-folder", json={
        "folder_path": "/nonexistent/path/xyz",
        "intent": "Build a QA agent",
        "solution_name": "test_qa",
    })
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "folder_not_found"


def test_scan_folder_empty_returns_400():
    with tempfile.TemporaryDirectory() as tmp:
        resp = client.post("/onboarding/scan-folder", json={
            "folder_path": tmp,
            "intent": "Build a QA agent",
            "solution_name": "test_qa",
        })
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "folder_empty"


def test_scan_folder_calls_llm_and_returns_files():
    mock_llm_response = '{"project.yaml": "name: Test QA\\ndomain: test-qa", "prompts.yaml": "roles: []", "tasks.yaml": "task_types: []"}'
    with tempfile.TemporaryDirectory() as tmp:
        with open(_os.path.join(tmp, "README.md"), "w") as f:
            f.write("# Test Project")
        with patch("src.interface.api._get_llm_gateway") as mock_gw:
            mock_gw.return_value.generate.return_value = mock_llm_response
            resp = client.post("/onboarding/scan-folder", json={
                "folder_path": tmp,
                "intent": "Build a QA agent",
                "solution_name": "test_qa",
            })
    assert resp.status_code == 200
    data = resp.json()
    assert "files" in data
    assert "project.yaml" in data["files"]
    assert "summary" in data


def test_scan_folder_missing_intent_returns_422():
    resp = client.post("/onboarding/scan-folder", json={
        "folder_path": "/any",
        "solution_name": "test_qa",
        # intent missing
    })
    assert resp.status_code == 422


# ── POST /onboarding/refine ───────────────────────────────────────────────────

def test_refine_calls_llm_with_feedback():
    current_files = {
        "project.yaml": "name: Test\ndomain: test",
        "prompts.yaml": "roles: []",
        "tasks.yaml": "task_types: []",
    }
    mock_response = '{"project.yaml": "name: Test QA\\ndomain: test-qa", "prompts.yaml": "roles: []", "tasks.yaml": "task_types: []"}'
    with patch("src.interface.api._get_llm_gateway") as mock_gw:
        mock_gw.return_value.generate.return_value = mock_response
        resp = client.post("/onboarding/refine", json={
            "solution_name": "test_qa",
            "current_files": current_files,
            "feedback": "Focus on firmware only",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "files" in data
    assert "summary" in data


def test_refine_missing_feedback_returns_422():
    resp = client.post("/onboarding/refine", json={
        "solution_name": "test_qa",
        "current_files": {"project.yaml": "", "prompts.yaml": "", "tasks.yaml": ""},
        # feedback missing
    })
    assert resp.status_code == 422


# ── POST /onboarding/save-solution ───────────────────────────────────────────

def test_save_solution_writes_files(tmp_path, monkeypatch):
    monkeypatch.setattr("src.core.project_loader._SOLUTIONS_DIR", str(tmp_path))
    resp = client.post("/onboarding/save-solution", json={
        "solution_name": "test_save",
        "files": {
            "project.yaml": "name: Test Save\ndomain: test-save",
            "prompts.yaml": "roles: {}",
            "tasks.yaml": "task_types: []",
        },
    })
    assert resp.status_code == 200
    assert (tmp_path / "test_save" / "project.yaml").exists()

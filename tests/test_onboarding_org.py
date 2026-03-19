"""Tests for onboarding enhancements: parent_solution, org_name, suggested_routes."""
from unittest.mock import patch, MagicMock


def test_onboarding_accepts_parent_solution_field():
    from fastapi.testclient import TestClient
    from src.interface.api import app
    client = TestClient(app)
    with patch("src.core.onboarding.generate_solution") as mock_gen:
        mock_gen.return_value = {
            "solution_name": "fw_team",
            "path": "/tmp/fw_team",
            "status": "created",
            "files": {"project.yaml": "name: fw_team\nparent: product_base\n"},
            "message": "Solution 'fw_team' created.",
            "suggested_routes": ["team_hw"],
        }
        resp = client.post("/onboarding/generate", json={
            "description": "Firmware team for IoT medical device",
            "solution_name": "fw_team",
            "parent_solution": "product_base",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "suggested_routes" in data
    assert isinstance(data["suggested_routes"], list)


def test_onboarding_suggested_routes_present_in_response():
    from fastapi.testclient import TestClient
    from src.interface.api import app
    client = TestClient(app)
    with patch("src.core.onboarding.generate_solution") as mock_gen:
        mock_gen.return_value = {
            "solution_name": "iot_fw",
            "path": "/tmp/iot_fw",
            "status": "created",
            "files": {},
            "message": "created",
            "suggested_routes": ["team_hw", "platform_infra"],
        }
        resp = client.post("/onboarding/generate", json={
            "description": "IoT firmware team",
            "solution_name": "iot_fw",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["suggested_routes"] == ["team_hw", "platform_infra"]


def test_onboarding_passes_parent_solution_to_generate():
    """Verify parent_solution is forwarded to generate_solution as a kwarg."""
    from fastapi.testclient import TestClient
    from src.interface.api import app
    client = TestClient(app)
    with patch("src.core.onboarding.generate_solution") as mock_gen:
        mock_gen.return_value = {
            "solution_name": "child",
            "path": "/tmp/child",
            "status": "created",
            "files": {},
            "message": "created",
            "suggested_routes": [],
        }
        client.post("/onboarding/generate", json={
            "description": "Child solution",
            "solution_name": "child",
            "parent_solution": "parent_base",
            "org_name": "acme",
        })
    call_kwargs = mock_gen.call_args
    assert call_kwargs is not None
    # Check that parent_solution and org_name were passed
    kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
    args = call_kwargs.args if call_kwargs.args else ()
    # parent_solution passed as keyword arg
    assert kwargs.get("parent_solution") == "parent_base" or "parent_base" in args
    assert kwargs.get("org_name") == "acme" or "acme" in args

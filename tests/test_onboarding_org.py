"""Tests for onboarding enhancements: parent_solution, org_name, suggested_routes."""
from unittest.mock import patch, MagicMock, ANY


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
    """Verify parent_solution and org_name are forwarded to generate_solution."""
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
    mock_gen.assert_called_once_with(
        description=ANY,
        solution_name=ANY,
        compliance_standards=ANY,
        integrations=ANY,
        parent_solution="parent_base",
        org_name="acme",
        org_context=ANY,
    )


def test_try_add_to_org_skips_when_org_name_mismatch(tmp_path):
    """_try_add_to_org must not modify org.yaml when the name field doesn't match."""
    import yaml
    from src.core.onboarding import _try_add_to_org

    # Write an org.yaml whose name is "other_org"
    org_yaml = tmp_path / "org.yaml"
    org_yaml.write_text(
        "org:\n  name: other_org\n  solutions:\n    - existing_sol\n",
        encoding="utf-8",
    )

    # Patch _SOLUTIONS_DIR so _try_add_to_org looks in tmp_path
    with patch("src.core.onboarding._SOLUTIONS_DIR", str(tmp_path)):
        _try_add_to_org(org_name="acme", solution_name="new_sol")

    # org.yaml must be unchanged — new_sol must NOT have been added
    with open(org_yaml, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert "new_sol" not in data["org"]["solutions"]
    assert data["org"]["solutions"] == ["existing_sol"]


def test_try_add_to_org_exception_branch_is_nonfatal(tmp_path):
    """_try_add_to_org must not raise when org.yaml contains invalid YAML."""
    from unittest.mock import patch
    from src.core.onboarding import _try_add_to_org

    # Write a malformed org.yaml that will cause yaml.safe_load to raise
    org_yaml = tmp_path / "org.yaml"
    org_yaml.write_text("{invalid: [unclosed", encoding="utf-8")

    # Patch _SOLUTIONS_DIR so the function finds the malformed file
    with patch("src.core.onboarding._SOLUTIONS_DIR", str(tmp_path)):
        # Must not raise — exception branch is non-fatal
        _try_add_to_org(org_name="acme", solution_name="new_sol")

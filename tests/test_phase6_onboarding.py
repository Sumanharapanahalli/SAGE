"""
SAGE Framework — Phase 6 Onboarding Wizard Tests
==================================================
Tests for:
  - generate_solution() creates the 3 YAML files in solutions/<name>/
  - generate_solution() returns status="exists" when dir already present
  - generate_solution() sanitizes solution_name to snake_case
  - _sanitize_name handles spaces, hyphens, uppercase
  - _extract_yaml strips markdown fences
  - _validate_yaml raises ValueError on bad YAML
  - POST /onboarding/generate returns 200 with created status
  - POST /onboarding/generate missing description returns 400
  - POST /onboarding/generate missing solution_name returns 400
  - POST /onboarding/generate returns exists when solution already present
  - GET /onboarding/templates returns list of available templates
"""

import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


MOCK_YAML = """
name: "Test Solution"
version: "1.0.0"
domain: "test"
description: A test solution.
active_modules:
  - dashboard
""".strip()


# ---------------------------------------------------------------------------
# Unit tests for onboarding module
# ---------------------------------------------------------------------------

class TestOnboardingModule:

    def test_sanitize_name_removes_spaces(self):
        from src.core.onboarding import _sanitize_name
        assert _sanitize_name("My Cool Solution") == "my_cool_solution"

    def test_sanitize_name_handles_hyphens(self):
        from src.core.onboarding import _sanitize_name
        assert _sanitize_name("agri-drones") == "agri_drones"

    def test_sanitize_name_lowercases(self):
        from src.core.onboarding import _sanitize_name
        assert _sanitize_name("FinTech Platform") == "fintech_platform"

    def test_sanitize_name_collapses_underscores(self):
        from src.core.onboarding import _sanitize_name
        assert _sanitize_name("foo__bar") == "foo_bar"

    def test_extract_yaml_strips_fences(self):
        from src.core.onboarding import _extract_yaml
        raw = "```yaml\nname: test\n```"
        assert _extract_yaml(raw) == "name: test"

    def test_extract_yaml_strips_plain_fences(self):
        from src.core.onboarding import _extract_yaml
        raw = "```\nkey: value\n```"
        assert _extract_yaml(raw) == "key: value"

    def test_extract_yaml_passthrough_clean(self):
        from src.core.onboarding import _extract_yaml
        raw = "key: value"
        assert _extract_yaml(raw) == "key: value"

    def test_validate_yaml_parses_valid(self):
        from src.core.onboarding import _validate_yaml
        result = _validate_yaml("name: test\nversion: '1.0'", "project.yaml")
        assert result["name"] == "test"

    def test_validate_yaml_raises_on_invalid(self):
        from src.core.onboarding import _validate_yaml
        with pytest.raises(ValueError, match="project.yaml"):
            _validate_yaml("key: [unclosed", "project.yaml")

    def test_validate_yaml_raises_on_non_dict(self):
        from src.core.onboarding import _validate_yaml
        with pytest.raises(ValueError):
            _validate_yaml("- item1\n- item2", "project.yaml")

    def test_generate_solution_creates_files(self):
        """generate_solution() must write 3 YAML files to solutions/<name>/."""
        import src.core.onboarding as ob_module
        mock_gw = MagicMock()
        mock_gw.generate.return_value = MOCK_YAML

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(ob_module, "_SOLUTIONS_DIR", tmpdir), \
                 patch("src.core.onboarding.llm_gateway", mock_gw):
                result = ob_module.generate_solution(
                    description="A test domain",
                    solution_name="test_sol",
                )

        assert result["status"] == "created"
        assert result["solution_name"] == "test_sol"
        assert "project.yaml" in result["files"]
        assert "prompts.yaml" in result["files"]
        assert "tasks.yaml" in result["files"]

    def test_generate_solution_returns_exists_when_dir_present(self):
        """generate_solution() must return status='exists' without overwriting."""
        import src.core.onboarding as ob_module

        with tempfile.TemporaryDirectory() as tmpdir:
            existing = os.path.join(tmpdir, "my_sol")
            os.makedirs(existing)
            with patch.object(ob_module, "_SOLUTIONS_DIR", tmpdir):
                result = ob_module.generate_solution(
                    description="A domain",
                    solution_name="my_sol",
                )

        assert result["status"] == "exists"
        assert result["files"] == {}

    def test_generate_solution_sanitizes_name(self):
        """generate_solution() must sanitize the solution_name."""
        import src.core.onboarding as ob_module
        mock_gw = MagicMock()
        mock_gw.generate.return_value = MOCK_YAML

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(ob_module, "_SOLUTIONS_DIR", tmpdir), \
                 patch("src.core.onboarding.llm_gateway", mock_gw):
                result = ob_module.generate_solution(
                    description="A test",
                    solution_name="My New Solution",
                )

        assert result["solution_name"] == "my_new_solution"

    def test_generate_solution_creates_subdirs(self):
        """generate_solution() must create workflows/, mcp_servers/, evals/ stubs."""
        import src.core.onboarding as ob_module
        mock_gw = MagicMock()
        mock_gw.generate.return_value = MOCK_YAML

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(ob_module, "_SOLUTIONS_DIR", tmpdir), \
                 patch("src.core.onboarding.llm_gateway", mock_gw):
                ob_module.generate_solution(
                    description="test",
                    solution_name="sub_test",
                )
            sol_dir = os.path.join(tmpdir, "sub_test")
            assert os.path.isdir(os.path.join(sol_dir, "workflows"))
            assert os.path.isdir(os.path.join(sol_dir, "mcp_servers"))
            assert os.path.isdir(os.path.join(sol_dir, "evals"))


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestOnboardingAPI:

    def _client(self):
        from src.interface.api import app
        return TestClient(app, raise_server_exceptions=False)

    def test_generate_returns_200(self):
        """POST /onboarding/generate with valid body must return 200."""
        import src.core.onboarding as ob_module
        mock_gw = MagicMock()
        mock_gw.generate.return_value = MOCK_YAML

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(ob_module, "_SOLUTIONS_DIR", tmpdir), \
                 patch("src.core.onboarding.llm_gateway", mock_gw):
                resp = self._client().post("/onboarding/generate", json={
                    "description": "We build agricultural drones for crop monitoring",
                    "solution_name": "agri_drones",
                })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert data["solution_name"] == "agri_drones"

    def test_generate_missing_description_returns_400(self):
        """POST /onboarding/generate without description must return 400."""
        resp = self._client().post("/onboarding/generate", json={"solution_name": "test"})
        assert resp.status_code == 400

    def test_generate_missing_solution_name_returns_400(self):
        """POST /onboarding/generate without solution_name must return 400."""
        resp = self._client().post("/onboarding/generate", json={"description": "A domain"})
        assert resp.status_code == 400

    def test_generate_existing_solution_returns_exists(self):
        """POST /onboarding/generate for existing solution must return status=exists."""
        import src.core.onboarding as ob_module

        with tempfile.TemporaryDirectory() as tmpdir:
            existing = os.path.join(tmpdir, "existing_sol")
            os.makedirs(existing)
            with patch.object(ob_module, "_SOLUTIONS_DIR", tmpdir):
                resp = self._client().post("/onboarding/generate", json={
                    "description": "Already exists",
                    "solution_name": "existing_sol",
                })

        assert resp.status_code == 200
        assert resp.json()["status"] == "exists"

    def test_templates_returns_list(self):
        """GET /onboarding/templates must return JSON with templates and count."""
        resp = self._client().get("/onboarding/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert "count" in data
        assert isinstance(data["templates"], list)
        assert data["count"] >= 0

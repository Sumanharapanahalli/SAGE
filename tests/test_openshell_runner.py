"""Tests for OpenShell runner integration."""
import os
import pytest
from unittest.mock import patch, MagicMock


def test_runner_detects_unavailable_when_not_installed():
    """When openshell is not on PATH, is_available() returns False."""
    with patch("shutil.which", return_value=None):
        from importlib import reload
        import src.integrations.openshell_runner as mod
        reload(mod)
        runner = mod.OpenShellRunner()
        assert not runner.is_available()


def test_runner_status_when_unavailable():
    with patch("shutil.which", return_value=None):
        from src.integrations.openshell_runner import OpenShellRunner
        runner = OpenShellRunner()
        runner._available = False
        runner._openshell_path = None
        status = runner.status()
        assert status["available"] is False
        assert "install" in status


def test_generate_policy_yaml_minimal():
    """generate_policy_yaml() produces valid YAML with version: 1."""
    from src.integrations.openshell_runner import OpenShellRunner
    runner = OpenShellRunner()
    yaml_str = runner.generate_policy_yaml({
        "filesystem_policy": {
            "include_workdir": True,
            "read_only": ["/usr", "/lib"],
            "read_write": ["/tmp"],
        }
    })
    import yaml
    parsed = yaml.safe_load(yaml_str)
    assert parsed["version"] == 1
    assert parsed["filesystem_policy"]["include_workdir"] is True
    assert "/usr" in parsed["filesystem_policy"]["read_only"]
    assert parsed["process"]["run_as_user"] == "sandbox"


def test_generate_policy_yaml_with_network():
    """Network policies are included when provided."""
    from src.integrations.openshell_runner import OpenShellRunner
    runner = OpenShellRunner()
    yaml_str = runner.generate_policy_yaml({
        "network_policies": {
            "github": {
                "name": "GitHub API",
                "endpoints": [{"host": "api.github.com", "port": 443, "access": "read-write"}],
                "binaries": [{"path": "/usr/bin/gh"}],
            }
        }
    })
    import yaml
    parsed = yaml.safe_load(yaml_str)
    assert "github" in parsed["network_policies"]
    assert parsed["network_policies"]["github"]["name"] == "GitHub API"


def test_sandbox_context_yields_none_when_unavailable():
    """When OpenShell is unavailable, sandbox() context yields None."""
    from src.integrations.openshell_runner import OpenShellRunner
    runner = OpenShellRunner()
    runner._available = False
    with runner.sandbox("test-trace-001", {}) as sb:
        assert sb is None


def test_get_openshell_runner_returns_singleton():
    """get_openshell_runner() returns the same instance each time."""
    from src.integrations.openshell_runner import get_openshell_runner
    r1 = get_openshell_runner()
    r2 = get_openshell_runner()
    assert r1 is r2


def test_sandbox_status_endpoint_exists():
    """GET /sandbox/status endpoint must be registered."""
    from src.interface.api import app
    routes = [r.path for r in app.routes]
    assert "/sandbox/status" in routes

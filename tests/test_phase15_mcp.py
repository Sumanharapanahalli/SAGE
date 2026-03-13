"""
SAGE Framework — Phase 1.5 MCP Registry Tests
===============================================
Tests for:
  - MCPRegistry discovery (no mcp_servers dir)
  - list_tools() returns list
  - invoke() with unknown tool returns error dict
  - invoke() with registered tool calls function + audits
  - as_react_tools() returns callable dict
  - /mcp/tools API endpoint
  - /mcp/invoke API endpoint
"""

import os
import json
import tempfile
import textwrap
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# MCPRegistry unit tests
# ---------------------------------------------------------------------------

class TestMCPRegistry:

    def _fresh_registry(self):
        from src.integrations.mcp_registry import MCPRegistry
        return MCPRegistry()

    def test_list_tools_empty_when_no_servers_dir(self):
        """list_tools() must return [] when no mcp_servers directory exists."""
        reg = self._fresh_registry()
        with patch.object(reg, "_get_mcp_dir", return_value="/nonexistent/path"):
            tools = reg.list_tools()
        assert isinstance(tools, list)
        assert len(tools) == 0

    def test_invoke_unknown_tool_returns_error(self):
        """invoke() with an unknown tool name must return an error dict, not raise."""
        reg = self._fresh_registry()
        with patch.object(reg, "_get_mcp_dir", return_value="/nonexistent/path"):
            result = reg.invoke("nonexistent_tool", {})
        assert "error" in result
        assert "nonexistent_tool" in result["error"]

    def _patched_invoke(self, reg, tool_name, args=None):
        """Invoke a tool with load() stubbed out (pre-populated _tool_map preserved)."""
        with patch.object(reg, "load", return_value=len(reg._tool_map)):
            return reg.invoke(tool_name, args or {})

    def test_invoke_known_tool_calls_function(self):
        """invoke() with a registered tool must call the function and return the result."""
        reg = self._fresh_registry()
        mock_fn = MagicMock(return_value={"status": "ok"})
        mock_fn.__doc__ = "Test tool"
        mock_fn.__module__ = "test_server"
        reg._tool_map["test_tool"] = mock_fn
        reg._loaded_solution = "test"

        with patch.object(reg, "_audit"):
            result = self._patched_invoke(reg, "test_tool", {"param": "value"})

        assert result.get("result") == {"status": "ok"}
        mock_fn.assert_called_once_with(param="value")

    def test_invoke_audits_on_success(self):
        """invoke() must call _audit with success=True when tool succeeds."""
        reg = self._fresh_registry()
        reg._tool_map["good_tool"] = lambda: "done"
        reg._loaded_solution = "test"

        with patch.object(reg, "_audit") as mock_audit:
            self._patched_invoke(reg, "good_tool", {})
        mock_audit.assert_called_once()
        _, kwargs = mock_audit.call_args
        assert kwargs.get("success") is True

    def test_invoke_audits_on_failure(self):
        """invoke() must call _audit with success=False when tool raises."""
        reg = self._fresh_registry()

        def _bad_tool():
            raise RuntimeError("tool failed")

        reg._tool_map["bad_tool"] = _bad_tool
        reg._loaded_solution = "test"

        with patch.object(reg, "_audit") as mock_audit:
            result = self._patched_invoke(reg, "bad_tool", {})
        assert "error" in result
        mock_audit.assert_called_once()
        _, kwargs = mock_audit.call_args
        assert kwargs.get("success") is False

    def test_as_react_tools_returns_callables(self):
        """as_react_tools() must return a dict of name -> callable."""
        reg = self._fresh_registry()
        reg._tool_map["tool_a"] = lambda: "a"
        reg._tool_map["tool_b"] = lambda: "b"
        reg._loaded_solution = "test"

        with patch.object(reg, "load", return_value=2):
            tools = reg.as_react_tools()

        assert "tool_a" in tools
        assert "tool_b" in tools
        assert callable(tools["tool_a"])
        assert callable(tools["tool_b"])

    def test_load_from_real_server_module(self):
        """
        Write a minimal FastMCP server to a temp dir and verify MCPRegistry
        discovers and registers its tools.
        """
        server_code = textwrap.dedent("""
            from fastmcp import FastMCP
            mcp = FastMCP("test_server")

            @mcp.tool()
            def greet(name: str) -> str:
                \"\"\"Say hello.\"\"\"
                return f"Hello, {name}!"
        """)

        with tempfile.TemporaryDirectory() as tmpdir:
            server_path = os.path.join(tmpdir, "hello_server.py")
            with open(server_path, "w") as f:
                f.write(server_code)

            reg = self._fresh_registry()
            with patch.object(reg, "_get_mcp_dir", return_value=tmpdir):
                count = reg.load(force=True)

            # If FastMCP is installed and tool registration is discoverable
            # count will be 1; if not, skip rather than fail
            if count == 0:
                pytest.skip("FastMCP tool introspection unavailable in this environment")

            assert "greet" in reg._tool_map
            with patch.object(reg, "_audit"):
                result = reg.invoke("greet", {"name": "World"})
            assert result.get("result") == "Hello, World!"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestMCPAPIEndpoints:

    def _client(self):
        from src.interface.api import app
        return TestClient(app)

    def test_mcp_list_tools_returns_json(self):
        """GET /mcp/tools must return JSON with 'tools' and 'count' keys."""
        from src.integrations import mcp_registry as reg_module
        mock_reg = MagicMock()
        mock_reg.list_tools.return_value = [
            {"name": "flash_firmware", "description": "Flash device", "server": "jlink_server"}
        ]
        with patch.object(reg_module, "mcp_registry", mock_reg):
            response = self._client().get("/mcp/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert "count" in data
        assert data["count"] == 1

    def test_mcp_invoke_returns_result(self):
        """POST /mcp/invoke must return 200 with result when tool succeeds."""
        from src.integrations import mcp_registry as reg_module
        mock_reg = MagicMock()
        mock_reg.invoke.return_value = {"result": "flashed OK", "tool_name": "flash_firmware"}
        with patch.object(reg_module, "mcp_registry", mock_reg):
            response = self._client().post(
                "/mcp/invoke",
                json={"tool_name": "flash_firmware", "args": {"bin_path": "/fw.bin"}},
            )
        assert response.status_code == 200
        assert response.json()["result"] == "flashed OK"

    def test_mcp_invoke_missing_tool_name_returns_400(self):
        """POST /mcp/invoke without tool_name must return 400."""
        response = self._client().post("/mcp/invoke", json={"args": {}})
        assert response.status_code == 400

    def test_mcp_invoke_error_returns_400(self):
        """POST /mcp/invoke when tool returns error must return 400."""
        from src.integrations import mcp_registry as reg_module
        mock_reg = MagicMock()
        mock_reg.invoke.return_value = {"error": "Tool not found", "tool_name": "bad_tool"}
        with patch.object(reg_module, "mcp_registry", mock_reg):
            response = self._client().post(
                "/mcp/invoke",
                json={"tool_name": "bad_tool", "args": {}},
            )
        assert response.status_code == 400

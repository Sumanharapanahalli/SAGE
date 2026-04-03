"""
Tests for Hardware MCP tools and Functional Safety API.
"""

import pytest
import os
import tempfile
from fastapi.testclient import TestClient
from src.interface.api import app

client = TestClient(app)


class TestHardwareToolDiscovery:
    """Test hardware tool availability detection."""

    def test_list_tools(self):
        from src.mcp_servers.hardware_tools import list_hardware_tools
        result = list_hardware_tools()
        assert "tools" in result
        assert "kicad" in result["tools"]
        assert "freecad" in result["tools"]
        assert "ngspice" in result["tools"]
        assert "gcc_arm" in result["tools"]
        assert "cppcheck" in result["tools"]
        assert "openscad" in result["tools"]
        assert "available_count" in result
        assert "total_count" in result
        assert result["total_count"] == 6

    def test_each_tool_has_required_fields(self):
        from src.mcp_servers.hardware_tools import list_hardware_tools
        result = list_hardware_tools()
        for tool_id, tool in result["tools"].items():
            assert "name" in tool
            assert "purpose" in tool
            assert "binary" in tool
            assert "available" in tool


class TestKiCadProjectCreation:
    """Test KiCad project scaffolding (no KiCad binary needed)."""

    def test_create_kicad_project(self):
        from src.mcp_servers.hardware_tools import kicad_create_project
        with tempfile.TemporaryDirectory() as tmpdir:
            result = kicad_create_project("pacemaker_pcb", tmpdir)
            assert result["success"] is True
            assert os.path.isdir(os.path.join(tmpdir, "pacemaker_pcb"))
            assert any(f.endswith(".kicad_pro") for f in result["files_created"])
            assert any(f.endswith(".kicad_sch") for f in result["files_created"])
            assert any(f.endswith(".kicad_pcb") for f in result["files_created"])


class TestToolRegistryComplete:
    """Test that all tools are registered in the MCP registry."""

    def test_registry_has_all_tools(self):
        from src.mcp_servers.hardware_tools import HARDWARE_TOOL_REGISTRY
        expected_tools = [
            "list_hardware_tools",
            "kicad_create_project", "kicad_run_erc", "kicad_run_drc",
            "kicad_export_gerbers", "kicad_export_bom", "kicad_export_netlist",
            "openscad_render", "openscad_render_png", "freecad_export_step",
            "ngspice_simulate", "firmware_compile", "firmware_size", "cppcheck_misra",
        ]
        for tool_name in expected_tools:
            assert tool_name in HARDWARE_TOOL_REGISTRY, f"Missing: {tool_name}"
            assert callable(HARDWARE_TOOL_REGISTRY[tool_name])


class TestFunctionalSafetyAPI:
    """Test /safety/* API endpoints."""

    def test_fmea_endpoint(self):
        resp = client.post("/safety/fmea", json={
            "entries": [
                {"component": "Pulse Gen", "failure_mode": "No output",
                 "effect": "Asystole", "severity": 10, "occurrence": 3, "detection": 4},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entries"][0]["rpn"] == 120

    def test_fta_endpoint(self):
        resp = client.post("/safety/fta", json={
            "tree": {
                "top_event": "Loss of pacing",
                "gate": "OR",
                "children": [
                    {"event": "SW fault", "probability": 0.001},
                    {"event": "HW fault", "probability": 0.002},
                ],
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["probability"] > 0

    def test_asil_endpoint(self):
        resp = client.post("/safety/asil", json={
            "severity": "S3", "exposure": "E4", "controllability": "C3",
        })
        assert resp.status_code == 200
        assert resp.json()["asil"] == "D"

    def test_sil_endpoint(self):
        resp = client.post("/safety/sil", json={
            "probability_dangerous_failure_per_hour": 1e-7,
        })
        assert resp.status_code == 200
        assert resp.json()["sil"] == 3

    def test_iec62304_endpoint(self):
        resp = client.post("/safety/iec62304-class", json={"risk_level": "death_possible"})
        assert resp.status_code == 200
        assert resp.json()["safety_class"] == "C"

    def test_full_safety_analysis_endpoint(self):
        resp = client.post("/safety/analysis", json={
            "product_name": "Pacemaker",
            "hazards": [
                {"id": "HAZ-001", "description": "Loss of pacing",
                 "cause": "SW fault", "effect": "Death",
                 "severity": "S3", "exposure": "E4", "controllability": "C3"},
            ],
            "fmea_entries": [
                {"component": "Pulse Gen", "failure_mode": "No output",
                 "effect": "Asystole", "severity": 10, "occurrence": 3, "detection": 4},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["iec62304_class"] == "C"
        assert data["max_asil"] == "D"
        assert len(data["safety_requirements"]) >= 1

    def test_hardware_tools_endpoint(self):
        resp = client.get("/safety/hardware-tools")
        assert resp.status_code == 200
        assert "tools" in resp.json()

"""
E2E tests for Multi-Standard Regulatory Compliance.

Simulates user journey:
1. View all standards in dashboard
2. Fill product profile and assess compliance
3. Check per-standard scores and gaps
4. Generate submission roadmap
5. Generate full compliance report
"""

import pytest
from fastapi.testclient import TestClient
from src.interface.api import app

client = TestClient(app)


class TestE2EStandardsDashboard:
    """User views the standards dashboard."""

    def test_list_all_standards(self):
        resp = client.get("/regulatory/standards")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 17  # 17 standards in registry
        ids = [s["id"] for s in data]
        assert "iec_62304" in ids
        assert "fda_cds" in ids
        assert "eu_mdr" in ids
        assert "eu_ai_act" in ids

    def test_get_single_standard(self):
        resp = client.get("/regulatory/standards/iec_62304")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "IEC 62304:2006/AMD1:2015 — Medical Device Software Lifecycle"
        assert len(data["requirements"]) >= 10

    def test_unknown_standard_returns_404(self):
        resp = client.get("/regulatory/standards/nonexistent")
        assert resp.status_code == 404


class TestE2EComplianceAssessment:
    """User assesses product compliance."""

    def test_medtech_product_us_eu(self):
        """Medtech product targeting US + EU should assess against 10+ standards."""
        resp = client.post("/regulatory/assess", json={
            "product": {
                "product_name": "CardioRisk CDS",
                "product_type": "samd",
                "risk_class": "II",
                "target_regions": ["us", "eu"],
                "uses_ai_ml": False,
                "processes_images": False,
                "processes_signals": False,
                "existing_artifacts": [
                    "software_requirements_spec",
                    "software_architecture_doc",
                    "risk_management_file",
                    "verification_plan",
                    "audit_trail",
                ],
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["standards_assessed"] >= 8
        assert 0 <= data["overall_score"] <= 100

        # Check key standards are assessed
        std_ids = list(data["assessments"].keys())
        assert "iec_62304" in std_ids
        assert "iso_14971" in std_ids
        assert "eu_mdr" in std_ids

    def test_aiml_product_triggers_ai_standards(self):
        """AI/ML product should trigger AI-specific assessments."""
        resp = client.post("/regulatory/assess", json={
            "product": {
                "product_name": "LungScan AI",
                "product_type": "samd",
                "risk_class": "III",
                "target_regions": ["us", "eu"],
                "uses_ai_ml": True,
                "processes_images": True,
                "processes_signals": False,
                "existing_artifacts": ["software_requirements_spec"],
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        std_ids = list(data["assessments"].keys())
        assert "fda_aiml" in std_ids
        assert "eu_ai_act" in std_ids

    def test_japan_only_product(self):
        """Japan-only product should include PMDA but not FDA/EU."""
        resp = client.post("/regulatory/assess", json={
            "product": {
                "product_name": "Japan CDS",
                "product_type": "samd",
                "risk_class": "II",
                "target_regions": ["japan"],
                "uses_ai_ml": False,
                "processes_images": False,
                "processes_signals": False,
                "existing_artifacts": [],
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        std_ids = list(data["assessments"].keys())
        assert "japan_pmda" in std_ids
        assert "fda_swv" not in std_ids
        assert "eu_mdr" not in std_ids

    def test_more_artifacts_higher_score(self):
        """Product with more artifacts should score higher."""
        minimal = client.post("/regulatory/assess", json={
            "product": {
                "product_name": "Minimal",
                "target_regions": ["us"],
                "existing_artifacts": [],
            },
            "standard_ids": ["iec_62304"],
        }).json()

        full = client.post("/regulatory/assess", json={
            "product": {
                "product_name": "Full",
                "target_regions": ["us"],
                "existing_artifacts": [
                    "software_development_plan", "software_requirements_spec",
                    "software_architecture_doc", "unit_test_reports",
                    "integration_test_reports", "system_test_reports",
                    "software_release_doc", "safety_classification",
                    "soup_inventory", "configuration_management_plan",
                    "maintenance_plan",
                ],
            },
            "standard_ids": ["iec_62304"],
        }).json()

        assert full["overall_score"] > minimal["overall_score"]


class TestE2EGapAnalysis:
    """User generates gap analysis."""

    def test_gap_analysis(self):
        resp = client.post("/regulatory/gap-analysis", json={
            "product": {
                "product_name": "TestProduct",
                "target_regions": ["us"],
                "existing_artifacts": ["software_requirements_spec"],
            },
            "standard_id": "iec_62304",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["standard_id"] == "iec_62304"
        assert len(data["gaps"]) > 0
        for gap in data["gaps"]:
            assert gap["status"] in ("missing", "partial", "met")


class TestE2ERoadmap:
    """User generates submission roadmap."""

    def test_roadmap_generation(self):
        resp = client.post("/regulatory/roadmap", json={
            "product_name": "GlobalDevice",
            "product_type": "samd",
            "risk_class": "II",
            "target_regions": ["us", "eu", "uk"],
            "uses_ai_ml": False,
            "processes_images": False,
            "processes_signals": False,
            "existing_artifacts": [],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "phases" in data
        assert len(data["phases"]) >= 3
        assert data["total_estimated_weeks"] > 0
        for phase in data["phases"]:
            assert "phase_name" in phase
            assert "deliverables" in phase
            assert "estimated_weeks" in phase


class TestE2EFullReport:
    """User generates full compliance report."""

    def test_full_report(self):
        resp = client.post("/regulatory/full-report", json={
            "product_name": "MedAssist Pro",
            "product_type": "samd",
            "risk_class": "II",
            "target_regions": ["us", "eu"],
            "uses_ai_ml": False,
            "processes_images": False,
            "processes_signals": False,
            "existing_artifacts": [
                "software_requirements_spec",
                "risk_management_file",
                "audit_trail",
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "assessments" in data
        assert "overall_score" in data
        assert "roadmap" in data
        assert len(data["assessments"]) >= 4


class TestE2EAllEndpointsReachable:
    """Verify all regulatory endpoints exist."""

    def test_all_endpoints(self):
        endpoints = [
            ("GET", "/regulatory/standards"),
            ("GET", "/regulatory/standards/iec_62304"),
            ("GET", "/regulatory/checklist/iec_62304"),
            ("POST", "/regulatory/assess"),
            ("POST", "/regulatory/gap-analysis"),
            ("POST", "/regulatory/roadmap"),
            ("POST", "/regulatory/full-report"),
        ]
        for method, path in endpoints:
            if method == "GET":
                resp = client.get(path)
            else:
                resp = client.post(path, json={})
            assert resp.status_code in (200, 422), f"{method} {path} returned {resp.status_code}"

    def test_openapi_includes_regulatory_routes(self):
        resp = client.get("/openapi.json")
        paths = resp.json()["paths"]
        reg_paths = [p for p in paths if p.startswith("/regulatory")]
        assert len(reg_paths) >= 5

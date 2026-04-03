"""
End-to-end tests for the CDS Compliance workflow.

Simulates the user journey through the CDS Compliance page:
1. Navigate to Classification tab → fill form → classify → see results
2. Navigate to Input Taxonomy tab → enter inputs → classify → see table
3. Navigate to Data Sources tab → add sources → validate → see status
4. Navigate to Labeling tab → fill form → generate → see labeling
5. Navigate to Full Package tab → generate → see complete package

Tests run against the live FastAPI backend (TestClient).
"""

import pytest
from fastapi.testclient import TestClient
from src.interface.api import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Scenario 1: Non-Device CDS (Drug Interaction Checker)
# Simulates user filling out the Classification tab for a simple drug checker
# ---------------------------------------------------------------------------

class TestE2EScenario_NonDeviceCDS:
    """Full user journey for a Non-Device CDS product."""

    def test_step1_classify_function(self):
        """User fills Classification form and clicks 'Classify Function'."""
        resp = client.post("/cds/classify", json={
            "function_description": "Checks patient medication list against drug-drug interaction database and alerts prescribing physician with recommended alternatives",
            "input_types": ["medication_list", "allergy_list", "patient_demographics"],
            "output_type": "recommendation",
            "intended_user": "physician",
            "urgency": "non_urgent",
            "data_sources": [
                {"name": "FDA Drug Labeling Database", "type": "fda_labeling"},
                {"name": "Clinical Pharmacology Guidelines", "type": "clinical_guideline"},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()

        # User sees green "Non-Device CDS" banner
        assert data["overall_classification"] == "non_device_cds"

        # User sees 4 green criterion badges
        assert data["criterion_1"]["passes"] is True, "Criterion 1 should pass — no images/signals"
        assert data["criterion_2"]["passes"] is True, "Criterion 2 should pass — FDA labeling source"
        assert data["criterion_3"]["passes"] is True, "Criterion 3 should pass — physician, recommendation"
        assert data["criterion_4"]["passes"] is True, "Criterion 4 should pass — non-urgent"

    def test_step2_classify_inputs(self):
        """User clicks Input Taxonomy tab and classifies inputs."""
        resp = client.post("/cds/classify-inputs", json={
            "input_types": ["medication_list", "allergy_list", "patient_demographics"],
        })
        assert resp.status_code == 200
        data = resp.json()

        # User sees table with 3 rows, all green (pass)
        assert len(data) == 3
        for item in data:
            assert item["criterion_1_impact"] == "pass"
            assert item["data_category"] in ("discrete", "text", "structured")

    def test_step3_validate_sources(self):
        """User clicks Data Sources tab and validates sources."""
        resp = client.post("/cds/validate-sources", json={
            "sources": [
                {"name": "FDA Drug Labeling Database", "type": "fda_labeling"},
                {"name": "Clinical Pharmacology Guidelines", "type": "clinical_guideline"},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()

        # User sees green "All Sources Accepted" banner
        assert data["overall_status"] == "accepted"
        assert len(data["sources"]) == 2
        for src in data["sources"]:
            assert src["validation_status"] == "well_understood_accepted"

    def test_step4_generate_labeling(self):
        """User clicks Labeling tab, fills product details, generates labeling."""
        resp = client.post("/cds/labeling", json={
            "product_name": "DrugSafe Alert",
            "intended_use": "Drug-drug interaction checking and alerting",
            "intended_users": ["physician", "pharmacist"],
            "target_population": "Adults 18+ with 2 or more concurrent medications",
            "algorithm_summary": "Rule-based matching against FDA-approved interaction database with severity scoring",
            "data_sources": [
                {"name": "FDA Drug Labeling Database", "type": "fda_labeling"},
                {"name": "Clinical Pharmacology Guidelines", "type": "clinical_guideline"},
            ],
            "validation_summary": "Validated against 10,000 known interactions with 98.5% sensitivity and 99.1% specificity",
            "known_limitations": [
                "Does not cover herbal supplement interactions",
                "Limited pediatric interaction data (ages <12)",
                "May not include interactions for drugs approved in last 30 days",
            ],
        })
        assert resp.status_code == 200
        data = resp.json()

        # User sees intended use statement
        assert "intended_use_statement" in data
        assert "DrugSafe Alert" in data["intended_use_statement"]
        assert "physician" in data["intended_use_statement"].lower()

        # User sees automation bias warning in red box
        assert "automation_bias_warning" in data
        assert "independent" in data["automation_bias_warning"].lower()

        # User sees all FDA-required labeling elements
        assert "target_patient_population" in data
        assert "algorithm_basis" in data
        assert "data_source_disclosure" in data
        assert "validation_evidence" in data
        assert "known_limitations" in data

    def test_step5_generate_full_package(self):
        """User clicks Full Package tab and generates complete compliance package."""
        resp = client.post("/cds/compliance-package", json={
            "product_name": "DrugSafe Alert",
            "function_description": "Checks patient medication list against drug-drug interaction database and alerts prescribing physician",
            "input_types": ["medication_list", "allergy_list", "patient_demographics"],
            "output_type": "recommendation",
            "intended_user": "physician",
            "urgency": "non_urgent",
            "data_sources": [
                {"name": "FDA Drug Labeling Database", "type": "fda_labeling"},
                {"name": "Clinical Pharmacology Guidelines", "type": "clinical_guideline"},
            ],
            "algorithm_description": "Rule-based matching against FDA-approved interaction database",
            "known_limitations": ["Does not cover herbal supplements"],
            "target_population": "Adults 18+ with 2+ concurrent medications",
            "validation_summary": "98.5% sensitivity on 10,000 interactions",
        })
        assert resp.status_code == 200
        data = resp.json()

        # User sees classification result
        assert data["cds_classification"]["overall_classification"] == "non_device_cds"

        # User can expand each section
        assert "labeling" in data
        assert "transparency_report" in data
        assert "automation_bias_risk" in data
        assert "input_taxonomy" in data
        assert "data_source_validation" in data
        assert "output_classification" in data
        assert "clinical_limitations" in data
        assert "bias_warning" in data

        # Transparency report has all required fields
        tr = data["transparency_report"]
        assert "inputs_summary" in tr
        assert "logic_description" in tr
        assert "evidence_basis" in tr
        assert "automation_bias_warning" in tr


# ---------------------------------------------------------------------------
# Scenario 2: Medical Device (CT Scan Analyzer)
# Simulates user journey where software IS a regulated device
# ---------------------------------------------------------------------------

class TestE2EScenario_DeviceCDS:
    """Full user journey for a Device CDS product."""

    def test_step1_classify_as_device(self):
        """User classifies CT image analysis — should be flagged as Device."""
        resp = client.post("/cds/classify", json={
            "function_description": "Analyzes chest CT scan images to detect and classify lung nodules with automated diagnosis",
            "input_types": ["ct_scan_image", "patient_demographics"],
            "output_type": "definitive_diagnosis",
            "intended_user": "radiologist",
            "urgency": "non_urgent",
            "data_sources": [{"name": "ACR Lung-RADS Guidelines", "type": "clinical_guideline"}],
        })
        assert resp.status_code == 200
        data = resp.json()

        # User sees red "Medical Device" banner
        assert data["overall_classification"] == "device"

        # User sees which criteria failed
        assert data["criterion_1"]["passes"] is False, "Fails C1 — processes CT images"
        assert data["criterion_3"]["passes"] is False, "Fails C3 — definitive diagnosis"

    def test_step2_inputs_show_image_flag(self):
        """User checks input taxonomy — CT scan flagged as image."""
        resp = client.post("/cds/classify-inputs", json={
            "input_types": ["ct_scan_image", "patient_demographics"],
        })
        assert resp.status_code == 200
        data = resp.json()

        ct_item = next(d for d in data if d["input_type"] == "ct_scan_image")
        assert ct_item["data_category"] == "image"
        assert ct_item["criterion_1_impact"] == "fail"

        demo_item = next(d for d in data if d["input_type"] == "patient_demographics")
        assert demo_item["criterion_1_impact"] == "pass"

    def test_step3_package_still_generates(self):
        """Even for devices, a compliance package is generated (for device pathway)."""
        resp = client.post("/cds/compliance-package", json={
            "product_name": "LungScan AI",
            "function_description": "Analyzes chest CT scans to detect lung nodules",
            "input_types": ["ct_scan_image"],
            "output_type": "definitive_diagnosis",
            "intended_user": "radiologist",
            "urgency": "non_urgent",
            "data_sources": [{"name": "ACR Guidelines", "type": "clinical_guideline"}],
            "algorithm_description": "Deep learning CNN on 50K CT scans",
            "known_limitations": ["Not for pediatric patients"],
            "target_population": "Adults with suspected lung nodules",
            "validation_summary": "Validated on 5,000 cases",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["cds_classification"]["overall_classification"] == "device"
        assert "labeling" in data


# ---------------------------------------------------------------------------
# Scenario 3: Edge cases and post-market monitoring
# ---------------------------------------------------------------------------

class TestE2EScenario_EdgeCases:
    """Edge cases: single recommendation, patient-facing, time-critical."""

    def test_single_recommendation_enforcement_discretion(self):
        """2026 update: single recommendation gets enforcement discretion."""
        resp = client.post("/cds/classify", json={
            "function_description": "Recommends specific FDA-approved statin based on lipid panel",
            "input_types": ["lipid_panel", "patient_demographics"],
            "output_type": "single_recommendation",
            "intended_user": "physician",
            "urgency": "non_urgent",
            "data_sources": [{"name": "ACC/AHA Cholesterol Guidelines", "type": "clinical_guideline"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_classification"] in ("non_device_cds", "enforcement_discretion")

    def test_patient_facing_fails_criterion_3(self):
        """Patient-facing symptom checker should fail."""
        resp = client.post("/cds/classify", json={
            "function_description": "Patient enters symptoms and receives possible diagnoses",
            "input_types": ["patient_reported_symptoms"],
            "output_type": "recommendation",
            "intended_user": "patient",
            "urgency": "non_urgent",
            "data_sources": [{"name": "Clinical guidelines", "type": "clinical_guideline"}],
        })
        assert resp.status_code == 200
        assert resp.json()["overall_classification"] == "device"

    def test_time_critical_fails_criterion_4(self):
        """Sepsis alert in time-critical setting should fail C4."""
        resp = client.post("/cds/classify", json={
            "function_description": "Monitors vitals and triggers sepsis alert",
            "input_types": ["vital_signs"],
            "output_type": "immediate_directive",
            "intended_user": "nurse",
            "urgency": "time_critical",
            "data_sources": [{"name": "Surviving Sepsis Campaign", "type": "clinical_guideline"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_classification"] == "device"
        assert data["criterion_4"]["passes"] is False

    def test_over_reliance_detection(self):
        """Post-market monitoring flags rubber-stamping."""
        resp = client.post("/cds/over-reliance", json={
            "total_recommendations": 500,
            "accepted_without_modification": 490,
            "average_review_time_seconds": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["over_reliance_detected"] is True

    def test_criterion_reevaluation_after_change(self):
        """Re-evaluate criteria after algorithm update."""
        resp = client.post("/cds/reevaluate", json={
            "change_description": "Added 500 new drug interactions to database",
            "previous_classification": "non_device_cds",
            "function_description": "Drug interaction checker",
            "input_types": ["medication_list"],
            "output_type": "recommendation",
            "intended_user": "physician",
            "urgency": "non_urgent",
            "data_sources": [{"name": "FDA Drug Labels", "type": "fda_labeling"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "new_classification" in data
        assert "reevaluation_date" in data
        assert data["classification_changed"] is False  # Same inputs → same result


# ---------------------------------------------------------------------------
# Scenario 4: UI page health check
# ---------------------------------------------------------------------------

class TestE2EUIHealthCheck:
    """Verify the frontend page and API endpoints are all reachable."""

    def test_all_cds_endpoints_exist(self):
        """Every CDS endpoint returns 200 or 422 (not 404)."""
        endpoints = [
            "/cds/classify", "/cds/classify-inputs", "/cds/validate-sources",
            "/cds/classify-output", "/cds/transparency-report", "/cds/labeling",
            "/cds/bias-warning", "/cds/bias-risk", "/cds/clinical-limitations",
            "/cds/validation-protocol", "/cds/over-reliance", "/cds/reevaluate",
            "/cds/patient-population", "/cds/compliance-package",
        ]
        for ep in endpoints:
            resp = client.post(ep, json={})
            assert resp.status_code in (200, 422), f"{ep} returned {resp.status_code}"

    def test_openapi_includes_cds_routes(self):
        """OpenAPI spec includes all CDS routes."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]
        cds_paths = [p for p in paths if p.startswith("/cds/")]
        assert len(cds_paths) >= 14, f"Expected 14+ CDS paths, got {len(cds_paths)}: {cds_paths}"

"""
API tests for CDS Compliance endpoints.
Tests all /cds/* routes against the FastAPI test client.
"""

import pytest
from fastapi.testclient import TestClient
from src.interface.api import app

client = TestClient(app)


class TestCDSClassifyEndpoint:
    """POST /cds/classify — 4-criterion assessment."""

    def test_non_device_cds_returns_200(self):
        resp = client.post("/cds/classify", json={
            "function_description": "Drug interaction checker for physicians",
            "input_types": ["medication_list", "allergy_list"],
            "output_type": "recommendation",
            "intended_user": "physician",
            "urgency": "non_urgent",
            "data_sources": [{"name": "FDA Drug Labels", "type": "fda_labeling"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_classification"] == "non_device_cds"
        assert data["criterion_1"]["passes"] is True
        assert data["criterion_2"]["passes"] is True
        assert data["criterion_3"]["passes"] is True
        assert data["criterion_4"]["passes"] is True

    def test_device_image_returns_200(self):
        resp = client.post("/cds/classify", json={
            "function_description": "CT scan lung nodule detector",
            "input_types": ["ct_scan_image"],
            "output_type": "definitive_diagnosis",
            "intended_user": "radiologist",
            "urgency": "non_urgent",
            "data_sources": [{"name": "ACR guidelines", "type": "clinical_guideline"}],
        })
        assert resp.status_code == 200
        assert resp.json()["overall_classification"] == "device"

    def test_missing_field_returns_422(self):
        resp = client.post("/cds/classify", json={"function_description": "test"})
        assert resp.status_code == 422


class TestCDSClassifyInputs:
    """POST /cds/classify-inputs."""

    def test_classifies_images(self):
        resp = client.post("/cds/classify-inputs", json={"input_types": ["ct_scan", "mri_image"]})
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["criterion_1_impact"] == "fail" for item in data)

    def test_classifies_discrete(self):
        resp = client.post("/cds/classify-inputs", json={"input_types": ["blood_pressure_single", "bmi"]})
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["criterion_1_impact"] == "pass" for item in data)


class TestCDSValidateSources:
    """POST /cds/validate-sources."""

    def test_accepted_sources(self):
        resp = client.post("/cds/validate-sources", json={
            "sources": [{"name": "AHA Guidelines", "type": "clinical_guideline"}],
        })
        assert resp.status_code == 200
        assert resp.json()["overall_status"] == "accepted"

    def test_proprietary_flagged(self):
        resp = client.post("/cds/validate-sources", json={
            "sources": [{"name": "Internal ML Model", "type": "proprietary"}],
        })
        assert resp.status_code == 200
        assert resp.json()["overall_status"] == "flagged"


class TestCDSClassifyOutput:
    """POST /cds/classify-output."""

    def test_recommendation(self):
        resp = client.post("/cds/classify-output", json={"output_type": "recommendation"})
        assert resp.status_code == 200
        assert resp.json()["criterion_3_compatible"] is True

    def test_diagnosis(self):
        resp = client.post("/cds/classify-output", json={"output_type": "definitive_diagnosis"})
        assert resp.status_code == 200
        assert resp.json()["criterion_3_compatible"] is False


class TestCDSTransparencyReport:
    """POST /cds/transparency-report."""

    def test_generates_report(self):
        resp = client.post("/cds/transparency-report", json={
            "function_description": "CV risk calculator",
            "inputs_used": ["blood_pressure", "cholesterol"],
            "data_sources": [{"name": "ACC/AHA", "type": "clinical_guideline"}],
            "algorithm_description": "Pooled Cohort Equations",
            "known_limitations": ["Ages 40-79 only"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "inputs_summary" in data
        assert "automation_bias_warning" in data


class TestCDSLabeling:
    """POST /cds/labeling."""

    def test_generates_labeling(self):
        resp = client.post("/cds/labeling", json={
            "product_name": "CardioRisk",
            "intended_use": "CV risk assessment",
            "intended_users": ["cardiologist"],
            "target_population": "Adults 40-79",
            "algorithm_summary": "PCE",
            "data_sources": [{"name": "ACC/AHA", "type": "clinical_guideline"}],
            "validation_summary": "Validated on 25K patients",
            "known_limitations": ["Not for <40"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "intended_use_statement" in data
        assert "automation_bias_warning" in data


class TestCDSBiasAndRisk:
    """POST /cds/bias-warning and /cds/bias-risk."""

    def test_bias_warning(self):
        resp = client.post("/cds/bias-warning", json={
            "function_description": "Drug dosing rec",
            "intended_user": "physician",
        })
        assert resp.status_code == 200
        assert "warning_text" in resp.json()

    def test_bias_risk(self):
        resp = client.post("/cds/bias-risk", json={
            "function_description": "Antibiotic recommender",
            "urgency": "non_urgent",
            "decision_impact": "treatment_selection",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_category"] == "automation_bias"
        assert "mitigation_strategies" in data


class TestCDSOverReliance:
    """POST /cds/over-reliance."""

    def test_detects_over_reliance(self):
        resp = client.post("/cds/over-reliance", json={
            "total_recommendations": 1000,
            "accepted_without_modification": 970,
            "average_review_time_seconds": 5,
        })
        assert resp.status_code == 200
        assert resp.json()["over_reliance_detected"] is True

    def test_normal_usage(self):
        resp = client.post("/cds/over-reliance", json={
            "total_recommendations": 1000,
            "accepted_without_modification": 750,
            "average_review_time_seconds": 45,
        })
        assert resp.status_code == 200
        assert resp.json()["over_reliance_detected"] is False


class TestCDSCompliancePackage:
    """POST /cds/compliance-package — E2E."""

    def test_full_package(self):
        resp = client.post("/cds/compliance-package", json={
            "product_name": "DrugSafe",
            "function_description": "Drug interaction checker",
            "input_types": ["medication_list", "allergy_list"],
            "output_type": "recommendation",
            "intended_user": "physician",
            "urgency": "non_urgent",
            "data_sources": [{"name": "FDA Drug Labels", "type": "fda_labeling"}],
            "algorithm_description": "Rule-based interaction matching",
            "known_limitations": ["No herbal supplements"],
            "target_population": "Adults 18+ with 2+ medications",
            "validation_summary": "98.5% sensitivity on 10K interactions",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["cds_classification"]["overall_classification"] == "non_device_cds"
        assert "labeling" in data
        assert "transparency_report" in data
        assert "automation_bias_risk" in data

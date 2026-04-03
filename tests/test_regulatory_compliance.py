"""
Test suite for Multi-Standard Regulatory Compliance Framework

Covers compliance assessment against:
- FDA: Software Validation, CSA, Cybersecurity, AI/ML, CDS (already covered)
- EU: MDR 2017/745, AI Act, IVDR
- International: IEC 62304, ISO 14971, IEC 82304-1, IMDRF SaMD
- Regional: UK MHRA, Health Canada, Japan PMDA, TGA Australia

TDD — tests written BEFORE implementation.
"""

import pytest
from datetime import datetime


class TestRegulatoryRegistry:
    """Test the registry of all supported regulatory standards."""

    @pytest.fixture
    def framework(self):
        from src.core.regulatory_compliance import RegulatoryComplianceFramework
        return RegulatoryComplianceFramework()

    def test_registry_contains_all_standards(self, framework):
        """Registry must include all major standards."""
        standards = framework.list_standards()
        standard_ids = [s["id"] for s in standards]

        # FDA
        assert "fda_swv" in standard_ids        # Software Validation
        assert "fda_csa" in standard_ids        # Computer Software Assurance
        assert "fda_cybersecurity" in standard_ids
        assert "fda_aiml" in standard_ids       # AI/ML guidance
        assert "fda_cds" in standard_ids        # CDS (already implemented)
        assert "fda_21cfr11" in standard_ids    # Electronic records

        # EU
        assert "eu_mdr" in standard_ids         # MDR 2017/745
        assert "eu_ai_act" in standard_ids      # AI Act
        assert "eu_ivdr" in standard_ids        # IVDR 2017/746

        # International
        assert "iec_62304" in standard_ids
        assert "iso_14971" in standard_ids
        assert "iec_82304" in standard_ids
        assert "imdrf_samd" in standard_ids

        # Regional
        assert "uk_mhra" in standard_ids
        assert "canada_hc" in standard_ids
        assert "japan_pmda" in standard_ids
        assert "aus_tga" in standard_ids

    def test_each_standard_has_required_fields(self, framework):
        """Each standard entry must have id, name, region, requirements, artifacts."""
        for std in framework.list_standards():
            assert "id" in std
            assert "name" in std
            assert "region" in std
            assert "category" in std
            assert "requirements" in std
            assert "required_artifacts" in std
            assert len(std["requirements"]) > 0
            assert len(std["required_artifacts"]) > 0


class TestComplianceAssessment:
    """Test compliance assessment for a product against standards."""

    @pytest.fixture
    def framework(self):
        from src.core.regulatory_compliance import RegulatoryComplianceFramework
        return RegulatoryComplianceFramework()

    @pytest.fixture
    def medtech_product(self):
        return {
            "product_name": "CardioRisk CDS",
            "product_type": "samd",
            "risk_class": "II",
            "intended_use": "Cardiovascular risk assessment for physicians",
            "target_regions": ["us", "eu", "uk"],
            "uses_ai_ml": False,
            "processes_images": False,
            "processes_signals": False,
            "intended_user": "physician",
            "data_sources": ["clinical_guideline", "peer_reviewed"],
            "existing_artifacts": [
                "software_requirements_spec",
                "software_architecture_doc",
                "risk_management_file",
                "verification_plan",
                "validation_plan",
                "audit_trail",
            ],
        }

    @pytest.fixture
    def aiml_product(self):
        return {
            "product_name": "LungScan AI",
            "product_type": "samd",
            "risk_class": "III",
            "intended_use": "CT scan analysis for lung nodule detection",
            "target_regions": ["us", "eu", "japan"],
            "uses_ai_ml": True,
            "processes_images": True,
            "processes_signals": False,
            "intended_user": "radiologist",
            "data_sources": ["clinical_guideline"],
            "existing_artifacts": ["software_requirements_spec"],
        }

    def test_assess_single_standard(self, framework, medtech_product):
        """Assess product against a single standard."""
        result = framework.assess_compliance(medtech_product, ["iec_62304"])
        assert "iec_62304" in result["assessments"]
        assessment = result["assessments"]["iec_62304"]
        assert "compliance_score" in assessment
        assert 0 <= assessment["compliance_score"] <= 100
        assert "gaps" in assessment
        assert "met_requirements" in assessment
        assert "required_artifacts" in assessment

    def test_assess_multiple_standards(self, framework, medtech_product):
        """Assess product against multiple standards simultaneously."""
        result = framework.assess_compliance(
            medtech_product, ["iec_62304", "iso_14971", "fda_cds"]
        )
        assert len(result["assessments"]) == 3
        assert "overall_score" in result
        assert 0 <= result["overall_score"] <= 100

    def test_assess_all_applicable_standards(self, framework, medtech_product):
        """Auto-detect applicable standards based on product profile."""
        result = framework.assess_compliance(medtech_product)
        # US + EU + UK targeting should pull in FDA, EU MDR, UK MHRA, plus international
        assert len(result["assessments"]) >= 5

    def test_aiml_product_triggers_ai_standards(self, framework, aiml_product):
        """AI/ML product should trigger AI-specific standards."""
        result = framework.assess_compliance(aiml_product)
        standard_ids = list(result["assessments"].keys())
        assert "fda_aiml" in standard_ids, "AI/ML product must be assessed against FDA AI/ML guidance"
        assert "eu_ai_act" in standard_ids, "AI/ML product targeting EU must be assessed against AI Act"

    def test_image_product_fails_cds_criterion_1(self, framework, aiml_product):
        """Product processing images should fail CDS Criterion 1."""
        result = framework.assess_compliance(aiml_product, ["fda_cds"])
        if "fda_cds" in result["assessments"]:
            assert result["assessments"]["fda_cds"]["compliance_score"] < 100

    def test_gaps_include_missing_artifacts(self, framework, aiml_product):
        """Gaps should list missing required artifacts."""
        result = framework.assess_compliance(aiml_product, ["iec_62304"])
        gaps = result["assessments"]["iec_62304"]["gaps"]
        # AI product only has SRS — should be missing many artifacts
        assert len(gaps) > 0

    def test_compliance_score_improves_with_artifacts(self, framework, medtech_product):
        """Product with more artifacts should score higher."""
        # Full artifacts
        full_result = framework.assess_compliance(medtech_product, ["iec_62304"])
        full_score = full_result["assessments"]["iec_62304"]["compliance_score"]

        # Stripped artifacts
        minimal_product = {**medtech_product, "existing_artifacts": ["software_requirements_spec"]}
        min_result = framework.assess_compliance(minimal_product, ["iec_62304"])
        min_score = min_result["assessments"]["iec_62304"]["compliance_score"]

        assert full_score > min_score


class TestGapAnalysis:
    """Test detailed gap analysis per standard."""

    @pytest.fixture
    def framework(self):
        from src.core.regulatory_compliance import RegulatoryComplianceFramework
        return RegulatoryComplianceFramework()

    def test_gap_analysis_returns_actionable_items(self, framework):
        product = {
            "product_name": "TestProduct",
            "product_type": "samd",
            "risk_class": "II",
            "target_regions": ["us"],
            "uses_ai_ml": False,
            "processes_images": False,
            "processes_signals": False,
            "existing_artifacts": [],
        }
        result = framework.generate_gap_analysis(product, "iec_62304")
        assert "standard_id" in result
        assert "gaps" in result
        assert len(result["gaps"]) > 0
        for gap in result["gaps"]:
            assert "requirement" in gap
            assert "status" in gap
            assert gap["status"] in ("missing", "partial", "met")
            assert "remediation" in gap

    def test_gap_analysis_for_eu_mdr(self, framework):
        product = {
            "product_name": "EU Device",
            "product_type": "samd",
            "risk_class": "IIa",
            "target_regions": ["eu"],
            "uses_ai_ml": False,
            "processes_images": False,
            "processes_signals": False,
            "existing_artifacts": ["software_requirements_spec"],
        }
        result = framework.generate_gap_analysis(product, "eu_mdr")
        assert result["standard_id"] == "eu_mdr"
        assert len(result["gaps"]) > 0


class TestRegulatoryDocumentGeneration:
    """Test regulatory document generation per standard."""

    @pytest.fixture
    def framework(self):
        from src.core.regulatory_compliance import RegulatoryComplianceFramework
        return RegulatoryComplianceFramework()

    def test_generate_checklist(self, framework):
        """Generate compliance checklist for a standard."""
        checklist = framework.generate_checklist("iec_62304")
        assert "standard_id" in checklist
        assert "items" in checklist
        assert len(checklist["items"]) > 0
        for item in checklist["items"]:
            assert "requirement" in item
            assert "description" in item
            assert "evidence_needed" in item

    def test_generate_submission_roadmap(self, framework):
        """Generate regulatory submission roadmap."""
        product = {
            "product_name": "TestDevice",
            "product_type": "samd",
            "risk_class": "II",
            "target_regions": ["us", "eu"],
            "uses_ai_ml": False,
            "processes_images": False,
            "processes_signals": False,
            "existing_artifacts": ["software_requirements_spec"],
        }
        roadmap = framework.generate_submission_roadmap(product)
        assert "phases" in roadmap
        assert len(roadmap["phases"]) > 0
        for phase in roadmap["phases"]:
            assert "phase_name" in phase
            assert "standards" in phase
            assert "deliverables" in phase


class TestMultiRegionCompliance:
    """Test compliance across multiple regions simultaneously."""

    @pytest.fixture
    def framework(self):
        from src.core.regulatory_compliance import RegulatoryComplianceFramework
        return RegulatoryComplianceFramework()

    def test_us_eu_uk_coverage(self, framework):
        """Product targeting US + EU + UK should be assessed against all three."""
        product = {
            "product_name": "Global CDS",
            "product_type": "samd",
            "risk_class": "II",
            "target_regions": ["us", "eu", "uk"],
            "uses_ai_ml": False,
            "processes_images": False,
            "processes_signals": False,
            "existing_artifacts": [],
        }
        result = framework.assess_compliance(product)
        regions_covered = set()
        for std_id, assessment in result["assessments"].items():
            regions_covered.add(assessment.get("region", ""))
        assert "us" in regions_covered or "international" in regions_covered
        assert "eu" in regions_covered or "international" in regions_covered

    def test_region_specific_standards_filter(self, framework):
        """Only Japan-applicable standards when targeting Japan only."""
        product = {
            "product_name": "Japan CDS",
            "product_type": "samd",
            "risk_class": "II",
            "target_regions": ["japan"],
            "uses_ai_ml": False,
            "processes_images": False,
            "processes_signals": False,
            "existing_artifacts": [],
        }
        result = framework.assess_compliance(product)
        standard_ids = list(result["assessments"].keys())
        # Should include Japan PMDA and international standards, but NOT FDA or EU MDR
        assert "japan_pmda" in standard_ids
        assert "fda_swv" not in standard_ids
        assert "eu_mdr" not in standard_ids


class TestCompliancePackageE2E:
    """E2E: Full compliance package generation."""

    @pytest.fixture
    def framework(self):
        from src.core.regulatory_compliance import RegulatoryComplianceFramework
        return RegulatoryComplianceFramework()

    def test_full_compliance_report(self, framework):
        """Generate complete multi-standard compliance report."""
        product = {
            "product_name": "MedAssist Pro",
            "product_type": "samd",
            "risk_class": "II",
            "intended_use": "Clinical decision support for medication management",
            "target_regions": ["us", "eu"],
            "uses_ai_ml": False,
            "processes_images": False,
            "processes_signals": False,
            "intended_user": "physician",
            "data_sources": ["clinical_guideline", "fda_labeling"],
            "existing_artifacts": [
                "software_requirements_spec",
                "software_architecture_doc",
                "risk_management_file",
                "verification_plan",
                "audit_trail",
            ],
        }
        report = framework.generate_full_compliance_report(product)

        assert "product_name" in report
        assert "assessments" in report
        assert "overall_score" in report
        assert "roadmap" in report
        assert "generated_at" in report
        assert len(report["assessments"]) >= 4  # At minimum: IEC 62304, ISO 14971, FDA, EU MDR

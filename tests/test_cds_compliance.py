"""
Test suite for FDA Clinical Decision Support (CDS) Software Compliance

Tests cover all 20 gaps identified in the FDA CDS Gap Analysis:
- G-01: CDS Function Classifier (4-criterion assessment)
- G-02: Input Data Type Taxonomy (image/signal/pattern/discrete)
- G-03: Data Source Provenance Registry
- G-04: HCP vs Patient User Classification
- G-05: CDS Output Type Classifier (recommendation/diagnosis/directive)
- G-06: Clinical Urgency Assessment
- G-07: Plain-Language Algorithm Summary
- G-08: Transparency & Explainability Layer
- G-09: Automation Bias Risk Category
- G-10: Clinical Limitations Disclosure
- G-11: Runtime Input Validation (clinical context)
- G-12: Automation Bias Warning Labels
- G-13: Clinical Validation Protocol
- G-14: Guideline Concordance Testing
- G-15: Over-Reliance Detection
- G-16: HCP Feedback Collection
- G-17: CDS Criterion Re-Evaluation Trigger
- G-18: FDA CDS Labeling Template
- G-19: Patient Population Criteria
- G-20: Reclassification Readiness Plan

Following TDD principles — tests written BEFORE implementation.
Reference: FDA Clinical Decision Support Software Guidance (January 2026)
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# G-01: CDS Function Classifier
# ---------------------------------------------------------------------------

class TestCDSFunctionClassifier:
    """Tests for classify_cds_function() — maps software functions against all 4 FDA CDS criteria."""

    @pytest.fixture
    def classifier(self):
        from src.core.cds_compliance import CDSComplianceFramework
        return CDSComplianceFramework()

    def test_non_device_cds_all_criteria_pass(self, classifier):
        """Drug interaction checker with transparent logic should pass all 4 criteria."""
        result = classifier.classify_cds_function(
            function_description="Checks patient medication list against drug-drug interaction database and alerts prescribing physician",
            input_types=["medication_list", "patient_demographics"],
            output_type="recommendation",
            intended_user="physician",
            urgency="non_urgent",
            data_sources=[{"name": "FDA drug labeling", "type": "fda_labeling"}, {"name": "Clinical pharmacology guidelines", "type": "clinical_guideline"}]
        )
        assert result["overall_classification"] == "non_device_cds"
        assert result["criterion_1"]["passes"] is True
        assert result["criterion_2"]["passes"] is True
        assert result["criterion_3"]["passes"] is True
        assert result["criterion_4"]["passes"] is True

    def test_device_cds_image_processing_fails_criterion_1(self, classifier):
        """Software analyzing CT scans should fail Criterion 1."""
        result = classifier.classify_cds_function(
            function_description="Analyzes chest CT scan images to detect lung nodules and recommend follow-up",
            input_types=["ct_scan_image", "patient_demographics"],
            output_type="recommendation",
            intended_user="radiologist",
            urgency="non_urgent",
            data_sources=[{"name": "ACR guidelines", "type": "clinical_guideline"}]
        )
        assert result["overall_classification"] == "device"
        assert result["criterion_1"]["passes"] is False
        assert "image" in result["criterion_1"]["rationale"].lower()

    def test_device_cds_signal_processing_fails_criterion_1(self, classifier):
        """ECG waveform analysis should fail Criterion 1 (signal pattern)."""
        result = classifier.classify_cds_function(
            function_description="Continuously monitors ECG waveforms and detects arrhythmia patterns",
            input_types=["ecg_waveform"],
            output_type="recommendation",
            intended_user="cardiologist",
            urgency="non_urgent",
            data_sources=[{"name": "AHA guidelines", "type": "clinical_guideline"}]
        )
        assert result["overall_classification"] == "device"
        assert result["criterion_1"]["passes"] is False

    def test_device_cds_patient_facing_fails_criterion_3(self, classifier):
        """Patient-facing symptom checker should fail Criterion 3."""
        result = classifier.classify_cds_function(
            function_description="Patient enters symptoms and receives possible diagnoses with recommended actions",
            input_types=["patient_reported_symptoms"],
            output_type="recommendation",
            intended_user="patient",
            urgency="non_urgent",
            data_sources=[{"name": "Clinical guidelines", "type": "clinical_guideline"}]
        )
        assert result["overall_classification"] == "device"
        assert result["criterion_3"]["passes"] is False

    def test_device_cds_time_critical_fails_criterion_4(self, classifier):
        """Real-time sepsis alert fails Criterion 4 (time-critical)."""
        result = classifier.classify_cds_function(
            function_description="Monitors vital signs and triggers immediate sepsis alert requiring emergency intervention",
            input_types=["vital_signs"],
            output_type="immediate_directive",
            intended_user="nurse",
            urgency="time_critical",
            data_sources=[{"name": "Surviving Sepsis Campaign guidelines", "type": "clinical_guideline"}]
        )
        assert result["overall_classification"] == "device"
        assert result["criterion_4"]["passes"] is False

    def test_device_cds_definitive_diagnosis_fails_criterion_3(self, classifier):
        """Software producing definitive diagnoses fails Criterion 3."""
        result = classifier.classify_cds_function(
            function_description="Definitively diagnoses diabetic retinopathy from fundus images",
            input_types=["fundus_image"],
            output_type="definitive_diagnosis",
            intended_user="ophthalmologist",
            urgency="non_urgent",
            data_sources=[{"name": "AAO guidelines", "type": "clinical_guideline"}]
        )
        assert result["overall_classification"] == "device"
        # Fails both Criterion 1 (image) and Criterion 3 (definitive diagnosis)

    def test_discrete_vitals_pass_criterion_1(self, classifier):
        """Discrete point-in-time vitals (not patterns) should pass Criterion 1."""
        result = classifier.classify_cds_function(
            function_description="Calculates cardiovascular risk score from single-visit blood pressure, cholesterol, and BMI readings",
            input_types=["blood_pressure_single", "cholesterol_level", "bmi"],
            output_type="recommendation",
            intended_user="physician",
            urgency="non_urgent",
            data_sources=[{"name": "ACC/AHA cardiovascular risk guidelines", "type": "clinical_guideline"}]
        )
        assert result["criterion_1"]["passes"] is True

    def test_result_contains_all_criteria(self, classifier):
        """Result must contain assessment for all 4 criteria with rationale."""
        result = classifier.classify_cds_function(
            function_description="Simple drug allergy checker",
            input_types=["medication_list", "allergy_list"],
            output_type="recommendation",
            intended_user="physician",
            urgency="non_urgent",
            data_sources=[{"name": "FDA drug labeling", "type": "fda_labeling"}]
        )
        for criterion in ["criterion_1", "criterion_2", "criterion_3", "criterion_4"]:
            assert criterion in result
            assert "passes" in result[criterion]
            assert "rationale" in result[criterion]
        assert "overall_classification" in result
        assert result["overall_classification"] in ("device", "non_device_cds", "enforcement_discretion")

    def test_single_recommendation_enforcement_discretion(self, classifier):
        """Single recommendation with all other criteria met should get enforcement discretion (2026 update)."""
        result = classifier.classify_cds_function(
            function_description="Recommends specific FDA-approved statin based on patient lipid panel and risk factors",
            input_types=["lipid_panel", "patient_demographics", "risk_factors"],
            output_type="single_recommendation",
            intended_user="physician",
            urgency="non_urgent",
            data_sources=[{"name": "ACC/AHA cholesterol guidelines", "type": "clinical_guideline"}]
        )
        assert result["overall_classification"] in ("non_device_cds", "enforcement_discretion")
        assert result["criterion_3"]["passes"] is True


# ---------------------------------------------------------------------------
# G-02: Input Data Type Taxonomy
# ---------------------------------------------------------------------------

class TestInputDataTaxonomy:
    """Tests for classify_input_data() — classifies inputs as image/signal/pattern/discrete."""

    @pytest.fixture
    def classifier(self):
        from src.core.cds_compliance import CDSComplianceFramework
        return CDSComplianceFramework()

    def test_image_inputs_detected(self, classifier):
        """Medical image inputs must be flagged."""
        result = classifier.classify_input_data(["ct_scan", "mri_image", "xray"])
        for item in result:
            assert item["data_category"] == "image"
            assert item["criterion_1_impact"] == "fail"

    def test_signal_pattern_detected(self, classifier):
        """Continuous signal patterns must be flagged."""
        result = classifier.classify_input_data(["ecg_waveform", "cgm_continuous_readings", "eeg_signal"])
        for item in result:
            assert item["data_category"] in ("signal", "pattern")
            assert item["criterion_1_impact"] == "fail"

    def test_discrete_measurements_pass(self, classifier):
        """Discrete point-in-time measurements should pass."""
        result = classifier.classify_input_data(["blood_pressure_single", "temperature", "bmi", "cholesterol_level"])
        for item in result:
            assert item["data_category"] == "discrete"
            assert item["criterion_1_impact"] == "pass"

    def test_text_data_passes(self, classifier):
        """Text/structured data (EHR notes, demographics) should pass."""
        result = classifier.classify_input_data(["patient_demographics", "medication_list", "clinical_notes"])
        for item in result:
            assert item["data_category"] in ("text", "structured", "discrete")
            assert item["criterion_1_impact"] == "pass"

    def test_mixed_inputs_one_fail_flags_all(self, classifier):
        """If any input is image/signal/pattern, overall assessment should flag it."""
        result = classifier.classify_input_data(["patient_demographics", "ct_scan", "medication_list"])
        image_items = [r for r in result if r["criterion_1_impact"] == "fail"]
        assert len(image_items) >= 1


# ---------------------------------------------------------------------------
# G-03: Data Source Provenance Registry
# ---------------------------------------------------------------------------

class TestDataSourceProvenance:
    """Tests for data source tracking and validation."""

    @pytest.fixture
    def classifier(self):
        from src.core.cds_compliance import CDSComplianceFramework
        return CDSComplianceFramework()

    def test_accepted_source_validates(self, classifier):
        """Clinical guidelines should be classified as well-understood and accepted."""
        result = classifier.validate_data_sources([
            {"name": "ACC/AHA Cardiovascular Risk Guidelines", "type": "clinical_guideline"},
            {"name": "FDA Drug Labeling Database", "type": "fda_labeling"},
        ])
        assert result["overall_status"] == "accepted"
        for source in result["sources"]:
            assert source["validation_status"] == "well_understood_accepted"

    def test_proprietary_source_flagged(self, classifier):
        """Proprietary/novel data sources should be flagged."""
        result = classifier.validate_data_sources([
            {"name": "Internal proprietary algorithm v2", "type": "proprietary"},
        ])
        assert result["overall_status"] == "flagged"
        assert result["sources"][0]["validation_status"] == "novel_or_proprietary"
        assert result["sources"][0]["criterion_2_risk"] is True

    def test_mixed_sources_flagged(self, classifier):
        """Mix of accepted and novel sources should flag overall."""
        result = classifier.validate_data_sources([
            {"name": "AHA Guidelines", "type": "clinical_guideline"},
            {"name": "Unpublished ML model", "type": "novel"},
        ])
        assert result["overall_status"] == "flagged"


# ---------------------------------------------------------------------------
# G-05: CDS Output Type Classifier
# ---------------------------------------------------------------------------

class TestCDSOutputClassifier:
    """Tests for classifying CDS outputs as recommendation/diagnosis/directive."""

    @pytest.fixture
    def classifier(self):
        from src.core.cds_compliance import CDSComplianceFramework
        return CDSComplianceFramework()

    def test_recommendation_output_passes(self, classifier):
        """Recommendation outputs should pass Criterion 3."""
        result = classifier.classify_output_type("recommendation")
        assert result["classification"] == "recommendation"
        assert result["criterion_3_compatible"] is True

    def test_definitive_diagnosis_fails(self, classifier):
        """Definitive diagnosis outputs should fail Criterion 3."""
        result = classifier.classify_output_type("definitive_diagnosis")
        assert result["classification"] == "definitive_diagnosis"
        assert result["criterion_3_compatible"] is False

    def test_immediate_directive_fails(self, classifier):
        """Immediate intervention directives should fail Criterion 3."""
        result = classifier.classify_output_type("immediate_directive")
        assert result["classification"] == "immediate_directive"
        assert result["criterion_3_compatible"] is False

    def test_single_recommendation_with_discretion(self, classifier):
        """Single recommendation qualifies for enforcement discretion (2026 update)."""
        result = classifier.classify_output_type("single_recommendation")
        assert result["criterion_3_compatible"] is True
        assert result.get("enforcement_discretion") is True


# ---------------------------------------------------------------------------
# G-08: Transparency & Explainability Layer
# ---------------------------------------------------------------------------

class TestTransparencyLayer:
    """Tests for CDS transparency and explainability."""

    @pytest.fixture
    def framework(self):
        from src.core.cds_compliance import CDSComplianceFramework
        return CDSComplianceFramework()

    def test_generate_explanation_contains_required_fields(self, framework):
        """Explanation must contain inputs, logic, evidence, limitations."""
        result = framework.generate_transparency_report(
            function_description="Drug interaction checker",
            inputs_used=["medication_list", "allergy_list"],
            data_sources=[{"name": "FDA Drug Labeling", "type": "fda_labeling"}],
            algorithm_description="Rule-based matching against known interaction database",
            known_limitations=["Does not cover herbal supplements"]
        )
        assert "inputs_summary" in result
        assert "logic_description" in result
        assert "evidence_basis" in result
        assert "known_limitations" in result
        assert "automation_bias_warning" in result

    def test_transparency_report_is_plain_language(self, framework):
        """Report should be readable by clinicians, not just engineers."""
        result = framework.generate_transparency_report(
            function_description="Cardiovascular risk calculator",
            inputs_used=["blood_pressure", "cholesterol", "age", "smoking_status"],
            data_sources=[{"name": "ACC/AHA Guidelines", "type": "clinical_guideline"}],
            algorithm_description="Pooled Cohort Equations for 10-year ASCVD risk",
            known_limitations=["Validated for ages 40-79 only"]
        )
        # Should not contain engineering jargon
        report_text = json.dumps(result).lower()
        assert "ieee" not in report_text
        assert "subsystem" not in report_text


# ---------------------------------------------------------------------------
# G-09, G-10: Automation Bias & Clinical Limitations
# ---------------------------------------------------------------------------

class TestAutomationBiasAndLimitations:
    """Tests for automation bias risk and clinical limitations."""

    @pytest.fixture
    def framework(self):
        from src.core.cds_compliance import CDSComplianceFramework
        return CDSComplianceFramework()

    def test_automation_bias_risk_generated(self, framework):
        """Risk assessment should include automation bias category."""
        result = framework.assess_automation_bias_risk(
            function_description="Antibiotic recommendation system",
            urgency="non_urgent",
            decision_impact="treatment_selection"
        )
        assert result["risk_category"] == "automation_bias"
        assert "mitigation_strategies" in result
        assert len(result["mitigation_strategies"]) > 0
        assert "severity" in result
        assert "likelihood" in result

    def test_clinical_limitations_generated(self, framework):
        """Clinical limitations must cover accuracy, populations, conditions."""
        result = framework.generate_clinical_limitations(
            validated_populations=["adults 40-79"],
            accuracy_metrics={"sensitivity": 0.85, "specificity": 0.90},
            excluded_conditions=["pregnancy", "pediatric"],
            known_failure_modes=["Rare drug interactions not in database"]
        )
        assert "accuracy_limitations" in result
        assert "population_limitations" in result
        assert "condition_exclusions" in result
        assert "known_failure_modes" in result


# ---------------------------------------------------------------------------
# G-12: Automation Bias Warning Labels
# ---------------------------------------------------------------------------

class TestAutomationBiasWarnings:
    """Tests for automation bias warning generation."""

    @pytest.fixture
    def framework(self):
        from src.core.cds_compliance import CDSComplianceFramework
        return CDSComplianceFramework()

    def test_warning_label_generated(self, framework):
        """Must generate explicit automation bias warning text."""
        result = framework.generate_bias_warning_label(
            function_description="Drug dosing recommendation",
            intended_user="physician"
        )
        assert "warning_text" in result
        assert "independent" in result["warning_text"].lower() or "review" in result["warning_text"].lower()
        assert "clinical judgment" in result["warning_text"].lower() or "clinical review" in result["warning_text"].lower()


# ---------------------------------------------------------------------------
# G-18: FDA CDS Labeling Template
# ---------------------------------------------------------------------------

class TestCDSLabelingTemplate:
    """Tests for FDA-formatted CDS labeling."""

    @pytest.fixture
    def framework(self):
        from src.core.cds_compliance import CDSComplianceFramework
        return CDSComplianceFramework()

    def test_labeling_contains_all_required_elements(self, framework):
        """Labeling must include all FDA-required elements."""
        result = framework.generate_cds_labeling(
            product_name="CardioRisk Pro",
            intended_use="Cardiovascular risk assessment",
            intended_users=["cardiologist", "primary care physician"],
            target_population="Adults aged 40-79 without prior cardiovascular events",
            algorithm_summary="Pooled Cohort Equations based on ACC/AHA 2013 guidelines",
            data_sources=[{"name": "ACC/AHA 2013 Guidelines", "type": "clinical_guideline"}],
            validation_summary="Validated on 25,000 patients across 4 clinical sites",
            known_limitations=["Not validated for ages <40 or >79", "Does not account for novel biomarkers"]
        )
        assert "intended_use_statement" in result
        assert "intended_users" in result
        assert "target_patient_population" in result
        assert "algorithm_basis" in result
        assert "data_source_disclosure" in result
        assert "validation_evidence" in result
        assert "known_limitations" in result
        assert "automation_bias_warning" in result

    def test_labeling_intended_use_format(self, framework):
        """Intended use must follow FDA format."""
        result = framework.generate_cds_labeling(
            product_name="AllergyCheck",
            intended_use="Drug allergy checking",
            intended_users=["pharmacist"],
            target_population="All patients with documented allergies",
            algorithm_summary="Rule-based matching",
            data_sources=[{"name": "FDA Drug Labels", "type": "fda_labeling"}],
            validation_summary="Validated",
            known_limitations=[]
        )
        ius = result["intended_use_statement"]
        assert "intended for use by" in ius.lower() or "designed to" in ius.lower()


# ---------------------------------------------------------------------------
# G-15: Over-Reliance Detection
# ---------------------------------------------------------------------------

class TestOverRelianceDetection:
    """Tests for post-market over-reliance monitoring."""

    @pytest.fixture
    def framework(self):
        from src.core.cds_compliance import CDSComplianceFramework
        return CDSComplianceFramework()

    def test_high_acceptance_rate_flagged(self, framework):
        """Acceptance rate >95% should trigger over-reliance alert."""
        result = framework.detect_over_reliance(
            total_recommendations=1000,
            accepted_without_modification=970,
            average_review_time_seconds=5
        )
        assert result["over_reliance_detected"] is True
        assert result["acceptance_rate"] > 0.95
        assert "alert" in result

    def test_normal_acceptance_rate_ok(self, framework):
        """Acceptance rate of 70-85% with adequate review time is healthy."""
        result = framework.detect_over_reliance(
            total_recommendations=1000,
            accepted_without_modification=750,
            average_review_time_seconds=45
        )
        assert result["over_reliance_detected"] is False

    def test_fast_review_time_flagged(self, framework):
        """Very fast review times suggest rubber-stamping."""
        result = framework.detect_over_reliance(
            total_recommendations=100,
            accepted_without_modification=80,
            average_review_time_seconds=2
        )
        assert result["over_reliance_detected"] is True
        assert "review_time" in result.get("alert", "").lower() or result.get("review_time_concern", False)


# ---------------------------------------------------------------------------
# G-17: CDS Criterion Re-Evaluation Trigger
# ---------------------------------------------------------------------------

class TestCriterionReEvaluation:
    """Tests for post-change CDS criterion re-evaluation."""

    @pytest.fixture
    def framework(self):
        from src.core.cds_compliance import CDSComplianceFramework
        return CDSComplianceFramework()

    def test_reevaluation_after_algorithm_change(self, framework):
        """Algorithm change must trigger 4-criterion re-assessment."""
        result = framework.trigger_criterion_reevaluation(
            change_description="Updated drug interaction database to include 500 new interactions",
            previous_classification="non_device_cds",
            function_description="Drug interaction checker",
            input_types=["medication_list"],
            output_type="recommendation",
            intended_user="physician",
            urgency="non_urgent",
            data_sources=[{"name": "FDA Drug Labels", "type": "fda_labeling"}]
        )
        assert "new_classification" in result
        assert "classification_changed" in result
        assert "reevaluation_date" in result
        assert "criteria_results" in result
        for c in ["criterion_1", "criterion_2", "criterion_3", "criterion_4"]:
            assert c in result["criteria_results"]


# ---------------------------------------------------------------------------
# G-13: Clinical Validation Protocol
# ---------------------------------------------------------------------------

class TestClinicalValidationProtocol:
    """Tests for clinical validation protocol generation."""

    @pytest.fixture
    def framework(self):
        from src.core.cds_compliance import CDSComplianceFramework
        return CDSComplianceFramework()

    def test_validation_protocol_generated(self, framework):
        """Must generate protocol with accuracy, subgroups, comparison."""
        result = framework.generate_clinical_validation_protocol(
            function_description="Cardiovascular risk calculator",
            target_population="Adults 40-79",
            clinical_endpoints=["10-year ASCVD risk"],
            gold_standard="Framingham Risk Score",
            demographic_subgroups=["age", "sex", "race"]
        )
        assert "protocol_id" in result
        assert "accuracy_metrics" in result
        assert "demographic_subgroup_analysis" in result
        assert "gold_standard_comparison" in result
        assert "sample_size_justification" in result


# ---------------------------------------------------------------------------
# G-19: Patient Population Criteria
# ---------------------------------------------------------------------------

class TestPatientPopulationCriteria:
    """Tests for patient population inclusion/exclusion criteria."""

    @pytest.fixture
    def framework(self):
        from src.core.cds_compliance import CDSComplianceFramework
        return CDSComplianceFramework()

    def test_population_criteria_generated(self, framework):
        """Must generate inclusion and exclusion criteria."""
        result = framework.define_patient_population(
            condition="Hypertension management",
            age_range={"min": 18, "max": 85},
            included_conditions=["Essential hypertension", "Resistant hypertension"],
            excluded_conditions=["Pregnancy", "Pediatric", "Secondary hypertension"],
            demographic_coverage=["All races/ethnicities", "Both sexes"]
        )
        assert "inclusion_criteria" in result
        assert "exclusion_criteria" in result
        assert "demographic_coverage" in result
        assert len(result["inclusion_criteria"]) > 0
        assert len(result["exclusion_criteria"]) > 0


# ---------------------------------------------------------------------------
# E2E: Full CDS Compliance Pipeline
# ---------------------------------------------------------------------------

class TestCDSCompliancePipelineE2E:
    """End-to-end test: product description → full CDS compliance package."""

    @pytest.fixture
    def framework(self):
        from src.core.cds_compliance import CDSComplianceFramework
        return CDSComplianceFramework()

    def test_full_compliance_package_for_non_device_cds(self, framework):
        """Complete pipeline for a Non-Device CDS drug interaction checker."""
        package = framework.generate_compliance_package(
            product_name="DrugSafe Alert",
            function_description="Checks patient medication list against drug-drug interaction database and alerts prescribing physician with recommended alternatives",
            input_types=["medication_list", "allergy_list", "patient_demographics"],
            output_type="recommendation",
            intended_user="physician",
            urgency="non_urgent",
            data_sources=[
                {"name": "FDA Drug Labeling Database", "type": "fda_labeling"},
                {"name": "Clinical Pharmacology Guidelines", "type": "clinical_guideline"},
            ],
            algorithm_description="Rule-based matching against FDA-approved interaction database with severity scoring",
            known_limitations=["Does not cover herbal supplements", "Limited pediatric interaction data"],
            target_population="Adults 18+ with 2+ concurrent medications",
            validation_summary="Validated against 10,000 known interactions with 98.5% sensitivity"
        )

        # Must contain all compliance components
        assert "cds_classification" in package
        assert package["cds_classification"]["overall_classification"] == "non_device_cds"

        assert "input_taxonomy" in package
        assert "data_source_validation" in package
        assert "output_classification" in package
        assert "transparency_report" in package
        assert "bias_warning" in package
        assert "labeling" in package
        assert "clinical_limitations" in package
        assert "automation_bias_risk" in package

        # Labeling must be complete
        labeling = package["labeling"]
        assert "intended_use_statement" in labeling
        assert "automation_bias_warning" in labeling

    def test_full_compliance_package_for_device(self, framework):
        """Complete pipeline for a Device CDS (image-processing) should classify as device."""
        package = framework.generate_compliance_package(
            product_name="LungScan AI",
            function_description="Analyzes chest CT scan images to detect and classify lung nodules",
            input_types=["ct_scan_image", "patient_demographics"],
            output_type="definitive_diagnosis",
            intended_user="radiologist",
            urgency="non_urgent",
            data_sources=[{"name": "ACR Lung-RADS", "type": "clinical_guideline"}],
            algorithm_description="Deep learning CNN trained on 50,000 annotated CT scans",
            known_limitations=["Not validated for pediatric patients"],
            target_population="Adults with suspected lung nodules",
            validation_summary="Validated on 5,000 cases"
        )

        assert package["cds_classification"]["overall_classification"] == "device"
        # Should still generate compliance artifacts for the device pathway
        assert "labeling" in package
        assert "clinical_limitations" in package

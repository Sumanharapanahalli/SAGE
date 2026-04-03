"""
SAGE[ai] - FDA Clinical Decision Support (CDS) Compliance Framework
====================================================================
Implements compliance checks against FDA's Clinical Decision Support Software
Guidance (January 2026, media/109618).

Covers all 4 Non-Device CDS criteria:
  Criterion 1: No image/signal processing
  Criterion 2: Medical information from well-understood sources
  Criterion 3: HCP recommendations (support, not replace)
  Criterion 4: Independent review & transparency

Also covers:
  - Input data type taxonomy (image/signal/pattern/discrete)
  - Data source provenance validation
  - Output type classification (recommendation/diagnosis/directive)
  - Transparency & explainability reports
  - Automation bias risk assessment and warnings
  - Clinical limitations disclosure
  - FDA CDS labeling template
  - Over-reliance detection (post-market)
  - CDS criterion re-evaluation triggers
  - Clinical validation protocol generation
  - Patient population criteria
  - Full compliance package generation

Reference: FDA Clinical Decision Support Software Guidance (January 6, 2026)
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input classification rules — FDA Criterion 1
# ---------------------------------------------------------------------------

IMAGE_KEYWORDS = frozenset([
    "image", "scan", "ct_scan", "mri", "xray", "x_ray", "x-ray",
    "ultrasound", "mammogram", "fundus", "retinal", "pathology",
    "dermatology", "dermoscopy", "endoscopy", "fluoroscopy",
    "pet_scan", "spect", "angiography", "radiograph",
    "ct_scan_image", "mri_image", "fundus_image",
])

SIGNAL_PATTERN_KEYWORDS = frozenset([
    "ecg", "ekg", "ecg_waveform", "eeg", "eeg_signal", "emg",
    "cgm", "cgm_continuous", "cgm_continuous_readings",
    "holter", "waveform", "continuous_monitoring",
    "ngs", "genomic_sequence", "next_gen_sequencing",
    "pulse_oximetry_waveform", "arterial_line_waveform",
    "fetal_heart_rate_tracing", "polysomnography",
])

DISCRETE_KEYWORDS = frozenset([
    "blood_pressure_single", "blood_pressure", "temperature",
    "bmi", "weight", "height", "heart_rate_single",
    "cholesterol_level", "cholesterol", "glucose_single",
    "hemoglobin", "creatinine", "lipid_panel",
    "patient_demographics", "age", "sex", "race",
    "medication_list", "allergy_list", "diagnosis_code",
    "lab_result", "vital_signs", "smoking_status",
    "clinical_notes", "patient_reported_symptoms",
    "discharge_summary", "risk_factors",
])

# Data source types and their FDA classification
SOURCE_ACCEPTED_TYPES = frozenset([
    "clinical_guideline", "peer_reviewed", "fda_labeling",
    "government", "textbook", "professional_society",
])

SOURCE_FLAGGED_TYPES = frozenset([
    "proprietary", "novel", "unpublished", "internal",
])


class CDSComplianceFramework:
    """
    FDA Clinical Decision Support Software compliance framework.

    Implements the 4-criterion test from the January 2026 FDA guidance
    to classify software functions as Device CDS or Non-Device CDS.
    """

    def __init__(self):
        self.logger = logging.getLogger("CDSCompliance")

    # ------------------------------------------------------------------
    # G-01: CDS Function Classifier
    # ------------------------------------------------------------------

    def classify_cds_function(
        self,
        function_description: str,
        input_types: List[str],
        output_type: str,
        intended_user: str,
        urgency: str,
        data_sources: List[Dict],
    ) -> Dict:
        """
        Classify a software function against all 4 FDA CDS criteria.

        Returns dict with per-criterion pass/fail, rationale, and
        overall classification (device / non_device_cds / enforcement_discretion).
        """
        c1 = self._evaluate_criterion_1(input_types, function_description)
        c2 = self._evaluate_criterion_2(data_sources)
        c3 = self._evaluate_criterion_3(output_type, intended_user, function_description)
        c4 = self._evaluate_criterion_4(urgency, function_description, output_type)

        all_pass = all(c["passes"] for c in [c1, c2, c3, c4])

        if all_pass:
            if output_type == "single_recommendation":
                classification = "enforcement_discretion"
            else:
                classification = "non_device_cds"
        else:
            classification = "device"

        return {
            "criterion_1": c1,
            "criterion_2": c2,
            "criterion_3": c3,
            "criterion_4": c4,
            "overall_classification": classification,
            "function_description": function_description,
            "assessment_date": datetime.now(timezone.utc).isoformat(),
            "guidance_reference": "FDA CDS Software Guidance, January 2026",
        }

    def _evaluate_criterion_1(self, input_types: List[str], description: str) -> Dict:
        """Criterion 1: Software must NOT acquire/process/analyze images or signals."""
        desc_lower = description.lower()
        flagged_inputs = []

        for inp in input_types:
            inp_lower = inp.lower().replace(" ", "_")
            if inp_lower in IMAGE_KEYWORDS or any(kw in inp_lower for kw in IMAGE_KEYWORDS):
                flagged_inputs.append({"input": inp, "reason": "medical image processing"})
            elif inp_lower in SIGNAL_PATTERN_KEYWORDS or any(kw in inp_lower for kw in SIGNAL_PATTERN_KEYWORDS):
                flagged_inputs.append({"input": inp, "reason": "signal/pattern processing"})

        # Also check description for image/signal keywords
        image_desc_hits = [kw for kw in ["image", "scan", "ct ", "mri ", "x-ray", "xray",
                                          "radiograph", "ultrasound", "fundus", "pathology",
                                          "dermoscop", "endoscop", "mammogra"]
                          if kw in desc_lower]
        signal_desc_hits = [kw for kw in ["waveform", "ecg", "ekg", "eeg", "cgm",
                                           "continuous monitor", "holter", "genomic seq"]
                           if kw in desc_lower]

        if image_desc_hits and not flagged_inputs:
            flagged_inputs.append({"input": "description", "reason": f"image keywords in description: {image_desc_hits}"})
        if signal_desc_hits and not flagged_inputs:
            flagged_inputs.append({"input": "description", "reason": f"signal keywords in description: {signal_desc_hits}"})

        passes = len(flagged_inputs) == 0
        if passes:
            rationale = "No medical image, IVD signal, or pattern processing detected in inputs or function description."
        else:
            reasons = "; ".join(f"{f['input']}: {f['reason']}" for f in flagged_inputs)
            rationale = f"Criterion 1 FAILS — image/signal/pattern processing detected: {reasons}"

        return {"passes": passes, "rationale": rationale, "flagged_inputs": flagged_inputs}

    def _evaluate_criterion_2(self, data_sources: List[Dict]) -> Dict:
        """Criterion 2: Software must use medical information from well-understood sources."""
        if not data_sources:
            return {
                "passes": False,
                "rationale": "No data sources provided. Criterion 2 requires identifiable medical information sources.",
                "flagged_sources": [],
            }

        flagged = []
        accepted = []
        for src in data_sources:
            src_type = src.get("type", "unknown").lower()
            if src_type in SOURCE_FLAGGED_TYPES or src_type == "unknown":
                flagged.append({"source": src.get("name", "unnamed"), "type": src_type,
                               "reason": "Not a well-understood and accepted source per FDA guidance"})
            else:
                accepted.append(src.get("name", "unnamed"))

        # Passes if at least one accepted source and no flagged-only scenario
        passes = len(accepted) > 0 and len(flagged) == 0
        if passes:
            rationale = f"All data sources are well-understood and accepted: {', '.join(accepted)}"
        elif flagged:
            rationale = f"Criterion 2 at RISK — flagged sources: {'; '.join(f['source'] + ' (' + f['type'] + ')' for f in flagged)}"
            # If there are also accepted sources, it's a mixed situation — still risky
            if accepted:
                passes = False  # Conservative: any flagged source is a risk
        else:
            rationale = "No accepted data sources identified."

        return {"passes": passes, "rationale": rationale, "flagged_sources": flagged}

    def _evaluate_criterion_3(self, output_type: str, intended_user: str, description: str) -> Dict:
        """Criterion 3: Software must support HCP decision-making, not replace it."""
        issues = []

        # Check intended user is HCP
        hcp_roles = {"physician", "doctor", "nurse", "pharmacist", "therapist",
                     "cardiologist", "radiologist", "surgeon", "ophthalmologist",
                     "psychiatrist", "oncologist", "hcp", "clinician",
                     "healthcare_professional", "prescriber", "provider",
                     "primary care physician", "specialist"}
        user_lower = intended_user.lower().replace("_", " ")
        is_hcp = any(role in user_lower for role in hcp_roles)

        if not is_hcp:
            issues.append(f"Intended user '{intended_user}' is not a healthcare professional")

        # Check output type
        device_outputs = {"definitive_diagnosis", "immediate_directive"}
        if output_type in device_outputs:
            issues.append(f"Output type '{output_type}' directs rather than supports clinical judgment")

        # Check description for directive language
        desc_lower = description.lower()
        directive_phrases = ["definitively diagnos", "automatically treat",
                            "directs the clinician", "replaces clinical judgment"]
        for phrase in directive_phrases:
            if phrase in desc_lower:
                issues.append(f"Description contains directive language: '{phrase}'")

        passes = len(issues) == 0
        if passes:
            rationale = f"Software supports {intended_user} decision-making with '{output_type}' output. Does not replace clinical judgment."
        else:
            rationale = f"Criterion 3 FAILS — {'; '.join(issues)}"

        return {"passes": passes, "rationale": rationale, "issues": issues}

    def _evaluate_criterion_4(self, urgency: str, description: str, output_type: str) -> Dict:
        """Criterion 4: HCP must be able to independently review the basis."""
        issues = []

        # Time-critical assessment
        if urgency in ("time_critical", "urgent", "emergency"):
            issues.append(f"Urgency '{urgency}' — clinician lacks time for independent review")

        # Check for black-box indicators
        desc_lower = description.lower()
        blackbox_phrases = ["black box", "opaque", "unexplainable",
                           "no explanation provided", "automatic", "immediate"]
        for phrase in blackbox_phrases:
            if phrase in desc_lower:
                issues.append(f"Description suggests limited transparency: '{phrase}'")

        # Immediate directives inherently limit review time
        if output_type == "immediate_directive":
            issues.append("Immediate directive output limits independent review opportunity")

        passes = len(issues) == 0
        if passes:
            rationale = "Non-urgent workflow allows HCP independent review of recommendation basis."
        else:
            rationale = f"Criterion 4 FAILS — {'; '.join(issues)}"

        return {"passes": passes, "rationale": rationale, "issues": issues}

    # ------------------------------------------------------------------
    # G-02: Input Data Type Taxonomy
    # ------------------------------------------------------------------

    def classify_input_data(self, input_types: List[str]) -> List[Dict]:
        """Classify input data types as image/signal/pattern/discrete/text."""
        results = []
        for inp in input_types:
            inp_lower = inp.lower().replace(" ", "_").replace("-", "_")

            if inp_lower in IMAGE_KEYWORDS or any(kw in inp_lower for kw in
                                                    ["image", "scan", "xray", "mri", "ct_scan",
                                                     "fundus", "pathology", "dermoscop",
                                                     "mammogra", "ultrasound", "endoscop"]):
                category = "image"
                impact = "fail"
            elif inp_lower in SIGNAL_PATTERN_KEYWORDS or any(kw in inp_lower for kw in
                                                              ["waveform", "ecg", "eeg", "emg",
                                                               "cgm_continuous", "holter",
                                                               "continuous_monitor", "ngs",
                                                               "genomic_seq"]):
                category = "signal" if "waveform" in inp_lower or "signal" in inp_lower else "pattern"
                impact = "fail"
            elif inp_lower in DISCRETE_KEYWORDS or any(kw in inp_lower for kw in
                                                        ["single", "level", "demographics",
                                                         "list", "code", "notes", "summary",
                                                         "temperature", "bmi", "weight"]):
                category = "discrete"
                impact = "pass"
            else:
                # Default: treat unknown as structured/text (conservative pass)
                category = "structured"
                impact = "pass"

            results.append({
                "input_type": inp,
                "data_category": category,
                "criterion_1_impact": impact,
            })
        return results

    # ------------------------------------------------------------------
    # G-03: Data Source Provenance Registry
    # ------------------------------------------------------------------

    def validate_data_sources(self, sources: List[Dict]) -> Dict:
        """Validate data sources against FDA accepted source types."""
        validated = []
        has_flagged = False

        for src in sources:
            src_type = src.get("type", "unknown").lower()
            if src_type in SOURCE_ACCEPTED_TYPES:
                status = "well_understood_accepted"
                risk = False
            else:
                status = "novel_or_proprietary"
                risk = True
                has_flagged = True

            validated.append({
                "name": src.get("name", "unnamed"),
                "type": src_type,
                "validation_status": status,
                "criterion_2_risk": risk,
            })

        return {
            "sources": validated,
            "overall_status": "flagged" if has_flagged else "accepted",
            "assessment_date": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # G-05: CDS Output Type Classifier
    # ------------------------------------------------------------------

    def classify_output_type(self, output_type: str) -> Dict:
        """Classify CDS output as recommendation/diagnosis/directive."""
        output_lower = output_type.lower()

        if output_lower in ("recommendation", "alert", "suggestion"):
            return {
                "classification": "recommendation",
                "criterion_3_compatible": True,
                "enforcement_discretion": False,
            }
        elif output_lower == "single_recommendation":
            return {
                "classification": "single_recommendation",
                "criterion_3_compatible": True,
                "enforcement_discretion": True,
            }
        elif output_lower in ("definitive_diagnosis", "diagnosis"):
            return {
                "classification": "definitive_diagnosis",
                "criterion_3_compatible": False,
                "enforcement_discretion": False,
            }
        elif output_lower in ("immediate_directive", "directive", "order"):
            return {
                "classification": "immediate_directive",
                "criterion_3_compatible": False,
                "enforcement_discretion": False,
            }
        else:
            return {
                "classification": output_lower,
                "criterion_3_compatible": False,
                "enforcement_discretion": False,
            }

    # ------------------------------------------------------------------
    # G-08: Transparency & Explainability Layer
    # ------------------------------------------------------------------

    def generate_transparency_report(
        self,
        function_description: str,
        inputs_used: List[str],
        data_sources: List[Dict],
        algorithm_description: str,
        known_limitations: List[str],
    ) -> Dict:
        """Generate a clinician-facing transparency report for Criterion 4 compliance."""
        return {
            "report_id": f"TR-{uuid.uuid4().hex[:8].upper()}",
            "function": function_description,
            "inputs_summary": f"This tool uses the following patient data: {', '.join(inputs_used)}.",
            "logic_description": (
                f"How this recommendation is generated: {algorithm_description}. "
                "The recommendation is based on established clinical evidence and should be "
                "reviewed by the treating clinician before any clinical action."
            ),
            "evidence_basis": [
                f"{src.get('name', 'Unknown')} ({src.get('type', 'unknown')})"
                for src in data_sources
            ],
            "known_limitations": known_limitations,
            "automation_bias_warning": (
                "IMPORTANT: This tool provides clinical decision support only. "
                "It does not replace independent clinical judgment. The healthcare "
                "professional must independently review the basis for any recommendation "
                "before making clinical decisions. Do not rely solely on this output."
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # G-09: Automation Bias Risk Assessment
    # ------------------------------------------------------------------

    def assess_automation_bias_risk(
        self,
        function_description: str,
        urgency: str,
        decision_impact: str,
    ) -> Dict:
        """Assess automation bias risk for a CDS function."""
        severity_map = {
            "treatment_selection": "high",
            "diagnostic_support": "high",
            "screening": "medium",
            "administrative": "low",
            "informational": "low",
        }
        severity = severity_map.get(decision_impact, "medium")

        likelihood_map = {
            "time_critical": "high",
            "urgent": "high",
            "non_urgent": "medium",
        }
        likelihood = likelihood_map.get(urgency, "medium")

        mitigation_strategies = [
            "Display recommendation rationale alongside output",
            "Require explicit clinician acknowledgment before action",
            "Show alternative recommendations when clinically appropriate",
            "Include confidence level or uncertainty indicator with output",
            "Provide access to underlying data and evidence sources",
            "Design for non-urgent workflows that allow review time",
            "Implement periodic clinician training on appropriate CDS use",
        ]

        if urgency in ("time_critical", "urgent"):
            mitigation_strategies.append(
                "CRITICAL: Time-critical workflows increase automation bias risk. "
                "Consider whether this function should be classified as a medical device."
            )

        return {
            "risk_category": "automation_bias",
            "function": function_description,
            "severity": severity,
            "likelihood": likelihood,
            "risk_level": "high" if severity == "high" and likelihood == "high" else
                         "medium" if severity == "high" or likelihood == "high" else "low",
            "mitigation_strategies": mitigation_strategies,
            "assessment_date": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # G-10: Clinical Limitations Disclosure
    # ------------------------------------------------------------------

    def generate_clinical_limitations(
        self,
        validated_populations: List[str],
        accuracy_metrics: Dict,
        excluded_conditions: List[str],
        known_failure_modes: List[str],
    ) -> Dict:
        """Generate clinical limitations disclosure for FDA labeling."""
        return {
            "accuracy_limitations": {
                "metrics": accuracy_metrics,
                "note": "These accuracy metrics were measured on the validation population "
                        "and may not generalize to all patient populations.",
            },
            "population_limitations": {
                "validated_on": validated_populations,
                "note": "Performance has not been validated outside the listed populations.",
            },
            "condition_exclusions": {
                "excluded": excluded_conditions,
                "note": "This tool should not be used for patients with the listed conditions.",
            },
            "known_failure_modes": known_failure_modes,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # G-12: Automation Bias Warning Labels
    # ------------------------------------------------------------------

    def generate_bias_warning_label(
        self,
        function_description: str,
        intended_user: str,
    ) -> Dict:
        """Generate automation bias warning text for CDS labeling."""
        return {
            "warning_text": (
                f"CLINICAL DECISION SUPPORT NOTICE: This {function_description} "
                f"is intended to support {intended_user} clinical judgment, not replace it. "
                "The healthcare professional must exercise independent clinical review "
                "of the basis for any recommendation before making patient care decisions. "
                "Do not rely primarily on this software output for clinical decisions."
            ),
            "short_warning": (
                "Decision support only. Independent clinical judgment required."
            ),
            "placement_requirements": [
                "Display prominently in user interface near recommendation output",
                "Include in product labeling and user documentation",
                "Present during initial setup and periodically during use",
            ],
        }

    # ------------------------------------------------------------------
    # G-13: Clinical Validation Protocol
    # ------------------------------------------------------------------

    def generate_clinical_validation_protocol(
        self,
        function_description: str,
        target_population: str,
        clinical_endpoints: List[str],
        gold_standard: str,
        demographic_subgroups: List[str],
    ) -> Dict:
        """Generate clinical validation protocol for FDA submission."""
        protocol_id = f"CVP-{uuid.uuid4().hex[:8].upper()}"

        return {
            "protocol_id": protocol_id,
            "function": function_description,
            "target_population": target_population,
            "accuracy_metrics": {
                "primary": ["Sensitivity", "Specificity", "Positive Predictive Value", "Negative Predictive Value"],
                "secondary": ["AUC-ROC", "F1 Score", "Calibration (Hosmer-Lemeshow)"],
                "endpoints": clinical_endpoints,
            },
            "gold_standard_comparison": {
                "reference_standard": gold_standard,
                "comparison_methodology": "Head-to-head comparison on same patient cohort",
                "statistical_tests": ["McNemar's test for paired proportions", "DeLong test for AUC comparison"],
            },
            "demographic_subgroup_analysis": {
                "subgroups": demographic_subgroups,
                "methodology": "Stratified analysis with interaction testing",
                "minimum_per_subgroup": 100,
                "bias_detection": "Fairness metrics (equalized odds, demographic parity)",
            },
            "sample_size_justification": {
                "methodology": "Power analysis for primary endpoint",
                "minimum_events": 100,
                "target_power": 0.80,
                "significance_level": 0.05,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # G-15: Over-Reliance Detection
    # ------------------------------------------------------------------

    def detect_over_reliance(
        self,
        total_recommendations: int,
        accepted_without_modification: int,
        average_review_time_seconds: float,
    ) -> Dict:
        """Detect potential over-reliance patterns in CDS usage."""
        acceptance_rate = accepted_without_modification / max(total_recommendations, 1)
        review_time_concern = average_review_time_seconds < 10

        over_reliance = acceptance_rate > 0.95 or review_time_concern

        alert_reasons = []
        if acceptance_rate > 0.95:
            alert_reasons.append(
                f"Acceptance rate {acceptance_rate:.1%} exceeds 95% threshold — "
                "may indicate insufficient independent review"
            )
        if review_time_concern:
            alert_reasons.append(
                f"Average review time {average_review_time_seconds:.0f}s is below 10s minimum — "
                "review time suggests rubber-stamping"
            )

        return {
            "over_reliance_detected": over_reliance,
            "acceptance_rate": acceptance_rate,
            "average_review_time_seconds": average_review_time_seconds,
            "review_time_concern": review_time_concern,
            "alert": "; ".join(alert_reasons) if alert_reasons else "No over-reliance indicators detected",
            "recommendation": (
                "Consider retraining clinicians on appropriate CDS use and "
                "implementing mandatory review checkpoints"
                if over_reliance else "Usage patterns are within acceptable range"
            ),
            "assessment_date": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # G-17: CDS Criterion Re-Evaluation Trigger
    # ------------------------------------------------------------------

    def trigger_criterion_reevaluation(
        self,
        change_description: str,
        previous_classification: str,
        function_description: str,
        input_types: List[str],
        output_type: str,
        intended_user: str,
        urgency: str,
        data_sources: List[Dict],
    ) -> Dict:
        """Re-evaluate CDS criteria after an algorithm change."""
        new_result = self.classify_cds_function(
            function_description=function_description,
            input_types=input_types,
            output_type=output_type,
            intended_user=intended_user,
            urgency=urgency,
            data_sources=data_sources,
        )

        new_classification = new_result["overall_classification"]
        changed = new_classification != previous_classification

        return {
            "change_description": change_description,
            "previous_classification": previous_classification,
            "new_classification": new_classification,
            "classification_changed": changed,
            "reevaluation_date": datetime.now(timezone.utc).isoformat(),
            "criteria_results": {
                "criterion_1": new_result["criterion_1"],
                "criterion_2": new_result["criterion_2"],
                "criterion_3": new_result["criterion_3"],
                "criterion_4": new_result["criterion_4"],
            },
            "action_required": (
                f"CLASSIFICATION CHANGED from {previous_classification} to {new_classification}. "
                "Regulatory pathway review required."
                if changed else "Classification unchanged. Document re-evaluation in change record."
            ),
        }

    # ------------------------------------------------------------------
    # G-18: FDA CDS Labeling Template
    # ------------------------------------------------------------------

    def generate_cds_labeling(
        self,
        product_name: str,
        intended_use: str,
        intended_users: List[str],
        target_population: str,
        algorithm_summary: str,
        data_sources: List[Dict],
        validation_summary: str,
        known_limitations: List[str],
    ) -> Dict:
        """Generate FDA-formatted CDS labeling."""
        users_str = ", ".join(intended_users)
        sources_str = "; ".join(s.get("name", "Unknown") for s in data_sources)

        return {
            "product_name": product_name,
            "intended_use_statement": (
                f"{product_name} is intended for use by {users_str} "
                f"to support clinical decision-making for {intended_use}. "
                "This software provides recommendations to support, not replace, "
                "independent clinical judgment."
            ),
            "intended_users": intended_users,
            "target_patient_population": target_population,
            "algorithm_basis": (
                f"How recommendations are generated: {algorithm_summary}. "
                "All recommendations are grounded in established clinical evidence."
            ),
            "data_source_disclosure": {
                "sources": [
                    {"name": s.get("name", "Unknown"), "type": s.get("type", "unknown")}
                    for s in data_sources
                ],
                "summary": f"This software uses the following evidence sources: {sources_str}.",
            },
            "validation_evidence": validation_summary,
            "known_limitations": known_limitations,
            "automation_bias_warning": (
                f"IMPORTANT: {product_name} provides clinical decision support only. "
                f"The {users_str} must independently review the basis for any "
                "recommendation and exercise independent clinical judgment before "
                "making patient care decisions. Do not rely primarily on this "
                "software output for clinical decisions."
            ),
            "regulatory_status": "Non-Device Clinical Decision Support Software per FDA CDS Guidance (2026)",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # G-19: Patient Population Criteria
    # ------------------------------------------------------------------

    def define_patient_population(
        self,
        condition: str,
        age_range: Dict,
        included_conditions: List[str],
        excluded_conditions: List[str],
        demographic_coverage: List[str],
    ) -> Dict:
        """Define patient population inclusion/exclusion criteria."""
        inclusion = [
            f"Age {age_range.get('min', 0)}-{age_range.get('max', 120)} years",
        ] + [f"Diagnosis of {c}" for c in included_conditions]

        exclusion = [f"{c}" for c in excluded_conditions]

        return {
            "condition": condition,
            "inclusion_criteria": inclusion,
            "exclusion_criteria": exclusion,
            "age_range": age_range,
            "demographic_coverage": demographic_coverage,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # E2E: Full Compliance Package
    # ------------------------------------------------------------------

    def generate_compliance_package(
        self,
        product_name: str,
        function_description: str,
        input_types: List[str],
        output_type: str,
        intended_user: str,
        urgency: str,
        data_sources: List[Dict],
        algorithm_description: str,
        known_limitations: List[str],
        target_population: str,
        validation_summary: str,
    ) -> Dict:
        """Generate complete FDA CDS compliance package."""
        self.logger.info("Generating CDS compliance package for: %s", product_name)

        # 1. CDS Function Classification (G-01)
        classification = self.classify_cds_function(
            function_description=function_description,
            input_types=input_types,
            output_type=output_type,
            intended_user=intended_user,
            urgency=urgency,
            data_sources=data_sources,
        )

        # 2. Input Data Taxonomy (G-02)
        input_taxonomy = self.classify_input_data(input_types)

        # 3. Data Source Validation (G-03)
        source_validation = self.validate_data_sources(data_sources)

        # 4. Output Classification (G-05)
        output_classification = self.classify_output_type(output_type)

        # 5. Transparency Report (G-08)
        transparency = self.generate_transparency_report(
            function_description=function_description,
            inputs_used=input_types,
            data_sources=data_sources,
            algorithm_description=algorithm_description,
            known_limitations=known_limitations,
        )

        # 6. Automation Bias Warning (G-12)
        bias_warning = self.generate_bias_warning_label(
            function_description=function_description,
            intended_user=intended_user,
        )

        # 7. CDS Labeling (G-18)
        labeling = self.generate_cds_labeling(
            product_name=product_name,
            intended_use=function_description,
            intended_users=[intended_user],
            target_population=target_population,
            algorithm_summary=algorithm_description,
            data_sources=data_sources,
            validation_summary=validation_summary,
            known_limitations=known_limitations,
        )

        # 8. Clinical Limitations (G-10)
        clinical_limitations = self.generate_clinical_limitations(
            validated_populations=[target_population],
            accuracy_metrics={"validation_summary": validation_summary},
            excluded_conditions=[],
            known_failure_modes=known_limitations,
        )

        # 9. Automation Bias Risk (G-09)
        bias_risk = self.assess_automation_bias_risk(
            function_description=function_description,
            urgency=urgency,
            decision_impact="treatment_selection",
        )

        return {
            "product_name": product_name,
            "cds_classification": classification,
            "input_taxonomy": input_taxonomy,
            "data_source_validation": source_validation,
            "output_classification": output_classification,
            "transparency_report": transparency,
            "bias_warning": bias_warning,
            "labeling": labeling,
            "clinical_limitations": clinical_limitations,
            "automation_bias_risk": bias_risk,
            "package_generated_at": datetime.now(timezone.utc).isoformat(),
            "guidance_reference": "FDA CDS Software Guidance, January 2026",
        }


# Singleton
cds_compliance = CDSComplianceFramework()

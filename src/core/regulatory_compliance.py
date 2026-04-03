"""
SAGE[ai] - Multi-Standard Regulatory Compliance Framework
==========================================================
Comprehensive regulatory compliance assessment across global standards.

Covers:
  FDA (US):   Software Validation, CSA, Cybersecurity, AI/ML, CDS, 21 CFR Part 11
  EU:         MDR 2017/745, AI Act, IVDR 2017/746
  International: IEC 62304, ISO 14971, IEC 82304-1, IMDRF SaMD
  Regional:   UK MHRA, Health Canada, Japan PMDA, TGA Australia

Usage:
    from src.core.regulatory_compliance import regulatory_compliance
    result = regulatory_compliance.assess_compliance(product_profile)
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Standards Registry — every standard SAGE can assess against
# ---------------------------------------------------------------------------

STANDARDS_REGISTRY: Dict[str, Dict] = {
    # ---- FDA (US) ----
    "fda_swv": {
        "id": "fda_swv",
        "name": "General Principles of Software Validation",
        "region": "us",
        "category": "software_lifecycle",
        "reference": "FDA Guidance, 2002 (still in effect)",
        "requirements": [
            "Software development lifecycle defined and documented",
            "Validation planning with defined scope and approach",
            "Requirements traceability to tests and design",
            "Structural testing (unit, integration, system)",
            "Risk-based testing approach",
            "Defect tracking and resolution",
            "Configuration management",
            "Change control procedures",
            "Validation report with summary of results",
        ],
        "required_artifacts": [
            "software_development_plan",
            "software_requirements_spec",
            "software_design_spec",
            "validation_plan",
            "validation_report",
            "traceability_matrix",
            "test_protocols",
            "test_reports",
            "defect_log",
            "configuration_management_plan",
        ],
    },
    "fda_csa": {
        "id": "fda_csa",
        "name": "Computer Software Assurance (CSA)",
        "region": "us",
        "category": "quality_system",
        "reference": "FDA Guidance, September 2022",
        "requirements": [
            "Risk-based testing (replace legacy CSV with assurance)",
            "Critical thinking over scripted testing",
            "Unscripted testing for exploratory validation",
            "Risk assessment to determine testing rigor",
            "Intended use documentation",
            "Record retention per 21 CFR 820",
        ],
        "required_artifacts": [
            "risk_assessment",
            "assurance_plan",
            "test_records",
            "intended_use_doc",
        ],
    },
    "fda_cybersecurity": {
        "id": "fda_cybersecurity",
        "name": "Cybersecurity in Medical Devices",
        "region": "us",
        "category": "security",
        "reference": "FDA Premarket Guidance, September 2023",
        "requirements": [
            "Threat modeling (STRIDE or equivalent)",
            "Software Bill of Materials (SBOM)",
            "Security risk assessment",
            "Vulnerability management plan",
            "Patch management and update capability",
            "Authentication and access control",
            "Data encryption (at rest and in transit)",
            "Security testing (penetration testing, fuzzing)",
            "Incident response plan",
            "Post-market cybersecurity monitoring",
        ],
        "required_artifacts": [
            "threat_model",
            "sbom",
            "security_risk_assessment",
            "vulnerability_management_plan",
            "penetration_test_report",
            "incident_response_plan",
        ],
    },
    "fda_aiml": {
        "id": "fda_aiml",
        "name": "AI/ML-Enabled Device Software Guidance",
        "region": "us",
        "category": "ai_ml",
        "reference": "FDA Marketing Submission Recommendations for AI/ML",
        "requirements": [
            "Description of ML model (architecture, training approach)",
            "Training data description (source, size, demographics)",
            "Performance evaluation (sensitivity, specificity, AUC)",
            "Bias evaluation across demographic subgroups",
            "Predetermined change control plan (PCCP)",
            "Real-world performance monitoring plan",
            "Human factors / usability evaluation",
            "Transparency about model limitations",
            "Algorithm lock or update strategy",
        ],
        "required_artifacts": [
            "model_description",
            "training_data_description",
            "performance_evaluation_report",
            "bias_evaluation_report",
            "predetermined_change_control_plan",
            "monitoring_plan",
            "human_factors_report",
        ],
    },
    "fda_cds": {
        "id": "fda_cds",
        "name": "Clinical Decision Support Software",
        "region": "us",
        "category": "classification",
        "reference": "FDA CDS Guidance, January 2026 (media/109618)",
        "requirements": [
            "4-criterion CDS classification (image, info, HCP, review)",
            "Input data type classification",
            "Data source provenance validation",
            "Output type classification",
            "Transparency and explainability",
            "Automation bias mitigation",
            "CDS-specific labeling",
        ],
        "required_artifacts": [
            "cds_classification_report",
            "transparency_report",
            "cds_labeling",
            "bias_warning_labels",
        ],
    },
    "fda_21cfr11": {
        "id": "fda_21cfr11",
        "name": "21 CFR Part 11 — Electronic Records and Signatures",
        "region": "us",
        "category": "electronic_records",
        "reference": "21 CFR Part 11",
        "requirements": [
            "Secure audit trail (immutable, timestamped)",
            "Electronic signature capability",
            "User authentication and access control",
            "System validation documentation",
            "Record retention and retrieval",
            "Authority checks for signature",
        ],
        "required_artifacts": [
            "audit_trail",
            "electronic_signature_system",
            "system_validation_doc",
            "access_control_policy",
        ],
    },

    # ---- EU ----
    "eu_mdr": {
        "id": "eu_mdr",
        "name": "EU Medical Device Regulation 2017/745",
        "region": "eu",
        "category": "device_regulation",
        "reference": "Regulation (EU) 2017/745",
        "requirements": [
            "CE marking conformity assessment",
            "Technical documentation (Annex II/III)",
            "Quality management system (Annex IX)",
            "Clinical evaluation per Annex XIV",
            "Post-market surveillance plan",
            "Unique Device Identification (UDI)",
            "Notified Body assessment (Class IIa and above)",
            "EU Declaration of Conformity",
            "Person Responsible for Regulatory Compliance (PRRC)",
            "EUDAMED registration",
        ],
        "required_artifacts": [
            "technical_documentation",
            "clinical_evaluation_report",
            "quality_management_system",
            "post_market_surveillance_plan",
            "declaration_of_conformity",
            "udi_registration",
            "risk_management_file",
        ],
    },
    "eu_ai_act": {
        "id": "eu_ai_act",
        "name": "EU Artificial Intelligence Act",
        "region": "eu",
        "category": "ai_regulation",
        "reference": "Regulation (EU) 2024/1689",
        "requirements": [
            "Risk classification (unacceptable/high/limited/minimal)",
            "Conformity assessment for high-risk AI",
            "Risk management system (continuous)",
            "Data governance (training data quality, representativeness)",
            "Technical documentation (Annex IV)",
            "Record-keeping and logging",
            "Transparency and information to deployers",
            "Human oversight measures",
            "Accuracy, robustness, cybersecurity",
            "Post-market monitoring system",
            "Registration in EU database",
        ],
        "required_artifacts": [
            "ai_risk_classification",
            "conformity_assessment",
            "risk_management_system",
            "data_governance_plan",
            "technical_documentation_annex_iv",
            "logging_system",
            "transparency_report",
            "human_oversight_plan",
        ],
    },
    "eu_ivdr": {
        "id": "eu_ivdr",
        "name": "EU In Vitro Diagnostic Regulation 2017/746",
        "region": "eu",
        "category": "ivd_regulation",
        "reference": "Regulation (EU) 2017/746",
        "requirements": [
            "IVD classification (Class A-D)",
            "Performance evaluation and clinical evidence",
            "Technical documentation per Annex II/III",
            "Quality management system",
            "Post-market performance follow-up (PMPF)",
            "CE marking and UDI",
        ],
        "required_artifacts": [
            "performance_evaluation_report",
            "clinical_evidence",
            "technical_documentation",
            "pmpf_plan",
        ],
    },

    # ---- International ----
    "iec_62304": {
        "id": "iec_62304",
        "name": "IEC 62304:2006/AMD1:2015 — Medical Device Software Lifecycle",
        "region": "international",
        "category": "software_lifecycle",
        "reference": "IEC 62304:2006+AMD1:2015",
        "requirements": [
            "Software development planning (5.1)",
            "Software requirements analysis (5.2)",
            "Software architectural design (5.3)",
            "Software detailed design (5.4)",
            "Software unit implementation (5.5)",
            "Software integration and integration testing (5.6)",
            "Software system testing (5.7)",
            "Software release (5.8)",
            "Software safety classification (A, B, C)",
            "Software maintenance plan (6.1)",
            "Software problem resolution (9.1)",
            "Software configuration management (8.1)",
            "SOUP management (7.1)",
        ],
        "required_artifacts": [
            "software_development_plan",
            "software_requirements_spec",
            "software_architecture_doc",
            "software_detailed_design",
            "unit_test_reports",
            "integration_test_reports",
            "system_test_reports",
            "software_release_doc",
            "safety_classification",
            "maintenance_plan",
            "soup_inventory",
            "configuration_management_plan",
        ],
    },
    "iso_14971": {
        "id": "iso_14971",
        "name": "ISO 14971:2019 — Risk Management for Medical Devices",
        "region": "international",
        "category": "risk_management",
        "reference": "ISO 14971:2019",
        "requirements": [
            "Risk management plan",
            "Hazard identification",
            "Risk analysis (severity, probability, detectability)",
            "Risk evaluation against acceptability criteria",
            "Risk control measures",
            "Residual risk evaluation",
            "Risk-benefit analysis",
            "Risk management report",
            "Production and post-production information",
        ],
        "required_artifacts": [
            "risk_management_plan",
            "risk_management_file",
            "hazard_analysis",
            "risk_control_measures",
            "residual_risk_evaluation",
            "risk_management_report",
        ],
    },
    "iec_82304": {
        "id": "iec_82304",
        "name": "IEC 82304-1:2016 — Health Software Product Safety",
        "region": "international",
        "category": "health_software",
        "reference": "IEC 82304-1:2016",
        "requirements": [
            "Health software product safety requirements",
            "Risk management per ISO 14971",
            "Software lifecycle per IEC 62304",
            "Usability engineering per IEC 62366",
            "Labeling and accompanying documents",
            "Post-market surveillance",
        ],
        "required_artifacts": [
            "product_safety_report",
            "risk_management_file",
            "usability_engineering_file",
            "labeling",
            "post_market_surveillance_plan",
        ],
    },
    "imdrf_samd": {
        "id": "imdrf_samd",
        "name": "IMDRF SaMD Framework — Global Classification",
        "region": "international",
        "category": "classification",
        "reference": "IMDRF/SaMD WG/N12/N41 FINAL:2013",
        "requirements": [
            "SaMD definition confirmation",
            "Risk categorization (I, II, III, IV)",
            "Clinical evaluation following IMDRF N12",
            "Quality management system",
            "SaMD clinical evaluation methodology",
        ],
        "required_artifacts": [
            "samd_definition_statement",
            "risk_categorization",
            "clinical_evaluation",
        ],
    },

    # ---- Regional ----
    "uk_mhra": {
        "id": "uk_mhra",
        "name": "UK MHRA — Software and AI as Medical Device",
        "region": "uk",
        "category": "device_regulation",
        "reference": "MHRA Software and AI Guidance, 2023+",
        "requirements": [
            "UKCA marking (or CE marking during transition)",
            "UK Responsible Person appointment",
            "Registration with MHRA",
            "Technical documentation per UK MDR 2002",
            "Clinical evidence appropriate to risk class",
            "Post-market surveillance",
            "Software as Medical Device classification",
        ],
        "required_artifacts": [
            "ukca_declaration",
            "technical_documentation",
            "clinical_evidence",
            "post_market_surveillance_plan",
            "mhra_registration",
        ],
    },
    "canada_hc": {
        "id": "canada_hc",
        "name": "Health Canada — SaMD Guidance",
        "region": "canada",
        "category": "device_regulation",
        "reference": "Health Canada Pre-market Guidance for SaMD, 2023",
        "requirements": [
            "Medical device classification (Class I-IV)",
            "Medical Device Licence (MDL) application",
            "Quality management system (ISO 13485)",
            "Safety and effectiveness evidence",
            "Cybersecurity requirements",
            "Post-market requirements",
        ],
        "required_artifacts": [
            "device_licence_application",
            "quality_management_system",
            "safety_effectiveness_evidence",
            "cybersecurity_assessment",
        ],
    },
    "japan_pmda": {
        "id": "japan_pmda",
        "name": "Japan PMDA — SaMD Regulatory Framework",
        "region": "japan",
        "category": "device_regulation",
        "reference": "PMDA SaMD Guidance, 2023+",
        "requirements": [
            "SaMD classification per Japanese regulations",
            "Marketing authorization application",
            "Clinical validation appropriate to class",
            "Quality management system (JIS Q 13485)",
            "Japanese language labeling",
            "Post-market safety management",
            "PMDA consultation (pre-submission)",
        ],
        "required_artifacts": [
            "marketing_authorization_app",
            "clinical_validation_report",
            "qms_certificate",
            "japanese_labeling",
        ],
    },
    "aus_tga": {
        "id": "aus_tga",
        "name": "TGA Australia — Software-Based Medical Devices",
        "region": "australia",
        "category": "device_regulation",
        "reference": "TGA Regulation of Software-Based Medical Devices, 2021+",
        "requirements": [
            "ARTG inclusion (Australian Register of Therapeutic Goods)",
            "Device classification per TGA rules",
            "Conformity assessment (aligned with IMDRF)",
            "Australian Sponsor appointment",
            "Essential Principles compliance",
            "Post-market vigilance",
        ],
        "required_artifacts": [
            "artg_application",
            "conformity_assessment",
            "essential_principles_checklist",
            "sponsor_declaration",
        ],
    },
    # ---- Safety-Critical Industry Standards ----
    "en_50128": {
        "id": "en_50128",
        "name": "EN 50128 — Railway Software (CENELEC)",
        "region": "international",
        "category": "railway_safety",
        "reference": "EN 50128:2011+A1:2020",
        "requirements": [
            "Software safety integrity level (SIL 0-4) determination",
            "Software lifecycle per CENELEC requirements",
            "Defensive programming techniques for SIL 3/4",
            "Formal methods for SIL 4 (recommended SIL 3)",
            "Independent safety assessment",
            "Configuration management",
            "Software verification and validation",
            "Coding standards compliance",
        ],
        "required_artifacts": [
            "software_safety_integrity_level",
            "software_development_plan",
            "software_requirements_spec",
            "software_architecture",
            "verification_report",
            "validation_report",
            "safety_case",
        ],
    },
    "iec_61508": {
        "id": "iec_61508",
        "name": "IEC 61508 — Functional Safety of E/E/PE Systems",
        "region": "international",
        "category": "functional_safety",
        "reference": "IEC 61508:2010 (Parts 1-7)",
        "requirements": [
            "Safety lifecycle management",
            "SIL determination (SIL 1-4)",
            "Hardware safety integrity (random failures)",
            "Systematic safety integrity (design faults)",
            "Software safety requirements",
            "Verification and validation",
            "Functional safety assessment",
            "Competence management",
        ],
        "required_artifacts": [
            "safety_plan",
            "sil_determination",
            "safety_requirements_spec",
            "safety_validation_report",
            "functional_safety_assessment",
        ],
    },
    "iec_61511": {
        "id": "iec_61511",
        "name": "IEC 61511 — Process Industry Functional Safety",
        "region": "international",
        "category": "process_safety",
        "reference": "IEC 61511:2016 (Parts 1-3)",
        "requirements": [
            "Safety Instrumented System (SIS) lifecycle",
            "SIL determination via LOPA or risk graph",
            "Safety Instrumented Function (SIF) design",
            "Proof test interval definition",
            "SIS verification and validation",
            "Management of functional safety",
            "Competency requirements",
        ],
        "required_artifacts": [
            "safety_requirement_specification",
            "sil_determination_report",
            "sif_design_doc",
            "proof_test_procedures",
            "safety_validation_report",
        ],
    },
    "do_178c": {
        "id": "do_178c",
        "name": "DO-178C — Airborne Software",
        "region": "international",
        "category": "avionics_safety",
        "reference": "RTCA DO-178C / EUROCAE ED-12C",
        "requirements": [
            "Design Assurance Level (DAL A-E) assignment",
            "Software planning (PSAC, SDP, SVP, SCMP, SQAP)",
            "Software development (requirements, design, code, integration)",
            "Software verification (reviews, analyses, testing)",
            "Structural coverage analysis (statement, decision, MC/DC for DAL A)",
            "Configuration management",
            "Quality assurance",
            "Certification liaison",
        ],
        "required_artifacts": [
            "psac",
            "software_development_plan",
            "software_verification_plan",
            "software_requirements",
            "software_design",
            "source_code",
            "verification_results",
            "configuration_index",
            "software_accomplishment_summary",
        ],
    },
    "ecss_e_st_40c": {
        "id": "ecss_e_st_40c",
        "name": "ECSS-E-ST-40C — Space Software Engineering",
        "region": "international",
        "category": "space_safety",
        "reference": "ECSS-E-ST-40C Rev.1 (2009)",
        "requirements": [
            "Software criticality category assignment",
            "Software engineering lifecycle",
            "Requirements engineering",
            "Architectural and detailed design",
            "Implementation and unit testing",
            "Integration and validation",
            "Delivery and acceptance",
            "Maintenance and disposal",
        ],
        "required_artifacts": [
            "software_requirements_doc",
            "software_design_doc",
            "software_validation_spec",
            "software_user_manual",
            "software_maintenance_plan",
        ],
    },
    "mil_std_882e": {
        "id": "mil_std_882e",
        "name": "MIL-STD-882E — System Safety",
        "region": "us",
        "category": "defense_safety",
        "reference": "MIL-STD-882E (2012)",
        "requirements": [
            "System safety program plan",
            "Preliminary hazard analysis",
            "Subsystem/system hazard analysis",
            "Operating and support hazard analysis",
            "Health hazard assessment",
            "Safety assessment report",
            "Mishap risk assessment",
            "Software safety criticality analysis",
        ],
        "required_artifacts": [
            "system_safety_program_plan",
            "preliminary_hazard_list",
            "hazard_analysis",
            "safety_assessment_report",
            "hazard_tracking_system",
        ],
    },
    "iso_13849": {
        "id": "iso_13849",
        "name": "ISO 13849 — Machinery Safety (Control Systems)",
        "region": "international",
        "category": "machinery_safety",
        "reference": "ISO 13849-1:2023",
        "requirements": [
            "Performance Level (PL) determination (a-e)",
            "Category determination (B, 1, 2, 3, 4)",
            "Safety function identification",
            "Validation of safety-related control systems",
            "Diagnostic coverage assessment",
            "Common cause failure analysis",
            "Software requirements for safety-related functions",
        ],
        "required_artifacts": [
            "performance_level_determination",
            "safety_function_spec",
            "validation_plan",
            "validation_report",
        ],
    },
}

# Region mapping for auto-detection
REGION_TO_STANDARDS = {
    "us": ["fda_swv", "fda_csa", "fda_cybersecurity", "fda_cds", "fda_21cfr11"],
    "eu": ["eu_mdr", "eu_ai_act", "eu_ivdr"],
    "uk": ["uk_mhra"],
    "canada": ["canada_hc"],
    "japan": ["japan_pmda"],
    "australia": ["aus_tga"],
    "international": ["iec_62304", "iso_14971", "iec_82304", "imdrf_samd", "iec_61508"],
}

AI_ML_STANDARDS = ["fda_aiml", "eu_ai_act"]

# Domain-specific standards auto-added based on product keywords
DOMAIN_SAFETY_STANDARDS = {
    "railway": ["en_50128", "iec_61508"],
    "nuclear": ["iec_61508"],
    "industrial_safety": ["iec_61511", "iec_61508"],
    "avionics": ["do_178c"],
    "space": ["ecss_e_st_40c", "do_178c"],
    "defense": ["mil_std_882e", "do_178c"],
    "machinery": ["iso_13849", "iec_61508"],
    "automotive": [],  # ISO 26262 already in international
    "marine": ["iec_61508"],
}


class RegulatoryComplianceFramework:
    """
    Multi-standard regulatory compliance assessment framework.

    Assesses products against global regulatory standards, identifies gaps,
    and generates compliance roadmaps.
    """

    def __init__(self):
        self.logger = logging.getLogger("RegulatoryCompliance")
        self._registry = STANDARDS_REGISTRY

    # ------------------------------------------------------------------
    # Registry
    # ------------------------------------------------------------------

    def list_standards(self) -> List[Dict]:
        """Return all registered regulatory standards."""
        return list(self._registry.values())

    def get_standard(self, standard_id: str) -> Optional[Dict]:
        """Get a single standard by ID."""
        return self._registry.get(standard_id)

    # ------------------------------------------------------------------
    # Auto-detect applicable standards
    # ------------------------------------------------------------------

    def _detect_applicable_standards(self, product: Dict) -> List[str]:
        """Determine which standards apply based on product profile."""
        applicable = set()

        # International standards always apply for medical software
        applicable.update(REGION_TO_STANDARDS["international"])

        # Region-specific standards
        for region in product.get("target_regions", []):
            region_lower = region.lower()
            if region_lower in REGION_TO_STANDARDS:
                applicable.update(REGION_TO_STANDARDS[region_lower])

        # AI/ML-specific standards
        if product.get("uses_ai_ml", False):
            applicable.update(AI_ML_STANDARDS)

        # Domain-specific safety standards (detected from product keywords or explicit domain)
        product_domain = product.get("domain") or ""
        product_desc = " ".join(filter(None, [
            product.get("intended_use"),
            product.get("product_name"),
            product.get("description"),
        ])).lower()

        for domain, standards in DOMAIN_SAFETY_STANDARDS.items():
            if domain in product_domain or domain in product_desc:
                applicable.update(standards)

        # Keyword-based domain detection for safety-critical industries
        keyword_to_standards = {
            "locomotive": ["en_50128", "iec_61508"],
            "railway": ["en_50128", "iec_61508"],
            "train": ["en_50128", "iec_61508"],
            "signalling": ["en_50128", "iec_61508"],
            "nuclear": ["iec_61508"],
            "reactor": ["iec_61508"],
            "process safety": ["iec_61511", "iec_61508"],
            "safety instrumented": ["iec_61511", "iec_61508"],
            "drone": ["do_178c"],
            "aircraft": ["do_178c"],
            "satellite": ["ecss_e_st_40c"],
            "spacecraft": ["ecss_e_st_40c"],
            "defense": ["mil_std_882e"],
            "military": ["mil_std_882e"],
            "weapon": ["mil_std_882e"],
            "machinery": ["iso_13849"],
            "crane": ["iso_13849"],
            "excavator": ["iso_13849"],
            "elevator": ["iec_61508"],
            "lift": ["iec_61508"],
        }
        for keyword, standards in keyword_to_standards.items():
            if keyword in product_desc:
                applicable.update(standards)

        return sorted(applicable)

    # ------------------------------------------------------------------
    # Compliance Assessment
    # ------------------------------------------------------------------

    def assess_compliance(
        self,
        product: Dict,
        standard_ids: Optional[List[str]] = None,
    ) -> Dict:
        """
        Assess product compliance against specified or auto-detected standards.

        Args:
            product: Product profile dict
            standard_ids: Specific standards to assess (None = auto-detect)

        Returns:
            Dict with per-standard assessments and overall score.
        """
        if standard_ids is None:
            standard_ids = self._detect_applicable_standards(product)

        assessments = {}
        for std_id in standard_ids:
            std = self._registry.get(std_id)
            if not std:
                continue
            assessments[std_id] = self._assess_single_standard(product, std)

        scores = [a["compliance_score"] for a in assessments.values()]
        overall = sum(scores) / max(len(scores), 1)

        return {
            "product_name": product.get("product_name", "Unknown"),
            "assessments": assessments,
            "overall_score": round(overall, 1),
            "standards_assessed": len(assessments),
            "assessed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _assess_single_standard(self, product: Dict, standard: Dict) -> Dict:
        """Assess product against a single standard."""
        existing = set(product.get("existing_artifacts", []))
        required = set(standard["required_artifacts"])

        met_artifacts = existing & required
        missing_artifacts = required - existing

        # Score: % of requirements covered based on artifact presence
        artifact_score = len(met_artifacts) / max(len(required), 1) * 100

        # Check specific requirement conditions
        met_reqs = []
        gaps = []
        for req in standard["requirements"]:
            # Simple heuristic: if related artifact exists, requirement is partially met
            req_lower = req.lower()
            is_met = False

            # Map requirements to artifacts
            if "traceability" in req_lower and "traceability_matrix" in existing:
                is_met = True
            elif "risk" in req_lower and ("risk_management_file" in existing or "risk_assessment" in existing):
                is_met = True
            elif "requirement" in req_lower and "software_requirements_spec" in existing:
                is_met = True
            elif "architecture" in req_lower and "software_architecture_doc" in existing:
                is_met = True
            elif "validation" in req_lower and ("validation_plan" in existing or "validation_report" in existing):
                is_met = True
            elif "verification" in req_lower and "verification_plan" in existing:
                is_met = True
            elif "audit" in req_lower and "audit_trail" in existing:
                is_met = True
            elif "test" in req_lower and any("test" in a for a in existing):
                is_met = True
            elif "soup" in req_lower and "soup_inventory" in existing:
                is_met = True
            elif "configuration" in req_lower and "configuration_management_plan" in existing:
                is_met = True
            elif "safety" in req_lower and "safety_classification" in existing:
                is_met = True

            if is_met:
                met_reqs.append(req)
            else:
                gaps.append(req)

        req_score = len(met_reqs) / max(len(standard["requirements"]), 1) * 100
        compliance_score = round((artifact_score * 0.6 + req_score * 0.4), 1)

        return {
            "standard_id": standard["id"],
            "standard_name": standard["name"],
            "region": standard["region"],
            "compliance_score": compliance_score,
            "met_requirements": met_reqs,
            "gaps": gaps,
            "required_artifacts": list(required),
            "met_artifacts": list(met_artifacts),
            "missing_artifacts": list(missing_artifacts),
        }

    # ------------------------------------------------------------------
    # Gap Analysis
    # ------------------------------------------------------------------

    def generate_gap_analysis(self, product: Dict, standard_id: str) -> Dict:
        """Generate detailed gap analysis for a specific standard."""
        std = self._registry.get(standard_id)
        if not std:
            return {"error": f"Standard {standard_id} not found"}

        existing = set(product.get("existing_artifacts", []))
        gaps = []

        for req in std["requirements"]:
            req_lower = req.lower()
            has_evidence = any(
                keyword in a for a in existing
                for keyword in req_lower.split()[:3]
            )

            if has_evidence:
                status = "met"
                remediation = "Evidence artifact exists. Verify completeness."
            elif any(partial in existing for partial in ["software_requirements_spec", "audit_trail"]):
                status = "partial"
                remediation = f"Partial evidence exists. Complete: {req}"
            else:
                status = "missing"
                remediation = f"Create documentation for: {req}"

            gaps.append({
                "requirement": req,
                "status": status,
                "remediation": remediation,
                "priority": "high" if "safety" in req_lower or "risk" in req_lower else "medium",
            })

        return {
            "standard_id": standard_id,
            "standard_name": std["name"],
            "gaps": gaps,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Checklist Generation
    # ------------------------------------------------------------------

    def generate_checklist(self, standard_id: str) -> Dict:
        """Generate compliance checklist for a standard."""
        std = self._registry.get(standard_id)
        if not std:
            return {"error": f"Standard {standard_id} not found"}

        items = []
        for i, req in enumerate(std["requirements"]):
            related_artifacts = [
                a for a in std["required_artifacts"]
                if any(word in a for word in req.lower().split()[:3])
            ]
            items.append({
                "id": f"{standard_id}-{i+1:03d}",
                "requirement": req,
                "description": f"Verify compliance with: {req}",
                "evidence_needed": related_artifacts or [f"Documentation for: {req}"],
                "checked": False,
            })

        return {
            "standard_id": standard_id,
            "standard_name": std["name"],
            "items": items,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Submission Roadmap
    # ------------------------------------------------------------------

    def generate_submission_roadmap(self, product: Dict) -> Dict:
        """Generate phased regulatory submission roadmap."""
        applicable = self._detect_applicable_standards(product)

        phases = [
            {
                "phase_name": "Phase 1: Foundation",
                "description": "Core lifecycle and risk management",
                "standards": [s for s in applicable if s in ("iec_62304", "iso_14971", "iec_82304")],
                "deliverables": [
                    "Software Development Plan",
                    "Risk Management Plan and File",
                    "Software Requirements Specification",
                    "Software Architecture Document",
                ],
                "estimated_weeks": 4,
            },
            {
                "phase_name": "Phase 2: Quality & Security",
                "description": "Quality system and cybersecurity",
                "standards": [s for s in applicable if s in ("fda_swv", "fda_csa", "fda_cybersecurity", "fda_21cfr11")],
                "deliverables": [
                    "Validation Plan and Reports",
                    "Threat Model and SBOM",
                    "Audit Trail System",
                    "Electronic Signature System",
                ],
                "estimated_weeks": 4,
            },
            {
                "phase_name": "Phase 3: Classification & Compliance",
                "description": "Regulatory classification and region-specific compliance",
                "standards": [s for s in applicable if s in ("fda_cds", "imdrf_samd", "eu_mdr", "eu_ai_act", "uk_mhra", "canada_hc", "japan_pmda", "aus_tga")],
                "deliverables": [
                    "CDS Classification Report",
                    "Technical Documentation",
                    "Clinical Evaluation Report",
                    "Declaration of Conformity",
                ],
                "estimated_weeks": 6,
            },
            {
                "phase_name": "Phase 4: Submission & Post-Market",
                "description": "Regulatory submissions and post-market setup",
                "standards": applicable,
                "deliverables": [
                    "Regulatory Submission Package(s)",
                    "Post-Market Surveillance Plan",
                    "Post-Market Clinical Follow-Up",
                    "Vigilance and Reporting Procedures",
                ],
                "estimated_weeks": 4,
            },
        ]

        # Filter out phases with no applicable standards
        phases = [p for p in phases if p["standards"]]

        return {
            "product_name": product.get("product_name", "Unknown"),
            "target_regions": product.get("target_regions", []),
            "phases": phases,
            "total_estimated_weeks": sum(p["estimated_weeks"] for p in phases),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Full Compliance Report
    # ------------------------------------------------------------------

    def generate_full_compliance_report(self, product: Dict) -> Dict:
        """Generate comprehensive multi-standard compliance report."""
        assessment = self.assess_compliance(product)
        roadmap = self.generate_submission_roadmap(product)

        return {
            "product_name": product.get("product_name", "Unknown"),
            "assessments": assessment["assessments"],
            "overall_score": assessment["overall_score"],
            "standards_assessed": assessment["standards_assessed"],
            "roadmap": roadmap,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# Singleton
regulatory_compliance = RegulatoryComplianceFramework()

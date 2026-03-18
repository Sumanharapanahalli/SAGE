"""
SAGE Compliance Flags — Regulatory Requirement Registry
========================================================
Maps industry standards to:
  - Required task types (what agents must check)
  - Test evidence flags (what HIL tests must produce)
  - Documentation requirements (what artifacts are mandatory)
  - Risk levels (criticality per IEC 62304 / DO-178C / EN 50128)

Source standards:
  MedTech:    IEC 62304:2015+A1, ISO 14971:2019, FDA 21 CFR 820, IEC 60601-1, IEC 62443
  Automotive: ISO 26262:2018, ISO/SAE 21434:2021, UN ECE WP.29 R155/R156
  Railways:   EN 50128:2011+A2, EN 50129:2018, EN 50126-1:2017
  Avionics:   DO-178C:2011, DO-254:2000, ARP4754A:2010
  IoT/ICS:    IEC 62443-2-4, IEC 62443-3-3, ETSI EN 303 645

Usage:
  from src.core.compliance_flags import (
      COMPLIANCE_FLAGS,
      get_required_flags,
      get_hil_required_tests,
      generate_compliance_checklist,
      list_domains,
  )
"""

from typing import Optional

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

COMPLIANCE_FLAGS: dict = {

    # ==========================================================================
    # MEDTECH — IEC 62304, ISO 14971, FDA 21 CFR 820, IEC 60601-1, IEC 62443
    # ==========================================================================
    "medtech": {
        "standard":     "IEC 62304:2015+A1 + ISO 14971:2019 + FDA 21 CFR 820",
        "description":  "Medical device software — covers embedded firmware, cloud backend, mobile apps",
        "authority":    "FDA (US), EMA/Notified Bodies (EU MDR), Health Canada, PMDA (Japan)",
        "risk_levels":  ["CLASS_A", "CLASS_B", "CLASS_C"],

        "software_class": {
            "CLASS_A": "No injury or damage to health possible",
            "CLASS_B": "Non-serious injury possible",
            "CLASS_C": "Death or serious injury possible",
        },

        "required_tasks": {
            "CLASS_A": [
                "ANALYZE_LOG",
                "REVIEW_FIRMWARE_CHANGE",
            ],
            "CLASS_B": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "SYSTEM_TEST",
                "HAZARD_ANALYSIS",
                "RISK_MITIGATION",
                "REVIEW_FIRMWARE_CHANGE",
                "ANALYZE_DEVICE_LOG",
                "GENERATE_TEST_PROTOCOL",
                "REVIEW_TEST_RESULTS",
                "UPDATE_DHF",
            ],
            "CLASS_C": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "SYSTEM_TEST",
                "HAZARD_ANALYSIS",
                "RISK_MITIGATION",
                "HIL_TEST_FIRMWARE",
                "PENETRATION_TEST",
                "TRACEABILITY_MATRIX",
                "REVIEW_FIRMWARE_CHANGE",
                "ANALYZE_DEVICE_LOG",
                "GENERATE_HAZARD_ANALYSIS",
                "UPDATE_RISK_REGISTER",
                "GENERATE_CAPA",
                "GENERATE_TEST_PROTOCOL",
                "REVIEW_TEST_RESULTS",
                "UPDATE_DHF",
                "CYBERSECURITY_ASSESSMENT",
                "GENERATE_SBOM",
            ],
        },

        "hil_required_for": ["CLASS_B", "CLASS_C"],

        "evidence_artifacts": [
            "Software Development Plan (IEC 62304 §5.1)",
            "Software Requirements Specification (IEC 62304 §5.2)",
            "Software Architecture Design (IEC 62304 §5.3)",
            "Software Detailed Design (IEC 62304 §5.4)",
            "Unit Test Protocol + Results (IEC 62304 §5.5)",
            "Integration Test Protocol + Results (IEC 62304 §5.6)",
            "System Test Protocol + Results (IEC 62304 §5.7)",
            "Software Release (IEC 62304 §5.8)",
            "Problem Resolution Record (IEC 62304 §9)",
            "Risk Management Plan (ISO 14971 §4.4)",
            "Risk Management File (ISO 14971 §6)",
            "Hazard Analysis (ISO 14971 §5)",
            "Risk Control Measures (ISO 14971 §6.2)",
            "Risk Control Verification (ISO 14971 §6.5)",
            "Post-Market Surveillance Plan (ISO 14971 §9 + EU MDR Art.83)",
            "Cybersecurity Risk Assessment (FDA 2023 Cybersecurity Guidance)",
            "Software Bill of Materials (FDA SBOM requirement 2023)",
            "Design History File / Technical File (21 CFR 820.30 / EU MDR Annex II)",
            "Electrical Safety Test Report (IEC 60601-1)",
            "Electromagnetic Compatibility Report (IEC 60601-1-2)",
            "Usability Engineering File (IEC 62366-1)",
        ],

        "critical_flags": [
            {
                "id":           "IEC62304-5.1",
                "level":        "CRITICAL",
                "description":  "Software development planning required for all classes",
                "clause":       "IEC 62304:2015 §5.1",
                "hil_required": False,
                "applies_to":   ["CLASS_A", "CLASS_B", "CLASS_C"],
            },
            {
                "id":           "IEC62304-5.2",
                "level":        "CRITICAL",
                "description":  "Software requirements must be documented and traceable",
                "clause":       "IEC 62304:2015 §5.2",
                "hil_required": False,
                "applies_to":   ["CLASS_B", "CLASS_C"],
            },
            {
                "id":           "IEC62304-5.5",
                "level":        "CRITICAL",
                "description":  "Unit testing required for Class B/C with documented results",
                "clause":       "IEC 62304:2015 §5.5",
                "hil_required": False,
                "applies_to":   ["CLASS_B", "CLASS_C"],
            },
            {
                "id":           "IEC62304-5.6",
                "level":        "CRITICAL",
                "description":  "Integration testing required with hardware and software components",
                "clause":       "IEC 62304:2015 §5.6",
                "hil_required": True,
                "applies_to":   ["CLASS_B", "CLASS_C"],
            },
            {
                "id":           "IEC62304-5.7",
                "level":        "CRITICAL",
                "description":  "System testing against all software requirements",
                "clause":       "IEC 62304:2015 §5.7",
                "hil_required": True,
                "applies_to":   ["CLASS_B", "CLASS_C"],
            },
            {
                "id":           "ISO14971-5",
                "level":        "CRITICAL",
                "description":  "Hazard identification for all intended uses and foreseeable misuses",
                "clause":       "ISO 14971:2019 §5",
                "hil_required": False,
                "applies_to":   ["CLASS_A", "CLASS_B", "CLASS_C"],
            },
            {
                "id":           "ISO14971-6.2",
                "level":        "CRITICAL",
                "description":  "Risk control measures implemented and verified in hardware+software",
                "clause":       "ISO 14971:2019 §6.2",
                "hil_required": True,
                "applies_to":   ["CLASS_B", "CLASS_C"],
            },
            {
                "id":           "IEC60601-1-ES",
                "level":        "CRITICAL",
                "description":  "Basic electrical safety testing (leakage current, dielectric strength)",
                "clause":       "IEC 60601-1:2005+A1:2012 §8",
                "hil_required": True,
                "applies_to":   ["CLASS_B", "CLASS_C"],
            },
            {
                "id":           "IEC60601-1-EMC",
                "level":        "CRITICAL",
                "description":  "EMC testing per IEC 60601-1-2 — emissions and immunity",
                "clause":       "IEC 60601-1-2:2014+A1:2020",
                "hil_required": True,
                "applies_to":   ["CLASS_B", "CLASS_C"],
            },
            {
                "id":           "FDA-CYBERSEC",
                "level":        "HIGH",
                "description":  "Cybersecurity vulnerability assessment and threat modelling",
                "clause":       "FDA Cybersecurity Guidance Dec 2023",
                "hil_required": False,
                "applies_to":   ["CLASS_B", "CLASS_C"],
            },
            {
                "id":           "FDA-SBOM",
                "level":        "HIGH",
                "description":  "Software Bill of Materials generated and maintained",
                "clause":       "FDA SBOM Requirement 2023",
                "hil_required": False,
                "applies_to":   ["CLASS_B", "CLASS_C"],
            },
            {
                "id":           "21CFR820-70",
                "level":        "HIGH",
                "description":  "Production and process controls including device testing",
                "clause":       "21 CFR 820.70",
                "hil_required": True,
                "applies_to":   ["CLASS_B", "CLASS_C"],
            },
            {
                "id":           "IEC62443-3-3-SR",
                "level":        "HIGH",
                "description":  "Security requirements for networked medical IoT devices",
                "clause":       "IEC 62443-3-3 System Security Requirements",
                "hil_required": False,
                "applies_to":   ["CLASS_B", "CLASS_C"],
            },
            {
                "id":           "IEC62304-8",
                "level":        "HIGH",
                "description":  "Software change control and traceability for all modifications",
                "clause":       "IEC 62304:2015 §8",
                "hil_required": False,
                "applies_to":   ["CLASS_A", "CLASS_B", "CLASS_C"],
            },
            {
                "id":           "MDR-PMCF",
                "level":        "HIGH",
                "description":  "Post-market clinical follow-up plan (EU MDR Article 83)",
                "clause":       "EU MDR 2017/745 Article 83",
                "hil_required": False,
                "applies_to":   ["CLASS_B", "CLASS_C"],
            },
        ],
    },

    # ==========================================================================
    # AUTOMOTIVE — ISO 26262, ISO/SAE 21434, UN ECE WP.29 R155/R156
    # ==========================================================================
    "automotive": {
        "standard":     "ISO 26262:2018 + ISO/SAE 21434:2021 + UN ECE WP.29 R155/R156",
        "description":  "Road vehicle functional safety and cybersecurity — from ASIL A to ASIL D",
        "authority":    "Type approval authorities (KBA Germany, NHTSA US, UNECE WP.29)",
        "risk_levels":  ["QM", "ASIL_A", "ASIL_B", "ASIL_C", "ASIL_D"],

        "asil_levels": {
            "QM":     "Quality Management — no safety requirement",
            "ASIL_A": "Lowest integrity — minor injury possible",
            "ASIL_B": "Low integrity — moderate injury possible",
            "ASIL_C": "Medium integrity — severe injury possible",
            "ASIL_D": "Highest integrity — life-threatening injury possible",
        },

        "required_tasks": {
            "QM": [
                "ANALYZE_LOG",
                "REVIEW_FIRMWARE_CHANGE",
            ],
            "ASIL_A": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "HAZARD_ANALYSIS",
                "REVIEW_FIRMWARE_CHANGE",
            ],
            "ASIL_B": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "SYSTEM_TEST",
                "HAZARD_ANALYSIS",
                "RISK_MITIGATION",
                "HIL_TEST_FIRMWARE",
                "GENERATE_TEST_PROTOCOL",
                "REVIEW_TEST_RESULTS",
            ],
            "ASIL_C": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "SYSTEM_TEST",
                "HAZARD_ANALYSIS",
                "RISK_MITIGATION",
                "HIL_TEST_FIRMWARE",
                "PENETRATION_TEST",
                "TRACEABILITY_MATRIX",
                "GENERATE_TEST_PROTOCOL",
                "REVIEW_TEST_RESULTS",
                "CYBERSECURITY_ASSESSMENT",
            ],
            "ASIL_D": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "SYSTEM_TEST",
                "HAZARD_ANALYSIS",
                "RISK_MITIGATION",
                "HIL_TEST_FIRMWARE",
                "PENETRATION_TEST",
                "TRACEABILITY_MATRIX",
                "FORMAL_VERIFICATION",
                "GENERATE_TEST_PROTOCOL",
                "REVIEW_TEST_RESULTS",
                "CYBERSECURITY_ASSESSMENT",
                "GENERATE_SBOM",
            ],
        },

        "hil_required_for": ["ASIL_B", "ASIL_C", "ASIL_D"],

        "evidence_artifacts": [
            "Safety Plan (ISO 26262-2 §6)",
            "Hazard Analysis and Risk Assessment — HARA (ISO 26262-3 §7)",
            "Functional Safety Concept (ISO 26262-3 §8)",
            "Technical Safety Concept (ISO 26262-4 §7)",
            "System Design Specification (ISO 26262-4 §8)",
            "Hardware Design Specification (ISO 26262-5)",
            "Software Requirements Specification (ISO 26262-6 §7)",
            "Software Architectural Design (ISO 26262-6 §8)",
            "Software Unit Design and Implementation (ISO 26262-6 §9)",
            "Software Unit Testing Report (ISO 26262-6 §9)",
            "Software Integration Testing Report (ISO 26262-6 §10)",
            "Vehicle Integration Testing Report (ISO 26262-6 §11)",
            "Safety Case (ISO 26262-2 §9)",
            "Functional Safety Assessment Report (ISO 26262-2 §13)",
            "Cybersecurity Assessment Report (ISO/SAE 21434 §15)",
            "Threat Analysis and Risk Assessment — TARA (ISO/SAE 21434 §15)",
            "Cybersecurity Plan (ISO/SAE 21434 §14)",
            "Vehicle Type Approval for Cybersecurity (UN ECE R155)",
            "Software Update Management System — SUMS (UN ECE R156)",
        ],

        "critical_flags": [
            {
                "id":           "ISO26262-3-7",
                "level":        "CRITICAL",
                "description":  "HARA: Hazard analysis and risk assessment with ASIL determination",
                "clause":       "ISO 26262-3:2018 §7",
                "hil_required": False,
                "applies_to":   ["ASIL_A", "ASIL_B", "ASIL_C", "ASIL_D"],
            },
            {
                "id":           "ISO26262-6-9",
                "level":        "CRITICAL",
                "description":  "Software unit testing — MC/DC coverage mandatory for ASIL C/D",
                "clause":       "ISO 26262-6:2018 §9",
                "hil_required": False,
                "applies_to":   ["ASIL_A", "ASIL_B", "ASIL_C", "ASIL_D"],
                "note":         "Statement/Branch coverage for ASIL A/B; MC/DC for ASIL C/D",
            },
            {
                "id":           "ISO26262-6-10",
                "level":        "CRITICAL",
                "description":  "Software integration testing with HIL including hardware interactions",
                "clause":       "ISO 26262-6:2018 §10",
                "hil_required": True,
                "applies_to":   ["ASIL_B", "ASIL_C", "ASIL_D"],
            },
            {
                "id":           "ISO26262-4-8",
                "level":        "CRITICAL",
                "description":  "Hardware-software interface testing (HSI)",
                "clause":       "ISO 26262-4:2018 §8",
                "hil_required": True,
                "applies_to":   ["ASIL_B", "ASIL_C", "ASIL_D"],
            },
            {
                "id":           "ISO26262-D-FMEA",
                "level":        "CRITICAL",
                "description":  "DFMEA for ASIL C/D hardware safety analysis",
                "clause":       "ISO 26262-5:2018 §8",
                "hil_required": False,
                "applies_to":   ["ASIL_C", "ASIL_D"],
            },
            {
                "id":           "ISO26262-D-FORMAL",
                "level":        "CRITICAL",
                "description":  "Formal methods for safety-critical path verification (ASIL D highly recommended)",
                "clause":       "ISO 26262-6:2018 Table 10",
                "hil_required": False,
                "applies_to":   ["ASIL_D"],
            },
            {
                "id":           "21434-TARA",
                "level":        "HIGH",
                "description":  "Threat Analysis and Risk Assessment for all vehicle ECUs",
                "clause":       "ISO/SAE 21434:2021 §15",
                "hil_required": False,
                "applies_to":   ["ASIL_A", "ASIL_B", "ASIL_C", "ASIL_D"],
            },
            {
                "id":           "WP29-R155",
                "level":        "HIGH",
                "description":  "Cybersecurity Management System type approval (UN ECE R155)",
                "clause":       "UN ECE WP.29 Regulation 155",
                "hil_required": False,
                "applies_to":   ["ASIL_A", "ASIL_B", "ASIL_C", "ASIL_D"],
            },
            {
                "id":           "WP29-R156",
                "level":        "HIGH",
                "description":  "Software Update Management System type approval (UN ECE R156)",
                "clause":       "UN ECE WP.29 Regulation 156",
                "hil_required": False,
                "applies_to":   ["ASIL_A", "ASIL_B", "ASIL_C", "ASIL_D"],
            },
            {
                "id":           "ISO26262-SAFETY-CASE",
                "level":        "HIGH",
                "description":  "Safety case documenting compliance argumentation",
                "clause":       "ISO 26262-2:2018 §9",
                "hil_required": False,
                "applies_to":   ["ASIL_B", "ASIL_C", "ASIL_D"],
            },
        ],
    },

    # ==========================================================================
    # RAILWAYS — EN 50128, EN 50129, EN 50126
    # ==========================================================================
    "railways": {
        "standard":     "EN 50128:2011+A2:2020 + EN 50129:2018 + EN 50126-1:2017",
        "description":  "Railway signalling and control software — SIL 0 to SIL 4",
        "authority":    "National Safety Authorities (NSAs), ERA (European Union Agency for Railways)",
        "risk_levels":  ["SIL_0", "SIL_1", "SIL_2", "SIL_3", "SIL_4"],

        "sil_levels": {
            "SIL_0": "No safety requirement — maintenance tools only",
            "SIL_1": "Low integrity — on-board comfort systems",
            "SIL_2": "Medium-low integrity — level crossings, yard equipment",
            "SIL_3": "Medium-high integrity — interlocking, ETCS sub-systems",
            "SIL_4": "Highest integrity — ATP, ETCS vital functions",
        },

        "required_tasks": {
            "SIL_0": ["ANALYZE_LOG", "REVIEW_FIRMWARE_CHANGE"],
            "SIL_1": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "HAZARD_ANALYSIS",
                "REVIEW_FIRMWARE_CHANGE",
            ],
            "SIL_2": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "SYSTEM_TEST",
                "HAZARD_ANALYSIS",
                "RISK_MITIGATION",
                "HIL_TEST_FIRMWARE",
                "GENERATE_TEST_PROTOCOL",
                "REVIEW_TEST_RESULTS",
                "TRACEABILITY_MATRIX",
            ],
            "SIL_3": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "SYSTEM_TEST",
                "HAZARD_ANALYSIS",
                "RISK_MITIGATION",
                "HIL_TEST_FIRMWARE",
                "PENETRATION_TEST",
                "TRACEABILITY_MATRIX",
                "FORMAL_VERIFICATION",
                "GENERATE_TEST_PROTOCOL",
                "REVIEW_TEST_RESULTS",
            ],
            "SIL_4": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "SYSTEM_TEST",
                "HAZARD_ANALYSIS",
                "RISK_MITIGATION",
                "HIL_TEST_FIRMWARE",
                "PENETRATION_TEST",
                "TRACEABILITY_MATRIX",
                "FORMAL_VERIFICATION",
                "INDEPENDENT_SAFETY_ASSESSMENT",
                "GENERATE_TEST_PROTOCOL",
                "REVIEW_TEST_RESULTS",
            ],
        },

        "hil_required_for": ["SIL_2", "SIL_3", "SIL_4"],

        "evidence_artifacts": [
            "Software Quality Assurance Plan (EN 50128 §5.2)",
            "Software Requirements Specification (EN 50128 §7.2)",
            "Software Architecture Design (EN 50128 §7.3)",
            "Software Design Specification (EN 50128 §7.4)",
            "Source Code (EN 50128 §7.5)",
            "Test Specification — Component (EN 50128 §8.4)",
            "Test Specification — Integration (EN 50128 §8.5)",
            "Test Specification — Overall System (EN 50128 §8.6)",
            "Test Report (EN 50128 §8.4-8.6)",
            "Validation Plan (EN 50128 §6.3)",
            "Verification and Validation Report (EN 50128 §6.5)",
            "Safety Case (EN 50129 §5)",
            "Preliminary System Safety Analysis (EN 50126 §9)",
            "RAM Analysis (EN 50126 §10)",
            "Independent Safety Assessment Report (EN 50128 §6.2 — SIL 3/4)",
            "Hazard Register (EN 50126 §9)",
            "CENELEC Role Definitions — Assessor, Verifier (EN 50128 §5.1)",
        ],

        "critical_flags": [
            {
                "id":           "EN50128-5.1-ROLES",
                "level":        "CRITICAL",
                "description":  "Mandatory independence between designer, tester, and assessor roles",
                "clause":       "EN 50128:2011 §5.1 Table 4",
                "hil_required": False,
                "applies_to":   ["SIL_2", "SIL_3", "SIL_4"],
            },
            {
                "id":           "EN50128-7.5-LANG",
                "level":        "CRITICAL",
                "description":  "Restricted programming language features (no dynamic allocation, no recursion for SIL 3/4)",
                "clause":       "EN 50128:2011 §7.5 Table 10",
                "hil_required": False,
                "applies_to":   ["SIL_3", "SIL_4"],
            },
            {
                "id":           "EN50128-8.4-COMP",
                "level":        "CRITICAL",
                "description":  "Component testing with documented results and traceability to requirements",
                "clause":       "EN 50128:2011 §8.4",
                "hil_required": False,
                "applies_to":   ["SIL_1", "SIL_2", "SIL_3", "SIL_4"],
            },
            {
                "id":           "EN50128-8.5-INTEG",
                "level":        "CRITICAL",
                "description":  "Integration testing covering HW/SW interfaces",
                "clause":       "EN 50128:2011 §8.5",
                "hil_required": True,
                "applies_to":   ["SIL_2", "SIL_3", "SIL_4"],
            },
            {
                "id":           "EN50128-FORMAL",
                "level":        "CRITICAL",
                "description":  "Formal methods (Highly Recommended for SIL 3, Mandatory for SIL 4)",
                "clause":       "EN 50128:2011 Table 5 — Formal Methods",
                "hil_required": False,
                "applies_to":   ["SIL_3", "SIL_4"],
            },
            {
                "id":           "EN50128-ISA",
                "level":        "CRITICAL",
                "description":  "Independent Safety Assessor review mandatory for SIL 3/4",
                "clause":       "EN 50128:2011 §6.2",
                "hil_required": False,
                "applies_to":   ["SIL_3", "SIL_4"],
            },
            {
                "id":           "EN50128-PROOF",
                "level":        "HIGH",
                "description":  "Software proof of correctness / code review by second party",
                "clause":       "EN 50128:2011 Table 5 — Static Analysis",
                "hil_required": False,
                "applies_to":   ["SIL_2", "SIL_3", "SIL_4"],
            },
            {
                "id":           "EN50129-SAFETY-CASE",
                "level":        "HIGH",
                "description":  "Safety case with complete hazard-to-control traceability",
                "clause":       "EN 50129:2018 §5",
                "hil_required": False,
                "applies_to":   ["SIL_2", "SIL_3", "SIL_4"],
            },
        ],
    },

    # ==========================================================================
    # AVIONICS — DO-178C, DO-254, ARP4754A
    # ==========================================================================
    "avionics": {
        "standard":     "DO-178C:2011 + DO-254:2000 + ARP4754A:2010",
        "description":  "Airborne software and hardware — from DAL E (no effect) to DAL A (catastrophic)",
        "authority":    "FAA (US), EASA (EU), Transport Canada, CAAC (China)",
        "risk_levels":  ["DAL_E", "DAL_D", "DAL_C", "DAL_B", "DAL_A"],

        "dal_levels": {
            "DAL_E": "No effect on aircraft operation",
            "DAL_D": "Minor — slight reduction in safety margins",
            "DAL_C": "Major — significant reduction in safety margins or workload increase",
            "DAL_B": "Hazardous — large reduction in safety margins, serious injuries",
            "DAL_A": "Catastrophic — prevents continued safe flight and landing",
        },

        "required_tasks": {
            "DAL_E": ["ANALYZE_LOG"],
            "DAL_D": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "REVIEW_FIRMWARE_CHANGE",
            ],
            "DAL_C": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "SYSTEM_TEST",
                "HAZARD_ANALYSIS",
                "HIL_TEST_FIRMWARE",
                "GENERATE_TEST_PROTOCOL",
                "REVIEW_TEST_RESULTS",
                "TRACEABILITY_MATRIX",
            ],
            "DAL_B": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "SYSTEM_TEST",
                "HAZARD_ANALYSIS",
                "HIL_TEST_FIRMWARE",
                "PENETRATION_TEST",
                "TRACEABILITY_MATRIX",
                "GENERATE_TEST_PROTOCOL",
                "REVIEW_TEST_RESULTS",
                "INDEPENDENCE_REVIEW",
            ],
            "DAL_A": [
                "UNIT_TEST",
                "INTEGRATION_TEST",
                "SYSTEM_TEST",
                "HAZARD_ANALYSIS",
                "HIL_TEST_FIRMWARE",
                "PENETRATION_TEST",
                "TRACEABILITY_MATRIX",
                "FORMAL_VERIFICATION",
                "INDEPENDENCE_REVIEW",
                "GENERATE_TEST_PROTOCOL",
                "REVIEW_TEST_RESULTS",
                "MULTIPLE_VERSION_DISSIMILAR_SOFTWARE",
            ],
        },

        "hil_required_for": ["DAL_C", "DAL_B", "DAL_A"],

        "evidence_artifacts": [
            "Plan for Software Aspects of Certification — PSAC (DO-178C §11.1)",
            "Software Development Plan — SDP (DO-178C §11.2)",
            "Software Verification Plan — SVP (DO-178C §11.3)",
            "Software Configuration Management Plan — SCMP (DO-178C §11.4)",
            "Software Quality Assurance Plan — SQAP (DO-178C §11.5)",
            "Software Requirements Data — SRD (DO-178C §11.6)",
            "Software Design Description — SDD (DO-178C §11.7)",
            "Source Code (DO-178C §11.8)",
            "Executable Object Code (DO-178C §11.9)",
            "Software Verification Cases and Procedures — SVCP (DO-178C §11.13)",
            "Software Verification Results — SVR (DO-178C §11.14)",
            "Software Life Cycle Environment Configuration Index — SECI (DO-178C §11.15)",
            "Software Configuration Index — SCI (DO-178C §11.16)",
            "Problem Reports (DO-178C §11.17)",
            "Software Accomplishment Summary — SAS (DO-178C §11.20)",
            "Hardware Design Plan (DO-254 §10.1)",
            "Hardware Verification Plan (DO-254 §10.2)",
            "Hardware Accomplishment Summary — HAS (DO-254 §10.8)",
            "System Safety Assessment — SSA (ARP4754A §7.3)",
            "Fault Tree Analysis — FTA (ARP4754A §7.4)",
            "Failure Modes and Effects Analysis — FMEA (ARP4754A §7.4)",
        ],

        "critical_flags": [
            {
                "id":           "DO178C-6.4-REVIEW",
                "level":        "CRITICAL",
                "description":  "Software reviews and analyses — requirements, design, code review",
                "clause":       "DO-178C §6.4",
                "hil_required": False,
                "applies_to":   ["DAL_C", "DAL_B", "DAL_A"],
            },
            {
                "id":           "DO178C-6.4.3-HWSW",
                "level":        "CRITICAL",
                "description":  "Hardware/software integration testing with actual target hardware",
                "clause":       "DO-178C §6.4.3",
                "hil_required": True,
                "applies_to":   ["DAL_C", "DAL_B", "DAL_A"],
            },
            {
                "id":           "DO178C-MC/DC",
                "level":        "CRITICAL",
                "description":  "Modified Condition/Decision Coverage (MC/DC) mandatory for DAL A/B",
                "clause":       "DO-178C §6.4.4.2",
                "hil_required": False,
                "applies_to":   ["DAL_B", "DAL_A"],
                "note":         "DAL_A: MC/DC; DAL_B: MC/DC; DAL_C: Decision coverage; DAL_D: Statement coverage",
            },
            {
                "id":           "DO178C-INDEPENDENCE",
                "level":        "CRITICAL",
                "description":  "Independence required for verification activities at DAL A/B",
                "clause":       "DO-178C §12.1.3",
                "hil_required": False,
                "applies_to":   ["DAL_B", "DAL_A"],
            },
            {
                "id":           "DO178C-TRACEABILITY",
                "level":        "CRITICAL",
                "description":  "Bidirectional traceability: system requirements → SW requirements → design → code → test",
                "clause":       "DO-178C §6.5",
                "hil_required": False,
                "applies_to":   ["DAL_C", "DAL_B", "DAL_A"],
            },
            {
                "id":           "DO178C-FORMAL",
                "level":        "HIGH",
                "description":  "Formal methods as alternative means of compliance for DAL A",
                "clause":       "DO-178C Supplement DO-333",
                "hil_required": False,
                "applies_to":   ["DAL_A"],
            },
            {
                "id":           "DO254-COMPLEX-HW",
                "level":        "HIGH",
                "description":  "Complex hardware (FPGAs, ASICs) requires DO-254 life cycle",
                "clause":       "DO-254 §1.4",
                "hil_required": True,
                "applies_to":   ["DAL_C", "DAL_B", "DAL_A"],
            },
            {
                "id":           "ARP4754A-PSAC",
                "level":        "HIGH",
                "description":  "PSAC approved by certification authority before development start",
                "clause":       "DO-178C §11.1 + ARP4754A §5.6",
                "hil_required": False,
                "applies_to":   ["DAL_C", "DAL_B", "DAL_A"],
            },
        ],
    },

    # ==========================================================================
    # IoT / ICS — IEC 62443, ETSI EN 303 645
    # ==========================================================================
    "iot_ics": {
        "standard":     "IEC 62443-2-4:2015 + IEC 62443-3-3:2013 + ETSI EN 303 645:2020",
        "description":  "Industrial control systems and consumer IoT cybersecurity — SL 1 to SL 4",
        "authority":    "CISA (US), ENISA (EU), BSI (Germany), NCSC (UK)",
        "risk_levels":  ["SL_1", "SL_2", "SL_3", "SL_4"],

        "security_levels": {
            "SL_1": "Protection against casual or coincidental violation — basic hygiene",
            "SL_2": "Protection against intentional violation with simple means — commodity threats",
            "SL_3": "Protection against sophisticated means with IACS-specific skills",
            "SL_4": "Protection against state-sponsored or nation-state level threats",
        },

        "required_tasks": {
            "SL_1": [
                "ANALYZE_LOG",
                "CYBERSECURITY_ASSESSMENT",
                "GENERATE_SBOM",
            ],
            "SL_2": [
                "ANALYZE_LOG",
                "CYBERSECURITY_ASSESSMENT",
                "PENETRATION_TEST",
                "GENERATE_SBOM",
                "REVIEW_FIRMWARE_CHANGE",
            ],
            "SL_3": [
                "ANALYZE_LOG",
                "CYBERSECURITY_ASSESSMENT",
                "PENETRATION_TEST",
                "GENERATE_SBOM",
                "HIL_TEST_FIRMWARE",
                "REVIEW_FIRMWARE_CHANGE",
                "TRACEABILITY_MATRIX",
                "GENERATE_TEST_PROTOCOL",
                "REVIEW_TEST_RESULTS",
            ],
            "SL_4": [
                "ANALYZE_LOG",
                "CYBERSECURITY_ASSESSMENT",
                "PENETRATION_TEST",
                "GENERATE_SBOM",
                "HIL_TEST_FIRMWARE",
                "REVIEW_FIRMWARE_CHANGE",
                "TRACEABILITY_MATRIX",
                "FORMAL_VERIFICATION",
                "GENERATE_TEST_PROTOCOL",
                "REVIEW_TEST_RESULTS",
                "INDEPENDENT_SAFETY_ASSESSMENT",
            ],
        },

        "hil_required_for": ["SL_3", "SL_4"],

        "evidence_artifacts": [
            "Cybersecurity Management System — CSMS (IEC 62443-2-1 §4)",
            "Security Risk Assessment (IEC 62443-3-2)",
            "Security Requirements Specification (IEC 62443-3-3 §SR)",
            "Security Architecture Description (IEC 62443-3-3 §4)",
            "Secure Development Life Cycle Plan — SDLC (IEC 62443-4-1)",
            "Threat Model — STRIDE/PASTA/DREAD (IEC 62443-3-2 §5)",
            "Security Test Plan (IEC 62443-4-1 §12)",
            "Penetration Test Report (IEC 62443-4-2)",
            "Vulnerability Assessment Report (IEC 62443-3-2)",
            "Software Bill of Materials — SBOM (ETSI EN 303 645 §5.3.14)",
            "Patch Management Plan (ETSI EN 303 645 §5.6)",
            "Default Credential Policy (ETSI EN 303 645 §5.1)",
            "Data Minimisation and Privacy Assessment (ETSI EN 303 645 §5.8)",
            "Communication Security Assessment (IEC 62443-3-3 §SR 4.1-4.3)",
            "Incident Response Plan (IEC 62443-2-1 §4.2.3)",
            "Secure Disposal Policy (ETSI EN 303 645 §5.9)",
        ],

        "critical_flags": [
            {
                "id":           "IEC62443-SR-1.1",
                "level":        "CRITICAL",
                "description":  "Human user identification and authentication for all interfaces",
                "clause":       "IEC 62443-3-3 SR 1.1",
                "hil_required": False,
                "applies_to":   ["SL_1", "SL_2", "SL_3", "SL_4"],
            },
            {
                "id":           "IEC62443-SR-3.1",
                "level":        "CRITICAL",
                "description":  "Communication integrity — all communications authenticated or encrypted",
                "clause":       "IEC 62443-3-3 SR 3.1",
                "hil_required": False,
                "applies_to":   ["SL_1", "SL_2", "SL_3", "SL_4"],
            },
            {
                "id":           "IEC62443-SR-3.3",
                "level":        "CRITICAL",
                "description":  "Security functionality verification testing",
                "clause":       "IEC 62443-3-3 SR 3.3",
                "hil_required": True,
                "applies_to":   ["SL_2", "SL_3", "SL_4"],
            },
            {
                "id":           "IEC62443-SR-4.1",
                "level":        "CRITICAL",
                "description":  "Information confidentiality — data-in-transit encryption",
                "clause":       "IEC 62443-3-3 SR 4.1",
                "hil_required": False,
                "applies_to":   ["SL_2", "SL_3", "SL_4"],
            },
            {
                "id":           "ETSI-303645-5.1",
                "level":        "CRITICAL",
                "description":  "No default passwords — unique per-device or user-set on first use",
                "clause":       "ETSI EN 303 645 §5.1",
                "hil_required": False,
                "applies_to":   ["SL_1", "SL_2", "SL_3", "SL_4"],
            },
            {
                "id":           "ETSI-303645-5.3",
                "level":        "CRITICAL",
                "description":  "Secure update mechanism with cryptographic verification",
                "clause":       "ETSI EN 303 645 §5.3",
                "hil_required": True,
                "applies_to":   ["SL_1", "SL_2", "SL_3", "SL_4"],
            },
            {
                "id":           "ETSI-303645-5.6",
                "level":        "HIGH",
                "description":  "Timely security updates with defined support period and EOL notice",
                "clause":       "ETSI EN 303 645 §5.6",
                "hil_required": False,
                "applies_to":   ["SL_1", "SL_2", "SL_3", "SL_4"],
            },
            {
                "id":           "IEC62443-4-1-SDLC",
                "level":        "HIGH",
                "description":  "Secure development life cycle practices for component suppliers",
                "clause":       "IEC 62443-4-1:2018",
                "hil_required": False,
                "applies_to":   ["SL_2", "SL_3", "SL_4"],
            },
            {
                "id":           "IEC62443-SR-2.8",
                "level":        "HIGH",
                "description":  "Audit log of all security-relevant events with tamper resistance",
                "clause":       "IEC 62443-3-3 SR 2.8",
                "hil_required": False,
                "applies_to":   ["SL_2", "SL_3", "SL_4"],
            },
            {
                "id":           "IEC62443-SR-5.1",
                "level":        "HIGH",
                "description":  "Network segmentation — separation of IACS from corporate/external networks",
                "clause":       "IEC 62443-3-3 SR 5.1",
                "hil_required": False,
                "applies_to":   ["SL_2", "SL_3", "SL_4"],
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def list_domains() -> list:
    """Return all supported compliance domains."""
    return list(COMPLIANCE_FLAGS.keys())


def get_domain_risk_levels(domain: str) -> list:
    """Return the risk levels defined for a domain."""
    entry = COMPLIANCE_FLAGS.get(domain.lower())
    if not entry:
        return []
    return entry.get("risk_levels", [])


def get_required_flags(domain: str, risk_level: str) -> list:
    """
    Return all compliance flags required for a domain at a given risk level.

    Args:
        domain:     One of: medtech, automotive, railways, avionics, iot_ics
        risk_level: Domain-specific risk level (e.g. CLASS_C, ASIL_D, SIL_4, DAL_A, SL_3)

    Returns list of flag dicts that apply to this risk level.
    """
    entry = COMPLIANCE_FLAGS.get(domain.lower())
    if not entry:
        return []

    risk_upper = risk_level.upper()
    flags = []
    for flag in entry.get("critical_flags", []):
        applies = flag.get("applies_to", [])
        if risk_upper in [a.upper() for a in applies]:
            flags.append(flag)
    return flags


def get_hil_required_tests(domain: str, risk_level: str) -> list:
    """
    Return list of flag IDs that REQUIRE hardware-in-the-loop testing
    for a domain at the given risk level.

    Args:
        domain:     One of: medtech, automotive, railways, avionics, iot_ics
        risk_level: Domain-specific risk level

    Returns list of flag ID strings.
    """
    flags = get_required_flags(domain, risk_level)
    return [f["id"] for f in flags if f.get("hil_required", False)]


def generate_compliance_checklist(domain: str, risk_level: str) -> dict:
    """
    Generate a full compliance checklist for a domain and risk level.
    Each item includes a pass/fail status field (default: null — not yet evaluated).

    Args:
        domain:     One of: medtech, automotive, railways, avionics, iot_ics
        risk_level: Domain-specific risk level

    Returns a structured checklist dict ready for regulatory audit use.
    """
    entry = COMPLIANCE_FLAGS.get(domain.lower())
    if not entry:
        return {
            "error":       f"Unknown domain: {domain}. Valid: {list_domains()}",
            "domain":      domain,
            "risk_level":  risk_level,
            "items":       [],
        }

    risk_upper    = risk_level.upper()
    flags         = get_required_flags(domain, risk_upper)
    required_tasks = entry.get("required_tasks", {}).get(risk_upper, [])
    artifacts     = entry.get("evidence_artifacts", [])
    hil_required  = risk_upper in [r.upper() for r in entry.get("hil_required_for", [])]

    checklist_items = []

    # Compliance flags
    for flag in flags:
        checklist_items.append({
            "id":              flag["id"],
            "type":            "compliance_flag",
            "level":           flag["level"],
            "description":     flag["description"],
            "clause":          flag.get("clause", ""),
            "hil_required":    flag.get("hil_required", False),
            "status":          None,   # null = not yet evaluated
            "evidence_ref":    None,   # to be filled in during audit
            "notes":           "",
        })

    # Required task types
    for task in required_tasks:
        checklist_items.append({
            "id":           f"TASK-{task}",
            "type":         "required_task",
            "level":        "REQUIRED",
            "description":  f"Task type '{task}' must be completed for {domain.upper()} {risk_upper}",
            "clause":       entry.get("standard", ""),
            "hil_required": "HIL" in task,
            "status":       None,
            "evidence_ref": None,
            "notes":        "",
        })

    # Evidence artifacts
    for i, artifact in enumerate(artifacts):
        checklist_items.append({
            "id":           f"DOC-{i+1:03d}",
            "type":         "evidence_artifact",
            "level":        "REQUIRED",
            "description":  artifact,
            "clause":       entry.get("standard", ""),
            "hil_required": False,
            "status":       None,
            "evidence_ref": None,
            "notes":        "",
        })

    return {
        "domain":           domain,
        "risk_level":       risk_upper,
        "standard":         entry.get("standard", ""),
        "description":      entry.get("description", ""),
        "authority":        entry.get("authority", ""),
        "hil_testing_required": hil_required,
        "total_items":      len(checklist_items),
        "flags":            len(flags),
        "required_tasks":   len(required_tasks),
        "artifacts":        len(artifacts),
        "items":            checklist_items,
    }


def assess_compliance_gap(domain: str, risk_level: str, completed_tasks: list) -> dict:
    """
    Assess compliance gaps given a list of completed task type strings.

    Args:
        domain:          Compliance domain
        risk_level:      Risk level
        completed_tasks: List of task type strings already completed

    Returns gap analysis with missing tasks and overall compliance percentage.
    """
    entry = COMPLIANCE_FLAGS.get(domain.lower())
    if not entry:
        return {"error": f"Unknown domain: {domain}"}

    risk_upper    = risk_level.upper()
    required      = entry.get("required_tasks", {}).get(risk_upper, [])
    completed_set = {t.upper() for t in completed_tasks}
    missing       = [t for t in required if t.upper() not in completed_set]
    hil_missing   = [t for t in missing if "HIL" in t]

    pct = round((len(required) - len(missing)) / len(required) * 100, 1) if required else 100.0

    return {
        "domain":            domain,
        "risk_level":        risk_upper,
        "required_tasks":    required,
        "completed_tasks":   list(completed_set & {t.upper() for t in required}),
        "missing_tasks":     missing,
        "hil_tasks_missing": hil_missing,
        "compliance_pct":    pct,
        "compliant":         len(missing) == 0,
        "blocking_gaps":     hil_missing,
    }

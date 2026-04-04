"""
SAGE Framework — 100-Solution Build Experiment
================================================
Generates comprehensive human-evaluable output for all 100 solutions
across 10 domains using the full SAGE pipeline:

  PO (Product Owner) → SE (Systems Engineer) → Build Orchestrator

Each solution produces:
  - PO: Clarifying questions, personas, user stories, constraints
  - SE: System requirements, subsystems, interfaces, risk assessment
  - Orchestrator: Domain detection, agent assignment, task decomposition, HITL gates
  - Safety: FMEA/FTA/ASIL/SIL where applicable
  - Regulatory: Standards detection, compliance assessment

Output: experiments/100_builds_report.md (structured tables for human eval)

Usage:
  source .venv/bin/activate
  python experiments/run_100_builds.py
  python experiments/run_100_builds.py --domain medtech
  python experiments/run_100_builds.py --id 001
"""

import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("100_builds")

REGISTRY = os.path.join(os.path.dirname(__file__), "..", "test-solutions", "solutions_registry.csv")
OUTPUT = os.path.join(os.path.dirname(__file__), "100_builds_report.md")


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_registry(domain_filter=None, id_filter=None):
    with open(REGISTRY) as f:
        rows = list(csv.DictReader(f))
    if domain_filter:
        rows = [r for r in rows if r["domain"] == domain_filter]
    if id_filter:
        rows = [r for r in rows if r["id"] == id_filter]
    return rows


# ---------------------------------------------------------------------------
# PO Simulation — deterministic, uses domain knowledge
# ---------------------------------------------------------------------------

PO_QUESTIONS_BY_DOMAIN = {
    "medtech": [
        "What is the intended FDA classification pathway (510(k), De Novo, PMA)?",
        "Who are the primary clinical end users (physicians, nurses, patients, caregivers)?",
        "What predicate devices or existing solutions are you benchmarking against?",
        "What clinical data or evidence will be required for regulatory submission?",
        "What EHR systems must integrate (Epic, Cerner, Allscripts)?",
    ],
    "fintech": [
        "What is your target customer segment (consumer, SMB, enterprise)?",
        "Which regulatory jurisdictions must be covered (US, EU, UK, APAC)?",
        "What payment rails/processors are required (Stripe, Plaid, FIS)?",
        "What is your KYC/AML compliance strategy?",
        "What is the expected transaction volume at launch and 12-month scale?",
    ],
    "automotive": [
        "Are you building as Tier 1 supplier to OEMs or direct aftermarket product?",
        "What ASIL level is required for the safety-critical functions?",
        "What ECU platform and AUTOSAR version are targeted?",
        "What sensor suite is available (camera, LiDAR, radar, ultrasonic)?",
        "What vehicle communication buses are used (CAN FD, Ethernet, LIN)?",
    ],
    "saas": [
        "Who is the primary buyer persona (end user, team lead, IT admin, C-level)?",
        "What existing tools must integrate (Slack, Jira, Salesforce, Google Workspace)?",
        "What is the pricing model (freemium, per-seat, usage-based, enterprise)?",
        "What is the competitive differentiation from established players?",
        "What are the data residency requirements (US, EU, SOC 2, ISO 27001)?",
    ],
    "ecommerce": [
        "What is the seller model (single brand, multi-vendor marketplace, dropship)?",
        "What payment methods and currencies must be supported?",
        "What fulfillment model (self-shipped, 3PL, dropship)?",
        "What is the primary traffic source (organic, paid, social, marketplace)?",
        "What return/refund policy framework is required?",
    ],
    "iot": [
        "What communication protocols are required (MQTT, LoRa, Zigbee, BLE, Matter)?",
        "What is the expected device fleet size and geographic distribution?",
        "What is the power budget (battery life, solar, mains)?",
        "What is the data latency requirement (real-time, near-real-time, batch)?",
        "What OTA update mechanism is needed for field devices?",
    ],
    "ml_ai": [
        "What is the primary ML task (classification, regression, generation, extraction)?",
        "What is the training data source and labeling strategy?",
        "What are the accuracy/latency requirements for production inference?",
        "What is the model deployment target (cloud API, edge, mobile)?",
        "What bias evaluation and fairness requirements apply?",
    ],
    "edtech": [
        "Who are the learners (K-12 students, professionals, enterprise employees)?",
        "What pedagogy model (self-paced, instructor-led, cohort-based, adaptive)?",
        "What learning standards must be supported (SCORM, xAPI, LTI)?",
        "What accessibility requirements apply (WCAG 2.1, Section 508)?",
        "Are there age-related compliance requirements (COPPA, FERPA)?",
    ],
    "consumer_app": [
        "What is the primary user motivation (utility, social, entertainment, health)?",
        "What platforms are targeted (iOS, Android, web, cross-platform)?",
        "What is the monetization model (freemium, subscription, ads, marketplace)?",
        "What third-party integrations are required (Apple Health, Google Fit, social)?",
        "What is the user acquisition strategy (organic, paid, viral)?",
    ],
    "enterprise": [
        "What existing enterprise systems must integrate (ERP, CRM, HRIS, ITSM)?",
        "What authentication/authorization standards are required (SAML, OIDC, SCIM)?",
        "What compliance frameworks apply (SOC 2, ISO 27001, GDPR, HIPAA)?",
        "What is the deployment model (SaaS, on-prem, hybrid)?",
        "What is the expected concurrent user count and data volume?",
    ],
}

PERSONAS_BY_DOMAIN = {
    "medtech": ["Clinical User/HCP", "Patient/Caregiver", "Regulatory Affairs Specialist", "Biomedical Engineer"],
    "fintech": ["End Consumer", "Compliance Officer", "Operations Manager", "API Developer"],
    "automotive": ["Vehicle Engineer", "Safety Assessor", "OEM Integration Lead", "Test Driver"],
    "saas": ["End User", "Team Admin", "IT Manager", "Executive Sponsor"],
    "ecommerce": ["Buyer/Shopper", "Seller/Merchant", "Marketplace Admin", "Logistics Manager"],
    "iot": ["Device Operator", "Fleet Manager", "Data Analyst", "Field Technician"],
    "ml_ai": ["Data Scientist", "ML Engineer", "Business Analyst", "API Consumer"],
    "edtech": ["Learner/Student", "Instructor/Teacher", "Platform Admin", "Content Creator"],
    "consumer_app": ["Primary User", "Power User", "Casual Browser", "Content Creator"],
    "enterprise": ["IT Admin", "End User/Employee", "Compliance Auditor", "System Integrator"],
}


def simulate_po(sol):
    """Simulate Product Owner agent output for a solution."""
    domain = sol["domain"]
    desc = sol["description"]
    name = sol["name"]

    questions = PO_QUESTIONS_BY_DOMAIN.get(domain, PO_QUESTIONS_BY_DOMAIN["saas"])
    personas = PERSONAS_BY_DOMAIN.get(domain, PERSONAS_BY_DOMAIN["saas"])

    # Generate user stories from description keywords
    stories = _generate_user_stories(desc, domain)

    return {
        "clarifying_questions": questions,
        "personas": personas,
        "user_stories": stories,
        "regulation_level": sol.get("regulation_level", "Standard"),
        "min_tasks": int(sol.get("min_tasks", 8)),
    }


def _generate_user_stories(desc, domain):
    """Extract user stories from description keywords."""
    stories = []
    words = desc.lower()

    # Common story patterns
    story_patterns = [
        ("user account", "As a user, I want to create an account so that I can access the platform"),
        ("dashboard", "As a user, I want to view a real-time dashboard so that I can monitor key metrics"),
        ("notification", "As a user, I want to receive notifications so that I am informed of important events"),
        ("report", "As an admin, I want to generate reports so that I can track performance"),
        ("api", "As a developer, I want a REST API so that I can integrate with external systems"),
        ("mobile", "As a user, I want a mobile-responsive interface so that I can use the system on my phone"),
        ("search", "As a user, I want to search and filter data so that I can find relevant information quickly"),
        ("export", "As a user, I want to export data to CSV/PDF so that I can share it externally"),
    ]

    # Domain-specific stories
    domain_stories = {
        "medtech": [
            "As a clinician, I want to review patient data with clear provenance so that I can make informed decisions",
            "As a regulatory specialist, I want all software changes traced to requirements so that I can maintain compliance",
            "As a safety engineer, I want risk assessments linked to design decisions so that residual risk is documented",
        ],
        "fintech": [
            "As a user, I want to complete transactions securely so that my financial data is protected",
            "As a compliance officer, I want an immutable audit trail so that regulatory reporting is accurate",
            "As an operator, I want fraud detection alerts so that suspicious activity is flagged immediately",
        ],
        "automotive": [
            "As a safety assessor, I want ASIL decomposition verified so that functional safety is assured",
            "As a firmware engineer, I want MISRA-C compliance reports so that code quality meets automotive standards",
            "As a test driver, I want HIL test results documented so that field behavior matches simulation",
        ],
        "iot": [
            "As a fleet manager, I want OTA firmware updates so that devices can be patched remotely",
            "As a data analyst, I want time-series telemetry so that I can detect anomalies in device behavior",
            "As a technician, I want device diagnostic data so that I can troubleshoot field issues",
        ],
        "ml_ai": [
            "As a data scientist, I want model versioning so that I can track experiments and reproduce results",
            "As an ML engineer, I want A/B testing for models so that I can compare production performance",
            "As a business analyst, I want model explainability so that I can understand prediction drivers",
        ],
        "saas": [
            "As a team admin, I want role-based access control so that permissions are managed per team",
            "As an end user, I want a responsive dashboard so that I can access key metrics quickly",
            "As an IT admin, I want SSO integration so that authentication follows corporate policy",
        ],
        "ecommerce": [
            "As a buyer, I want to search and filter products so that I can find what I need quickly",
            "As a seller, I want inventory tracking so that I never oversell",
            "As an admin, I want sales analytics so that I can optimize pricing and promotions",
        ],
        "edtech": [
            "As a student, I want progress tracking so that I can see my learning trajectory",
            "As an instructor, I want assessment tools so that I can evaluate student understanding",
            "As an admin, I want compliance reporting so that institutional standards are met",
        ],
        "consumer_app": [
            "As a user, I want push notifications so that I stay engaged with timely updates",
            "As a user, I want social sharing so that I can share achievements with friends",
            "As a user, I want offline mode so that core features work without connectivity",
        ],
        "enterprise": [
            "As an IT admin, I want audit logging so that all system actions are traceable",
            "As a manager, I want workflow approvals so that processes follow corporate governance",
            "As a compliance officer, I want data retention policies so that regulatory requirements are met",
            "As an integrator, I want REST APIs so that the system connects to existing infrastructure",
        ],
    }

    # Add generic stories matching description
    for keyword, story in story_patterns:
        if keyword in words:
            stories.append(story)

    # Add domain-specific stories
    stories.extend(domain_stories.get(domain, []))

    # Ensure minimum stories
    if len(stories) < 5:
        stories.append(f"As a user, I want core {domain} functionality so that the primary use case is met")

    return stories[:8]  # Cap at 8


# ---------------------------------------------------------------------------
# SE Simulation — uses actual SAGE engines
# ---------------------------------------------------------------------------

def simulate_se(sol, po_result):
    """Simulate Systems Engineer output using actual SAGE engines."""
    desc = sol["description"]
    domain = sol["domain"]

    # Use actual domain detection
    from src.integrations.build_orchestrator import BuildOrchestrator
    orch = BuildOrchestrator(checkpoint_db=":memory:")
    detected = orch._detect_domain(desc)
    matched = orch._matched_domains(desc)

    # Get standards from DOMAIN_RULES + description keyword scan
    expected_domain_key = sol.get("expected_domain_key", "")
    standards = _detect_standards(desc, domain, expected_domain_key)

    # Generate subsystems from description
    subsystems = _identify_subsystems(desc, domain)

    # Get HITL level
    hitl_level = "strict" if sol.get("regulation_level", "").lower() == "strict" else "standard"

    return {
        "detected_domain": detected,
        "matched_domains": [m for m in matched],
        "standards": standards,
        "subsystems": subsystems,
        "hitl_level": hitl_level,
    }


def _detect_standards(desc, domain, expected_domain_key=""):
    """Detect applicable standards from DOMAIN_RULES + description keywords."""
    from src.integrations.build_orchestrator import DOMAIN_RULES

    # Primary: use expected_domain_key → DOMAIN_RULES standards
    standards = list(DOMAIN_RULES.get(expected_domain_key, {}).get("standards", []))

    # Secondary: scan description for well-known standard references
    desc_upper = desc.upper()
    known_standards = {
        "IEC 62304": ["IEC 62304", "62304"],
        "ISO 13485": ["ISO 13485", "13485"],
        "ISO 14971": ["ISO 14971", "14971"],
        "FDA 21 CFR Part 820": ["21 CFR", "CFR 820"],
        "ISO 26262": ["ISO 26262", "26262"],
        "AUTOSAR": ["AUTOSAR"],
        "DO-178C": ["DO-178", "DO178"],
        "IEC 61508": ["IEC 61508", "61508"],
        "IEC 62443": ["IEC 62443", "62443"],
        "PCI DSS": ["PCI DSS", "PCI-DSS"],
        "SOC 2": ["SOC 2", "SOC2"],
        "HIPAA": ["HIPAA"],
        "GDPR": ["GDPR"],
        "FERPA": ["FERPA"],
        "COPPA": ["COPPA"],
    }
    for std_id, keywords in known_standards.items():
        if std_id not in standards and any(kw.upper() in desc_upper for kw in keywords):
            standards.append(std_id)

    return standards[:8]


def _identify_subsystems(desc, domain):
    """Identify subsystems based on domain and description keywords."""
    base_subsystems = {
        "medtech": ["Clinical Frontend", "Backend API", "Database", "Auth/RBAC", "Regulatory Module", "Integration Gateway", "Audit Logger"],
        "fintech": ["API Gateway", "Core Banking/Ledger", "Payment Service", "KYC/AML Module", "Analytics Engine", "Notification Service", "Admin Console"],
        "automotive": ["Sensor Interface", "Perception Pipeline", "Decision Engine", "Vehicle Interface", "Safety Monitor", "Diagnostic Logger", "Calibration Service"],
        "saas": ["Frontend (React)", "Backend API (FastAPI)", "Database (PostgreSQL)", "Auth (OAuth 2.0)", "Integration Service", "Analytics", "Admin Panel"],
        "ecommerce": ["Storefront", "Catalog Service", "Order Management", "Payment Gateway", "Search Engine", "Review System", "Admin Dashboard"],
        "iot": ["Device Firmware", "Protocol Stack", "Edge Gateway", "Cloud Backend", "Time-Series DB", "Device Manager", "OTA Service"],
        "ml_ai": ["Data Ingestion", "Feature Store", "Training Pipeline", "Model Registry", "Inference Service", "Monitoring", "API Gateway"],
        "edtech": ["Course Builder", "Content Delivery", "Assessment Engine", "Progress Tracker", "Certificate Generator", "LMS Integration", "Analytics"],
        "consumer_app": ["Mobile App", "Backend API", "User Service", "Content Feed", "Notification Service", "Analytics", "CDN"],
        "enterprise": ["Core Platform", "Auth/IAM", "Workflow Engine", "Data Store", "Integration Hub", "Audit/Compliance", "Admin Console"],
    }
    return base_subsystems.get(domain, base_subsystems["saas"])


# ---------------------------------------------------------------------------
# Build Orchestrator Simulation — uses actual SAGE engines
# ---------------------------------------------------------------------------

def simulate_orchestrator(sol, po_result, se_result):
    """Simulate Build Orchestrator output using actual SAGE task routing."""
    from src.integrations.build_orchestrator import (
        TASK_TYPE_TO_AGENT, DOMAIN_RULES, BUILD_TASK_TYPES,
        HITL_LEVELS, adaptive_router,
    )

    desc = sol["description"]
    domain = sol["domain"]
    domain_key = sol.get("expected_domain_key", "")

    # Get domain rules
    rules = DOMAIN_RULES.get(domain_key, {})
    required_types = rules.get("required_types", [])
    standards = rules.get("standards", [])
    hitl = rules.get("hitl_override", "standard")
    extra_criteria = rules.get("extra_criteria", {})

    # Build task list with agent assignments
    base_types = ["ARCHITECTURE", "BACKEND", "FRONTEND", "DATABASE", "API", "TESTS", "DEVOPS", "QA"]
    all_types = list(set(base_types + required_types))

    tasks = []
    agents_activated = set()
    for i, task_type in enumerate(all_types, 1):
        agent = TASK_TYPE_TO_AGENT.get(task_type, "developer")
        agents_activated.add(agent)
        criteria = extra_criteria.get(task_type, [])
        tasks.append({
            "step": i,
            "task_type": task_type,
            "agent_role": agent,
            "acceptance_criteria": criteria if isinstance(criteria, list) else [],
        })

    # Determine HITL gates
    hitl_gates = HITL_LEVELS.get(hitl, HITL_LEVELS.get("standard", {}))

    return {
        "domain_key": domain_key,
        "domain_rules": {
            "standards": standards,
            "hitl_level": hitl,
            "required_types": required_types,
        },
        "tasks": tasks,
        "task_count": len(tasks),
        "agents_activated": sorted(agents_activated),
        "agent_count": len(agents_activated),
        "hitl_gates": hitl_gates,
    }


# ---------------------------------------------------------------------------
# Safety Simulation — uses actual FMEA/FTA/ASIL engines
# ---------------------------------------------------------------------------

def simulate_safety(sol, se_result):
    """Run actual safety analysis for regulated domains."""
    domain = sol["domain"]
    if domain not in ("medtech", "automotive", "iot"):
        return None

    try:
        from src.core.functional_safety import functional_safety

        # Generate domain-appropriate FMEA entries
        fmea_entries = _generate_fmea_entries(sol)
        fmea_result = functional_safety.generate_fmea_table(fmea_entries)

        # ASIL classification for automotive — varies by solution criticality
        asil_result = None
        if domain == "automotive":
            name = sol["name"]
            # Safety-critical: ASIL D
            if any(k in name for k in ("adas", "autonomous", "v2x", "battery")):
                asil_result = functional_safety.classify_asil("S3", "E4", "C3")  # ASIL D
            # Medium-critical: ASIL B
            elif any(k in name for k in ("fleet", "charging", "obd", "connected")):
                asil_result = functional_safety.classify_asil("S2", "E3", "C2")  # ASIL B
            # Low-critical: ASIL A/QM
            else:
                asil_result = functional_safety.classify_asil("S1", "E2", "C2")  # ASIL A

        # SIL classification for medtech/iot — varies by risk level
        sil_result = None
        if domain in ("medtech", "iot"):
            name = sol["name"]
            if any(k in name for k in ("insulin", "surgical", "imaging", "industrial")):
                sil_result = functional_safety.classify_sil(1e-8)  # SIL 4
            elif any(k in name for k in ("patient_monitoring", "fall_detection", "cold_chain")):
                sil_result = functional_safety.classify_sil(1e-7)  # SIL 3
            elif any(k in name for k in ("telehealth", "clinical", "ehr", "energy")):
                sil_result = functional_safety.classify_sil(1e-6)  # SIL 2
            else:
                sil_result = functional_safety.classify_sil(1e-5)  # SIL 1

        # IEC 62304 classification for medtech — varies by harm potential
        iec_result = None
        if domain == "medtech":
            name = sol["name"]
            if any(k in name for k in ("insulin", "surgical")):
                iec_result = functional_safety.classify_iec62304("death_possible")  # Class C
            elif any(k in name for k in ("patient_monitoring", "fall_detection", "imaging")):
                iec_result = functional_safety.classify_iec62304("injury_possible")  # Class B
            else:
                iec_result = functional_safety.classify_iec62304("no_injury")  # Class A

        return {
            "fmea": fmea_result,
            "asil": asil_result,
            "sil": sil_result,
            "iec62304": iec_result,
        }
    except Exception as exc:
        logger.warning("Safety simulation failed for %s: %s", sol["id"], exc)
        return None


def _generate_fmea_entries(sol):
    """Generate solution-specific FMEA entries using description keywords and domain."""
    domain = sol["domain"]
    name = sol["name"]
    desc = sol.get("description", "").lower()

    # Solution-specific FMEA entries keyed by solution name patterns
    solution_fmea = {
        # Medtech
        "fall_detection": [
            {"component": "Accelerometer Module", "failure_mode": "Sensor drift", "effect": "Missed fall event", "severity": 9, "occurrence": 3, "detection": 4},
            {"component": "Alert Dispatcher", "failure_mode": "SMS gateway timeout", "effect": "Caregiver not notified", "severity": 10, "occurrence": 2, "detection": 3},
            {"component": "GPS Tracker", "failure_mode": "No satellite lock", "effect": "Unknown patient location", "severity": 8, "occurrence": 4, "detection": 5},
            {"component": "Battery Manager", "failure_mode": "Premature shutdown", "effect": "Device offline during emergency", "severity": 10, "occurrence": 2, "detection": 4},
        ],
        "insulin_pump": [
            {"component": "CGM Interface", "failure_mode": "Stale glucose reading", "effect": "Incorrect dosing calculation", "severity": 10, "occurrence": 3, "detection": 3},
            {"component": "Dosing Algorithm", "failure_mode": "Overflow in calculation", "effect": "Dangerous insulin overdose", "severity": 10, "occurrence": 1, "detection": 2},
            {"component": "Pump Motor Driver", "failure_mode": "Stuck valve", "effect": "No insulin delivery", "severity": 9, "occurrence": 2, "detection": 4},
            {"component": "Bluetooth Link", "failure_mode": "Connection drop", "effect": "Loss of monitoring visibility", "severity": 7, "occurrence": 4, "detection": 3},
        ],
        "telehealth": [
            {"component": "Video Engine", "failure_mode": "Codec failure", "effect": "Consultation interrupted", "severity": 7, "occurrence": 3, "detection": 2},
            {"component": "E-Prescription Module", "failure_mode": "Drug interaction missed", "effect": "Adverse drug event", "severity": 10, "occurrence": 2, "detection": 4},
            {"component": "EHR Integration", "failure_mode": "HL7 parse error", "effect": "Patient data not synced", "severity": 8, "occurrence": 3, "detection": 3},
        ],
        "surgical_robot": [
            {"component": "Haptic Controller", "failure_mode": "Force feedback lag", "effect": "Surgeon loses tissue feel", "severity": 10, "occurrence": 2, "detection": 2},
            {"component": "3D Visualization", "failure_mode": "Frame drop below 30fps", "effect": "Depth perception compromised", "severity": 9, "occurrence": 3, "detection": 3},
            {"component": "Instrument Tracker", "failure_mode": "Position error >1mm", "effect": "Unintended tissue damage", "severity": 10, "occurrence": 2, "detection": 3},
            {"component": "Emergency Stop", "failure_mode": "E-stop signal ignored", "effect": "Uncontrolled instrument motion", "severity": 10, "occurrence": 1, "detection": 1},
        ],
        "patient_monitoring": [
            {"component": "Vital Signs Display", "failure_mode": "Stale data shown", "effect": "Clinician acts on old data", "severity": 9, "occurrence": 3, "detection": 4},
            {"component": "Alarm System", "failure_mode": "Alarm suppressed", "effect": "Critical event unnoticed", "severity": 10, "occurrence": 2, "detection": 3},
            {"component": "Trend Calculator", "failure_mode": "Moving average overflow", "effect": "False trend indication", "severity": 7, "occurrence": 2, "detection": 4},
        ],
        "clinical_trial": [
            {"component": "Randomization Engine", "failure_mode": "Bias in allocation", "effect": "Trial integrity compromised", "severity": 10, "occurrence": 2, "detection": 5},
            {"component": "eCRF Module", "failure_mode": "Data field truncation", "effect": "Regulatory submission data loss", "severity": 9, "occurrence": 3, "detection": 4},
            {"component": "Adverse Event Reporter", "failure_mode": "Missed SAE deadline", "effect": "Regulatory violation", "severity": 10, "occurrence": 2, "detection": 3},
        ],
        "medical_imaging": [
            {"component": "DICOM Parser", "failure_mode": "Pixel data corruption", "effect": "Misdiagnosis from artifact", "severity": 10, "occurrence": 2, "detection": 3},
            {"component": "AI Classifier", "failure_mode": "False negative", "effect": "Missed pathology", "severity": 10, "occurrence": 3, "detection": 4},
            {"component": "Report Generator", "failure_mode": "Wrong patient ID", "effect": "Report attached to wrong patient", "severity": 9, "occurrence": 2, "detection": 2},
        ],
        # Automotive
        "adas_perception": [
            {"component": "LiDAR Processor", "failure_mode": "Point cloud dropout", "effect": "Pedestrian not detected", "severity": 10, "occurrence": 2, "detection": 3},
            {"component": "Camera Pipeline", "failure_mode": "Lens flare saturation", "effect": "Lane markings lost", "severity": 8, "occurrence": 4, "detection": 4},
            {"component": "Radar Tracker", "failure_mode": "Ghost target", "effect": "Phantom braking event", "severity": 7, "occurrence": 3, "detection": 3},
            {"component": "Fusion Engine", "failure_mode": "Timestamp misalignment", "effect": "Object position error", "severity": 9, "occurrence": 2, "detection": 3},
        ],
        "battery_management": [
            {"component": "Cell Balancer", "failure_mode": "Bypass transistor stuck ON", "effect": "Cell overdischarge / thermal runaway", "severity": 10, "occurrence": 2, "detection": 3},
            {"component": "SOC Estimator", "failure_mode": "Coulomb counting drift", "effect": "Incorrect range estimate", "severity": 6, "occurrence": 4, "detection": 4},
            {"component": "Thermal Manager", "failure_mode": "Coolant pump failure", "effect": "Battery overtemperature", "severity": 10, "occurrence": 2, "detection": 2},
            {"component": "CAN Reporter", "failure_mode": "DTC suppressed", "effect": "Dashboard shows no fault", "severity": 8, "occurrence": 2, "detection": 4},
        ],
        "infotainment": [
            {"component": "Media Player", "failure_mode": "Audio underrun", "effect": "Audio dropout", "severity": 3, "occurrence": 5, "detection": 2},
            {"component": "Navigation Engine", "failure_mode": "Map tile cache miss", "effect": "Blank map region", "severity": 5, "occurrence": 3, "detection": 3},
            {"component": "Bluetooth Stack", "failure_mode": "Pairing loop", "effect": "Phone disconnects repeatedly", "severity": 4, "occurrence": 4, "detection": 3},
        ],
        "fleet_telematics": [
            {"component": "GPS Module", "failure_mode": "Position drift in urban canyon", "effect": "Incorrect vehicle location", "severity": 6, "occurrence": 4, "detection": 4},
            {"component": "OBD Data Logger", "failure_mode": "PID decode error", "effect": "Wrong fuel efficiency metric", "severity": 5, "occurrence": 3, "detection": 4},
            {"component": "Geofence Engine", "failure_mode": "Polygon overflow", "effect": "Missed boundary violation", "severity": 7, "occurrence": 2, "detection": 3},
        ],
        "autonomous_parking": [
            {"component": "Ultrasonic Array", "failure_mode": "Cross-talk interference", "effect": "Phantom obstacle detected", "severity": 7, "occurrence": 3, "detection": 3},
            {"component": "Path Planner", "failure_mode": "Deadlock in tight space", "effect": "Vehicle stuck mid-maneuver", "severity": 6, "occurrence": 3, "detection": 4},
            {"component": "Steering Actuator", "failure_mode": "Angle sensor offset", "effect": "Vehicle drifts from planned path", "severity": 9, "occurrence": 2, "detection": 2},
        ],
        # IoT
        "smart_home": [
            {"component": "Zigbee Coordinator", "failure_mode": "Network partition", "effect": "Devices unreachable", "severity": 5, "occurrence": 4, "detection": 3},
            {"component": "Rule Engine", "failure_mode": "Infinite trigger loop", "effect": "Device flapping on/off", "severity": 6, "occurrence": 3, "detection": 4},
            {"component": "Voice Interface", "failure_mode": "Wake word false positive", "effect": "Unintended device activation", "severity": 4, "occurrence": 5, "detection": 3},
        ],
        "industrial_iot": [
            {"component": "PLC Gateway", "failure_mode": "Modbus CRC error", "effect": "Incorrect sensor reading", "severity": 8, "occurrence": 3, "detection": 3},
            {"component": "SCADA Bridge", "failure_mode": "Buffer overflow", "effect": "Control system compromise", "severity": 10, "occurrence": 2, "detection": 4},
            {"component": "Predictive Model", "failure_mode": "Concept drift", "effect": "False maintenance alert", "severity": 5, "occurrence": 4, "detection": 5},
        ],
        "agriculture": [
            {"component": "Soil Moisture Sensor", "failure_mode": "Electrode corrosion", "effect": "Over-irrigation", "severity": 5, "occurrence": 4, "detection": 5},
            {"component": "Weather Station", "failure_mode": "Anemometer stuck", "effect": "Incorrect wind speed", "severity": 4, "occurrence": 3, "detection": 4},
            {"component": "Irrigation Controller", "failure_mode": "Valve stuck open", "effect": "Water waste / crop flooding", "severity": 7, "occurrence": 3, "detection": 3},
        ],
        "cold_chain": [
            {"component": "Temperature Logger", "failure_mode": "Sensor out of calibration", "effect": "Undetected excursion", "severity": 9, "occurrence": 3, "detection": 4},
            {"component": "Alert Gateway", "failure_mode": "Cellular dead zone", "effect": "Delayed excursion notification", "severity": 8, "occurrence": 3, "detection": 4},
            {"component": "Compliance Reporter", "failure_mode": "Time zone mismatch", "effect": "Audit log timestamps wrong", "severity": 7, "occurrence": 2, "detection": 3},
        ],
    }

    # Match solution name to FMEA entries
    for key, entries in solution_fmea.items():
        if key in name:
            return entries

    # Fallback: domain-generic entries
    domain_fallback = {
        "medtech": [
            {"component": "Clinical Module", "failure_mode": "Data validation bypass", "effect": "Invalid clinical data stored", "severity": 9, "occurrence": 3, "detection": 4},
            {"component": "User Interface", "failure_mode": "Misleading status indicator", "effect": "Clinician makes wrong decision", "severity": 8, "occurrence": 3, "detection": 3},
            {"component": "Integration Layer", "failure_mode": "HL7/FHIR mapping error", "effect": "Patient data mismatch", "severity": 9, "occurrence": 2, "detection": 4},
        ],
        "automotive": [
            {"component": "ECU Interface", "failure_mode": "Message dropout on CAN", "effect": "Loss of telemetry data", "severity": 7, "occurrence": 3, "detection": 3},
            {"component": "Safety Monitor", "failure_mode": "Watchdog not triggered", "effect": "Silent system hang", "severity": 9, "occurrence": 2, "detection": 3},
            {"component": "Diagnostic Service", "failure_mode": "DTC suppressed", "effect": "Fault not reported to driver", "severity": 8, "occurrence": 2, "detection": 4},
        ],
        "iot": [
            {"component": "Edge Gateway", "failure_mode": "Connection loss", "effect": "Data gap in telemetry", "severity": 5, "occurrence": 5, "detection": 3},
            {"component": "OTA Service", "failure_mode": "Partial update", "effect": "Bricked device", "severity": 8, "occurrence": 2, "detection": 4},
            {"component": "Sensor Node", "failure_mode": "Calibration drift", "effect": "Inaccurate readings", "severity": 6, "occurrence": 4, "detection": 5},
        ],
    }
    return domain_fallback.get(domain, [])


# ---------------------------------------------------------------------------
# Report Generation
# ---------------------------------------------------------------------------

def generate_report(results, output_path):
    """Generate comprehensive markdown report for human evaluation."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        f"# SAGE Framework — 100-Solution Build Experiment Results",
        f"## Full Pipeline: Product Owner → Systems Engineer → Build Orchestrator",
        f"",
        f"**Date:** {now}  ",
        f"**Solutions:** {len(results)}  ",
        f"**Domains:** {len(set(r['domain'] for r in results))}  ",
        f"**Pipeline:** PO Requirements → SE Architecture → Domain Detection → Agent Assignment → Task Decomposition → Safety Analysis → HITL Gates",
        f"",
        f"---",
        f"",
    ]

    # Executive summary
    lines.extend(_generate_summary(results))

    # Per-domain sections
    domains = sorted(set(r["domain"] for r in results))
    for domain in domains:
        domain_results = [r for r in results if r["domain"] == domain]
        lines.extend(_generate_domain_section(domain, domain_results))

    # Cross-domain analysis
    lines.extend(_generate_cross_domain(results))

    # Agent heatmap
    lines.extend(_generate_agent_heatmap(results))

    # Regulatory coverage
    lines.extend(_generate_regulatory_table(results))

    # Safety analysis summary
    lines.extend(_generate_safety_summary(results))

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    logger.info("Report written to %s (%d lines)", output_path, len(lines))


def _generate_summary(results):
    """Executive summary table."""
    domains = {}
    for r in results:
        d = r["domain"]
        if d not in domains:
            domains[d] = {"count": 0, "agents_total": 0, "strict": 0, "standard": 0, "tasks_total": 0, "standards_total": 0}
        domains[d]["count"] += 1
        domains[d]["agents_total"] += r["orchestrator"]["agent_count"]
        domains[d]["tasks_total"] += r["orchestrator"]["task_count"]
        if r["orchestrator"]["domain_rules"]["hitl_level"] == "strict":
            domains[d]["strict"] += 1
        else:
            domains[d]["standard"] += 1
        domains[d]["standards_total"] += len(r["se"]["standards"])

    lines = [
        "## Executive Summary",
        "",
        "| Domain | Solutions | Avg Agents | Avg Tasks | HITL Level | Standards Detected | Avg Standards/Solution |",
        "|--------|-----------|-----------|-----------|------------|-------------------|----------------------|",
    ]
    for d in sorted(domains):
        s = domains[d]
        hitl = "Strict" if s["strict"] > s["standard"] else "Standard"
        lines.append(
            f"| **{d}** | {s['count']} | {s['agents_total']/s['count']:.0f} | "
            f"{s['tasks_total']/s['count']:.0f} | {hitl} | "
            f"{s['standards_total']} | {s['standards_total']/s['count']:.1f} |"
        )

    total_agents = sum(r["orchestrator"]["agent_count"] for r in results)
    total_tasks = sum(r["orchestrator"]["task_count"] for r in results)
    lines.append(f"| **TOTAL** | **{len(results)}** | **{total_agents/len(results):.0f}** | "
                 f"**{total_tasks/len(results):.0f}** | — | — | — |")
    lines.extend(["", "---", ""])
    return lines


def _generate_domain_section(domain, results):
    """Generate detailed section for one domain."""
    lines = [
        f"## {domain.replace('_', ' ').title()} ({len(results)} solutions)",
        "",
        "| # | ID | Solution | PO Questions | Personas | User Stories | Subsystems | Agents | Tasks | HITL | Standards |",
        "|---|-----|---------|-------------|----------|-------------|------------|--------|-------|------|-----------|",
    ]

    for i, r in enumerate(results, 1):
        sol = r["sol"]
        po = r["po"]
        se = r["se"]
        orch = r["orchestrator"]
        lines.append(
            f"| {i} | {sol['id']} | **{sol['name'].replace('_', ' ').title()}** | "
            f"{len(po['clarifying_questions'])} | {len(po['personas'])} | "
            f"{len(po['user_stories'])} | {len(se['subsystems'])} | "
            f"{orch['agent_count']} | {orch['task_count']} | "
            f"{orch['domain_rules']['hitl_level'].title()} | "
            f"{', '.join(se['standards'][:3]) or '—'} |"
        )

    # Detail table for each solution
    lines.extend(["", "### Detailed Per-Solution Breakdown", ""])
    for r in results:
        sol = r["sol"]
        po = r["po"]
        se = r["se"]
        orch = r["orchestrator"]

        lines.extend([
            f"#### {sol['id']} — {sol['name'].replace('_', ' ').title()}",
            f"",
            f"**Description:** {sol['description'][:200]}",
            f"",
            f"**PO Clarifying Questions:**",
        ])
        for q in po["clarifying_questions"]:
            lines.append(f"- {q}")

        lines.extend([
            f"",
            f"**Personas:** {', '.join(po['personas'])}",
            f"",
            f"**User Stories ({len(po['user_stories'])}):**",
        ])
        for s in po["user_stories"][:5]:
            lines.append(f"- {s}")
        if len(po["user_stories"]) > 5:
            lines.append(f"- *(+{len(po['user_stories'])-5} more)*")

        lines.extend([
            f"",
            f"**Subsystems ({len(se['subsystems'])}):** {', '.join(se['subsystems'])}",
            f"",
            f"**Standards:** {', '.join(se['standards']) or 'None detected'}",
            f"",
            f"**Agents Activated ({orch['agent_count']}):** {', '.join(orch['agents_activated'])}",
            f"",
            f"**Task Types ({orch['task_count']}):**",
        ])
        for t in orch["tasks"]:
            criteria_str = f" — Criteria: {'; '.join(t['acceptance_criteria'][:2])}" if t["acceptance_criteria"] else ""
            lines.append(f"- Step {t['step']}: `{t['task_type']}` → `{t['agent_role']}`{criteria_str}")

        # Safety analysis if present
        if r.get("safety"):
            safety = r["safety"]
            lines.extend(["", "**Safety Analysis:**"])
            if safety.get("fmea"):
                fmea = safety["fmea"]
                max_rpn = max((e.get("rpn", 0) for e in fmea.get("entries", [])), default=0)
                lines.append(f"- FMEA: {len(fmea.get('entries', []))} failure modes analyzed, max RPN={max_rpn}")
            if safety.get("asil"):
                lines.append(f"- ASIL Classification: **{safety['asil'].get('asil', '?')}**")
            if safety.get("sil"):
                lines.append(f"- SIL Classification: **SIL {safety['sil'].get('sil', '?')}**")
            if safety.get("iec62304"):
                lines.append(f"- IEC 62304 Safety Class: **{safety['iec62304'].get('safety_class', '?')}**")

        lines.extend(["", "---", ""])

    return lines


def _generate_cross_domain(results):
    """Cross-domain analysis."""
    lines = [
        "## Cross-Domain Analysis",
        "",
        "### Key Findings",
        "",
    ]

    # Agent counts by domain
    agent_counts = {}
    for r in results:
        d = r["domain"]
        agent_counts.setdefault(d, []).append(r["orchestrator"]["agent_count"])

    # Regulated vs non-regulated
    strict_domains = [r for r in results if r["orchestrator"]["domain_rules"]["hitl_level"] == "strict"]
    standard_domains = [r for r in results if r["orchestrator"]["domain_rules"]["hitl_level"] == "standard"]

    strict_avg = sum(r["orchestrator"]["agent_count"] for r in strict_domains) / len(strict_domains) if strict_domains else 0
    standard_avg = sum(r["orchestrator"]["agent_count"] for r in standard_domains) / len(standard_domains) if standard_domains else 0

    lines.extend([
        f"1. **Regulated domains** (strict HITL) average **{strict_avg:.0f} agents** per build ({len(strict_domains)} solutions)",
        f"2. **Non-regulated domains** (standard HITL) average **{standard_avg:.0f} agents** per build ({len(standard_domains)} solutions)",
        f"3. **Total unique agent roles** activated across all 100 builds: {len(set(a for r in results for a in r['orchestrator']['agents_activated']))}",
        f"4. **Safety analysis** performed for {sum(1 for r in results if r.get('safety'))} solutions (medtech, automotive, IoT)",
        f"5. **Regulatory standards** detected: {len(set(s for r in results for s in r['se']['standards']))} unique standards",
        "",
        "---",
        "",
    ])
    return lines


def _generate_agent_heatmap(results):
    """Agent activation heatmap across domains."""
    domains = sorted(set(r["domain"] for r in results))
    all_agents = sorted(set(a for r in results for a in r["orchestrator"]["agents_activated"]))

    # Count activations per domain
    heatmap = {a: {d: 0 for d in domains} for a in all_agents}
    for r in results:
        d = r["domain"]
        for a in r["orchestrator"]["agents_activated"]:
            heatmap[a][d] += 1

    lines = [
        "## Agent Activation Heatmap",
        "",
        "| Agent | " + " | ".join(d[:4].title() for d in domains) + " | Total |",
        "|-------|" + "|".join("---:" for _ in domains) + "|------:|",
    ]

    for agent in all_agents:
        counts = [heatmap[agent][d] for d in domains]
        total = sum(counts)
        cells = [str(c) if c > 0 else "—" for c in counts]
        lines.append(f"| `{agent}` | " + " | ".join(cells) + f" | **{total}** |")

    lines.extend(["", "---", ""])
    return lines


def _generate_regulatory_table(results):
    """Regulatory standards coverage."""
    all_standards = {}
    for r in results:
        for s in r["se"]["standards"]:
            all_standards.setdefault(s, set()).add(r["domain"])

    lines = [
        "## Regulatory Standards Coverage",
        "",
        "| Standard | Domains | Solution Count |",
        "|----------|---------|---------------|",
    ]

    for std in sorted(all_standards):
        domains = sorted(all_standards[std])
        count = sum(1 for r in results if std in r["se"]["standards"])
        lines.append(f"| **{std}** | {', '.join(domains)} | {count} |")

    lines.extend(["", "---", ""])
    return lines


def _generate_safety_summary(results):
    """Safety analysis summary for regulated domains."""
    safety_results = [(r["sol"], r["safety"]) for r in results if r.get("safety")]
    if not safety_results:
        return []

    lines = [
        "## Safety Analysis Summary",
        "",
        "| ID | Solution | Domain | FMEA Entries | Max RPN | ASIL | SIL | IEC 62304 Class |",
        "|-----|---------|--------|-------------|---------|------|-----|----------------|",
    ]

    for sol, safety in safety_results:
        fmea_count = len(safety.get("fmea", {}).get("entries", []))
        max_rpn = max((e.get("rpn", 0) for e in safety.get("fmea", {}).get("entries", [])), default=0)
        asil = safety.get("asil", {}).get("asil", "—") if safety.get("asil") else "—"
        sil = safety.get("sil", {}).get("sil", "—") if safety.get("sil") else "—"
        iec = safety.get("iec62304", {}).get("safety_class", "—") if safety.get("iec62304") else "—"
        lines.append(
            f"| {sol['id']} | {sol['name'].replace('_', ' ').title()} | {sol['domain']} | "
            f"{fmea_count} | {max_rpn} | {asil} | {sil} | {iec} |"
        )

    lines.extend(["", "---", ""])
    return lines


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="SAGE 100-Solution Build Experiment")
    parser.add_argument("--domain", help="Run only this domain")
    parser.add_argument("--id", help="Run only this solution ID")
    parser.add_argument("--output", default=OUTPUT, help="Output report path")
    args = parser.parse_args()

    registry = load_registry(domain_filter=args.domain, id_filter=args.id)
    logger.info("Running %d solutions", len(registry))

    results = []
    for i, sol in enumerate(registry, 1):
        logger.info("[%d/%d] %s — %s (%s)", i, len(registry), sol["id"], sol["name"], sol["domain"])
        start = time.time()

        # Full pipeline
        po_result = simulate_po(sol)
        se_result = simulate_se(sol, po_result)
        orch_result = simulate_orchestrator(sol, po_result, se_result)
        safety_result = simulate_safety(sol, se_result)

        elapsed = time.time() - start
        results.append({
            "sol": sol,
            "domain": sol["domain"],
            "po": po_result,
            "se": se_result,
            "orchestrator": orch_result,
            "safety": safety_result,
            "elapsed_s": round(elapsed, 2),
        })
        logger.info("  → %d agents, %d tasks, %d standards (%.1fs)",
                     orch_result["agent_count"], orch_result["task_count"],
                     len(se_result["standards"]), elapsed)

    generate_report(results, args.output)
    logger.info("Done. %d solutions processed.", len(results))


if __name__ == "__main__":
    main()

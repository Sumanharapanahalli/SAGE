"""
SAGE Framework — Build Orchestrator
=====================================
The brain of the 0→1→N pipeline. Decomposes a product description into
parallel agent tasks, executes them through a 3-tier isolation cascade
(OpenShell → SandboxRunner → OpenSWE), and gates every critical step
behind human approval + critic review.

Design Patterns Applied (ref: Google Cloud Agentic AI Architecture):
  - ReAct (Reason and Act): the primary execution pattern — each agent task
    uses Thought→Action→Observation loops for self-correcting code generation
  - Hierarchical Task Decomposition: multi-level task tree, not flat list
  - Multi-Agent Coordinator: dynamic routing to specialist agents per task type
  - Review and Critique (actor-critic): bounded loop with acceptance criteria
  - Multi-Agent Parallel: wave-based execution of independent tasks
  - Human-in-the-Loop: configurable approval granularity per solution
  - Custom Logic: composition of all above patterns into a single workflow

Pipeline (ReAct at every level):
  THINK: decompose (hierarchical) → ACT: critic reviews plan → OBSERVE: score
  → [HITL: approve plan]
  → THINK: scaffold → ACT: execute agents (ReAct loops per task, wave parallel)
  → OBSERVE: critic reviews code → [HITL if strict]
  → ACT: integrate → OBSERVE: critic reviews integration
  → [HITL: approve build] → finalize

Singleton: build_orchestrator = BuildOrchestrator()
"""

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("BuildOrchestrator")


# ---------------------------------------------------------------------------
# Adaptive Agent Router — Q-Learning inspired (ruflo pattern)
# ---------------------------------------------------------------------------

class AdaptiveRouter:
    """Q-Learning inspired agent router. Learns which agent handles which task best.

    Starts with the static TASK_TYPE_TO_AGENT mapping as defaults. Tracks
    success/failure rates per (task_type, agent_role) pair. When routing, picks
    the agent with the highest success rate for that task type. Falls back to
    default mapping for cold-start. Stores routing history in memory so it
    compounds across builds.
    """

    # Minimum observations before we trust learned scores over defaults
    MIN_OBSERVATIONS = 3
    # Learning rate for exponential moving average
    LEARNING_RATE = 0.3

    def __init__(self):
        self._scores: dict[str, dict[str, float]] = {}   # task_type -> {agent_role: score}
        self._counts: dict[str, dict[str, int]] = {}     # task_type -> {agent_role: count}
        self._lock = threading.Lock()

    def route(self, task_type: str) -> str:
        """Pick best agent for task_type based on learned scores.

        Returns the agent_role with the highest score for the given task_type.
        Falls back to the static TASK_TYPE_TO_AGENT mapping when there are
        insufficient observations.
        """
        default = TASK_TYPE_TO_AGENT.get(task_type, "developer")

        with self._lock:
            if task_type not in self._scores:
                return default

            type_scores = self._scores[task_type]
            type_counts = self._counts.get(task_type, {})

            # Only trust scores with enough observations
            candidates = {
                role: score
                for role, score in type_scores.items()
                if type_counts.get(role, 0) >= self.MIN_OBSERVATIONS
            }

            if not candidates:
                return default

            best_role = max(candidates, key=candidates.get)
            # Only override default if the learned score is meaningfully better
            default_score = candidates.get(default, 0.0)
            if candidates[best_role] > default_score:
                return best_role
            return default

    def record(self, task_type: str, agent_role: str, success: bool, quality_score: float = 0.0):
        """Update routing scores after task completion.

        Uses an exponential moving average so recent results are weighted
        more heavily, allowing the router to adapt to changing conditions.

        Args:
            task_type: The BUILD_TASK_TYPE that was executed.
            agent_role: The agent that handled the task.
            success: Whether the task completed successfully.
            quality_score: Optional quality score (0.0-1.0) from critic or other evaluator.
        """
        # Combine success flag and quality into a single reward signal
        reward = (1.0 if success else 0.0) * 0.5 + min(max(quality_score, 0.0), 1.0) * 0.5

        with self._lock:
            if task_type not in self._scores:
                self._scores[task_type] = {}
                self._counts[task_type] = {}

            old_score = self._scores[task_type].get(agent_role, 0.5)
            count = self._counts[task_type].get(agent_role, 0)

            # Exponential moving average
            new_score = old_score + self.LEARNING_RATE * (reward - old_score)
            self._scores[task_type][agent_role] = new_score
            self._counts[task_type][agent_role] = count + 1

    def get_stats(self) -> dict:
        """Return routing statistics for observability."""
        with self._lock:
            return {
                "scores": {k: dict(v) for k, v in self._scores.items()},
                "counts": {k: dict(v) for k, v in self._counts.items()},
            }


# Module-level adaptive router singleton — compounds across builds
adaptive_router = AdaptiveRouter()

# ---------------------------------------------------------------------------
# Build-specific task types for the planner — hierarchical decomposition
# Each type maps to a specialist agent pattern and carries acceptance criteria.
# ---------------------------------------------------------------------------
BUILD_TASK_TYPES = {
    # --- Software ---
    "BACKEND":   "Build backend service, API endpoints, business logic",
    "FRONTEND":  "Build frontend UI components, pages, routing",
    "TESTS":     "Write unit tests, integration tests, e2e tests",
    "INFRA":     "Infrastructure setup: Docker, CI/CD, deployment configs",
    "DOCS":      "Documentation: README, API docs, architecture docs",
    "DATABASE":  "Database schema, migrations, seed data",
    "API":       "API design, OpenAPI spec, endpoint contracts",
    "CONFIG":    "Configuration files, environment setup, tooling",
    "AGENTIC":   "Design and implement an agentic AI pattern (specify which pattern from the registry)",
    # --- Hardware / Embedded / Mechanical ---
    "FIRMWARE":     "Firmware source code, HAL drivers, RTOS tasks, cross-compilation configs",
    "HARDWARE_SIM": "Hardware simulation models (SPICE, Verilog, VHDL, SystemC), test benches",
    "PCB_DESIGN":   "PCB schematic capture, layout, BOM generation, DRC rules",
    "MECHANICAL":   "CAD models (STEP/STL), tolerance analysis, assembly instructions",
    "SAFETY":       "Safety analysis: FMEA, fault trees, hazard analysis (ISO 26262 / ISO 14971)",
    "COMPLIANCE":   "Regulatory compliance artifacts: DHF, risk matrix, traceability matrix, V&V protocols",
    "EMBEDDED_TEST": "Hardware-in-the-loop (HIL) test specs, firmware unit tests, integration test harnesses",
    # --- Quality & Testing ---
    "QA":           "Quality assurance test planning, test case design, test execution reports",
    "SYSTEM_TEST":  "System-level integration testing, end-to-end test suites, performance testing",
    # --- Business & Strategy ---
    "BUSINESS_ANALYSIS": "Business requirements, user stories, process flows, ROI analysis",
    "MARKET_RESEARCH":   "Market analysis, competitor research, positioning, go-to-market strategy",
    "FINANCIAL":         "Financial model, pricing strategy, cost analysis, budget planning",
    "PRODUCT_MGMT":      "Product requirements doc, roadmap, prioritization, success metrics",
    # --- Regulatory & Legal ---
    "REGULATORY":   "Regulatory submission artifacts, audit preparation, standards mapping",
    "LEGAL":        "Terms of service, privacy policy, licensing, IP review",
    # --- Design & UX ---
    "UX_DESIGN":    "User research, wireframes, interaction design, accessibility audit",
    # --- Infrastructure & Operations ---
    "DEVOPS":       "CI/CD pipelines, monitoring setup, alerting, SRE runbooks",
    "OPERATIONS":   "Operational runbooks, SLA definitions, incident response, capacity planning",
    # --- Content & Localization ---
    "TRAINING":       "User guides, training materials, onboarding docs, video scripts",
    "LOCALIZATION":   "i18n/l10n setup, translation configs, locale-specific content",
    # --- Cross-Cutting ---
    "SECURITY":  "Security review, threat model, penetration test plan, SBOM",
    "DATA":      "Data pipeline, ETL jobs, data model, analytics schema",
    "ML_MODEL":  "ML model training pipeline, evaluation, deployment artifacts",
}

# ---------------------------------------------------------------------------
# Agent Coordinator: maps task types to specialist agent roles
# (Multi-Agent Coordinator pattern — dynamic routing, not hardcoded dispatch)
# Falls back to OpenSWE/LLM for any type not mapped here.
# ---------------------------------------------------------------------------
TASK_TYPE_TO_AGENT = {
    # Software
    "BACKEND":  "developer",
    "FRONTEND": "developer",
    "DATABASE": "developer",
    "API":      "developer",
    "TESTS":    "developer",
    "INFRA":    "developer",
    "DOCS":     "developer",
    "CONFIG":   "developer",
    "AGENTIC":  "developer",
    # Hardware / Embedded / Mechanical
    "FIRMWARE":      "firmware_engineer",
    "HARDWARE_SIM":  "hardware_sim_engineer",
    "PCB_DESIGN":    "pcb_designer",
    "MECHANICAL":    "developer",    # mechanical engineer role if defined
    "SAFETY":        "analyst",      # safety officer role if defined
    "COMPLIANCE":    "analyst",      # compliance officer role if defined
    "EMBEDDED_TEST": "embedded_tester",
    # Quality & Testing
    "QA":           "qa_engineer",
    "SYSTEM_TEST":  "system_tester",
    # Business & Strategy
    "BUSINESS_ANALYSIS": "business_analyst",
    "MARKET_RESEARCH":   "marketing_strategist",
    "FINANCIAL":         "financial_analyst",
    "PRODUCT_MGMT":      "product_manager",
    # Regulatory & Legal
    "REGULATORY":   "regulatory_specialist",
    "LEGAL":        "legal_advisor",
    # Design & UX
    "UX_DESIGN":    "ux_designer",
    # Infrastructure & Operations
    "DEVOPS":       "devops_engineer",
    "OPERATIONS":   "operations_manager",
    # Content & Localization
    "TRAINING":       "technical_writer",
    "LOCALIZATION":   "localization_engineer",
    # Cross-cutting
    "SECURITY":  "analyst",
    "DATA":      "data_scientist",
    "ML_MODEL":  "data_scientist",
    # Solution-defined roles (from prompts.yaml) can extend this at runtime.
}

# ---------------------------------------------------------------------------
# Agent Workforce Registry — functional team groupings (CAMEL + OWL pattern)
# Used by _build_agent_context() for organized team presentation to planner.
# ---------------------------------------------------------------------------
WORKFORCE_REGISTRY = {
    "engineering": {
        "lead": "developer",
        "members": ["qa_engineer", "system_tester", "devops_engineer", "localization_engineer",
                     "data_engineer", "agentic_engineer"],
        "capabilities": ["code generation", "testing", "deployment", "i18n",
                         "data pipelines", "agent frameworks"],
    },
    "analysis": {
        "lead": "analyst",
        "members": ["business_analyst", "financial_analyst", "data_scientist",
                     "ml_engineer", "gen_ai_engineer"],
        "capabilities": ["data analysis", "business modeling", "market research",
                         "MLOps", "LLM applications", "RAG pipelines"],
    },
    "design": {
        "lead": "ux_designer",
        "members": ["product_manager"],
        "capabilities": ["user research", "wireframes", "product strategy"],
    },
    "compliance": {
        "lead": "regulatory_specialist",
        "members": ["legal_advisor", "safety_engineer"],
        "capabilities": ["regulatory submissions", "safety analysis", "legal review"],
    },
    "operations": {
        "lead": "operations_manager",
        "members": ["technical_writer", "marketing_strategist"],
        "capabilities": ["runbooks", "documentation", "go-to-market"],
    },
    "hardware": {
        "lead": "firmware_engineer",
        "members": ["pcb_designer", "embedded_tester", "hardware_sim_engineer"],
        "capabilities": ["firmware development", "PCB design", "HIL testing", "hardware simulation"],
    },
    "quality": {
        "lead": "qa_engineer",
        "members": ["system_tester", "ux_designer"],
        "capabilities": ["browser testing", "QA automation", "accessibility auditing",
                         "visual regression", "performance benchmarking", "security scanning"],
    },
}

# ---------------------------------------------------------------------------
# Artifact Type Registry — output expectations per task type
# Teaches the system what kind of output each task should produce,
# enabling type-aware validation, file extension checks, and
# domain-specific tooling hints.
# ---------------------------------------------------------------------------
ARTIFACT_TYPES = {
    # Code artifacts
    "BACKEND":       {"category": "code", "extensions": [".py", ".go", ".rs", ".java", ".ts", ".js"], "validator": "syntax"},
    "FRONTEND":      {"category": "code", "extensions": [".tsx", ".jsx", ".vue", ".svelte", ".html", ".css"], "validator": "syntax"},
    "API":           {"category": "code", "extensions": [".py", ".ts", ".yaml", ".json"], "validator": "openapi"},
    "DATABASE":      {"category": "code", "extensions": [".sql", ".py", ".prisma"], "validator": "syntax"},
    "TESTS":         {"category": "code", "extensions": [".py", ".ts", ".js", ".spec"], "validator": "syntax"},
    "ML_MODEL":      {"category": "code", "extensions": [".py", ".ipynb", ".yaml"], "validator": "syntax"},
    "DATA":          {"category": "code", "extensions": [".py", ".sql", ".yaml"], "validator": "syntax"},
    "AGENTIC":       {"category": "code", "extensions": [".py", ".ts"], "validator": "syntax"},
    "SECURITY":      {"category": "code", "extensions": [".py", ".yaml", ".json"], "validator": "syntax"},
    # Hardware/firmware artifacts
    "FIRMWARE":      {"category": "hardware", "extensions": [".c", ".h", ".cpp", ".ld", ".cmake"], "validator": "syntax",
                      "mcp_tools": ["kicad", "openocd", "gcc-arm"]},
    "PCB_DESIGN":    {"category": "hardware", "extensions": [".kicad_pcb", ".kicad_sch", ".gbr", ".drl"], "validator": "gerber",
                      "mcp_tools": ["kicad", "drc_checker"]},
    "EMBEDDED_TEST": {"category": "hardware", "extensions": [".c", ".py", ".robot"], "validator": "syntax",
                      "mcp_tools": ["openocd", "gdb"]},
    "MECHANICAL":    {"category": "hardware", "extensions": [".step", ".stl", ".dxf"], "validator": "cad",
                      "mcp_tools": ["freecad", "openscad"]},
    # Infrastructure artifacts
    "INFRA":         {"category": "infra", "extensions": [".tf", ".yaml", ".yml", ".Dockerfile"], "validator": "syntax"},
    "DEVOPS":        {"category": "infra", "extensions": [".yaml", ".yml", ".sh", ".Dockerfile"], "validator": "syntax"},
    "CONFIG":        {"category": "infra", "extensions": [".yaml", ".yml", ".toml", ".json", ".env"], "validator": "syntax"},
    # Document artifacts
    "DOCS":          {"category": "document", "extensions": [".md", ".rst", ".txt"], "validator": "prose"},
    "COMPLIANCE":    {"category": "document", "extensions": [".md", ".pdf", ".docx"], "validator": "prose"},
    "REGULATORY":    {"category": "document", "extensions": [".md", ".pdf", ".docx"], "validator": "prose"},
    "LEGAL":         {"category": "document", "extensions": [".md", ".pdf", ".docx"], "validator": "prose"},
    "SAFETY":        {"category": "document", "extensions": [".md", ".xlsx", ".pdf"], "validator": "prose"},
    # Design artifacts
    "UX_DESIGN":     {"category": "design", "extensions": [".fig", ".sketch", ".html", ".md"], "validator": "prose"},
    # Business artifacts
    "BUSINESS":      {"category": "document", "extensions": [".md", ".xlsx", ".pptx"], "validator": "prose"},
    "MARKETING":     {"category": "document", "extensions": [".md", ".html"], "validator": "prose"},
    "PRODUCT":       {"category": "document", "extensions": [".md", ".yaml"], "validator": "prose"},
    "OPERATIONS":    {"category": "document", "extensions": [".md", ".yaml"], "validator": "prose"},
    "LOCALIZATION":  {"category": "code", "extensions": [".json", ".yaml", ".po", ".xliff"], "validator": "syntax"},
    # QA/Browser artifacts
    "BROWSER_QA":    {"category": "qa", "extensions": [".json", ".png", ".md"], "validator": "prose"},
    "BROWSER_A11Y":  {"category": "qa", "extensions": [".json", ".md"], "validator": "prose"},
    "BROWSER_PERF":  {"category": "qa", "extensions": [".json", ".md"], "validator": "prose"},
    "SECURITY_AUDIT":{"category": "qa", "extensions": [".json", ".md"], "validator": "prose"},
}

# ---------------------------------------------------------------------------
# Agent Roles Registry — skills, tools, MCP servers per role
# Used by "Hire an Agent" flow + _build_agent_context()
# ---------------------------------------------------------------------------
AGENT_ROLES_REGISTRY: dict[str, dict[str, Any]] = {
    # ── Engineering Team ──────────────────────────────────────────────
    "developer": {
        "title": "Software Developer",
        "description": "Code generation, MR creation, code review",
        "team": "engineering",
        "skills": [
            "Full-stack code generation (Python, TypeScript, Go, Rust, Java, C++)",
            "REST API design and implementation",
            "Database schema design (SQL, NoSQL)",
            "Git branching, merge conflict resolution",
            "Code review and refactoring",
            "Dependency management and package selection",
            "Error handling and logging patterns",
            "Unit test writing alongside production code",
        ],
        "tools": ["code_editor", "git", "package_manager", "linter", "formatter", "debugger"],
        "mcp_server": "developer_tools",
        "mcp_capabilities": [
            "file_read", "file_write", "file_search",
            "git_commit", "git_branch", "git_diff",
            "run_tests", "run_linter", "run_formatter",
            "package_install", "package_search",
        ],
        "hire_when": "You need code written, reviewed, or refactored",
    },
    "qa_engineer": {
        "title": "QA Engineer",
        "description": "Test planning, test case design, test execution reports",
        "team": "engineering",
        "skills": [
            "Test strategy and plan design",
            "Unit, integration, and acceptance test case creation",
            "Test coverage analysis and gap identification",
            "Regression test suite maintenance",
            "Bug report writing with reproduction steps",
            "Test data generation and fixtures",
            "Mutation testing and fault injection",
            "Test automation framework setup (pytest, Jest, Cypress)",
        ],
        "tools": ["test_runner", "coverage_analyzer", "bug_tracker", "test_data_generator"],
        "mcp_server": "qa_tools",
        "mcp_capabilities": [
            "run_tests", "coverage_report", "generate_test_data",
            "create_bug_report", "list_test_suites", "mutation_test",
        ],
        "hire_when": "You need test plans, test cases, or quality assurance",
    },
    "system_tester": {
        "title": "System Tester",
        "description": "System-level integration testing, E2E suites, performance testing",
        "team": "engineering",
        "skills": [
            "End-to-end test scenario design",
            "Performance and load testing (k6, Locust, JMeter)",
            "API contract testing",
            "Cross-browser and cross-platform testing",
            "Chaos engineering and resilience testing",
            "Security penetration testing basics",
            "Environment provisioning for test",
            "Test report generation with metrics",
        ],
        "tools": ["e2e_runner", "load_tester", "api_tester", "browser_automation"],
        "mcp_server": "system_test_tools",
        "mcp_capabilities": [
            "run_e2e_tests", "run_load_test", "run_api_contract_test",
            "provision_test_env", "generate_test_report", "run_security_scan",
        ],
        "hire_when": "You need E2E tests, performance benchmarks, or system validation",
    },
    "devops_engineer": {
        "title": "DevOps Engineer",
        "description": "CI/CD pipelines, monitoring, alerting, SRE runbooks",
        "team": "engineering",
        "skills": [
            "CI/CD pipeline design (GitHub Actions, GitLab CI, Jenkins)",
            "Container orchestration (Docker, Kubernetes)",
            "Infrastructure as Code (Terraform, Pulumi, CloudFormation)",
            "Monitoring and alerting (Prometheus, Grafana, Datadog)",
            "Log aggregation (ELK, Loki)",
            "Secret management (Vault, AWS Secrets Manager)",
            "Auto-scaling and capacity planning",
            "Incident response runbooks and SRE practices",
        ],
        "tools": ["docker", "kubernetes", "terraform", "ci_pipeline", "monitoring"],
        "mcp_server": "devops_tools",
        "mcp_capabilities": [
            "deploy_service", "create_pipeline", "provision_infra",
            "configure_monitoring", "manage_secrets", "scale_service",
            "create_runbook", "check_service_health",
        ],
        "hire_when": "You need deployment pipelines, infrastructure, or monitoring",
    },
    "localization_engineer": {
        "title": "Localization Engineer",
        "description": "i18n/l10n setup, translation configs, locale content",
        "team": "engineering",
        "skills": [
            "i18n framework setup (react-intl, i18next, gettext)",
            "String extraction and translation key management",
            "RTL layout support",
            "Date, number, and currency formatting per locale",
            "Translation memory and glossary management",
            "Locale-specific testing and QA",
            "Content adaptation for cultural context",
            "Translation workflow automation",
        ],
        "tools": ["i18n_extractor", "translation_manager", "locale_tester"],
        "mcp_server": "localization_tools",
        "mcp_capabilities": [
            "extract_strings", "manage_translations", "validate_locale",
            "format_dates_numbers", "check_rtl_layout", "import_translations",
        ],
        "hire_when": "You need multi-language support or localization",
    },

    # ── Analysis Team ─────────────────────────────────────────────────
    "analyst": {
        "title": "Technical Analyst",
        "description": "Log analysis, error triage, root cause analysis",
        "team": "analysis",
        "skills": [
            "Log pattern analysis and anomaly detection",
            "Error triage and severity classification",
            "Root cause analysis (5-whys, fishbone)",
            "Metrics analysis and trend identification",
            "Incident post-mortem writing",
            "System dependency mapping",
            "Performance bottleneck identification",
            "Alerting threshold tuning",
        ],
        "tools": ["log_analyzer", "metrics_dashboard", "trace_viewer", "dependency_mapper"],
        "mcp_server": "analyst_tools",
        "mcp_capabilities": [
            "search_logs", "analyze_metrics", "trace_request",
            "map_dependencies", "identify_anomalies", "generate_postmortem",
        ],
        "hire_when": "You need error analysis, log investigation, or root cause diagnosis",
    },
    "business_analyst": {
        "title": "Business Analyst",
        "description": "Business requirements, user stories, process flows, ROI analysis",
        "team": "analysis",
        "skills": [
            "Requirements elicitation and documentation",
            "User story writing (Given-When-Then, INVEST)",
            "Business process modeling (BPMN)",
            "Stakeholder analysis and communication planning",
            "ROI and cost-benefit analysis",
            "Gap analysis (current vs. desired state)",
            "Acceptance criteria definition",
            "Competitive analysis and market positioning",
        ],
        "tools": ["requirements_editor", "process_modeler", "spreadsheet", "survey_builder"],
        "mcp_server": "business_analysis_tools",
        "mcp_capabilities": [
            "create_user_story", "model_process", "analyze_roi",
            "generate_requirements_doc", "create_stakeholder_map",
            "define_acceptance_criteria",
        ],
        "hire_when": "You need requirements, user stories, or business process analysis",
    },
    "financial_analyst": {
        "title": "Financial Analyst",
        "description": "Financial models, pricing strategy, cost analysis, budgets",
        "team": "analysis",
        "skills": [
            "Financial modeling (DCF, NPV, IRR)",
            "Pricing strategy design (freemium, tiered, usage-based)",
            "Cost structure analysis and optimization",
            "Budget forecasting and variance analysis",
            "Unit economics (CAC, LTV, payback period)",
            "Revenue projection and scenario planning",
            "Funding round preparation and cap table modeling",
            "Financial reporting and KPI dashboards",
        ],
        "tools": ["spreadsheet", "financial_model", "chart_builder", "data_query"],
        "mcp_server": "financial_tools",
        "mcp_capabilities": [
            "build_financial_model", "calculate_unit_economics",
            "project_revenue", "analyze_pricing", "create_budget",
            "generate_financial_report",
        ],
        "hire_when": "You need financial models, pricing, budgets, or investor materials",
    },
    "data_scientist": {
        "title": "Data Scientist",
        "description": "Data pipelines, ML models, analytics, evaluation",
        "team": "analysis",
        "skills": [
            "Data pipeline design (ETL, streaming, batch)",
            "Exploratory data analysis (EDA)",
            "ML model selection, training, and evaluation",
            "Feature engineering and selection",
            "A/B test design and statistical analysis",
            "Data visualization and dashboarding",
            "Model deployment and serving (MLflow, BentoML)",
            "Data quality monitoring and drift detection",
        ],
        "tools": ["jupyter", "pandas", "sklearn", "mlflow", "data_viz", "sql_client"],
        "mcp_server": "data_science_tools",
        "mcp_capabilities": [
            "run_query", "train_model", "evaluate_model",
            "create_visualization", "design_experiment",
            "build_pipeline", "detect_drift",
        ],
        "hire_when": "You need data analysis, ML models, or experiment design",
    },

    # ── Design Team ───────────────────────────────────────────────────
    "ux_designer": {
        "title": "UX Designer",
        "description": "User research, wireframes, interaction design, accessibility",
        "team": "design",
        "skills": [
            "User research (interviews, surveys, personas)",
            "Wireframing and prototyping",
            "Interaction design and user flows",
            "Design system creation and maintenance",
            "Accessibility compliance (WCAG 2.1 AA)",
            "Usability testing and heuristic evaluation",
            "Information architecture",
            "Responsive design patterns",
        ],
        "tools": ["figma", "wireframe_tool", "prototype_builder", "accessibility_checker"],
        "mcp_server": "ux_design_tools",
        "mcp_capabilities": [
            "create_wireframe", "build_prototype", "run_usability_test",
            "check_accessibility", "generate_design_tokens",
            "create_user_flow",
        ],
        "hire_when": "You need UI design, wireframes, user research, or accessibility review",
    },
    "product_manager": {
        "title": "Product Manager",
        "description": "Product requirements, roadmap, prioritization, success metrics",
        "team": "design",
        "skills": [
            "Product requirements document (PRD) writing",
            "Roadmap planning and prioritization (RICE, MoSCoW)",
            "Success metrics and OKR definition",
            "User journey mapping",
            "Feature prioritization and trade-off analysis",
            "Go/no-go decision frameworks",
            "Sprint planning and backlog grooming",
            "Product analytics interpretation",
        ],
        "tools": ["roadmap_builder", "analytics_dashboard", "survey_builder", "task_tracker"],
        "mcp_server": "product_mgmt_tools",
        "mcp_capabilities": [
            "create_prd", "build_roadmap", "define_okrs",
            "prioritize_features", "analyze_user_metrics",
            "create_sprint_plan",
        ],
        "hire_when": "You need product strategy, roadmaps, PRDs, or prioritization",
    },

    # ── Compliance Team ───────────────────────────────────────────────
    "regulatory_specialist": {
        "title": "Regulatory Specialist",
        "description": "Regulatory submissions, audit prep, standards mapping",
        "team": "compliance",
        "skills": [
            "Regulatory standard mapping (ISO, IEC, FDA, CE, FCC)",
            "Design History File (DHF) compilation",
            "Risk management (ISO 14971, FMEA)",
            "510(k) / CE technical file preparation",
            "Audit readiness assessment and checklist creation",
            "Traceability matrix (requirements ↔ tests ↔ risks)",
            "SOUP/OTS software classification",
            "Post-market surveillance planning",
        ],
        "tools": ["compliance_checker", "traceability_matrix", "risk_register", "audit_tool"],
        "mcp_server": "regulatory_tools",
        "mcp_capabilities": [
            "check_compliance", "build_traceability_matrix",
            "create_risk_register", "generate_dhf",
            "map_standards", "prepare_submission",
        ],
        "hire_when": "You need regulatory compliance, audit prep, or standards mapping",
    },
    "legal_advisor": {
        "title": "Legal Advisor",
        "description": "Terms of service, privacy policy, licensing, IP review",
        "team": "compliance",
        "skills": [
            "Terms of Service and Privacy Policy drafting",
            "Open-source license compliance (GPL, MIT, Apache)",
            "Data protection assessment (GDPR, CCPA, HIPAA)",
            "Intellectual property review and patent landscape",
            "Contract review and vendor agreement analysis",
            "Employment law basics for hiring",
            "Regulatory filing and notification requirements",
            "Liability and indemnification clause review",
        ],
        "tools": ["license_scanner", "policy_generator", "contract_analyzer", "legal_db"],
        "mcp_server": "legal_tools",
        "mcp_capabilities": [
            "scan_licenses", "generate_privacy_policy",
            "generate_terms_of_service", "check_gdpr_compliance",
            "review_contract", "assess_ip_risk",
        ],
        "hire_when": "You need legal documents, license compliance, or privacy policies",
    },
    "safety_engineer": {
        "title": "Safety Engineer",
        "description": "FMEA, fault trees, hazard analysis (ISO 26262 / ISO 14971)",
        "team": "compliance",
        "skills": [
            "FMEA (Failure Mode and Effects Analysis)",
            "FTA (Fault Tree Analysis)",
            "Hazard analysis and risk assessment",
            "Safety Integrity Level (SIL) / ASIL classification",
            "Safety case construction (GSN)",
            "Functional safety standard compliance (IEC 61508, ISO 26262, DO-178C)",
            "Safety validation and verification planning",
            "Incident investigation and corrective action",
        ],
        "tools": ["fmea_tool", "fault_tree_builder", "risk_matrix", "safety_case_editor"],
        "mcp_server": "safety_tools",
        "mcp_capabilities": [
            "create_fmea", "build_fault_tree", "assess_risk",
            "classify_sil_asil", "generate_safety_case",
            "plan_safety_validation",
        ],
        "hire_when": "You need safety analysis, FMEA, fault trees, or hazard assessment",
    },

    # ── Operations Team ───────────────────────────────────────────────
    "operations_manager": {
        "title": "Operations Manager",
        "description": "Operational runbooks, SLA definitions, incident response, capacity",
        "team": "operations",
        "skills": [
            "Operational runbook creation",
            "SLA/SLO/SLI definition and tracking",
            "Incident response playbook design",
            "Capacity planning and scaling strategy",
            "Vendor management and procurement",
            "On-call rotation and escalation policy",
            "Change management process design",
            "Operational cost optimization",
        ],
        "tools": ["runbook_editor", "incident_tracker", "capacity_planner", "vendor_manager"],
        "mcp_server": "operations_tools",
        "mcp_capabilities": [
            "create_runbook", "define_sla", "create_incident_playbook",
            "plan_capacity", "track_incidents", "manage_on_call",
        ],
        "hire_when": "You need runbooks, SLAs, incident response, or capacity planning",
    },
    "technical_writer": {
        "title": "Technical Writer",
        "description": "User guides, training materials, onboarding docs, video scripts",
        "team": "operations",
        "skills": [
            "User guide and manual writing",
            "API documentation (OpenAPI, Swagger)",
            "Tutorial and quickstart creation",
            "Release notes and changelog writing",
            "Video script and storyboard creation",
            "Knowledge base article writing",
            "Onboarding documentation and walkthrough design",
            "Style guide creation and enforcement",
        ],
        "tools": ["doc_editor", "diagram_builder", "screenshot_tool", "api_doc_generator"],
        "mcp_server": "documentation_tools",
        "mcp_capabilities": [
            "create_user_guide", "generate_api_docs",
            "create_tutorial", "write_release_notes",
            "build_knowledge_base", "create_video_script",
        ],
        "hire_when": "You need documentation, tutorials, API docs, or training materials",
    },
    "marketing_strategist": {
        "title": "Marketing Strategist",
        "description": "Market analysis, competitor research, positioning, GTM strategy",
        "team": "operations",
        "skills": [
            "Market analysis and TAM/SAM/SOM estimation",
            "Competitor analysis and differentiation mapping",
            "Brand positioning and messaging framework",
            "Go-to-market strategy and launch planning",
            "Content marketing strategy (blog, social, email)",
            "SEO and SEM keyword strategy",
            "Customer segmentation and persona development",
            "Campaign planning and performance tracking",
        ],
        "tools": ["market_research", "seo_analyzer", "content_calendar", "analytics"],
        "mcp_server": "marketing_tools",
        "mcp_capabilities": [
            "analyze_market", "research_competitors",
            "create_positioning", "plan_gtm_strategy",
            "generate_content_plan", "analyze_seo",
        ],
        "hire_when": "You need market research, GTM strategy, or marketing plans",
    },

    # ── Hardware Team ──────────────────────────────────────────────────
    "firmware_engineer": {
        "title": "Firmware Engineer",
        "description": "Embedded firmware, RTOS, HAL drivers, cross-compilation",
        "team": "hardware",
        "skills": [
            "Embedded C/C++ firmware development",
            "RTOS programming (FreeRTOS, Zephyr, ThreadX)",
            "Hardware Abstraction Layer (HAL) driver development",
            "Cross-compilation (GCC-ARM, IAR, Keil)",
            "Peripheral integration (SPI, I2C, UART, CAN, USB)",
            "Bootloader and OTA update implementation",
            "Power management and sleep mode optimization",
            "Interrupt handling and real-time constraints",
        ],
        "tools": ["gcc-arm", "openocd", "gdb", "jlink", "make", "cmake"],
        "mcp_server": "firmware_tools",
        "mcp_capabilities": [
            "compile_firmware", "flash_device", "debug_firmware",
            "analyze_binary", "read_registers", "run_unit_tests",
        ],
        "docker_image": "sage/firmware-toolchain:latest",
        "docker_packages": ["gcc-arm-none-eabi", "openocd", "cmake", "ninja-build", "gdb-multiarch"],
        "hire_when": "You need embedded firmware, RTOS tasks, or hardware driver development",
    },
    "pcb_designer": {
        "title": "PCB Designer",
        "description": "Schematic capture, PCB layout, BOM generation, DRC",
        "team": "hardware",
        "skills": [
            "Schematic capture and symbol creation (KiCad)",
            "PCB layout and routing (2-layer to 12-layer)",
            "Design Rule Check (DRC) and ERC validation",
            "BOM generation and component sourcing",
            "Gerber and drill file generation for fabrication",
            "Signal integrity and impedance matching",
            "Thermal analysis and copper pour optimization",
            "Component footprint creation and library management",
        ],
        "tools": ["kicad", "kicad-cli", "gerber_viewer", "bom_manager"],
        "mcp_server": "pcb_tools",
        "mcp_capabilities": [
            "create_schematic", "layout_pcb", "run_drc",
            "generate_gerbers", "generate_bom", "check_erc",
        ],
        "docker_image": "sage/pcb-toolchain:latest",
        "docker_packages": ["kicad", "kicad-cli", "python3-kicad"],
        "hire_when": "You need PCB design, schematic capture, or board layout",
    },
    "embedded_tester": {
        "title": "Embedded Test Engineer",
        "description": "HIL testing, firmware unit tests, hardware integration tests",
        "team": "hardware",
        "skills": [
            "Hardware-in-the-loop (HIL) test design",
            "Firmware unit testing (Unity, CppUTest, Google Test)",
            "Integration test harness development",
            "Serial protocol testing (UART, SPI, I2C)",
            "CAN bus testing and diagnostics",
            "Code coverage analysis for embedded (gcov, lcov)",
            "Automated test fixture design",
            "Compliance test execution (EMC, environmental)",
        ],
        "tools": ["unity_test", "cppcheck", "valgrind", "gcov", "can_analyzer"],
        "mcp_server": "embedded_test_tools",
        "mcp_capabilities": [
            "run_firmware_tests", "analyze_coverage", "test_serial",
            "test_can_bus", "run_static_analysis", "generate_test_report",
        ],
        "docker_image": "sage/embedded-test:latest",
        "docker_packages": ["gcc-arm-none-eabi", "cppcheck", "valgrind", "lcov", "can-utils"],
        "hire_when": "You need firmware testing, HIL tests, or embedded quality assurance",
    },
    "hardware_sim_engineer": {
        "title": "Hardware Simulation Engineer",
        "description": "SPICE simulation, Verilog/VHDL, SystemC modeling",
        "team": "hardware",
        "skills": [
            "SPICE circuit simulation (ngspice, LTspice)",
            "Verilog/VHDL digital design and simulation",
            "SystemC modeling for SoC verification",
            "FPGA synthesis and implementation",
            "Waveform analysis and timing verification",
            "Power analysis and thermal simulation",
            "Design verification and testbench creation",
            "Hardware/software co-simulation",
        ],
        "tools": ["ngspice", "iverilog", "gtkwave", "yosys", "verilator"],
        "mcp_server": "hw_sim_tools",
        "mcp_capabilities": [
            "run_spice_sim", "simulate_verilog", "synthesize_fpga",
            "analyze_waveform", "run_power_analysis", "create_testbench",
        ],
        "docker_image": "sage/hw-simulation:latest",
        "docker_packages": ["ngspice", "iverilog", "gtkwave", "yosys", "verilator"],
        "hire_when": "You need circuit simulation, FPGA design, or hardware verification",
    },

    # ── Orchestration Roles (internal, not hireable) ──────────────────
    "planner": {
        "title": "Planner",
        "description": "Task decomposition, dependency analysis",
        "team": "orchestration",
        "skills": ["Hierarchical task decomposition", "Dependency graph analysis", "Wave scheduling"],
        "tools": ["planner_llm"],
        "mcp_server": None,
        "mcp_capabilities": [],
        "hire_when": None,  # internal role
    },
    "monitor": {
        "title": "Monitor",
        "description": "Integration monitoring, health checks",
        "team": "orchestration",
        "skills": ["Service health monitoring", "Integration verification", "Alert management"],
        "tools": ["health_checker"],
        "mcp_server": None,
        "mcp_capabilities": [],
        "hire_when": None,  # internal role
    },
    "critic": {
        "title": "Critic",
        "description": "Adversarial review, quality scoring, compliance checking",
        "team": "orchestration",
        "skills": ["Code review", "Plan review", "Security analysis", "Compliance verification"],
        "tools": ["critic_llm"],
        "mcp_server": None,
        "mcp_capabilities": [],
        "hire_when": None,  # internal role
    },
}

# Backward-compat: flat description dict for _build_agent_context()
_AGENT_DESCRIPTIONS = {
    role: info["description"] for role, info in AGENT_ROLES_REGISTRY.items()
}

def get_hireable_roles() -> list[dict[str, Any]]:
    """Return roles available for 'Hire an Agent' — excludes internal orchestration roles."""
    return [
        {
            "role": role,
            "title": info["title"],
            "description": info["description"],
            "team": info["team"],
            "skills": info["skills"],
            "tools": info["tools"],
            "mcp_server": info["mcp_server"],
            "mcp_capabilities": info["mcp_capabilities"],
            "hire_when": info["hire_when"],
        }
        for role, info in AGENT_ROLES_REGISTRY.items()
        if info.get("hire_when") is not None
    ]

# ---------------------------------------------------------------------------
# HITL Granularity levels — configurable per solution via project.yaml
# (Human-in-the-Loop pattern — regulated domains get more gates)
# ---------------------------------------------------------------------------
HITL_LEVELS = {
    "minimal":   ["plan", "final"],           # 2 gates: plan + final
    "standard":  ["plan", "code", "final"],   # 3 gates: + post-code review
    "strict":    ["plan", "wave", "code", "integration", "final"],  # every stage
}

# ---------------------------------------------------------------------------
# Agentic AI Design Pattern Registry
# (ref: https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system)
#
# The planner uses this registry to select the right architecture pattern
# when the product being built requires agentic AI capabilities.
# This makes the orchestrator "pattern-aware" — it doesn't just build
# conventional software, it builds AI-native systems using proven patterns.
# ---------------------------------------------------------------------------
AGENTIC_PATTERNS = {
    "single_agent": {
        "name": "Single-Agent System",
        "description": "One LLM with tools handles requests end-to-end via ReAct reasoning",
        "when_to_use": [
            "Simple Q&A or task automation",
            "Single-domain chatbot",
            "Tool-augmented assistant",
        ],
        "components": ["LLM", "tool registry", "system prompt", "ReAct loop"],
    },
    "multi_agent_sequential": {
        "name": "Multi-Agent Sequential Pipeline",
        "description": "Agents execute in fixed linear order; output feeds the next",
        "when_to_use": [
            "Data processing pipelines (ETL, enrichment)",
            "Content generation with review stages",
            "Multi-step analysis workflows",
        ],
        "components": ["agent chain", "state passing", "error propagation"],
    },
    "multi_agent_parallel": {
        "name": "Multi-Agent Parallel Execution",
        "description": "Multiple agents run simultaneously; outputs synthesized after",
        "when_to_use": [
            "Independent subtask execution",
            "Parallel data analysis",
            "Multi-source research aggregation",
        ],
        "components": ["wave scheduler", "result aggregator", "dependency graph"],
    },
    "review_and_critique": {
        "name": "Review and Critique (Actor-Critic)",
        "description": "Generator produces output; critic evaluates and loops until quality threshold",
        "when_to_use": [
            "Code generation with quality gates",
            "Content that must meet compliance standards",
            "Any output requiring adversarial validation",
        ],
        "components": ["generator agent", "critic agent", "acceptance criteria", "iteration loop"],
    },
    "coordinator": {
        "name": "Multi-Agent Coordinator",
        "description": "Central coordinator decomposes and routes to specialist agents",
        "when_to_use": [
            "Complex products with diverse components",
            "Systems requiring multiple domain experts",
            "Dynamic task routing based on content",
        ],
        "components": ["coordinator", "specialist agents", "task router", "result merger"],
    },
    "hierarchical_decomposition": {
        "name": "Hierarchical Task Decomposition",
        "description": "Multi-level agent hierarchy: root breaks tasks across levels",
        "when_to_use": [
            "Complex products requiring recursive breakdown",
            "Enterprise systems with nested subsystems",
            "Large-scale code generation projects",
        ],
        "components": ["root planner", "sub-planners", "task tree", "dependency graph"],
    },
    "swarm": {
        "name": "Multi-Agent Swarm",
        "description": "Agents collaborate peer-to-peer through debate and info sharing",
        "when_to_use": [
            "Creative brainstorming",
            "Consensus-building on design decisions",
            "Multi-perspective analysis",
        ],
        "components": ["peer agents", "message bus", "voting/consensus", "shared state"],
    },
    "react": {
        "name": "ReAct (Reason and Act)",
        "description": "Iterative Thought→Action→Observation loop with self-correction",
        "when_to_use": [
            "Tool-using agents that need to adapt",
            "Exploratory tasks with uncertain outcomes",
            "Any agent that should self-verify its work",
        ],
        "components": ["reasoning engine", "action executor", "observation parser", "loop controller"],
    },
    "human_in_the_loop": {
        "name": "Human-in-the-Loop",
        "description": "Agent pauses at checkpoints for human review/approval",
        "when_to_use": [
            "Regulated industries (medical, financial)",
            "High-risk actions (deployments, data changes)",
            "Any system where human judgment is required",
        ],
        "components": ["approval queue", "proposal store", "notification system", "feedback loop"],
    },
    "iterative_refinement": {
        "name": "Iterative Refinement",
        "description": "Agents progressively improve output over cycles until quality threshold",
        "when_to_use": [
            "Content optimization (SEO, copy)",
            "Code optimization (performance, readability)",
            "Design iteration based on feedback",
        ],
        "components": ["refiner agent", "quality scorer", "termination criteria", "history tracker"],
    },
}

# ---------------------------------------------------------------------------
# Domain Detection Rules — maps product keywords to required task types,
# compliance standards, and HITL overrides. This ensures that when someone
# says "build a surgical robot", the planner knows to include FIRMWARE,
# SAFETY, COMPLIANCE, MECHANICAL, and EMBEDDED_TEST tasks — not just
# BACKEND and FRONTEND.
# ---------------------------------------------------------------------------
DOMAIN_RULES = {
    "medical_device": {
        "keywords": ["medical device", "surgical", "implant", "diagnostic", "patient monitor",
                      "clinical", "FDA", "IEC 62304", "ISO 13485", "ISO 14971", "hospital",
                      "wearable health", "pulse oximeter", "infusion pump", "ventilator",
                      "medical imaging", "glucose", "insulin", "rehabilitation", "prosthetic",
                      "Class II", "Class III", "SaMD", "510(k)", "De Novo"],
        "required_types": ["FIRMWARE", "SAFETY", "COMPLIANCE", "EMBEDDED_TEST", "DOCS"],
        "standards": ["IEC 62304", "ISO 13485", "ISO 14971", "FDA 21 CFR Part 820"],
        "hitl_override": "strict",
        "extra_criteria": {
            "FIRMWARE": ["IEC 62304 software class documented", "SOUP components listed"],
            "SAFETY": ["ISO 14971 risk management file complete", "Residual risk acceptable"],
            "COMPLIANCE": ["DHF (Design History File) structure created", "V&V protocol drafted"],
        },
    },
    "automotive": {
        "keywords": ["automotive", "vehicle", "ECU", "CAN bus", "ADAS", "infotainment",
                      "ISO 26262", "AUTOSAR", "OBD", "telematics", "car", "truck",
                      "autonomous driving", "lidar", "radar sensor", "ASIL",
                      "V2X", "electric vehicle", "EV charging", "fleet management",
                      "HMI", "parking", "battery management",
                      "OCPP", "charging station", "charging network"],
        "required_types": ["FIRMWARE", "SAFETY", "COMPLIANCE", "EMBEDDED_TEST", "HARDWARE_SIM"],
        "standards": ["ISO 26262", "AUTOSAR", "UNECE R155/R156"],
        "hitl_override": "strict",
        "extra_criteria": {
            "FIRMWARE": ["AUTOSAR compliance checked", "MISRA C violations zero"],
            "SAFETY": ["ASIL level determined for each function", "Fault tree analysis complete"],
        },
    },
    "avionics": {
        "keywords": ["avionics", "aircraft", "flight", "DO-178C", "DO-254", "aerospace",
                      "satellite", "rocket", "UAV", "drone", "navigation system",
                      "flight controller", "autopilot"],
        "required_types": ["FIRMWARE", "SAFETY", "COMPLIANCE", "EMBEDDED_TEST", "HARDWARE_SIM"],
        "standards": ["DO-178C", "DO-254", "DO-326A", "ARP 4754A"],
        "hitl_override": "strict",
        "extra_criteria": {
            "FIRMWARE": ["DAL level assigned", "MC/DC coverage documented"],
            "SAFETY": ["Functional hazard assessment complete", "Common cause analysis done"],
        },
    },
    "robotics": {
        "keywords": ["robot", "robotic", "actuator", "servo", "motor control", "kinematics",
                      "ROS", "end effector", "manipulator", "cobot", "autonomous"],
        "required_types": ["FIRMWARE", "MECHANICAL", "SAFETY", "EMBEDDED_TEST", "HARDWARE_SIM"],
        "standards": ["ISO 10218", "ISO/TS 15066"],
        "hitl_override": "strict",
        "extra_criteria": {
            "MECHANICAL": ["Joint limits verified", "Payload capacity documented"],
            "SAFETY": ["Collaborative operation zones defined", "Emergency stop tested"],
        },
    },
    "iot": {
        "keywords": ["IoT", "sensor", "gateway", "edge device", "MQTT", "LoRa", "Zigbee",
                      "smart home", "connected device", "embedded sensor", "telemetry",
                      "wearable", "monitoring", "BLE", "Matter", "Z-Wave", "OPC-UA",
                      "smart parking", "cold chain", "agriculture", "energy management"],
        "required_types": ["FIRMWARE", "EMBEDDED_TEST", "SECURITY", "CONFIG"],
        "standards": ["IEC 62443"],
        "hitl_override": "standard",
        "extra_criteria": {
            "FIRMWARE": ["OTA update mechanism implemented", "Watchdog timer configured"],
            "SECURITY": ["Device identity provisioned", "Firmware signing enabled"],
        },
    },
    "fintech": {
        "keywords": ["fintech", "payment", "banking", "trading", "PCI DSS", "SOX",
                      "KYC", "AML", "ledger", "transaction", "wallet", "crypto",
                      "insurance", "loan", "credit", "neobank", "remittance",
                      "accounting", "invoice", "billing", "financial", "pricing",
                      "expense", "investment", "fund", "claims",
                      "portfolio", "robo-advisor", "SEC", "tax-loss"],
        "required_types": ["SECURITY", "COMPLIANCE", "TESTS", "DATABASE"],
        "standards": ["PCI DSS", "SOX", "SOC 2"],
        "hitl_override": "strict",
        "extra_criteria": {
            "SECURITY": ["PCI DSS SAQ completed", "Encryption at rest and in transit"],
            "DATABASE": ["Transaction isolation level documented", "Audit trail on all writes"],
        },
    },
    "hardware_generic": {
        "keywords": ["PCB", "schematic", "circuit", "FPGA", "ASIC", "SoC", "power supply",
                      "antenna", "RF", "analog", "digital design", "signal processing"],
        "required_types": ["PCB_DESIGN", "HARDWARE_SIM", "FIRMWARE", "EMBEDDED_TEST"],
        "standards": [],
        "hitl_override": "standard",
        "extra_criteria": {},
    },
    "ml_ai": {
        "keywords": ["machine learning", "deep learning", "neural network", "training pipeline",
                      "model serving", "MLOps", "computer vision", "NLP", "LLM",
                      "recommendation engine", "classification", "regression",
                      "AI-powered", "OCR", "speech recognition", "chatbot", "RAG",
                      "anomaly detection", "fraud detection", "embedding", "search engine",
                      "translation", "content moderation", "image generation",
                      "ML ", "model training", "feature store", "NER",
                      "voice assistant", "NLU", "TTS", "ASR",
                      "Stable Diffusion", "XGBoost", "neural", "collaborative filtering",
                      "unsupervised", "time-series", "pipeline"],
        "required_types": ["ML_MODEL", "DATA", "TESTS", "INFRA"],
        "standards": [],
        "hitl_override": "standard",
        "extra_criteria": {
            "ML_MODEL": ["Bias evaluation performed", "Model card generated"],
        },
    },
    "saas_product": {
        "keywords": ["SaaS", "subscription", "B2B", "B2C", "marketplace", "platform",
                      "multi-tenant", "recurring revenue", "freemium", "self-service",
                      "helpdesk", "CRM", "project management", "analytics dashboard",
                      "form builder", "scheduling", "email marketing", "API gateway",
                      "collaboration", "ticket", "knowledge base",
                      "HR management", "onboarding", "payroll", "developer portal",
                      "rate limiting", "API key", "no-code",
                      "data source", "chart builder", "dashboard builder"],
        "required_types": ["BUSINESS_ANALYSIS", "FINANCIAL", "LEGAL", "UX_DESIGN",
                           "MARKET_RESEARCH", "PRODUCT_MGMT", "OPERATIONS", "DEVOPS"],
        "standards": ["SOC 2"],
        "hitl_override": "standard",
        "extra_criteria": {
            "BUSINESS_ANALYSIS": ["Pricing tiers defined", "Churn risk factors identified"],
            "FINANCIAL": ["MRR/ARR projections modeled", "CAC and LTV estimated"],
            "LEGAL": ["Subscription terms cover cancellation and refunds", "Data processing agreement drafted"],
        },
    },
    "consumer_app": {
        "keywords": ["mobile app", "consumer", "social", "game", "entertainment",
                      "iOS", "Android", "app store", "play store", "casual game",
                      "food delivery", "dating", "travel", "meditation", "fitness",
                      "recipe", "pet care", "event", "habit", "podcast", "streaming",
                      "booking", "tracking app", "community",
                      "restaurant", "discovery", "ticketing", "listening",
                      "mindfulness", "sleep", "guided sessions",
                      "delivery app", "hosting",
                      "matching algorithm", "profile", "chat"],
        "required_types": ["UX_DESIGN", "MARKET_RESEARCH", "LOCALIZATION", "TRAINING",
                           "QA", "PRODUCT_MGMT"],
        "standards": [],
        "hitl_override": "standard",
        "extra_criteria": {
            "UX_DESIGN": ["App store screenshot mockups prepared", "Onboarding flow under 3 steps"],
            "LOCALIZATION": ["Top 5 target locales identified", "Store listing translated"],
        },
    },
    "enterprise": {
        "keywords": ["enterprise", "ERP", "CRM", "B2B", "procurement", "workflow automation",
                      "back-office", "supply chain", "HR system", "asset management",
                      "IAM", "SSO", "SAML", "SCIM", "data warehouse", "compliance",
                      "contract management", "knowledge management", "visitor management",
                      "GRC", "governance", "ISO 27001", "SOC 2",
                      "ETL", "data catalog", "lineage", "e-signature",
                      "clause extraction", "obligation tracking"],
        "required_types": ["BUSINESS_ANALYSIS", "SYSTEM_TEST", "TRAINING", "OPERATIONS",
                           "LEGAL", "DEVOPS", "QA", "PRODUCT_MGMT"],
        "standards": ["SOC 2", "ISO 27001"],
        "hitl_override": "standard",
        "extra_criteria": {
            "BUSINESS_ANALYSIS": ["Integration points with existing systems mapped", "Migration plan drafted"],
            "SYSTEM_TEST": ["Load test simulates expected concurrent users", "Failover scenario tested"],
            "TRAINING": ["Admin guide separate from end-user guide", "Role-based training paths defined"],
        },
    },
    "ecommerce": {
        "keywords": ["e-commerce", "ecommerce", "online store", "shopping cart", "checkout",
                      "inventory", "catalog", "payments", "Shopify", "WooCommerce",
                      "order management", "marketplace", "dropshipping", "subscription box",
                      "delivery", "grocery", "product recommendation", "loyalty", "rewards",
                      "returns", "pricing", "seller",
                      "repricing", "refund", "exchange management",
                      "competitor price", "multi-store", "product import"],
        "required_types": ["UX_DESIGN", "FINANCIAL", "LEGAL", "SECURITY", "OPERATIONS",
                           "MARKET_RESEARCH", "QA"],
        "standards": ["PCI DSS"],
        "hitl_override": "standard",
        "extra_criteria": {
            "SECURITY": ["Payment flow PCI compliant", "Fraud detection rules defined"],
            "LEGAL": ["Return/refund policy drafted", "Consumer protection compliance checked"],
        },
    },
    "healthcare_software": {
        "keywords": ["health record", "EHR", "EMR", "telehealth", "telemedicine",
                      "HIPAA", "patient portal", "clinical workflow", "pharmacy",
                      "clinical trial", "HL7", "FHIR", "mental health", "wellness",
                      "therapy", "caregiver", "e-prescri",
                      "patient enrollment", "adverse events", "21 CFR"],
        "required_types": ["REGULATORY", "SECURITY", "COMPLIANCE", "QA", "SYSTEM_TEST",
                           "TRAINING", "OPERATIONS", "LEGAL"],
        "standards": ["HIPAA", "HITECH", "HL7 FHIR"],
        "hitl_override": "strict",
        "extra_criteria": {
            "REGULATORY": ["HIPAA risk assessment complete", "BAA template prepared"],
            "SECURITY": ["PHI encryption at rest and in transit", "Access audit logging enabled"],
        },
    },
    "edtech": {
        "keywords": ["education", "e-learning", "LMS", "course", "student", "teacher",
                      "classroom", "curriculum", "tutoring", "assessment",
                      "flashcard", "quiz", "exam", "proctoring", "school",
                      "learning", "bootcamp", "coding challenge", "instructor",
                      "skill assessment", "virtual lab", "SCORM",
                      "spaced repetition", "gamification", "study",
                      "pronunciation", "language learning",
                      "tutor", "adaptive learning", "Socratic"],
        "required_types": ["UX_DESIGN", "TRAINING", "LOCALIZATION", "QA",
                           "PRODUCT_MGMT", "BUSINESS_ANALYSIS"],
        "standards": ["FERPA", "COPPA", "WCAG 2.1"],
        "hitl_override": "standard",
        "extra_criteria": {
            "UX_DESIGN": ["Accessibility for learners with disabilities", "Mobile-responsive for student devices"],
            "LEGAL": ["FERPA/COPPA compliance if minors involved"],
        },
    },
}

# Default acceptance criteria injected into each task for the critic
# (Review and Critique pattern — bounded evaluation, not open-ended)
DEFAULT_ACCEPTANCE_CRITERIA = {
    # Software
    "BACKEND":  ["Handles errors gracefully", "Has input validation", "Returns structured responses"],
    "FRONTEND": ["Responsive layout", "Error states handled", "Loading states shown"],
    "TESTS":    ["Covers happy path", "Covers error path", "No hardcoded test data"],
    "INFRA":    ["Idempotent", "Secrets not hardcoded", "Rollback documented"],
    "DATABASE": ["Migrations reversible", "Indexes on query columns", "No data loss on rollback"],
    "API":      ["RESTful conventions", "Error codes documented", "Versioned endpoints"],
    "DOCS":     ["Accurate to implementation", "Setup instructions work", "No stale references"],
    "CONFIG":   ["Environment-specific values parameterized", "Defaults are safe", "Validated on load"],
    "AGENTIC":  ["Pattern correctly implemented per registry spec", "Graceful degradation on LLM failure", "Observable via audit log"],
    # Hardware / Embedded / Mechanical
    "FIRMWARE":      ["Compiles without warnings", "No dynamic memory allocation in safety-critical paths", "Interrupt handlers are reentrant-safe"],
    "HARDWARE_SIM":  ["Simulation matches timing constraints", "Test bench covers all I/O states", "Power analysis within budget"],
    "PCB_DESIGN":    ["DRC passes with zero violations", "BOM has no single-source components", "Thermal analysis within limits"],
    "MECHANICAL":    ["Tolerance stack-up within spec", "Assembly sequence documented", "Material selection justified"],
    "SAFETY":        ["All hazards identified and mitigated", "Risk matrix complete", "Traceability to requirements"],
    "COMPLIANCE":    ["All applicable standards referenced", "Evidence artifacts linked", "Gap analysis complete"],
    "EMBEDDED_TEST": ["HIL test coverage ≥ 90%", "All fault injection tests pass", "Timing requirements verified"],
    # Quality & Testing
    "QA":           ["Test plan covers all requirements", "Test cases are reproducible", "Pass/fail criteria defined for each case"],
    "SYSTEM_TEST":  ["End-to-end scenarios cover critical user paths", "Performance baselines established", "Environment parity with production documented"],
    # Business & Strategy
    "BUSINESS_ANALYSIS": ["Requirements traceable to business objectives", "User stories follow INVEST criteria", "Process flows cover happy and exception paths"],
    "MARKET_RESEARCH":   ["Competitor analysis covers top 5 alternatives", "Target personas defined with evidence", "Go-to-market timeline realistic"],
    "FINANCIAL":         ["Revenue model assumptions documented", "Unit economics calculated", "Break-even timeline identified"],
    "PRODUCT_MGMT":      ["Success metrics are measurable (KPIs defined)", "Roadmap items prioritized with rationale", "MVP scope clearly bounded"],
    # Regulatory & Legal
    "REGULATORY":   ["All applicable regulations identified", "Submission timeline drafted", "Gap analysis against each standard complete"],
    "LEGAL":        ["Terms of service cover liability and disputes", "Privacy policy compliant with GDPR/CCPA", "IP ownership and licensing clarified"],
    # Design & UX
    "UX_DESIGN":    ["User research findings documented", "Wireframes cover core flows", "Accessibility audit against WCAG 2.1 AA"],
    # Infrastructure & Operations
    "DEVOPS":       ["CI/CD pipeline runs green on sample commit", "Monitoring covers uptime, latency, error rate", "Rollback procedure documented and tested"],
    "OPERATIONS":   ["Runbooks cover top 5 incident scenarios", "SLA targets defined with measurement method", "Capacity plan covers 12-month growth forecast"],
    # Content & Localization
    "TRAINING":       ["User guide covers all primary workflows", "Screenshots/diagrams match current UI", "Onboarding path tested with sample user"],
    "LOCALIZATION":   ["i18n framework configured with fallback locale", "String extraction covers all user-facing text", "RTL layout tested if applicable"],
    # Cross-cutting
    "SECURITY":  ["Threat model covers STRIDE categories", "No critical/high vulnerabilities", "SBOM generated"],
    "DATA":      ["Schema documented", "Idempotent pipelines", "Data validation on ingestion"],
    "ML_MODEL":  ["Evaluation metrics documented", "Training reproducible", "Inference latency within SLA"],
}

# Run states
STATES = {
    "decomposing":      "Breaking product description into tasks",
    "critic_plan":      "Critic reviewing the implementation plan",
    "awaiting_plan":    "Waiting for human approval of the plan",
    "scaffolding":      "Creating project structure",
    "executing":        "Running agent tasks",
    "critic_code":      "Critic reviewing code output",
    "integrating":      "Merging and testing",
    "critic_integration": "Critic reviewing integration results",
    "awaiting_build":   "Waiting for human approval of the build",
    "finalizing":       "Completing and archiving",
    "completed":        "Build complete",
    "failed":           "Build failed",
    "rejected":         "Build rejected by human",
}


class BuildOrchestrator:
    """
    Orchestrates the full 0→1→N build pipeline.

    Thread-safe via a lock on the runs dict.

    Enhanced with:
    - SQLite checkpointing for crash recovery (DeerFlow-inspired)
    - Context summarization for long task chains
    - Dependency failure propagation
    """

    # Maximum context length (chars) before summarization kicks in
    MAX_CONTEXT_LENGTH = 8000

    def __init__(self, checkpoint_db: str = ""):
        self.logger = logging.getLogger("BuildOrchestrator")
        self._runs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._checkpoint_db = checkpoint_db or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data", "build_checkpoints.db",
        )
        self._init_checkpoint_db()
        self._restore_runs()

    # ------------------------------------------------------------------
    # Checkpoint persistence (SQLite-backed crash recovery)
    # ------------------------------------------------------------------

    def _init_checkpoint_db(self):
        """Create the build_checkpoints table if it does not exist."""
        try:
            import sqlite3
            os.makedirs(os.path.dirname(self._checkpoint_db), exist_ok=True)
            conn = sqlite3.connect(self._checkpoint_db)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS build_runs (
                    run_id     TEXT PRIMARY KEY,
                    state      TEXT NOT NULL,
                    data       TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()
            conn.close()
            self.logger.info("Build checkpoint DB initialised at %s", self._checkpoint_db)
        except Exception as exc:
            self.logger.warning("Checkpoint DB init failed (non-fatal): %s", exc)

    def _checkpoint(self, run: dict):
        """Persist current run state to SQLite for crash recovery."""
        try:
            import sqlite3
            # Serialize run — skip non-serialisable fields
            safe_run = {k: v for k, v in run.items() if k != "_thread"}
            data = json.dumps(safe_run, default=str)
            conn = sqlite3.connect(self._checkpoint_db)
            conn.execute(
                "INSERT OR REPLACE INTO build_runs (run_id, state, data, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (run["run_id"], run["state"], data, run.get("updated_at", "")),
            )
            conn.commit()
            conn.close()
            self.logger.debug("Checkpointed run %s at state=%s", run["run_id"], run["state"])
        except Exception as exc:
            self.logger.warning("Checkpoint failed for run %s: %s", run.get("run_id"), exc)

    def _restore_runs(self):
        """Restore in-progress builds from checkpoint DB on startup."""
        try:
            import sqlite3
            conn = sqlite3.connect(self._checkpoint_db)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM build_runs WHERE state NOT IN ('completed', 'failed', 'rejected')"
            ).fetchall()
            conn.close()

            restored = 0
            for row in rows:
                try:
                    run = json.loads(row["data"])
                    with self._lock:
                        self._runs[run["run_id"]] = run
                    restored += 1
                except Exception as exc:
                    self.logger.warning("Failed to restore run %s: %s", row["run_id"], exc)

            if restored:
                self.logger.info("Restored %d in-progress build run(s) from checkpoint", restored)
        except Exception as exc:
            self.logger.debug("Checkpoint restore skipped: %s", exc)

    # ------------------------------------------------------------------
    # Context Summarization (DeerFlow-inspired)
    # ------------------------------------------------------------------

    def _summarize_context(self, results: list[dict]) -> str:
        """Compress completed task results into a concise summary.

        When the accumulated context from prior wave results exceeds
        MAX_CONTEXT_LENGTH, summarize to keep the LLM context window lean.
        Returns a summary string suitable for injection into the next agent's context.
        """
        if not results:
            return ""

        # Build full context
        parts = []
        for r in results:
            task = r.get("task", {})
            result = r.get("result", {})
            parts.append(
                f"[{task.get('task_type', '?')}] {task.get('description', '')[:100]} "
                f"→ status={result.get('status', '?')}, "
                f"files={result.get('files_changed', [])[:3]}"
            )

        full_context = "\n".join(parts)

        if len(full_context) <= self.MAX_CONTEXT_LENGTH:
            return full_context

        # Summarize: keep task types, status, and key metrics
        summary_parts = [
            f"[SUMMARIZED — {len(results)} prior tasks]",
            f"Completed: {sum(1 for r in results if r.get('result', {}).get('status') == 'completed')}",
            f"Failed: {sum(1 for r in results if r.get('result', {}).get('status') in ('error', 'failed'))}",
        ]
        # Include last 3 results in full detail
        for r in results[-3:]:
            task = r.get("task", {})
            result = r.get("result", {})
            summary_parts.append(
                f"  {task.get('task_type', '?')}: {task.get('description', '')[:80]} "
                f"→ {result.get('status', '?')}"
            )

        # Include all unique file paths
        all_files = set()
        for r in results:
            all_files.update(r.get("result", {}).get("files_changed", []))
        if all_files:
            summary_parts.append(f"Files touched: {sorted(all_files)[:20]}")

        return "\n".join(summary_parts)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(
        self,
        product_description: str,
        solution_name: str = "",
        repo_url: str = "",
        workspace_dir: str = "",
        critic_threshold: int = 70,
        hitl_level: str = "standard",
    ) -> dict:
        """
        Start a new build pipeline.

        Uses Hierarchical Task Decomposition to break the product into a
        multi-level task tree, then runs the critic review loop with
        acceptance criteria before surfacing to human.

        Args:
            product_description: Plain-English description of what to build.
            solution_name: Name for the generated solution.
            repo_url: Git URL to clone (optional).
            workspace_dir: Local workspace path (optional).
            critic_threshold: Minimum critic score to pass (0-100).
            hitl_level: Approval granularity — "minimal", "standard", or "strict".

        Returns immediately with run_id and decomposed plan.
        """
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        hitl_gates = HITL_LEVELS.get(hitl_level, HITL_LEVELS["standard"])

        run = {
            "run_id": run_id,
            "product_description": product_description,
            "solution_name": solution_name or f"build_{run_id[:8]}",
            "repo_url": repo_url,
            "workspace_dir": workspace_dir or "",
            "critic_threshold": critic_threshold,
            "hitl_level": hitl_level,
            "hitl_gates": hitl_gates,
            "state": "decomposing",
            "created_at": now,
            "updated_at": now,
            "plan": [],
            "critic_reports": [],
            "agent_results": [],
            "integration_result": None,
            "error": None,
        }

        with self._lock:
            self._runs[run_id] = run
        self._checkpoint(run)

        # Decompose via planner
        try:
            phase_start = time.monotonic()
            plan = self._decompose(run)
            run.setdefault("phase_durations", {})["decompose"] = round(time.monotonic() - phase_start, 2)
            run["plan"] = plan
            run["updated_at"] = datetime.now(timezone.utc).isoformat()

            if not plan:
                run["state"] = "failed"
                run["error"] = "Planner could not decompose the product description"
                self._audit(run_id, "BUILD_DECOMPOSE_FAILED", run["error"])
                return self._run_summary(run)

            self._audit(run_id, "BUILD_DECOMPOSED", json.dumps(plan)[:500])

            # Critic reviews the plan
            run["state"] = "critic_plan"
            phase_start = time.monotonic()
            critic_result = self._critic_review_plan(run)
            run.setdefault("phase_durations", {})["critic_plan"] = round(time.monotonic() - phase_start, 2)
            run["critic_reports"].append({
                "phase": "plan",
                "result": critic_result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Move to awaiting human approval
            run["state"] = "awaiting_plan"
            run["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._checkpoint(run)

            self._audit(run_id, "BUILD_AWAITING_PLAN_APPROVAL", json.dumps({
                "task_count": len(plan),
                "critic_score": critic_result.get("final_score", 0),
            }))

        except Exception as exc:
            self.logger.error("Build start failed: %s", exc)
            run["state"] = "failed"
            run["error"] = str(exc)

        return self._run_summary(run)

    def approve_plan(self, run_id: str, feedback: str = "") -> dict:
        """
        Human approves the decomposed plan. Triggers scaffold + execution.
        """
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return {"error": f"Run '{run_id}' not found"}
            if run["state"] != "awaiting_plan":
                return {"error": f"Run is not awaiting plan approval (state: {run['state']})"}

            self._audit(run_id, "BUILD_PLAN_APPROVED", feedback[:500])

            # Scaffold
            run["state"] = "scaffolding"
            run["updated_at"] = datetime.now(timezone.utc).isoformat()
            phase_start = time.monotonic()
            scaffold_result = self._scaffold(run)
            run.setdefault("phase_durations", {})["scaffold"] = round(time.monotonic() - phase_start, 2)

            # Execute agents
            run["state"] = "executing"
            run["updated_at"] = datetime.now(timezone.utc).isoformat()
            phase_start = time.monotonic()
            self._execute_agents(run)
            run.setdefault("phase_durations", {})["execute"] = round(time.monotonic() - phase_start, 2)

            # Critic reviews code
            run["state"] = "critic_code"
            run["updated_at"] = datetime.now(timezone.utc).isoformat()
            phase_start = time.monotonic()
            code_critic = self._critic_review_code(run)
            run.setdefault("phase_durations", {})["critic_code"] = round(time.monotonic() - phase_start, 2)
            run["critic_reports"].append({
                "phase": "code",
                "result": code_critic,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Integrate
            run["state"] = "integrating"
            run["updated_at"] = datetime.now(timezone.utc).isoformat()
            phase_start = time.monotonic()
            integration = self._integrate(run)
            run.setdefault("phase_durations", {})["integrate"] = round(time.monotonic() - phase_start, 2)
            run["integration_result"] = integration

            # Critic reviews integration
            run["state"] = "critic_integration"
            run["updated_at"] = datetime.now(timezone.utc).isoformat()
            phase_start = time.monotonic()
            int_critic = self._critic_review_integration(run)
            run.setdefault("phase_durations", {})["critic_integration"] = round(time.monotonic() - phase_start, 2)
            run["critic_reports"].append({
                "phase": "integration",
                "result": int_critic,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Await final human approval
            run["state"] = "awaiting_build"
            run["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._checkpoint(run)

            self._audit(run_id, "BUILD_AWAITING_BUILD_APPROVAL", json.dumps({
                "agent_count": len(run["agent_results"]),
                "code_critic_score": code_critic.get("final_score", 0),
                "integration_critic_score": int_critic.get("final_score", 0),
            })[:500])

            return self._run_summary(run)

    def approve_build(self, run_id: str, feedback: str = "") -> dict:
        """
        Human approves the final build. Triggers finalization.
        """
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return {"error": f"Run '{run_id}' not found"}
            if run["state"] != "awaiting_build":
                return {"error": f"Run is not awaiting build approval (state: {run['state']})"}

            self._audit(run_id, "BUILD_APPROVED", feedback[:500])

            # Finalize
            run["state"] = "finalizing"
            run["updated_at"] = datetime.now(timezone.utc).isoformat()
            phase_start = time.monotonic()
            self._finalize(run, feedback)
            run.setdefault("phase_durations", {})["finalize"] = round(time.monotonic() - phase_start, 2)

            run["state"] = "completed"
            run["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._checkpoint(run)

            self._audit(run_id, "BUILD_COMPLETED", json.dumps({
                "solution": run["solution_name"],
                "task_count": len(run["plan"]),
            }))

            return self._run_summary(run)

    def reject(self, run_id: str, feedback: str = "") -> dict:
        """
        Reject a build run. Sets state to 'rejected' and records feedback.
        """
        run = self._runs.get(run_id)
        if run is None:
            return {"error": f"Run '{run_id}' not found"}
        with self._lock:
            run["state"] = "rejected"
            run["error"] = f"Rejected: {feedback}" if feedback else "Rejected by human"
            run["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._audit(run_id, "BUILD_REJECTED", feedback[:500])
        return self._run_summary(run)

    def get_status(self, run_id: str) -> dict:
        """Return full status of a build run."""
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return {"error": f"Run '{run_id}' not found"}
            return self._run_summary(run)

    def list_runs(self) -> list[dict]:
        """List all build runs with summary info."""
        with self._lock:
            return [
                {
                    "run_id": r["run_id"],
                    "solution_name": r["solution_name"],
                    "state": r["state"],
                    "created_at": r["created_at"],
                    "task_count": len(r.get("plan", [])),
                }
                for r in self._runs.values()
            ]

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    def _decompose(self, run: dict) -> list[dict]:
        """
        Hierarchical Task Decomposition (Google pattern #8).

        Uses PlannerAgent to decompose the product into a task tree with:
        - Multi-level breakdown (top-level components → atomic tasks)
        - Acceptance criteria per task (for bounded critic evaluation)
        - Agent routing hints (coordinator pattern)
        - Dependency declarations (for wave parallelism)

        The planner prompt is enriched with awareness of all available
        agent patterns and existing solution roles.
        """
        try:
            from src.agents.planner import planner_agent

            # Build coordinator context: available agents and their capabilities
            agent_context = self._build_agent_context()

            # Detect product domain to guide task type selection
            domain_hints = self._detect_domain(run["product_description"])

            plan = planner_agent.create_plan(
                description=(
                    f"Build the following product from scratch:\n\n"
                    f"{run['product_description']}\n\n"
                    f"Solution name: {run['solution_name']}\n\n"
                    f"## Domain Detection\n{domain_hints}\n\n"
                    f"## Decomposition Rules\n"
                    f"1. HIERARCHICAL: Break into top-level components first, then "
                    f"atomic implementable tasks within each component.\n"
                    f"2. ACCEPTANCE CRITERIA: Each task MUST include 'acceptance_criteria' "
                    f"(list of strings) — concrete, testable conditions for completion.\n"
                    f"3. DEPENDENCIES: Each task should declare 'depends_on' (list of step numbers) "
                    f"— tasks with no dependencies can run in parallel (wave execution).\n"
                    f"4. AGENT ROUTING: Each task should include 'agent_role' — which specialist "
                    f"agent should handle it.\n"
                    f"5. DOMAIN-APPROPRIATE TYPES: Use the task types that match the product domain. "
                    f"A firmware product needs FIRMWARE + EMBEDDED_TEST + SAFETY tasks, not just BACKEND. "
                    f"A mechanical product needs MECHANICAL + PCB_DESIGN tasks. A pure web app only "
                    f"needs software types. Match the domain.\n\n"
                    f"## Available Agent Roles\n{agent_context}\n\n"
                    f"## Task Types (use the ones relevant to this product's domain)\n"
                    f"Output format per task: {{step, task_type, description, payload, "
                    f"acceptance_criteria, depends_on, agent_role}}"
                ),
                override_task_types=BUILD_TASK_TYPES,
            )

            # Enrich tasks with default acceptance criteria if not provided by LLM
            matched_domains = self._matched_domains(run["product_description"])
            for task in plan:
                task_type = task.get("task_type", "")
                if not task.get("acceptance_criteria"):
                    task["acceptance_criteria"] = DEFAULT_ACCEPTANCE_CRITERIA.get(
                        task_type, ["Meets task description requirements"]
                    )
                # Append domain-specific extra criteria
                for domain in matched_domains:
                    extras = domain.get("extra_criteria", {}).get(task_type, [])
                    existing = task.get("acceptance_criteria", [])
                    for ec in extras:
                        if ec not in existing:
                            existing.append(ec)
                    task["acceptance_criteria"] = existing
                if not task.get("depends_on"):
                    task["depends_on"] = []
                if not task.get("agent_role"):
                    task["agent_role"] = TASK_TYPE_TO_AGENT.get(task_type, "developer")

            return plan
        except Exception as exc:
            self.logger.error("Decompose failed: %s", exc)
            return []

    def _matched_domains(self, description: str) -> list[dict]:
        """Return list of DOMAIN_RULES entries matching the product description.

        Requires at least 2 keyword hits to reduce false positives (e.g.,
        "mobile app" alone shouldn't trigger consumer_app for a medtech product).
        Single-hit is allowed for very specific keywords (standards like ISO/FDA).
        """
        desc_lower = description.lower()
        matched = []
        for domain_id, rule in DOMAIN_RULES.items():
            hits = sum(1 for kw in rule["keywords"] if kw.lower() in desc_lower)
            # Standards keywords (ISO, FDA, DO-, PCI, etc.) are high-signal — 1 hit enough
            standard_kws = [kw for kw in rule["keywords"]
                           if any(s in kw.upper() for s in ["ISO", "FDA", "IEC", "DO-", "PCI", "SOX", "SOC", "AUTOSAR"])]
            has_standard_hit = any(kw.lower() in desc_lower for kw in standard_kws)
            if hits >= 2 or has_standard_hit:
                matched.append({**rule, "domain": domain_id})
        return matched

    def _detect_domain(self, description: str) -> str:
        """
        Detect product domain from description keywords and return guidance
        for the planner about which task types and standards apply.

        This ensures that a "surgical robot" gets FIRMWARE + SAFETY + MECHANICAL
        tasks, not just BACKEND + FRONTEND.
        """
        matched = self._matched_domains(description)
        if not matched:
            return (
                "Domain: **General Software**\n"
                "Use software task types: BACKEND, FRONTEND, TESTS, DATABASE, API, "
                "INFRA, CONFIG, DOCS. Add AGENTIC if the product needs AI capabilities."
            )

        lines = []
        all_required = set()
        all_standards = set()
        hitl_override = "standard"

        for rule in matched:
            all_required.update(rule.get("required_types", []))
            all_standards.update(rule.get("standards", []))
            rule_hitl = rule.get("hitl_override", "standard")
            if rule_hitl == "strict":
                hitl_override = "strict"

        matched_names = [did for did, rule in DOMAIN_RULES.items() if rule in matched]
        lines.append(f"Detected domain(s): **{', '.join(matched_names)}** (matched by keywords)")
        lines.append(f"\n**REQUIRED task types for this domain** (DO NOT skip these):")
        for rt in sorted(all_required):
            desc = BUILD_TASK_TYPES.get(rt, "")
            lines.append(f"  - {rt}: {desc}")

        if all_standards:
            lines.append(f"\n**Applicable standards:** {', '.join(sorted(all_standards))}")
            lines.append(
                "Include COMPLIANCE tasks that produce evidence artifacts for these standards."
            )

        lines.append(f"\n**Recommended HITL level:** {hitl_override}")
        lines.append(
            "\nYou may ALSO use standard software types (BACKEND, FRONTEND, etc.) "
            "alongside the domain-specific types. Most hardware products also need "
            "software components."
        )

        return "\n".join(lines)

    def _build_agent_context(self) -> str:
        """
        Multi-Agent Coordinator: gather available agent roles AND agentic AI
        design patterns so the planner can:
        1. Route tasks to the right specialist agent
        2. Recommend the right agentic pattern for the product being built

        This makes the orchestrator pattern-aware — when a product requires
        AI capabilities, the planner can design it using proven patterns.

        Uses WORKFORCE_REGISTRY to present agents as organized functional teams.
        """
        lines = []

        # Framework agents organized by workforce teams
        lines.append("### Framework Agent Teams (always available)")
        lines.append("")

        team_display_names = {
            "engineering": "Engineering",
            "analysis": "Analysis & Data",
            "design": "Design & Product",
            "compliance": "Compliance & Legal",
            "operations": "Operations & Content",
        }

        for team_id, team in WORKFORCE_REGISTRY.items():
            display_name = team_display_names.get(team_id, team_id.title())
            capabilities = ", ".join(team["capabilities"])
            lines.append(f"**{display_name}** (capabilities: {capabilities}):")
            lead = team["lead"]
            lead_desc = _AGENT_DESCRIPTIONS.get(lead, "")
            lines.append(f"- {lead} (lead): {lead_desc}")
            for member in team["members"]:
                member_desc = _AGENT_DESCRIPTIONS.get(member, "")
                lines.append(f"- {member}: {member_desc}")
            lines.append("")

        lines.append("**Orchestration:**")
        for role in ("planner", "monitor", "critic"):
            lines.append(f"- {role}: {_AGENT_DESCRIPTIONS.get(role, '')}")

        # Adaptive routing stats — show the planner what's working
        stats = adaptive_router.get_stats()
        if stats.get("scores"):
            lines.append("")
            lines.append("### Routing Intelligence (learned from prior builds)")
            for task_type, role_scores in stats["scores"].items():
                counts = stats.get("counts", {}).get(task_type, {})
                best_role = max(role_scores, key=role_scores.get)
                best_count = counts.get(best_role, 0)
                if best_count >= AdaptiveRouter.MIN_OBSERVATIONS:
                    lines.append(
                        f"- {task_type}: best agent = {best_role} "
                        f"(score: {role_scores[best_role]:.2f}, n={best_count})"
                    )

        # Solution-defined roles (from prompts.yaml)
        try:
            from src.core.project_loader import project_config
            roles = project_config.get_prompts().get("roles", {})
            if roles:
                lines.append("\n### Solution-Defined Roles (from prompts.yaml)")
                for role_id, role_cfg in roles.items():
                    name = role_cfg.get("name", role_id)
                    desc = role_cfg.get("description", "")
                    lines.append(f"- {role_id}: {name} — {desc}")
        except Exception:
            pass

        # Design patterns for the BUILD PROCESS itself
        lines.append("\n### Build Process Patterns (applied automatically)")
        lines.append("- ReAct: Each agent task uses Thought→Action→Observation loops")
        lines.append("- Parallel Execution: Independent tasks grouped into waves")
        lines.append("- Review & Critique: Every output gets critic review")
        lines.append("- Iterative Refinement: Critic feedback drives revision loops")
        lines.append("- HITL: Human approval at configurable gate points")

        # Agentic AI patterns the PRODUCT can use
        lines.append("\n### Agentic AI Patterns for the PRODUCT (use when applicable)")
        lines.append(
            "If the product being built needs AI/agent capabilities, "
            "recommend one of these proven patterns in the task descriptions. "
            "Include a task of type CONFIG to set up the pattern's components."
        )
        for pid, pattern in AGENTIC_PATTERNS.items():
            use_cases = "; ".join(pattern["when_to_use"][:2])
            lines.append(f"- **{pattern['name']}** ({pid}): {pattern['description']}")
            lines.append(f"  Use when: {use_cases}")
            lines.append(f"  Components: {', '.join(pattern['components'])}")

        return "\n".join(lines)

    def _scaffold(self, run: dict) -> dict:
        """Create initial project structure."""
        workspace = run.get("workspace_dir", "")
        if not workspace:
            return {"status": "skipped", "reason": "no workspace_dir"}

        try:
            os.makedirs(workspace, exist_ok=True)

            # Create basic structure
            dirs = ["src", "tests", "docs", "config"]
            for d in dirs:
                os.makedirs(os.path.join(workspace, d), exist_ok=True)

            # README
            readme_path = os.path.join(workspace, "README.md")
            if not os.path.exists(readme_path):
                with open(readme_path, "w") as f:
                    f.write(f"# {run['solution_name']}\n\n{run['product_description']}\n")

            # AGENTS.md — record of which agents built what
            agents_path = os.path.join(workspace, "AGENTS.md")
            if not os.path.exists(agents_path):
                with open(agents_path, "w") as f:
                    f.write(f"# Build Agents — {run['solution_name']}\n\n")
                    f.write(f"Build started: {run['created_at']}\n\n")
                    f.write("## Tasks\n\n")
                    for task in run.get("plan", []):
                        f.write(f"- **{task.get('task_type', '?')}**: {task.get('description', '')}\n")

            self.logger.info("Scaffolded workspace: %s", workspace)
            return {"status": "completed", "workspace": workspace}

        except Exception as exc:
            self.logger.error("Scaffold failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    def _execute_agents(self, run: dict) -> None:
        """
        Multi-Agent Parallel execution with dependency-aware wave scheduling.

        Uses the 'depends_on' field from hierarchical decomposition to build
        a dependency graph, then groups tasks into waves where each wave
        contains only tasks whose dependencies have already completed.

        Enhanced with:
        - Context summarization between waves (DeerFlow-inspired)
        - Per-wave checkpointing for crash recovery
        - Dependency failure propagation (skip blocked tasks)

        Coordinator routing: each task's 'agent_role' field determines which
        specialist agent handles it. Execution uses the 3-tier isolation
        cascade: OpenShell (container) → SandboxRunner (local) → OpenSWE (autonomous).
        """
        from src.integrations.openswe_runner import get_openswe_runner
        from src.integrations.openshell_runner import get_openshell_runner
        from src.integrations.sandbox_runner import sandbox_runner as local_sandbox

        openswe = get_openswe_runner()
        openshell = get_openshell_runner()
        results = []
        plan = run.get("plan", [])
        failed_steps: set = set()

        # Build dependency-aware waves
        waves = self._compute_waves(plan)

        for wave_num, wave in enumerate(waves):
            # Filter out tasks whose dependencies failed
            executable = []
            for task in wave:
                deps = task.get("depends_on", [])
                if any(d in failed_steps for d in deps):
                    self.logger.warning(
                        "Skipping task step=%s (dependency failed): %s",
                        task.get("step"), task.get("task_type"),
                    )
                    results.append({
                        "task": task,
                        "result": {"status": "blocked", "reason": "dependency_failed"},
                        "step": task.get("step", 0),
                        "wave": wave_num,
                        "agent_role": task.get("agent_role", "developer"),
                    })
                    failed_steps.add(task.get("step", 0))
                    continue
                executable.append(task)

            if not executable:
                self.logger.warning("Wave %d: all tasks blocked, skipping", wave_num)
                continue

            self.logger.info(
                "Executing wave %d/%d: %d task(s) [%s]",
                wave_num + 1, len(waves), len(executable),
                ", ".join(t.get("task_type", "?") for t in executable),
            )

            # Inject summarized context from prior waves
            prior_context = self._summarize_context(results)
            if prior_context:
                run["_prior_wave_context"] = prior_context

            wave_results = []
            for task in executable:
                # Coordinator pattern: route to specialist agent
                agent_role = task.get("agent_role", "developer")
                result = self._route_to_agent(
                    task, agent_role, openswe, run,
                    openshell=openshell, local_sandbox=local_sandbox,
                )

                # Record outcome in adaptive router for future routing decisions
                task_type = task.get("task_type", "")
                success = result.get("status") == "completed"
                adaptive_router.record(
                    task_type=task_type,
                    agent_role=agent_role,
                    success=success,
                    quality_score=0.5 if success else 0.0,
                )

                wave_results.append({
                    "task": task,
                    "result": result,
                    "step": task.get("step", 0),
                    "wave": wave_num,
                    "agent_role": agent_role,
                })

            results.extend(wave_results)

            # Track failed steps for dependency propagation
            for wr in wave_results:
                if wr["result"].get("status") in ("error", "failed"):
                    failed_steps.add(wr["task"].get("step", 0))

            # Anti-drift checkpoint: verify wave outputs align with plan intent
            for wr in wave_results:
                if not self._check_drift(wr["task"], wr["result"]):
                    wr["drift_warning"] = True
                    self.logger.warning(
                        "DRIFT DETECTED: task step=%s type=%s — output may not align with plan",
                        wr["task"].get("step", "?"),
                        wr["task"].get("task_type", "?"),
                    )
                    run_id = run.get("run_id", "unknown")
                    self._audit(
                        run_id,
                        "BUILD_DRIFT_WARNING",
                        json.dumps({
                            "step": wr["task"].get("step", 0),
                            "task_type": wr["task"].get("task_type", ""),
                            "description": wr["task"].get("description", "")[:200],
                        }),
                    )

            # Checkpoint after each wave for crash recovery
            run["agent_results"] = results
            run["_completed_waves"] = wave_num + 1
            self._checkpoint(run)

        # Count drift warnings and add to run metadata
        drift_count = sum(1 for r in results if r.get("drift_warning"))
        if drift_count:
            run["drift_warnings"] = drift_count

        # Count failures (including blocked) and update run state accordingly
        failed = [r for r in results if r["result"].get("status") in ("error", "failed", "blocked")]
        if failed and len(failed) == len(results):
            run["state"] = "failed"
            run["error"] = f"All {len(failed)} agent tasks failed or blocked"
        elif failed:
            self.logger.warning(
                "%d/%d tasks failed/blocked (completed: %d)",
                len(failed), len(results), len(results) - len(failed),
            )

        run["agent_results"] = results

    def _compute_waves(self, plan: list[dict]) -> list[list[dict]]:
        """
        Compute execution waves from task dependency graph.

        Tasks with no dependencies (or whose dependencies are all satisfied)
        form the next wave. This produces optimal parallelism.
        """
        if not plan:
            return []

        # Map step number → task
        task_map = {task.get("step", i): task for i, task in enumerate(plan)}
        completed = set()
        remaining = list(plan)
        waves = []

        max_iterations = len(plan) + 1  # prevent infinite loop on circular deps
        for _ in range(max_iterations):
            if not remaining:
                break

            # Find tasks whose dependencies are all in 'completed'
            ready = []
            still_waiting = []
            for task in remaining:
                deps = task.get("depends_on", [])
                if all(d in completed for d in deps):
                    ready.append(task)
                else:
                    still_waiting.append(task)

            if not ready:
                # Circular dependency or missing deps — execute everything left
                self.logger.warning(
                    "Dependency deadlock detected — forcing %d remaining task(s)",
                    len(still_waiting),
                )
                for task in still_waiting:
                    task["forced"] = True
                ready = still_waiting
                still_waiting = []

            waves.append(ready)
            for task in ready:
                completed.add(task.get("step", 0))
            remaining = still_waiting

        return waves

    def _check_drift(self, task: dict, result: dict) -> bool:
        """Anti-drift checkpoint — verify that a task's output aligns with its intent.

        Performs lightweight heuristic checks:
        1. If the task failed, that's not drift — it's failure (handled elsewhere).
        2. If files_changed exist, verify at least one filename relates to the task_type.
        3. If the result has code, verify it's not empty for code-producing task types.

        Returns True if aligned (no drift), False if drift detected.
        """
        status = result.get("status", "")

        # Failed tasks aren't drift — they're failures
        if status == "failed" or status == "error":
            return True

        task_type = task.get("task_type", "")
        files_changed = result.get("files_changed", [])

        # Task types that should produce files — derived from ARTIFACT_TYPES registry
        code_producing_types = {
            tt for tt, info in ARTIFACT_TYPES.items()
            if info.get("category") in ("code", "hardware", "infra")
        }

        # Check: code-producing tasks should have files or code
        if task_type in code_producing_types:
            code = result.get("code", "")
            if not files_changed and not code:
                self.logger.debug(
                    "Drift check: task_type=%s produced no files or code", task_type
                )
                return False

        # Check: files_changed should have some relevance to the task
        # Use simple keyword matching from task description
        if files_changed and task.get("description"):
            desc_lower = task["description"].lower()
            # Extract a few key terms from the description
            key_terms = set()
            for word in desc_lower.split():
                if len(word) > 3:
                    key_terms.add(word.strip(".,;:!?()"))

            # Check if any file path contains any key term
            files_lower = " ".join(f.lower() for f in files_changed)
            has_relevance = any(term in files_lower for term in key_terms)

            # Also accept if files match common patterns for the task type
            type_patterns = {
                "BACKEND": ["app", "server", "api", "route", "service", "main", "src"],
                "FRONTEND": ["app", "component", "page", "ui", "view", "src", "index"],
                "TESTS": ["test", "spec", "fixture"],
                "DATABASE": ["schema", "migration", "model", "db", "seed"],
                "CONFIG": ["config", "docker", "ci", "env", "yaml", "yml", "toml"],
                "DOCS": ["readme", "doc", "guide", "md"],
                "INFRA": ["docker", "terraform", "deploy", "infra", "ci", "cd"],
                "FIRMWARE": ["firmware", "hal", "driver", "rtos", "embedded"],
            }
            patterns = type_patterns.get(task_type, [])
            has_pattern_match = any(
                p in files_lower for p in patterns
            )

            if not has_relevance and not has_pattern_match:
                self.logger.debug(
                    "Drift check: files %s don't relate to task_type=%s desc=%s",
                    files_changed[:3], task_type, task["description"][:80],
                )
                return False

        return True

    def _route_to_agent(
        self, task: dict, agent_role: str, openswe, run: dict,
        openshell=None, local_sandbox=None,
    ) -> dict:
        """
        Multi-Agent Coordinator + ReAct dispatch with 3-tier isolation cascade.

        Uses the AdaptiveRouter to potentially override the static agent_role
        based on learned success rates from prior builds.

        Execution cascade (tries most-isolated first, falls back):
          Tier 1: OpenShell — NVIDIA container sandbox (SSH-based, YAML policies)
          Tier 2: SandboxRunner — local repo clone with branch isolation
          Tier 3: OpenSWE — autonomous coding agent (external SWE → LangGraph → LLM)

        The task's acceptance_criteria are passed through to the agent so
        the ReAct OBSERVATION step can self-verify against them.
        """
        # Adaptive routing: let the router suggest a better agent if it has data
        task_type = task.get("task_type", "")
        learned_role = adaptive_router.route(task_type)
        if learned_role != agent_role:
            self.logger.info(
                "AdaptiveRouter override: %s → %s (was %s)",
                task_type, learned_role, agent_role,
            )
            agent_role = learned_role

        enriched_task = self._enrich_task(task, run)

        workspace = run.get("workspace_dir", "")

        # ── Tier 1: OpenShell container sandbox ──────────────────────────
        if openshell and openshell.is_available():
            result = self._try_openshell(enriched_task, workspace, openshell, openswe)
            if result is not None:
                return result
            self.logger.info("Tier 1 (OpenShell) unavailable for task, falling through")

        # ── Tier 2: SandboxRunner local isolation ────────────────────────
        if local_sandbox and workspace:
            result = self._try_sandbox_runner(enriched_task, workspace, local_sandbox, openswe)
            if result is not None:
                return result
            self.logger.info("Tier 2 (SandboxRunner) failed for task, falling through")

        # ── Tier 3: Domain-aware runner (falls back to OpenSWE) ──────────
        # Select the correct domain runner based on agent role
        from src.integrations.base_runner import get_runner_for_role
        domain_runner = get_runner_for_role(agent_role)
        if domain_runner and domain_runner.name != "openswe":
            self.logger.info(
                "Tier 3 (domain runner '%s') for task_type=%s, role=%s",
                domain_runner.name, task_type, agent_role,
            )
            run_result = domain_runner.execute(
                task=enriched_task,
                workspace=workspace,
            )
            return run_result.to_dict()

        # Default: OpenSWE direct (software engineering tasks)
        self.logger.info("Tier 3 (OpenSWE direct) for task_type=%s", task_type)
        return openswe.build(
            task=enriched_task,
            repo_path=workspace,
        )

    def _enrich_task(self, task: dict, run: dict) -> dict:
        """Enrich task with context, acceptance criteria, and artifact info."""
        enriched_task = {**task}
        task_type = task.get("task_type", "")

        # Inject summarized context from prior waves for continuity
        prior_ctx = run.get("_prior_wave_context", "")
        if prior_ctx:
            enriched_task["description"] = (
                f"{task.get('description', '')}\n\n"
                f"[Prior wave context]\n{prior_ctx[:2000]}"
            )

        # Pass acceptance criteria through — the ReAct loop uses them
        # in its OBSERVATION step for self-verification
        acceptance = task.get("acceptance_criteria", [])
        if acceptance:
            enriched_task["description"] = (
                f"{task.get('description', '')}\n\n"
                f"Acceptance Criteria (verify in OBSERVATION step):\n"
                + "\n".join(f"- {c}" for c in acceptance)
            )

        # Artifact type awareness — enrich context with expected output format
        artifact_info = ARTIFACT_TYPES.get(task_type, {})
        if artifact_info:
            extensions = ", ".join(artifact_info.get("extensions", []))
            category = artifact_info.get("category", "code")
            mcp_tools = artifact_info.get("mcp_tools", [])

            artifact_hint = f"\n\nExpected output: {category} artifact(s) with extensions: {extensions}"
            if mcp_tools:
                artifact_hint += f"\nDomain tools available: {', '.join(mcp_tools)}"
            enriched_task["description"] = enriched_task.get("description", "") + artifact_hint

            enriched_task.setdefault("payload", {})
            enriched_task["payload"]["artifact_category"] = category
            enriched_task["payload"]["expected_extensions"] = artifact_info.get("extensions", [])
            enriched_task["payload"]["standards"] = run.get("detected_domains", [])

        return enriched_task

    def _try_openshell(self, task: dict, workspace: str, openshell, openswe) -> Optional[dict]:
        """
        Tier 1: Execute task inside an OpenShell container sandbox.

        Creates an isolated container with YAML security policies, then runs
        OpenSWE inside it via the sandbox_handle parameter. If OpenShell fails
        at any point, returns None to fall through to Tier 2.
        """
        task_type = task.get("task_type", "")
        # Sanitize task_type for sandbox name (alphanumeric + dashes only)
        safe_type = "".join(c if c.isalnum() or c in "-_" else "" for c in task_type)[:32]
        sandbox_name = f"build-{safe_type}-{uuid.uuid4().hex[:8]}"

        # Build security policy based on task type
        policy = self._build_sandbox_policy(task)

        try:
            with openshell.sandbox(sandbox_name, policy) as sb:
                if sb is None:
                    return None

                self.logger.info(
                    "Tier 1 (OpenShell): executing task_type=%s in sandbox %s",
                    task_type, sandbox_name,
                )

                # Run OpenSWE inside the container via sandbox_handle
                result = openswe.build(
                    task=task,
                    repo_path=workspace,
                    sandbox_handle=sb,
                )
                result["execution_tier"] = "openshell"
                return result

        except Exception as exc:
            self.logger.warning(
                "Tier 1 (OpenShell) failed for %s: %s", task_type, exc,
            )
            return None

    def _try_sandbox_runner(
        self, task: dict, workspace: str, local_sandbox, openswe,
    ) -> Optional[dict]:
        """
        Tier 2: Execute task in a local repo clone with branch isolation.

        Clones the workspace into a temp dir, creates an isolated branch,
        runs OpenSWE there, then collects results. Falls through to Tier 3
        on failure.
        """
        task_type = task.get("task_type", "")
        branch_name = f"sage-build/{task_type}-{uuid.uuid4().hex[:8]}"
        sandbox_dir = None

        try:
            # Clone workspace into isolated temp directory
            import tempfile
            sandbox_dir = tempfile.mkdtemp(prefix="sage-build-")

            # Copy workspace to sandbox (faster than git clone for local dirs)
            import shutil
            if os.path.isdir(workspace):
                shutil.copytree(workspace, sandbox_dir, dirs_exist_ok=True)
            else:
                # If workspace is a remote URL, use SandboxRunner's clone
                clone_result = local_sandbox.clone_repo(workspace, sandbox_dir)
                if not clone_result.get("success"):
                    self.logger.warning(
                        "Tier 2: clone failed: %s", clone_result.get("error"),
                    )
                    return None

            # Create isolated branch
            local_sandbox.execute(
                f"git checkout -b {branch_name}", sandbox_dir,
            )

            self.logger.info(
                "Tier 2 (SandboxRunner): executing task_type=%s in %s",
                task_type, sandbox_dir,
            )

            # Run OpenSWE in the sandboxed directory
            result = openswe.build(
                task=task,
                repo_path=sandbox_dir,
            )

            # Collect diff from sandbox for the orchestrator
            diff_result = local_sandbox.get_diff(sandbox_dir)
            if diff_result.get("success") and diff_result.get("stdout"):
                result.setdefault("sandbox_diff", diff_result["stdout"][:10000])

            result["execution_tier"] = "sandbox_runner"
            return result

        except Exception as exc:
            self.logger.warning(
                "Tier 2 (SandboxRunner) failed for %s: %s", task_type, exc,
            )
            return None

        finally:
            # Cleanup sandbox directory
            if sandbox_dir and os.path.isdir(sandbox_dir):
                try:
                    import shutil
                    shutil.rmtree(sandbox_dir, ignore_errors=True)
                except Exception:
                    pass

    def _resolve_docker_image(self, task: dict) -> Optional[str]:
        """
        Resolve the Docker image for a task based on its agent role.

        When an agent is hired, its docker_image field defines the execution
        environment. This ensures hiring a firmware_engineer automatically
        brings gcc-arm, openocd, etc. into the sandbox.
        """
        task_type = task.get("task_type", "")
        agent_role = task.get("agent_role", "")

        # Check agent's docker_image
        agent_info = AGENT_ROLES_REGISTRY.get(agent_role, {})
        if agent_info.get("docker_image"):
            return agent_info["docker_image"]

        # Fallback: resolve from task type → agent mapping
        mapped_role = TASK_TYPE_TO_AGENT.get(task_type, "")
        mapped_info = AGENT_ROLES_REGISTRY.get(mapped_role, {})
        return mapped_info.get("docker_image")

    def _build_sandbox_policy(self, task: dict) -> dict:
        """
        Build an OpenShell YAML security policy based on task type.

        More restrictive for code generation tasks, more permissive for
        tasks that need network access (API integration, deployment).
        Includes the Docker image from the agent's toolchain.
        """
        task_type = task.get("task_type", "")

        # Base policy: restricted filesystem, no network by default
        policy = {
            "filesystem_policy": {
                "read_only_paths": ["/usr", "/lib", "/etc"],
                "writable_paths": ["/workspace", "/tmp"],
                "hidden_paths": ["/root", "/home"],
            },
            "process": {
                "run_as_user": "sandbox",
                "run_as_group": "sandbox",
            },
            "network_policies": {
                "allow_outbound": False,
                "allowed_hosts": [],
            },
        }

        # Task types that need network access
        network_tasks = {
            "api_integration", "deployment", "cloud_setup",
            "ci_cd_pipeline", "package_management", "dependency_setup",
        }
        if task_type in network_tasks:
            policy["network_policies"]["allow_outbound"] = True

        # Task types that need broader filesystem access
        broad_fs_tasks = {
            "database_setup", "infrastructure", "deployment",
            "monitoring_setup", "environment_config",
        }
        if task_type in broad_fs_tasks:
            policy["filesystem_policy"]["writable_paths"].append("/var")

        # Attach Docker image from agent's toolchain
        docker_image = self._resolve_docker_image(task)
        if docker_image:
            policy["docker_image"] = docker_image
            # Also attach the package list for image building
            agent_role = task.get("agent_role", TASK_TYPE_TO_AGENT.get(task_type, ""))
            agent_info = AGENT_ROLES_REGISTRY.get(agent_role, {})
            if agent_info.get("docker_packages"):
                policy["docker_packages"] = agent_info["docker_packages"]

        return policy

    def _integrate(self, run: dict) -> dict:
        """Merge results and run tests."""
        results = run.get("agent_results", [])
        all_files = []
        all_code = []

        for r in results:
            res = r.get("result", {})
            all_files.extend(res.get("files_changed", []))
            code = res.get("code", "")
            if code:
                all_code.append(code)

        return {
            "status": "completed",
            "files_changed": list(set(all_files)),
            "total_tasks": len(results),
            "completed_tasks": sum(
                1 for r in results
                if r.get("result", {}).get("status") == "completed"
            ),
            "combined_diff_preview": "\n---\n".join(all_code[:5])[:4000],
        }

    def _finalize(self, run: dict, feedback: str = "") -> None:
        """Finalize the build. Store feedback in vector memory."""
        try:
            from src.memory.vector_store import vector_memory

            summary = (
                f"BUILD COMPLETED: {run['solution_name']}\n"
                f"Product: {run['product_description'][:200]}\n"
                f"Tasks: {len(run.get('plan', []))}\n"
                f"Critic scores: {json.dumps([r.get('result', {}).get('final_score', 0) for r in run.get('critic_reports', [])])}\n"
                f"Human feedback: {feedback[:200]}"
            )
            vector_memory.add_feedback(
                summary,
                metadata={
                    "type": "build_completion",
                    "solution": run["solution_name"],
                    "source": "BuildOrchestrator",
                },
            )
        except Exception as exc:
            self.logger.debug("Finalize vector store failed (non-fatal): %s", exc)

    # ------------------------------------------------------------------
    # Critic integration
    # ------------------------------------------------------------------

    def _revise_plan(self, plan: list, review: dict) -> list:
        """
        Revision function for the actor-critic loop.

        Takes the current plan and critic review, asks the LLM to produce
        a revised plan addressing the critic's feedback. Returns the
        revised plan (list of task dicts).
        """
        from src.core.llm_gateway import llm_gateway

        flaws = review.get("flaws", [])
        suggestions = review.get("suggestions", [])
        missing = review.get("missing", [])
        score = review.get("score", 0)

        feedback_lines = []
        if flaws:
            feedback_lines.append("Flaws identified:\n" + "\n".join(f"- {f}" for f in flaws))
        if suggestions:
            feedback_lines.append("Suggestions:\n" + "\n".join(f"- {s}" for s in suggestions))
        if missing:
            feedback_lines.append("Missing elements:\n" + "\n".join(f"- {m}" for m in missing))

        prompt = (
            f"You are revising a build plan that scored {score}/100.\n\n"
            f"Critic feedback:\n{'\\n'.join(feedback_lines)}\n\n"
            f"Current plan ({len(plan)} tasks):\n"
            f"{json.dumps(plan[:30], indent=2, default=str)[:6000]}\n\n"
            f"Revise the plan to address the critic's feedback. "
            f"Return ONLY a JSON array of task objects. Each task must have: "
            f"step, task_type, description, agent_role, depends_on, acceptance_criteria.\n"
            f"Keep existing good tasks. Add missing ones. Fix flawed ones."
        )

        try:
            response = llm_gateway.generate(
                prompt,
                "You are a build planner that outputs valid JSON arrays of task objects.",
                trace_name="build.revise_plan",
            )
            # Parse JSON array from response
            import re
            response = response.replace("```json", "").replace("```", "").strip()
            arr_match = re.search(r'\[[\s\S]*\]', response)
            if arr_match:
                revised = json.loads(arr_match.group(0))
                if isinstance(revised, list) and len(revised) > 0:
                    self.logger.info(
                        "Plan revised: %d → %d tasks",
                        len(plan), len(revised),
                    )
                    return revised
        except Exception as exc:
            self.logger.warning("Plan revision failed: %s", exc)

        return plan  # Return unchanged if revision fails

    def _critic_review_plan(self, run: dict) -> dict:
        """
        Review and Critique pattern with bounded evaluation and revision loop.

        The critic evaluates the plan against:
        1. Completeness: does it cover all necessary components?
        2. Dependencies: are they correctly declared?
        3. Acceptance criteria: are they concrete and testable?
        4. Agent routing: are tasks assigned to appropriate specialists?

        When the score is below threshold, the revise_fn is called to
        improve the plan before the next critic iteration.
        """
        try:
            from src.agents.critic import critic_agent

            # Build structured context for bounded evaluation
            criteria_summary = []
            for task in run.get("plan", []):
                ac = task.get("acceptance_criteria", [])
                criteria_summary.append(
                    f"{task.get('task_type', '?')}: {', '.join(ac[:3])}"
                )

            context = (
                f"Evaluate this plan against these criteria:\n"
                f"1. Does it cover all components needed for: {run['product_description'][:200]}?\n"
                f"2. Are dependencies correctly declared (no circular deps)?\n"
                f"3. Are acceptance criteria concrete and testable?\n"
                f"4. Are agent roles appropriate for each task type?\n\n"
                f"Task acceptance criteria:\n" + "\n".join(criteria_summary[:20])
            )

            # Closure captures run so revised plans update the run in-place
            def _revise_and_update(plan, review):
                revised = self._revise_plan(plan, review)
                if revised is not plan:
                    run["plan"] = revised
                return revised

            result = critic_agent.review_with_loop(
                review_fn="plan",
                artifact=run["plan"],
                description=run["product_description"],
                threshold=run.get("critic_threshold", 70),
                max_iterations=3,
                revise_fn=_revise_and_update,
            )

            self.logger.info(
                "Critic plan review: %d iterations, final score %d",
                result.get("iterations", 1),
                result.get("final_score", 0),
            )

            return result
        except Exception as exc:
            self.logger.warning("Critic plan review failed: %s", exc)
            return {"passed": False, "critic_error": True, "final_score": 0, "error": str(exc), "history": []}

    def _critic_review_code(self, run: dict) -> dict:
        """Run critic on agent code outputs."""
        try:
            from src.agents.critic import critic_agent

            all_code = []
            for r in run.get("agent_results", []):
                code = r.get("result", {}).get("code", "")
                if code:
                    all_code.append(f"## {r.get('task', {}).get('description', '')}\n{code}")

            combined = "\n\n".join(all_code)[:8000]
            if not combined:
                return {"passed": True, "final_score": 100, "history": [], "note": "No code to review"}

            return critic_agent.review_with_loop(
                review_fn="code",
                artifact=combined,
                description=run["product_description"],
                threshold=run.get("critic_threshold", 70),
                max_iterations=2,
            )
        except Exception as exc:
            self.logger.warning("Critic code review failed: %s", exc)
            return {"passed": False, "critic_error": True, "final_score": 0, "error": str(exc), "history": []}

    def _critic_review_integration(self, run: dict) -> dict:
        """Run critic on integration results."""
        try:
            from src.agents.critic import critic_agent

            integration = run.get("integration_result", {})
            return critic_agent.review_with_loop(
                review_fn="integration",
                artifact=integration.get("combined_diff_preview", ""),
                description=run["product_description"],
                threshold=run.get("critic_threshold", 70),
                max_iterations=2,
            )
        except Exception as exc:
            self.logger.warning("Critic integration review failed: %s", exc)
            return {"passed": False, "critic_error": True, "final_score": 0, "error": str(exc), "history": []}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_summary(self, run: dict) -> dict:
        """Return a summary dict suitable for API responses."""
        critic_scores = []
        for report in run.get("critic_reports", []):
            result = report.get("result", {})
            critic_scores.append({
                "phase": report.get("phase", ""),
                "score": result.get("final_score", 0),
                "passed": result.get("passed", False),
                "iterations": result.get("iterations", 0),
            })

        return {
            "run_id": run["run_id"],
            "solution_name": run["solution_name"],
            "state": run["state"],
            "state_description": STATES.get(run["state"], ""),
            "created_at": run["created_at"],
            "updated_at": run["updated_at"],
            "product_description": run["product_description"],
            "hitl_level": run.get("hitl_level", "standard"),
            "hitl_gates": run.get("hitl_gates", []),
            "plan": run.get("plan", []),
            "task_count": len(run.get("plan", [])),
            "critic_scores": critic_scores,
            "critic_reports": run.get("critic_reports", []),
            "agent_results": [
                {
                    "task_type": r.get("task", {}).get("task_type", ""),
                    "description": r.get("task", {}).get("description", ""),
                    "status": r.get("result", {}).get("status", "unknown"),
                    "tier": r.get("result", {}).get("tier", ""),
                    "step": r.get("step", 0),
                    "wave": r.get("wave", 0),
                    "agent_role": r.get("agent_role", ""),
                    "acceptance_criteria": r.get("task", {}).get("acceptance_criteria", []),
                    "error": r.get("result", {}).get("error", ""),
                    "files_changed": r.get("result", {}).get("files_changed", []),
                }
                for r in run.get("agent_results", [])
            ],
            "integration_result": run.get("integration_result"),
            "phase_durations": run.get("phase_durations", {}),
            **({"error": run["error"]} if run.get("error") else {}),
        }

    def _audit(self, run_id: str, action: str, content: str) -> None:
        """Write build event to audit log."""
        try:
            from src.memory.audit_logger import audit_logger

            audit_logger.log_event(
                actor="BuildOrchestrator",
                action_type=action,
                input_context=f"run_id={run_id}",
                output_content=content[:500],
                metadata={"run_id": run_id},
            )
        except Exception as exc:
            self.logger.debug("Audit failed (non-fatal): %s", exc)


# Module-level singleton
build_orchestrator = BuildOrchestrator()

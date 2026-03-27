"""
SAGE Framework — OpenDoc (Documentation/Compliance) Runner
============================================================
Domain-specific execution for document creation and regulatory compliance.

Workflow: research → outline → draft → cross-reference → validate → publish

Differs from OpenSWE because:
  - Artifacts are documents (Markdown, LaTeX, PDF), not code
  - Verification is template/standard compliance, not test suites
  - Cross-referencing (requirements <-> tests <-> risks) is the hard problem
  - Regulatory standards have legally binding clause coverage requirements

Roles: technical_writer, regulatory_specialist, legal_advisor,
       safety_engineer, business_analyst, financial_analyst, analyst
Docker: sage/doc-toolchain:latest (lightweight)
"""

import logging

from src.integrations.base_runner import (
    BaseRunner, RunResult, VerificationReport, VerificationFinding,
    VerificationSeverity, Exercise, ExerciseScore,
    register_runner, DOC_ROLES,
)

logger = logging.getLogger("Runner.opendoc")


class OpenDocRunner(BaseRunner):
    """Documentation and compliance execution runner."""

    def __init__(self):
        super().__init__(
            name="opendoc",
            roles=list(DOC_ROLES),
            docker_image="sage/doc-toolchain:latest",
        )

    def execute(self, task, workspace, sandbox_handle=None):
        run_id = self._new_run_id()
        try:
            description = task.get("description", "")
            task_type = task.get("task_type", "DOCUMENTATION")
            agent_role = task.get("agent_role", "technical_writer")

            from src.core.llm_gateway import llm_gateway

            role_prompts = {
                "regulatory_specialist": (
                    "You are a senior regulatory affairs specialist.\n"
                    "Generate compliance documents following applicable standards (ISO, IEC, FDA).\n"
                    "Include traceability matrices, risk assessments, and standard clause coverage.\n"
                ),
                "legal_advisor": (
                    "You are a legal advisor specializing in technology companies.\n"
                    "Generate legally sound documents: ToS, privacy policies, license reviews.\n"
                    "Reference applicable regulations (GDPR, CCPA, HIPAA) where relevant.\n"
                ),
                "safety_engineer": (
                    "You are a functional safety engineer (ISO 26262, IEC 61508, ISO 14971).\n"
                    "Generate safety analysis documents: FMEA, fault trees, safety cases.\n"
                    "Include severity/occurrence/detection ratings and risk priority numbers.\n"
                ),
                "financial_analyst": (
                    "You are a financial analyst specializing in tech startups.\n"
                    "Generate financial models, pricing analyses, and unit economics.\n"
                    "Include assumptions, sensitivity analysis, and scenario planning.\n"
                ),
                "business_analyst": (
                    "You are a business analyst.\n"
                    "Generate requirements documents, user stories, and process flows.\n"
                    "Use standard formats (Given-When-Then, INVEST criteria).\n"
                ),
                "analyst": (
                    "You are a technical analyst.\n"
                    "Generate analysis reports with root cause analysis and recommendations.\n"
                    "Include data-driven findings and actionable next steps.\n"
                ),
            }

            base_prompt = role_prompts.get(agent_role, (
                "You are a senior technical writer.\n"
                "Generate well-structured documentation with clear sections.\n"
                "Include examples, diagrams descriptions, and cross-references.\n"
            ))

            system_prompt = (
                f"{base_prompt}\n"
                "Output as JSON: {\"files\": [{\"path\": \"...\", \"content\": \"...\"}], "
                "\"sections_count\": N, \"word_count\": N, "
                "\"references\": [\"...\"], \"standard_clauses_covered\": []}\n"
            )

            response = llm_gateway.generate_for_task(
                task_type=task_type,
                prompt=f"Task: {description}\nRole: {agent_role}",
                system_prompt=system_prompt,
                trace_name=f"opendoc.{agent_role}",
            )

            files_changed = []
            metrics = {}
            try:
                import json
                start = response.find("{")
                end = response.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(response[start:end])
                    files_changed = [f["path"] for f in parsed.get("files", [])]
                    metrics["sections_count"] = parsed.get("sections_count", 0)
                    metrics["word_count"] = parsed.get("word_count", 0)
                    metrics["references"] = parsed.get("references", [])
                    clauses = parsed.get("standard_clauses_covered", [])
                    metrics["standard_clauses_covered"] = clauses
            except Exception:
                pass

            return self._make_result(
                run_id=run_id, status="completed", tier="direct",
                output=response, files_changed=files_changed,
                artifacts=[{"path": f, "type": "document"} for f in files_changed],
                metrics=metrics,
            )
        except Exception as exc:
            self.logger.error("OpenDoc execute failed: %s", exc)
            return self._make_error(run_id, str(exc))

    def verify(self, result, task):
        findings = []
        score = 30.0

        if result.status == "error":
            return VerificationReport(passed=False, score=0.0, findings=[
                VerificationFinding("execution", VerificationSeverity.ERROR, "Failed"),
            ])

        metrics = result.metrics or {}

        # Section completeness
        sections_complete = metrics.get("sections_complete", metrics.get("sections_count", 0))
        sections_required = metrics.get("sections_required", 0)
        if sections_required > 0 and sections_complete > 0:
            ratio = sections_complete / sections_required
            score += ratio * 25
            if ratio >= 1.0:
                findings.append(VerificationFinding(
                    "completeness", VerificationSeverity.PASS,
                    f"All {sections_required} sections complete",
                ))
            else:
                findings.append(VerificationFinding(
                    "completeness", VerificationSeverity.WARNING,
                    f"{sections_complete}/{sections_required} sections complete",
                ))

        # Standard coverage for regulatory docs
        coverage_pct = metrics.get("standard_coverage_pct")
        if coverage_pct is not None:
            if coverage_pct >= 90:
                score += 20
                findings.append(VerificationFinding(
                    "standard_coverage", VerificationSeverity.PASS,
                    f"Standard coverage: {coverage_pct}%",
                ))
            elif coverage_pct >= 70:
                score += 10
                findings.append(VerificationFinding(
                    "standard_coverage", VerificationSeverity.WARNING,
                    f"Standard coverage: {coverage_pct}% — gaps need review",
                ))
            else:
                findings.append(VerificationFinding(
                    "standard_coverage", VerificationSeverity.ERROR,
                    f"Standard coverage only {coverage_pct}%",
                ))

        # Files produced
        if result.files_changed or result.artifacts:
            score += 15

        # Document content quality
        output_lower = (result.output or "").lower()
        doc_kws = ["section", "requirement", "reference", "appendix", "summary", "scope", "purpose"]
        if sum(1 for k in doc_kws if k in output_lower) >= 2:
            score += 10

        score = min(score, 100.0)
        return VerificationReport(passed=score >= 40.0, score=score, findings=findings, metrics=metrics)

    def get_toolchain(self):
        return {
            "runner": self.name, "docker_image": self.docker_image,
            "roles": self.roles,
            "tools": ["markdown", "latex", "pandoc", "jinja2", "vale"],
            "packages": ["pandoc", "texlive-base", "vale", "python3-jinja2"],
        }

    def get_workflow(self):
        return [
            {"step": 1, "name": "research", "description": "Research context, standards, and prior documents"},
            {"step": 2, "name": "outline", "description": "Create document outline from template"},
            {"step": 3, "name": "draft", "description": "Draft document content"},
            {"step": 4, "name": "write", "description": "Write full document sections"},
            {"step": 5, "name": "cross_reference", "description": "Validate cross-references and traceability"},
            {"step": 6, "name": "validate", "description": "Check template compliance and standard coverage"},
            {"step": 7, "name": "publish", "description": "Generate final output (PDF/HTML)"},
        ]

    def get_experience_keys(self):
        return ["task_type", "document_type", "standard", "audience", "domain"]

    def get_exercises(self, difficulty="intermediate"):
        """Load from central catalog (~50 opendoc seeds), fall back to hardcoded."""
        catalog = self._load_catalog_exercises(difficulty)
        if catalog:
            return catalog
        fallback = {
            "beginner": [
                Exercise(id="doc-b01", role="technical_writer", task_type="DOCUMENTATION",
                         difficulty="beginner",
                         description="Write a quickstart guide for a REST API with authentication",
                         acceptance_criteria=["Installation section", "Auth example", "First API call"],
                         expected_artifacts=["quickstart.md"], tags=["api", "quickstart"]),
            ],
            "intermediate": [
                Exercise(id="doc-i01", role="regulatory_specialist", task_type="REGULATORY",
                         difficulty="intermediate",
                         description="Create an ISO 14971 risk management plan for a patient monitoring device",
                         acceptance_criteria=["ISO 14971 sections", "Risk acceptability", "FMEA template"],
                         expected_artifacts=["risk_management_plan.md"], tags=["iso-14971", "medical"]),
            ],
            "advanced": [
                Exercise(id="doc-a01", role="regulatory_specialist", task_type="REGULATORY",
                         difficulty="advanced",
                         description="Prepare a 510(k) pre-submission package for an AI diagnostic tool",
                         acceptance_criteria=["Predicate comparison", "IEC 62304 classification", "Traceability"],
                         expected_artifacts=["presubmission.md", "traceability.md"], tags=["510k", "fda"]),
            ],
        }
        return fallback.get(difficulty, fallback["intermediate"])

    def grade_exercise(self, exercise, result):
        """Structural checks (40%) + LLM-as-judge (60%)."""
        score = 0.0
        criteria = {}
        hints = []

        if result.status == "completed":
            score += 20
            criteria["execution_success"] = True

        # Document structure
        output_lower = (result.output or "").lower()
        doc_kws = ["section", "requirement", "criteria", "scope", "purpose",
                    "reference", "appendix", "revision", "approval", "traceability"]
        kw_hits = sum(1 for k in doc_kws if k in output_lower)
        if kw_hits >= 3:
            score += 20
            criteria["structured_content"] = True
        else:
            hints.append("Include clear section headers and structured content")

        # Word count (substance check)
        word_count = result.metrics.get("word_count", 0) or len((result.output or "").split())
        if word_count > 500:
            score += 15
            criteria["sufficient_depth"] = True
        elif word_count > 100:
            score += 10
            criteria["sufficient_content"] = True
        else:
            hints.append("Provide more detailed content")

        # Compliance/regulatory patterns
        reg_kws = ["iso", "iec", "fda", "compliance", "audit", "risk", "hazard",
                    "dhf", "dhr", "verification", "validation", "capa"]
        if sum(1 for k in reg_kws if k in output_lower) >= 2:
            score += 15
            criteria["regulatory_awareness"] = True

        # Cross-referencing
        if any(k in output_lower for k in ["cross-reference", "traceability", "trace matrix", "req-"]):
            score += 10
            criteria["cross_references"] = True

        if result.verification and result.verification.passed:
            score += 15
            criteria["verification_passed"] = True

        return self._combined_grade(
            exercise, result, min(score, 100.0), criteria, hints,
            domain_context=(
                "Grade as a senior technical writer / regulatory specialist. Check for:\n"
                "- Document follows the relevant standard's required structure\n"
                "- Content is specific and actionable, not generic boilerplate\n"
                "- Traceability to requirements / design inputs\n"
                "- Proper revision control and approval blocks\n"
                "- Regulatory language accuracy (e.g., correct FDA terminology)"
            ),
        )


_runner = OpenDocRunner()
register_runner(_runner)

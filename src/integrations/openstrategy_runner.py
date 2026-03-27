"""
SAGE Framework — OpenStrategy (Strategy/Planning) Runner
=========================================================
Domain-specific execution for product strategy, marketing, and operations.

Workflow: analyze context → research → apply framework → draft strategy → validate → action plan

Roles: product_manager, marketing_strategist, operations_manager
Docker: none needed (LLM-native tasks)
"""

import logging

from src.integrations.base_runner import (
    BaseRunner, RunResult, VerificationReport, VerificationFinding,
    VerificationSeverity, Exercise, ExerciseScore,
    register_runner, STRATEGY_ROLES,
)

logger = logging.getLogger("Runner.openstrategy")


class OpenStrategyRunner(BaseRunner):
    """Strategy and planning execution runner."""

    def __init__(self):
        super().__init__(
            name="openstrategy",
            roles=list(STRATEGY_ROLES),
            docker_image="",
        )

    def execute(self, task, workspace, sandbox_handle=None):
        run_id = self._new_run_id()
        try:
            description = task.get("description", "")
            task_type = task.get("task_type", "PRODUCT_STRATEGY")
            agent_role = task.get("agent_role", "product_manager")

            from src.core.llm_gateway import llm_gateway

            role_prompts = {
                "product_manager": (
                    "You are a senior product manager.\n"
                    "Generate product strategy artifacts: PRDs, roadmaps, prioritization.\n"
                    "Use frameworks: RICE scoring, MoSCoW, user story mapping.\n"
                ),
                "marketing_strategist": (
                    "You are a senior marketing strategist.\n"
                    "Generate market analysis, GTM strategy, positioning, content plans.\n"
                    "Use frameworks: TAM/SAM/SOM, SWOT, competitive matrix.\n"
                ),
                "operations_manager": (
                    "You are a senior operations manager.\n"
                    "Generate runbooks, SLA definitions, incident playbooks, capacity plans.\n"
                    "Include measurable KPIs and escalation procedures.\n"
                ),
            }

            system_prompt = (
                f"{role_prompts.get(agent_role, role_prompts['product_manager'])}\n"
                "Output as JSON: {\"files\": [{\"path\": \"...\", \"content\": \"...\"}], "
                "\"framework_used\": \"...\", "
                "\"sections\": [\"...\"], \"action_items\": [\"...\"]}\n"
            )

            response = llm_gateway.generate_for_task(
                task_type=task_type,
                prompt=f"Task: {description}\nRole: {agent_role}",
                system_prompt=system_prompt,
                trace_name=f"openstrategy.{agent_role}",
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
                    metrics["framework_used"] = parsed.get("framework_used", "")
                    metrics["sections"] = parsed.get("sections", [])
                    metrics["action_items"] = parsed.get("action_items", [])
                    metrics["framework_sections_complete"] = len(parsed.get("sections", []))
                    metrics["framework_sections_total"] = len(parsed.get("sections", []))
            except Exception:
                pass

            return self._make_result(
                run_id=run_id, status="completed", tier="direct",
                output=response, files_changed=files_changed,
                artifacts=[{"path": f, "type": "document"} for f in files_changed],
                metrics=metrics,
            )
        except Exception as exc:
            self.logger.error("OpenStrategy execute failed: %s", exc)
            return self._make_error(run_id, str(exc))

    def verify(self, result, task):
        findings = []
        score = 30.0

        if result.status == "error":
            return VerificationReport(passed=False, score=0.0, findings=[
                VerificationFinding("execution", VerificationSeverity.ERROR, "Failed"),
            ])

        metrics = result.metrics or {}

        # Framework completeness
        complete = metrics.get("framework_sections_complete", 0)
        total = metrics.get("framework_sections_total", 0)
        if total > 0:
            ratio = complete / total
            score += ratio * 25
            if ratio >= 0.8:
                findings.append(VerificationFinding(
                    "framework_completeness", VerificationSeverity.PASS,
                    f"Framework {complete}/{total} sections complete",
                ))

        # Action items present
        actions = metrics.get("action_items", [])
        if actions:
            score += 15
            findings.append(VerificationFinding(
                "actionable", VerificationSeverity.PASS,
                f"{len(actions)} action items defined",
            ))

        # Files produced
        if result.files_changed or result.artifacts:
            score += 15

        # Strategy keywords
        output_lower = (result.output or "").lower()
        strat_kws = ["market", "customer", "revenue", "roadmap", "priority", "metric", "kpi",
                      "strategy", "analysis", "action", "plan"]
        if sum(1 for k in strat_kws if k in output_lower) >= 3:
            score += 15

        score = min(score, 100.0)
        return VerificationReport(passed=score >= 40.0, score=score, findings=findings, metrics=metrics)

    def get_toolchain(self):
        return {
            "runner": self.name, "docker_image": self.docker_image,
            "roles": self.roles,
            "tools": ["analysis_templates", "spreadsheet", "data_query", "chart_builder"],
            "packages": [],
        }

    def get_workflow(self):
        return [
            {"step": 1, "name": "analyze", "description": "Analyze current context and constraints"},
            {"step": 2, "name": "research", "description": "Research market, competitors, or operations data"},
            {"step": 3, "name": "framework", "description": "Apply strategic framework (RICE, SWOT, TAM)"},
            {"step": 4, "name": "plan", "description": "Draft strategy document"},
            {"step": 5, "name": "validate", "description": "Validate assumptions and feasibility"},
            {"step": 6, "name": "action_plan", "description": "Create actionable next steps"},
        ]

    def get_experience_keys(self):
        return ["task_type", "industry", "stage", "framework_type", "domain"]

    def get_exercises(self, difficulty="intermediate"):
        """Load from central catalog (~45 openstrategy seeds), fall back to hardcoded."""
        catalog = self._load_catalog_exercises(difficulty)
        if catalog:
            return catalog
        fallback = {
            "beginner": [
                Exercise(id="strat-b01", role="product_manager", task_type="PRODUCT_STRATEGY",
                         difficulty="beginner",
                         description="Prioritize 5 features for a SaaS dashboard using RICE scoring",
                         acceptance_criteria=["RICE framework used", "Priority ranking", "Rationale per feature"],
                         expected_artifacts=["prioritization.md"], tags=["rice", "prioritization"]),
            ],
            "intermediate": [
                Exercise(id="strat-i01", role="product_manager", task_type="PRODUCT_STRATEGY",
                         difficulty="intermediate",
                         description="Write a PRD for a mobile app notification system with personalization",
                         acceptance_criteria=["Problem statement", "OKRs", "User stories", "Launch plan"],
                         expected_artifacts=["prd.md"], tags=["prd", "mobile"]),
            ],
            "advanced": [
                Exercise(id="strat-a01", role="product_manager", task_type="PRODUCT_STRATEGY",
                         difficulty="advanced",
                         description="Create a GTM strategy for an AI developer tool in enterprise market",
                         acceptance_criteria=["TAM/SAM/SOM", "Buyer personas", "Pricing tiers", "12-month roadmap"],
                         expected_artifacts=["gtm_strategy.md", "roadmap.md"], tags=["gtm", "enterprise"]),
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

        # Strategic vocabulary
        output_lower = (result.output or "").lower()
        strat_kws = ["market", "customer", "revenue", "priority", "metric", "strategy",
                      "plan", "competitor", "segment", "persona", "pricing", "roadmap"]
        kw_hits = sum(1 for k in strat_kws if k in output_lower)
        if kw_hits >= 4:
            score += 20
            criteria["strategy_vocabulary"] = True
        elif kw_hits >= 2:
            score += 10

        # Framework usage
        framework_kws = ["rice", "tam", "sam", "som", "swot", "porter", "okr",
                         "jtbd", "jobs to be done", "value proposition", "canvas"]
        if sum(1 for k in framework_kws if k in output_lower) >= 1:
            score += 15
            criteria["uses_frameworks"] = True
        else:
            hints.append("Apply recognized strategic frameworks (RICE, SWOT, TAM/SAM/SOM)")

        # Actionability
        action_kws = ["action", "next step", "timeline", "milestone", "deliverable",
                       "owner", "deadline", "kpi", "success metric"]
        if sum(1 for k in action_kws if k in output_lower) >= 2:
            score += 15
            criteria["actionable"] = True
        else:
            hints.append("Include concrete, actionable next steps with owners and timelines")

        # Data-driven (numbers, metrics)
        import re
        numbers = re.findall(r'\b\d+[%$KMB]?\b', result.output or "")
        if len(numbers) >= 3:
            score += 10
            criteria["data_driven"] = True
        else:
            hints.append("Support claims with data points and quantified metrics")

        # Depth
        word_count = len((result.output or "").split())
        if word_count > 300:
            score += 10
            criteria["sufficient_depth"] = True

        if result.verification and result.verification.passed:
            score += 10
            criteria["verification_passed"] = True

        return self._combined_grade(
            exercise, result, min(score, 100.0), criteria, hints,
            domain_context=(
                "Grade as a senior product strategist / PM. Check for:\n"
                "- Use of recognized frameworks (RICE, SWOT, Porter's, TAM/SAM/SOM)\n"
                "- Data-driven reasoning with quantified metrics\n"
                "- Clear actionability: who does what by when\n"
                "- Customer empathy and market awareness\n"
                "- Realistic assumptions and risk acknowledgment"
            ),
        )


_runner = OpenStrategyRunner()
register_runner(_runner)

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
        exercises = {
            "beginner": [
                Exercise(
                    id="strat-b01", role="product_manager", task_type="PRODUCT_STRATEGY",
                    difficulty="beginner",
                    description="Prioritize 5 features for a SaaS dashboard using RICE scoring",
                    acceptance_criteria=[
                        "Uses RICE framework (Reach, Impact, Confidence, Effort)",
                        "Has actionable priority ranking",
                        "Each feature scored with rationale",
                        "Final recommendation with reasoning",
                    ],
                    expected_artifacts=["prioritization.md"],
                    tags=["rice", "prioritization", "saas"],
                ),
                Exercise(
                    id="strat-b02", role="marketing_strategist", task_type="MARKETING",
                    difficulty="beginner",
                    description="Create a competitive analysis for a developer tools startup",
                    acceptance_criteria=[
                        "Identifies at least 3 competitors",
                        "Uses structured comparison (features, pricing, positioning)",
                        "Has actionable differentiation recommendations",
                        "Includes market positioning map",
                    ],
                    expected_artifacts=["competitive_analysis.md"],
                    tags=["competitive", "devtools"],
                ),
            ],
            "intermediate": [
                Exercise(
                    id="strat-i01", role="product_manager", task_type="PRODUCT_STRATEGY",
                    difficulty="intermediate",
                    description="Write a PRD for a mobile app notification system with personalization",
                    acceptance_criteria=[
                        "Problem statement with user data",
                        "Success metrics (OKRs)",
                        "User stories with acceptance criteria",
                        "Technical constraints section",
                        "Launch plan with phases",
                    ],
                    expected_artifacts=["prd.md", "user_stories.md"],
                    tags=["prd", "mobile", "notifications"],
                ),
            ],
            "advanced": [
                Exercise(
                    id="strat-a01", role="product_manager", task_type="PRODUCT_STRATEGY",
                    difficulty="advanced",
                    description="Create a complete GTM strategy for launching an AI developer tool in enterprise market",
                    acceptance_criteria=[
                        "TAM/SAM/SOM analysis",
                        "Buyer persona definitions",
                        "Pricing strategy with tiers",
                        "Sales motion (PLG vs enterprise)",
                        "12-month launch roadmap",
                        "Success metrics and milestones",
                    ],
                    expected_artifacts=["gtm_strategy.md", "pricing.md", "roadmap.md"],
                    tags=["gtm", "enterprise", "ai", "advanced"],
                ),
            ],
        }
        return exercises.get(difficulty, exercises["intermediate"])

    def grade_exercise(self, exercise, result):
        score = 0.0
        criteria_results = {}
        hints = []

        if result.status == "completed":
            score += 20
            criteria_results["execution_success"] = True

        expected = set(exercise.expected_artifacts)
        produced = set(result.files_changed) | {a.get("path", "") for a in result.artifacts}
        match = len(expected & produced) / max(len(expected), 1)
        score += match * 25
        criteria_results["artifacts_match"] = match >= 0.5

        metrics = result.metrics or {}
        if metrics.get("action_items"):
            score += 15
            criteria_results["has_actions"] = True
        else:
            hints.append("Include concrete, actionable next steps")

        output_lower = (result.output or "").lower()
        strat_kws = ["market", "customer", "revenue", "priority", "metric", "strategy", "plan"]
        if sum(1 for k in strat_kws if k in output_lower) >= 3:
            score += 20
            criteria_results["strategy_patterns"] = True

        if result.verification and result.verification.passed:
            score += 10

        score = min(score, 100.0)
        return ExerciseScore(
            exercise_id=exercise.id, passed=score >= 50, score=score,
            criteria_results=criteria_results,
            feedback="Good strategic thinking" if score >= 70 else "Strengthen frameworks and actionability",
            improvement_hints=hints,
        )


_runner = OpenStrategyRunner()
register_runner(_runner)

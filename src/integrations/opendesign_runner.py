"""
SAGE Framework — OpenDesign (UX/Design) Runner
================================================
Domain-specific execution for UX design and accessibility.

Workflow: research → wireframe → prototype → accessibility audit → design token export

Differs from OpenSWE because:
  - Artifacts are visual (wireframes, SVGs, design tokens), not code
  - Verification includes WCAG accessibility and human perception rules
  - Touch targets, contrast ratios, and spacing are measurable acceptance criteria
  - Design systems require consistency across components

Roles: ux_designer
Docker: sage/design-toolchain:latest
"""

import logging

from src.integrations.base_runner import (
    BaseRunner, RunResult, VerificationReport, VerificationFinding,
    VerificationSeverity, Exercise, ExerciseScore,
    register_runner, DESIGN_ROLES,
)

logger = logging.getLogger("Runner.opendesign")


class OpenDesignRunner(BaseRunner):
    """UX and design execution runner."""

    def __init__(self):
        super().__init__(
            name="opendesign",
            roles=list(DESIGN_ROLES),
            docker_image="sage/design-toolchain:latest",
        )

    def execute(self, task, workspace, sandbox_handle=None):
        run_id = self._new_run_id()
        try:
            description = task.get("description", "")
            task_type = task.get("task_type", "UI_DESIGN")

            from src.core.llm_gateway import llm_gateway

            system_prompt = (
                "You are a senior UX designer.\n"
                "Generate design artifacts following these rules:\n"
                "- WCAG 2.1 AA compliance minimum\n"
                "- Minimum touch target 44x44px\n"
                "- Color contrast ratio >= 4.5:1 for normal text\n"
                "- Consistent spacing using 8px grid\n"
                "- Include design tokens (JSON) for colors, spacing, typography\n"
                "- Describe wireframes in structured format\n\n"
                "Output as JSON: {\"files\": [{\"path\": \"...\", \"content\": \"...\"}], "
                "\"wcag_level\": \"AA\", \"components\": [\"...\"], "
                "\"design_tokens\": {\"colors\": {}, \"spacing\": {}, \"typography\": {}}}\n"
            )

            response = llm_gateway.generate_for_task(
                task_type=task_type,
                prompt=f"Task: {description}",
                system_prompt=system_prompt,
                trace_name="opendesign.generate",
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
                    metrics["wcag_level"] = parsed.get("wcag_level", "unknown")
                    metrics["components"] = parsed.get("components", [])
            except Exception:
                pass

            return self._make_result(
                run_id=run_id, status="completed", tier="direct",
                output=response, files_changed=files_changed, metrics=metrics,
            )
        except Exception as exc:
            self.logger.error("OpenDesign execute failed: %s", exc)
            return self._make_error(run_id, str(exc))

    def verify(self, result, task):
        findings = []
        score = 30.0

        if result.status == "error":
            return VerificationReport(passed=False, score=0.0, findings=[
                VerificationFinding("execution", VerificationSeverity.ERROR, "Failed"),
            ])

        metrics = result.metrics or {}

        # WCAG violations
        violations = metrics.get("wcag_violations", -1)
        if violations == 0:
            score += 25
            findings.append(VerificationFinding(
                "wcag", VerificationSeverity.PASS, "WCAG AA compliant — zero violations",
            ))
        elif violations > 0:
            findings.append(VerificationFinding(
                "wcag", VerificationSeverity.ERROR, f"{violations} WCAG violations",
            ))

        # Contrast ratio
        contrast = metrics.get("contrast_ratio_min")
        if isinstance(contrast, (int, float)):
            if contrast >= 4.5:
                score += 15
                findings.append(VerificationFinding(
                    "contrast", VerificationSeverity.PASS, f"Contrast: {contrast}:1",
                ))
            else:
                findings.append(VerificationFinding(
                    "contrast", VerificationSeverity.ERROR,
                    f"Contrast {contrast}:1 below 4.5:1 minimum",
                ))

        # Touch targets
        min_touch = metrics.get("min_touch_target")
        if isinstance(min_touch, (int, float)) and min_touch >= 44:
            score += 10
            findings.append(VerificationFinding(
                "touch_target", VerificationSeverity.PASS, f"Min touch: {min_touch}px",
            ))

        # Files produced
        if result.files_changed:
            score += 15

        # Design keywords
        output_lower = (result.output or "").lower()
        design_kws = ["wireframe", "component", "color", "spacing", "typography", "layout", "token"]
        if sum(1 for k in design_kws if k in output_lower) >= 2:
            score += 10

        score = min(score, 100.0)
        return VerificationReport(passed=score >= 40.0, score=score, findings=findings, metrics=metrics)

    def get_toolchain(self):
        return {
            "runner": self.name, "docker_image": self.docker_image,
            "roles": self.roles,
            "tools": ["svg_generator", "accessibility_checker", "token_generator", "wireframe_dsl"],
            "packages": ["axe-core", "pa11y", "svg-optimizer", "design-tokens-cli"],
        }

    def get_workflow(self):
        return [
            {"step": 1, "name": "research", "description": "Research user needs and platform patterns"},
            {"step": 2, "name": "wireframe", "description": "Create wireframe layouts"},
            {"step": 3, "name": "design", "description": "Design components and screens"},
            {"step": 4, "name": "prototype", "description": "Build interactive prototype"},
            {"step": 5, "name": "accessibility", "description": "Run WCAG accessibility audit"},
            {"step": 6, "name": "tokens", "description": "Export design tokens (colors, spacing, type)"},
        ]

    def get_experience_keys(self):
        return ["task_type", "platform", "screen_type", "component_type", "domain"]

    def get_exercises(self, difficulty="intermediate"):
        """Load from central catalog (~45 opendesign seeds), fall back to hardcoded."""
        catalog = self._load_catalog_exercises(difficulty)
        if catalog:
            return catalog
        fallback = {
            "beginner": [
                Exercise(id="design-b01", role="ux_designer", task_type="UI_DESIGN",
                         difficulty="beginner",
                         description="Design a button component system with primary, secondary, disabled states",
                         acceptance_criteria=["WCAG AA contrast", "44px touch targets", "Design tokens"],
                         expected_artifacts=["button.svg", "tokens.json"], tags=["component", "button"]),
            ],
            "intermediate": [
                Exercise(id="design-i01", role="ux_designer", task_type="UI_DESIGN",
                         difficulty="intermediate",
                         description="Design a mobile login flow with email, social login, password reset",
                         acceptance_criteria=["Wireframes for all screens", "WCAG AA", "Error states"],
                         expected_artifacts=["login_flow.svg", "tokens.json"], tags=["mobile", "auth"]),
            ],
            "advanced": [
                Exercise(id="design-a01", role="ux_designer", task_type="UI_DESIGN",
                         difficulty="advanced",
                         description="Design a complete design system with 10 components, dark/light themes",
                         acceptance_criteria=["10 components", "Dark/light tokens", "WCAG AA both themes"],
                         expected_artifacts=["design_system.md", "tokens_light.json"], tags=["design-system"]),
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

        # WCAG compliance
        metrics = result.metrics or {}
        if metrics.get("wcag_violations", -1) == 0:
            score += 20
            criteria["wcag_clean"] = True
        else:
            hints.append("Ensure all designs pass WCAG AA audit")

        # Touch targets
        if isinstance(metrics.get("min_touch_target"), (int, float)) and metrics["min_touch_target"] >= 44:
            score += 10
            criteria["touch_targets"] = True

        # Design patterns in output
        output_lower = (result.output or "").lower()
        design_kws = ["token", "color", "spacing", "component", "typography",
                       "grid", "breakpoint", "responsive", "state", "variant"]
        kw_hits = sum(1 for k in design_kws if k in output_lower)
        if kw_hits >= 3:
            score += 15
            criteria["design_patterns"] = True
        elif kw_hits >= 1:
            score += 8

        # Accessibility awareness
        a11y_kws = ["wcag", "aria", "contrast", "screen reader", "focus", "keyboard",
                     "alt text", "semantic", "accessible"]
        if sum(1 for k in a11y_kws if k in output_lower) >= 2:
            score += 15
            criteria["accessibility_aware"] = True
        else:
            hints.append("Address accessibility: WCAG, ARIA, keyboard navigation")

        # Design system structure
        system_kws = ["atomic", "molecule", "organism", "template", "page", "design system"]
        if sum(1 for k in system_kws if k in output_lower) >= 1:
            score += 10
            criteria["design_system_thinking"] = True

        if result.verification and result.verification.passed:
            score += 10
            criteria["verification_passed"] = True

        return self._combined_grade(
            exercise, result, min(score, 100.0), criteria, hints,
            domain_context=(
                "Grade as a senior UX designer. Check for:\n"
                "- WCAG 2.2 AA compliance (contrast, touch targets, keyboard nav)\n"
                "- Proper design token structure (colors, spacing, typography)\n"
                "- Responsive design considerations\n"
                "- User flow completeness (happy path + error states + loading)\n"
                "- Atomic design principles and component reusability"
            ),
        )


_runner = OpenDesignRunner()
register_runner(_runner)

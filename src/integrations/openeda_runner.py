"""
SAGE Framework — OpenEDA (Electronics Design) Runner
======================================================
Domain-specific execution for PCB design and electronics.

Workflow: requirements → schematic → ERC → layout → DRC → Gerbers → BOM

Differs from OpenSWE because:
  - Artifacts are KiCad projects, Gerber files, BOMs — not source code
  - Verification is DRC/ERC checks, not test suites
  - Component selection requires parametric database search
  - Output goes to fab houses, not git repos

Roles: pcb_designer
Docker: sage/pcb-toolchain:latest
"""

import logging

from src.integrations.base_runner import (
    BaseRunner, RunResult, VerificationReport, VerificationFinding,
    VerificationSeverity, Exercise, ExerciseScore,
    register_runner, EDA_ROLES,
)

logger = logging.getLogger("Runner.openeda")


class OpenEDARunner(BaseRunner):
    """PCB design and electronics execution runner."""

    def __init__(self):
        super().__init__(
            name="openeda",
            roles=list(EDA_ROLES),
            docker_image="sage/pcb-toolchain:latest",
        )

    def execute(self, task, workspace, sandbox_handle=None):
        run_id = self._new_run_id()
        try:
            description = task.get("description", "")
            task_type = task.get("task_type", "PCB_DESIGN")

            from src.core.llm_gateway import llm_gateway

            system_prompt = (
                "You are a senior PCB designer and electronics engineer.\n"
                "Generate EDA design artifacts following these rules:\n"
                "- KiCad format for schematics and layouts\n"
                "- Include BOM with manufacturer part numbers\n"
                "- Follow IPC standards for footprints\n"
                "- Include design rule specifications\n"
                "- Specify PCB stackup and impedance requirements\n\n"
                "Output as JSON: {\"files\": [{\"path\": \"...\", \"content\": \"...\"}], "
                "\"components\": N, \"layers\": N, \"board_area_mm2\": N, "
                "\"drc_rules\": {\"min_trace_mm\": N, \"min_clearance_mm\": N}}\n"
            )

            response = llm_gateway.generate_for_task(
                task_type=task_type,
                prompt=f"Task: {description}\nPayload: {task.get('payload', {})}",
                system_prompt=system_prompt,
                trace_name="openeda.generate",
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
                    metrics.update({
                        "components": parsed.get("components", 0),
                        "layers": parsed.get("layers", 2),
                        "board_area_mm2": parsed.get("board_area_mm2", 0),
                    })
            except Exception:
                pass

            return self._make_result(
                run_id=run_id, status="completed", tier="direct",
                output=response, files_changed=files_changed,
                metrics=metrics,
            )
        except Exception as exc:
            self.logger.error("OpenEDA execute failed: %s", exc)
            return self._make_error(run_id, str(exc))

    def verify(self, result, task):
        findings = []
        score = 30.0

        if result.status == "error":
            return VerificationReport(passed=False, score=0.0, findings=[
                VerificationFinding("execution", VerificationSeverity.ERROR, "Failed"),
            ])

        metrics = result.metrics or {}

        # DRC check
        drc_errors = metrics.get("drc_errors", -1)
        if drc_errors == 0:
            score += 25
            findings.append(VerificationFinding(
                "drc", VerificationSeverity.PASS, "DRC clean — zero errors",
            ))
        elif drc_errors > 0:
            findings.append(VerificationFinding(
                "drc", VerificationSeverity.ERROR, f"DRC: {drc_errors} errors",
            ))

        # ERC check
        erc_errors = metrics.get("erc_errors", -1)
        if erc_errors == 0:
            score += 20
            findings.append(VerificationFinding(
                "erc", VerificationSeverity.PASS, "ERC clean — all nets connected",
            ))
        elif erc_errors > 0:
            findings.append(VerificationFinding(
                "erc", VerificationSeverity.ERROR, f"ERC: {erc_errors} errors",
            ))

        # Unrouted nets
        unrouted = metrics.get("unrouted_nets", -1)
        if unrouted == 0:
            score += 10
        elif unrouted > 0:
            findings.append(VerificationFinding(
                "routing", VerificationSeverity.ERROR, f"{unrouted} unrouted nets",
            ))

        # Files produced
        if result.files_changed or result.artifacts:
            score += 15

        score = min(score, 100.0)
        return VerificationReport(passed=score >= 40.0, score=score, findings=findings, metrics=metrics)

    def get_toolchain(self):
        return {
            "runner": self.name, "docker_image": self.docker_image,
            "roles": self.roles,
            "tools": ["kicad", "kicad-cli", "gerber_viewer", "bom_manager"],
            "packages": ["kicad", "kicad-cli", "python3-kicad"],
        }

    def get_workflow(self):
        return [
            {"step": 1, "name": "requirements", "description": "Parse electrical requirements and constraints"},
            {"step": 2, "name": "schematic", "description": "Create schematic with symbol library"},
            {"step": 3, "name": "erc", "description": "Run Electrical Rule Check"},
            {"step": 4, "name": "layout", "description": "Place components and route traces"},
            {"step": 5, "name": "drc", "description": "Run Design Rule Check"},
            {"step": 6, "name": "design_rule_check", "description": "Verify clearances and trace widths"},
            {"step": 7, "name": "gerber", "description": "Generate Gerber and drill files"},
            {"step": 8, "name": "bom", "description": "Generate Bill of Materials"},
        ]

    def get_experience_keys(self):
        return ["task_type", "board_type", "layer_count", "domain"]

    def get_exercises(self, difficulty="intermediate"):
        exercises = {
            "beginner": [
                Exercise(
                    id="eda-b01", role="pcb_designer", task_type="PCB_DESIGN",
                    difficulty="beginner",
                    description="Design a simple LED circuit with resistor on a single-layer PCB",
                    acceptance_criteria=[
                        "Schematic has LED and current-limiting resistor",
                        "DRC clean with 0.2mm minimum clearance",
                        "ERC shows no unconnected pins",
                        "Gerber files generated",
                    ],
                    expected_artifacts=["led_circuit.kicad_sch", "led_circuit.kicad_pcb"],
                    tags=["basic", "single-layer"],
                ),
            ],
            "intermediate": [
                Exercise(
                    id="eda-i01", role="pcb_designer", task_type="PCB_DESIGN",
                    difficulty="intermediate",
                    description="Design a 2-layer Arduino shield with I2C and SPI connectors",
                    acceptance_criteria=[
                        "DRC clean", "ERC clean", "2-layer stackup",
                        "BOM complete with part numbers",
                        "Layout fits standard Arduino shield dimensions",
                    ],
                    expected_artifacts=["shield.kicad_sch", "shield.kicad_pcb", "bom.csv"],
                    tags=["arduino", "2-layer", "connectors"],
                ),
            ],
            "advanced": [
                Exercise(
                    id="eda-a01", role="pcb_designer", task_type="PCB_DESIGN",
                    difficulty="advanced",
                    description="Design a 4-layer USB-C power delivery board with ESD protection",
                    acceptance_criteria=[
                        "DRC clean", "ERC clean", "4-layer controlled impedance stackup",
                        "USB differential pair: 90 ohm impedance",
                        "ESD protection on all external connectors",
                        "Gerber output with drill files",
                    ],
                    expected_artifacts=["usb_pd.kicad_sch", "usb_pd.kicad_pcb", "stackup.txt", "bom.csv"],
                    tags=["usb-c", "4-layer", "impedance", "advanced"],
                ),
            ],
        }
        return exercises.get(difficulty, exercises["intermediate"])

    def grade_exercise(self, exercise, result):
        score = 0.0
        criteria_results = {}
        hints = []

        if result.status == "completed":
            score += 25
            criteria_results["execution_success"] = True

        # Artifacts
        expected = set(exercise.expected_artifacts)
        produced = set(result.files_changed) | {a.get("path", "") for a in result.artifacts}
        match = len(expected & produced) / max(len(expected), 1)
        score += match * 25
        criteria_results["artifacts_match"] = match >= 0.5

        # DRC/ERC metrics
        metrics = result.metrics or {}
        if metrics.get("drc_errors", -1) == 0:
            score += 20
            criteria_results["drc_clean"] = True
        else:
            criteria_results["drc_clean"] = False
            hints.append("Ensure DRC passes with zero errors")

        if metrics.get("erc_errors", -1) == 0:
            score += 15
            criteria_results["erc_clean"] = True

        # EDA keywords in output
        eda_kws = ["schematic", "pcb", "trace", "clearance", "component", "footprint", "net"]
        output_lower = (result.output or "").lower()
        if sum(1 for k in eda_kws if k in output_lower) >= 2:
            score += 15

        score = min(score, 100.0)
        return ExerciseScore(
            exercise_id=exercise.id, passed=score >= 50, score=score,
            criteria_results=criteria_results,
            feedback="Good PCB design" if score >= 70 else "Review EDA best practices",
            improvement_hints=hints,
        )


_runner = OpenEDARunner()
register_runner(_runner)

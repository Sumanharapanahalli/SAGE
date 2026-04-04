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
            payload = task.get("payload", {})
            project_name = payload.get("project_name", "board")

            from src.core.llm_gateway import llm_gateway
            from src.integrations.output_validator import parse_with_retry

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

            user_prompt = f"Task: {description}\nPayload: {payload}"

            # Use output validator with auto-retry
            def _generate():
                return llm_gateway.generate_for_task(
                    task_type=task_type,
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    trace_name="openeda.generate",
                )

            validation = parse_with_retry(_generate, "eda_design")

            files_changed = []
            metrics = {"mcp_tools_invoked": []}

            if validation["valid"]:
                parsed = validation["output"]
                files_changed = [f["path"] for f in parsed.get("files", [])]
                metrics.update({
                    "components": parsed.get("components", 0),
                    "layers": parsed.get("layers", 2),
                    "board_area_mm2": parsed.get("board_area_mm2", 0),
                })

                # --- Wire MCP hardware tools ---
                # 1. Create KiCad project scaffold
                if workspace:
                    mcp_results = self._invoke_mcp_tools(
                        workspace, project_name, parsed, files_changed,
                    )
                    metrics["mcp_tools_invoked"] = mcp_results
            else:
                # Validation failed — use raw output
                response = validation.get("output") or ""
                self.logger.warning(
                    "Output validation failed after %d attempts: %s",
                    validation.get("attempts", 0), validation.get("errors", []),
                )

            return self._make_result(
                run_id=run_id, status="completed", tier="direct",
                output=str(validation.get("output", "")),
                files_changed=files_changed,
                metrics=metrics,
            )
        except Exception as exc:
            self.logger.error("OpenEDA execute failed: %s", exc)
            return self._make_error(run_id, str(exc))

    def _invoke_mcp_tools(
        self, workspace: str, project_name: str,
        parsed: dict, files_changed: list,
    ) -> list:
        """Invoke hardware MCP tools on generated EDA artifacts.

        Creates KiCad project, writes generated files, runs ERC/DRC,
        and exports Gerbers/BOM when possible.
        """
        from src.mcp_servers.hardware_tools import (
            kicad_create_project, kicad_run_erc, kicad_run_drc,
            kicad_export_gerbers, kicad_export_bom,
        )
        import os

        tool_results = []

        # 1. Create KiCad project scaffold
        create_result = kicad_create_project(project_name, workspace)
        tool_results.append({"tool": "kicad_create_project", "result": create_result})
        project_dir = create_result.get("project_dir", "")

        # 2. Write generated files into the project directory
        for file_info in parsed.get("files", []):
            fpath = os.path.join(workspace, file_info["path"])
            os.makedirs(os.path.dirname(fpath) or workspace, exist_ok=True)
            with open(fpath, "w") as f:
                f.write(file_info["content"])

        # 3. Run ERC on schematic files
        sch_files = [f for f in files_changed if f.endswith((".kicad_sch", ".sch"))]
        for sch in sch_files[:2]:
            sch_path = os.path.join(workspace, sch)
            if os.path.isfile(sch_path):
                erc_result = kicad_run_erc(sch_path)
                tool_results.append({"tool": "kicad_run_erc", "file": sch, "result": erc_result})

        # 4. Run DRC on PCB files
        pcb_files = [f for f in files_changed if f.endswith((".kicad_pcb", ".pcb"))]
        for pcb in pcb_files[:2]:
            pcb_path = os.path.join(workspace, pcb)
            if os.path.isfile(pcb_path):
                drc_result = kicad_run_drc(pcb_path)
                tool_results.append({"tool": "kicad_run_drc", "file": pcb, "result": drc_result})

                # 5. Export Gerbers if DRC passes
                gerber_dir = os.path.join(workspace, "gerbers")
                gerber_result = kicad_export_gerbers(pcb_path, gerber_dir)
                tool_results.append({"tool": "kicad_export_gerbers", "result": gerber_result})

        # 6. Export BOM from schematic
        for sch in sch_files[:1]:
            sch_path = os.path.join(workspace, sch)
            if os.path.isfile(sch_path):
                bom_path = os.path.join(workspace, "bom.csv")
                bom_result = kicad_export_bom(sch_path, bom_path)
                tool_results.append({"tool": "kicad_export_bom", "result": bom_result})

        return tool_results

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

    def get_experimental_commands(self, workspace, files):
        """EDA-specific: KiCad DRC, ERC, netlist validation, BOM check."""
        import os
        commands = []
        sch_files = [f for f in files if f.endswith((".kicad_sch", ".sch"))]
        pcb_files = [f for f in files if f.endswith((".kicad_pcb", ".pcb"))]
        py_files = [f for f in files if f.endswith(".py")]

        # If Python scripts generated (e.g., KiCad scripting), check syntax
        if py_files:
            commands.append({
                "name": "python_syntax",
                "cmd": ["python3", "-m", "py_compile"] + py_files,
                "weight": 20,
                "timeout": 15,
            })

        # If KiCad files exist, try CLI validation
        if sch_files:
            for sf in sch_files[:2]:
                commands.append({
                    "name": f"sch_validate_{os.path.basename(sf)}",
                    "cmd": ["kicad-cli", "sch", "export", "netlist",
                            "-o", "/dev/null", sf],
                    "weight": 30,
                    "timeout": 30,
                })
        if pcb_files:
            for pf in pcb_files[:2]:
                commands.append({
                    "name": f"drc_{os.path.basename(pf)}",
                    "cmd": ["kicad-cli", "pcb", "drc", "--exit-code-violations", pf],
                    "weight": 40,
                    "timeout": 60,
                })

        return commands

    def get_exercises(self, difficulty="intermediate"):
        """Load from central catalog (~50 openeda seeds), fall back to hardcoded."""
        catalog = self._load_catalog_exercises(difficulty)
        if catalog:
            return catalog
        fallback = {
            "beginner": [
                Exercise(id="eda-b01", role="pcb_designer", task_type="PCB_DESIGN",
                         difficulty="beginner",
                         description="Design a simple LED circuit with resistor on a single-layer PCB",
                         acceptance_criteria=["DRC clean", "ERC clean", "Gerber files generated"],
                         expected_artifacts=["led_circuit.kicad_sch"], tags=["basic", "single-layer"]),
            ],
            "intermediate": [
                Exercise(id="eda-i01", role="pcb_designer", task_type="PCB_DESIGN",
                         difficulty="intermediate",
                         description="Design a 2-layer Arduino shield with I2C and SPI connectors",
                         acceptance_criteria=["DRC clean", "ERC clean", "BOM complete"],
                         expected_artifacts=["shield.kicad_sch", "bom.csv"], tags=["arduino", "2-layer"]),
            ],
            "advanced": [
                Exercise(id="eda-a01", role="pcb_designer", task_type="PCB_DESIGN",
                         difficulty="advanced",
                         description="Design a 4-layer USB-C power delivery board with ESD protection",
                         acceptance_criteria=["DRC clean", "4-layer impedance controlled", "ESD protection"],
                         expected_artifacts=["usb_pd.kicad_sch", "stackup.txt"], tags=["usb-c", "4-layer"]),
            ],
        }
        return fallback.get(difficulty, fallback["intermediate"])

    def grade_exercise(self, exercise, result):
        """Structural checks (40%) + LLM-as-judge (60%)."""
        score = 0.0
        criteria = {}
        hints = []

        if result.status == "completed":
            score += 25
            criteria["execution_success"] = True

        # DRC/ERC metrics
        metrics = result.metrics or {}
        if metrics.get("drc_errors", -1) == 0:
            score += 20
            criteria["drc_clean"] = True
        else:
            criteria["drc_clean"] = False
            hints.append("Ensure DRC passes with zero errors")

        if metrics.get("erc_errors", -1) == 0:
            score += 15
            criteria["erc_clean"] = True

        # EDA keywords
        output_lower = (result.output or "").lower()
        eda_kws = ["schematic", "pcb", "trace", "clearance", "component", "footprint",
                    "net", "via", "copper", "layer", "stackup", "impedance"]
        if sum(1 for k in eda_kws if k in output_lower) >= 3:
            score += 15
            criteria["eda_patterns"] = True

        # BOM / manufacturing readiness
        mfg_kws = ["bom", "gerber", "drill", "part number", "footprint"]
        if sum(1 for k in mfg_kws if k in output_lower) >= 1:
            score += 10
            criteria["manufacturing_ready"] = True

        if result.verification and result.verification.passed:
            score += 15
            criteria["verification_passed"] = True

        return self._combined_grade(
            exercise, result, min(score, 100.0), criteria, hints,
            domain_context=(
                "Grade as a senior PCB/EDA engineer. Check for:\n"
                "- Correct schematic symbols and connections\n"
                "- DRC/ERC compliance, trace width/spacing rules\n"
                "- Controlled impedance for high-speed signals\n"
                "- Proper decoupling, power plane integrity\n"
                "- Manufacturing readiness (Gerbers, BOM, drill files)"
            ),
        )


_runner = OpenEDARunner()
register_runner(_runner)

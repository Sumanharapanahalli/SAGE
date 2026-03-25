"""
SAGE Framework — OpenSim (Hardware Simulation) Runner
======================================================
Domain-specific execution for SPICE/Verilog/HDL simulation.

Workflow: spec → model → simulate → waveform analysis → timing check → synthesis

Roles: hardware_sim_engineer
Docker: sage/hw-simulation:latest
"""

import logging

from src.integrations.base_runner import (
    BaseRunner, RunResult, VerificationReport, VerificationFinding,
    VerificationSeverity, Exercise, ExerciseScore,
    register_runner, SIM_ROLES,
)

logger = logging.getLogger("Runner.opensim")


class OpenSimRunner(BaseRunner):
    """Hardware simulation execution runner."""

    def __init__(self):
        super().__init__(
            name="opensim",
            roles=list(SIM_ROLES),
            docker_image="sage/hw-simulation:latest",
        )

    def execute(self, task, workspace, sandbox_handle=None):
        run_id = self._new_run_id()
        try:
            description = task.get("description", "")
            task_type = task.get("task_type", "HARDWARE_SIM")

            from src.core.llm_gateway import llm_gateway

            system_prompt = (
                "You are a senior hardware simulation engineer.\n"
                "Generate simulation models following these rules:\n"
                "- Use SPICE netlist format for analog circuits\n"
                "- Use Verilog for digital designs\n"
                "- Include testbench with stimulus\n"
                "- Specify simulation parameters (time, step, accuracy)\n"
                "- Include expected output waveform descriptions\n\n"
                "Output as JSON: {\"files\": [{\"path\": \"...\", \"content\": \"...\"}], "
                "\"sim_type\": \"spice|verilog\", \"sim_time_us\": N, "
                "\"expected_outputs\": [\"...\"]}\n"
            )

            response = llm_gateway.generate_for_task(
                task_type=task_type,
                prompt=f"Task: {description}",
                system_prompt=system_prompt,
                trace_name="opensim.generate",
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
                    metrics["sim_type"] = parsed.get("sim_type", "unknown")
                    metrics["sim_time_us"] = parsed.get("sim_time_us", 0)
            except Exception:
                pass

            return self._make_result(
                run_id=run_id, status="completed", tier="direct",
                output=response, files_changed=files_changed, metrics=metrics,
            )
        except Exception as exc:
            self.logger.error("OpenSim execute failed: %s", exc)
            return self._make_error(run_id, str(exc))

    def verify(self, result, task):
        findings = []
        score = 30.0

        if result.status == "error":
            return VerificationReport(passed=False, score=0.0, findings=[
                VerificationFinding("execution", VerificationSeverity.ERROR, "Failed"),
            ])

        metrics = result.metrics or {}

        # Convergence check
        converged = metrics.get("converged", None)
        if converged is True:
            score += 25
            findings.append(VerificationFinding(
                "convergence", VerificationSeverity.PASS, "Simulation converged",
            ))
        elif converged is False:
            findings.append(VerificationFinding(
                "convergence", VerificationSeverity.ERROR, "Simulation did not converge",
            ))

        # Timing check
        timing_slack = metrics.get("timing_slack_ns")
        if isinstance(timing_slack, (int, float)):
            if timing_slack >= 0:
                score += 20
                findings.append(VerificationFinding(
                    "timing", VerificationSeverity.PASS,
                    f"Timing met: {timing_slack}ns slack",
                ))
            else:
                findings.append(VerificationFinding(
                    "timing", VerificationSeverity.ERROR,
                    f"Timing violation: {timing_slack}ns slack",
                ))

        # Files produced
        if result.files_changed:
            score += 15

        # Simulation keywords
        output_lower = (result.output or "").lower()
        sim_kws = ["spice", "verilog", "module", "wire", "reg", "netlist", "testbench", "stimulus"]
        if sum(1 for k in sim_kws if k in output_lower) >= 2:
            score += 10

        score = min(score, 100.0)
        return VerificationReport(passed=score >= 40.0, score=score, findings=findings, metrics=metrics)

    def get_toolchain(self):
        return {
            "runner": self.name, "docker_image": self.docker_image,
            "roles": self.roles,
            "tools": ["ngspice", "iverilog", "verilator", "gtkwave", "yosys"],
            "packages": ["ngspice", "iverilog", "gtkwave", "yosys", "verilator"],
        }

    def get_workflow(self):
        return [
            {"step": 1, "name": "spec_review", "description": "Parse circuit/HDL specification"},
            {"step": 2, "name": "model", "description": "Create SPICE netlist or Verilog module"},
            {"step": 3, "name": "testbench", "description": "Create testbench with stimulus"},
            {"step": 4, "name": "simulate", "description": "Run simulation engine"},
            {"step": 5, "name": "run_simulation", "description": "Execute simulation with parameters"},
            {"step": 6, "name": "waveform_analysis", "description": "Analyze output waveforms"},
            {"step": 7, "name": "timing_check", "description": "Verify timing constraints"},
            {"step": 8, "name": "synthesis", "description": "Synthesize to gate-level (digital only)"},
        ]

    def get_experience_keys(self):
        return ["task_type", "circuit_type", "sim_tool", "frequency_range", "domain"]

    def get_exercises(self, difficulty="intermediate"):
        exercises = {
            "beginner": [
                Exercise(
                    id="sim-b01", role="hardware_sim_engineer", task_type="HARDWARE_SIM",
                    difficulty="beginner",
                    description="Simulate an RC low-pass filter with cutoff at 1kHz using SPICE",
                    acceptance_criteria=[
                        "SPICE netlist is valid",
                        "Simulation converges",
                        "Waveform shows -3dB at 1kHz cutoff",
                        "Includes .tran and .ac analysis",
                    ],
                    expected_artifacts=["rc_filter.spice", "testbench.spice"],
                    tags=["spice", "analog", "filter"],
                ),
            ],
            "intermediate": [
                Exercise(
                    id="sim-i01", role="hardware_sim_engineer", task_type="HARDWARE_SIM",
                    difficulty="intermediate",
                    description="Write Verilog for a synchronous FIFO (depth 16, width 8) with full/empty flags",
                    acceptance_criteria=[
                        "Verilog syntax valid",
                        "Simulation converges with iverilog",
                        "Testbench covers empty, full, wrap-around",
                        "Timing constraints met at 100MHz",
                    ],
                    expected_artifacts=["fifo.v", "fifo_tb.v"],
                    tags=["verilog", "digital", "fifo"],
                ),
            ],
            "advanced": [
                Exercise(
                    id="sim-a01", role="hardware_sim_engineer", task_type="HARDWARE_SIM",
                    difficulty="advanced",
                    description="Design a PLL with 100MHz output from 25MHz reference and verify lock time",
                    acceptance_criteria=[
                        "SPICE model of PLL loop",
                        "Simulation converges",
                        "Lock time measured from waveform",
                        "Phase noise analysis included",
                    ],
                    expected_artifacts=["pll.spice", "pll_tb.spice", "analysis.txt"],
                    tags=["pll", "analog", "mixed-signal"],
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

        expected = set(exercise.expected_artifacts)
        produced = set(result.files_changed)
        match = len(expected & produced) / max(len(expected), 1)
        score += match * 25
        criteria_results["artifacts_match"] = match >= 0.5

        metrics = result.metrics or {}
        if metrics.get("converged") is True:
            score += 25
            criteria_results["sim_converged"] = True
        else:
            hints.append("Ensure simulation converges — check parameters")

        output_lower = (result.output or "").lower()
        sim_kws = ["spice", "verilog", "module", "testbench", ".tran", ".ac", "wire", "reg"]
        if sum(1 for k in sim_kws if k in output_lower) >= 2:
            score += 15

        if result.verification and result.verification.passed:
            score += 10

        score = min(score, 100.0)
        return ExerciseScore(
            exercise_id=exercise.id, passed=score >= 50, score=score,
            criteria_results=criteria_results,
            feedback="Good simulation work" if score >= 70 else "Review simulation practices",
            improvement_hints=hints,
        )


_runner = OpenSimRunner()
register_runner(_runner)

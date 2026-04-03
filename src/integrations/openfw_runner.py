"""
SAGE Framework — OpenFW (Firmware) Runner
===========================================
Domain-specific execution for firmware/embedded engineering.

Workflow: read HW spec → write HAL/driver code → cross-compile → static analysis
          → binary metrics → emulator test → report

Differs from OpenSWE because:
  - Code is cross-compiled for ARM/RISC-V, not executed locally
  - Verification is binary metrics (size, stack depth), not test suites
  - Artifacts are ELF/HEX binaries, not source PRs
  - Static analysis (cppcheck) is mandatory, not optional

Roles: firmware_engineer, embedded_tester
Docker: sage/firmware-toolchain:latest
"""

import logging

from src.integrations.base_runner import (
    BaseRunner, RunResult, VerificationReport, VerificationFinding,
    VerificationSeverity, Exercise, ExerciseScore,
    register_runner, FIRMWARE_ROLES,
)

logger = logging.getLogger("Runner.openfw")


class OpenFWRunner(BaseRunner):
    """Firmware and embedded systems execution runner."""

    def __init__(self):
        super().__init__(
            name="openfw",
            roles=list(FIRMWARE_ROLES),
            docker_image="sage/firmware-toolchain:latest",
        )

    # ── Execute ─────────────────────────────────────────────────────────

    def execute(self, task, workspace, sandbox_handle=None):
        run_id = self._new_run_id()
        try:
            description = task.get("description", "")
            task_type = task.get("task_type", "FIRMWARE")

            # Use LLM to generate firmware code
            from src.core.llm_gateway import llm_gateway

            system_prompt = (
                "You are a senior embedded firmware engineer.\n"
                "Generate production-quality embedded C code following these rules:\n"
                "- Use HAL abstraction for hardware access\n"
                "- All pointer dereferences must check for NULL\n"
                "- Use volatile for memory-mapped peripheral registers\n"
                "- Include proper interrupt priority configuration\n"
                "- Follow MISRA-C guidelines where practical\n"
                "- Include a Makefile or CMakeLists.txt for cross-compilation\n\n"
                "Output as JSON: {\"files\": [{\"path\": \"...\", \"content\": \"...\"}], "
                "\"target_mcu\": \"...\", \"binary_estimate_kb\": N, \"ram_estimate_kb\": N}\n"
            )

            response = llm_gateway.generate_for_task(
                task_type=task_type,
                prompt=f"Task: {description}\nPayload: {task.get('payload', {})}",
                system_prompt=system_prompt,
                trace_name="openfw.generate",
            )

            # Parse response
            files_changed = []
            metrics = {}
            try:
                import json
                # Try to extract JSON from response
                start = response.find("{")
                end = response.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(response[start:end])
                    files_changed = [f["path"] for f in parsed.get("files", [])]
                    metrics["target_mcu"] = parsed.get("target_mcu", "generic")
                    metrics["binary_estimate_kb"] = parsed.get("binary_estimate_kb", 0)
                    metrics["ram_estimate_kb"] = parsed.get("ram_estimate_kb", 0)
            except (json.JSONDecodeError, KeyError):
                pass

            metrics["task_type"] = task_type
            return self._make_result(
                run_id=run_id,
                status="completed",
                tier="direct",
                output=response,
                files_changed=files_changed,
                metrics=metrics,
            )

        except Exception as exc:
            self.logger.error("OpenFW execute failed: %s", exc)
            return self._make_error(run_id, str(exc))

    # ── Verify ──────────────────────────────────────────────────────────

    def verify(self, result, task):
        findings = []
        score = 30.0  # base for producing any output

        if result.status == "error":
            findings.append(VerificationFinding(
                check="execution", severity=VerificationSeverity.ERROR,
                message="Execution failed", details={"errors": result.errors},
            ))
            return VerificationReport(passed=False, score=0.0, findings=findings)

        metrics = result.metrics or {}

        # Check binary size vs flash limit
        binary_kb = metrics.get("binary_estimate_kb") or metrics.get("binary_size", 0)
        if isinstance(binary_kb, (int, float)) and binary_kb > 0:
            flash_limit = metrics.get("flash_limit", 256 * 1024)  # default 256KB
            if binary_kb <= flash_limit:
                score += 15
                findings.append(VerificationFinding(
                    check="binary_size", severity=VerificationSeverity.PASS,
                    message=f"Binary {binary_kb}KB fits flash",
                    details={"binary_size": binary_kb},
                ))
            else:
                findings.append(VerificationFinding(
                    check="binary_size", severity=VerificationSeverity.ERROR,
                    message=f"Binary {binary_kb}KB exceeds flash limit {flash_limit}KB",
                ))

        # Check files produced
        if result.files_changed:
            score += 20
            has_c = any(f.endswith(".c") or f.endswith(".cpp") for f in result.files_changed)
            has_h = any(f.endswith(".h") or f.endswith(".hpp") for f in result.files_changed)
            has_build = any("make" in f.lower() or "cmake" in f.lower() for f in result.files_changed)
            if has_c:
                score += 10
            if has_h:
                score += 5
            if has_build:
                score += 10
            findings.append(VerificationFinding(
                check="artifacts", severity=VerificationSeverity.PASS,
                message=f"Produced {len(result.files_changed)} files (C={has_c}, H={has_h}, Build={has_build})",
            ))

        # Check output contains embedded patterns
        output_lower = (result.output or "").lower()
        embedded_patterns = ["hal_", "gpio", "uart", "spi", "i2c", "interrupt", "volatile", "rtos"]
        matched = sum(1 for p in embedded_patterns if p in output_lower)
        if matched >= 2:
            score += 10
            findings.append(VerificationFinding(
                check="embedded_patterns", severity=VerificationSeverity.PASS,
                message=f"Contains {matched} embedded patterns",
            ))

        score = min(score, 100.0)
        return VerificationReport(
            passed=score >= 40.0,
            score=score,
            findings=findings,
            metrics={"binary_size": binary_kb} if isinstance(binary_kb, (int, float)) else {},
        )

    # ── Toolchain ───────────────────────────────────────────────────────

    def get_toolchain(self):
        return {
            "runner": self.name,
            "docker_image": self.docker_image,
            "roles": self.roles,
            "tools": ["gcc-arm-none-eabi", "openocd", "gdb-multiarch", "cmake", "ninja", "make"],
            "packages": ["gcc-arm-none-eabi", "openocd", "cmake", "ninja-build", "gdb-multiarch",
                         "cppcheck", "valgrind", "lcov", "qemu-system-arm"],
        }

    def get_workflow(self):
        return [
            {"step": 1, "name": "spec_review", "description": "Read hardware spec and requirements"},
            {"step": 2, "name": "code", "description": "Generate HAL/driver/application code"},
            {"step": 3, "name": "cross_compile", "description": "Cross-compile for target MCU"},
            {"step": 4, "name": "static_analysis", "description": "Run cppcheck, MISRA checks"},
            {"step": 5, "name": "binary_metrics", "description": "Measure binary size, stack depth, RAM usage"},
            {"step": 6, "name": "emulator_test", "description": "Run unit tests on QEMU ARM emulator"},
            {"step": 7, "name": "report", "description": "Generate build report with metrics"},
        ]

    def get_experience_keys(self):
        return ["task_type", "mcu_family", "peripheral", "domain", "rtos"]

    def get_experimental_commands(self, workspace, files):
        """Firmware-specific: C syntax check, cross-compile attempt, static analysis."""
        import os
        commands = []
        c_files = [f for f in files if f.endswith((".c", ".cpp"))]
        h_files = [f for f in files if f.endswith((".h", ".hpp"))]

        if c_files:
            # GCC syntax check (host compiler — catches syntax errors even without ARM headers)
            compiler = "gcc" if any(f.endswith(".c") for f in c_files) else "g++"
            commands.append({
                "name": "c_syntax_check",
                "cmd": [compiler, "-fsyntax-only", "-Wall", "-Wextra",
                        "-Wno-unknown-pragmas", f"-I{workspace}"] + c_files,
                "weight": 30,
                "timeout": 30,
            })
            # Try ARM cross-compile if toolchain available
            commands.append({
                "name": "arm_cross_compile",
                "cmd": ["arm-none-eabi-gcc", "-fsyntax-only", "-mcpu=cortex-m4",
                        "-mthumb", f"-I{workspace}"] + c_files,
                "weight": 25,
                "timeout": 30,
            })
            # Static analysis with cppcheck if available
            commands.append({
                "name": "static_analysis",
                "cmd": ["cppcheck", "--enable=warning,style", "--error-exitcode=1",
                        "--quiet"] + c_files,
                "weight": 20,
                "timeout": 30,
            })

        if h_files:
            # Verify headers are self-contained (include guard check)
            for hf in h_files[:5]:
                commands.append({
                    "name": f"header_check_{os.path.basename(hf)}",
                    "cmd": ["gcc", "-fsyntax-only", "-x", "c", f"-I{workspace}", hf],
                    "weight": 5,
                    "timeout": 10,
                })

        return commands

    # ── Exercises ───────────────────────────────────────────────────────

    def get_exercises(self, difficulty="intermediate"):
        """Load exercises from central catalog (469 seeds), fall back to hardcoded."""
        catalog = self._load_catalog_exercises(difficulty)
        if catalog:
            return catalog
        # Fallback: minimal hardcoded set
        fallback = {
            "beginner": [
                Exercise(id="fw-b01", role="firmware_engineer", task_type="FIRMWARE",
                         difficulty="beginner",
                         description="Write a GPIO driver to blink an LED on STM32F4 at 1Hz",
                         acceptance_criteria=["Compiles for ARM Cortex-M4", "Binary under 64KB",
                                              "Uses HAL GPIO functions", "Includes Makefile or CMake"],
                         expected_artifacts=["main.c", "gpio_driver.c", "Makefile"],
                         tags=["gpio", "stm32"]),
            ],
            "intermediate": [
                Exercise(id="fw-i01", role="firmware_engineer", task_type="FIRMWARE",
                         difficulty="intermediate",
                         description="Write an I2C driver for BME280 sensor on STM32",
                         acceptance_criteria=["Compiles for ARM", "I2C read/write", "Handles NACK errors"],
                         expected_artifacts=["bme280.c", "bme280.h", "main.c"],
                         tags=["i2c", "sensor"]),
            ],
            "advanced": [
                Exercise(id="fw-a01", role="firmware_engineer", task_type="FIRMWARE",
                         difficulty="advanced",
                         description="Implement FreeRTOS CAN bus gateway with message filtering",
                         acceptance_criteria=["FreeRTOS tasks", "CAN filtering", "Watchdog"],
                         expected_artifacts=["main.c", "can_gateway.c", "CMakeLists.txt"],
                         tags=["rtos", "can"]),
            ],
        }
        return fallback.get(difficulty, fallback["intermediate"])

    def grade_exercise(self, exercise, result):
        """Structural checks (40%) + LLM-as-judge (60%)."""
        score = 0.0
        criteria = {}
        hints = []

        # Structural: execution success
        if result.status == "completed":
            score += 25
            criteria["execution_success"] = True
        else:
            criteria["execution_success"] = False
            hints.append("Ensure code compiles without errors")

        # Structural: binary metrics
        binary_size = result.metrics.get("binary_size", result.metrics.get("binary_estimate_kb", 0))
        if isinstance(binary_size, (int, float)) and binary_size > 0:
            score += 15
            criteria["has_binary_metrics"] = True
        else:
            criteria["has_binary_metrics"] = False
            hints.append("Include binary size estimation")

        # Structural: embedded patterns
        output_lower = (result.output or "").lower()
        fw_keywords = ["hal_", "gpio", "uart", "spi", "i2c", "interrupt", "#include", "volatile"]
        kw_hits = sum(1 for k in fw_keywords if k in output_lower)
        if kw_hits >= 2:
            score += 20
            criteria["embedded_patterns"] = True
        else:
            criteria["embedded_patterns"] = False
            hints.append("Use proper HAL/peripheral abstractions")

        # Structural: build system
        build_files = [f for f in result.files_changed if "make" in f.lower() or "cmake" in f.lower()]
        if build_files:
            score += 15
            criteria["has_build_system"] = True
        else:
            criteria["has_build_system"] = False
            hints.append("Include Makefile or CMakeLists.txt")

        # Structural: MISRA / safety patterns
        safety_patterns = ["null", "assert", "error", "timeout", "watchdog"]
        safety_hits = sum(1 for p in safety_patterns if p in output_lower)
        if safety_hits >= 2:
            score += 10
            criteria["safety_patterns"] = True

        # Verification bonus
        if result.verification and result.verification.passed:
            score += 15
            criteria["verification_passed"] = True

        return self._combined_grade(
            exercise, result, min(score, 100.0), criteria, hints,
            domain_context=(
                "Grade as a firmware/embedded engineer. Check for:\n"
                "- Correct HAL usage, volatile qualifiers, interrupt safety\n"
                "- MISRA-C compliance, NULL checks, error handling\n"
                "- Memory-mapped register access patterns\n"
                "- Cross-compilation readiness (ARM Cortex-M target)"
            ),
        )


# Auto-register
_runner = OpenFWRunner()
register_runner(_runner)

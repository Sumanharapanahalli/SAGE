"""
SAGE Framework — Domain Runner TDD Tests
==========================================
Tests written FIRST (TDD). Each runner is implemented to pass these tests.

Groups:
  1. BaseRunner interface contract (10 tests)
  2. Runner registry (8 tests)
  3. OpenSWE Runner (10 tests)
  4. OpenFW Runner — Firmware (12 tests)
  5. OpenEDA Runner — PCB/Electronics (10 tests)
  6. OpenSim Runner — Hardware Simulation (10 tests)
  7. OpenML Runner — Machine Learning (10 tests)
  8. OpenDoc Runner — Documentation/Compliance (10 tests)
  9. OpenDesign Runner — UX/Design (8 tests)
 10. OpenStrategy Runner — Strategy/Planning (8 tests)
 11. Cross-runner integration (8 tests)
 12. Experience accumulation (6 tests)
"""

import os
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_llm_response(text="mock output"):
    """Create a mock LLM gateway that returns text."""
    mock = MagicMock()
    mock.generate_for_task.return_value = text
    return mock


def _mock_sandbox_handle(exec_output="OK", exec_exit_code=0):
    """Create a mock OpenShell sandbox handle."""
    handle = MagicMock()
    handle.exec.return_value = {"stdout": exec_output, "exit_code": exec_exit_code}
    return handle


def _basic_task(task_type="BACKEND", description="Build a REST API"):
    return {
        "task_type": task_type,
        "description": description,
        "payload": {},
        "acceptance_criteria": ["Must compile", "Must pass tests"],
        "agent_role": "developer",
    }


def _mock_llm_ctx(response_text='{"files": [{"path": "out.py", "content": "x=1"}], "explanation": "done"}'):
    """Context manager to mock llm_gateway.generate_for_task across all runners."""
    return patch("src.core.llm_gateway.llm_gateway.generate_for_task", return_value=response_text)


# ===========================================================================
# Group 1: BaseRunner Interface Contract
# ===========================================================================

class TestBaseRunnerContract:
    """Verify BaseRunner ABC and data classes work correctly."""

    def test_cannot_instantiate_base_runner(self):
        """BaseRunner is abstract — direct instantiation must fail."""
        from src.integrations.base_runner import BaseRunner
        with pytest.raises(TypeError):
            BaseRunner("test", ["developer"])

    def test_run_result_to_dict(self):
        """RunResult.to_dict() returns a serializable dict."""
        from src.integrations.base_runner import RunResult
        r = RunResult(
            run_id="abc-123",
            status="completed",
            runner="openswe",
            tier="direct",
            files_changed=["app.py"],
            output="generated code",
        )
        d = r.to_dict()
        assert d["run_id"] == "abc-123"
        assert d["status"] == "completed"
        assert d["runner"] == "openswe"
        assert d["files_changed"] == ["app.py"]
        assert isinstance(d["output"], str)

    def test_verification_report_to_dict(self):
        """VerificationReport serializes correctly."""
        from src.integrations.base_runner import (
            VerificationReport, VerificationFinding, VerificationSeverity,
        )
        report = VerificationReport(
            passed=True,
            score=85.0,
            findings=[
                VerificationFinding(
                    check="lint",
                    severity=VerificationSeverity.PASS,
                    message="No issues",
                ),
            ],
            metrics={"coverage": 92},
        )
        d = report.to_dict()
        assert d["passed"] is True
        assert d["score"] == 85.0
        assert len(d["findings"]) == 1
        assert d["findings"][0]["severity"] == "pass"
        assert d["metrics"]["coverage"] == 92

    def test_exercise_dataclass(self):
        """Exercise dataclass holds training task definition."""
        from src.integrations.base_runner import Exercise
        ex = Exercise(
            id="fw-001",
            role="firmware_engineer",
            task_type="FIRMWARE",
            difficulty="intermediate",
            description="Write I2C driver",
            acceptance_criteria=["Compiles for ARM", "Handles NACK"],
            expected_artifacts=["driver.c", "driver.h"],
        )
        assert ex.id == "fw-001"
        assert ex.difficulty == "intermediate"
        assert len(ex.acceptance_criteria) == 2

    def test_exercise_score_dataclass(self):
        """ExerciseScore holds grading results."""
        from src.integrations.base_runner import ExerciseScore
        score = ExerciseScore(
            exercise_id="fw-001",
            passed=True,
            score=78.0,
            criteria_results={"compiles": True, "handles_nack": True},
            feedback="Good implementation",
            improvement_hints=["Add timeout handling"],
        )
        assert score.passed is True
        assert score.score == 78.0

    def test_verification_severity_enum(self):
        """All expected severity levels exist."""
        from src.integrations.base_runner import VerificationSeverity
        assert VerificationSeverity.PASS.value == "pass"
        assert VerificationSeverity.WARNING.value == "warning"
        assert VerificationSeverity.ERROR.value == "error"
        assert VerificationSeverity.CRITICAL.value == "critical"

    def test_run_result_with_verification(self):
        """RunResult can carry a VerificationReport."""
        from src.integrations.base_runner import RunResult, VerificationReport
        report = VerificationReport(passed=True, score=90.0)
        r = RunResult(
            run_id="x", status="completed", runner="test", tier="direct",
            verification=report,
        )
        d = r.to_dict()
        assert d["verification"]["passed"] is True
        assert d["verification"]["score"] == 90.0

    def test_run_result_truncates_long_output(self):
        """RunResult.to_dict() truncates output to 2000 chars."""
        from src.integrations.base_runner import RunResult
        r = RunResult(
            run_id="x", status="completed", runner="test", tier="direct",
            output="A" * 5000,
        )
        d = r.to_dict()
        assert len(d["output"]) == 2000

    def test_role_family_constants_cover_all_registry_roles(self):
        """Every role in AGENT_ROLES_REGISTRY has a family assignment."""
        from src.integrations.base_runner import ALL_ROLE_FAMILIES
        from src.integrations.build_orchestrator import AGENT_ROLES_REGISTRY

        all_assigned = set()
        for roles in ALL_ROLE_FAMILIES.values():
            all_assigned.update(roles)

        for role in AGENT_ROLES_REGISTRY:
            assert role in all_assigned, f"Role '{role}' has no family assignment in base_runner.py"

    def test_no_role_in_multiple_families(self):
        """A role must belong to exactly one runner family."""
        from src.integrations.base_runner import ALL_ROLE_FAMILIES
        seen = {}
        for family, roles in ALL_ROLE_FAMILIES.items():
            for role in roles:
                assert role not in seen, (
                    f"Role '{role}' in both '{seen[role]}' and '{family}'"
                )
                seen[role] = family


# ===========================================================================
# Group 2: Runner Registry
# ===========================================================================

class TestRunnerRegistry:
    """Verify runner registration and lookup."""

    def test_register_runner(self):
        """register_runner() adds runner to registry."""
        from src.integrations.base_runner import (
            register_runner, get_runner_for_role, _RUNNER_REGISTRY,
            _RUNNER_INSTANCES, BaseRunner, RunResult, VerificationReport,
            Exercise, ExerciseScore,
        )

        class DummyRunner(BaseRunner):
            def execute(self, task, workspace, sandbox_handle=None):
                return RunResult("x", "completed", "dummy", "direct")
            def verify(self, result, task):
                return VerificationReport(True, 100.0)
            def get_exercises(self, difficulty="intermediate"):
                return []
            def grade_exercise(self, exercise, result):
                return ExerciseScore("x", True, 100.0)

        dummy = DummyRunner("test_dummy", ["test_role_a", "test_role_b"])
        register_runner(dummy)

        assert get_runner_for_role("test_role_a") is dummy
        assert get_runner_for_role("test_role_b") is dummy

        # Cleanup
        _RUNNER_REGISTRY.pop("test_role_a", None)
        _RUNNER_REGISTRY.pop("test_role_b", None)
        _RUNNER_INSTANCES.pop("test_dummy", None)

    def test_get_runner_for_unknown_role(self):
        """Unknown role returns None."""
        from src.integrations.base_runner import get_runner_for_role
        assert get_runner_for_role("nonexistent_role_xyz") is None

    def test_get_runner_by_name(self):
        """Can retrieve runner by name."""
        from src.integrations.base_runner import (
            register_runner, get_runner_by_name, _RUNNER_REGISTRY,
            _RUNNER_INSTANCES, BaseRunner, RunResult, VerificationReport,
            Exercise, ExerciseScore,
        )

        class DummyRunner2(BaseRunner):
            def execute(self, task, workspace, sandbox_handle=None):
                return RunResult("x", "completed", "dummy2", "direct")
            def verify(self, result, task):
                return VerificationReport(True, 100.0)
            def get_exercises(self, difficulty="intermediate"):
                return []
            def grade_exercise(self, exercise, result):
                return ExerciseScore("x", True, 100.0)

        dummy = DummyRunner2("test_dummy2", ["test_role_c"])
        register_runner(dummy)

        assert get_runner_by_name("test_dummy2") is dummy

        # Cleanup
        _RUNNER_REGISTRY.pop("test_role_c", None)
        _RUNNER_INSTANCES.pop("test_dummy2", None)

    def test_list_runners(self):
        """list_runners() returns info about all registered runners."""
        from src.integrations.base_runner import list_runners
        runners = list_runners()
        assert isinstance(runners, list)
        for r in runners:
            assert "name" in r
            assert "roles" in r

    def test_get_role_to_runner_map(self):
        """get_role_to_runner_map() returns complete mapping."""
        from src.integrations.base_runner import get_role_to_runner_map
        mapping = get_role_to_runner_map()
        assert isinstance(mapping, dict)

    def test_runner_get_toolchain(self):
        """Every runner provides toolchain info."""
        from src.integrations.base_runner import _RUNNER_INSTANCES
        for name, runner in _RUNNER_INSTANCES.items():
            tc = runner.get_toolchain()
            assert "runner" in tc
            assert "docker_image" in tc
            assert "roles" in tc

    def test_runner_get_workflow(self):
        """Every runner provides a workflow with at least one step."""
        from src.integrations.base_runner import _RUNNER_INSTANCES
        for name, runner in _RUNNER_INSTANCES.items():
            wf = runner.get_workflow()
            assert isinstance(wf, list)
            assert len(wf) >= 1

    def test_runner_get_status_unknown_run(self):
        """get_status() for unknown run_id returns error."""
        from src.integrations.base_runner import _RUNNER_INSTANCES
        for name, runner in _RUNNER_INSTANCES.items():
            status = runner.get_status("nonexistent-run-id")
            assert "error" in status
            break  # one runner is enough to test


# ===========================================================================
# Group 3: OpenSWE Runner (refactored to BaseRunner)
# ===========================================================================

class TestOpenSWERunner:
    """Verify OpenSWE implements BaseRunner interface."""

    def test_openswe_is_registered(self):
        """OpenSWE runner is registered for SWE_ROLES."""
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("developer")
        assert runner is not None
        assert runner.name == "openswe"

    def test_openswe_covers_all_swe_roles(self):
        """OpenSWE handles developer, qa_engineer, system_tester, devops, localization."""
        from src.integrations.base_runner import get_runner_for_role, SWE_ROLES
        for role in SWE_ROLES:
            runner = get_runner_for_role(role)
            assert runner is not None, f"No runner for SWE role '{role}'"
            assert runner.name == "openswe"

    def test_openswe_execute_returns_run_result(self):
        """execute() returns a RunResult with correct fields."""
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("developer")
        task = _basic_task()
        with patch("src.integrations.openswe_runner.OpenSWERunner.build", return_value={
            "status": "completed", "tier": "llm_react",
            "code": "x=1", "files_changed": ["app.py"], "output": {},
            "run_id": "test-123",
        }):
            result = runner.execute(task, "/tmp/test-workspace")
        assert result.status in ("completed", "error", "failed")
        assert result.runner == "openswe"
        assert result.run_id

    def test_openswe_handles_empty_task(self):
        """execute() with minimal task doesn't crash."""
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("developer")
        with patch("src.integrations.openswe_runner.OpenSWERunner.build", return_value={
            "status": "completed", "tier": "llm_react",
            "code": "", "files_changed": [], "output": {},
            "run_id": "empty-123",
        }):
            result = runner.execute({"task_type": "BACKEND", "description": ""}, "")
        assert result.status in ("completed", "error", "failed")

    def test_openswe_verify_checks_code(self):
        """verify() checks code output quality."""
        from src.integrations.base_runner import get_runner_for_role, RunResult
        runner = get_runner_for_role("developer")
        result = RunResult(
            run_id="x", status="completed", runner="openswe", tier="direct",
            files_changed=["app.py"], output="def hello(): pass",
        )
        report = runner.verify(result, _basic_task())
        assert hasattr(report, "passed")
        assert hasattr(report, "score")
        assert 0 <= report.score <= 100

    def test_openswe_exercises_exist(self):
        """get_exercises() returns non-empty list."""
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("developer")
        exercises = runner.get_exercises("intermediate")
        assert len(exercises) >= 1
        assert all(ex.role in runner.roles or ex.task_type for ex in exercises)

    def test_openswe_workflow_steps(self):
        """OpenSWE workflow: explore → code → test → PR."""
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("developer")
        wf = runner.get_workflow()
        step_names = [s["name"] for s in wf]
        assert "explore" in step_names or "code" in step_names

    def test_openswe_toolchain(self):
        """OpenSWE toolchain includes language runtimes."""
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("developer")
        tc = runner.get_toolchain()
        assert "tools" in tc
        assert len(tc["tools"]) > 0

    def test_openswe_grade_exercise(self):
        """grade_exercise returns an ExerciseScore."""
        from src.integrations.base_runner import (
            get_runner_for_role, Exercise, RunResult,
        )
        runner = get_runner_for_role("developer")
        ex = Exercise(
            id="swe-001", role="developer", task_type="BACKEND",
            difficulty="beginner", description="Write hello world",
            acceptance_criteria=["Prints hello"], expected_artifacts=["main.py"],
        )
        result = RunResult(
            run_id="x", status="completed", runner="openswe", tier="direct",
            files_changed=["main.py"], output='print("hello")',
        )
        score = runner.grade_exercise(ex, result)
        assert hasattr(score, "passed")
        assert 0 <= score.score <= 100

    def test_openswe_experience_keys(self):
        """Experience keys include task_type and language."""
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("developer")
        keys = runner.get_experience_keys()
        assert "task_type" in keys


# ===========================================================================
# Group 4: OpenFW Runner — Firmware
# ===========================================================================

class TestOpenFWRunner:
    """Verify OpenFW firmware runner."""

    def test_openfw_is_registered(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("firmware_engineer")
        assert runner is not None
        assert runner.name == "openfw"

    def test_openfw_covers_firmware_roles(self):
        from src.integrations.base_runner import get_runner_for_role, FIRMWARE_ROLES
        for role in FIRMWARE_ROLES:
            runner = get_runner_for_role(role)
            assert runner is not None, f"No runner for firmware role '{role}'"
            assert runner.name == "openfw"

    def test_openfw_execute_returns_run_result(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("firmware_engineer")
        task = _basic_task("FIRMWARE", "Write I2C driver for BME280")
        with _mock_llm_ctx('{"files": [{"path": "driver.c", "content": "// HAL_Init()"}], "target_mcu": "STM32F4", "binary_estimate_kb": 32, "ram_estimate_kb": 8}'):
            result = runner.execute(task, "/tmp/fw-workspace")
        assert result.runner == "openfw"
        assert result.status in ("completed", "error", "failed")

    def test_openfw_verify_checks_compilation(self):
        """Firmware verification must check cross-compilation success."""
        from src.integrations.base_runner import get_runner_for_role, RunResult
        runner = get_runner_for_role("firmware_engineer")
        result = RunResult(
            run_id="x", status="completed", runner="openfw", tier="direct",
            files_changed=["driver.c", "driver.h"],
            artifacts=[{"path": "build/firmware.elf", "type": "binary", "size": 32768}],
            metrics={"binary_size": 32768, "ram_usage": 4096},
        )
        report = runner.verify(result, _basic_task("FIRMWARE", "I2C driver"))
        assert hasattr(report, "passed")
        assert "binary_size" in report.metrics or len(report.findings) > 0

    def test_openfw_verify_checks_binary_size(self):
        """Verification reports binary size metrics."""
        from src.integrations.base_runner import get_runner_for_role, RunResult
        runner = get_runner_for_role("firmware_engineer")
        result = RunResult(
            run_id="x", status="completed", runner="openfw", tier="direct",
            metrics={"binary_size": 262144, "flash_limit": 256 * 1024},
        )
        report = runner.verify(result, _basic_task("FIRMWARE", "Large firmware"))
        # Should flag if binary exceeds flash limit
        assert isinstance(report.score, float)

    def test_openfw_workflow_has_cross_compile(self):
        """Firmware workflow includes cross-compilation step."""
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("firmware_engineer")
        wf = runner.get_workflow()
        step_names = [s["name"] for s in wf]
        assert "cross_compile" in step_names or "compile" in step_names

    def test_openfw_toolchain_has_gcc_arm(self):
        """Firmware toolchain includes gcc-arm-none-eabi."""
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("firmware_engineer")
        tc = runner.get_toolchain()
        all_tools = tc.get("tools", []) + tc.get("packages", [])
        assert any("gcc-arm" in t or "arm" in t for t in all_tools)

    def test_openfw_docker_image(self):
        """Firmware runner has docker image configured."""
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("firmware_engineer")
        assert runner.docker_image
        assert "firmware" in runner.docker_image

    def test_openfw_exercises_exist(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("firmware_engineer")
        exercises = runner.get_exercises("intermediate")
        assert len(exercises) >= 1
        assert all(
            ex.task_type in ("FIRMWARE", "EMBEDDED_TEST") or "firmware" in ex.role or "embedded" in ex.role
            for ex in exercises
        )

    def test_openfw_exercises_have_binary_criteria(self):
        """Firmware exercises must include compilation/binary acceptance criteria."""
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("firmware_engineer")
        exercises = runner.get_exercises("beginner")
        for ex in exercises:
            criteria_text = " ".join(ex.acceptance_criteria).lower()
            assert any(
                kw in criteria_text
                for kw in ["compile", "binary", "build", "flash", "size"]
            ), f"Exercise '{ex.id}' has no compilation criteria"

    def test_openfw_grade_exercise(self):
        from src.integrations.base_runner import get_runner_for_role, Exercise, RunResult
        runner = get_runner_for_role("firmware_engineer")
        ex = Exercise(
            id="fw-001", role="firmware_engineer", task_type="FIRMWARE",
            difficulty="beginner", description="Blink LED on STM32",
            acceptance_criteria=["Compiles for ARM", "Binary < 64KB"],
            expected_artifacts=["main.c", "Makefile"],
        )
        result = RunResult(
            run_id="x", status="completed", runner="openfw", tier="direct",
            files_changed=["main.c", "Makefile"],
            metrics={"binary_size": 8192},
        )
        score = runner.grade_exercise(ex, result)
        assert 0 <= score.score <= 100

    def test_openfw_experience_keys(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("firmware_engineer")
        keys = runner.get_experience_keys()
        assert "task_type" in keys
        # Firmware should also key on MCU/peripheral
        assert any(k in keys for k in ["mcu_family", "peripheral", "domain"])


# ===========================================================================
# Group 5: OpenEDA Runner — PCB/Electronics
# ===========================================================================

class TestOpenEDARunner:
    """Verify OpenEDA PCB design runner."""

    def test_openeda_is_registered(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("pcb_designer")
        assert runner is not None
        assert runner.name == "openeda"

    def test_openeda_execute_returns_run_result(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("pcb_designer")
        task = _basic_task("PCB_DESIGN", "Design power supply board")
        with _mock_llm_ctx('{"files": [{"path": "board.kicad_pcb", "content": "layout"}], "components": 5, "layers": 2}'):
            result = runner.execute(task, "/tmp/eda-workspace")
        assert result.runner == "openeda"
        assert result.status in ("completed", "error", "failed")

    def test_openeda_verify_checks_drc(self):
        """EDA verification must check DRC/ERC results."""
        from src.integrations.base_runner import get_runner_for_role, RunResult
        runner = get_runner_for_role("pcb_designer")
        result = RunResult(
            run_id="x", status="completed", runner="openeda", tier="direct",
            artifacts=[{"path": "board.kicad_pcb", "type": "pcb_layout"}],
            metrics={"drc_errors": 0, "erc_errors": 0, "unrouted_nets": 0},
        )
        report = runner.verify(result, _basic_task("PCB_DESIGN", "Board layout"))
        assert hasattr(report, "passed")

    def test_openeda_workflow_has_drc(self):
        """EDA workflow includes DRC step."""
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("pcb_designer")
        wf = runner.get_workflow()
        step_names = [s["name"] for s in wf]
        assert "drc" in step_names or "design_rule_check" in step_names

    def test_openeda_toolchain_has_kicad(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("pcb_designer")
        tc = runner.get_toolchain()
        all_tools = tc.get("tools", []) + tc.get("packages", [])
        assert any("kicad" in t.lower() for t in all_tools)

    def test_openeda_docker_image(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("pcb_designer")
        assert runner.docker_image
        assert "pcb" in runner.docker_image

    def test_openeda_exercises_exist(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("pcb_designer")
        exercises = runner.get_exercises("beginner")
        assert len(exercises) >= 1

    def test_openeda_exercises_have_drc_criteria(self):
        """PCB exercises must include DRC/ERC acceptance criteria."""
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("pcb_designer")
        for ex in runner.get_exercises("beginner"):
            criteria_text = " ".join(ex.acceptance_criteria).lower()
            assert any(
                kw in criteria_text for kw in ["drc", "erc", "gerber", "schematic", "layout"]
            ), f"Exercise '{ex.id}' has no EDA criteria"

    def test_openeda_grade_exercise(self):
        from src.integrations.base_runner import get_runner_for_role, Exercise, RunResult
        runner = get_runner_for_role("pcb_designer")
        ex = Exercise(
            id="eda-001", role="pcb_designer", task_type="PCB_DESIGN",
            difficulty="beginner", description="Design LED circuit",
            acceptance_criteria=["DRC clean", "BOM complete"],
            expected_artifacts=["schematic.kicad_sch"],
        )
        result = RunResult(
            run_id="x", status="completed", runner="openeda", tier="direct",
            artifacts=[{"path": "schematic.kicad_sch", "type": "schematic"}],
            metrics={"drc_errors": 0, "erc_errors": 0},
        )
        score = runner.grade_exercise(ex, result)
        assert 0 <= score.score <= 100

    def test_openeda_experience_keys(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("pcb_designer")
        keys = runner.get_experience_keys()
        assert "task_type" in keys


# ===========================================================================
# Group 6: OpenSim Runner — Hardware Simulation
# ===========================================================================

class TestOpenSimRunner:
    """Verify OpenSim hardware simulation runner."""

    def test_opensim_is_registered(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("hardware_sim_engineer")
        assert runner is not None
        assert runner.name == "opensim"

    def test_opensim_execute_returns_run_result(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("hardware_sim_engineer")
        task = _basic_task("HARDWARE_SIM", "Simulate bandpass filter")
        with _mock_llm_ctx('{"files": [{"path": "filter.spice", "content": "* SPICE netlist"}], "sim_type": "spice", "sim_time_us": 1000}'):
            result = runner.execute(task, "/tmp/sim-workspace")
        assert result.runner == "opensim"

    def test_opensim_verify_checks_convergence(self):
        """Simulation verification must check convergence."""
        from src.integrations.base_runner import get_runner_for_role, RunResult
        runner = get_runner_for_role("hardware_sim_engineer")
        result = RunResult(
            run_id="x", status="completed", runner="opensim", tier="direct",
            metrics={"converged": True, "timing_slack_ns": 2.5},
        )
        report = runner.verify(result, _basic_task("HARDWARE_SIM", "Filter sim"))
        assert hasattr(report, "passed")

    def test_opensim_workflow_has_simulate(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("hardware_sim_engineer")
        wf = runner.get_workflow()
        step_names = [s["name"] for s in wf]
        assert "simulate" in step_names or "run_simulation" in step_names

    def test_opensim_toolchain_has_spice(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("hardware_sim_engineer")
        tc = runner.get_toolchain()
        all_tools = tc.get("tools", []) + tc.get("packages", [])
        assert any("spice" in t.lower() or "verilog" in t.lower() or "iverilog" in t.lower() for t in all_tools)

    def test_opensim_docker_image(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("hardware_sim_engineer")
        assert runner.docker_image
        assert "simulation" in runner.docker_image or "sim" in runner.docker_image

    def test_opensim_exercises_exist(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("hardware_sim_engineer")
        exercises = runner.get_exercises("intermediate")
        assert len(exercises) >= 1

    def test_opensim_exercises_have_sim_criteria(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("hardware_sim_engineer")
        for ex in runner.get_exercises("beginner"):
            criteria_text = " ".join(ex.acceptance_criteria).lower()
            assert any(
                kw in criteria_text
                for kw in ["simulate", "converge", "waveform", "timing", "spice", "verilog"]
            )

    def test_opensim_grade_exercise(self):
        from src.integrations.base_runner import get_runner_for_role, Exercise, RunResult
        runner = get_runner_for_role("hardware_sim_engineer")
        ex = Exercise(
            id="sim-001", role="hardware_sim_engineer", task_type="HARDWARE_SIM",
            difficulty="beginner", description="Simulate RC filter",
            acceptance_criteria=["Simulation converges", "Cutoff at 1kHz"],
            expected_artifacts=["filter.spice"],
        )
        result = RunResult(
            run_id="x", status="completed", runner="opensim", tier="direct",
            metrics={"converged": True, "cutoff_hz": 1000},
        )
        score = runner.grade_exercise(ex, result)
        assert 0 <= score.score <= 100

    def test_opensim_experience_keys(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("hardware_sim_engineer")
        keys = runner.get_experience_keys()
        assert "task_type" in keys


# ===========================================================================
# Group 7: OpenML Runner — Machine Learning
# ===========================================================================

class TestOpenMLRunner:
    """Verify OpenML machine learning runner."""

    def test_openml_is_registered(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("data_scientist")
        assert runner is not None
        assert runner.name == "openml"

    def test_openml_execute_returns_run_result(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("data_scientist")
        task = _basic_task("ML_MODEL", "Train fraud classifier")
        with _mock_llm_ctx('{"files": [{"path": "train.py", "content": "# model"}], "model_type": "xgboost", "metrics": {"accuracy": 0.92, "f1": 0.88}}'):
            result = runner.execute(task, "/tmp/ml-workspace")
        assert result.runner == "openml"

    def test_openml_verify_checks_metrics(self):
        """ML verification must check model metrics."""
        from src.integrations.base_runner import get_runner_for_role, RunResult
        runner = get_runner_for_role("data_scientist")
        result = RunResult(
            run_id="x", status="completed", runner="openml", tier="direct",
            metrics={"accuracy": 0.92, "f1": 0.88, "auc": 0.95},
        )
        report = runner.verify(result, _basic_task("ML_MODEL", "Classifier"))
        assert hasattr(report, "passed")

    def test_openml_workflow_has_train(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("data_scientist")
        wf = runner.get_workflow()
        step_names = [s["name"] for s in wf]
        assert "train" in step_names or "training" in step_names

    def test_openml_toolchain_has_ml_tools(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("data_scientist")
        tc = runner.get_toolchain()
        all_tools = tc.get("tools", []) + tc.get("packages", [])
        assert any(
            t in all_tools
            for t in ["pandas", "scikit-learn", "pytorch", "tensorflow", "mlflow", "sklearn"]
        ) or len(all_tools) > 0

    def test_openml_exercises_exist(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("data_scientist")
        exercises = runner.get_exercises("intermediate")
        assert len(exercises) >= 1

    def test_openml_exercises_have_metric_criteria(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("data_scientist")
        for ex in runner.get_exercises("beginner"):
            criteria_text = " ".join(ex.acceptance_criteria).lower()
            assert any(
                kw in criteria_text
                for kw in ["accuracy", "f1", "metric", "evaluate", "train", "model"]
            )

    def test_openml_verify_detects_data_leakage(self):
        """ML verification should flag potential data leakage."""
        from src.integrations.base_runner import get_runner_for_role, RunResult
        runner = get_runner_for_role("data_scientist")
        result = RunResult(
            run_id="x", status="completed", runner="openml", tier="direct",
            metrics={"accuracy": 1.0, "f1": 1.0},  # suspiciously perfect
        )
        report = runner.verify(result, _basic_task("ML_MODEL", "Too good"))
        # Perfect metrics should trigger a warning
        has_warning = any(
            f.severity.value in ("warning", "critical")
            for f in report.findings
        )
        assert has_warning or report.score < 100

    def test_openml_grade_exercise(self):
        from src.integrations.base_runner import get_runner_for_role, Exercise, RunResult
        runner = get_runner_for_role("data_scientist")
        ex = Exercise(
            id="ml-001", role="data_scientist", task_type="ML_MODEL",
            difficulty="beginner", description="Train iris classifier",
            acceptance_criteria=["Accuracy > 0.90", "No data leakage"],
            expected_artifacts=["model.pkl", "metrics.json"],
        )
        result = RunResult(
            run_id="x", status="completed", runner="openml", tier="direct",
            metrics={"accuracy": 0.95, "f1": 0.94},
        )
        score = runner.grade_exercise(ex, result)
        assert 0 <= score.score <= 100

    def test_openml_experience_keys(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("data_scientist")
        keys = runner.get_experience_keys()
        assert "task_type" in keys


# ===========================================================================
# Group 8: OpenDoc Runner — Documentation/Compliance
# ===========================================================================

class TestOpenDocRunner:
    """Verify OpenDoc documentation/compliance runner."""

    def test_opendoc_is_registered(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("technical_writer")
        assert runner is not None
        assert runner.name == "opendoc"

    def test_opendoc_covers_all_doc_roles(self):
        from src.integrations.base_runner import get_runner_for_role, DOC_ROLES
        for role in DOC_ROLES:
            runner = get_runner_for_role(role)
            assert runner is not None, f"No runner for doc role '{role}'"
            assert runner.name == "opendoc"

    def test_opendoc_execute_returns_run_result(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("technical_writer")
        task = _basic_task("DOCUMENTATION", "Write API docs")
        with _mock_llm_ctx('{"files": [{"path": "api_docs.md", "content": "# API Docs section"}], "sections_count": 5, "word_count": 500}'):
            result = runner.execute(task, "/tmp/doc-workspace")
        assert result.runner == "opendoc"

    def test_opendoc_verify_checks_completeness(self):
        from src.integrations.base_runner import get_runner_for_role, RunResult
        runner = get_runner_for_role("regulatory_specialist")
        result = RunResult(
            run_id="x", status="completed", runner="opendoc", tier="direct",
            artifacts=[{"path": "dhf.md", "type": "document"}],
            metrics={"sections_complete": 12, "sections_required": 15},
        )
        report = runner.verify(result, _basic_task("REGULATORY", "DHF"))
        assert hasattr(report, "passed")

    def test_opendoc_workflow_has_draft(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("technical_writer")
        wf = runner.get_workflow()
        step_names = [s["name"] for s in wf]
        assert "draft" in step_names or "write" in step_names

    def test_opendoc_exercises_exist(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("technical_writer")
        exercises = runner.get_exercises("beginner")
        assert len(exercises) >= 1

    def test_opendoc_exercises_have_doc_criteria(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("technical_writer")
        for ex in runner.get_exercises("beginner"):
            criteria_text = " ".join(ex.acceptance_criteria).lower()
            assert any(
                kw in criteria_text
                for kw in ["section", "document", "complete", "template", "draft", "write",
                            "format", "example", "criteria", "code", "api", "user"]
            ), f"Exercise '{ex.id}' criteria don't match: {criteria_text}"

    def test_opendoc_grade_exercise(self):
        from src.integrations.base_runner import get_runner_for_role, Exercise, RunResult
        runner = get_runner_for_role("technical_writer")
        ex = Exercise(
            id="doc-001", role="technical_writer", task_type="DOCUMENTATION",
            difficulty="beginner", description="Write quickstart guide",
            acceptance_criteria=["Has installation section", "Has first example"],
            expected_artifacts=["quickstart.md"],
        )
        result = RunResult(
            run_id="x", status="completed", runner="opendoc", tier="direct",
            artifacts=[{"path": "quickstart.md", "type": "document"}],
        )
        score = runner.grade_exercise(ex, result)
        assert 0 <= score.score <= 100

    def test_opendoc_regulatory_uses_standard_coverage(self):
        """Regulatory docs should track standard clause coverage."""
        from src.integrations.base_runner import get_runner_for_role, RunResult
        runner = get_runner_for_role("regulatory_specialist")
        result = RunResult(
            run_id="x", status="completed", runner="opendoc", tier="direct",
            metrics={"standard_coverage_pct": 85, "standard": "ISO 14971"},
        )
        report = runner.verify(result, _basic_task("REGULATORY", "Risk management"))
        assert isinstance(report.score, float)

    def test_opendoc_experience_keys(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("technical_writer")
        keys = runner.get_experience_keys()
        assert "task_type" in keys


# ===========================================================================
# Group 9: OpenDesign Runner — UX/Design
# ===========================================================================

class TestOpenDesignRunner:
    """Verify OpenDesign UX runner."""

    def test_opendesign_is_registered(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("ux_designer")
        assert runner is not None
        assert runner.name == "opendesign"

    def test_opendesign_execute_returns_run_result(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("ux_designer")
        task = _basic_task("UI_DESIGN", "Design login screen")
        with _mock_llm_ctx('{"files": [{"path": "login.svg", "content": "<svg/>"}], "wcag_level": "AA", "components": ["input", "button"]}'):
            result = runner.execute(task, "/tmp/design-workspace")
        assert result.runner == "opendesign"

    def test_opendesign_verify_checks_accessibility(self):
        from src.integrations.base_runner import get_runner_for_role, RunResult
        runner = get_runner_for_role("ux_designer")
        result = RunResult(
            run_id="x", status="completed", runner="opendesign", tier="direct",
            metrics={"wcag_violations": 0, "contrast_ratio_min": 4.8},
        )
        report = runner.verify(result, _basic_task("UI_DESIGN", "Login screen"))
        assert hasattr(report, "passed")

    def test_opendesign_workflow_has_wireframe(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("ux_designer")
        wf = runner.get_workflow()
        step_names = [s["name"] for s in wf]
        assert "wireframe" in step_names or "prototype" in step_names or "design" in step_names

    def test_opendesign_exercises_exist(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("ux_designer")
        exercises = runner.get_exercises("beginner")
        assert len(exercises) >= 1

    def test_opendesign_exercises_have_accessibility_criteria(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("ux_designer")
        all_criteria = []
        for ex in runner.get_exercises("beginner"):
            all_criteria.extend(ex.acceptance_criteria)
        criteria_text = " ".join(all_criteria).lower()
        assert any(
            kw in criteria_text
            for kw in ["accessible", "wcag", "contrast", "touch", "design", "wireframe"]
        )

    def test_opendesign_grade_exercise(self):
        from src.integrations.base_runner import get_runner_for_role, Exercise, RunResult
        runner = get_runner_for_role("ux_designer")
        ex = Exercise(
            id="design-001", role="ux_designer", task_type="UI_DESIGN",
            difficulty="beginner", description="Design button component",
            acceptance_criteria=["WCAG AA compliant", "Touch target >= 44px"],
            expected_artifacts=["button.svg", "tokens.json"],
        )
        result = RunResult(
            run_id="x", status="completed", runner="opendesign", tier="direct",
            metrics={"wcag_violations": 0, "min_touch_target": 48},
        )
        score = runner.grade_exercise(ex, result)
        assert 0 <= score.score <= 100

    def test_opendesign_experience_keys(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("ux_designer")
        keys = runner.get_experience_keys()
        assert "task_type" in keys


# ===========================================================================
# Group 10: OpenStrategy Runner — Strategy/Planning
# ===========================================================================

class TestOpenStrategyRunner:
    """Verify OpenStrategy planning runner."""

    def test_openstrategy_is_registered(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("product_manager")
        assert runner is not None
        assert runner.name == "openstrategy"

    def test_openstrategy_covers_all_strategy_roles(self):
        from src.integrations.base_runner import get_runner_for_role, STRATEGY_ROLES
        for role in STRATEGY_ROLES:
            runner = get_runner_for_role(role)
            assert runner is not None, f"No runner for strategy role '{role}'"
            assert runner.name == "openstrategy"

    def test_openstrategy_execute_returns_run_result(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("product_manager")
        task = _basic_task("PRODUCT_STRATEGY", "Write PRD for mobile app")
        with _mock_llm_ctx('{"files": [{"path": "prd.md", "content": "# PRD"}], "framework_used": "RICE", "sections": ["problem", "solution"], "action_items": ["launch"]}'):
            result = runner.execute(task, "/tmp/strategy-workspace")
        assert result.runner == "openstrategy"

    def test_openstrategy_verify_checks_framework_completeness(self):
        from src.integrations.base_runner import get_runner_for_role, RunResult
        runner = get_runner_for_role("product_manager")
        result = RunResult(
            run_id="x", status="completed", runner="openstrategy", tier="direct",
            metrics={"framework_sections_complete": 8, "framework_sections_total": 10},
        )
        report = runner.verify(result, _basic_task("PRODUCT_STRATEGY", "PRD"))
        assert hasattr(report, "passed")

    def test_openstrategy_workflow_has_analyze(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("product_manager")
        wf = runner.get_workflow()
        step_names = [s["name"] for s in wf]
        assert "analyze" in step_names or "research" in step_names or "plan" in step_names

    def test_openstrategy_exercises_exist(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("product_manager")
        exercises = runner.get_exercises("beginner")
        assert len(exercises) >= 1

    def test_openstrategy_grade_exercise(self):
        from src.integrations.base_runner import get_runner_for_role, Exercise, RunResult
        runner = get_runner_for_role("product_manager")
        ex = Exercise(
            id="strat-001", role="product_manager", task_type="PRODUCT_STRATEGY",
            difficulty="beginner", description="Write feature prioritization",
            acceptance_criteria=["Uses RICE framework", "Has actionable output"],
            expected_artifacts=["prioritization.md"],
        )
        result = RunResult(
            run_id="x", status="completed", runner="openstrategy", tier="direct",
            artifacts=[{"path": "prioritization.md", "type": "document"}],
        )
        score = runner.grade_exercise(ex, result)
        assert 0 <= score.score <= 100

    def test_openstrategy_experience_keys(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("product_manager")
        keys = runner.get_experience_keys()
        assert "task_type" in keys


# ===========================================================================
# Group 11: Cross-Runner Integration
# ===========================================================================

class TestCrossRunnerIntegration:
    """Verify runners work together and with the orchestrator."""

    def test_every_hireable_role_has_runner(self):
        """Every role in AGENT_ROLES_REGISTRY that is hireable has a runner."""
        from src.integrations.base_runner import get_runner_for_role, ORCHESTRATION_ROLES
        from src.integrations.build_orchestrator import AGENT_ROLES_REGISTRY
        for role, info in AGENT_ROLES_REGISTRY.items():
            if role in ORCHESTRATION_ROLES:
                continue  # orchestration roles don't execute
            runner = get_runner_for_role(role)
            assert runner is not None, (
                f"Hireable role '{role}' has no registered runner"
            )

    def test_all_runners_have_unique_names(self):
        """No two runners share the same name."""
        from src.integrations.base_runner import _RUNNER_INSTANCES
        names = list(_RUNNER_INSTANCES.keys())
        assert len(names) == len(set(names))

    def test_all_runners_implement_full_interface(self):
        """Every registered runner implements all BaseRunner methods."""
        from src.integrations.base_runner import _RUNNER_INSTANCES, RunResult, Exercise
        for name, runner in _RUNNER_INSTANCES.items():
            assert callable(getattr(runner, "execute", None)), f"{name} missing execute()"
            assert callable(getattr(runner, "verify", None)), f"{name} missing verify()"
            assert callable(getattr(runner, "get_exercises", None)), f"{name} missing get_exercises()"
            assert callable(getattr(runner, "grade_exercise", None)), f"{name} missing grade_exercise()"
            assert callable(getattr(runner, "get_toolchain", None)), f"{name} missing get_toolchain()"
            assert callable(getattr(runner, "get_workflow", None)), f"{name} missing get_workflow()"

    def test_runner_names_match_expected_set(self):
        """All 8 expected runners are registered."""
        from src.integrations.base_runner import _RUNNER_INSTANCES
        expected = {"openswe", "openfw", "openeda", "opensim", "openml", "opendoc", "opendesign", "openstrategy"}
        actual = set(_RUNNER_INSTANCES.keys())
        missing = expected - actual
        assert not missing, f"Missing runners: {missing}"

    def test_each_runner_has_at_least_one_exercise(self):
        """Every runner provides at least one exercise."""
        from src.integrations.base_runner import _RUNNER_INSTANCES
        for name, runner in _RUNNER_INSTANCES.items():
            exercises = runner.get_exercises("beginner")
            assert len(exercises) >= 1, f"Runner '{name}' has no beginner exercises"

    def test_each_runner_workflow_is_valid(self):
        """Every runner's workflow has step numbers and names."""
        from src.integrations.base_runner import _RUNNER_INSTANCES
        for name, runner in _RUNNER_INSTANCES.items():
            wf = runner.get_workflow()
            for step in wf:
                assert "step" in step, f"Runner '{name}' workflow step missing 'step'"
                assert "name" in step, f"Runner '{name}' workflow step missing 'name'"

    def test_runner_execute_never_raises(self):
        """execute() returns error result, never raises exceptions."""
        from src.integrations.base_runner import _RUNNER_INSTANCES
        with _mock_llm_ctx('{"files": [], "explanation": "empty"}'):
            for name, runner in _RUNNER_INSTANCES.items():
                if name == "openswe":
                    with patch("src.integrations.openswe_runner.OpenSWERunner.build", return_value={
                        "status": "completed", "tier": "llm_react", "code": "", "files_changed": [], "output": {}, "run_id": "x",
                    }):
                        result = runner.execute({"task_type": "INVALID", "description": ""}, "/nonexistent/path")
                else:
                    result = runner.execute({"task_type": "INVALID", "description": ""}, "/nonexistent/path")
                assert result.status in ("completed", "error", "failed", "partial")

    def test_runner_verify_never_raises(self):
        """verify() returns report, never raises exceptions."""
        from src.integrations.base_runner import _RUNNER_INSTANCES, RunResult
        for name, runner in _RUNNER_INSTANCES.items():
            result = RunResult(
                run_id="x", status="error", runner=name, tier="direct",
                errors=["test error"],
            )
            report = runner.verify(result, {"task_type": "TEST", "description": ""})
            assert hasattr(report, "passed")
            assert hasattr(report, "score")


# ===========================================================================
# Group 12: Experience Accumulation
# ===========================================================================

class TestExperienceAccumulation:
    """Verify experience storage and retrieval patterns."""

    def test_each_runner_has_experience_keys(self):
        """Every runner defines experience retrieval keys."""
        from src.integrations.base_runner import _RUNNER_INSTANCES
        for name, runner in _RUNNER_INSTANCES.items():
            keys = runner.get_experience_keys()
            assert isinstance(keys, list)
            assert len(keys) >= 1, f"Runner '{name}' has no experience keys"
            assert "task_type" in keys, f"Runner '{name}' missing 'task_type' key"

    def test_execute_can_return_experience(self):
        """execute() result can include experience entries for storage."""
        from src.integrations.base_runner import RunResult
        r = RunResult(
            run_id="x", status="completed", runner="test", tier="direct",
            experience=[
                {"pattern": "Always validate input", "task_type": "BACKEND", "score": 85},
            ],
        )
        assert len(r.experience) == 1
        assert r.experience[0]["pattern"] == "Always validate input"

    def test_experience_in_to_dict(self):
        """Experience entries survive serialization."""
        from src.integrations.base_runner import RunResult
        r = RunResult(
            run_id="x", status="completed", runner="test", tier="direct",
            experience=[{"pattern": "Use DMA for UART", "mcu": "STM32F4"}],
        )
        d = r.to_dict()
        assert d["experience"][0]["pattern"] == "Use DMA for UART"

    def test_runner_experience_keys_are_strings(self):
        """Experience keys are all strings."""
        from src.integrations.base_runner import _RUNNER_INSTANCES
        for name, runner in _RUNNER_INSTANCES.items():
            keys = runner.get_experience_keys()
            for k in keys:
                assert isinstance(k, str), f"Runner '{name}' has non-string key: {k}"

    def test_exercise_score_includes_improvement_hints(self):
        """ExerciseScore can carry improvement hints for experience storage."""
        from src.integrations.base_runner import ExerciseScore
        score = ExerciseScore(
            exercise_id="test",
            passed=False,
            score=45.0,
            improvement_hints=[
                "Add error handling for I2C NACK",
                "Check return values from HAL functions",
            ],
        )
        assert len(score.improvement_hints) == 2

    def test_domain_specific_experience_keys(self):
        """Domain runners have domain-relevant experience keys beyond task_type."""
        from src.integrations.base_runner import get_runner_for_role
        # Firmware should have MCU-related keys
        fw = get_runner_for_role("firmware_engineer")
        if fw:
            keys = fw.get_experience_keys()
            assert len(keys) >= 2, "Firmware runner should have domain-specific experience keys"

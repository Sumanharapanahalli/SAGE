"""
Tests for Build Orchestrator Fixes (TDD)
==========================================
Option 4: Wire MCP tools to domain runners
Option 2: Agent MessageBus
Option 5: Structured output validation + auto-retry
Option 1: Cascade failure propagation (transitive)
Option 3: Capability-match warm-start for AdaptiveRouter
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Option 4: Wire MCP Hardware Tools to Domain Runners
# ---------------------------------------------------------------------------

class TestOpenEDAHardwareTools:
    """OpenEDA runner should use hardware_tools MCP functions."""

    def test_execute_calls_kicad_create_project(self):
        """When OpenEDA executes a PCB_DESIGN task, it should create a KiCad project."""
        from src.integrations.openeda_runner import OpenEDARunner

        runner = OpenEDARunner()
        with tempfile.TemporaryDirectory() as workspace:
            with patch("src.core.llm_gateway.llm_gateway") as mock_llm:
                mock_llm.generate_for_task.return_value = json.dumps({
                    "files": [{"path": "board.kicad_sch", "content": "(kicad_sch)"}],
                    "components": 5,
                    "layers": 2,
                    "board_area_mm2": 1600,
                })

                result = runner.execute(
                    {"description": "Design LED PCB", "task_type": "PCB_DESIGN",
                     "payload": {"project_name": "led_board"}},
                    workspace,
                )

            assert result.status == "completed"
            # Should have created a KiCad project directory
            project_dir = os.path.join(workspace, "led_board")
            assert os.path.isdir(project_dir)
            assert any(f.endswith(".kicad_pro") for f in os.listdir(project_dir))

    def test_verify_runs_erc_drc_when_available(self):
        """Verification should invoke KiCad ERC/DRC on generated files."""
        from src.integrations.openeda_runner import OpenEDARunner
        from src.integrations.base_runner import RunResult

        runner = OpenEDARunner()
        result = RunResult(
            run_id="test-123", status="completed", runner="openeda", tier="direct",
            output="schematic generated", files_changed=["board.kicad_sch", "board.kicad_pcb"],
            metrics={"drc_errors": 0, "erc_errors": 0, "components": 5},
        )
        report = runner.verify(result, {"task_type": "PCB_DESIGN"})
        assert report.passed
        assert report.score > 50

    def test_execute_exports_gerbers_when_pcb_exists(self):
        """After generating a PCB, the runner should attempt Gerber export."""
        from src.integrations.openeda_runner import OpenEDARunner

        runner = OpenEDARunner()
        with tempfile.TemporaryDirectory() as workspace:
            with patch("src.core.llm_gateway.llm_gateway") as mock_llm:
                mock_llm.generate_for_task.return_value = json.dumps({
                    "files": [
                        {"path": "board.kicad_sch", "content": "(kicad_sch)"},
                        {"path": "board.kicad_pcb", "content": "(kicad_pcb)"},
                    ],
                    "components": 3, "layers": 2, "board_area_mm2": 900,
                })

                result = runner.execute(
                    {"description": "Design sensor PCB", "task_type": "PCB_DESIGN",
                     "payload": {"project_name": "sensor"}},
                    workspace,
                )

            # Result should report MCP tool invocations
            assert result.status == "completed"
            assert "mcp_tools_invoked" in result.metrics


class TestOpenFWHardwareTools:
    """OpenFW runner should use hardware_tools MCP functions."""

    def test_execute_runs_cppcheck_on_generated_code(self):
        """Firmware execution should run cppcheck static analysis."""
        from src.integrations.openfw_runner import OpenFWRunner

        runner = OpenFWRunner()
        with tempfile.TemporaryDirectory() as workspace:
            with patch("src.core.llm_gateway.llm_gateway") as mock_llm:
                mock_llm.generate_for_task.return_value = json.dumps({
                    "files": [
                        {"path": "main.c", "content": "int main() { return 0; }"},
                        {"path": "Makefile", "content": "all: main.c"},
                    ],
                    "target_mcu": "cortex-m4",
                    "binary_estimate_kb": 32,
                    "ram_estimate_kb": 8,
                })

                result = runner.execute(
                    {"description": "Write LED blinker firmware", "task_type": "FIRMWARE",
                     "payload": {}},
                    workspace,
                )

            assert result.status == "completed"
            # Should have attempted static analysis
            assert "mcp_tools_invoked" in result.metrics

    def test_execute_writes_files_to_workspace(self):
        """Generated firmware files should be written to workspace."""
        from src.integrations.openfw_runner import OpenFWRunner

        runner = OpenFWRunner()
        with tempfile.TemporaryDirectory() as workspace:
            with patch("src.core.llm_gateway.llm_gateway") as mock_llm:
                mock_llm.generate_for_task.return_value = json.dumps({
                    "files": [
                        {"path": "main.c", "content": "#include <stdint.h>\nint main() { return 0; }"},
                    ],
                    "target_mcu": "cortex-m4",
                    "binary_estimate_kb": 16,
                    "ram_estimate_kb": 4,
                })

                result = runner.execute(
                    {"description": "Blinker", "task_type": "FIRMWARE", "payload": {}},
                    workspace,
                )

            assert result.status == "completed"
            assert os.path.isfile(os.path.join(workspace, "main.c"))


# ---------------------------------------------------------------------------
# Option 2: Agent MessageBus
# ---------------------------------------------------------------------------

class TestMessageBus:
    """Test structured inter-agent messaging."""

    def test_create_bus(self):
        from src.integrations.message_bus import MessageBus
        bus = MessageBus()
        assert bus is not None

    def test_publish_and_read(self):
        from src.integrations.message_bus import MessageBus
        bus = MessageBus()
        bus.publish("agent_a", "architecture", {"stack": "Python+FastAPI"})
        messages = bus.read("architecture")
        assert len(messages) == 1
        assert messages[0]["sender"] == "agent_a"
        assert messages[0]["data"]["stack"] == "Python+FastAPI"

    def test_read_empty_topic(self):
        from src.integrations.message_bus import MessageBus
        bus = MessageBus()
        messages = bus.read("nonexistent")
        assert messages == []

    def test_multiple_publishers(self):
        from src.integrations.message_bus import MessageBus
        bus = MessageBus()
        bus.publish("agent_a", "design", {"layer": "HAL"})
        bus.publish("agent_b", "design", {"layer": "Driver"})
        messages = bus.read("design")
        assert len(messages) == 2

    def test_point_to_point(self):
        from src.integrations.message_bus import MessageBus
        bus = MessageBus()
        bus.send("agent_a", "agent_b", {"file": "main.c"})
        inbox = bus.inbox("agent_b")
        assert len(inbox) == 1
        assert inbox[0]["sender"] == "agent_a"

    def test_inbox_empty(self):
        from src.integrations.message_bus import MessageBus
        bus = MessageBus()
        assert bus.inbox("agent_c") == []

    def test_get_summary(self):
        """Summary should produce a markdown digest of all messages."""
        from src.integrations.message_bus import MessageBus
        bus = MessageBus()
        bus.publish("arch_agent", "architecture", {"pattern": "microservices"})
        bus.publish("fw_agent", "firmware", {"mcu": "STM32F4"})
        summary = bus.get_summary()
        assert "architecture" in summary
        assert "firmware" in summary
        assert "microservices" in summary

    def test_clear(self):
        from src.integrations.message_bus import MessageBus
        bus = MessageBus()
        bus.publish("a", "topic", {"data": 1})
        bus.clear()
        assert bus.read("topic") == []

    def test_thread_safety(self):
        """Bus should handle concurrent publishes safely."""
        import threading
        from src.integrations.message_bus import MessageBus
        bus = MessageBus()

        def publish_n(agent, n):
            for i in range(n):
                bus.publish(agent, "load", {"i": i})

        threads = [threading.Thread(target=publish_n, args=(f"agent_{t}", 50)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(bus.read("load")) == 200


# ---------------------------------------------------------------------------
# Option 5: Structured Output Validation + Auto-Retry
# ---------------------------------------------------------------------------

class TestOutputValidation:
    """Test Pydantic validation of agent outputs with auto-retry."""

    def test_valid_output_passes(self):
        from src.integrations.output_validator import validate_agent_output
        output = {
            "files": [{"path": "main.py", "content": "print('hello')"}],
            "explanation": "A hello world script",
        }
        result = validate_agent_output(output, "code_generation")
        assert result["valid"] is True

    def test_invalid_output_detected(self):
        from src.integrations.output_validator import validate_agent_output
        output = {"garbage": True}
        result = validate_agent_output(output, "code_generation")
        assert result["valid"] is False
        assert "errors" in result

    def test_missing_files_field(self):
        from src.integrations.output_validator import validate_agent_output
        output = {"explanation": "did something"}
        result = validate_agent_output(output, "code_generation")
        assert result["valid"] is False

    def test_auto_retry_on_parse_failure(self):
        """If LLM output fails JSON parse, retry once."""
        from src.integrations.output_validator import parse_with_retry

        call_count = 0

        def mock_generate():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "not valid json {{"
            return '{"files": [{"path": "a.py", "content": "x=1"}], "explanation": "fixed"}'

        result = parse_with_retry(mock_generate, "code_generation")
        assert result["valid"] is True
        assert call_count == 2

    def test_auto_retry_max_attempts(self):
        """Should give up after 2 attempts."""
        from src.integrations.output_validator import parse_with_retry

        def mock_generate():
            return "always broken"

        result = parse_with_retry(mock_generate, "code_generation", max_retries=2)
        assert result["valid"] is False

    def test_eda_output_schema(self):
        from src.integrations.output_validator import validate_agent_output
        output = {
            "files": [{"path": "board.kicad_sch", "content": "(kicad_sch)"}],
            "components": 5,
            "layers": 2,
            "board_area_mm2": 1600,
        }
        result = validate_agent_output(output, "eda_design")
        assert result["valid"] is True

    def test_firmware_output_schema(self):
        from src.integrations.output_validator import validate_agent_output
        output = {
            "files": [{"path": "main.c", "content": "int main(){}"}],
            "target_mcu": "cortex-m4",
            "binary_estimate_kb": 32,
            "ram_estimate_kb": 8,
        }
        result = validate_agent_output(output, "firmware")
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# Option 1: Cascade Failure Propagation (Transitive)
# ---------------------------------------------------------------------------

class TestCascadeFailure:
    """Test that failure cascades transitively through dependency chains."""

    def _make_orchestrator(self):
        from src.integrations.build_orchestrator import BuildOrchestrator
        return BuildOrchestrator(checkpoint_db=":memory:")

    def test_direct_dependency_blocked(self):
        """Task depending on a failed task should be blocked."""
        orch = self._make_orchestrator()
        plan = [
            {"step": 1, "task_type": "BACKEND", "description": "API", "depends_on": []},
            {"step": 2, "task_type": "TESTS", "description": "Tests", "depends_on": [1]},
        ]
        waves = orch._compute_waves(plan)
        assert len(waves) == 2
        assert waves[0][0]["step"] == 1
        assert waves[1][0]["step"] == 2

    def test_transitive_dependency_blocked(self):
        """Task depending on a blocked task should also be blocked (3-level chain)."""
        orch = self._make_orchestrator()
        plan = [
            {"step": 1, "task_type": "BACKEND", "description": "API", "depends_on": []},
            {"step": 2, "task_type": "TESTS", "description": "Tests", "depends_on": [1]},
            {"step": 3, "task_type": "DOCS", "description": "Docs", "depends_on": [2]},
        ]
        waves = orch._compute_waves(plan)
        # Wave 1: step 1, Wave 2: step 2, Wave 3: step 3
        assert len(waves) == 3

    def test_cascade_failure_in_execute(self):
        """In _execute_agents, if step 1 fails, step 2 and step 3 should be blocked."""
        orch = self._make_orchestrator()
        run = {
            "run_id": "test-cascade",
            "plan": [
                {"step": 1, "task_type": "BACKEND", "description": "API", "depends_on": [],
                 "agent_role": "developer"},
                {"step": 2, "task_type": "TESTS", "description": "Tests", "depends_on": [1],
                 "agent_role": "developer"},
                {"step": 3, "task_type": "DOCS", "description": "Docs", "depends_on": [2],
                 "agent_role": "developer"},
            ],
            "workspace_dir": "",
            "agent_results": [],
            "detected_domains": [],
        }

        with patch.object(orch, "_route_to_agent") as mock_route, \
             patch.object(orch, "_checkpoint"), \
             patch.object(orch, "_audit"), \
             patch.object(orch, "_summarize_context", return_value=""), \
             patch.object(orch, "_check_drift", return_value=True):
            mock_route.return_value = {"status": "error", "error": "compile failed"}
            orch._execute_agents(run)

        results = run["agent_results"]
        # Step 1 should be error (actually executed)
        assert results[0]["result"]["status"] == "error"
        # Step 2 should be blocked (dependency on step 1)
        assert results[1]["result"]["status"] == "blocked"
        # Step 3 should ALSO be blocked (transitive dependency through step 2)
        assert results[2]["result"]["status"] == "blocked"


# ---------------------------------------------------------------------------
# Option 3: Capability-Match Warm-Start for AdaptiveRouter
# ---------------------------------------------------------------------------

class TestCapabilityWarmStart:
    """Test keyword overlap scoring for cold-start routing."""

    def test_cold_start_uses_capability_match(self):
        """With zero observations, router should use keyword overlap if descriptions provided."""
        from src.integrations.build_orchestrator import AdaptiveRouter
        router = AdaptiveRouter()

        # Register role descriptions
        router.set_role_descriptions({
            "developer": "Write backend APIs, frontend code, database schemas, tests",
            "firmware_engineer": "Write embedded C firmware, HAL drivers, cross-compile for ARM Cortex-M",
            "pcb_designer": "Design PCB schematics, layouts, run ERC DRC, export Gerbers",
        })

        # Cold start — no observations yet
        result = router.route_with_context("FIRMWARE", "Write I2C driver for STM32 sensor")
        assert result == "firmware_engineer"

    def test_cold_start_pcb_design(self):
        from src.integrations.build_orchestrator import AdaptiveRouter
        router = AdaptiveRouter()
        router.set_role_descriptions({
            "developer": "Write backend APIs, frontend code, database schemas",
            "pcb_designer": "Design PCB schematics, layouts, DRC, Gerber export",
        })
        result = router.route_with_context("PCB_DESIGN", "Design 4-layer PCB with USB-C")
        assert result == "pcb_designer"

    def test_learned_score_overrides_capability(self):
        """Once enough observations exist, learned scores should win."""
        from src.integrations.build_orchestrator import AdaptiveRouter
        router = AdaptiveRouter()
        router.set_role_descriptions({
            "developer": "Write backend APIs",
            "analyst": "Analyze logs and data",
        })

        # Record enough observations that analyst is better at BACKEND tasks (unusual but possible)
        for _ in range(5):
            router.record("BACKEND", "analyst", success=True, quality_score=0.9)
            router.record("BACKEND", "developer", success=False, quality_score=0.1)

        result = router.route("BACKEND")
        assert result == "analyst"  # Learned score overrides both default AND capability

    def test_no_descriptions_falls_back_to_default(self):
        """Without descriptions, cold start should use static mapping."""
        from src.integrations.build_orchestrator import AdaptiveRouter
        router = AdaptiveRouter()
        # No set_role_descriptions called
        result = router.route_with_context("FIRMWARE", "Write I2C driver")
        assert result == "firmware_engineer"  # Falls back to TASK_TYPE_TO_AGENT

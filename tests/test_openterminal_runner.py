"""
SAGE Framework — OpenTerminal Runner TDD Tests
=================================================
Tests written FIRST (TDD) for the Meta-Harness-inspired terminal runner.

Features tested:
  1. BaseRunner contract compliance (execute, verify, get_exercises, grade_exercise)
  2. Tmux session management (create, attach, destroy)
  3. Marker-based command polling (__CMDEND__N__ markers)
  4. Environment bootstrapping (pre-discovery of installed tools)
  5. Structured reasoning enforcement (analysis + plan + commands)
  6. Double-confirmation task completion
  7. Proactive context summarization
  8. Runner registration and role mapping

Inspired by: https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact
"""

import json
import time
from unittest.mock import MagicMock, patch, PropertyMock, call

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_runner():
    """Create an OpenTerminalRunner with mocked dependencies."""
    with patch("src.integrations.openterminal_runner._check_tmux_available", return_value=True):
        from src.integrations.openterminal_runner import OpenTerminalRunner
        return OpenTerminalRunner()


def _basic_task(description="List all Python files in /tmp"):
    return {
        "task_type": "TERMINAL",
        "description": description,
        "payload": {},
        "acceptance_criteria": ["Command executes successfully", "Output captured"],
        "agent_role": "terminal_operator",
    }


def _mock_llm_ctx(response_text=None):
    """Mock LLM gateway for terminal command generation."""
    if response_text is None:
        response_text = json.dumps({
            "analysis": "Need to list Python files in /tmp directory",
            "plan": "Use find command with .py extension filter",
            "commands": [
                {"command": "find /tmp -name '*.py' -type f", "duration": 5}
            ],
            "task_complete": False,
        })
    return patch("src.core.llm_gateway.llm_gateway.generate_for_task", return_value=response_text)


def _mock_llm_generate_ctx(response_text="summarized context"):
    """Mock LLM gateway generate for context summarization."""
    return patch("src.core.llm_gateway.llm_gateway.generate", return_value=response_text)


# ===========================================================================
# Group 1: BaseRunner Contract Compliance
# ===========================================================================

class TestBaseRunnerContract:
    """OpenTerminalRunner must implement all BaseRunner abstract methods."""

    def test_is_subclass_of_base_runner(self):
        runner = _fresh_runner()
        from src.integrations.base_runner import BaseRunner
        assert isinstance(runner, BaseRunner)

    def test_has_correct_name(self):
        runner = _fresh_runner()
        assert runner.name == "openterminal"

    def test_has_correct_roles(self):
        runner = _fresh_runner()
        assert "terminal_operator" in runner.roles
        assert "shell_expert" in runner.roles

    def test_execute_returns_run_result(self):
        runner = _fresh_runner()
        task = _basic_task()
        with _mock_llm_ctx(), \
             patch.object(runner, "_create_tmux_session", return_value="session-1"), \
             patch.object(runner, "_destroy_tmux_session"), \
             patch.object(runner, "_gather_env_snapshot", return_value={"cwd": "/tmp"}), \
             patch.object(runner, "_run_agent_loop", return_value={
                 "status": "completed",
                 "output": "file1.py\nfile2.py",
                 "commands_executed": 1,
             }):
            result = runner.execute(task, "/tmp/workspace")
            assert result.run_id is not None
            assert result.status == "completed"
            assert result.runner == "openterminal"

    def test_verify_returns_verification_report(self):
        runner = _fresh_runner()
        from src.integrations.base_runner import RunResult
        result = RunResult(
            run_id="test-123", status="completed",
            runner="openterminal", tier="direct",
            output="file1.py\nfile2.py",
            metrics={"commands_executed": 1, "exit_code": 0},
        )
        task = _basic_task()
        report = runner.verify(result, task)
        assert hasattr(report, "passed")
        assert hasattr(report, "score")
        assert hasattr(report, "findings")

    def test_get_exercises_returns_list(self):
        runner = _fresh_runner()
        exercises = runner.get_exercises("beginner")
        assert isinstance(exercises, list)

    def test_grade_exercise_returns_score(self):
        runner = _fresh_runner()
        from src.integrations.base_runner import Exercise, RunResult
        exercise = Exercise(
            id="term-b01", role="terminal_operator",
            task_type="terminal_execution", difficulty="beginner",
            description="List files in current directory",
            acceptance_criteria=["Output contains file listing"],
            expected_artifacts=[],
        )
        result = RunResult(
            run_id="test-grade", status="completed",
            runner="openterminal", tier="direct",
            output="file1.txt\nfile2.txt",
            metrics={"exit_code": 0, "commands_executed": 1},
        )
        with patch.object(runner, "_llm_grade", return_value={"score": 80, "passed": True, "criteria_results": {}, "feedback": "Good", "improvement_hints": []}):
            score = runner.grade_exercise(exercise, result)
            assert hasattr(score, "score")
            assert hasattr(score, "passed")

    def test_get_toolchain_includes_tmux(self):
        runner = _fresh_runner()
        toolchain = runner.get_toolchain()
        assert "tmux" in toolchain.get("tools", []) or "tmux" in str(toolchain)

    def test_get_workflow_has_bootstrap_step(self):
        runner = _fresh_runner()
        workflow = runner.get_workflow()
        step_names = [s.get("name", "") for s in workflow]
        assert "bootstrap" in step_names or "env_discovery" in step_names


# ===========================================================================
# Group 2: Tmux Session Management
# ===========================================================================

class TestTmuxSessionManagement:
    """Tmux session create, attach, destroy lifecycle."""

    def test_create_session_returns_session_id(self):
        runner = _fresh_runner()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            session_id = runner._create_tmux_session("test-task-1")
            assert session_id is not None
            assert "sage" in session_id.lower() or "term" in session_id.lower()

    def test_create_session_calls_tmux_new(self):
        runner = _fresh_runner()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            runner._create_tmux_session("task-abc")
            # Verify tmux new-session was called
            called_args = [str(c) for c in mock_run.call_args_list]
            assert any("new-session" in str(c) or "new" in str(c) for c in called_args)

    def test_destroy_session_cleans_up(self):
        runner = _fresh_runner()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            runner._destroy_tmux_session("sage-term-abc123")
            called_args = [str(c) for c in mock_run.call_args_list]
            assert any("kill-session" in str(c) for c in called_args)

    def test_capture_pane_output(self):
        runner = _fresh_runner()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="$ ls\nfile1.txt\nfile2.txt\n"
            )
            output = runner._capture_tmux_pane("sage-term-abc")
            assert isinstance(output, str)
            assert "file1.txt" in output

    def test_send_keys_to_session(self):
        runner = _fresh_runner()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            runner._send_tmux_keys("sage-term-abc", "ls -la")
            called_args = [str(c) for c in mock_run.call_args_list]
            assert any("send-keys" in str(c) for c in called_args)


# ===========================================================================
# Group 3: Marker-Based Command Polling
# ===========================================================================

class TestMarkerBasedPolling:
    """Marker injection and polling instead of fixed sleep."""

    def test_marker_format(self):
        """Markers must follow __CMDEND__N__ format."""
        runner = _fresh_runner()
        marker = runner._make_marker(1)
        assert "__CMDEND__1__" in marker

    def test_marker_increments(self):
        runner = _fresh_runner()
        m1 = runner._make_marker(1)
        m2 = runner._make_marker(2)
        assert "1" in m1
        assert "2" in m2
        assert m1 != m2

    def test_poll_detects_marker_in_output(self):
        """Polling should return immediately when marker appears."""
        runner = _fresh_runner()
        marker = runner._make_marker(1)
        # Simulate tmux output that contains the marker
        with patch.object(runner, "_capture_tmux_pane", return_value=f"some output\n{marker}\n"):
            found, output = runner._poll_for_marker("session-1", marker, timeout=5)
            assert found is True

    def test_poll_timeout_when_marker_absent(self):
        """Polling should timeout when marker never appears."""
        runner = _fresh_runner()
        marker = runner._make_marker(99)
        with patch.object(runner, "_capture_tmux_pane", return_value="no marker here"):
            found, output = runner._poll_for_marker("session-1", marker, timeout=0.1)
            assert found is False

    def test_command_with_marker_injection(self):
        """Commands should have marker echo appended."""
        runner = _fresh_runner()
        cmd = "ls -la"
        injected = runner._inject_marker(cmd, 3)
        assert cmd in injected
        assert "__CMDEND__3__" in injected

    def test_poll_extracts_output_before_marker(self):
        """Output between command and marker is the command output."""
        runner = _fresh_runner()
        marker = runner._make_marker(1)
        pane_content = f"$ ls -la\ntotal 4\nfile1.txt\nfile2.txt\n{marker}\n$"
        with patch.object(runner, "_capture_tmux_pane", return_value=pane_content):
            found, output = runner._poll_for_marker("s1", marker, timeout=5)
            assert found is True
            assert isinstance(output, str)


# ===========================================================================
# Group 4: Environment Bootstrapping
# ===========================================================================

class TestEnvironmentBootstrapping:
    """Pre-discovery of sandbox environment before agent loop."""

    def test_gather_env_snapshot_returns_dict(self):
        runner = _fresh_runner()
        with patch.object(runner, "_send_tmux_keys"), \
             patch.object(runner, "_poll_for_marker", return_value=(True, "Python 3.12\ngcc 12.3\n")), \
             patch.object(runner, "_capture_tmux_pane", return_value="/home/user\n"):
            snapshot = runner._gather_env_snapshot("session-1")
            assert isinstance(snapshot, dict)

    def test_snapshot_includes_working_directory(self):
        runner = _fresh_runner()
        env_output = "CWD=/home/user\nPython 3.12.0\ngcc 12.3.0"
        with patch.object(runner, "_send_tmux_keys"), \
             patch.object(runner, "_poll_for_marker", return_value=(True, env_output)), \
             patch.object(runner, "_capture_tmux_pane", return_value=env_output):
            snapshot = runner._gather_env_snapshot("session-1")
            assert "working_directory" in snapshot or "cwd" in snapshot

    def test_snapshot_includes_installed_languages(self):
        runner = _fresh_runner()
        env_output = "Python 3.12.0\ngcc 12.3.0\nnode v20.10\nrustc 1.75.0"
        with patch.object(runner, "_send_tmux_keys"), \
             patch.object(runner, "_poll_for_marker", return_value=(True, env_output)), \
             patch.object(runner, "_capture_tmux_pane", return_value=env_output):
            snapshot = runner._gather_env_snapshot("session-1")
            assert "languages" in snapshot or "tools_available" in snapshot

    def test_snapshot_includes_system_info(self):
        runner = _fresh_runner()
        env_output = "Linux 6.1.0\n4096 MB RAM\nDisk: 50GB free"
        with patch.object(runner, "_send_tmux_keys"), \
             patch.object(runner, "_poll_for_marker", return_value=(True, env_output)), \
             patch.object(runner, "_capture_tmux_pane", return_value=env_output):
            snapshot = runner._gather_env_snapshot("session-1")
            assert "system" in snapshot or "os" in snapshot

    def test_snapshot_injected_into_initial_prompt(self):
        """Environment snapshot must be part of the first LLM prompt."""
        runner = _fresh_runner()
        snapshot = {"cwd": "/home/user", "languages": {"python": "3.12"}, "system": {"os": "Linux"}}
        prompt = runner._build_initial_prompt(_basic_task(), snapshot)
        assert "/home/user" in prompt or "python" in prompt.lower()

    def test_bootstrap_failure_returns_partial_snapshot(self):
        """If some probes fail, return what we got — don't crash."""
        runner = _fresh_runner()
        with patch.object(runner, "_send_tmux_keys"), \
             patch.object(runner, "_poll_for_marker", return_value=(False, "")), \
             patch.object(runner, "_capture_tmux_pane", return_value=""):
            snapshot = runner._gather_env_snapshot("session-1")
            assert isinstance(snapshot, dict)


# ===========================================================================
# Group 5: Structured Reasoning Enforcement
# ===========================================================================

class TestStructuredReasoning:
    """LLM tool calls must include analysis + plan + commands."""

    def test_parse_valid_structured_response(self):
        runner = _fresh_runner()
        response = json.dumps({
            "analysis": "The directory exists and contains Python files",
            "plan": "List all .py files recursively",
            "commands": [{"command": "find . -name '*.py'", "duration": 5}],
            "task_complete": False,
        })
        parsed = runner._parse_agent_response(response)
        assert parsed["analysis"] != ""
        assert parsed["plan"] != ""
        assert len(parsed["commands"]) > 0

    def test_reject_response_without_analysis(self):
        """Response missing analysis field should be flagged."""
        runner = _fresh_runner()
        response = json.dumps({
            "plan": "Just run it",
            "commands": [{"command": "ls", "duration": 1}],
            "task_complete": False,
        })
        parsed = runner._parse_agent_response(response)
        assert parsed.get("valid") is False or parsed.get("analysis") == ""

    def test_reject_response_without_plan(self):
        runner = _fresh_runner()
        response = json.dumps({
            "analysis": "Analyzing the situation",
            "commands": [{"command": "ls", "duration": 1}],
            "task_complete": False,
        })
        parsed = runner._parse_agent_response(response)
        assert parsed.get("valid") is False or parsed.get("plan") == ""

    def test_commands_have_duration_field(self):
        runner = _fresh_runner()
        response = json.dumps({
            "analysis": "Need to check files",
            "plan": "Use ls command",
            "commands": [{"command": "ls -la", "duration": 3}],
            "task_complete": False,
        })
        parsed = runner._parse_agent_response(response)
        for cmd in parsed["commands"]:
            assert "duration" in cmd or "timeout" in cmd

    def test_system_prompt_enforces_structure(self):
        """The system prompt must instruct the LLM to use structured format."""
        runner = _fresh_runner()
        prompt = runner._get_system_prompt()
        assert "analysis" in prompt.lower()
        assert "plan" in prompt.lower()
        assert "command" in prompt.lower()


# ===========================================================================
# Group 6: Double-Confirmation Task Completion
# ===========================================================================

class TestDoubleConfirmation:
    """Task completion requires a verification checklist before finalizing."""

    def test_first_completion_returns_verification_checklist(self):
        runner = _fresh_runner()
        result = runner._handle_task_complete(
            first_attempt=True,
            task=_basic_task(),
            output_so_far="file1.py found",
        )
        assert result["confirmed"] is False
        assert "checklist" in result or "verification" in result

    def test_checklist_has_three_perspectives(self):
        """Verification from test engineer, QA engineer, user perspectives."""
        runner = _fresh_runner()
        result = runner._handle_task_complete(
            first_attempt=True,
            task=_basic_task(),
            output_so_far="task done",
        )
        checklist = result.get("checklist", result.get("verification", ""))
        checklist_str = str(checklist).lower()
        # Should reference multiple perspectives
        assert any(p in checklist_str for p in ["test", "qa", "user", "engineer", "verify"])

    def test_second_completion_confirms(self):
        runner = _fresh_runner()
        result = runner._handle_task_complete(
            first_attempt=False,
            task=_basic_task(),
            output_so_far="verified and confirmed",
        )
        assert result["confirmed"] is True

    def test_agent_loop_respects_double_confirmation(self):
        """Agent loop should not terminate on first task_complete."""
        runner = _fresh_runner()
        # First response: task_complete=True (first time)
        responses = [
            json.dumps({
                "analysis": "Task appears done",
                "plan": "Verify completion",
                "commands": [],
                "task_complete": True,
            }),
            json.dumps({
                "analysis": "Verified from all perspectives",
                "plan": "Confirm completion",
                "commands": [],
                "task_complete": True,
            }),
        ]
        call_count = [0]

        def mock_generate(*args, **kwargs):
            idx = min(call_count[0], len(responses) - 1)
            call_count[0] += 1
            return responses[idx]

        with patch("src.core.llm_gateway.llm_gateway.generate_for_task", side_effect=mock_generate), \
             patch.object(runner, "_create_tmux_session", return_value="session-1"), \
             patch.object(runner, "_destroy_tmux_session"), \
             patch.object(runner, "_gather_env_snapshot", return_value={"cwd": "/tmp"}):
            loop_result = runner._run_agent_loop("session-1", _basic_task(), {"cwd": "/tmp"})
            # Agent should have been called at least twice (first complete + verification)
            assert call_count[0] >= 2


# ===========================================================================
# Group 7: Proactive Context Summarization
# ===========================================================================

class TestContextSummarization:
    """Context management to prevent overflow in long sessions."""

    def test_message_history_tracks_turns(self):
        runner = _fresh_runner()
        history = runner._create_message_history()
        assert isinstance(history, list) or hasattr(history, "append")

    def test_summarize_triggers_on_threshold(self):
        """Should summarize when message count exceeds threshold."""
        runner = _fresh_runner()
        # Build up a long message history
        history = []
        for i in range(runner._max_history_before_summarize + 5):
            history.append({"role": "user", "content": f"Turn {i} output"})
            history.append({"role": "assistant", "content": f"Turn {i} response"})

        with _mock_llm_generate_ctx("Summary of previous 20 turns: explored files, found bugs"):
            should_summarize = runner._should_summarize(history)
            assert should_summarize is True

    def test_summarize_produces_condensed_history(self):
        runner = _fresh_runner()
        history = [
            {"role": "user", "content": f"Turn {i}"} for i in range(30)
        ]
        with _mock_llm_generate_ctx("Condensed: explored filesystem, found 3 Python files"):
            condensed = runner._summarize_history(history)
            assert len(condensed) < len(history)

    def test_summarize_preserves_recent_messages(self):
        """Recent messages should NOT be summarized — only older ones."""
        runner = _fresh_runner()
        history = [
            {"role": "user", "content": f"Turn {i}"} for i in range(30)
        ]
        with _mock_llm_generate_ctx("Condensed: earlier turns"):
            condensed = runner._summarize_history(history)
            # Last few messages should remain intact
            assert condensed[-1]["content"] == history[-1]["content"]

    def test_context_overflow_recovery(self):
        """On context overflow error, should recover via summarization."""
        runner = _fresh_runner()
        # Simulate an overflow error from LLM
        error = runner._handle_context_overflow(
            history=[{"role": "user", "content": "x" * 100000}],
            session_id="s1",
        )
        assert error is None or isinstance(error, list)  # Returns new condensed history


# ===========================================================================
# Group 8: Runner Registration
# ===========================================================================

class TestRegistration:
    """Runner must register with the runner registry."""

    def test_terminal_roles_defined(self):
        from src.integrations.base_runner import ALL_ROLE_FAMILIES
        assert "openterminal" in ALL_ROLE_FAMILIES

    def test_runner_registered_for_terminal_operator(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("terminal_operator")
        assert runner is not None
        assert runner.name == "openterminal"

    def test_runner_registered_for_shell_expert(self):
        from src.integrations.base_runner import get_runner_for_role
        runner = get_runner_for_role("shell_expert")
        assert runner is not None
        assert runner.name == "openterminal"

    def test_runner_accessible_by_name(self):
        from src.integrations.base_runner import get_runner_by_name
        runner = get_runner_by_name("openterminal")
        assert runner is not None

    def test_runner_in_list_runners(self):
        from src.integrations.base_runner import list_runners
        runners = list_runners()
        names = [r["name"] for r in runners]
        assert "openterminal" in names


# ===========================================================================
# Group 9: Error Handling & Resilience
# ===========================================================================

class TestResilience:
    """Runner should handle failures gracefully."""

    def test_tmux_unavailable_returns_error_result(self):
        """If tmux is not installed, execute returns error RunResult."""
        with patch("src.integrations.openterminal_runner._check_tmux_available", return_value=False):
            from src.integrations.openterminal_runner import OpenTerminalRunner
            runner = OpenTerminalRunner()
            result = runner.execute(_basic_task(), "/tmp")
            assert result.status == "error"
            assert any("tmux" in e.lower() for e in result.errors)

    def test_llm_failure_returns_error_result(self):
        runner = _fresh_runner()
        with patch("src.core.llm_gateway.llm_gateway.generate_for_task", side_effect=Exception("LLM down")), \
             patch.object(runner, "_create_tmux_session", return_value="s1"), \
             patch.object(runner, "_destroy_tmux_session"), \
             patch.object(runner, "_gather_env_snapshot", return_value={}):
            result = runner.execute(_basic_task(), "/tmp")
            assert result.status == "error"

    def test_command_timeout_captured_in_metrics(self):
        runner = _fresh_runner()
        marker = runner._make_marker(1)
        with patch.object(runner, "_capture_tmux_pane", return_value="still running..."):
            found, output = runner._poll_for_marker("s1", marker, timeout=0.1)
            assert found is False

    def test_max_episodes_prevents_infinite_loop(self):
        """Agent loop must terminate after max_episodes."""
        runner = _fresh_runner()
        assert hasattr(runner, "_max_episodes")
        assert runner._max_episodes > 0
        assert runner._max_episodes <= 100  # Reasonable upper bound

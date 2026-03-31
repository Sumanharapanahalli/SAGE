"""
SAGE Framework — OpenTerminal Runner
=======================================
Terminal-native execution runner inspired by Stanford IRIS Lab's Meta-Harness.

Key innovations from Meta-Harness (https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact):
  - Environment bootstrapping: pre-discover installed tools before agent loop
  - Marker-based command polling: inject __CMDEND__N__ markers, poll tmux instead of sleeping
  - Structured reasoning enforcement: every tool call requires analysis + plan + commands
  - Double-confirmation completion: task_complete triggers verification checklist first
  - Proactive context summarization: condense history before context overflow

Workflow: bootstrap env → agent loop (reason → command → poll → observe) → verify → report

Roles: terminal_operator, shell_expert
"""

import json
import logging
import re
import shutil
import subprocess
import time
import uuid
from typing import Any, Optional

from src.integrations.base_runner import (
    BaseRunner, RunResult, VerificationReport, VerificationFinding,
    VerificationSeverity, Exercise, ExerciseScore,
    register_runner,
)

logger = logging.getLogger("Runner.openterminal")

# Role family for terminal operations
TERMINAL_ROLES = ["terminal_operator", "shell_expert"]


def _check_tmux_available() -> bool:
    """Check if tmux is installed and accessible."""
    return shutil.which("tmux") is not None


class OpenTerminalRunner(BaseRunner):
    """
    Terminal-native execution runner using tmux sessions.

    Agents execute shell commands in isolated tmux sessions with:
      - Marker-based polling (no fixed sleeps)
      - Environment pre-discovery (saves 2-5 exploratory turns)
      - Structured reasoning (analysis + plan + commands enforced)
      - Double-confirmation before task completion
      - Proactive context summarization for long sessions
    """

    def __init__(self):
        super().__init__(
            name="openterminal",
            roles=list(TERMINAL_ROLES),
            docker_image="",  # Uses host tmux, no Docker needed
        )
        self._tmux_available = _check_tmux_available()
        self._max_episodes = 50  # Max agent loop iterations
        self._max_history_before_summarize = 20  # Summarize after this many messages
        self._poll_interval = 0.2  # Seconds between tmux polls
        self._command_counter = 0  # For marker numbering

    # ── BaseRunner: execute ─────────────────────────────────────────────

    def execute(self, task: dict, workspace: str, sandbox_handle: Any = None) -> RunResult:
        run_id = self._new_run_id()
        if not self._tmux_available:
            return self._make_error(run_id, "tmux is not installed or not in PATH")

        session_id = None
        try:
            session_id = self._create_tmux_session(run_id)
            env_snapshot = self._gather_env_snapshot(session_id)
            loop_result = self._run_agent_loop(session_id, task, env_snapshot)

            return self._make_result(
                run_id=run_id,
                status=loop_result.get("status", "completed"),
                tier="direct",
                output=loop_result.get("output", ""),
                files_changed=loop_result.get("files_changed", []),
                metrics={
                    "commands_executed": loop_result.get("commands_executed", 0),
                    "episodes": loop_result.get("episodes", 0),
                    "exit_code": loop_result.get("exit_code", 0),
                    "env_snapshot": env_snapshot,
                },
            )
        except Exception as exc:
            self.logger.error("OpenTerminal execute failed: %s", exc)
            return self._make_error(run_id, str(exc))
        finally:
            if session_id:
                try:
                    self._destroy_tmux_session(session_id)
                except Exception:
                    pass

    # ── BaseRunner: verify ──────────────────────────────────────────────

    def verify(self, result: RunResult, task: dict) -> VerificationReport:
        findings = []
        score = 30.0  # Base for producing output

        if result.status == "error":
            findings.append(VerificationFinding(
                check="execution",
                severity=VerificationSeverity.ERROR,
                message="Execution failed",
                details={"errors": result.errors},
            ))
            return VerificationReport(passed=False, score=0.0, findings=findings)

        metrics = result.metrics or {}

        # Check commands executed
        cmds = metrics.get("commands_executed", 0)
        if cmds > 0:
            score += 20.0
            findings.append(VerificationFinding(
                check="commands_executed",
                severity=VerificationSeverity.PASS,
                message=f"{cmds} commands executed successfully",
            ))
        else:
            findings.append(VerificationFinding(
                check="commands_executed",
                severity=VerificationSeverity.WARNING,
                message="No commands were executed",
            ))

        # Check exit code
        exit_code = metrics.get("exit_code", -1)
        if exit_code == 0:
            score += 20.0
            findings.append(VerificationFinding(
                check="exit_code",
                severity=VerificationSeverity.PASS,
                message="Final exit code is 0",
            ))
        else:
            findings.append(VerificationFinding(
                check="exit_code",
                severity=VerificationSeverity.WARNING,
                message=f"Non-zero exit code: {exit_code}",
            ))

        # Check output is non-empty
        if result.output and len(result.output.strip()) > 0:
            score += 15.0
            findings.append(VerificationFinding(
                check="output_captured",
                severity=VerificationSeverity.PASS,
                message="Output captured from terminal",
            ))

        # Check acceptance criteria (keyword match)
        criteria = task.get("acceptance_criteria", [])
        if criteria:
            matched = sum(
                1 for c in criteria
                if c.lower() in (result.output or "").lower()
            )
            if matched > 0:
                score += 15.0 * (matched / len(criteria))

        score = min(score, 100.0)
        return VerificationReport(
            passed=score >= 50.0,
            score=round(score, 1),
            findings=findings,
        )

    # ── BaseRunner: get_exercises ───────────────────────────────────────

    def get_exercises(self, difficulty: str = "intermediate") -> list[Exercise]:
        catalog = self._load_catalog_exercises(difficulty)
        if catalog:
            return catalog

        # Fallback: minimal built-in exercises
        return [
            Exercise(
                id="term-b01",
                role="terminal_operator",
                task_type="terminal_execution",
                difficulty="beginner",
                description="List all files in the current directory including hidden files",
                acceptance_criteria=["Output includes hidden files", "Uses ls command"],
                expected_artifacts=[],
                tags=["shell", "filesystem", "basics"],
            ),
        ]

    # ── BaseRunner: grade_exercise ──────────────────────────────────────

    def grade_exercise(self, exercise: Exercise, result: RunResult) -> ExerciseScore:
        structural_score = 0.0
        structural_criteria = {}
        hints = []

        # Check completion
        if result.status == "completed":
            structural_score += 30.0
            structural_criteria["completed"] = True
        else:
            structural_criteria["completed"] = False
            hints.append("Task did not complete successfully")

        # Check exit code
        exit_code = (result.metrics or {}).get("exit_code", -1)
        if exit_code == 0:
            structural_score += 20.0
            structural_criteria["clean_exit"] = True
        else:
            structural_criteria["clean_exit"] = False
            hints.append(f"Non-zero exit code: {exit_code}")

        # Check commands executed
        cmds = (result.metrics or {}).get("commands_executed", 0)
        if cmds > 0:
            structural_score += 15.0
            structural_criteria["commands_run"] = True
        else:
            structural_criteria["commands_run"] = False
            hints.append("No commands were executed")

        # Check acceptance criteria via keyword match
        output_lower = (result.output or "").lower()
        for criterion in exercise.acceptance_criteria:
            key = f"criterion:{criterion[:40]}"
            if criterion.lower() in output_lower:
                structural_criteria[key] = True
                structural_score += 35.0 / max(len(exercise.acceptance_criteria), 1)
            else:
                structural_criteria[key] = False
                hints.append(f"Unmet: {criterion}")

        return self._combined_grade(
            exercise, result,
            structural_score=min(structural_score, 100.0),
            structural_criteria=structural_criteria,
            structural_hints=hints,
            domain_context="Terminal/shell command execution domain.",
        )

    # ── Toolchain & Workflow ────────────────────────────────────────────

    def get_toolchain(self) -> dict:
        base = super().get_toolchain()
        base["tools"] = list(set(base.get("tools", []) + [
            "tmux", "bash", "find", "grep", "awk", "sed", "curl", "wget",
            "python3", "git", "ssh", "tar", "gzip",
        ]))
        return base

    def get_workflow(self) -> list[dict]:
        return [
            {"step": 1, "name": "env_discovery", "description": "Bootstrap environment snapshot"},
            {"step": 2, "name": "agent_loop", "description": "ReAct loop: reason → command → observe"},
            {"step": 3, "name": "verify", "description": "Double-confirmation + verification"},
            {"step": 4, "name": "report", "description": "Collect output and artifacts"},
        ]

    # ── Tmux Session Management ─────────────────────────────────────────

    def _create_tmux_session(self, task_id: str) -> str:
        """Create a new tmux session for isolated terminal execution."""
        session_id = f"sage-term-{task_id[:12]}"
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_id, "-x", "200", "-y", "50"],
            capture_output=True, text=True, timeout=10,
        )
        self.logger.info("Created tmux session: %s", session_id)
        return session_id

    def _destroy_tmux_session(self, session_id: str) -> None:
        """Kill a tmux session."""
        subprocess.run(
            ["tmux", "kill-session", "-t", session_id],
            capture_output=True, text=True, timeout=10,
        )
        self.logger.info("Destroyed tmux session: %s", session_id)

    def _capture_tmux_pane(self, session_id: str) -> str:
        """Capture current tmux pane content."""
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", session_id, "-p", "-S", "-1000"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout

    def _send_tmux_keys(self, session_id: str, keys: str) -> None:
        """Send keystrokes to a tmux session."""
        subprocess.run(
            ["tmux", "send-keys", "-t", session_id, keys, "Enter"],
            capture_output=True, text=True, timeout=10,
        )

    # ── Marker-Based Command Polling ────────────────────────────────────

    def _make_marker(self, index: int) -> str:
        """Generate a unique command-end marker."""
        return f"__CMDEND__{index}__"

    def _inject_marker(self, command: str, index: int) -> str:
        """Append marker echo after a command."""
        marker = self._make_marker(index)
        return f"{command} ; echo '{marker}'"

    def _poll_for_marker(
        self, session_id: str, marker: str, timeout: float = 60.0
    ) -> tuple[bool, str]:
        """
        Poll tmux pane until marker appears or timeout.

        Returns (found, output_text).
        Fast commands finish immediately instead of sleeping for fixed duration.
        """
        start = time.monotonic()
        while (time.monotonic() - start) < timeout:
            pane = self._capture_tmux_pane(session_id)
            if marker in pane:
                # Extract output before marker
                idx = pane.rfind(marker)
                output = pane[:idx] if idx >= 0 else pane
                return True, output
            time.sleep(self._poll_interval)
        # Timeout — return what we have
        pane = self._capture_tmux_pane(session_id)
        return False, pane

    # ── Environment Bootstrapping ───────────────────────────────────────

    def _gather_env_snapshot(self, session_id: str) -> dict:
        """
        Pre-discover the sandbox environment before starting the agent loop.

        Runs a compound shell command to capture:
          - Working directory
          - Installed languages/compilers
          - Available package managers
          - System info (OS, memory, disk)

        This saves 2-5 exploratory turns that agents typically waste.
        """
        snapshot = {
            "cwd": "",
            "languages": {},
            "tools_available": [],
            "system": {},
        }

        # Single compound command to gather everything
        discovery_cmd = (
            "echo '===CWD===' && pwd && "
            "echo '===PYTHON===' && (python3 --version 2>&1 || echo 'not found') && "
            "echo '===GCC===' && (gcc --version 2>&1 | head -1 || echo 'not found') && "
            "echo '===NODE===' && (node --version 2>&1 || echo 'not found') && "
            "echo '===RUST===' && (rustc --version 2>&1 || echo 'not found') && "
            "echo '===GO===' && (go version 2>&1 || echo 'not found') && "
            "echo '===JAVA===' && (java -version 2>&1 | head -1 || echo 'not found') && "
            "echo '===OS===' && (uname -sr 2>&1 || echo 'unknown') && "
            "echo '===MEM===' && (free -m 2>/dev/null | head -2 || echo 'unknown') && "
            "echo '===DISK===' && (df -h / 2>/dev/null | tail -1 || echo 'unknown')"
        )

        marker_idx = 0
        self._send_tmux_keys(session_id, self._inject_marker(discovery_cmd, marker_idx))
        found, output = self._poll_for_marker(
            session_id, self._make_marker(marker_idx), timeout=15
        )

        if not found:
            self.logger.warning("Environment discovery timed out — using partial snapshot")
            return snapshot

        # Parse sections
        try:
            sections = {}
            current_section = None
            for line in output.split("\n"):
                line = line.strip()
                if line.startswith("===") and line.endswith("==="):
                    current_section = line.strip("=")
                elif current_section and line:
                    sections.setdefault(current_section, []).append(line)

            snapshot["cwd"] = " ".join(sections.get("CWD", ["unknown"]))
            snapshot["working_directory"] = snapshot["cwd"]

            # Parse languages
            for lang in ["PYTHON", "GCC", "NODE", "RUST", "GO", "JAVA"]:
                val = " ".join(sections.get(lang, []))
                if val and "not found" not in val.lower():
                    snapshot["languages"][lang.lower()] = val
                    snapshot["tools_available"].append(lang.lower())

            # Parse system info
            snapshot["system"]["os"] = " ".join(sections.get("OS", ["unknown"]))
            snapshot["system"]["memory"] = " ".join(sections.get("MEM", ["unknown"]))
            snapshot["system"]["disk"] = " ".join(sections.get("DISK", ["unknown"]))

        except Exception as exc:
            self.logger.debug("Env snapshot parse error: %s", exc)

        return snapshot

    # ── Agent Loop ──────────────────────────────────────────────────────

    def _run_agent_loop(
        self, session_id: str, task: dict, env_snapshot: dict
    ) -> dict:
        """
        Main agent loop: reason → command → poll → observe.

        Iterates up to _max_episodes. Each iteration:
          1. Call LLM with structured tool schema
          2. Parse response (analysis + plan + commands)
          3. Execute commands with marker polling
          4. Feed output back
          5. Handle task_complete with double-confirmation
        """
        from src.core.llm_gateway import llm_gateway

        history = self._create_message_history()
        initial_prompt = self._build_initial_prompt(task, env_snapshot)
        all_output = []
        commands_executed = 0
        task_complete_seen = False
        last_exit_code = 0

        for episode in range(self._max_episodes):
            # Check if we need context summarization
            if self._should_summarize(history):
                history = self._summarize_history(history)

            # Build prompt with history
            prompt = initial_prompt if episode == 0 else self._build_turn_prompt(
                history, all_output[-1] if all_output else ""
            )

            try:
                response = llm_gateway.generate_for_task(
                    task_type="TERMINAL",
                    prompt=prompt,
                    system_prompt=self._get_system_prompt(),
                    trace_name=f"openterminal.loop.{episode}",
                )
            except Exception as exc:
                self.logger.error("LLM call failed at episode %d: %s", episode, exc)
                raise

            # Parse structured response
            parsed = self._parse_agent_response(response)
            history.append({"role": "assistant", "content": response})

            # Handle task completion
            if parsed.get("task_complete"):
                completion = self._handle_task_complete(
                    first_attempt=not task_complete_seen,
                    task=task,
                    output_so_far="\n".join(all_output),
                )
                if completion["confirmed"]:
                    return {
                        "status": "completed",
                        "output": "\n".join(all_output),
                        "commands_executed": commands_executed,
                        "episodes": episode + 1,
                        "exit_code": last_exit_code,
                    }
                task_complete_seen = True
                # Feed verification checklist back to agent
                history.append({
                    "role": "user",
                    "content": json.dumps(completion),
                })
                continue

            # Execute commands with marker-based polling
            for cmd_spec in parsed.get("commands", []):
                cmd = cmd_spec.get("command", "")
                if not cmd:
                    continue
                duration = cmd_spec.get("duration", 30)
                self._command_counter += 1
                injected = self._inject_marker(cmd, self._command_counter)
                self._send_tmux_keys(session_id, injected)

                found, output = self._poll_for_marker(
                    session_id,
                    self._make_marker(self._command_counter),
                    timeout=min(duration * 2, 600),
                )
                commands_executed += 1
                all_output.append(output)
                history.append({"role": "user", "content": f"Output:\n{output[:4000]}"})

        return {
            "status": "completed",
            "output": "\n".join(all_output),
            "commands_executed": commands_executed,
            "episodes": self._max_episodes,
            "exit_code": last_exit_code,
        }

    # ── Structured Reasoning ────────────────────────────────────────────

    def _get_system_prompt(self) -> str:
        """System prompt enforcing structured reasoning at every turn."""
        return (
            "You are a senior terminal/shell expert solving tasks in a Linux environment.\n\n"
            "You MUST respond in valid JSON with these fields:\n"
            "{\n"
            '  "analysis": "Your analysis of the current state and what you observe",\n'
            '  "plan": "Your step-by-step plan for what to do next",\n'
            '  "commands": [\n'
            '    {"command": "the shell command to execute", "duration": 5}\n'
            "  ],\n"
            '  "task_complete": false\n'
            "}\n\n"
            "Rules:\n"
            "- ALWAYS provide analysis and plan before any command\n"
            "- Set duration to expected seconds for the command to complete\n"
            '- Set task_complete to true ONLY when the task is fully done\n'
            "- Use pipes, redirects, and compound commands efficiently\n"
            "- Check command output before proceeding to next step\n"
            "- If a command fails, analyze why and adjust your plan\n"
        )

    def _parse_agent_response(self, response: str) -> dict:
        """
        Parse structured agent response.

        Expects JSON with: analysis, plan, commands, task_complete.
        Returns parsed dict with 'valid' flag if structure is incomplete.
        """
        try:
            # Extract JSON from response (may have markdown wrapping)
            cleaned = response.replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{[\s\S]*\}', cleaned)
            if not match:
                return {"valid": False, "analysis": "", "plan": "", "commands": [], "task_complete": False}

            parsed = json.loads(match.group(0))

            # Validate required fields
            analysis = parsed.get("analysis", "")
            plan = parsed.get("plan", "")
            commands = parsed.get("commands", [])
            task_complete = parsed.get("task_complete", False)

            # Validate command structure
            validated_commands = []
            for cmd in commands:
                if isinstance(cmd, dict) and "command" in cmd:
                    validated_commands.append({
                        "command": cmd["command"],
                        "duration": cmd.get("duration", cmd.get("timeout", 30)),
                    })

            return {
                "valid": bool(analysis and plan),
                "analysis": analysis,
                "plan": plan,
                "commands": validated_commands,
                "task_complete": task_complete,
            }

        except (json.JSONDecodeError, AttributeError):
            return {"valid": False, "analysis": "", "plan": "", "commands": [], "task_complete": False}

    def _build_initial_prompt(self, task: dict, env_snapshot: dict) -> str:
        """Build the first prompt with task + environment context."""
        env_text = json.dumps(env_snapshot, indent=2, default=str)
        return (
            f"## Task\n{task.get('description', '')}\n\n"
            f"## Acceptance Criteria\n"
            + "\n".join(f"- {c}" for c in task.get("acceptance_criteria", []))
            + f"\n\n## Environment\n```json\n{env_text}\n```\n\n"
            "Analyze the environment and task, then execute the necessary commands."
        )

    def _build_turn_prompt(self, history: list, last_output: str) -> str:
        """Build subsequent turn prompts with observation."""
        return (
            f"## Terminal Output\n```\n{last_output[:4000]}\n```\n\n"
            "Analyze the output, update your plan, and execute the next commands."
        )

    # ── Double-Confirmation Completion ──────────────────────────────────

    def _handle_task_complete(
        self, first_attempt: bool, task: dict, output_so_far: str
    ) -> dict:
        """
        Handle task completion with double-confirmation pattern.

        First call: return verification checklist (agent must verify from 3 perspectives).
        Second call: confirm completion.
        """
        if first_attempt:
            checklist = (
                "Before confirming completion, verify from THREE perspectives:\n\n"
                "1. **Test Engineer**: Does the output match ALL acceptance criteria?\n"
                f"   Criteria: {task.get('acceptance_criteria', [])}\n\n"
                "2. **QA Engineer**: Are there edge cases not covered? Any error output?\n"
                "   Check for: warnings, partial failures, unexpected output\n\n"
                "3. **User**: Would the person who requested this task be satisfied?\n"
                f"   Task: {task.get('description', '')}\n\n"
                "Review the output and set task_complete=true again ONLY if all checks pass."
            )
            return {
                "confirmed": False,
                "checklist": checklist,
                "verification": "Please verify from test/QA/user perspectives before confirming.",
            }
        else:
            return {"confirmed": True}

    # ── Context Summarization ───────────────────────────────────────────

    def _create_message_history(self) -> list:
        """Create a new message history list."""
        return []

    def _should_summarize(self, history: list) -> bool:
        """Check if history exceeds summarization threshold."""
        return len(history) > self._max_history_before_summarize

    def _summarize_history(self, history: list) -> list:
        """
        Proactively summarize older messages to prevent context overflow.

        Keeps the last 6 messages intact, summarizes everything before.
        """
        if len(history) <= 6:
            return history

        keep_recent = 6
        old_messages = history[:-keep_recent]
        recent = history[-keep_recent:]

        try:
            from src.core.llm_gateway import llm_gateway
            old_text = "\n".join(
                f"[{m.get('role', 'unknown')}]: {str(m.get('content', ''))[:200]}"
                for m in old_messages
            )
            summary = llm_gateway.generate(
                f"Summarize this conversation history concisely, preserving key findings and state:\n\n{old_text}",
                system_prompt="You are a conversation summarizer. Be concise but preserve all important details.",
                trace_name="openterminal.summarize",
            )
            return [{"role": "system", "content": f"[Summary of earlier turns]: {summary}"}] + recent
        except Exception:
            # If summarization fails, just keep recent
            return [{"role": "system", "content": "[Earlier turns truncated]"}] + recent

    def _handle_context_overflow(self, history: list, session_id: str) -> Optional[list]:
        """Recover from context overflow by aggressive summarization."""
        try:
            return self._summarize_history(history)
        except Exception:
            # Last resort: keep only most recent messages
            return history[-4:] if len(history) > 4 else history


# ---------------------------------------------------------------------------
# Module-level registration
# ---------------------------------------------------------------------------

try:
    _runner = OpenTerminalRunner()
    register_runner(_runner)
except Exception as _exc:
    logger.debug("OpenTerminal runner registration skipped: %s", _exc)

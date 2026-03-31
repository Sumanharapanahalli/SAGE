"""
SAGE CodingAgent — Autonomous code implementation with HITL diff review.

The agent uses a ReAct (Reason + Act) loop with filesystem tools to:
  1. Explore the SAGE codebase
  2. Write code changes directly to disk
  3. Run tests to verify
  4. Surface the diff as a ProposalStore entry for director review

No code is committed until a director approves the code_diff proposal.
On rejection the working tree is reverted cleanly.
"""
import json
import logging
import os
import subprocess

logger = logging.getLogger("CodingAgent")

# Project root — two levels up from src/agents/
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class CodingAgent:
    """
    Autonomous coding agent. Implements tasks from an approved plan,
    proposes the resulting diff for director approval.
    """

    def __init__(self):
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            from src.core.llm_gateway import llm_gateway
            self._llm = llm_gateway
        return self._llm

    # -----------------------------------------------------------------------
    # Tools
    # -----------------------------------------------------------------------

    def _tool_read_file(self, path: str) -> str:
        """Read a file from the SAGE codebase. Path is relative to project root."""
        try:
            full = os.path.join(_ROOT, path)
            with open(full, encoding="utf-8", errors="replace") as f:
                content = f.read()
            # Truncate very large files
            if len(content) > 8000:
                content = content[:8000] + f"\n... [truncated — {len(content)} total chars]"
            return content
        except FileNotFoundError:
            return f"ERROR: File not found: {path}"
        except Exception as exc:
            return f"ERROR reading {path}: {exc}"

    def _tool_write_file(self, path: str, content: str) -> str:
        """Write content to a file in the SAGE codebase. Creates parent dirs if needed."""
        try:
            full = os.path.join(_ROOT, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            return f"OK: wrote {len(content)} chars to {path}"
        except Exception as exc:
            return f"ERROR writing {path}: {exc}"

    def _tool_list_dir(self, path: str = "") -> str:
        """List files and directories at path (relative to project root)."""
        try:
            full = os.path.join(_ROOT, path) if path else _ROOT
            entries = []
            for name in sorted(os.listdir(full)):
                item = os.path.join(full, name)
                entries.append(f"{'d' if os.path.isdir(item) else 'f'}  {name}")
            return "\n".join(entries[:60]) or "(empty)"
        except Exception as exc:
            return f"ERROR listing {path}: {exc}"

    def _tool_search_code(self, pattern: str, path: str = "src") -> str:
        """Search code with grep. pattern is a regex, path is relative to project root."""
        try:
            full_path = os.path.join(_ROOT, path)
            result = subprocess.run(
                ["grep", "-rn", "--include=*.py", "--include=*.ts", "--include=*.tsx",
                 "-m", "30", pattern, full_path],
                capture_output=True, text=True, timeout=10,
            )
            out = result.stdout[:3000]
            # Make paths relative
            out = out.replace(_ROOT + os.sep, "").replace(_ROOT + "/", "")
            return out or "(no matches)"
        except Exception as exc:
            return f"ERROR searching: {exc}"

    def _tool_run_tests(self, scope: str = "framework") -> str:
        """Run tests. scope: 'framework' runs pytest, 'web' runs npm build."""
        try:
            if scope == "web":
                result = subprocess.run(
                    ["npm", "run", "build"],
                    capture_output=True, text=True, timeout=120,
                    cwd=os.path.join(_ROOT, "web"),
                )
                ok = result.returncode == 0
                out = (result.stdout + result.stderr)[-2000:]
                return f"{'PASS' if ok else 'FAIL'} (returncode={result.returncode})\n{out}"
            else:
                venv_python = os.path.join(_ROOT, ".venv", "Scripts", "python")
                if not os.path.exists(venv_python):
                    venv_python = os.path.join(_ROOT, ".venv", "bin", "python")
                result = subprocess.run(
                    [venv_python, "-m", "pytest", "tests/", "-x", "-q", "--tb=short"],
                    capture_output=True, text=True, timeout=180,
                    cwd=_ROOT,
                )
                ok = result.returncode == 0
                out = (result.stdout + result.stderr)[-3000:]
                return f"{'PASS' if ok else 'FAIL'} (returncode={result.returncode})\n{out}"
        except subprocess.TimeoutExpired:
            return "TIMEOUT: tests took too long"
        except Exception as exc:
            return f"ERROR running tests: {exc}"

    def _tool_git_diff(self) -> str:
        """Show the current git diff (all uncommitted changes)."""
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD"],
                capture_output=True, text=True, timeout=10, cwd=_ROOT,
            )
            diff = result.stdout or ""
            if not diff.strip():
                # Also check staged
                result2 = subprocess.run(
                    ["git", "diff", "--cached"],
                    capture_output=True, text=True, timeout=10, cwd=_ROOT,
                )
                diff = result2.stdout or ""
            return diff[:6000] if diff.strip() else "(no changes detected)"
        except Exception as exc:
            return f"ERROR getting diff: {exc}"

    # -----------------------------------------------------------------------
    # ReAct loop
    # -----------------------------------------------------------------------

    def _react_loop(self, task: str, max_steps: int = 12) -> tuple:
        """
        Run the ReAct loop. Returns (final_answer: str, written_files: list[str]).
        """
        tools = {
            "read_file":    self._tool_read_file,
            "write_file":   self._tool_write_file,
            "list_dir":     self._tool_list_dir,
            "search_code":  self._tool_search_code,
            "run_tests":    self._tool_run_tests,
            "git_diff":     self._tool_git_diff,
        }

        # Merge MCP tools exported in React-compatible format (best-effort)
        try:
            from src.integrations.mcp_registry import mcp_registry
            mcp_tools = mcp_registry.as_react_tools()
            tools.update(mcp_tools)
        except Exception:
            pass  # MCP tools are supplementary

        tool_descriptions = "\n".join(
            f"  - {name}({', '.join(fn.__code__.co_varnames[1:fn.__code__.co_argcount])}): {fn.__doc__.strip().splitlines()[0]}"
            for name, fn in tools.items()
        )

        system_prompt = (
            "You are a TEXT-ONLY planning agent. You output ONLY the formatted lines below — nothing else.\n"
            "You do NOT write files yourself. You do NOT use any built-in tools or code execution.\n"
            "The CodingAgent Python process will call the actual tools based on your text output.\n\n"
            "Task: implement the given software engineering step on the SAGE Framework codebase.\n\n"
            "Available tool calls (you emit these as text — Python executes them):\n"
            f"{tool_descriptions}\n\n"
            "STRICT output format — one of these per response, nothing else:\n"
            "  Thought: <your reasoning>\n"
            "  Action: tool_name({\"arg\": \"value\"})\n"
            "OR when all changes are done:\n"
            "  Thought: <final reasoning>\n"
            "  FinalAnswer: <plain-text summary of what was implemented>\n\n"
            "CRITICAL RULES:\n"
            "  1. Output ONLY the Thought+Action or Thought+FinalAnswer lines. No prose, no markdown.\n"
            "  2. Do NOT ask for permissions. Do NOT use file dialogs. Do NOT say 'I need permission'.\n"
            "  3. To write a file, emit: Action: write_file({\"path\": \"...\", \"content\": \"...\"})\n"
            "  4. Always read existing files first before writing.\n"
            "  5. Write minimal focused changes — do not refactor unrelated code.\n"
            "  6. Run tests after writing, then call git_diff before FinalAnswer.\n"
            "  7. FinalAnswer must be plain text (not JSON, not markdown headers)."
        )

        history = [f"Task: {task}"]
        written_files = []

        for step in range(max_steps):
            user_prompt = "\n\n".join(history) + "\n\nStep:"
            response = self.llm.generate(user_prompt, system_prompt, trace_name="coder.react")
            history.append(f"Step {step + 1}:\n{response}")

            if "FinalAnswer:" in response:
                idx = response.index("FinalAnswer:")
                return response[idx + len("FinalAnswer:"):].strip(), written_files

            if "Action:" in response:
                action_idx = response.index("Action:")
                action_line = response[action_idx + len("Action:"):].split("\n")[0].strip()
                try:
                    tool_name = action_line[: action_line.index("(")].strip()
                    args_str  = action_line[action_line.index("(") + 1 : action_line.rindex(")")].strip()
                    tool_args = json.loads(args_str) if args_str else {}
                except (ValueError, json.JSONDecodeError) as exc:
                    history.append(f"Observation: Error parsing action '{action_line}': {exc}")
                    continue

                if tool_name in tools:
                    try:
                        obs = tools[tool_name](**tool_args)
                        if tool_name == "write_file" and "ERROR" not in str(obs):
                            written_files.append(tool_args.get("path", ""))
                    except Exception as exc:
                        obs = f"Error executing {tool_name}: {exc}"
                else:
                    obs = f"Unknown tool '{tool_name}'. Available: {list(tools.keys())}"

                history.append(f"Observation: {str(obs)[:2000]}")

        # Max steps reached — force final answer
        forced = "\n\n".join(history) + "\n\nYou have reached the step limit. Summarise what was done:"
        response = self.llm.generate(forced, system_prompt, trace_name="coder.react.final")
        return response, written_files

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    def implement_step(self, step: dict, plan_trace_id: str = "") -> dict:
        """
        Implement a single plan step. Returns a dict suitable for creating
        a code_diff ProposalStore entry.

        Args:
            step:           A plan step dict with task_type, description, payload.
            plan_trace_id:  The parent plan's trace_id for correlation.

        Returns:
            dict with: summary, diff, written_files, test_result
        """
        description = step.get("description", str(step))
        payload     = step.get("payload", {})

        task = (
            f"{description}\n"
            + (f"Additional context: {json.dumps(payload)}" if payload else "")
        )

        logger.info("CodingAgent: implementing '%s'", description[:80])

        summary, written_files = self._react_loop(task)
        diff = self._tool_git_diff()
        test_result = self._tool_run_tests("framework")

        logger.info(
            "CodingAgent: done. files_written=%d tests=%s",
            len(written_files), "PASS" if "PASS" in test_result else "FAIL",
        )

        return {
            "summary":       summary,
            "diff":          diff,
            "written_files": written_files,
            "test_result":   test_result,
            "tests_passed":  "PASS" in test_result,
            "plan_trace_id": plan_trace_id,
            "step":          step,
        }


# Global singleton
coding_agent = CodingAgent()

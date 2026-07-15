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
from typing import Optional

logger = logging.getLogger("CodingAgent")

# Project root — two levels up from src/agents/
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class CodingAgent:
    """
    Autonomous coding agent. Implements tasks from an approved plan,
    proposes the resulting diff for director approval.
    """

    def __init__(self, root: str = None):
        self._llm = None
        # The write/read/exec root. Defaults to the SAGE checkout for existing callers, but
        # the Merge-Gate runner injects the MR's isolated WORKTREE so the agent writes into
        # the branch — not the live tree (the old behaviour, gap B6, committed nothing).
        self.root = root or _ROOT
        # Isolated mode: a root was explicitly injected (worktree). In this mode the agent
        # must not load MCP tools, which ignore self.root and would write outside the branch.
        self._isolated = root is not None

    @property
    def llm(self):
        if self._llm is None:
            from src.core.llm_gateway import llm_gateway

            self._llm = llm_gateway
        return self._llm

    # -----------------------------------------------------------------------
    # Tools
    # -----------------------------------------------------------------------

    def _contained(self, path: str) -> str:
        """Resolve *path* under self.root and REFUSE anything that escapes it.

        os.path.join(root, abs_path) silently discards root and returns abs_path — so an
        LLM that writes with an absolute path (or a `..` traversal) escapes the worktree and
        edits the live tree. That is exactly how the first Merge-Gate dogfood leaked into
        main. All file tools resolve through here; an out-of-root path raises ValueError.
        """
        root = os.path.abspath(self.root)
        full = os.path.abspath(os.path.join(root, path))
        if os.path.commonpath([root, full]) != root:
            raise ValueError(f"path escapes the agent root: {path!r}")
        return full

    def _tool_read_file(self, path: str) -> str:
        """Read a file from the SAGE codebase. Path is relative to project root."""
        try:
            full = self._contained(path)
            with open(full, encoding="utf-8", errors="replace") as f:
                content = f.read()
            # Truncate very large files
            if len(content) > 8000:
                content = (
                    content[:8000] + f"\n... [truncated — {len(content)} total chars]"
                )
            return content
        except FileNotFoundError:
            return f"ERROR: File not found: {path}"
        except Exception as exc:
            return f"ERROR reading {path}: {exc}"

    def _tool_write_file(self, path: str, content: str) -> str:
        """Write content to a file in the SAGE codebase. Creates parent dirs if needed."""
        try:
            full = self._contained(path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            return f"OK: wrote {len(content)} chars to {path}"
        except Exception as exc:
            return f"ERROR writing {path}: {exc}"

    def _tool_list_dir(self, path: str = "") -> str:
        """List files and directories at path (relative to project root)."""
        try:
            full = self._contained(path) if path else os.path.abspath(self.root)
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
            full_path = self._contained(path)
            result = subprocess.run(
                [
                    "grep",
                    "-rn",
                    "--include=*.py",
                    "--include=*.ts",
                    "--include=*.tsx",
                    "-m",
                    "30",
                    pattern,
                    full_path,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            out = result.stdout[:3000]
            # Make paths relative
            out = out.replace(self.root + os.sep, "").replace(self.root + "/", "")
            return out or "(no matches)"
        except Exception as exc:
            return f"ERROR searching: {exc}"

    def _tool_run_tests(self, scope: str = "framework") -> str:
        """Run tests. scope: 'framework' runs pytest, 'web' runs npm build."""
        try:
            if scope == "web":
                result = subprocess.run(
                    ["npm", "run", "build"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=os.path.join(self.root, "web"),
                )
                ok = result.returncode == 0
                out = (result.stdout + result.stderr)[-2000:]
                return f"{'PASS' if ok else 'FAIL'} (returncode={result.returncode})\n{out}"
            else:
                venv_python = os.path.join(self.root, ".venv", "Scripts", "python")
                if not os.path.exists(venv_python):
                    venv_python = os.path.join(self.root, ".venv", "bin", "python")
                result = subprocess.run(
                    [venv_python, "-m", "pytest", "tests/", "-x", "-q", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=180,
                    cwd=self.root,
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
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.root,
            )
            diff = result.stdout or ""
            if not diff.strip():
                # Also check staged
                result2 = subprocess.run(
                    ["git", "diff", "--cached"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=self.root,
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
            "read_file": self._tool_read_file,
            "write_file": self._tool_write_file,
            "list_dir": self._tool_list_dir,
            "search_code": self._tool_search_code,
            "run_tests": self._tool_run_tests,
            "git_diff": self._tool_git_diff,
        }

        # Merge MCP tools exported in React-compatible format (best-effort).
        # NOT in isolated mode: MCP tools resolve paths against the framework repo, not the
        # agent's injected root, so they would write OUTSIDE the worktree — which is exactly
        # how the first Merge-Gate dogfood leaked a change into the live checkout instead of
        # the branch. When the coder is confined to a worktree, use ONLY the built-in tools,
        # every one of which honours self.root.
        if not self._isolated:
            try:
                from src.integrations.mcp_registry import mcp_registry

                tools.update(mcp_registry.as_react_tools())
            except Exception:
                pass  # MCP tools are supplementary

        def _describe(name, fn) -> str:
            # Robust against tools that lack a docstring or a __code__ (MCP/wrapped
            # callables) — the old direct fn.__doc__.strip() / fn.__code__ access crashed
            # the whole loop the moment any such tool was registered.
            try:
                params = ", ".join(fn.__code__.co_varnames[1 : fn.__code__.co_argcount])
            except AttributeError:
                params = ""
            doc = (fn.__doc__ or "").strip()
            first = doc.splitlines()[0] if doc else name
            return f"  - {name}({params}): {first}"

        tool_descriptions = "\n".join(_describe(name, fn) for name, fn in tools.items())

        system_prompt = (
            "You are a TEXT-ONLY planning agent. You output ONLY the formatted lines below — nothing else.\n"
            "You do NOT write files yourself. You do NOT use any built-in tools or code execution.\n"
            "The CodingAgent Python process will call the actual tools based on your text output.\n\n"
            "Task: implement the given software engineering step on the SAGE Framework codebase.\n\n"
            "Available tool calls (you emit these as text — Python executes them):\n"
            f"{tool_descriptions}\n\n"
            "STRICT output format — one of these per response, nothing else:\n"
            "  Thought: <your reasoning>\n"
            '  Action: tool_name({"arg": "value"})\n'
            "OR when all changes are done:\n"
            "  Thought: <final reasoning>\n"
            "  FinalAnswer: <plain-text summary of what was implemented>\n\n"
            "CRITICAL RULES:\n"
            "  1. Output ONLY the Thought+Action or Thought+FinalAnswer lines. No prose, no markdown.\n"
            "  2. Do NOT ask for permissions. Do NOT use file dialogs. Do NOT say 'I need permission'.\n"
            '  3. To write a file, emit: Action: write_file({"path": "...", "content": "..."})\n'
            "  4. Always read existing files first before writing.\n"
            "  5. Write minimal focused changes — do not refactor unrelated code.\n"
            "  6. Run tests after writing, then call git_diff before FinalAnswer.\n"
            "  7. FinalAnswer must be plain text (not JSON, not markdown headers)."
        )

        history = [f"Task: {task}"]
        written_files = []

        for step in range(max_steps):
            user_prompt = "\n\n".join(history) + "\n\nStep:"
            response = self.llm.generate(
                user_prompt, system_prompt, trace_name="coder.react"
            )
            history.append(f"Step {step + 1}:\n{response}")

            if "FinalAnswer:" in response:
                idx = response.index("FinalAnswer:")
                return response[idx + len("FinalAnswer:") :].strip(), written_files

            if "Action:" in response:
                action_idx = response.index("Action:")
                action_line = (
                    response[action_idx + len("Action:") :].split("\n")[0].strip()
                )
                try:
                    tool_name = action_line[: action_line.index("(")].strip()
                    args_str = action_line[
                        action_line.index("(") + 1 : action_line.rindex(")")
                    ].strip()
                    tool_args = json.loads(args_str) if args_str else {}
                except (ValueError, json.JSONDecodeError) as exc:
                    history.append(
                        f"Observation: Error parsing action '{action_line}': {exc}"
                    )
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
        forced = (
            "\n\n".join(history)
            + "\n\nYou have reached the step limit. Summarise what was done:"
        )
        response = self.llm.generate(
            forced, system_prompt, trace_name="coder.react.final"
        )
        return response, written_files

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    def implement_step(
        self, step: dict, plan_trace_id: str = "", beam_width: int = 1
    ) -> dict:
        """
        Implement a single plan step. Returns a dict suitable for creating
        a code_diff ProposalStore entry.

        Args:
            step:           A plan step dict with task_type, description, payload.
            plan_trace_id:  The parent plan's trace_id for correlation.
            beam_width:     If > 1, runs `beam_width` sequential ReAct-loop attempts
                            in the MAIN working tree, isolating each attempt from the
                            next via `git stash` (game-theory Phase 2, scoped-down
                            variant — no WorktreeManager, no per-candidate parallelism;
                            see docs/proposals/20260630-game-theory-for-sage). The
                            best-scoring candidate's changes are restored; the rest
                            are dropped. Falls back to single-shot if the working tree
                            isn't clean at call time (best-of-N requires a clean
                            baseline to safely isolate candidates). Default 1
                            preserves the original single-shot behaviour byte-for-byte.

        Returns:
            dict with: summary, diff, written_files, test_result
        """
        description = step.get("description", str(step))
        payload = step.get("payload", {})

        task = f"{description}\n" + (
            f"Additional context: {json.dumps(payload)}" if payload else ""
        )

        logger.info("CodingAgent: implementing '%s'", description[:80])

        if beam_width > 1 and not self._working_tree_is_clean():
            logger.warning(
                "implement_step: beam_width=%d requested but working tree is not "
                "clean — falling back to single-shot (best-of-N needs a clean "
                "baseline to safely isolate candidates).",
                beam_width,
            )
            result = self._implement_step_once(task, plan_trace_id, step)
            result["beam_search_skipped_reason"] = "working tree not clean"
            return result

        if beam_width <= 1:
            return self._implement_step_once(task, plan_trace_id, step)

        return self._implement_step_via_beam_search(
            task, plan_trace_id, step, beam_width
        )

    def _implement_step_once(self, task: str, plan_trace_id: str, step: dict) -> dict:
        """Single ReAct-loop attempt against the current working tree."""
        summary, written_files = self._react_loop(task)
        diff = self._tool_git_diff()
        test_result = self._tool_run_tests("framework")

        logger.info(
            "CodingAgent: done. files_written=%d tests=%s",
            len(written_files),
            "PASS" if "PASS" in test_result else "FAIL",
        )

        return {
            "summary": summary,
            "diff": diff,
            "written_files": written_files,
            "test_result": test_result,
            "tests_passed": "PASS" in test_result,
            "plan_trace_id": plan_trace_id,
            "step": step,
        }

    def _implement_step_via_beam_search(
        self, task: str, plan_trace_id: str, step: dict, beam_width: int
    ) -> dict:
        """Run `beam_width` sequential ReAct-loop attempts, isolated via git stash.

        Game-theory Phase 2 (scoped-down): reuses PlanSelector's existing
        N-generate→score→rank→select engine, same as the Planner and Developer
        Phase 2 wiring. Unlike those two (pure-text, no filesystem writes), each
        candidate here writes real files to the MAIN working tree — so between
        attempts the candidate's changes are stashed to restore a clean baseline
        for the next attempt. The winning candidate's stash is re-applied at the
        end; every other candidate's stash is dropped (discarded).
        """
        from src.core.plan_selector import get_plan_selector
        from src.agents.critic import critic_agent

        candidates_scored = {"n": 0}

        def _generator(ctx: str) -> dict:
            summary, written_files = self._react_loop(f"{task}\n\n{ctx}")
            diff = self._tool_git_diff()
            test_result = self._tool_run_tests("framework")
            stash_sha = self._stash_candidate()
            return {
                "summary": summary,
                "written_files": written_files,
                "diff": diff,
                "test_result": test_result,
                "tests_passed": "PASS" in test_result,
                "stash_sha": stash_sha,
            }

        def _critic(candidate: dict) -> dict:
            candidates_scored["n"] += 1
            diff = candidate.get("diff", "")
            if not diff.strip() or diff == "(no changes detected)":
                return {"score": 0.0, "feedback": "no changes produced"}
            review = critic_agent.multi_critic_review("code", diff, task)
            llm_score = review.get("score", 0)
            final = llm_score if candidate.get("tests_passed") else llm_score * 0.3
            return {"score": final / 100.0, "feedback": review.get("summary", "")}

        result = get_plan_selector().select(
            generator=_generator,
            critic=_critic,
            beam_width=beam_width,
            apply_reflection=False,  # avoid a surprise extra stash-isolated ReAct pass
        )

        candidates = [c.plan for c in result.candidates if c.plan]
        best = (
            result.candidates[result.selected_index].plan if result.candidates else None
        )

        # Restore the winner, discard every other candidate's stash.
        for c in candidates:
            sha = c.get("stash_sha")
            if not sha:
                continue
            if c is best:
                self._apply_stash(sha)
            self._drop_stash(sha)

        if not best:
            best = {
                "summary": "All candidates failed.",
                "written_files": [],
                "diff": "(no changes detected)",
                "test_result": "",
                "tests_passed": False,
            }

        return {
            "summary": best.get("summary", ""),
            "diff": best.get("diff", ""),
            "written_files": best.get("written_files", []),
            "test_result": best.get("test_result", ""),
            "tests_passed": best.get("tests_passed", False),
            "plan_trace_id": plan_trace_id,
            "step": step,
            "verification": {
                "candidates_scored": candidates_scored["n"],
                "winning_score": result.selected_score,
            },
        }

    # -----------------------------------------------------------------------
    # git-stash candidate isolation (scoped-down best-of-N — no WorktreeManager)
    # -----------------------------------------------------------------------

    def _working_tree_is_clean(self) -> bool:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0 and not result.stdout.strip()
        except Exception as exc:
            logger.warning("git status check failed: %s", exc)
            return False

    def _stash_candidate(self) -> Optional[str]:
        """Stash all current changes (tracked + untracked) and return the stash SHA, or None if there was nothing to stash."""
        try:
            result = subprocess.run(
                ["git", "stash", "push", "-u", "-m", "sage-candidate"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0 or "No local changes to save" in (
                result.stdout + result.stderr
            ):
                return None
            sha_result = subprocess.run(
                ["git", "rev-parse", "stash@{0}"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return sha_result.stdout.strip() if sha_result.returncode == 0 else None
        except Exception as exc:
            logger.warning("git stash push failed: %s", exc)
            return None

    def _apply_stash(self, sha: str) -> None:
        try:
            subprocess.run(
                ["git", "stash", "apply", sha],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except Exception as exc:
            logger.warning("git stash apply %s failed: %s", sha, exc)

    def _drop_stash(self, sha: str) -> None:
        """Resolve *sha* to its current stash@{n} ref and drop it (indices shift after every drop, so this is re-resolved each call rather than cached)."""
        try:
            list_result = subprocess.run(
                ["git", "stash", "list", "--format=%H %gd"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in list_result.stdout.splitlines():
                parts = line.split(" ", 1)
                if len(parts) == 2 and parts[0] == sha:
                    subprocess.run(
                        ["git", "stash", "drop", parts[1]],
                        cwd=self.root,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    return
        except Exception as exc:
            logger.warning("git stash drop %s failed: %s", sha, exc)


# Global singleton
coding_agent = CodingAgent()

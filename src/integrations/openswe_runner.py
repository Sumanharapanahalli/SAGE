"""
SAGE Framework — Open SWE Runner (ReAct Pattern)
==================================================
3-tier degradation for code generation tasks:
  1. External Open SWE service (OPENSWE_URL env var)
  2. swe_workflow via LangGraph runner
  3. Direct LLM with ReAct loop (always available)

The LLM fallback (Tier 3) uses the ReAct pattern:
  Thought → Action → Observation → repeat
Each iteration the agent:
  1. THINKS about what code to generate and why
  2. ACTS by generating code (one file at a time)
  3. OBSERVES by self-reviewing against acceptance criteria
  4. DECIDES: done? or another iteration to fix issues?

This produces better code than single-shot generation because the
agent catches its own mistakes before the critic sees the output.

Thread-safe singleton via get_openswe_runner().
Audit every build action; return error dicts, never raise.
"""

import json
import logging
import os
import threading
import time
import uuid
from typing import Optional

logger = logging.getLogger("OpenSWERunner")


class OpenSWERunner:
    """
    Executes code generation tasks with 3-tier degradation.

    Tier 1: External Open SWE service at OPENSWE_URL
    Tier 2: swe_workflow via LangGraph
    Tier 3: Direct LLM code generation
    """

    def __init__(self):
        self.logger = logging.getLogger("OpenSWERunner")
        self._openswe_url = os.environ.get("OPENSWE_URL", "").rstrip("/")
        self._runs: dict[str, dict] = {}

    def build(
        self,
        task: dict,
        repo_path: str = "",
        sandbox_handle=None,
    ) -> dict:
        """
        Execute a code generation task.

        Args:
            task: Dict with 'description', 'task_type', and optional 'payload'.
            repo_path: Working directory for the generated code.
            sandbox_handle: Optional OpenShell SandboxHandle for isolation.

        Returns:
            Dict with run_id, status, output, and tier used.
        """
        run_id = str(uuid.uuid4())
        description = task.get("description", "")
        self.logger.info("Build task [%s]: %s", run_id[:8], description[:80])

        # Try tiers in order
        result = self._try_external_swe(task, repo_path, sandbox_handle)
        if result is None:
            result = self._try_langgraph_swe(task, repo_path)
        if result is None:
            result = self._try_llm_fallback(task, repo_path)

        result["run_id"] = run_id
        self._runs[run_id] = result

        # Audit
        self._audit(run_id, "BUILD_TASK", result)

        return result

    def get_status(self, run_id: str) -> dict:
        """Return status of a build task."""
        meta = self._runs.get(run_id)
        if meta is None:
            return {"error": f"Run '{run_id}' not found", "run_id": run_id}
        return {
            "run_id": run_id,
            "status": meta.get("status", "unknown"),
            "tier": meta.get("tier", "unknown"),
        }

    # ------------------------------------------------------------------
    # Tier 1: External Open SWE service
    # ------------------------------------------------------------------

    def _try_external_swe(self, task: dict, repo_path: str, sandbox_handle) -> Optional[dict]:
        """Try the external Open SWE service."""
        if not self._openswe_url:
            return None

        try:
            import urllib.request
            import urllib.error

            payload = json.dumps({
                "task": task.get("description", ""),
                "task_type": task.get("task_type", ""),
                "repo_path": repo_path,
                "payload": task.get("payload", {}),
            }).encode()

            req = urllib.request.Request(
                f"{self._openswe_url}/task",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode())

            return {
                "status": "completed",
                "tier": "openswe_external",
                "output": data,
                "code": data.get("code", ""),
                "files_changed": data.get("files_changed", []),
            }
        except Exception as exc:
            self.logger.debug("External Open SWE unavailable: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Tier 2: LangGraph swe_workflow
    # ------------------------------------------------------------------

    def _try_langgraph_swe(self, task: dict, repo_path: str) -> Optional[dict]:
        """Try running the swe_workflow via LangGraph."""
        try:
            from src.integrations.langgraph_runner import langgraph_runner

            if not callable(getattr(langgraph_runner, 'run', None)):
                return None

            result = langgraph_runner.run("swe_workflow", {
                "task": task.get("description", ""),
                "task_type": task.get("task_type", ""),
                "repo_path": repo_path,
            })

            if isinstance(result, dict) and "error" not in result:
                return {
                    "status": result.get("status", "completed"),
                    "tier": "langgraph_swe",
                    "output": result,
                    "code": result.get("state", {}).get("code", ""),
                    "files_changed": result.get("state", {}).get("files_changed", []),
                }
        except Exception as exc:
            self.logger.debug("LangGraph swe_workflow unavailable: %s", exc)

        return None

    # ------------------------------------------------------------------
    # Tier 3: Direct LLM code generation
    # ------------------------------------------------------------------

    def _sanitize_prompt_input(self, text: str) -> str:
        """Strip prompt injection patterns from user-provided text."""
        lines = text.split('\n')
        sanitized = []
        for line in lines:
            stripped = line.strip().upper()
            if any(stripped.startswith(p) for p in ['IGNORE', 'BREAK', 'SYSTEM:', 'ASSISTANT:', 'HUMAN:']):
                sanitized.append(f'[FILTERED: {line[:50]}]')
            else:
                sanitized.append(line)
        return '\n'.join(sanitized)

    def _try_llm_fallback(self, task: dict, repo_path: str) -> dict:
        """
        ReAct-pattern LLM code generation (Tier 3 fallback).

        Uses iterative Thought→Action→Observation loop:
          1. THOUGHT: Reason about the task and plan the approach
          2. ACTION: Generate code for one component at a time
          3. OBSERVATION: Self-review against acceptance criteria
          4. DECIDE: Complete or iterate (max 3 rounds)

        This produces better code than single-shot because the agent
        catches its own mistakes before the critic sees the output.
        """
        try:
            from src.core.llm_gateway import llm_gateway

            description = self._sanitize_prompt_input(task.get("description", ""))
            task_type = task.get("task_type", "BACKEND")
            payload = task.get("payload", {})
            acceptance_criteria = task.get("acceptance_criteria", [])

            # --- ReAct System Prompt ---
            system_prompt = (
                "You are a senior software engineer using the ReAct pattern.\n\n"
                "For each iteration, structure your response as:\n\n"
                "THOUGHT: <your reasoning about what to build and why>\n"
                "ACTION: Generate code\n"
                "```json\n"
                "{\n"
                '  "files": [{"path": "<path>", "content": "<content>"}],\n'
                '  "explanation": "<what you built>"\n'
                "}\n"
                "```\n"
                "OBSERVATION: <self-review of what you just generated>\n"
                "STATUS: <DONE if all criteria met, or ITERATE with what to fix>\n\n"
                "Write production-ready code. Include error handling.\n"
                "Do not include markdown fences inside JSON string values."
            )

            # --- Build user prompt with context ---
            criteria_str = ""
            if acceptance_criteria:
                criteria_str = (
                    "\n\nAcceptance Criteria (ALL must be met):\n"
                    + "\n".join(f"- {c}" for c in acceptance_criteria)
                )

            user_prompt = (
                f"Task Type: {task_type}\n"
                f"Description: {description}\n"
                f"{criteria_str}\n"
            )
            if payload:
                user_prompt += f"\nAdditional Context: {json.dumps(payload)}\n"
            if repo_path:
                user_prompt += f"\nRepository Path: {repo_path}\n"

            # --- ReAct Loop ---
            max_iterations = 3
            all_files = []
            all_thoughts = []
            start = time.monotonic()
            MAX_TOTAL_SECONDS = 300  # 5 min total for all iterations

            for iteration in range(1, max_iterations + 1):
                if time.monotonic() - start > MAX_TOTAL_SECONDS:
                    self.logger.warning("ReAct loop timeout after %.0fs", time.monotonic() - start)
                    break

                if iteration > 1:
                    # Feed back the observation from the previous iteration
                    user_prompt = (
                        f"Iteration {iteration}/{max_iterations}.\n"
                        f"Previous issues to fix:\n{all_thoughts[-1]}\n\n"
                        f"Current files so far: {json.dumps([f['path'] for f in all_files])}\n\n"
                        f"Fix the issues and generate improved code. "
                        f"Only output files that need changes."
                    )

                response = llm_gateway.generate(
                    user_prompt, system_prompt,
                    trace_name=f"openswe.react_iter{iteration}",
                )

                # Parse the ReAct response
                parsed = self._parse_react_response(response)
                new_files = parsed.get("files", [])
                if not new_files and parsed.get("parse_error"):
                    self.logger.warning(
                        "ReAct iteration %d: JSON parse failed — empty files returned",
                        iteration,
                    )
                observation = parsed.get("observation", "")
                status = parsed.get("status", "DONE")

                # Merge files (later iterations override earlier for same path)
                file_map = {f["path"]: f for f in all_files}
                for f in new_files:
                    if f.get("path"):
                        file_map[f["path"]] = f
                all_files = list(file_map.values())

                all_thoughts.append(
                    f"Iteration {iteration}: {parsed.get('thought', '')} | "
                    f"Observation: {observation}"
                )

                self.logger.info(
                    "ReAct iteration %d/%d — status: %s, files: %d",
                    iteration, max_iterations, status, len(all_files),
                )

                # If the agent says DONE, stop iterating
                if "DONE" in status.upper():
                    break

            # Combine all code
            combined_code = "\n\n".join(
                f"# {f.get('path', 'unknown')}\n{f.get('content', '')}"
                for f in all_files
            )
            files_changed = [f.get("path", "") for f in all_files if f.get("path")]

            return {
                "status": "completed",
                "tier": "llm_react",
                "output": {
                    "files": all_files,
                    "react_iterations": len(all_thoughts),
                    "react_trace": all_thoughts,
                    "explanation": all_thoughts[-1] if all_thoughts else "",
                },
                "code": combined_code,
                "files_changed": files_changed,
            }

        except Exception as exc:
            self.logger.error("ReAct LLM fallback failed: %s", exc)
            return {
                "status": "error",
                "tier": "llm_react",
                "error": str(exc),
                "code": "",
                "files_changed": [],
            }

    def _parse_react_response(self, response: str) -> dict:
        """Parse a ReAct-formatted LLM response into structured data."""
        import re

        result = {"thought": "", "files": [], "observation": "", "status": "DONE"}

        # Extract THOUGHT
        thought_match = re.search(r'THOUGHT:\s*(.*?)(?=ACTION:|$)', response, re.DOTALL)
        if thought_match:
            result["thought"] = thought_match.group(1).strip()

        # Extract JSON from ACTION block
        json_match = re.search(r'```json\s*([\s\S]*?)```', response)
        if json_match:
            try:
                data = json.loads(json_match.group(1).strip())
                result["files"] = data.get("files", [])
            except json.JSONDecodeError:
                result["parse_error"] = True

        if not result["files"]:
            # Try to find any JSON object with "files" key
            obj_match = re.search(r'\{[\s\S]*"files"[\s\S]*\}', response)
            if obj_match:
                try:
                    cleaned = obj_match.group(0).replace("```json", "").replace("```", "")
                    data = json.loads(cleaned)
                    result["files"] = data.get("files", [])
                    if result["files"]:
                        result.pop("parse_error", None)
                except json.JSONDecodeError:
                    result["parse_error"] = True

        # Extract OBSERVATION
        obs_match = re.search(r'OBSERVATION:\s*(.*?)(?=STATUS:|$)', response, re.DOTALL)
        if obs_match:
            result["observation"] = obs_match.group(1).strip()

        # Extract STATUS
        status_match = re.search(r'STATUS:\s*(.*?)$', response, re.MULTILINE)
        if status_match:
            result["status"] = status_match.group(1).strip()

        return result

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def _audit(self, run_id: str, action: str, result: dict) -> None:
        """Write build event to audit log."""
        try:
            from src.memory.audit_logger import audit_logger

            audit_logger.log_event(
                actor="OpenSWERunner",
                action_type=action,
                input_context=f"run_id={run_id}",
                output_content=json.dumps(result)[:500],
                metadata={
                    "run_id": run_id,
                    "tier": result.get("tier", "unknown"),
                    "status": result.get("status", "unknown"),
                },
            )
        except Exception as exc:
            self.logger.debug("Audit failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Thread-safe singleton
# ---------------------------------------------------------------------------
_runner: Optional[OpenSWERunner] = None
_runner_lock = threading.Lock()


def get_openswe_runner() -> OpenSWERunner:
    global _runner
    if _runner is None:
        with _runner_lock:
            if _runner is None:
                _runner = OpenSWERunner()
    return _runner

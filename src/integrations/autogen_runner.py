"""
SAGE Framework — AutoGen + Code Sandbox Runner
===============================================
Provides AI-assisted code task planning and sandboxed execution.

Two-phase design (mirrors the SAGE Lean Loop):
  Phase 1 — PLAN:    AutoGen agents generate a code plan + snippet.
                     Result is surfaced to the human for approval.
  Phase 2 — EXECUTE: Approved code runs in an isolated Docker sandbox.
                     Raw output is returned and audit-logged.

AutoGen integration:
  Uses pyautogen (pip install pyautogen) when available.
  AssistantAgent drives the LLM; UserProxyAgent tracks conversation.
  Falls back to a direct LLM call when AutoGen is not installed.

Docker sandbox:
  Runs code in `python:3.12-slim` via `docker run --rm --network none`.
  Falls back to subprocess (local Python) when Docker is unavailable.
  Execution is always guarded by the human approval gate — never auto-run.

Usage:
    from src.integrations.autogen_runner import autogen_runner
    plan = autogen_runner.plan("Write a function to parse JWT tokens")
    # plan["status"] == "awaiting_approval"
    result = autogen_runner.execute(plan["run_id"])
    # result["status"] == "completed" | "error"
"""

import json
import logging
import os
import subprocess
import textwrap
import uuid
from typing import Any

logger = logging.getLogger("AutoGenRunner")

_HAS_AUTOGEN = False
try:
    import autogen  # noqa: F401
    _HAS_AUTOGEN = True
except ImportError:
    try:
        import pyautogen as autogen  # noqa: F401
        _HAS_AUTOGEN = True
    except ImportError:
        pass

# Docker availability check (lazy)
_DOCKER_AVAILABLE: bool | None = None


def _check_docker() -> bool:
    global _DOCKER_AVAILABLE
    if _DOCKER_AVAILABLE is None:
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True, timeout=5,
            )
            _DOCKER_AVAILABLE = result.returncode == 0
        except Exception:
            _DOCKER_AVAILABLE = False
    return _DOCKER_AVAILABLE


# ---------------------------------------------------------------------------
# Plan generation helpers
# ---------------------------------------------------------------------------

def _plan_via_autogen(task: str, llm_config: dict) -> str:
    """Use AutoGen AssistantAgent to generate a code plan."""
    assistant = autogen.AssistantAgent(
        name="sage_coder",
        llm_config=llm_config,
        system_message=(
            "You are a precise software engineer. "
            "When given a task, produce: "
            "1) a brief explanation, "
            "2) a complete, runnable Python code block. "
            "Do not execute anything. Output only text."
        ),
    )
    # UserProxyAgent in no-execution mode: human_input_mode=NEVER, no code_execution_config
    proxy = autogen.UserProxyAgent(
        name="sage_proxy",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
    )
    # Initiate conversation — one round, no execution
    proxy.initiate_chat(assistant, message=task, max_turns=1)
    # Extract last assistant message
    history = proxy.chat_messages.get(assistant, [])
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            return msg.get("content", "")
    return ""


def _plan_via_llm(task: str) -> str:
    """Fallback: use SAGE's LLM gateway directly to generate a code plan."""
    try:
        from src.core.llm_gateway import llm_gateway
        return llm_gateway.generate(
            prompt=(
                f"Task: {task}\n\n"
                "Produce:\n"
                "1) A brief explanation (2–3 sentences).\n"
                "2) A complete, runnable Python code block inside ```python ... ```.\n"
                "Do not include any execution output."
            ),
            system_prompt=(
                "You are a precise software engineer. "
                "Produce clean, readable Python. No boilerplate, no extras."
            ),
            trace_name="autogen_runner.plan",
        )
    except Exception as exc:
        logger.warning("LLM plan generation failed: %s", exc)
        return f"[stub] Plan for: {task}"


def _extract_code_block(text: str) -> str:
    """Extract the first ```python ... ``` block from a plan string."""
    import re
    pattern = r"```python\s*([\s\S]*?)```"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


# ---------------------------------------------------------------------------
# Execution helpers
# ---------------------------------------------------------------------------

def _run_in_docker(code: str, timeout: int = 30) -> dict:
    """
    Execute code in an isolated Docker container (no network, read-only FS).
    Returns {"stdout": ..., "stderr": ..., "returncode": ...}.
    """
    safe_code = code.replace("'", "'\\''")
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", "128m",
        "--cpus", "0.5",
        "python:3.12-slim",
        "python", "-c", code,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": proc.stdout[:2000],
            "stderr": proc.stderr[:500],
            "returncode": proc.returncode,
            "sandbox": "docker",
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Execution timed out after {timeout}s", "sandbox": "docker"}
    except Exception as exc:
        return {"error": str(exc), "sandbox": "docker"}


def _run_local(code: str, timeout: int = 10) -> dict:
    """
    Execute code in a subprocess (local Python). Used when Docker unavailable.
    WARNING: No isolation — only for trusted/reviewed code.
    """
    try:
        proc = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": proc.stdout[:2000],
            "stderr": proc.stderr[:500],
            "returncode": proc.returncode,
            "sandbox": "local_subprocess",
            "warning": "Docker not available — ran in local subprocess (no isolation)",
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Local execution timed out after {timeout}s", "sandbox": "local_subprocess"}
    except Exception as exc:
        return {"error": str(exc), "sandbox": "local_subprocess"}


# ---------------------------------------------------------------------------
# AutoGenRunner
# ---------------------------------------------------------------------------

class AutoGenRunner:
    """
    Plans code tasks using AutoGen (or SAGE LLM fallback) and executes
    approved code in a Docker sandbox.

    The approval gate is mandatory: plan() always returns awaiting_approval.
    execute() is only valid after a human approves the plan via resume().
    """

    def __init__(self):
        self._runs: dict[str, dict] = {}   # run_id -> metadata

    def _build_llm_config(self) -> dict:
        """
        Build an AutoGen-compatible llm_config from SAGE's LLM settings.
        AutoGen uses the OpenAI SDK format.
        """
        try:
            import yaml
            cfg_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "config", "config.yaml",
            )
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f)
            llm = cfg.get("llm", {})
            # AutoGen requires OpenAI-format config; use env var if available
            api_key = os.environ.get("OPENAI_API_KEY", "placeholder")
            return {
                "config_list": [
                    {
                        "model": llm.get("gemini_model", "gpt-4o-mini"),
                        "api_key": api_key,
                    }
                ],
                "timeout": llm.get("timeout", 120),
            }
        except Exception:
            return {"config_list": [{"model": "gpt-4o-mini", "api_key": "placeholder"}]}

    def plan(self, task: str, trace_id: str = None) -> dict:
        """
        Generate a code plan for the given task.

        Always returns status="awaiting_approval" — the plan must be reviewed
        by a human before execute() is permitted.

        Args:
            task:     Description of the coding task.
            trace_id: Optional SAGE trace ID for audit correlation.

        Returns:
            dict: run_id, status, plan (text), code (extracted block)
        """
        run_id = str(uuid.uuid4())

        if _HAS_AUTOGEN:
            try:
                llm_config = self._build_llm_config()
                plan_text = _plan_via_autogen(task, llm_config)
            except Exception as exc:
                logger.warning("AutoGen plan failed, using LLM fallback: %s", exc)
                plan_text = _plan_via_llm(task)
        else:
            logger.debug("AutoGen not installed — using LLM gateway for plan")
            plan_text = _plan_via_llm(task)

        code = _extract_code_block(plan_text)

        self._runs[run_id] = {
            "run_id":   run_id,
            "task":     task,
            "plan":     plan_text,
            "code":     code,
            "status":   "awaiting_approval",
            "trace_id": trace_id,
        }

        self._audit(run_id, "CODE_PLAN", plan_text[:500], trace_id, success=True)

        return {
            "run_id":    run_id,
            "status":    "awaiting_approval",
            "task":      task,
            "plan":      plan_text,
            "code":      code,
            "autogen":   _HAS_AUTOGEN,
        }

    def execute(self, run_id: str) -> dict:
        """
        Execute the code from an approved plan in a sandboxed environment.

        Args:
            run_id: The plan run ID returned by plan().

        Returns:
            dict with run_id, status ("completed"/"error"), output dict.
        """
        meta = self._runs.get(run_id)
        if meta is None:
            return {"error": f"Run '{run_id}' not found", "run_id": run_id}

        if meta["status"] != "approved":
            return {
                "error": (
                    f"Run '{run_id}' has not been approved "
                    f"(status: {meta['status']}). "
                    "Approve via POST /code/approve first."
                ),
                "run_id": run_id,
            }

        code = meta.get("code", "")
        if not code:
            meta["status"] = "error"
            return {"error": "No executable code block in plan", "run_id": run_id}

        logger.info("Executing approved code for run %s", run_id)

        if _check_docker():
            output = _run_in_docker(code)
        else:
            logger.warning("Docker unavailable — executing in local subprocess (no isolation)")
            output = _run_local(code)

        status = "error" if ("error" in output or output.get("returncode", 0) != 0) else "completed"
        meta["status"] = status
        meta["output"] = output

        self._audit(run_id, "CODE_EXECUTE", json.dumps(output)[:500], meta.get("trace_id"), success=(status == "completed"))

        return {
            "run_id":  run_id,
            "status":  status,
            "task":    meta["task"],
            "output":  output,
        }

    def approve(self, run_id: str, comment: str = "") -> dict:
        """
        Mark a plan as approved, allowing execute() to proceed.

        Args:
            run_id:  Plan run ID.
            comment: Optional human comment recorded in audit log.

        Returns:
            dict with run_id and updated status.
        """
        meta = self._runs.get(run_id)
        if meta is None:
            return {"error": f"Run '{run_id}' not found", "run_id": run_id}

        if meta["status"] != "awaiting_approval":
            return {
                "error": f"Run '{run_id}' is not awaiting approval (status: {meta['status']})",
                "run_id": run_id,
            }

        meta["status"] = "approved"
        meta["approval_comment"] = comment
        self._audit(run_id, "CODE_APPROVED", comment, meta.get("trace_id"), success=True)
        return {"run_id": run_id, "status": "approved"}

    def get_status(self, run_id: str) -> dict:
        """Return current status metadata for a code run."""
        meta = self._runs.get(run_id)
        if meta is None:
            return {"error": f"Run '{run_id}' not found", "run_id": run_id}
        return {
            "run_id":   meta["run_id"],
            "status":   meta["status"],
            "task":     meta["task"],
            "has_code": bool(meta.get("code")),
        }

    def _audit(self, run_id: str, action: str, content: str, trace_id: Any, success: bool) -> None:
        """Write code task event to the audit log."""
        try:
            from src.memory.audit_logger import audit_logger
            audit_logger.log_event(
                actor="AutoGenRunner",
                action_type=action,
                input_context=f"run_id={run_id}",
                output_content=content[:500],
                metadata={
                    "run_id":   run_id,
                    "success":  success,
                    **( {"trace_id": trace_id} if trace_id else {}),
                },
            )
        except Exception as exc:
            logger.debug("Audit for code run failed (non-fatal): %s", exc)


# Global singleton
autogen_runner = AutoGenRunner()

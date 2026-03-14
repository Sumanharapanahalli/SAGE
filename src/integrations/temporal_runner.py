"""
SAGE Framework — Temporal Durable Workflow Runner
===================================================
Optional integration with Temporal.io for long-running, fault-tolerant
workflows that must survive process restarts and can wait hours/days for
external events (CI completion, human approval, downstream API responses).

When to use Temporal vs LangGraph:
  LangGraph  — single-session workflows, interrupt → approve → resume
               within the same process. Best for analysis pipelines.
  Temporal   — multi-day workflows, external event waits, automatic
               retries on failure. Best for CI/CD, deployment, compliance.

Configuration:
  TEMPORAL_HOST     — Temporal server address (default: localhost:7233)
  TEMPORAL_NAMESPACE — Temporal namespace (default: "default")

Graceful degradation:
  If Temporal is not available (server not running or temporalio not installed),
  falls back to the LangGraph runner and logs a warning. SAGE continues normally.

Usage:
    from src.integrations.temporal_runner import temporal_runner
    run = temporal_runner.start("deploy_workflow", {"artifact": "v1.2.3"})
    # run["status"] == "started" | "fallback" | "error"
    status = temporal_runner.get_status(run["workflow_id"])
"""

import logging
import os
import uuid

logger = logging.getLogger("TemporalRunner")

_HAS_TEMPORAL = False
try:
    import temporalio  # noqa: F401
    _HAS_TEMPORAL = True
except ImportError:
    pass

_DEFAULT_HOST      = "localhost:7233"
_DEFAULT_NAMESPACE = "default"
_DEFAULT_TASK_QUEUE = "sage-task-queue"


class TemporalRunner:
    """
    Wraps the Temporal Python SDK client for starting and monitoring
    durable workflows. Falls back to LangGraphRunner when unavailable.
    """

    def __init__(self):
        self._client = None
        self._runs: dict[str, dict] = {}   # workflow_id -> metadata

    async def _get_client(self):
        """Lazily connect to the Temporal server."""
        if self._client is not None:
            return self._client
        if not _HAS_TEMPORAL:
            return None
        try:
            from temporalio.client import Client
            host      = os.environ.get("TEMPORAL_HOST", _DEFAULT_HOST)
            namespace = os.environ.get("TEMPORAL_NAMESPACE", _DEFAULT_NAMESPACE)
            self._client = await Client.connect(host, namespace=namespace)
            logger.info("Connected to Temporal at %s (namespace: %s)", host, namespace)
            return self._client
        except Exception as exc:
            logger.warning("Cannot connect to Temporal: %s", exc)
            return None

    def start(self, workflow_name: str, args: dict = None, workflow_id: str = None) -> dict:
        """
        Start a durable Temporal workflow (sync wrapper).

        Args:
            workflow_name: Workflow type name registered with the Temporal worker.
            args:          Input dict passed to the workflow.
            workflow_id:   Optional deterministic ID (generated if omitted).

        Returns:
            dict with workflow_id, status, fallback (bool).
            status = "started" | "fallback" | "error"
        """
        import asyncio

        workflow_id = workflow_id or f"sage-{workflow_name}-{str(uuid.uuid4())[:8]}"
        args = args or {}

        if not _HAS_TEMPORAL:
            return self._fallback(workflow_name, args, workflow_id, "temporalio not installed")

        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(
                self._async_start(workflow_name, args, workflow_id)
            )
            loop.close()
            return result
        except Exception as exc:
            logger.warning("Temporal start failed (%s) — using LangGraph fallback", exc)
            return self._fallback(workflow_name, args, workflow_id, str(exc))

    async def _async_start(self, workflow_name: str, args: dict, workflow_id: str) -> dict:
        client = await self._get_client()
        if client is None:
            return self._fallback(workflow_name, args, workflow_id, "Temporal server unreachable")

        task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", _DEFAULT_TASK_QUEUE)
        try:
            # Import workflow type dynamically (must be registered by the worker)
            # We use execute_workflow with the string-based workflow type name
            handle = await client.start_workflow(
                workflow_name,
                args,
                id=workflow_id,
                task_queue=task_queue,
            )
            self._runs[workflow_id] = {
                "workflow_id":   workflow_id,
                "workflow_name": workflow_name,
                "status":        "started",
                "fallback":      False,
                "handle":        handle,
            }
            self._audit(workflow_id, workflow_name, "started")
            return {
                "workflow_id":   workflow_id,
                "workflow_name": workflow_name,
                "status":        "started",
                "fallback":      False,
            }
        except Exception as exc:
            logger.error("Temporal workflow start error: %s", exc)
            return self._fallback(workflow_name, args, workflow_id, str(exc))

    def _fallback(self, workflow_name: str, args: dict, workflow_id: str, reason: str) -> dict:
        """Fall back to LangGraph runner for the same workflow."""
        logger.info("Temporal fallback for '%s': %s", workflow_name, reason)
        try:
            from src.integrations.langgraph_runner import langgraph_runner
            lg_result = langgraph_runner.run(workflow_name, args)
            self._runs[workflow_id] = {
                "workflow_id":   workflow_id,
                "workflow_name": workflow_name,
                "status":        lg_result.get("status", "completed"),
                "fallback":      True,
                "langgraph_run": lg_result,
            }
            return {
                "workflow_id":   workflow_id,
                "workflow_name": workflow_name,
                "status":        lg_result.get("status", "completed"),
                "fallback":      True,
                "reason":        reason,
            }
        except Exception as lg_exc:
            self._runs[workflow_id] = {
                "workflow_id": workflow_id,
                "workflow_name": workflow_name,
                "status": "error",
                "fallback": True,
            }
            return {
                "workflow_id":   workflow_id,
                "workflow_name": workflow_name,
                "status":        "error",
                "fallback":      True,
                "reason":        reason,
                "fallback_error": str(lg_exc),
            }

    def get_status(self, workflow_id: str) -> dict:
        """
        Get the current status of a workflow run.

        For Temporal workflows, polls the server for the execution status.
        For fallback runs, returns the stored status.
        """
        import asyncio

        meta = self._runs.get(workflow_id)
        if meta is None:
            return {"error": f"Workflow '{workflow_id}' not found", "workflow_id": workflow_id}

        if meta.get("fallback") or not _HAS_TEMPORAL:
            return {
                "workflow_id":   meta["workflow_id"],
                "workflow_name": meta["workflow_name"],
                "status":        meta["status"],
                "fallback":      True,
            }

        # Poll Temporal for live status
        try:
            handle = meta.get("handle")
            if handle is None:
                return {
                    "workflow_id": workflow_id,
                    "status": meta["status"],
                    "fallback": False,
                }
            loop = asyncio.new_event_loop()
            desc = loop.run_until_complete(handle.describe())
            loop.close()
            status = str(desc.status).lower().replace("workflowexecutionstatus.", "")
            meta["status"] = status
            return {
                "workflow_id":   workflow_id,
                "workflow_name": meta["workflow_name"],
                "status":        status,
                "fallback":      False,
            }
        except Exception as exc:
            logger.warning("Temporal describe failed: %s", exc)
            return {
                "workflow_id": workflow_id,
                "status":      meta.get("status", "unknown"),
                "fallback":    False,
                "error":       str(exc),
            }

    def list_runs(self) -> list[dict]:
        """Return metadata for all workflow runs in this process session."""
        return [
            {
                "workflow_id":   v["workflow_id"],
                "workflow_name": v["workflow_name"],
                "status":        v["status"],
                "fallback":      v.get("fallback", False),
            }
            for v in self._runs.values()
        ]

    def _audit(self, workflow_id: str, workflow_name: str, status: str) -> None:
        """Write workflow event to the audit log."""
        try:
            from src.memory.audit_logger import audit_logger
            audit_logger.log_event(
                actor="TemporalRunner",
                action_type="TEMPORAL_WORKFLOW",
                input_context=f"workflow={workflow_name} id={workflow_id}",
                output_content=status,
                metadata={"workflow_id": workflow_id, "status": status},
            )
        except Exception as exc:
            logger.debug("Audit for temporal workflow failed (non-fatal): %s", exc)


# Global singleton
temporal_runner = TemporalRunner()

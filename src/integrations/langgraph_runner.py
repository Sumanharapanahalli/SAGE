"""
SAGE Framework — LangGraph Orchestration Runner
================================================
Optional orchestration engine activated by setting:
  orchestration.engine: "langgraph"   in config/config.yaml

Architecture:
  solutions/<name>/workflows/*.py   ← each file defines a StateGraph and
                                       exposes a compiled `workflow` attribute

  LangGraphRunner.run(name, state)  → {run_id, status, ...}
  LangGraphRunner.resume(run_id, …) → {run_id, status, ...}
  LangGraphRunner.get_status(id)    → {run_id, status, state, ...}

Approval gate:
  Workflows compiled with interrupt_before=["<node>"] pause at that node.
  The runner surfaces status="awaiting_approval" and stores the thread state.
  Human calls POST /workflow/resume with {run_id, feedback} to continue.

Graceful degradation:
  If langgraph is not installed, every method returns an error dict instead
  of raising — SAGE still runs normally with the default queue engine.

SQLite checkpointing:
  Uses langgraph-checkpoint-sqlite when available; falls back to in-memory
  MemorySaver so state is preserved for the process lifetime.
"""

import importlib.util
import logging
import os
import sys
import uuid
from typing import Any

logger = logging.getLogger("LangGraphRunner")

_HAS_LANGGRAPH = False
try:
    import langgraph  # noqa: F401
    _HAS_LANGGRAPH = True
except ImportError:
    pass


def _get_checkpointer():
    """
    Return the best available LangGraph checkpointer.
    Prefers SqliteSaver (persistent) → MemorySaver (in-process).
    """
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "langgraph_checkpoints.db",
    )
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Try langgraph-checkpoint-sqlite first
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        return SqliteSaver.from_conn_string(db_path)
    except (ImportError, AttributeError):
        pass
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver  # noqa
    except ImportError:
        pass

    # Fallback: in-memory checkpointer
    try:
        from langgraph.checkpoint.memory import MemorySaver
        logger.debug(
            "langgraph-checkpoint-sqlite not available — using MemorySaver "
            "(run state is in-process only)"
        )
        return MemorySaver()
    except ImportError:
        return None


class LangGraphRunner:
    """
    Discovers, loads, and runs LangGraph StateGraph workflows for the active
    solution. Each run gets a unique thread_id for checkpointer isolation.

    Usage (from TaskWorker or API):
        from src.integrations.langgraph_runner import langgraph_runner
        result = langgraph_runner.run("analysis_workflow", {"task": "..."})
        # If result["status"] == "awaiting_approval":
        result = langgraph_runner.resume(result["run_id"], {"approved": True})
    """

    def __init__(self):
        self._workflows: dict[str, Any] = {}   # name -> compiled graph
        self._loaded_solution: str = ""
        self._checkpointer = None
        self._runs: dict[str, dict] = {}       # run_id -> run metadata

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _get_workflows_dir(self) -> str:
        """Resolve path to active solution's workflows/ directory."""
        try:
            from src.core.project_loader import project_config, _SOLUTIONS_DIR
            return os.path.join(_SOLUTIONS_DIR, project_config.project_name, "workflows")
        except Exception:
            return ""

    def load(self, force: bool = False) -> int:
        """
        Discover and register workflow modules for the active solution.

        Args:
            force: Re-load even if already loaded for this solution.

        Returns:
            Number of workflows registered.
        """
        if not _HAS_LANGGRAPH:
            return 0

        try:
            from src.core.project_loader import project_config
            solution = project_config.project_name
        except Exception:
            solution = ""

        if not force and solution == self._loaded_solution and self._workflows:
            return len(self._workflows)

        self._workflows.clear()
        self._loaded_solution = solution

        if self._checkpointer is None:
            self._checkpointer = _get_checkpointer()

        workflows_dir = self._get_workflows_dir()
        if not workflows_dir or not os.path.isdir(workflows_dir):
            logger.debug("No workflows/ directory at: %s", workflows_dir)
            return 0

        # Add solution dir to sys.path
        solution_dir = os.path.dirname(workflows_dir)
        if solution_dir not in sys.path:
            sys.path.insert(0, solution_dir)

        for filename in sorted(os.listdir(workflows_dir)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            self._load_workflow(workflows_dir, filename)

        logger.info(
            "LangGraphRunner loaded %d workflow(s) [solution: %s]",
            len(self._workflows), solution,
        )
        return len(self._workflows)

    def _load_workflow(self, workflows_dir: str, filename: str) -> None:
        """Import a workflow module and register its compiled graph."""
        name = filename[:-3]
        path = os.path.join(workflows_dir, filename)
        try:
            spec = importlib.util.spec_from_file_location(
                f"workflows.{name}", path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Convention: module must expose `workflow` (compiled StateGraph)
            graph = getattr(module, "workflow", None)
            if graph is None:
                logger.debug("No 'workflow' attribute in %s — skipping", filename)
                return

            self._workflows[name] = graph
            logger.debug("Loaded workflow: %s", name)
        except Exception as exc:
            logger.warning("Could not load workflow %s: %s", filename, exc)

    # ------------------------------------------------------------------
    # Run interface
    # ------------------------------------------------------------------

    def list_workflows(self) -> list[dict]:
        """Return metadata for all registered workflows."""
        self.load()
        return [{"name": name} for name in sorted(self._workflows)]

    def run(
        self,
        workflow_name: str,
        initial_state: dict,
        run_id: str = None,
    ) -> dict:
        """
        Start a workflow run.

        Args:
            workflow_name: Name of the workflow (filename without .py).
            initial_state: Initial state dict passed to the graph.
            run_id:        Optional caller-supplied ID; generated if omitted.

        Returns:
            dict with keys: run_id, status, workflow_name, result (or error).
            status values: "completed" | "awaiting_approval" | "error"
        """
        if not _HAS_LANGGRAPH:
            return {"error": "langgraph not installed", "run_id": run_id or str(uuid.uuid4())}

        self.load()

        graph = self._workflows.get(workflow_name)
        if graph is None:
            available = list(self._workflows)
            return {
                "error": f"Workflow '{workflow_name}' not found. Available: {available}",
                "run_id": run_id or str(uuid.uuid4()),
            }

        run_id = run_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": run_id}}
        if self._checkpointer is not None:
            config["configurable"]["checkpointer"] = self._checkpointer

        self._runs[run_id] = {
            "run_id": run_id,
            "workflow_name": workflow_name,
            "status": "running",
            "config": config,
        }

        try:
            result = graph.invoke(initial_state, config=config)
            # Check if the graph interrupted (paused for human approval)
            interrupted = self._is_interrupted(graph, config)
            status = "awaiting_approval" if interrupted else "completed"
            self._runs[run_id]["status"] = status
            self._runs[run_id]["last_result"] = result
            self._audit(run_id, workflow_name, status, result)
            return {
                "run_id": run_id,
                "status": status,
                "workflow_name": workflow_name,
                "result": result,
            }
        except Exception as exc:
            logger.error("Workflow '%s' run %s failed: %s", workflow_name, run_id, exc)
            self._runs[run_id]["status"] = "error"
            return {
                "error": str(exc),
                "run_id": run_id,
                "workflow_name": workflow_name,
            }

    def resume(self, run_id: str, feedback: dict = None) -> dict:
        """
        Resume a workflow paused at an approval gate.

        Args:
            run_id:   The run to resume.
            feedback: Dict merged into the graph state before resuming.
                      Typically includes {"approved": True/False, "comment": "..."}.

        Returns:
            Same shape as run() return value.
        """
        if not _HAS_LANGGRAPH:
            return {"error": "langgraph not installed", "run_id": run_id}

        meta = self._runs.get(run_id)
        if meta is None:
            return {"error": f"Run '{run_id}' not found", "run_id": run_id}

        if meta["status"] != "awaiting_approval":
            return {
                "error": f"Run '{run_id}' is not awaiting approval (status: {meta['status']})",
                "run_id": run_id,
            }

        graph = self._workflows.get(meta["workflow_name"])
        if graph is None:
            return {"error": "Workflow no longer loaded", "run_id": run_id}

        config = meta["config"]
        feedback = feedback or {}

        try:
            # Pass feedback into the graph state update, then resume
            result = graph.invoke(feedback, config=config)
            interrupted = self._is_interrupted(graph, config)
            status = "awaiting_approval" if interrupted else "completed"
            meta["status"] = status
            meta["last_result"] = result
            self._audit(run_id, meta["workflow_name"], status, result)
            return {
                "run_id": run_id,
                "status": status,
                "workflow_name": meta["workflow_name"],
                "result": result,
            }
        except Exception as exc:
            logger.error("Workflow resume %s failed: %s", run_id, exc)
            meta["status"] = "error"
            return {"error": str(exc), "run_id": run_id}

    def get_status(self, run_id: str) -> dict:
        """Return current status of a workflow run."""
        meta = self._runs.get(run_id)
        if meta is None:
            return {"error": f"Run '{run_id}' not found", "run_id": run_id}
        return {
            "run_id": meta["run_id"],
            "workflow_name": meta["workflow_name"],
            "status": meta["status"],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_interrupted(graph, config: dict) -> bool:
        """
        Check whether the graph paused at an interrupt_before/after node.
        Inspects the checkpointer state to detect pending interrupts.
        """
        try:
            state = graph.get_state(config)
            # LangGraph sets next=() when graph finished; non-empty next = interrupted
            if hasattr(state, "next") and state.next:
                return True
        except Exception:
            pass
        return False

    def _audit(self, run_id: str, workflow_name: str, status: str, result) -> None:
        """Write workflow run event to the audit log."""
        try:
            import json
            from src.memory.audit_logger import audit_logger
            audit_logger.log_event(
                actor="LangGraphRunner",
                action_type="WORKFLOW_RUN",
                input_context=f"workflow={workflow_name} run_id={run_id}",
                output_content=str(result)[:500],
                metadata={"workflow": workflow_name, "run_id": run_id, "status": status},
            )
        except Exception as exc:
            logger.debug("Audit for workflow run failed (non-fatal): %s", exc)


# Global singleton
langgraph_runner = LangGraphRunner()

"""
SAGE Dynamic Agent Spawner — Recursive Agent Composition
=========================================================

Agents can spawn sub-agents during execution for recursive task
decomposition. The orchestrator agent decides at runtime which
specialist to invoke, enabling dynamic team composition.

Pattern: AutoGen/CrewAI agent-as-tool, DeerFlow supervisor topology
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class SpawnedAgent:
    """Record of a dynamically spawned sub-agent."""
    spawn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_task_id: str = ""
    role: str = ""
    task: str = ""
    context: str = ""
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    error: str = ""
    spawned_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str = ""
    depth: int = 0  # recursion depth

    def to_dict(self) -> dict:
        return {
            "spawn_id": self.spawn_id,
            "parent_task_id": self.parent_task_id,
            "role": self.role,
            "task": self.task[:200],
            "status": self.status,
            "error": self.error,
            "spawned_at": self.spawned_at,
            "completed_at": self.completed_at,
            "depth": self.depth,
        }


class AgentSpawner:
    """
    Dynamic agent spawning with depth control and budget checks.

    Usage:
        spawner = AgentSpawner(agent_fn=universal_agent.run)
        result = spawner.spawn(
            parent_task_id="task-123",
            role="security_auditor",
            task="Review authentication flow for vulnerabilities",
            depth=1,
        )
    """

    def __init__(
        self,
        agent_fn: Callable = None,
        max_depth: int = 3,
        max_concurrent: int = 5,
    ):
        self._agent_fn = agent_fn
        self._max_depth = max_depth
        self._max_concurrent = max_concurrent
        self._spawns: dict[str, SpawnedAgent] = {}
        self._active_count = 0
        self._lock = threading.Lock()

    def set_agent_fn(self, fn: Callable) -> None:
        """Set the agent execution function (lazy binding)."""
        self._agent_fn = fn

    def spawn(
        self,
        role: str,
        task: str,
        context: str = "",
        parent_task_id: str = "",
        depth: int = 0,
    ) -> dict:
        """
        Spawn a sub-agent to handle a task.

        Args:
            role: Agent role (from prompts.yaml)
            task: Task description
            context: Additional context
            parent_task_id: Parent task for tracing
            depth: Current recursion depth

        Returns:
            {spawn_id, status, result, error}
        """
        # Depth check
        if depth >= self._max_depth:
            return {
                "spawn_id": "",
                "status": "rejected",
                "error": f"Max spawn depth ({self._max_depth}) reached",
            }

        # Concurrency check
        with self._lock:
            if self._active_count >= self._max_concurrent:
                return {
                    "spawn_id": "",
                    "status": "rejected",
                    "error": f"Max concurrent spawns ({self._max_concurrent}) reached",
                }
            self._active_count += 1

        # Budget check
        budget_ok = self._check_budget(parent_task_id)
        if not budget_ok:
            with self._lock:
                self._active_count -= 1
            return {
                "spawn_id": "",
                "status": "rejected",
                "error": "Budget exceeded for parent task",
            }

        record = SpawnedAgent(
            parent_task_id=parent_task_id,
            role=role,
            task=task,
            context=context,
            status="running",
            depth=depth,
        )

        with self._lock:
            self._spawns[record.spawn_id] = record

        self._emit("agent.spawned", {
            "spawn_id": record.spawn_id,
            "parent_task_id": parent_task_id,
            "role": role,
            "depth": depth,
        })

        # Execute
        try:
            if self._agent_fn:
                result = self._agent_fn(
                    role_id=role,
                    task=task,
                    context=context,
                )
            else:
                result = self._default_executor(role, task, context)

            record.status = "completed"
            record.result = result
            record.completed_at = datetime.now(timezone.utc).isoformat()

            self._emit("agent.completed", {
                "spawn_id": record.spawn_id,
                "role": role,
                "status": "completed",
                "depth": depth,
            })

        except Exception as exc:
            record.status = "failed"
            record.error = str(exc)
            record.completed_at = datetime.now(timezone.utc).isoformat()
            logger.warning("Spawned agent %s failed: %s", role, exc)

        finally:
            with self._lock:
                self._active_count -= 1

        return {
            "spawn_id": record.spawn_id,
            "status": record.status,
            "result": record.result,
            "error": record.error,
        }

    def get_spawn(self, spawn_id: str) -> Optional[dict]:
        """Get a spawn record."""
        with self._lock:
            s = self._spawns.get(spawn_id)
        return s.to_dict() if s else None

    def list_spawns(self, parent_task_id: str = None, limit: int = 50) -> list[dict]:
        """List spawned agents, optionally filtered by parent."""
        with self._lock:
            spawns = list(self._spawns.values())
        if parent_task_id:
            spawns = [s for s in spawns if s.parent_task_id == parent_task_id]
        spawns.sort(key=lambda s: s.spawned_at, reverse=True)
        return [s.to_dict() for s in spawns[:limit]]

    def get_stats(self) -> dict:
        """Return spawner statistics."""
        with self._lock:
            total = len(self._spawns)
            completed = sum(1 for s in self._spawns.values() if s.status == "completed")
            failed = sum(1 for s in self._spawns.values() if s.status == "failed")
            max_depth_seen = max(
                (s.depth for s in self._spawns.values()), default=0
            )
        return {
            "total_spawns": total,
            "active": self._active_count,
            "completed": completed,
            "failed": failed,
            "max_depth_seen": max_depth_seen,
            "max_depth_limit": self._max_depth,
            "max_concurrent": self._max_concurrent,
        }

    @staticmethod
    def _default_executor(role: str, task: str, context: str) -> dict:
        """Default no-op executor for testing."""
        return {
            "summary": f"Simulated execution by {role}",
            "analysis": f"Task: {task}",
            "status": "completed",
        }

    @staticmethod
    def _check_budget(task_id: str) -> bool:
        """Check if budget allows spawning."""
        try:
            from src.core.budget_manager import get_budget_manager
            bm = get_budget_manager()
            check = bm.check_budget(f"task:{task_id}")
            return check["allowed"]
        except Exception:
            return True  # allow if budget manager unavailable

    @staticmethod
    def _emit(event_type: str, data: dict) -> None:
        try:
            from src.core.event_bus import get_event_bus
            get_event_bus().publish(event_type, data, source="agent_spawner")
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────────

_spawner: Optional[AgentSpawner] = None
_sp_lock = threading.Lock()


def get_agent_spawner() -> AgentSpawner:
    global _spawner
    if _spawner is None:
        with _sp_lock:
            if _spawner is None:
                _spawner = AgentSpawner()
    return _spawner

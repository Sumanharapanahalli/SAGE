"""
SAGE Backtrack Planner — HTN-Style Re-Planning
================================================

When a subtree of tasks fails repeatedly, instead of just blocking
downstream tasks, propagates back up to re-plan that branch.
Implements hierarchical task network (HTN) decomposition with
backtracking on failure.

Pattern: HTN Planning with re-planning, Aider-style reversible commits
"""

import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class BacktrackRecord:
    """Record of a backtrack event."""
    backtrack_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    failed_task_id: str = ""
    failed_task_type: str = ""
    failure_count: int = 0
    replan_scope: str = ""  # subtree | branch | full
    original_plan: list = field(default_factory=list)
    new_plan: list = field(default_factory=list)
    status: str = "pending"  # pending, replanning, replanned, failed
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "backtrack_id": self.backtrack_id,
            "failed_task_id": self.failed_task_id,
            "failed_task_type": self.failed_task_type,
            "failure_count": self.failure_count,
            "replan_scope": self.replan_scope,
            "original_plan_size": len(self.original_plan),
            "new_plan_size": len(self.new_plan),
            "status": self.status,
            "created_at": self.created_at,
        }


class BacktrackPlanner:
    """
    Hierarchical re-planning with failure-driven backtracking.

    When a task fails beyond retry limit:
    1. Identify the subtree affected
    2. Collect failure context (error messages, attempts)
    3. Re-plan the failed branch with failure context
    4. Replace failed subtree with new plan

    Usage:
        planner = BacktrackPlanner(replan_fn=my_replanner)
        new_tasks = planner.handle_failure(
            failed_task_id="task-123",
            error="Compilation failed: missing header",
            task_graph={...},
        )
    """

    def __init__(
        self,
        replan_fn: Callable = None,
        max_backtracks: int = 3,
        failure_threshold: int = 2,
    ):
        self._replan_fn = replan_fn
        self._max_backtracks = max_backtracks
        self._failure_threshold = failure_threshold
        self._failure_counts: dict[str, int] = defaultdict(int)
        self._records: dict[str, BacktrackRecord] = {}
        self._lock = threading.Lock()

    def set_replan_fn(self, fn: Callable) -> None:
        """Set the replanning function (lazy binding)."""
        self._replan_fn = fn

    def record_failure(self, task_id: str, task_type: str = "") -> int:
        """
        Record a task failure. Returns current failure count.
        """
        with self._lock:
            self._failure_counts[task_id] += 1
            return self._failure_counts[task_id]

    def should_backtrack(self, task_id: str) -> bool:
        """Check if failure count exceeds threshold."""
        with self._lock:
            count = self._failure_counts.get(task_id, 0)
            total_backtracks = sum(
                1 for r in self._records.values()
                if r.status in ("replanned", "replanning")
            )
        return (count >= self._failure_threshold and
                total_backtracks < self._max_backtracks)

    def handle_failure(
        self,
        failed_task_id: str,
        error: str,
        task_graph: dict,
        context: str = "",
    ) -> Optional[dict]:
        """
        Handle a repeated task failure by re-planning.

        Args:
            failed_task_id: ID of the failed task
            error: Error message
            task_graph: Current task graph {tasks: [...], dependencies: [...]}
            context: Additional context for replanning

        Returns:
            {backtrack_id, new_tasks: [...]} or None if no backtrack needed
        """
        task_type = ""
        for t in task_graph.get("tasks", []):
            if t.get("task_id") == failed_task_id:
                task_type = t.get("task_type", "")
                break

        count = self.record_failure(failed_task_id, task_type)

        if not self.should_backtrack(failed_task_id):
            return None

        # Identify affected subtree
        affected = self._identify_affected_subtree(
            failed_task_id, task_graph,
        )
        scope = "subtree" if len(affected) > 1 else "branch"

        record = BacktrackRecord(
            failed_task_id=failed_task_id,
            failed_task_type=task_type,
            failure_count=count,
            replan_scope=scope,
            original_plan=affected,
            status="replanning",
        )

        with self._lock:
            self._records[record.backtrack_id] = record

        self._emit("backtrack.started", {
            "backtrack_id": record.backtrack_id,
            "failed_task_id": failed_task_id,
            "scope": scope,
            "affected_count": len(affected),
        })

        # Re-plan
        try:
            new_tasks = self._replan(
                failed_task_id=failed_task_id,
                error=error,
                affected_tasks=affected,
                context=context,
            )
            record.new_plan = new_tasks
            record.status = "replanned"

            self._emit("backtrack.replanned", {
                "backtrack_id": record.backtrack_id,
                "new_task_count": len(new_tasks),
            })

            return {
                "backtrack_id": record.backtrack_id,
                "new_tasks": new_tasks,
                "replaced_tasks": [t.get("task_id", "") for t in affected],
            }

        except Exception as exc:
            record.status = "failed"
            logger.warning("Backtrack replanning failed: %s", exc)
            return None

    def _identify_affected_subtree(
        self, failed_id: str, task_graph: dict,
    ) -> list[dict]:
        """Find all tasks downstream of the failed task."""
        tasks = task_graph.get("tasks", [])
        deps = task_graph.get("dependencies", [])

        # Build adjacency (task_id → downstream task_ids)
        downstream: dict[str, list[str]] = defaultdict(list)
        for d in deps:
            downstream[d.get("from", "")].append(d.get("to", ""))

        # BFS from failed task
        affected_ids = {failed_id}
        queue = [failed_id]
        while queue:
            current = queue.pop(0)
            for child in downstream.get(current, []):
                if child not in affected_ids:
                    affected_ids.add(child)
                    queue.append(child)

        # Return affected task dicts
        return [t for t in tasks if t.get("task_id") in affected_ids]

    def _replan(
        self,
        failed_task_id: str,
        error: str,
        affected_tasks: list[dict],
        context: str,
    ) -> list[dict]:
        """Generate replacement tasks for the failed subtree."""
        if self._replan_fn:
            return self._replan_fn(
                failed_task_id=failed_task_id,
                error=error,
                affected_tasks=affected_tasks,
                context=context,
            )

        # Default: return same tasks with modified payload
        return [
            {
                **t,
                "task_id": f"replan-{uuid.uuid4().hex[:8]}",
                "payload": {
                    **t.get("payload", {}),
                    "_replan_context": f"Previous attempt failed: {error}",
                    "_original_task_id": t.get("task_id", ""),
                },
            }
            for t in affected_tasks
        ]

    def get_record(self, backtrack_id: str) -> Optional[dict]:
        with self._lock:
            r = self._records.get(backtrack_id)
        return r.to_dict() if r else None

    def list_records(self, limit: int = 20) -> list[dict]:
        with self._lock:
            items = sorted(
                self._records.values(),
                key=lambda r: r.created_at,
                reverse=True,
            )[:limit]
        return [r.to_dict() for r in items]

    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._records)
            replanned = sum(
                1 for r in self._records.values() if r.status == "replanned"
            )
            failed = sum(
                1 for r in self._records.values() if r.status == "failed"
            )
        return {
            "total_backtracks": total,
            "successful_replans": replanned,
            "failed_replans": failed,
            "max_backtracks": self._max_backtracks,
            "failure_threshold": self._failure_threshold,
            "tracked_failures": len(self._failure_counts),
        }

    @staticmethod
    def _emit(event_type: str, data: dict) -> None:
        try:
            from src.core.event_bus import get_event_bus
            get_event_bus().publish(event_type, data, source="backtrack_planner")
        except Exception:
            pass


# Singleton
_backtrack_planner: Optional[BacktrackPlanner] = None
_bp_lock = threading.Lock()


def get_backtrack_planner() -> BacktrackPlanner:
    global _backtrack_planner
    if _backtrack_planner is None:
        with _bp_lock:
            if _backtrack_planner is None:
                _backtrack_planner = BacktrackPlanner()
    return _backtrack_planner

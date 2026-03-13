"""
SAGE[ai] - Queue Manager
=========================
Thread-safe FIFO task queue with SQLite persistence. Ensures single-lane
execution for compliance and survives process restarts.

Task types:
  ANALYZE_LOG    - Run analyst agent on a log entry
  CREATE_MR      - Create a merge request from an issue
  REVIEW_MR      - Review a merge request
  FLASH_FIRMWARE - Flash firmware via J-Link
  MONITOR_CHECK  - On-demand monitor poll

ISO 13485 Note: Single-lane serialized execution ensures a deterministic,
auditable sequence of AI actions. No parallel AI decisions.

Persistence Note: Tasks are written to SQLite on submit and updated on
completion/failure. Pending tasks are restored on process restart.
"""

import json
import logging
import os
import queue
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# Path to the shared audit/task SQLite database
_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "audit_log.db",
)


class TaskStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task:
    """Represents a single unit of work in the task queue."""

    def __init__(self, task_type: str, payload: dict, priority: int = 5):
        self.task_id = str(uuid.uuid4())
        self.task_type = task_type
        self.payload = payload
        self.priority = priority  # Lower number = higher priority (1=highest, 10=lowest)
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.result: Any = None
        self.error: Optional[str] = None

    def __lt__(self, other: "Task") -> bool:
        """Priority queue comparison: lower priority number = higher priority."""
        return self.priority < other.priority

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "payload_keys": list(self.payload.keys()),
        }


class TaskQueue:
    """
    Thread-safe FIFO priority task queue backed by SQLite for persistence.

    On startup, any tasks left in 'pending' or 'in_progress' state (from a
    previous run) are automatically restored to the in-memory queue.

    Usage:
        from src.core.queue_manager import task_queue
        task_id = task_queue.submit("ANALYZE_LOG", {"log_entry": "Error: ..."})
    """

    def __init__(self, db_path: str = _DB_PATH):
        self._queue: queue.PriorityQueue = queue.PriorityQueue()
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger("TaskQueue")
        self._db_path = db_path
        self._init_db()
        self._restore_pending_tasks()

    # -----------------------------------------------------------------------
    # SQLite helpers
    # -----------------------------------------------------------------------

    def _init_db(self):
        """Create the task_queue table if it does not exist."""
        try:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            conn = sqlite3.connect(self._db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_queue (
                    task_id      TEXT PRIMARY KEY,
                    task_type    TEXT NOT NULL,
                    payload      TEXT NOT NULL,
                    priority     INTEGER DEFAULT 5,
                    status       TEXT DEFAULT 'pending',
                    created_at   TEXT,
                    started_at   TEXT,
                    completed_at TEXT,
                    result       TEXT,
                    error        TEXT
                )
            """)
            conn.commit()
            conn.close()
            self.logger.info("Task queue SQLite storage initialised at %s", self._db_path)
        except Exception as exc:
            self.logger.error("Failed to initialise task queue DB: %s", exc)

    def _restore_pending_tasks(self):
        """Load pending/in-progress tasks from a previous run on startup."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM task_queue "
                "WHERE status IN ('pending', 'in_progress') "
                "ORDER BY priority ASC, created_at ASC"
            )
            rows = cursor.fetchall()
            conn.close()

            restored = 0
            for row in rows:
                task = Task.__new__(Task)
                task.task_id = row["task_id"]
                task.task_type = row["task_type"]
                task.payload = json.loads(row["payload"])
                task.priority = row["priority"]
                # Reset in_progress → pending; the worker that held the task is gone
                task.status = TaskStatus.PENDING
                task.created_at = row["created_at"]
                task.started_at = None
                task.completed_at = None
                task.result = None
                task.error = None

                with self._lock:
                    self._tasks[task.task_id] = task
                self._queue.put((task.priority, task.created_at, task))
                restored += 1

            if restored:
                self.logger.info(
                    "Restored %d pending task(s) from SQLite on startup.", restored
                )
        except Exception as exc:
            self.logger.error("Failed to restore pending tasks: %s", exc)

    def _db_insert(self, task: Task):
        """Persist a newly submitted task to SQLite."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO task_queue "
                "(task_id, task_type, payload, priority, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    task.task_id,
                    task.task_type,
                    json.dumps(task.payload),
                    task.priority,
                    task.status,
                    task.created_at,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self.logger.error("DB insert failed for task %s: %s", task.task_id, exc)

    def _db_update(self, task: Task):
        """Update status, timestamps and result/error for an existing task."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "UPDATE task_queue "
                "SET status=?, started_at=?, completed_at=?, result=?, error=? "
                "WHERE task_id=?",
                (
                    task.status,
                    task.started_at,
                    task.completed_at,
                    json.dumps(task.result) if task.result is not None else None,
                    task.error,
                    task.task_id,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            self.logger.error("DB update failed for task %s: %s", task.task_id, exc)

    # -----------------------------------------------------------------------
    # Public Queue Operations
    # -----------------------------------------------------------------------

    def submit(self, task_type: str, payload: dict, priority: int = 5) -> str:
        """
        Adds a new task to the queue and persists it to SQLite.

        Args:
            task_type: Task category (e.g. 'ANALYZE_LOG', 'CREATE_MR')
            payload:   Task-specific data dict
            priority:  Integer priority 1-10 (1=highest, default=5)

        Returns:
            task_id string for tracking.
        """
        task = Task(task_type, payload, priority)
        with self._lock:
            self._tasks[task.task_id] = task
        self._db_insert(task)
        self._queue.put((priority, task.created_at, task))
        self.logger.info(
            "Task submitted: %s [%s] priority=%d (id: %s)",
            task_type, TaskStatus.PENDING, priority, task.task_id,
        )
        return task.task_id

    def get_next(self, timeout: float = 1.0) -> Optional[Task]:
        """
        Blocking get of the next highest-priority task.

        Args:
            timeout: Max seconds to wait (default 1.0)

        Returns:
            Task object or None if queue is empty after timeout.
        """
        try:
            _, _, task = self._queue.get(timeout=timeout)
            with self._lock:
                task.status = TaskStatus.IN_PROGRESS
                task.started_at = datetime.now(timezone.utc).isoformat()
                self._db_update(task)
            self.logger.debug("Dequeued task: %s (id: %s)", task.task_type, task.task_id)
            return task
        except queue.Empty:
            return None

    def mark_done(self, task_id: str, result: Any = None):
        """
        Marks a task as completed with an optional result.

        Args:
            task_id: The task's ID
            result:  Optional result data
        """
        with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now(timezone.utc).isoformat()
                task.result = result
                self._db_update(task)
                self.logger.info("Task completed: %s (id: %s)", task.task_type, task_id)
            else:
                self.logger.warning("mark_done called for unknown task_id: %s", task_id)
        self._queue.task_done()

    def mark_failed(self, task_id: str, error: str):
        """Marks a task as failed and persists the error message."""
        with self._lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now(timezone.utc).isoformat()
                task.error = error
                self._db_update(task)
                self.logger.error(
                    "Task FAILED: %s (id: %s) — %s", task.task_type, task_id, error
                )
        try:
            self._queue.task_done()
        except ValueError:
            pass

    def get_status(self, task_id: str) -> Optional[dict]:
        """
        Returns the current status of a task.

        Args:
            task_id: Task ID to look up

        Returns:
            Task status dict or None if not found.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            return task.to_dict() if task else None

    def get_pending_count(self) -> int:
        """Returns the number of tasks currently in the queue (not started)."""
        return self._queue.qsize()

    def get_all_tasks(self) -> list:
        """Returns status of all tracked tasks (for dashboard)."""
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]


class TaskWorker(threading.Thread):
    """
    Background worker thread that processes tasks from the TaskQueue.
    Dispatches to the appropriate agent based on task_type.
    Single-lane: processes one task at a time (by design).
    """

    def __init__(self, task_queue: TaskQueue, name: str = "TaskWorker"):
        super().__init__(name=name, daemon=True)
        self._queue = task_queue
        self._running = False
        self.logger = logging.getLogger("TaskWorker")

    def run(self):
        """Main task processing loop."""
        self._running = True
        self.logger.info("TaskWorker started (single-lane compliance mode).")

        while self._running:
            task = self._queue.get_next(timeout=1.0)
            if task is None:
                continue  # Queue empty, keep polling

            self.logger.info("Processing task: %s (id: %s)", task.task_type, task.task_id)
            try:
                result = self._dispatch(task)
                self._queue.mark_done(task.task_id, result)
            except Exception as e:
                self.logger.error("Task %s failed with exception: %s", task.task_id, e)
                self._queue.mark_failed(task.task_id, str(e))

        self.logger.info("TaskWorker stopped.")

    def stop(self):
        """Signals the worker to stop after completing the current task."""
        self._running = False

    def _dispatch(self, task: Task) -> Any:
        """
        Routes a task to the appropriate agent method.

        Args:
            task: The Task to dispatch

        Returns:
            Result from the agent (dict, str, etc.)
        """
        task_type = task.task_type.upper()
        payload = task.payload

        if task_type == "ANALYZE_LOG":
            from src.agents.analyst import analyst_agent
            log_entry = payload.get("log_entry", "")
            if not log_entry:
                raise ValueError("ANALYZE_LOG task missing 'log_entry' in payload.")
            return analyst_agent.analyze_log(log_entry)

        elif task_type == "CREATE_MR":
            from src.agents.developer import developer_agent
            project_id = payload.get("project_id")
            issue_iid = payload.get("issue_iid")
            if not project_id or not issue_iid:
                raise ValueError("CREATE_MR task missing 'project_id' or 'issue_iid'.")
            return developer_agent.create_mr_from_issue(
                project_id=int(project_id),
                issue_iid=int(issue_iid),
                source_branch=payload.get("source_branch"),
            )

        elif task_type == "REVIEW_MR":
            from src.agents.developer import developer_agent
            project_id = payload.get("project_id")
            mr_iid = payload.get("mr_iid")
            if not project_id or not mr_iid:
                raise ValueError("REVIEW_MR task missing 'project_id' or 'mr_iid'.")
            return developer_agent.review_merge_request(
                project_id=int(project_id),
                mr_iid=int(mr_iid),
            )

        elif task_type == "FLASH_FIRMWARE":
            # Delegates to J-Link MCP server tool
            from mcp_servers.jlink_server import flash_firmware, connect_jlink
            device = payload.get("device", "")
            bin_path = payload.get("bin_path", "")
            interface = payload.get("interface", "SWD")
            speed = payload.get("speed", 4000)
            if not device or not bin_path:
                raise ValueError("FLASH_FIRMWARE task missing 'device' or 'bin_path'.")
            connect_result = connect_jlink(device=device, interface=interface, speed=speed)
            if "error" in connect_result:
                raise RuntimeError(f"J-Link connect failed: {connect_result['error']}")
            return flash_firmware(bin_path=bin_path)

        elif task_type == "MONITOR_CHECK":
            from src.agents.monitor import monitor_agent
            source = payload.get("source", "all")
            if source in ("teams", "all") and monitor_agent._teams_team_id:
                monitor_agent._poll_teams.__func__  # Check it exists
            return {"status": "monitor_check_triggered", "source": source}

        elif task_type == "PLAN_TASK":
            from src.agents.planner import planner_agent
            description = payload.get("description", "")
            if not description:
                raise ValueError("PLAN_TASK missing 'description' in payload.")
            return planner_agent.plan_and_execute(description)

        elif task_type == "WORKFLOW":
            from src.integrations.langgraph_runner import langgraph_runner
            workflow_name = payload.get("workflow_name", "")
            if not workflow_name:
                raise ValueError("WORKFLOW task missing 'workflow_name' in payload.")
            state = payload.get("state", {})
            return langgraph_runner.run(workflow_name, state)

        elif task_type == "CODE_TASK":
            from src.integrations.autogen_runner import autogen_runner
            task_description = payload.get("task", "")
            if not task_description:
                raise ValueError("CODE_TASK missing 'task' in payload.")
            trace_id = payload.get("trace_id")
            return autogen_runner.plan(task_description, trace_id=trace_id)

        else:
            raise ValueError(
                f"Unknown task_type: '{task_type}'. "
                "Supported: ANALYZE_LOG, CREATE_MR, REVIEW_MR, FLASH_FIRMWARE, "
                "MONITOR_CHECK, PLAN_TASK, WORKFLOW, CODE_TASK"
            )


# ---------------------------------------------------------------------------
# Global instances
# ---------------------------------------------------------------------------
task_queue = TaskQueue()
task_worker = TaskWorker(task_queue)

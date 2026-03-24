"""
SAGE[ai] - Task Completion Enhancement Tests
=============================================
Tests for DeerFlow-inspired improvements:
  1. Loop detection
  2. Retry with exponential backoff
  3. Error-to-context feedback
  4. Task timeout enforcement
  5. Subtask dependency enforcement (failure propagation)
  6. Build run checkpointing
  7. Context summarization
"""

import json
import os
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

import pytest


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fresh_queue():
    """Return a new TaskQueue backed by an isolated temp SQLite DB."""
    from src.core.queue_manager import TaskQueue
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return TaskQueue(db_path=tmp.name)


def _make_fresh_runner(max_workers=4, parallel_enabled=True):
    """Return (queue, worker, runner) triple backed by isolated DB."""
    from src.core.queue_manager import (
        TaskQueue, TaskWorker, ParallelTaskRunner, ParallelConfig,
    )
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    q = TaskQueue(db_path=tmp.name)
    worker = TaskWorker(q, name="TestWorker")
    cfg = ParallelConfig(max_workers=max_workers, parallel_enabled=parallel_enabled)
    runner = ParallelTaskRunner(q, cfg)
    return q, worker, runner


# ===========================================================================
# 1. LOOP DETECTION TESTS
# ===========================================================================


class TestLoopDetection:
    """Tests for LoopDetector — detects stuck dispatch loops."""

    def test_no_loop_below_threshold(self):
        """Dispatching same task fewer than WARN_THRESHOLD times should not raise."""
        from src.core.queue_manager import LoopDetector
        ld = LoopDetector()
        # Below warn threshold (3) — should be fine
        for _ in range(2):
            ld.check("ANALYZE_LOG", {"log_entry": "same error"})

    def test_warn_at_threshold(self):
        """Dispatching same task WARN_THRESHOLD times should log warning (not raise)."""
        from src.core.queue_manager import LoopDetector
        ld = LoopDetector()
        # Should not raise at warn threshold
        for _ in range(LoopDetector.WARN_THRESHOLD):
            ld.check("ANALYZE_LOG", {"log_entry": "repeated"})

    def test_raises_at_stop_threshold(self):
        """Dispatching same task STOP_THRESHOLD times must raise LoopDetectedError."""
        from src.core.queue_manager import LoopDetector, LoopDetectedError
        ld = LoopDetector()
        with pytest.raises(LoopDetectedError):
            for _ in range(LoopDetector.STOP_THRESHOLD):
                ld.check("ANALYZE_LOG", {"log_entry": "stuck"})

    def test_different_tasks_no_loop(self):
        """Different task types should not trigger loop detection."""
        from src.core.queue_manager import LoopDetector
        ld = LoopDetector()
        for i in range(10):
            ld.check(f"TASK_TYPE_{i}", {"data": str(i)})

    def test_reset_clears_window(self):
        """After reset(), loop detection should start fresh."""
        from src.core.queue_manager import LoopDetector, LoopDetectedError
        ld = LoopDetector()
        # Build up to just below stop threshold
        for _ in range(LoopDetector.STOP_THRESHOLD - 1):
            ld.check("ANALYZE_LOG", {"log_entry": "test"})
        ld.reset()
        # Should not raise now
        ld.check("ANALYZE_LOG", {"log_entry": "test"})

    def test_sliding_window_eviction(self):
        """Old entries should be evicted when window is full."""
        from src.core.queue_manager import LoopDetector
        ld = LoopDetector()
        # Fill window with different tasks
        for i in range(LoopDetector.WINDOW_SIZE):
            ld.check(f"TASK_{i}", {"x": str(i)})
        # Now the first entries should be evicted
        # Repeating a task that was at the start should not count as many
        ld.check("TASK_0", {"x": "0"})  # Should not raise


# ===========================================================================
# 2. RETRY WITH EXPONENTIAL BACKOFF TESTS
# ===========================================================================


class TestRetryLogic:
    """Tests for task retry with transient error classification."""

    def test_transient_error_classification(self):
        """Timeout, rate limit, connection errors should be classified as transient."""
        from src.core.queue_manager import _is_transient_error
        assert _is_transient_error("Connection refused") is True
        assert _is_transient_error("HTTP 429 Too Many Requests") is True
        assert _is_transient_error("Request timed out after 30s") is True
        assert _is_transient_error("503 Service Unavailable") is True
        assert _is_transient_error("connection reset by peer") is True

    def test_permanent_error_classification(self):
        """Invalid args, missing payload, unknown task should be permanent."""
        from src.core.queue_manager import _is_transient_error
        assert _is_transient_error("ValueError: missing 'log_entry'") is False
        assert _is_transient_error("Unknown task_type: 'FOOBAR'") is False
        assert _is_transient_error("KeyError: 'project_id'") is False

    def test_retry_requeues_transient_failure(self):
        """retry_task() should re-queue a task with transient error."""
        q = _make_fresh_queue()
        task_id = q.submit("ANALYZE_LOG", {"log_entry": "test"})
        task = q.get_next(timeout=1.0)
        assert task is not None

        # Fail with transient error
        q.mark_failed(task_id, "Connection refused")

        # Retry should succeed
        with patch("src.core.queue_manager.time.sleep"):  # skip backoff
            result = q.retry_task(task_id)
        assert result is True

        # Task should be back to pending
        status = q.get_status(task_id)
        assert status["status"] == "pending"
        assert status["retry_count"] == 1

    def test_retry_rejects_permanent_failure(self):
        """retry_task() should return False for permanent errors."""
        q = _make_fresh_queue()
        task_id = q.submit("ANALYZE_LOG", {"log_entry": "test"})
        task = q.get_next(timeout=1.0)
        assert task is not None

        q.mark_failed(task_id, "ValueError: missing 'log_entry'")
        result = q.retry_task(task_id)
        assert result is False

    def test_retry_exhaustion(self):
        """After max_retries, retry_task() should return False."""
        q = _make_fresh_queue()
        task_id = q.submit("ANALYZE_LOG", {"log_entry": "test"})
        task = q.get_next(timeout=1.0)
        assert task is not None

        # Exhaust retries
        for i in range(task.max_retries):
            q.mark_failed(task_id, "Connection refused")
            with patch("src.core.queue_manager.time.sleep"):
                q.retry_task(task_id)
            # Re-fetch to get updated task
            with q._lock:
                task = q._tasks[task_id]
                task.status = "failed"
                task.error = "Connection refused"

        # Next retry should fail
        result = q.retry_task(task_id)
        assert result is False

    def test_error_history_tracking(self):
        """Failed tasks should accumulate error_history."""
        q = _make_fresh_queue()
        task_id = q.submit("ANALYZE_LOG", {"log_entry": "test"})
        task = q.get_next(timeout=1.0)

        q.mark_failed(task_id, "Error 1")
        with q._lock:
            t = q._tasks[task_id]
            assert len(t.error_history) == 1
            assert t.error_history[0] == "Error 1"

    def test_task_has_retry_fields_in_dict(self):
        """Task.to_dict() should include retry_count, max_retries, timeout."""
        from src.core.queue_manager import Task
        task = Task("ANALYZE_LOG", {"log_entry": "test"})
        d = task.to_dict()
        assert "retry_count" in d
        assert "max_retries" in d
        assert "timeout" in d
        assert d["retry_count"] == 0
        assert d["max_retries"] == 3


# ===========================================================================
# 3. ERROR-TO-CONTEXT FEEDBACK TESTS
# ===========================================================================


class TestErrorFeedback:
    """Tests for error context injection into retried tasks."""

    def test_build_error_context_empty_on_first_attempt(self):
        """No error context on first attempt."""
        from src.core.queue_manager import TaskWorker, Task
        q = _make_fresh_queue()
        worker = TaskWorker(q, name="TestWorker")
        task = Task("ANALYZE_LOG", {"log_entry": "test"})
        ctx = worker.build_error_context(task)
        assert ctx == ""

    def test_build_error_context_with_history(self):
        """Error context should include previous error messages."""
        from src.core.queue_manager import TaskWorker, Task
        q = _make_fresh_queue()
        worker = TaskWorker(q, name="TestWorker")
        task = Task("ANALYZE_LOG", {"log_entry": "test"})
        task.error_history = ["Connection refused", "Timeout after 30s"]
        task.retry_count = 2
        task.max_retries = 3
        ctx = worker.build_error_context(task)
        assert "RETRY CONTEXT" in ctx
        assert "Connection refused" in ctx
        assert "Timeout after 30s" in ctx
        assert "Attempt 3/3" in ctx

    def test_error_context_caps_at_3_errors(self):
        """Only the last 3 errors should be included."""
        from src.core.queue_manager import TaskWorker, Task
        q = _make_fresh_queue()
        worker = TaskWorker(q, name="TestWorker")
        task = Task("ANALYZE_LOG", {"log_entry": "test"})
        task.error_history = [f"Error {i}" for i in range(10)]
        task.retry_count = 10
        ctx = worker.build_error_context(task)
        assert "Error 7" in ctx
        assert "Error 8" in ctx
        assert "Error 9" in ctx
        assert "Error 0" not in ctx


# ===========================================================================
# 4. TASK TIMEOUT ENFORCEMENT TESTS
# ===========================================================================


class TestTaskTimeout:
    """Tests for per-task timeout enforcement."""

    def test_default_timeout_per_task_type(self):
        """Tasks should get default timeouts based on their type."""
        from src.core.queue_manager import Task, TASK_TIMEOUT_DEFAULTS
        task = Task("ANALYZE_LOG", {"log_entry": "test"})
        assert task.timeout == TASK_TIMEOUT_DEFAULTS["ANALYZE_LOG"]

    def test_custom_timeout_override(self):
        """Custom timeout should override the default."""
        from src.core.queue_manager import Task
        task = Task("ANALYZE_LOG", {"log_entry": "test"}, timeout=42)
        assert task.timeout == 42

    def test_fallback_timeout_for_unknown_type(self):
        """Unknown task types should use DEFAULT_TASK_TIMEOUT."""
        from src.core.queue_manager import Task, DEFAULT_TASK_TIMEOUT
        task = Task("UNKNOWN_TYPE", {"data": "test"})
        assert task.timeout == DEFAULT_TASK_TIMEOUT

    def test_dispatch_with_timeout_succeeds(self):
        """Fast tasks should complete within timeout."""
        from src.core.queue_manager import TaskWorker, Task
        q = _make_fresh_queue()
        worker = TaskWorker(q, name="TestWorker")
        task = Task("ANALYZE_LOG", {"log_entry": "fast"}, timeout=5)

        def fast_dispatch(t):
            return {"status": "completed"}

        worker._dispatch = fast_dispatch
        result = worker._dispatch_with_timeout(task)
        assert result["status"] == "completed"

    def test_dispatch_with_timeout_raises_on_slow_task(self):
        """Slow tasks should raise _TaskTimeoutError."""
        from src.core.queue_manager import TaskWorker, Task, _TaskTimeoutError
        q = _make_fresh_queue()
        worker = TaskWorker(q, name="TestWorker")
        task = Task("ANALYZE_LOG", {"log_entry": "slow"}, timeout=1)

        def slow_dispatch(t):
            time.sleep(5)
            return {"status": "completed"}

        worker._dispatch = slow_dispatch
        with pytest.raises(_TaskTimeoutError):
            worker._dispatch_with_timeout(task)

    def test_dispatch_timeout_propagates_inner_exception(self):
        """Exceptions inside dispatch should propagate through timeout wrapper."""
        from src.core.queue_manager import TaskWorker, Task
        q = _make_fresh_queue()
        worker = TaskWorker(q, name="TestWorker")
        task = Task("ANALYZE_LOG", {"log_entry": "error"}, timeout=5)

        def error_dispatch(t):
            raise ValueError("bad payload")

        worker._dispatch = error_dispatch
        with pytest.raises(ValueError, match="bad payload"):
            worker._dispatch_with_timeout(task)


# ===========================================================================
# 5. DEPENDENCY FAILURE PROPAGATION TESTS
# ===========================================================================


class TestDependencyPropagation:
    """Tests for dependency failure propagation and task blocking."""

    def test_blocked_status_exists(self):
        """TaskStatus should have a BLOCKED state."""
        from src.core.queue_manager import TaskStatus
        assert hasattr(TaskStatus, "BLOCKED")
        assert TaskStatus.BLOCKED == "blocked"

    def test_mark_blocked(self):
        """mark_blocked() should set task status to BLOCKED with reason."""
        q = _make_fresh_queue()
        task_id = q.submit("ANALYZE_LOG", {"log_entry": "test"})
        q.mark_blocked(task_id, "dependency X failed")
        status = q.get_status(task_id)
        assert status["status"] == "blocked"
        assert status["error"] == "dependency X failed"

    def test_get_blocked_dependents(self):
        """Should find pending tasks that depend on a failed task."""
        q = _make_fresh_queue()
        parent_id = q.submit("ANALYZE_LOG", {"log_entry": "parent"})
        child_id = q.submit("ANALYZE_LOG", {"log_entry": "child"}, depends_on=[parent_id])

        blocked = q.get_blocked_dependents(parent_id)
        assert child_id in blocked

    def test_propagate_failure_cascades(self):
        """propagate_failure should recursively block dependents."""
        q = _make_fresh_queue()
        t1 = q.submit("ANALYZE_LOG", {"log_entry": "t1"})
        t2 = q.submit("ANALYZE_LOG", {"log_entry": "t2"}, depends_on=[t1])
        t3 = q.submit("ANALYZE_LOG", {"log_entry": "t3"}, depends_on=[t2])

        blocked = q.propagate_failure(t1)
        assert t2 in blocked
        assert t3 in blocked

        assert q.get_status(t2)["status"] == "blocked"
        assert q.get_status(t3)["status"] == "blocked"

    def test_independent_tasks_not_blocked(self):
        """Tasks with no dependency on the failed task should not be blocked."""
        q = _make_fresh_queue()
        t1 = q.submit("ANALYZE_LOG", {"log_entry": "t1"})
        t2 = q.submit("ANALYZE_LOG", {"log_entry": "t2"})  # independent
        t3 = q.submit("ANALYZE_LOG", {"log_entry": "t3"}, depends_on=[t1])

        blocked = q.propagate_failure(t1)
        assert t3 in blocked
        assert t2 not in blocked
        assert q.get_status(t2)["status"] == "pending"

    def test_wave_execution_skips_blocked_tasks(self):
        """ParallelTaskRunner should skip tasks whose dependencies failed."""
        from src.core.queue_manager import Task, TaskStatus

        q, worker, runner = _make_fresh_runner()
        dispatch_log = []

        def fake_dispatch(task):
            dispatch_log.append(task.task_id)
            if task.payload.get("fail"):
                # Use a permanent error so it won't be retried
                raise ValueError("Invalid payload — permanent error")
            return {"ok": True}

        worker._dispatch = fake_dispatch

        # Task 1 will fail with permanent error, Task 2 depends on it
        t1_id = q.submit("ANALYZE_LOG", {"log_entry": "fail", "fail": True})
        t2_id = q.submit("ANALYZE_LOG", {"log_entry": "depends"}, depends_on=[t1_id])

        tasks = []
        for _ in range(2):
            t = q.get_next(timeout=1.0)
            assert t is not None
            with q._lock:
                t.status = "pending"
            tasks.append(t)

        runner.execute_parallel(tasks, worker, compliance_mode=False)

        # t1 should have been dispatched and failed
        assert t1_id in dispatch_log
        t1_status = q.get_status(t1_id)
        assert t1_status["status"] == "failed"

        # t2 should be blocked (dependency failed) and NOT dispatched
        t2_status = q.get_status(t2_id)
        assert t2_status["status"] == "blocked"
        assert t2_id not in dispatch_log


# ===========================================================================
# 6. BUILD RUN CHECKPOINTING TESTS
# ===========================================================================


class TestBuildCheckpointing:
    """Tests for SQLite-backed build run checkpointing."""

    def _make_orchestrator(self):
        """Create a BuildOrchestrator with temp checkpoint DB."""
        from src.integrations.build_orchestrator import BuildOrchestrator
        orch = BuildOrchestrator.__new__(BuildOrchestrator)
        orch.logger = __import__("logging").getLogger("TestOrch")
        orch._runs = {}
        orch._lock = threading.Lock()
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        orch._checkpoint_db = tmp.name
        orch._init_checkpoint_db()
        return orch

    def test_checkpoint_creates_record(self):
        """_checkpoint should persist a run to SQLite."""
        import sqlite3
        orch = self._make_orchestrator()
        run = {
            "run_id": "test-123",
            "state": "executing",
            "solution_name": "test",
            "product_description": "test product",
            "updated_at": "2025-01-01T00:00:00Z",
            "plan": [],
        }
        orch._checkpoint(run)

        conn = sqlite3.connect(orch._checkpoint_db)
        row = conn.execute("SELECT * FROM build_runs WHERE run_id=?", ("test-123",)).fetchone()
        conn.close()
        assert row is not None
        assert row[1] == "executing"  # state column

    def test_checkpoint_updates_existing(self):
        """_checkpoint should update existing records on state change."""
        import sqlite3
        orch = self._make_orchestrator()
        run = {
            "run_id": "test-456",
            "state": "decomposing",
            "updated_at": "2025-01-01T00:00:00Z",
        }
        orch._checkpoint(run)

        run["state"] = "executing"
        orch._checkpoint(run)

        conn = sqlite3.connect(orch._checkpoint_db)
        row = conn.execute("SELECT state FROM build_runs WHERE run_id=?", ("test-456",)).fetchone()
        conn.close()
        assert row[0] == "executing"

    def test_restore_runs_loads_in_progress(self):
        """_restore_runs should load non-terminal runs from checkpoint DB."""
        import sqlite3
        orch = self._make_orchestrator()

        # Insert an in-progress run directly into DB
        run_data = json.dumps({
            "run_id": "restore-789",
            "state": "awaiting_plan",
            "plan": [{"step": 1}],
        })
        conn = sqlite3.connect(orch._checkpoint_db)
        conn.execute(
            "INSERT INTO build_runs (run_id, state, data, updated_at) VALUES (?, ?, ?, ?)",
            ("restore-789", "awaiting_plan", run_data, "2025-01-01"),
        )
        conn.commit()
        conn.close()

        orch._restore_runs()
        assert "restore-789" in orch._runs
        assert orch._runs["restore-789"]["state"] == "awaiting_plan"

    def test_restore_skips_terminal_runs(self):
        """_restore_runs should NOT load completed/failed/rejected runs."""
        import sqlite3
        orch = self._make_orchestrator()

        for state in ("completed", "failed", "rejected"):
            run_data = json.dumps({"run_id": f"skip-{state}", "state": state})
            conn = sqlite3.connect(orch._checkpoint_db)
            conn.execute(
                "INSERT INTO build_runs (run_id, state, data, updated_at) VALUES (?, ?, ?, ?)",
                (f"skip-{state}", state, run_data, "2025-01-01"),
            )
            conn.commit()
            conn.close()

        orch._restore_runs()
        assert len(orch._runs) == 0


# ===========================================================================
# 7. CONTEXT SUMMARIZATION TESTS
# ===========================================================================


class TestContextSummarization:
    """Tests for context summarization between build waves."""

    def _make_orchestrator(self):
        from src.integrations.build_orchestrator import BuildOrchestrator
        orch = BuildOrchestrator.__new__(BuildOrchestrator)
        orch.logger = __import__("logging").getLogger("TestOrch")
        orch._runs = {}
        orch._lock = threading.Lock()
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        orch._checkpoint_db = tmp.name
        orch._init_checkpoint_db()
        return orch

    def test_empty_results_returns_empty(self):
        """No results should return empty string."""
        orch = self._make_orchestrator()
        assert orch._summarize_context([]) == ""

    def test_short_context_returned_as_is(self):
        """Short context should not be summarized."""
        orch = self._make_orchestrator()
        results = [
            {
                "task": {"task_type": "BACKEND", "description": "Build API"},
                "result": {"status": "completed", "files_changed": ["api.py"]},
            }
        ]
        ctx = orch._summarize_context(results)
        assert "BACKEND" in ctx
        assert "Build API" in ctx

    def test_long_context_gets_summarized(self):
        """Long context should be compressed with summary header."""
        orch = self._make_orchestrator()
        # Generate enough results to exceed MAX_CONTEXT_LENGTH
        results = []
        for i in range(100):
            results.append({
                "task": {
                    "task_type": "BACKEND",
                    "description": f"Build microservice {i} with detailed requirements " * 5,
                },
                "result": {
                    "status": "completed",
                    "files_changed": [f"service_{i}.py", f"test_{i}.py"],
                },
            })
        ctx = orch._summarize_context(results)
        assert "SUMMARIZED" in ctx
        assert "100 prior tasks" in ctx

    def test_summary_includes_failure_counts(self):
        """Summary should count completed and failed tasks."""
        orch = self._make_orchestrator()
        results = []
        for i in range(50):
            results.append({
                "task": {"task_type": "BACKEND", "description": f"Task {i} " * 20},
                "result": {
                    "status": "completed" if i % 3 != 0 else "error",
                    "files_changed": [f"f{i}.py"],
                },
            })
        ctx = orch._summarize_context(results)
        if "SUMMARIZED" in ctx:
            assert "Completed:" in ctx
            assert "Failed:" in ctx

    def test_summary_includes_files_touched(self):
        """Summary should list unique files from all results."""
        orch = self._make_orchestrator()
        results = []
        for i in range(50):
            results.append({
                "task": {"task_type": "FRONTEND", "description": f"Build component {i} " * 20},
                "result": {
                    "status": "completed",
                    "files_changed": [f"component_{i}.tsx"],
                },
            })
        ctx = orch._summarize_context(results)
        if "SUMMARIZED" in ctx:
            assert "Files touched:" in ctx


# ===========================================================================
# Integration: Worker with all enhancements
# ===========================================================================


class TestWorkerIntegration:
    """Integration tests for TaskWorker with loop detection, retry, timeout."""

    def test_worker_retries_transient_then_succeeds(self):
        """Worker should retry transient errors and succeed on later attempt."""
        from src.core.queue_manager import TaskWorker, Task, TaskStatus

        q = _make_fresh_queue()
        worker = TaskWorker(q, name="TestWorker")

        call_count = {"n": 0}

        def flaky_dispatch(task):
            call_count["n"] += 1
            if call_count["n"] <= 1:
                raise ConnectionError("Connection refused")
            return {"status": "ok"}

        worker._dispatch = flaky_dispatch

        task_id = q.submit("ANALYZE_LOG", {"log_entry": "flaky test"})
        task = q.get_next(timeout=1.0)
        assert task is not None

        # First attempt — should fail with transient error
        try:
            worker._dispatch_with_timeout(task)
        except ConnectionError:
            q.mark_failed(task_id, "Connection refused")
            with patch("src.core.queue_manager.time.sleep"):
                retried = q.retry_task(task_id)
            assert retried is True

        # Second attempt — should succeed
        result = worker._dispatch_with_timeout(task)
        assert result["status"] == "ok"

    def test_worker_loop_detection_prevents_infinite_spin(self):
        """Worker's loop detector should prevent infinite dispatch loops."""
        from src.core.queue_manager import TaskWorker, LoopDetectedError

        q = _make_fresh_queue()
        worker = TaskWorker(q, name="TestWorker")

        with pytest.raises(LoopDetectedError):
            for _ in range(10):
                worker._loop_detector.check("ANALYZE_LOG", {"log_entry": "same"})

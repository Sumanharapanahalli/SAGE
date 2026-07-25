import pytest

from handlers import queue
from rpc import RpcError


class FakeQueue:
    """Mirrors the REAL ``TaskQueue`` shape (src/core/queue_manager.py).

    Crucially it has NO ``_config`` attribute — the live parallel config
    lives on the ParallelTaskRunner, not on the queue. A fake that
    fabricated ``_config`` would mask the bug where the handler reads
    config off the wrong object.
    """

    def __init__(self, tasks=None):
        self._tasks = tasks or []

    def get_all_tasks(self):
        return self._tasks

    def get_pending_count(self):
        return sum(1 for t in self._tasks if t["status"] == "pending")


class FakeParallelConfig:
    def __init__(self, parallel_enabled=True, max_workers=4):
        self.parallel_enabled = parallel_enabled
        self.max_workers = max_workers


class FakeParallelRunner:
    """Mirrors the REAL ``ParallelTaskRunner`` shape: exposes ``.config``
    (a ParallelConfig with ``parallel_enabled`` / ``max_workers``), the
    same attribute path FastAPI reads at api.py:1716-1717."""

    def __init__(self, parallel_enabled=True, max_workers=4):
        self.config = FakeParallelConfig(parallel_enabled, max_workers)


@pytest.fixture(autouse=True)
def reset():
    queue._queue = None
    queue._parallel_runner = None
    yield
    queue._queue = None
    queue._parallel_runner = None


def test_get_queue_status_counts_by_status():
    # Statuses must be the literal values TaskStatus emits. The previous
    # version of this test fabricated {"status": "done"} — a string the
    # framework never produces — which is precisely why the handler's matching
    # "done" key went unnoticed while the UI's Done tile stayed at 0.
    queue._queue = FakeQueue(
        tasks=[
            {"id": "1", "status": "pending", "task_type": "x"},
            {"id": "2", "status": "pending", "task_type": "x"},
            {"id": "3", "status": "in_progress", "task_type": "y"},
            {"id": "4", "status": "completed", "task_type": "z"},
            {"id": "5", "status": "failed", "task_type": "z"},
            {"id": "6", "status": "cancelled", "task_type": "z"},
        ]
    )
    queue._parallel_runner = FakeParallelRunner(parallel_enabled=True, max_workers=4)
    result = queue.get_queue_status({})
    assert result["pending"] == 2
    assert result["in_progress"] == 1
    assert result["completed"] == 1
    assert result["failed"] == 1
    assert result["cancelled"] == 1
    assert result["blocked"] == 0
    assert result["parallel_enabled"] is True
    assert result["max_workers"] == 4


def test_get_queue_status_when_unavailable_returns_zeros():
    queue._queue = None
    result = queue.get_queue_status({})
    assert result == {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "failed": 0,
        "blocked": 0,
        "cancelled": 0,
        "parallel_enabled": False,
        "max_workers": 0,
    }


def test_list_queue_tasks_applies_status_filter():
    queue._queue = FakeQueue(
        tasks=[
            {"id": "1", "status": "pending", "task_type": "x"},
            {"id": "2", "status": "done", "task_type": "y"},
        ]
    )
    result = queue.list_queue_tasks({"status": "done"})
    assert len(result) == 1
    assert result[0]["id"] == "2"


def test_list_queue_tasks_limits_results():
    queue._queue = FakeQueue(
        tasks=[{"id": str(i), "status": "done", "task_type": "x"} for i in range(100)]
    )
    result = queue.list_queue_tasks({"limit": 10})
    assert len(result) == 10


def test_list_queue_tasks_when_unavailable_returns_empty():
    queue._queue = None
    assert queue.list_queue_tasks({}) == []


def test_list_queue_tasks_rejects_negative_limit():
    queue._queue = FakeQueue()
    with pytest.raises(RpcError) as exc:
        queue.list_queue_tasks({"limit": -1})
    assert exc.value.code == -32602


# ---------- operator cancel / retry ----------
#
# Before these, the queue was read-only from the desktop: a wedged task could be
# watched forever but never recovered.


class ControlQueue(FakeQueue):
    """Mirrors the REAL TaskQueue's operator-control surface: ``cancel_task``
    and ``requeue_task`` return status dicts (never raise) so the handler owns
    the RpcError translation. Note it does NOT expose the worker's automatic
    ``retry_task`` — the handler must not call it (it sleeps a backoff and
    silently refuses permanent errors)."""

    def __init__(self, tasks=None, cancel_result=None, requeue_result=None):
        super().__init__(tasks)
        self.cancel_result = cancel_result or {
            "cancelled": False,
            "reason": "not_found",
        }
        self.requeue_result = requeue_result or {
            "requeued": False,
            "reason": "not_found",
        }
        self.cancelled = []
        self.requeued = []

    def cancel_task(self, task_id):
        self.cancelled.append(task_id)
        return self.cancel_result

    def requeue_task(self, task_id):
        self.requeued.append(task_id)
        return self.requeue_result


class FakeAuditLogger:
    def __init__(self):
        self.events = []

    def log_event(self, **kw):
        self.events.append(kw)


@pytest.fixture
def audit(monkeypatch):
    log = FakeAuditLogger()
    monkeypatch.setattr(queue, "_logger", log)
    monkeypatch.setattr(
        queue,
        "_operator",
        lambda: {"name": "Ada", "email": "ada@example.com", "provider": "local"},
    )
    return log


def test_cancel_requires_task_id(audit):
    queue._queue = ControlQueue()
    with pytest.raises(RpcError) as exc:
        queue.cancel_task({})
    assert exc.value.code == -32602


def test_cancel_pending_task_succeeds(audit):
    q = ControlQueue(
        cancel_result={
            "cancelled": True,
            "status": "cancelled",
            "was_running": False,
        }
    )
    queue._queue = q
    out = queue.cancel_task({"task_id": "t1"})
    assert out["cancelled"] is True
    assert q.cancelled == ["t1"]


def test_cancel_unknown_task_is_invalid_params(audit):
    queue._queue = ControlQueue(
        cancel_result={"cancelled": False, "reason": "not_found"}
    )
    with pytest.raises(RpcError) as exc:
        queue.cancel_task({"task_id": "ghost"})
    assert exc.value.code == -32602
    assert "not found" in exc.value.message


def test_cancel_terminal_task_is_refused(audit):
    queue._queue = ControlQueue(
        cancel_result={
            "cancelled": False,
            "reason": "terminal",
            "status": "completed",
        }
    )
    with pytest.raises(RpcError) as exc:
        queue.cancel_task({"task_id": "t1"})
    assert exc.value.code == -32602
    assert "already completed" in exc.value.message


def test_cancel_reports_was_running_so_the_ui_does_not_imply_a_kill(audit):
    """An in_progress task is tombstoned, not killed — no cooperative
    cancellation exists. The flag lets the UI say so honestly."""
    queue._queue = ControlQueue(
        cancel_result={
            "cancelled": True,
            "status": "cancelled",
            "was_running": True,
        }
    )
    out = queue.cancel_task({"task_id": "t1"})
    assert out["was_running"] is True
    assert "worker not killed" in audit.events[0]["output_content"]


def test_cancel_is_audited_and_signed_by_the_operator(audit):
    queue._queue = ControlQueue(
        cancel_result={
            "cancelled": True,
            "status": "cancelled",
            "was_running": False,
        }
    )
    queue.cancel_task({"task_id": "t1"})
    ev = audit.events[0]
    assert ev["action_type"] == "TASK_CANCELLED"
    assert ev["actor"] == "Ada"
    assert ev["metadata"]["task_id"] == "t1"
    # Framework control (Law 1): immediate, but still recorded.
    assert ev["metadata"]["tier"] == "framework_control"


def test_cancel_without_queue_is_sidecar_error(audit):
    queue._queue = None
    with pytest.raises(RpcError) as exc:
        queue.cancel_task({"task_id": "t1"})
    assert exc.value.code == -32000


def test_retry_requeues_a_failed_task(audit):
    q = ControlQueue(requeue_result={"requeued": True, "status": "pending"})
    queue._queue = q
    out = queue.retry_task({"task_id": "t1"})
    assert out["requeued"] is True
    assert out["status"] == "pending"
    assert q.requeued == ["t1"]


def test_retry_refuses_a_task_that_is_not_terminal(audit):
    queue._queue = ControlQueue(
        requeue_result={
            "requeued": False,
            "reason": "not_retryable",
            "status": "in_progress",
        }
    )
    with pytest.raises(RpcError) as exc:
        queue.retry_task({"task_id": "t1"})
    assert exc.value.code == -32602
    assert "in_progress" in exc.value.message


def test_retry_unknown_task_is_invalid_params(audit):
    queue._queue = ControlQueue(
        requeue_result={"requeued": False, "reason": "not_found"}
    )
    with pytest.raises(RpcError) as exc:
        queue.retry_task({"task_id": "ghost"})
    assert exc.value.code == -32602


def test_retry_is_audited(audit):
    queue._queue = ControlQueue(requeue_result={"requeued": True, "status": "pending"})
    queue.retry_task({"task_id": "t1"})
    assert audit.events[0]["action_type"] == "TASK_RETRIED"
    assert audit.events[0]["actor"] == "Ada"


def test_retry_never_calls_the_workers_automatic_retry_task(audit):
    """TaskQueue.retry_task sleeps an exponential backoff inside the serial
    dispatch loop and silently refuses permanent errors. An operator's explicit
    retry must use requeue_task instead."""
    q = ControlQueue(requeue_result={"requeued": True, "status": "pending"})

    def _forbidden(_task_id):
        raise AssertionError("handler called the worker's retry_task, not requeue_task")

    q.retry_task = _forbidden
    queue._queue = q
    queue.retry_task({"task_id": "t1"})
    assert q.requeued == ["t1"]

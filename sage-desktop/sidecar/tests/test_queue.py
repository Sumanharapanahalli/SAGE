from unittest.mock import MagicMock
import pytest

from handlers import queue
from rpc import RpcError


class FakeQueue:
    def __init__(self, tasks=None, parallel_enabled=True, max_workers=4):
        self._tasks = tasks or []
        self._config = MagicMock()
        self._config.parallel_enabled = parallel_enabled
        self._config.max_workers = max_workers

    def get_all_tasks(self):
        return self._tasks

    def get_pending_count(self):
        return sum(1 for t in self._tasks if t["status"] == "pending")


@pytest.fixture(autouse=True)
def reset():
    queue._queue = None
    yield
    queue._queue = None


def test_get_queue_status_counts_by_status():
    queue._queue = FakeQueue(tasks=[
        {"id": "1", "status": "pending", "task_type": "x"},
        {"id": "2", "status": "pending", "task_type": "x"},
        {"id": "3", "status": "in_progress", "task_type": "y"},
        {"id": "4", "status": "done", "task_type": "z"},
        {"id": "5", "status": "failed", "task_type": "z"},
    ])
    result = queue.get_queue_status({})
    assert result["pending"] == 2
    assert result["in_progress"] == 1
    assert result["done"] == 1
    assert result["failed"] == 1
    assert result["blocked"] == 0
    assert result["parallel_enabled"] is True
    assert result["max_workers"] == 4


def test_get_queue_status_when_unavailable_returns_zeros():
    queue._queue = None
    result = queue.get_queue_status({})
    assert result == {
        "pending": 0,
        "in_progress": 0,
        "done": 0,
        "failed": 0,
        "blocked": 0,
        "parallel_enabled": False,
        "max_workers": 0,
    }


def test_list_queue_tasks_applies_status_filter():
    queue._queue = FakeQueue(tasks=[
        {"id": "1", "status": "pending", "task_type": "x"},
        {"id": "2", "status": "done", "task_type": "y"},
    ])
    result = queue.list_queue_tasks({"status": "done"})
    assert len(result) == 1
    assert result[0]["id"] == "2"


def test_list_queue_tasks_limits_results():
    queue._queue = FakeQueue(tasks=[
        {"id": str(i), "status": "done", "task_type": "x"} for i in range(100)
    ])
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

import pytest
from unittest.mock import MagicMock
import time


def test_get_scheduled_tasks_empty_when_none():
    from src.core.project_loader import ProjectConfig
    cfg = ProjectConfig.__new__(ProjectConfig)
    cfg._tasks = {}
    assert cfg.get_scheduled_tasks() == []


def test_get_scheduled_tasks_returns_list():
    from src.core.project_loader import ProjectConfig
    cfg = ProjectConfig.__new__(ProjectConfig)
    cfg._tasks = {
        "scheduled": [
            {"task_type": "MONITOR_CHECK", "cron": "*/5 * * * *", "payload": {}}
        ]
    }
    tasks = cfg.get_scheduled_tasks()
    assert len(tasks) == 1
    assert tasks[0]["task_type"] == "MONITOR_CHECK"


def test_scheduler_submits_due_task():
    """Scheduler calls queue_manager.submit() when a task is due."""
    from src.core.task_scheduler import TaskScheduler

    mock_qm = MagicMock()
    mock_pc = MagicMock()
    mock_pc.get_scheduled_tasks.return_value = [
        {"task_type": "MONITOR_CHECK", "cron": "* * * * *", "payload": {"source": "all"}}
    ]

    scheduler = TaskScheduler(queue_manager=mock_qm, project_config=mock_pc)
    # Force the task to be due by setting last_run far in the past
    scheduler._last_run["MONITOR_CHECK_* * * * *"] = 0.0
    scheduler._tick()
    mock_qm.submit.assert_called_once_with(
        "MONITOR_CHECK", {"source": "all"}, priority=8, source="scheduler"
    )


def test_scheduler_does_not_resubmit_within_interval():
    from src.core.task_scheduler import TaskScheduler

    mock_qm = MagicMock()
    mock_pc = MagicMock()
    mock_pc.get_scheduled_tasks.return_value = [
        {"task_type": "ANALYZE_LOG", "cron": "0 * * * *", "payload": {}}
    ]

    scheduler = TaskScheduler(queue_manager=mock_qm, project_config=mock_pc)
    scheduler._last_run["ANALYZE_LOG_0 * * * *"] = time.time()  # just ran
    scheduler._tick()
    mock_qm.submit.assert_not_called()

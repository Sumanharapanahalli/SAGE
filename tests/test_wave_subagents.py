import pytest
from unittest.mock import MagicMock


def test_subtask_fanout_submits_children():
    """When _fanout_subtasks is called with 3 subtasks, submit is called 3 times."""
    from src.core.queue_manager import _fanout_subtasks

    mock_qm = MagicMock()
    parent_task_id = "parent-001"
    subtasks = [
        {"task_type": "ANALYZE_LOG", "payload": {"log_entry": "error A"}, "wave": 0},
        {"task_type": "ANALYZE_LOG", "payload": {"log_entry": "error B"}, "wave": 0},
        {"task_type": "REVIEW_MR",   "payload": {"mr_iid": 42},           "wave": 1},
    ]
    _fanout_subtasks(mock_qm, parent_task_id, subtasks)
    assert mock_qm.submit.call_count == 3


def test_wave_0_tasks_have_no_depends_on():
    """Wave 0 subtasks are submitted with empty depends_on."""
    from src.core.queue_manager import _fanout_subtasks
    mock_qm = MagicMock()
    mock_qm.submit.return_value = "task-id-001"
    subtasks = [
        {"task_type": "ANALYZE_LOG", "payload": {}, "wave": 0},
    ]
    _fanout_subtasks(mock_qm, "parent-x", subtasks)
    call_kwargs = mock_qm.submit.call_args[1]
    assert call_kwargs.get("depends_on", []) == []


def test_wave_1_tasks_depend_on_wave_0():
    """Wave 1 subtasks list wave 0 task_ids in depends_on."""
    from src.core.queue_manager import _fanout_subtasks

    submitted_ids = ["id-w0-a", "id-w0-b", "id-w1-a"]
    mock_qm = MagicMock()
    mock_qm.submit.side_effect = iter(submitted_ids)

    subtasks = [
        {"task_type": "ANALYZE_LOG", "payload": {}, "wave": 0},
        {"task_type": "ANALYZE_LOG", "payload": {}, "wave": 0},
        {"task_type": "REVIEW_MR",   "payload": {}, "wave": 1},
    ]
    _fanout_subtasks(mock_qm, "parent-y", subtasks)
    wave1_call = mock_qm.submit.call_args_list[2]
    depends = wave1_call[1].get("depends_on", [])
    assert set(depends) == {"id-w0-a", "id-w0-b"}


def test_subtasks_endpoint_exists():
    from src.interface.api import app
    routes = [r.path for r in app.routes]
    assert "/tasks/{task_id}/subtasks" in routes

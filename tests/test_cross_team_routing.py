# tests/test_cross_team_routing.py

def test_get_task_queue_returns_taskqueue_instance():
    from src.core.queue_manager import get_task_queue, TaskQueue
    q = get_task_queue("solution_a")
    assert isinstance(q, TaskQueue)


def test_get_task_queue_different_solutions_different_instances():
    from src.core.queue_manager import get_task_queue
    assert get_task_queue("sol_x") is not get_task_queue("sol_y")


def test_get_task_queue_same_solution_same_instance():
    from src.core.queue_manager import get_task_queue
    assert get_task_queue("sol_z") is get_task_queue("sol_z")

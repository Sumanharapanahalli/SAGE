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


def test_submit_task_no_target_queues_to_active_solution():
    from src.interface.api import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.post("/tasks/submit", json={
        "task_type": "ANALYZE_LOG",
        "payload": {"log_entry": "test"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert data["status"] == "queued"


def test_submit_task_unknown_target_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("SAGE_SOLUTIONS_DIR", str(tmp_path))
    from src.interface.api import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.post("/tasks/submit", json={
        "task_type": "ANALYZE_LOG",
        "payload": {},
        "target_solution": "nonexistent_team_xyz",
    })
    assert resp.status_code == 404


def test_submit_task_unpermitted_target_returns_403(tmp_path, monkeypatch):
    monkeypatch.setenv("SAGE_SOLUTIONS_DIR", str(tmp_path))
    # Create the target solution directory so it passes the 404 check
    (tmp_path / "target_team").mkdir()
    (tmp_path / "target_team" / "project.yaml").write_text("name: target_team\n")

    from src.interface.api import app
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    client = TestClient(app)
    with patch("src.core.org_loader.org_loader") as mock_org:
        mock_org.org_name = "test_org"
        mock_org.is_route_allowed.return_value = False
        resp = client.post("/tasks/submit", json={
            "task_type": "ANALYZE_LOG",
            "payload": {},
            "target_solution": "target_team",
            "source_solution": "my_team",
        })
    assert resp.status_code == 403
    assert "not permitted" in resp.json().get("detail", "").lower()

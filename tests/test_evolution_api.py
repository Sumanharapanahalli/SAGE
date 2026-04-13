import pytest
from fastapi.testclient import TestClient
from src.interface.api import app

client = TestClient(app)

def test_list_evolution_experiments():
    response = client.get("/evolution/experiments")
    assert response.status_code == 200
    data = response.json()
    assert "experiments" in data
    assert isinstance(data["experiments"], list)

def test_start_evolution_experiment():
    payload = {
        "solution_name": "test_solution",
        "target_type": "prompt",
        "population_size": 10,
        "max_generations": 5,
        "mutation_rate": 0.1,
        "crossover_rate": 0.7
    }
    response = client.post("/evolution/experiments", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "experiment_id" in data

def test_get_evolution_status():
    # First start an experiment
    payload = {
        "solution_name": "test_solution",
        "target_type": "prompt",
        "population_size": 10,
        "max_generations": 5,
        "mutation_rate": 0.1,
        "crossover_rate": 0.7
    }
    start_response = client.post("/evolution/experiments", json=payload)
    experiment_id = start_response.json()["experiment_id"]

    # Then check status
    response = client.get(f"/evolution/experiments/{experiment_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "current_generation" in data

def test_get_experiment_details():
    # Start experiment
    payload = {
        "solution_name": "test_solution",
        "target_type": "code",
        "population_size": 15,
        "max_generations": 10
    }
    start_response = client.post("/evolution/experiments", json=payload)
    experiment_id = start_response.json()["experiment_id"]

    # Get experiment details
    response = client.get(f"/evolution/experiments/{experiment_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["experiment_id"] == experiment_id
    assert data["solution_name"] == "test_solution"
    assert data["target_type"] == "code"
    assert data["population_size"] == 15
    assert data["max_generations"] == 10

def test_update_experiment():
    # Start experiment
    payload = {
        "solution_name": "test_solution",
        "target_type": "build",
        "population_size": 20,
        "max_generations": 30
    }
    start_response = client.post("/evolution/experiments", json=payload)
    experiment_id = start_response.json()["experiment_id"]

    # Update experiment status
    update_payload = {"status": "paused"}
    response = client.put(f"/evolution/experiments/{experiment_id}", json=update_payload)
    assert response.status_code == 200
    assert "message" in response.json()

    # Verify update
    get_response = client.get(f"/evolution/experiments/{experiment_id}")
    assert get_response.json()["status"] == "paused"

def test_stop_experiment():
    # Start experiment
    payload = {
        "solution_name": "test_solution",
        "target_type": "prompt",
        "population_size": 5,
        "max_generations": 3
    }
    start_response = client.post("/evolution/experiments", json=payload)
    experiment_id = start_response.json()["experiment_id"]

    # Stop experiment
    response = client.delete(f"/evolution/experiments/{experiment_id}")
    assert response.status_code == 200
    assert "message" in response.json()

    # Verify experiment is stopped
    get_response = client.get(f"/evolution/experiments/{experiment_id}")
    assert get_response.json()["status"] == "stopped"

def test_experiment_not_found():
    # Test getting non-existent experiment
    response = client.get("/evolution/experiments/non-existent-id")
    assert response.status_code == 404

    # Test getting status of non-existent experiment
    response = client.get("/evolution/experiments/non-existent-id/status")
    assert response.status_code == 404

def test_invalid_experiment_update():
    # Start experiment
    payload = {
        "solution_name": "test_solution",
        "target_type": "prompt",
        "population_size": 10,
        "max_generations": 5
    }
    start_response = client.post("/evolution/experiments", json=payload)
    experiment_id = start_response.json()["experiment_id"]

    # Try invalid status
    update_payload = {"status": "invalid_status"}
    response = client.put(f"/evolution/experiments/{experiment_id}", json=update_payload)
    assert response.status_code == 400

def test_start_experiment_validation():
    # Test missing solution name
    payload = {
        "solution_name": "",
        "target_type": "prompt",
        "population_size": 10,
        "max_generations": 5
    }
    response = client.post("/evolution/experiments", json=payload)
    assert response.status_code == 400

def test_list_candidates():
    # Start experiment
    payload = {
        "solution_name": "test_solution",
        "target_type": "prompt",
        "population_size": 10,
        "max_generations": 5
    }
    start_response = client.post("/evolution/experiments", json=payload)
    experiment_id = start_response.json()["experiment_id"]

    # List candidates
    response = client.get(f"/evolution/experiments/{experiment_id}/candidates")
    assert response.status_code == 200
    data = response.json()
    assert "candidates" in data
    assert isinstance(data["candidates"], list)

def test_approve_candidate():
    # Start experiment
    payload = {
        "solution_name": "test_solution",
        "target_type": "prompt",
        "population_size": 10,
        "max_generations": 5
    }
    start_response = client.post("/evolution/experiments", json=payload)
    experiment_id = start_response.json()["experiment_id"]

    # Approve candidate
    approval_payload = {
        "experiment_id": experiment_id,
        "candidate_id": "test-candidate-1",
        "approved": True,
        "feedback": "Good improvement to prompt clarity"
    }
    response = client.post("/evolution/candidates/approve", json=approval_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert "candidate_id" in data

def test_reject_candidate():
    # Start experiment
    payload = {
        "solution_name": "test_solution",
        "target_type": "code",
        "population_size": 10,
        "max_generations": 5
    }
    start_response = client.post("/evolution/experiments", json=payload)
    experiment_id = start_response.json()["experiment_id"]

    # Reject candidate
    rejection_payload = {
        "experiment_id": experiment_id,
        "candidate_id": "test-candidate-2",
        "approved": False,
        "feedback": "Code quality issues detected"
    }
    response = client.post("/evolution/candidates/approve", json=rejection_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"

def test_compliance_report():
    # Start experiment
    payload = {
        "solution_name": "test_solution",
        "target_type": "build",
        "population_size": 15,
        "max_generations": 10
    }
    start_response = client.post("/evolution/experiments", json=payload)
    experiment_id = start_response.json()["experiment_id"]

    # Get compliance report
    response = client.get(f"/evolution/experiments/{experiment_id}/compliance")
    assert response.status_code == 200
    data = response.json()
    assert "total_candidates" in data
    assert "approved_candidates" in data
    assert "rejected_candidates" in data
    assert "compliance_score" in data
    assert "risk_metrics" in data

def test_candidates_not_found():
    # Test candidates for non-existent experiment
    response = client.get("/evolution/experiments/non-existent-id/candidates")
    assert response.status_code == 404

def test_compliance_not_found():
    # Test compliance report for non-existent experiment
    response = client.get("/evolution/experiments/non-existent-id/compliance")
    assert response.status_code == 404
"""
Collective Intelligence API — Endpoint Tests
=============================================
Tests the REST API layer for learnings, help requests, sync, and stats.
"""

import os
import pytest
from unittest.mock import patch, MagicMock


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_collective(tmp_path):
    """Mock CollectiveMemory for API tests."""
    from src.core.collective_memory import CollectiveMemory
    cm = CollectiveMemory(
        repo_path=str(tmp_path / "api_collective"),
        require_approval=False,
    )
    return cm


@pytest.fixture
def client(mock_collective):
    """FastAPI test client with mocked collective memory."""
    from fastapi.testclient import TestClient
    from src.interface.routes.collective_intelligence import router, _get_cm
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    # Override dependency
    app.dependency_overrides[_get_cm] = lambda: mock_collective

    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════════
# LEARNING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

class TestLearningEndpoints:

    def test_post_learning_returns_201(self, client):
        resp = client.post("/collective/learnings", json={
            "author_agent": "analyst",
            "author_solution": "medtech",
            "topic": "uart",
            "title": "Test learning",
            "content": "Some useful content",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data

    def test_post_learning_validates_required_fields(self, client):
        resp = client.post("/collective/learnings", json={})
        assert resp.status_code == 422

    def test_get_learnings_returns_list(self, client):
        client.post("/collective/learnings", json={
            "author_agent": "a", "author_solution": "s",
            "topic": "t", "title": "T", "content": "C",
        })
        resp = client.get("/collective/learnings")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["learnings"], list)
        assert data["count"] >= 1

    def test_get_learnings_with_query(self, client):
        client.post("/collective/learnings", json={
            "author_agent": "a", "author_solution": "medtech",
            "topic": "uart", "title": "UART overflow", "content": "Buffer stuff",
        })
        resp = client.get("/collective/learnings", params={"query": "UART"})
        assert resp.status_code == 200

    def test_get_learnings_filters_by_solution(self, client):
        client.post("/collective/learnings", json={
            "author_agent": "a", "author_solution": "medtech",
            "topic": "t", "title": "T1", "content": "C",
        })
        client.post("/collective/learnings", json={
            "author_agent": "a", "author_solution": "automotive",
            "topic": "t", "title": "T2", "content": "C",
        })
        resp = client.get("/collective/learnings", params={"solution": "medtech"})
        data = resp.json()
        assert all(l["author_solution"] == "medtech" for l in data["learnings"])

    def test_get_learning_by_id(self, client):
        resp = client.post("/collective/learnings", json={
            "author_agent": "a", "author_solution": "s",
            "topic": "t", "title": "T", "content": "C",
        })
        learning_id = resp.json()["id"]
        resp2 = client.get(f"/collective/learnings/{learning_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == learning_id

    def test_get_learning_404(self, client):
        resp = client.get("/collective/learnings/nonexistent-id")
        assert resp.status_code == 404

    def test_validate_learning(self, client):
        resp = client.post("/collective/learnings", json={
            "author_agent": "a", "author_solution": "s",
            "topic": "t", "title": "T", "content": "C",
        })
        learning_id = resp.json()["id"]
        resp2 = client.post(
            f"/collective/learnings/{learning_id}/validate",
            json={"validated_by": "qa_agent"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["validation_count"] == 1


# ═══════════════════════════════════════════════════════════════════════
# HELP REQUEST ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

class TestHelpRequestEndpoints:

    def test_post_help_request_returns_201(self, client):
        resp = client.post("/collective/help-requests", json={
            "title": "Need help with I2C",
            "requester_agent": "dev",
            "requester_solution": "auto",
            "urgency": "high",
            "required_expertise": ["i2c"],
            "context": "Bus hangs after sleep/wake.",
        })
        assert resp.status_code == 201
        assert resp.json()["id"].startswith("hr-")

    def test_get_help_requests(self, client):
        client.post("/collective/help-requests", json={
            "title": "Help", "requester_agent": "a",
            "requester_solution": "s", "context": "ctx",
        })
        resp = client.get("/collective/help-requests")
        assert resp.status_code == 200
        assert len(resp.json()["requests"]) >= 1

    def test_claim_help_request(self, client):
        resp = client.post("/collective/help-requests", json={
            "title": "Help", "requester_agent": "a",
            "requester_solution": "s", "context": "ctx",
        })
        req_id = resp.json()["id"]
        resp2 = client.put(f"/collective/help-requests/{req_id}/claim", json={
            "agent": "expert", "solution": "iot",
        })
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "claimed"

    def test_claim_already_claimed_returns_409(self, client):
        resp = client.post("/collective/help-requests", json={
            "title": "Help", "requester_agent": "a",
            "requester_solution": "s", "context": "ctx",
        })
        req_id = resp.json()["id"]
        client.put(f"/collective/help-requests/{req_id}/claim", json={
            "agent": "a1", "solution": "s1",
        })
        resp2 = client.put(f"/collective/help-requests/{req_id}/claim", json={
            "agent": "a2", "solution": "s2",
        })
        assert resp2.status_code == 409

    def test_respond_to_help_request(self, client):
        resp = client.post("/collective/help-requests", json={
            "title": "Help", "requester_agent": "a",
            "requester_solution": "s", "context": "ctx",
        })
        req_id = resp.json()["id"]
        client.put(f"/collective/help-requests/{req_id}/claim", json={
            "agent": "expert", "solution": "iot",
        })
        resp2 = client.put(f"/collective/help-requests/{req_id}/respond", json={
            "responder_agent": "expert", "responder_solution": "iot",
            "content": "Try the errata workaround.",
        })
        assert resp2.status_code == 200
        assert len(resp2.json()["responses"]) == 1

    def test_close_help_request(self, client):
        resp = client.post("/collective/help-requests", json={
            "title": "Help", "requester_agent": "a",
            "requester_solution": "s", "context": "ctx",
        })
        req_id = resp.json()["id"]
        resp2 = client.put(f"/collective/help-requests/{req_id}/close")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "closed"


# ═══════════════════════════════════════════════════════════════════════
# SYNC & STATS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

class TestSyncAndStats:

    def test_post_sync(self, client):
        resp = client.post("/collective/sync")
        assert resp.status_code == 200
        assert "indexed" in resp.json()

    def test_get_stats(self, client):
        resp = client.get("/collective/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "learning_count" in data
        assert "help_request_count" in data
        assert "topics" in data
        assert "contributors" in data


# ═══════════════════════════════════════════════════════════════════════
# ERROR PATHS & CORNER CASES
# ═══════════════════════════════════════════════════════════════════════

class TestAPIEdgeCases:

    def test_validate_nonexistent_learning_returns_404(self, client):
        resp = client.post(
            "/collective/learnings/nonexistent-id/validate",
            json={"validated_by": "qa"},
        )
        assert resp.status_code == 404

    def test_respond_nonexistent_help_request_returns_404(self, client):
        resp = client.put(
            "/collective/help-requests/hr-nonexistent/respond",
            json={"responder_agent": "a", "responder_solution": "s", "content": "x"},
        )
        assert resp.status_code == 404

    def test_close_nonexistent_help_request_returns_404(self, client):
        resp = client.put("/collective/help-requests/hr-nonexistent/close")
        assert resp.status_code == 404

    def test_claim_nonexistent_help_request_returns_404(self, client):
        resp = client.put(
            "/collective/help-requests/hr-nonexistent/claim",
            json={"agent": "a", "solution": "s"},
        )
        assert resp.status_code == 404

    def test_get_learnings_with_tags_filter(self, client):
        """GET /collective/learnings with tags parameter filters results."""
        client.post("/collective/learnings", json={
            "author_agent": "a", "author_solution": "s",
            "topic": "t", "title": "Tagged", "content": "C",
            "tags": ["python", "web"],
        })
        client.post("/collective/learnings", json={
            "author_agent": "a", "author_solution": "s",
            "topic": "t", "title": "Other", "content": "C",
            "tags": ["rust"],
        })
        resp = client.get("/collective/learnings", params={"tags": "python"})
        data = resp.json()
        assert resp.status_code == 200
        for l in data["learnings"]:
            assert "python" in l.get("tags", [])

    def test_get_help_requests_with_expertise_filter(self, client):
        """GET /collective/help-requests with expertise parameter."""
        client.post("/collective/help-requests", json={
            "title": "I2C help", "requester_agent": "a",
            "requester_solution": "s", "context": "c",
            "required_expertise": ["i2c", "stm32"],
        })
        client.post("/collective/help-requests", json={
            "title": "Python help", "requester_agent": "a",
            "requester_solution": "s", "context": "c",
            "required_expertise": ["python"],
        })
        resp = client.get("/collective/help-requests", params={"expertise": "i2c"})
        data = resp.json()
        assert resp.status_code == 200
        for r in data["requests"]:
            assert "i2c" in r.get("required_expertise", [])

    def test_post_learning_with_all_optional_fields(self, client):
        """POST learning with all fields including optionals."""
        resp = client.post("/collective/learnings", json={
            "author_agent": "analyst",
            "author_solution": "medtech",
            "topic": "compliance",
            "title": "Full learning",
            "content": "Complete content",
            "tags": ["a", "b"],
            "confidence": 0.9,
            "source_task_id": "task-xyz",
        })
        assert resp.status_code == 201
        learning_id = resp.json()["id"]
        resp2 = client.get(f"/collective/learnings/{learning_id}")
        data = resp2.json()
        assert data["tags"] == ["a", "b"]
        assert data["confidence"] == 0.9

    def test_get_help_requests_closed_status(self, client):
        """GET /collective/help-requests?status=closed returns closed ones."""
        resp = client.post("/collective/help-requests", json={
            "title": "Help", "requester_agent": "a",
            "requester_solution": "s", "context": "c",
        })
        req_id = resp.json()["id"]
        client.put(f"/collective/help-requests/{req_id}/close")
        resp2 = client.get("/collective/help-requests", params={"status": "closed"})
        data = resp2.json()
        assert any(r["id"] == req_id for r in data["requests"])

# tests/test_agent_endpoints.py
from fastapi.testclient import TestClient
from unittest.mock import patch


def test_analyze_jd_endpoint_exists():
    from src.interface.api import app
    routes = [r.path for r in app.routes]
    assert "/agents/analyze-jd" in routes


def test_analyze_jd_returns_role_config():
    from src.interface.api import app
    client = TestClient(app)
    mock_config = {
        "role_key": "security_reviewer",
        "name": "Security Reviewer",
        "description": "Reviews PRs for OWASP issues",
        "system_prompt": "You are a security reviewer...",
        "task_types": [{"name": "REVIEW_CODE_SECURITY", "description": "Review diffs"}],
        "output_schema": {"severity": "RED|AMBER|GREEN"},
        "eval_case": {"input": "SELECT * FROM users WHERE id='${id}'", "expected_keywords": ["injection"]},
    }
    with patch("src.core.agent_factory.jd_to_role_config", return_value=mock_config):
        resp = client.post("/agents/analyze-jd", json={
            "jd_text": "Senior Security Engineer...",
            "solution_context": "Node.js API",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["role_key"] == "security_reviewer"
    assert "task_types" in data


def test_analyze_jd_returns_422_on_empty_jd():
    from src.interface.api import app
    client = TestClient(app)
    resp = client.post("/agents/analyze-jd", json={"jd_text": "   ", "solution_context": ""})
    assert resp.status_code == 422


def test_performance_endpoint_exists():
    from src.interface.api import app
    routes = [r.path for r in app.routes]
    assert any("/agents/{" in r for r in routes)


def test_performance_returns_stats():
    from src.interface.api import app
    client = TestClient(app)
    resp = client.get("/agents/analyst/performance")
    assert resp.status_code == 200
    data = resp.json()
    assert "role_key" in data
    assert "approval_rate" in data
    assert "total_proposals" in data

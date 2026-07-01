"""
API tests for POST /agent/run: input sanitization (Task 10) and per-IP rate
limiting (Task 6).

NOTE: AgentRunRequest declares ``context: str`` (Pydantic v2), so payloads use
a string context. UniversalAgent is patched so the endpoint logic — not the
real agent — is exercised, keeping these tests fast and deterministic.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def _payload(task="do something", role_id="engineer"):
    return {
        "role_id": role_id,
        "task": task,
        "context": "",
        "actor": "tester",
    }


@pytest.fixture
def client():
    from src.interface.api import app, _agent_run_limiter
    _agent_run_limiter.reset()
    with TestClient(app) as c:
        yield c
    _agent_run_limiter.reset()


# ---------------------------------------------------------------------------
# Task 10 — input sanitization
# ---------------------------------------------------------------------------


def test_clean_valid_request_succeeds_not_422(client):
    with patch("src.agents.universal.UniversalAgent") as MockAgent:
        MockAgent.return_value.run.return_value = {"status": "ok", "output": "done"}
        resp = client.post("/agent/run", json=_payload("Refactor the auth module."))

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "output": "done"}
    MockAgent.return_value.run.assert_called_once()


def test_clean_request_passes_sanitized_task_to_agent(client):
    with patch("src.agents.universal.UniversalAgent") as MockAgent:
        MockAgent.return_value.run.return_value = {"status": "ok"}
        resp = client.post(
            "/agent/run", json=_payload("keep\ttab\nnewline\x00\x1bstripcontrol")
        )

    assert resp.status_code == 200
    _, kwargs = MockAgent.return_value.run.call_args
    assert kwargs["task"] == "keep\ttab\nnewlinestripcontrol"


def test_over_4000_char_task_returns_422(client):
    with patch("src.agents.universal.UniversalAgent") as MockAgent:
        resp = client.post("/agent/run", json=_payload("a" * 4001))

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    # Must come from the sanitizer's length check (a plain string message),
    # NOT from Pydantic request validation (which returns a list).
    assert isinstance(detail, str)
    assert "4000" in detail
    MockAgent.return_value.run.assert_not_called()


def test_exactly_4000_char_task_accepted_not_422(client):
    with patch("src.agents.universal.UniversalAgent") as MockAgent:
        MockAgent.return_value.run.return_value = {"status": "ok"}
        resp = client.post("/agent/run", json=_payload("a" * 4000))

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Task 6 — per-IP rate limiting
# ---------------------------------------------------------------------------

RATE_LIMIT = 10
WINDOW_SECONDS = 60.0


def test_rate_limit_returns_429_with_retry_after_after_excess(client):
    """The first RATE_LIMIT requests from one IP succeed; the next is 429."""
    headers = {"X-Forwarded-For": "203.0.113.10"}
    with patch("src.agents.universal.UniversalAgent") as MockAgent:
        MockAgent.return_value.run.return_value = {"status": "ok"}
        for i in range(RATE_LIMIT):
            resp = client.post("/agent/run", json=_payload(), headers=headers)
            assert resp.status_code != 429, f"request {i + 1} unexpectedly throttled"

        blocked = client.post("/agent/run", json=_payload(), headers=headers)
    assert blocked.status_code == 429
    retry_after = blocked.headers.get("Retry-After")
    assert retry_after is not None, "Retry-After header missing on 429"
    assert retry_after.isdigit(), f"Retry-After not an integer: {retry_after!r}"
    assert 0 < int(retry_after) <= WINDOW_SECONDS


def test_second_ip_is_unaffected_by_first_ips_limit(client):
    """Exhausting one IP's bucket does not throttle a different IP."""
    ip_a = {"X-Forwarded-For": "203.0.113.10"}
    ip_b = {"X-Forwarded-For": "198.51.100.20"}
    with patch("src.agents.universal.UniversalAgent") as MockAgent:
        MockAgent.return_value.run.return_value = {"status": "ok"}
        for _ in range(RATE_LIMIT):
            client.post("/agent/run", json=_payload(), headers=ip_a)
        assert client.post("/agent/run", json=_payload(), headers=ip_a).status_code == 429

        for i in range(RATE_LIMIT):
            resp = client.post("/agent/run", json=_payload(), headers=ip_b)
            assert resp.status_code != 429, f"IP B request {i + 1} unexpectedly throttled"


def test_disabled_when_rate_limit_zero(client):
    """A capacity of 0 disables throttling entirely."""
    from src.interface.api import _agent_run_limiter
    _agent_run_limiter.configure(capacity=0, window_seconds=WINDOW_SECONDS)
    headers = {"X-Forwarded-For": "203.0.113.30"}
    with patch("src.agents.universal.UniversalAgent") as MockAgent:
        MockAgent.return_value.run.return_value = {"status": "ok"}
        for _ in range(RATE_LIMIT * 3):
            resp = client.post("/agent/run", json=_payload(), headers=headers)
            assert resp.status_code != 429
    _agent_run_limiter.configure(capacity=RATE_LIMIT, window_seconds=WINDOW_SECONDS)


def test_rate_limit_check_precedes_oversize_task_rejection(client):
    """Rate limiting is the outer guard — an over-limit request is 429 even
    when the payload would otherwise be a 422."""
    headers = {"X-Forwarded-For": "203.0.113.40"}
    with patch("src.agents.universal.UniversalAgent") as MockAgent:
        MockAgent.return_value.run.return_value = {"status": "ok"}
        for _ in range(RATE_LIMIT):
            client.post("/agent/run", json=_payload(), headers=headers)
        blocked = client.post("/agent/run", json=_payload("a" * 4001), headers=headers)
    assert blocked.status_code == 429

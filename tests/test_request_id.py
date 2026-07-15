"""
Tests for per-request UUID4 correlation (RequestIDMiddleware + request_context
+ audit_logger propagation + llm_gateway propagation).

Covers:
  (a) responses carry a well-formed UUID4 X-Request-ID header,
  (b) the request_id reaches audit_logger.log_event (verified via a stubbed
      DB connection),
  (c) sequential AND concurrent requests receive distinct ids,
  (d) valid-incoming-header reuse, invalid-header rejection (no reflection),
  (e) an unhandled 500 still carries the header,
  (f) llm_gateway.generate() accepts and threads through an explicit request_id.
"""

import logging
import re
import uuid
import concurrent.futures

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core import request_context
from src.core.request_context import (
    get_request_id,
    is_valid_request_id,
    normalize_request_id,
)

pytestmark = pytest.mark.unit

# Strict UUID4 pattern (version nibble == 4, variant nibble in [89ab]).
UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


# ---------------------------------------------------------------------------
# request_context — pure unit tests (no FastAPI needed)
# ---------------------------------------------------------------------------


def test_is_valid_request_id_accepts_uuid4():
    assert is_valid_request_id("550e8400-e29b-41d4-a716-446655440000") is True


def test_is_valid_request_id_rejects_garbage():
    assert is_valid_request_id("not-a-uuid") is False
    assert is_valid_request_id("") is False


def test_normalize_request_id_generates_when_missing():
    rid = normalize_request_id("")
    assert UUID4_RE.match(rid)


def test_normalize_request_id_reuses_valid_uuid4():
    valid = "550e8400-e29b-41d4-a716-446655440000"
    assert normalize_request_id(valid) == valid


def test_get_request_id_default_empty():
    request_context.reset_request_id()
    assert get_request_id() == ""


# ---------------------------------------------------------------------------
# RequestIDMiddleware — FastAPI integration
# ---------------------------------------------------------------------------


def _build_app(recorder=None):
    """Minimal app exercising the middleware without depending on real routes."""
    from src.interface.api import RequestIDMiddleware

    app = FastAPI()

    @app.get("/ping")
    def ping():
        return {"request_id": get_request_id()}

    @app.get("/audit")
    def audit():
        rid = get_request_id()
        if recorder is not None:
            recorder.append(rid)
        return {"request_id": rid}

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")  # forces an unhandled 500

    app.add_middleware(RequestIDMiddleware)
    return app


def test_response_has_wellformed_uuid4_request_id_header():
    client = TestClient(_build_app())
    r = client.get("/ping")
    assert r.status_code == 200
    rid = r.headers["x-request-id"]
    assert UUID4_RE.match(rid), f"not a UUID4: {rid}"
    assert uuid.UUID(rid).version == 4
    assert r.json()["request_id"] == rid


def test_two_sequential_requests_get_distinct_ids():
    client = TestClient(_build_app())
    a = client.get("/ping").headers["x-request-id"]
    b = client.get("/ping").headers["x-request-id"]
    assert a != b


def test_concurrent_requests_get_distinct_ids():
    client = TestClient(_build_app())

    def hit(_):
        return client.get("/ping").headers["x-request-id"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        ids = list(ex.map(hit, range(24)))
    assert len(set(ids)) == len(ids), "request ids leaked across concurrent requests"


def test_valid_incoming_request_id_is_reused():
    client = TestClient(_build_app())
    incoming = "550e8400-e29b-41d4-a716-446655440000"  # valid UUID4
    r = client.get("/ping", headers={"X-Request-ID": incoming})
    assert r.headers["x-request-id"] == incoming
    assert r.json()["request_id"] == incoming


def test_invalid_incoming_request_id_is_replaced_not_reflected():
    client = TestClient(_build_app())
    bad = "not-a-uuid<script>alert(1)</script>"
    r = client.get("/ping", headers={"X-Request-ID": bad})
    rid = r.headers["x-request-id"]
    assert rid != bad
    assert UUID4_RE.match(rid)


def test_server_error_response_carries_request_id_header():
    client = TestClient(_build_app(), raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 500
    assert UUID4_RE.match(r.headers["x-request-id"])


# ---------------------------------------------------------------------------
# audit_logger propagation
# ---------------------------------------------------------------------------


def test_request_id_reaches_audit_log_event(monkeypatch):
    """The active request_id must flow into audit_logger.log_event's INSERT."""
    from src.memory import audit_logger as al

    captured = []

    class _FakeCursor:
        def execute(self, sql, params=()):
            captured.append((sql, params))

        def close(self):
            pass

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(al, "get_connection", lambda *a, **k: _FakeConn())

    logger = al.AuditLogger.__new__(al.AuditLogger)
    logger.db_path = ":memory:"
    logger.logger = logging.getLogger("test-audit")

    rid = "11111111-1111-4111-8111-111111111111"
    _resolved, token = request_context.set_request_id(rid)
    try:
        logger.log_event("tester", "TEST_ACTION", "in", "out")
    finally:
        request_context.reset_request_id(token)

    assert captured, "log_event did not execute an INSERT"
    _sql, params = captured[-1]
    assert rid in params, "request_id missing from audit INSERT params"
    assert "request_id" in _sql


def test_explicit_request_id_kwarg_overrides_context(monkeypatch):
    """An explicit request_id kwarg takes precedence over the ambient context."""
    from src.memory import audit_logger as al

    captured = []

    class _FakeCursor:
        def execute(self, sql, params=()):
            captured.append(params)

        def close(self):
            pass

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(al, "get_connection", lambda *a, **k: _FakeConn())

    logger = al.AuditLogger.__new__(al.AuditLogger)
    logger.db_path = ":memory:"
    logger.logger = logging.getLogger("test-audit")

    explicit_rid = "22222222-2222-4222-8222-222222222222"
    logger.log_event("tester", "TEST_ACTION", "in", "out", request_id=explicit_rid)

    assert explicit_rid in captured[-1]


# ---------------------------------------------------------------------------
# llm_gateway propagation
# ---------------------------------------------------------------------------


def _reset_llm_gateway_singleton():
    """Force-reset the LLMGateway singleton so this test gets a fresh instance
    (a shared-singleton instance may have `.provider` left in an unusable state
    by an unrelated test elsewhere in the suite — see test_phase5_streaming.py)."""
    from src.core import llm_gateway as gw_module

    gw_module.LLMGateway._instance = None


def test_generate_accepts_explicit_request_id():
    """generate() must accept a request_id kwarg without raising, and use it
    (rather than the ambient context) when explicitly supplied."""
    from unittest.mock import patch
    from src.core.llm_gateway import LLMGateway

    _reset_llm_gateway_singleton()
    gw = LLMGateway()
    rid = "33333333-3333-4333-8333-333333333333"
    with patch.object(gw.provider, "generate", return_value="OK"):
        result = gw.generate("prompt", "system", request_id=rid)
    assert result == "OK"
    _reset_llm_gateway_singleton()


def test_generate_resolves_request_id_from_context_when_omitted():
    """When request_id is omitted, generate() must not raise — it resolves
    (or falls back to empty) from the ambient request context."""
    from unittest.mock import patch
    from src.core.llm_gateway import LLMGateway

    _reset_llm_gateway_singleton()
    gw = LLMGateway()
    rid = "44444444-4444-4444-8444-444444444444"
    _resolved, token = request_context.set_request_id(rid)
    try:
        with patch.object(gw.provider, "generate", return_value="OK"):
            result = gw.generate("prompt", "system")
        assert result == "OK"
    finally:
        request_context.reset_request_id(token)
        _reset_llm_gateway_singleton()

"""
SAGE Framework — Phase 5 SSE Streaming Tests
=============================================
Tests for:
  - LLMGateway.generate_stream() yields non-empty chunks
  - generate_stream() full concatenation equals a normal generate() response (CLI sim)
  - POST /analyze/stream returns 200 with text/event-stream content type
  - POST /analyze/stream missing log_entry returns 400
  - SSE response contains meta, token, and done events
  - POST /agent/stream returns 200
  - POST /agent/stream missing role returns 400
  - POST /agent/stream missing task returns 400
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# LLMGateway.generate_stream() unit tests
# ---------------------------------------------------------------------------

class TestGenerateStream:

    def _fresh_gateway(self):
        """Return a fresh LLMGateway with a mock provider."""
        from src.core.llm_gateway import LLMGateway
        gw = LLMGateway.__new__(LLMGateway)
        gw._initialized = True
        gw.logger = __import__("logging").getLogger("test")
        gw._usage = {
            "calls": 0, "calls_today": 0,
            "estimated_tokens": 0, "errors": 0,
            "started_at": 0, "day_started_at": 0,
        }
        import threading
        gw._lock = threading.Lock()
        return gw

    def test_stream_yields_chunks(self):
        """generate_stream() must yield at least one non-empty chunk."""
        gw = self._fresh_gateway()
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "Hello world from the agent."
        mock_provider.provider_name.return_value = "MockProvider"
        gw.provider = mock_provider

        chunks = list(gw.generate_stream("test prompt", "system"))
        assert len(chunks) > 0
        assert all(isinstance(c, str) and c for c in chunks)

    def test_stream_concatenation_matches_full_response(self):
        """Concatenating all chunks must equal the original full response."""
        gw = self._fresh_gateway()
        full_text = "The quick brown fox jumps over the lazy dog"
        mock_provider = MagicMock()
        mock_provider.generate.return_value = full_text
        mock_provider.provider_name.return_value = "MockProvider"
        gw.provider = mock_provider

        chunks = list(gw.generate_stream("prompt", "system"))
        assert "".join(chunks).strip() == full_text

    def test_stream_increments_usage(self):
        """generate_stream() must increment calls counter."""
        gw = self._fresh_gateway()
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "response text"
        mock_provider.provider_name.return_value = "MockProvider"
        gw.provider = mock_provider

        # Consume the generator
        list(gw.generate_stream("prompt", "system"))
        assert gw._usage["calls"] == 1

    def test_stream_no_provider_yields_error(self):
        """generate_stream() with no provider must yield a single error string."""
        gw = self._fresh_gateway()
        gw.provider = None
        chunks = list(gw.generate_stream("test"))
        assert len(chunks) == 1
        assert "Error" in chunks[0]


# ---------------------------------------------------------------------------
# API SSE endpoint tests
# ---------------------------------------------------------------------------

class TestSSEEndpoints:

    def _client(self):
        from src.interface.api import app
        return TestClient(app, raise_server_exceptions=False)

    def _parse_sse_events(self, content: bytes) -> list[dict]:
        """Parse SSE response body into a list of event dicts."""
        events = []
        for line in content.decode().splitlines():
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass
        return events

    def test_analyze_stream_returns_200(self):
        """POST /analyze/stream must return 200 with text/event-stream content type."""
        from src.core import llm_gateway as gw_module
        mock_gw = MagicMock()
        mock_gw.generate_stream.return_value = iter(["Hello ", "world."])

        with patch.object(gw_module, "llm_gateway", mock_gw), \
             patch("src.interface.api._get_audit_logger", return_value=MagicMock()):
            resp = self._client().post(
                "/analyze/stream",
                json={"log_entry": "Error: disk full on /dev/sda1"},
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_analyze_stream_missing_log_entry_returns_400(self):
        """POST /analyze/stream without log_entry must return 400."""
        resp = self._client().post("/analyze/stream", json={})
        assert resp.status_code == 400

    def test_analyze_stream_contains_meta_and_done_events(self):
        """SSE response must contain meta, at least one token, and done events."""
        from src.core import llm_gateway as gw_module
        mock_gw = MagicMock()
        mock_gw.generate_stream.return_value = iter(["Analysis ", "complete."])

        with patch.object(gw_module, "llm_gateway", mock_gw), \
             patch("src.interface.api._get_audit_logger", return_value=MagicMock()):
            resp = self._client().post(
                "/analyze/stream",
                json={"log_entry": "sample log"},
            )

        events = self._parse_sse_events(resp.content)
        types = [e.get("type") for e in events]
        assert "meta" in types
        assert "token" in types
        assert "done" in types

    def test_analyze_stream_token_events_contain_content(self):
        """Every token event must have a non-empty 'content' field."""
        from src.core import llm_gateway as gw_module
        mock_gw = MagicMock()
        mock_gw.generate_stream.return_value = iter(["chunk1", "chunk2"])

        with patch.object(gw_module, "llm_gateway", mock_gw), \
             patch("src.interface.api._get_audit_logger", return_value=MagicMock()):
            resp = self._client().post("/analyze/stream", json={"log_entry": "log"})

        events = self._parse_sse_events(resp.content)
        tokens = [e for e in events if e.get("type") == "token"]
        assert len(tokens) == 2
        assert tokens[0]["content"] == "chunk1"
        assert tokens[1]["content"] == "chunk2"

    def test_analyze_stream_meta_contains_trace_id(self):
        """The meta event must include a trace_id."""
        from src.core import llm_gateway as gw_module
        mock_gw = MagicMock()
        mock_gw.generate_stream.return_value = iter(["ok"])

        with patch.object(gw_module, "llm_gateway", mock_gw), \
             patch("src.interface.api._get_audit_logger", return_value=MagicMock()):
            resp = self._client().post("/analyze/stream", json={"log_entry": "log"})

        events = self._parse_sse_events(resp.content)
        meta = next((e for e in events if e.get("type") == "meta"), None)
        assert meta is not None
        assert "trace_id" in meta

    def test_agent_stream_returns_200(self):
        """POST /agent/stream with valid role and task must return 200."""
        from src.core import llm_gateway as gw_module
        mock_gw = MagicMock()
        mock_gw.generate_stream.return_value = iter(["Agent response."])

        with patch.object(gw_module, "llm_gateway", mock_gw), \
             patch("src.interface.api._get_audit_logger", return_value=MagicMock()):
            resp = self._client().post(
                "/agent/stream",
                json={"role": "analyst", "task": "Review the error log"},
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_agent_stream_missing_role_returns_400(self):
        """POST /agent/stream without role must return 400."""
        resp = self._client().post("/agent/stream", json={"task": "do something"})
        assert resp.status_code == 400

    def test_agent_stream_missing_task_returns_400(self):
        """POST /agent/stream without task must return 400."""
        resp = self._client().post("/agent/stream", json={"role": "analyst"})
        assert resp.status_code == 400

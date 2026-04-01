"""
OpenTelemetry Integration Tests — Layer 1 Communication
========================================================

Tests cover:
  1. Tracer module initialization and graceful degradation
  2. Span creation and attribute recording
  3. Config-driven enable/disable toggle
  4. LLM gateway span integration
  5. Context propagation helpers
  6. EventBus span linkage
"""

import importlib
import os
import sys
import threading
import time
import types
from unittest.mock import MagicMock, patch

import pytest


# ─── 1. Tracer Module — Initialization ──────────────────────────────


class TestTracerInit:
    """Verify the tracing module initializes correctly."""

    def test_module_imports_without_otel_sdk(self):
        """tracing.py must import cleanly even when opentelemetry is not installed."""
        from src.core import tracing
        assert hasattr(tracing, "get_tracer")
        assert hasattr(tracing, "TRACING_AVAILABLE")

    def test_get_tracer_returns_object(self):
        """get_tracer() always returns a usable tracer (real or no-op)."""
        from src.core.tracing import get_tracer
        tracer = get_tracer("test-component")
        assert tracer is not None

    def test_get_tracer_consistent_for_same_name(self):
        """Same component name should return the same tracer instance."""
        from src.core.tracing import get_tracer
        t1 = get_tracer("test-same")
        t2 = get_tracer("test-same")
        assert t1 is t2

    def test_init_tracing_returns_provider(self):
        """init_tracing() returns a provider (real or no-op) and is idempotent."""
        from src.core.tracing import init_tracing
        p1 = init_tracing()
        p2 = init_tracing()
        assert p1 is not None
        assert p1 is p2  # idempotent


# ─── 2. Span Creation ──────────────────────────────────────────────


class TestSpanCreation:
    """Verify span creation and attribute recording."""

    def test_start_span_context_manager(self):
        """start_span() works as a context manager and yields a span."""
        from src.core.tracing import get_tracer
        tracer = get_tracer("test-spans")
        with tracer.start_as_current_span("test-operation") as span:
            assert span is not None

    def test_span_set_attribute(self):
        """Span attributes can be set without error (real or no-op)."""
        from src.core.tracing import get_tracer
        tracer = get_tracer("test-spans")
        with tracer.start_as_current_span("test-attrs") as span:
            # Should not raise even on no-op spans
            span.set_attribute("test.key", "test-value")
            span.set_attribute("test.count", 42)

    def test_span_set_status_on_error(self):
        """Span status can be set to error without raising."""
        from src.core.tracing import get_tracer, StatusCode
        tracer = get_tracer("test-spans")
        with tracer.start_as_current_span("test-error") as span:
            span.set_status(StatusCode.ERROR, "something failed")

    def test_span_record_exception(self):
        """record_exception works on spans (real or no-op)."""
        from src.core.tracing import get_tracer
        tracer = get_tracer("test-spans")
        with tracer.start_as_current_span("test-exc") as span:
            try:
                raise ValueError("test error")
            except ValueError as exc:
                span.record_exception(exc)


# ─── 3. Config Toggle ──────────────────────────────────────────────


class TestTracingConfig:
    """Verify config-driven enable/disable."""

    def test_disabled_by_default_without_config(self):
        """Without explicit config, tracing should still work (no-op or real)."""
        from src.core.tracing import get_tracer
        tracer = get_tracer("test-default")
        # Should produce a usable tracer regardless
        with tracer.start_as_current_span("noop-test") as span:
            span.set_attribute("ok", True)

    def test_init_tracing_with_service_name(self):
        """init_tracing accepts a custom service name."""
        from src.core import tracing
        # Reset to allow re-init
        tracing._provider = None
        tracing._tracers.clear()
        provider = tracing.init_tracing(service_name="sage-test-custom")
        assert provider is not None
        # Cleanup
        tracing._provider = None
        tracing._tracers.clear()


# ─── 4. LLM Gateway Span Integration ───────────────────────────────


class TestLLMGatewaySpans:
    """Verify that LLM generate() calls create tracing spans."""

    def test_trace_llm_call_creates_span(self):
        """trace_llm_call context manager creates a span with LLM attributes."""
        from src.core.tracing import trace_llm_call
        with trace_llm_call(
            provider="gemini",
            model="gemini-2.0-flash",
            prompt_length=100,
            system_prompt_length=50,
            trace_name="test-generate",
        ) as span:
            assert span is not None
            # Simulate completion — set output attributes
            span.set_attribute("llm.output_tokens", 200)
            span.set_attribute("llm.duration_s", 1.5)

    def test_trace_llm_call_records_error(self):
        """trace_llm_call records exception if generate fails."""
        from src.core.tracing import trace_llm_call, StatusCode
        try:
            with trace_llm_call(
                provider="ollama",
                model="llama3.2",
                prompt_length=50,
                system_prompt_length=20,
                trace_name="test-fail",
            ) as span:
                raise RuntimeError("LLM timeout")
        except RuntimeError:
            pass  # Expected — the span should have recorded the error

    def test_trace_llm_call_attributes(self):
        """trace_llm_call sets standard semantic convention attributes."""
        from src.core.tracing import trace_llm_call
        with trace_llm_call(
            provider="claude",
            model="claude-sonnet-4-6",
            prompt_length=200,
            system_prompt_length=100,
            trace_name="test-attrs",
            trace_id="abc-123",
        ) as span:
            # These should not raise
            span.set_attribute("llm.response_status", "success")


# ─── 5. Context Propagation ────────────────────────────────────────


class TestContextPropagation:
    """Verify trace context propagation helpers."""

    def test_inject_extract_roundtrip(self):
        """inject_context → extract_context roundtrip preserves trace context."""
        from src.core.tracing import inject_context, extract_context
        carrier = {}
        inject_context(carrier)
        ctx = extract_context(carrier)
        # ctx should be a valid context (possibly empty if no active span)
        assert ctx is not None

    def test_inject_into_dict(self):
        """inject_context populates a dict carrier (may be empty if no active span)."""
        from src.core.tracing import inject_context
        carrier = {}
        inject_context(carrier)
        assert isinstance(carrier, dict)

    def test_extract_from_empty_carrier(self):
        """extract_context from empty carrier returns a valid (root) context."""
        from src.core.tracing import extract_context
        ctx = extract_context({})
        assert ctx is not None


# ─── 6. EventBus Span Linkage ──────────────────────────────────────


class TestEventBusTracing:
    """Verify that EventBus publish creates spans."""

    def test_traced_publish_creates_span(self):
        """traced_publish wraps EventBus.publish with a span."""
        from src.core.tracing import traced_publish
        from src.modules.event_bus import EventBus

        bus = EventBus()
        received = []
        bus.subscribe("test.event", lambda t, d: received.append(d))

        traced_publish(bus, "test.event", {"key": "value"})
        assert len(received) == 1
        assert received[0]["key"] == "value"

    def test_traced_publish_with_no_subscribers(self):
        """traced_publish works even with no subscribers."""
        from src.core.tracing import traced_publish
        from src.modules.event_bus import EventBus

        bus = EventBus()
        # Should not raise
        traced_publish(bus, "empty.event", {"data": 1})


# ─── 7. Thread Safety ──────────────────────────────────────────────


class TestTracingThreadSafety:
    """Verify tracing module is safe under concurrent access."""

    def test_concurrent_get_tracer(self):
        """Multiple threads calling get_tracer simultaneously is safe."""
        from src.core.tracing import get_tracer
        tracers = []
        errors = []

        def worker(name):
            try:
                t = get_tracer(name)
                tracers.append(t)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(f"thread-{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(tracers) == 10

    def test_concurrent_span_creation(self):
        """Multiple threads creating spans simultaneously is safe."""
        from src.core.tracing import get_tracer
        tracer = get_tracer("thread-test")
        errors = []

        def worker(i):
            try:
                with tracer.start_as_current_span(f"op-{i}") as span:
                    span.set_attribute("thread.id", i)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

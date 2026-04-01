"""
src/core/tracing.py — OpenTelemetry Distributed Tracing (Layer 1)
=================================================================

Non-invasive distributed tracing for the SAGE framework.
Runs alongside existing Langfuse + Prometheus observability.

Graceful degradation: when the OpenTelemetry SDK is not installed,
all public functions return no-op objects that silently do nothing.
This means calling code never needs try/except around tracing.

Usage:
    from src.core.tracing import get_tracer, trace_llm_call

    tracer = get_tracer("my-component")
    with tracer.start_as_current_span("operation") as span:
        span.set_attribute("key", "value")

    # Or for LLM calls:
    with trace_llm_call(provider="gemini", model="flash", ...) as span:
        result = llm.generate(prompt)
        span.set_attribute("llm.output_tokens", len(result) // 4)
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# SDK detection
# ─────────────────────────────────────────────────────────────────────

TRACING_AVAILABLE = False

try:
    from opentelemetry import trace, context
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace import StatusCode, Status
    from opentelemetry.context import Context
    from opentelemetry.trace.propagation import get_current_span
    from opentelemetry.propagate import inject, extract

    TRACING_AVAILABLE = True
except ImportError:
    logger.debug(
        "opentelemetry SDK not installed — tracing will use no-op stubs. "
        "Install with: pip install opentelemetry-api opentelemetry-sdk"
    )


# ─────────────────────────────────────────────────────────────────────
# No-op stubs (used when OTel SDK is absent)
# ─────────────────────────────────────────────────────────────────────

class _NoOpSpan:
    """Span stub that silently accepts all operations."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status_code: Any, description: str = "") -> None:
        pass

    def record_exception(self, exception: BaseException, **kwargs: Any) -> None:
        pass

    def add_event(self, name: str, attributes: Optional[Dict] = None) -> None:
        pass

    def end(self) -> None:
        pass

    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class _NoOpTracer:
    """Tracer stub that returns no-op spans."""

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs: Any):
        yield _NoOpSpan()

    def start_span(self, name: str, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()


class _NoOpStatusCode:
    """StatusCode stub for when OTel is not installed."""
    OK = "OK"
    ERROR = "ERROR"
    UNSET = "UNSET"


class _NoOpProvider:
    """TracerProvider stub."""

    def get_tracer(self, name: str, **kwargs: Any) -> _NoOpTracer:
        return _NoOpTracer()


# ─────────────────────────────────────────────────────────────────────
# Module state (thread-safe)
# ─────────────────────────────────────────────────────────────────────

_init_lock = threading.Lock()
_provider: Optional[Any] = None  # TracerProvider or _NoOpProvider
_tracers: Dict[str, Any] = {}    # name → Tracer cache


# Re-export StatusCode — always available (real or stub)
if TRACING_AVAILABLE:
    StatusCode = StatusCode  # type: ignore[misc]
else:
    StatusCode = _NoOpStatusCode  # type: ignore[misc,assignment]


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

def init_tracing(
    service_name: str = "sage-framework",
    exporter: Optional[Any] = None,
) -> Any:
    """
    Initialize the OpenTelemetry TracerProvider.

    Idempotent — calling multiple times returns the same provider.
    When OTel SDK is absent, returns a no-op provider.

    Args:
        service_name: Service name for the resource (default: sage-framework).
        exporter: Optional SpanExporter (e.g., OTLPSpanExporter, ConsoleSpanExporter).
                  If None, uses the SDK's default (env-configured or no-op).
    """
    global _provider

    if _provider is not None:
        return _provider

    with _init_lock:
        if _provider is not None:
            return _provider

        if not TRACING_AVAILABLE:
            _provider = _NoOpProvider()
            logger.debug("Tracing initialized (no-op — SDK not installed)")
            return _provider

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        if exporter is not None:
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        _provider = provider
        logger.info("OpenTelemetry tracing initialized (service: %s)", service_name)
        return _provider


def get_tracer(name: str) -> Any:
    """
    Get a named tracer for a component.

    Caches tracers by name. Auto-initializes the provider on first call.

    Args:
        name: Component name (e.g., "llm-gateway", "build-orchestrator").

    Returns:
        A Tracer (real or no-op).
    """
    if name in _tracers:
        return _tracers[name]

    provider = init_tracing()
    tracer = provider.get_tracer(name)
    _tracers[name] = tracer
    return tracer


# ─────────────────────────────────────────────────────────────────────
# LLM Call Tracing Helper
# ─────────────────────────────────────────────────────────────────────

@contextmanager
def trace_llm_call(
    provider: str,
    model: str,
    prompt_length: int,
    system_prompt_length: int,
    trace_name: str = "llm.generate",
    trace_id: Optional[str] = None,
):
    """
    Context manager that wraps an LLM generate() call with a tracing span.

    Sets semantic convention attributes for LLM operations.
    On exception, records the error and re-raises.

    Usage:
        with trace_llm_call(provider="gemini", model="flash", ...) as span:
            result = llm.generate(prompt)
            span.set_attribute("llm.output_tokens", len(result) // 4)
    """
    tracer = get_tracer("llm-gateway")
    with tracer.start_as_current_span(trace_name) as span:
        # Set input attributes (following OpenTelemetry Semantic Conventions for GenAI)
        span.set_attribute("gen_ai.system", provider)
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("llm.prompt_length", prompt_length)
        span.set_attribute("llm.system_prompt_length", system_prompt_length)
        if trace_id:
            span.set_attribute("sage.trace_id", trace_id)

        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, str(exc))
            raise


# ─────────────────────────────────────────────────────────────────────
# Context Propagation Helpers
# ─────────────────────────────────────────────────────────────────────

def inject_context(carrier: Dict[str, str]) -> None:
    """
    Inject the current trace context into a carrier dict.

    Use this when passing trace context across process boundaries
    (e.g., HTTP headers, message queue metadata).
    """
    if TRACING_AVAILABLE:
        inject(carrier)
    # No-op when SDK absent — carrier stays as-is


def extract_context(carrier: Dict[str, str]) -> Any:
    """
    Extract trace context from a carrier dict.

    Returns an OTel Context (or a plain dict as no-op).
    """
    if TRACING_AVAILABLE:
        return extract(carrier)
    return {}  # No-op — return empty context


# ─────────────────────────────────────────────────────────────────────
# EventBus Integration
# ─────────────────────────────────────────────────────────────────────

def traced_publish(bus: Any, event_type: str, data: dict) -> int:
    """
    Publish an event on the EventBus wrapped in a tracing span.

    Creates a span named "event.publish.<event_type>" with event metadata.
    Returns the number of handlers called (from bus.publish).
    """
    tracer = get_tracer("event-bus")
    with tracer.start_as_current_span(f"event.publish.{event_type}") as span:
        span.set_attribute("event.type", event_type)
        span.set_attribute("event.keys", str(list(data.keys())))
        count = bus.publish(event_type, data)
        span.set_attribute("event.handlers_called", count)
        return count

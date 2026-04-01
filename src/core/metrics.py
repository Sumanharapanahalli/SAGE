"""
src/core/metrics.py — Prometheus metrics for the SAGE Framework
================================================================
Exposes a /metrics endpoint via prometheus_fastapi_instrumentator
plus three custom application metrics:

  sage_jobs_processed_total   Counter  – incremented on every completed job
  sage_jobs_failed_total      Counter  – incremented on every failed job
  sage_queue_depth            Gauge    – current pending-task count (set by caller)

Usage (in api.py lifespan):
    from src.core.metrics import setup_metrics
    setup_metrics(app)

Usage (in any module that processes jobs):
    from src.core.metrics import inc_jobs_processed, inc_jobs_failed, set_queue_depth
    inc_jobs_processed(job_type="build")
    inc_jobs_failed(job_type="build", error_type="timeout")
    set_queue_depth(42, queue_name="default")
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Prometheus client setup (lazy so tests that don't need metrics skip the dep)
# ─────────────────────────────────────────────────────────────────────────────

try:
    from prometheus_client import Counter, Gauge, CollectorRegistry, REGISTRY
    from prometheus_fastapi_instrumentator import Instrumentator

    _METRICS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _METRICS_AVAILABLE = False
    logger.warning(
        "prometheus_client / prometheus_fastapi_instrumentator not installed. "
        "Metrics endpoint will return 503. "
        "Install with: pip install prometheus-client prometheus-fastapi-instrumentator"
    )

# ─────────────────────────────────────────────────────────────────────────────
# Custom application metrics (defined at module level — singletons)
# ─────────────────────────────────────────────────────────────────────────────

if _METRICS_AVAILABLE:
    JOBS_PROCESSED: Counter = Counter(
        name="sage_jobs_processed_total",
        documentation="Total number of SAGE jobs processed successfully.",
        labelnames=["job_type"],
    )

    JOBS_FAILED: Counter = Counter(
        name="sage_jobs_failed_total",
        documentation="Total number of SAGE jobs that failed.",
        labelnames=["job_type", "error_type"],
    )

    QUEUE_DEPTH: Gauge = Gauge(
        name="sage_queue_depth",
        documentation="Current number of tasks waiting in the SAGE queue.",
        labelnames=["queue_name"],
    )

    WORKERS_ACTIVE: Gauge = Gauge(
        name="sage_workers_active",
        documentation="Number of currently active SAGE worker threads.",
        labelnames=["worker_type"],
    )

    BUILD_DURATION_SECONDS: Counter = Counter(
        name="sage_build_duration_seconds_total",
        documentation="Cumulative seconds spent in build tasks.",
        labelnames=["domain", "task_type"],
    )

else:
    # Stub objects so calling code doesn't need try/except everywhere
    class _NoOpCounter:  # type: ignore[no-redef]
        def labels(self, **_: str) -> "_NoOpCounter":
            return self
        def inc(self, amount: float = 1) -> None:
            pass

    class _NoOpGauge:  # type: ignore[no-redef]
        def labels(self, **_: str) -> "_NoOpGauge":
            return self
        def set(self, value: float) -> None:
            pass
        def inc(self, amount: float = 1) -> None:
            pass
        def dec(self, amount: float = 1) -> None:
            pass

    JOBS_PROCESSED = _NoOpCounter()  # type: ignore[assignment]
    JOBS_FAILED = _NoOpCounter()     # type: ignore[assignment]
    QUEUE_DEPTH = _NoOpGauge()       # type: ignore[assignment]
    WORKERS_ACTIVE = _NoOpGauge()    # type: ignore[assignment]
    BUILD_DURATION_SECONDS = _NoOpCounter()  # type: ignore[assignment]


# ─────────────────────────────────────────────────────────────────────────────
# Public helper functions (used by queue manager, build orchestrator, etc.)
# ─────────────────────────────────────────────────────────────────────────────

def inc_jobs_processed(job_type: str = "unknown") -> None:
    """Increment the processed-jobs counter for a given job type."""
    JOBS_PROCESSED.labels(job_type=job_type).inc()


def inc_jobs_failed(
    job_type: str = "unknown",
    error_type: str = "unknown",
) -> None:
    """Increment the failed-jobs counter for a given job type and error category."""
    JOBS_FAILED.labels(job_type=job_type, error_type=error_type).inc()


def set_queue_depth(depth: int, queue_name: str = "default") -> None:
    """Set the current queue depth gauge (should be called periodically by queue manager)."""
    QUEUE_DEPTH.labels(queue_name=queue_name).set(depth)


def set_workers_active(count: int, worker_type: str = "default") -> None:
    """Update the count of active workers (called on worker spawn/teardown)."""
    WORKERS_ACTIVE.labels(worker_type=worker_type).set(count)


def add_build_duration(seconds: float, domain: str = "unknown", task_type: str = "unknown") -> None:
    """Accumulate time spent in build tasks (called after each task completes)."""
    BUILD_DURATION_SECONDS.labels(domain=domain, task_type=task_type).inc(seconds)


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI integration
# ─────────────────────────────────────────────────────────────────────────────

def setup_metrics(app: "FastAPI") -> None:  # type: ignore[name-defined]  # noqa: F821
    """
    Wire Prometheus instrumentation into the FastAPI app.

    Exposes:
      GET /metrics  — Prometheus text format, scraped by Prometheus server

    Instruments all HTTP requests automatically (latency histograms, status
    code counters) via prometheus_fastapi_instrumentator.

    Must be called once, at app startup (in the lifespan context or after
    app = FastAPI(...)).

    Args:
        app: The FastAPI application instance.
    """
    if not _METRICS_AVAILABLE:
        logger.warning("Metrics setup skipped: prometheus packages not installed.")
        _register_fallback_endpoint(app)
        return

    metrics_enabled = os.getenv("ENABLE_METRICS", "true").lower() not in ("0", "false", "no")
    if not metrics_enabled:
        logger.info("Metrics disabled via ENABLE_METRICS env var.")
        return

    try:
        instrumentator = (
            Instrumentator(
                should_group_status_codes=True,
                should_ignore_untemplated=True,
                should_instrument_requests_inprogress=True,
                inprogress_name="sage_http_requests_inprogress",
                inprogress_labels=True,
                excluded_handlers=[
                    "/metrics",
                    "/health",
                    "/health/llm",
                    "/docs",
                    "/openapi.json",
                    "/redoc",
                ],
            )
            .instrument(app)
            .expose(
                app,
                endpoint="/metrics",
                include_in_schema=True,
                tags=["Observability"],
            )
        )
        logger.info("Prometheus metrics endpoint registered at /metrics")
    except Exception as exc:
        logger.error("Failed to set up Prometheus metrics: %s", exc, exc_info=True)
        _register_fallback_endpoint(app)


def _register_fallback_endpoint(app: "FastAPI") -> None:  # type: ignore[name-defined]  # noqa: F821
    """Register a /metrics stub that returns 503 when the real stack is unavailable."""
    from fastapi import Response

    @app.get("/metrics", include_in_schema=True, tags=["Observability"])
    async def metrics_unavailable() -> Response:
        return Response(
            content="# Prometheus metrics unavailable\n",
            status_code=503,
            media_type="text/plain; version=0.0.4",
        )

"""
alert_service.py — AlertService coordinator + FastAPI router

Coordinator pipeline:
  FallEventRequest
    → [idempotency check]
    → FallClassifierAgent.classify()
    → NotificationRouterAgent.notify_all()   (push + SMS + email in parallel)
    → DispatchDeciderAgent.start_grace_period()
    → return 202 with alert_id

Self-cancellation:
  POST /alerts/{alert_id}/cancel
    → DispatchDeciderAgent.cancel()
    → halts emergency dispatch

Every step is written to the SQLite audit trail.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.agents.dispatch_decider import DispatchDeciderAgent, GracePeriodState
from backend.agents.fall_classifier import (
    AlertClassification,
    FallClassifierAgent,
    FallEventInput,
    FallSeverity,
)
from backend.agents.notification_router import CaregiverContact, NotificationRouterAgent

logger = logging.getLogger(__name__)

AUDIT_DB_PATH = ".sage/alert_audit.db"
IDEMPOTENCY_TTL_SECONDS = 3600  # deduplicate for 1 hour


# ── Pydantic I/O models ──────────────────────────────────────────────────────

class FallEventRequest(BaseModel):
    event_id: str = Field(..., description="Device-generated UUID — idempotency key")
    device_id: str
    user_id: str
    event_type: str = Field(
        ...,
        description="fall_detected | sos_button | impact",
    )
    impact_force_g: Optional[float] = None
    button_pressed: bool = False
    accelerometer_data: Optional[dict] = None
    gyroscope_data: Optional[dict] = None
    metadata: dict = Field(default_factory=dict)


class AlertResponse(BaseModel):
    alert_id: str
    event_id: str
    status: str
    severity: str
    confidence: float
    grace_period_seconds: int
    message: str
    is_duplicate: bool = False
    processing_ms: Optional[float] = None


class CancellationRequest(BaseModel):
    cancelled_by: str = Field(
        default="user",
        description="Actor performing the cancellation (user | caregiver | admin)",
    )


class CancellationResponse(BaseModel):
    alert_id: str
    cancelled: bool
    message: str


# ── Idempotency store ────────────────────────────────────────────────────────

class IdempotencyStore:
    """Async-safe in-memory deduplication with TTL eviction."""

    def __init__(self, ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS) -> None:
        # event_id → (alert_id, created_at)
        self._store: dict[str, tuple[str, float]] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

    async def get_or_create(self, event_id: str) -> tuple[str, bool]:
        """
        Returns (alert_id, is_new).
        is_new=True  → first time we see this event_id, a new alert_id was minted.
        is_new=False → duplicate; returns the existing alert_id.
        """
        async with self._lock:
            self._evict_expired()
            if event_id in self._store:
                alert_id, _ = self._store[event_id]
                return alert_id, False
            alert_id = str(uuid.uuid4())
            self._store[event_id] = (alert_id, time.time())
            return alert_id, True

    def _evict_expired(self) -> None:
        cutoff = time.time() - self._ttl
        expired = [k for k, (_, ts) in self._store.items() if ts < cutoff]
        for k in expired:
            del self._store[k]


# ── Audit logger ─────────────────────────────────────────────────────────────

class AuditLogger:
    """
    Append-only SQLite audit trail.
    Each row captures: alert_id, event_id, event name, actor, detail, unix timestamp.
    """

    def __init__(self, db_path: str = AUDIT_DB_PATH) -> None:
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_audit (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id   TEXT    NOT NULL,
                    event_id   TEXT,
                    event      TEXT    NOT NULL,
                    actor      TEXT    NOT NULL DEFAULT 'system',
                    detail     TEXT,
                    timestamp  REAL    NOT NULL,
                    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_alert ON alert_audit(alert_id)"
            )
            conn.commit()

    def log(
        self,
        alert_id: str,
        event: str,
        actor: str = "system",
        detail: str = "",
        event_id: Optional[str] = None,
    ) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT INTO alert_audit "
                    "(alert_id, event_id, event, actor, detail, timestamp) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (alert_id, event_id, event, actor, detail, time.time()),
                )
                conn.commit()
        except Exception as exc:
            logger.error("AuditLogger: write failed — %s", exc)

    def get_trail(self, alert_id: str) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM alert_audit WHERE alert_id = ? ORDER BY timestamp ASC",
                (alert_id,),
            ).fetchall()
        return [dict(r) for r in rows]


# ── Coordinator ──────────────────────────────────────────────────────────────

class AlertService:
    """
    Coordinator agent that owns the full alert lifecycle.

    Agent call order:
      1. FallClassifierAgent  — synchronous, zero I/O → < 1 ms
      2. NotificationRouterAgent — async, parallel channels → ~120 ms (wall clock)
      3. DispatchDeciderAgent — spawns background task, returns immediately

    Total pipeline latency target: < 300 ms (well within 3 s SLA).
    """

    def __init__(self) -> None:
        self.classifier = FallClassifierAgent()
        self.router = NotificationRouterAgent()
        self.decider = DispatchDeciderAgent(
            dispatch_callback=self._on_emergency_dispatch
        )
        self.idempotency = IdempotencyStore()
        self.audit = AuditLogger()

    # ── public actions ───────────────────────────────────────────────────────

    async def process_fall_event(self, req: FallEventRequest) -> AlertResponse:
        wall_start = time.monotonic()

        # ── step 1: idempotency ───────────────────────────────────────────
        alert_id, is_new = await self.idempotency.get_or_create(req.event_id)
        if not is_new:
            logger.info(
                "AlertService: DUPLICATE event_id=%s → alert_id=%s",
                req.event_id,
                alert_id,
            )
            return AlertResponse(
                alert_id=alert_id,
                event_id=req.event_id,
                status="duplicate",
                severity="unknown",
                confidence=0.0,
                grace_period_seconds=0,
                message="Duplicate event — already being processed.",
                is_duplicate=True,
            )

        self.audit.log(
            alert_id=alert_id,
            event_id=req.event_id,
            event="RECEIVED",
            actor=f"device:{req.device_id}",
            detail=(
                f"event_type={req.event_type} "
                f"impact={req.impact_force_g}g "
                f"sos={req.button_pressed}"
            ),
        )

        # ── step 2: fall classifier agent ─────────────────────────────────
        fall_input = FallEventInput(
            event_id=req.event_id,
            device_id=req.device_id,
            user_id=req.user_id,
            event_type=req.event_type,
            accelerometer_data=req.accelerometer_data,
            gyroscope_data=req.gyroscope_data,
            impact_force_g=req.impact_force_g,
            button_pressed=req.button_pressed,
            metadata=req.metadata,
        )
        classification: AlertClassification = self.classifier.classify(fall_input)

        self.audit.log(
            alert_id=alert_id,
            event_id=req.event_id,
            event="CLASSIFIED",
            actor="agent:fall_classifier",
            detail=(
                f"severity={classification.severity} "
                f"confidence={classification.confidence:.3f} "
                f"grace={classification.grace_period_seconds}s "
                f"reason={classification.reasoning}"
            ),
        )

        if classification.severity == FallSeverity.FALSE_ALARM:
            self.audit.log(
                alert_id=alert_id,
                event_id=req.event_id,
                event="DISMISSED",
                actor="agent:fall_classifier",
                detail="False alarm — no notifications sent",
            )
            return AlertResponse(
                alert_id=alert_id,
                event_id=req.event_id,
                status="dismissed",
                severity=classification.severity,
                confidence=classification.confidence,
                grace_period_seconds=0,
                message="Event classified as false alarm. No action taken.",
                processing_ms=round((time.monotonic() - wall_start) * 1000, 1),
            )

        # ── step 3: notification router agent — parallel channels ─────────
        caregivers = await self._get_caregivers(req.user_id)
        routing = await self.router.notify_all(alert_id, classification, caregivers)

        self.audit.log(
            alert_id=alert_id,
            event_id=req.event_id,
            event="NOTIFIED",
            actor="agent:notification_router",
            detail=(
                f"channels={routing.channels_used} "
                f"primary_sent={routing.primary_notification_sent} "
                f"latency_ms={routing.notification_latency_ms:.0f}"
            ),
        )

        # ── step 4: dispatch decider — start grace period (background) ────
        self.decider.start_grace_period(
            alert_id=alert_id,
            user_id=req.user_id,
            severity=classification.severity,
            timeout_seconds=classification.grace_period_seconds,
            audit_callback=self.audit.log,
        )

        self.audit.log(
            alert_id=alert_id,
            event_id=req.event_id,
            event="GRACE_PERIOD_STARTED",
            actor="agent:dispatch_decider",
            detail=f"timeout={classification.grace_period_seconds}s",
        )

        processing_ms = round((time.monotonic() - wall_start) * 1000, 1)
        logger.info(
            "AlertService: event=%s alert=%s severity=%s processed in %.0f ms",
            req.event_id,
            alert_id,
            classification.severity,
            processing_ms,
        )

        return AlertResponse(
            alert_id=alert_id,
            event_id=req.event_id,
            status="active",
            severity=classification.severity,
            confidence=classification.confidence,
            grace_period_seconds=classification.grace_period_seconds,
            message=(
                f"Alert active. Cancel within {classification.grace_period_seconds}s "
                "to halt emergency dispatch."
            ),
            processing_ms=processing_ms,
        )

    async def cancel_alert(
        self, alert_id: str, cancelled_by: str
    ) -> CancellationResponse:
        self.audit.log(
            alert_id=alert_id,
            event="CANCELLATION_REQUESTED",
            actor=cancelled_by,
            detail="Self-cancellation initiated",
        )

        success = await self.decider.cancel(alert_id, cancelled_by=cancelled_by)

        if success:
            self.audit.log(
                alert_id=alert_id,
                event="CANCELLED",
                actor=cancelled_by,
                detail="Grace period cancelled — emergency dispatch halted",
            )
            return CancellationResponse(
                alert_id=alert_id,
                cancelled=True,
                message="Alert cancelled. Emergency dispatch halted.",
            )

        state = self.decider.get_state(alert_id)
        if state and state.status.value == "DISPATCHED":
            reason = "emergency already dispatched — too late to cancel"
        elif not state:
            reason = "alert not found"
        else:
            reason = f"alert in status {state.status}"

        return CancellationResponse(
            alert_id=alert_id,
            cancelled=False,
            message=f"Cancellation failed: {reason}.",
        )

    async def get_audit_trail(self, alert_id: str) -> list[dict]:
        return self.audit.get_trail(alert_id)

    def get_grace_period_status(self, alert_id: str) -> Optional[dict]:
        state = self.decider.get_state(alert_id)
        if not state:
            return None
        remaining = self.decider.get_remaining_seconds(alert_id)
        return {
            "alert_id": state.alert_id,
            "status": state.status,
            "severity": state.severity,
            "timeout_seconds": state.timeout_seconds,
            "remaining_seconds": remaining,
            "started_at": state.started_at,
            "cancelled_at": state.cancelled_at,
            "dispatched_at": state.dispatched_at,
            "cancelled_by": state.cancelled_by,
        }

    # ── private helpers ───────────────────────────────────────────────────────

    async def _get_caregivers(self, user_id: str) -> list[CaregiverContact]:
        """
        Load caregiver contacts for a user.
        Production: query your user-profile service / database.
        """
        # Stub: one primary caregiver per user
        return [
            CaregiverContact(
                caregiver_id=f"cg_{user_id}_primary",
                name="Primary Caregiver",
                fcm_token=f"fcm_token_{user_id}_primary_placeholder",
                phone_number="+15550001234",
                email=f"caregiver_{user_id}@example.com",
                priority=1,
            )
        ]

    async def _on_emergency_dispatch(self, state: GracePeriodState) -> None:
        """
        Called by DispatchDeciderAgent when grace period expires without cancellation.
        Production: call 911/emergency API, alert facility on-call, create incident.
        """
        self.audit.log(
            alert_id=state.alert_id,
            event="EMERGENCY_DISPATCHED",
            actor="agent:dispatch_decider",
            detail=(
                f"Emergency services called for user={state.user_id} "
                f"severity={state.severity}"
            ),
        )
        logger.critical(
            "EMERGENCY: dispatching for alert=%s user=%s severity=%s",
            state.alert_id,
            state.user_id,
            state.severity,
        )


# ── Dependency injection ──────────────────────────────────────────────────────

_alert_service: Optional[AlertService] = None


def get_alert_service() -> AlertService:
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertService()
    return _alert_service


# ── FastAPI router ────────────────────────────────────────────────────────────

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post(
    "/fall-event",
    response_model=AlertResponse,
    status_code=202,
    summary="Receive fall event from device",
)
async def receive_fall_event(
    req: FallEventRequest,
    service: AlertService = Depends(get_alert_service),
) -> AlertResponse:
    """
    Accept a fall/SOS event from a wearable device.

    - Deduplicates by `event_id` (idempotency key)
    - Classifies severity via FallClassifierAgent
    - Notifies caregivers via push + SMS + email in parallel
    - Starts grace period for self-cancellation
    - Logs every step to audit trail
    """
    return await service.process_fall_event(req)


@router.post(
    "/{alert_id}/cancel",
    response_model=CancellationResponse,
    summary="Cancel active alert within grace period",
)
async def cancel_alert(
    alert_id: str,
    req: CancellationRequest,
    service: AlertService = Depends(get_alert_service),
) -> CancellationResponse:
    """
    Cancel an active alert before the grace period expires.
    Halts emergency services dispatch.
    Returns 200 whether or not cancellation succeeded (see `cancelled` field).
    """
    return await service.cancel_alert(alert_id, cancelled_by=req.cancelled_by)


@router.get(
    "/{alert_id}/status",
    summary="Get grace period status for an alert",
)
async def get_alert_status(
    alert_id: str,
    service: AlertService = Depends(get_alert_service),
) -> dict:
    """Current grace period state and remaining seconds for self-cancellation."""
    status = service.get_grace_period_status(alert_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id!r} not found")
    return status


@router.get(
    "/{alert_id}/audit",
    summary="Retrieve full audit trail for an alert",
)
async def get_audit_trail(
    alert_id: str,
    service: AlertService = Depends(get_alert_service),
) -> dict:
    """Return every lifecycle event recorded for this alert, oldest first."""
    trail = await service.get_audit_trail(alert_id)
    return {"alert_id": alert_id, "count": len(trail), "events": trail}


# ── FastAPI app factory ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    logger.info("Alert processing service started")
    yield
    logger.info("Alert processing service stopping")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Fall Alert Processing Service",
        description=(
            "Multi-agent coordinator: FallClassifier → NotificationRouter → DispatchDecider. "
            "Handles fall events with idempotency, parallel notifications, and 60s grace period."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.services.alert_service:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )

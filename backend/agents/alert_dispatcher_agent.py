"""
agents/alert_dispatcher_agent.py — AlertDispatcherAgent

Specialist agent that manages the alert lifecycle:
  - Receive fall classification → dispatch notifications → start grace period
  - Acknowledge / dismiss / escalate alerts
  - Persist alert state with full audit trail

Wraps AlertService (coordinator + channels) and adds ReAct tracing.
"""
from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from backend.agents.fall_classifier import AlertClassification, FallSeverity
from backend.agents.notification_router import CaregiverContact, NotificationRouterAgent
from backend.services.gps_store import get_gps_store

logger = logging.getLogger(__name__)

_DB_PATH = Path(".sage/alert_state.db")


@dataclass
class AlertDispatchResult:
    alert_id: str
    event_id: str
    status: str
    severity: str
    channels_notified: list[str]
    grace_period_seconds: int
    dispatch_id: Optional[str]
    react_trace: list[str]
    processing_ms: float


class AlertDispatcherAgent:
    """
    Dispatches caregiver notifications and manages alert state transitions.

    ReAct loop (per alert):
      THOUGHT: assess classification + determine dispatch strategy
      ACTION:  notify caregivers (push/SMS/email in parallel)
      OBSERVATION: record outcomes, update alert state
    """

    def __init__(
        self,
        router: Optional[NotificationRouterAgent] = None,
    ) -> None:
        self._router = router or NotificationRouterAgent()
        self._db = _DB_PATH
        self._init_db()

    def _init_db(self) -> None:
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_state (
                    alert_id         TEXT PRIMARY KEY,
                    event_id         TEXT NOT NULL,
                    device_id        TEXT NOT NULL,
                    user_id          TEXT NOT NULL,
                    severity         TEXT NOT NULL,
                    status           TEXT NOT NULL DEFAULT 'pending',
                    confidence       REAL,
                    grace_seconds    INTEGER,
                    dispatch_id      TEXT,
                    channels         TEXT,
                    acknowledged_by  TEXT,
                    dismissed_by     TEXT,
                    escalated_by     TEXT,
                    note             TEXT,
                    created_at       REAL NOT NULL,
                    updated_at       REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_alert_user ON alert_state(user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_alert_device ON alert_state(device_id)"
            )
            conn.commit()

    async def dispatch(
        self,
        alert_id: str,
        classification: AlertClassification,
        caregivers: list[CaregiverContact],
        device_id: str,
    ) -> AlertDispatchResult:
        start = time.monotonic()
        trace: list[str] = []

        # ── THOUGHT ──────────────────────────────────────────────────────────
        thought = (
            f"THOUGHT: Processing alert_id={alert_id} event_id={classification.event_id} "
            f"severity={classification.severity} confidence={classification.confidence:.2f}. "
            f"{len(caregivers)} caregiver(s) to notify. "
            f"Grace period: {classification.grace_period_seconds}s."
        )
        trace.append(thought)
        logger.info("AlertDispatcherAgent | %s", thought)

        # Persist initial state
        now = time.time()
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO alert_state "
                "(alert_id, event_id, device_id, user_id, severity, status, "
                "confidence, grace_seconds, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)",
                (
                    alert_id,
                    classification.event_id,
                    device_id,
                    classification.user_id,
                    classification.severity,
                    classification.confidence,
                    classification.grace_period_seconds,
                    now,
                    now,
                ),
            )
            conn.commit()

        # ── ACTION: notify caregivers ─────────────────────────────────────────
        action = (
            f"ACTION: Dispatching notifications via push/SMS/email to "
            f"{len(caregivers)} caregiver(s) for severity={classification.severity}"
        )
        trace.append(action)
        logger.info("AlertDispatcherAgent | %s", action)

        routing = await self._router.notify_all(alert_id, classification, caregivers)

        # ── OBSERVATION ───────────────────────────────────────────────────────
        successes = [r.channel for r in routing.results if r.success]
        failures = [r.channel for r in routing.results if not r.success]
        obs = (
            f"OBSERVATION: Notifications dispatched in {routing.notification_latency_ms:.0f}ms. "
            f"Channels succeeded: {successes}. "
            f"Channels failed: {failures}. "
            f"Primary sent: {routing.primary_notification_sent}."
        )
        trace.append(obs)
        logger.info("AlertDispatcherAgent | %s", obs)

        # Update state with channels used
        channels_str = ",".join(successes)
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                "UPDATE alert_state SET channels = ?, updated_at = ? WHERE alert_id = ?",
                (channels_str, time.time(), alert_id),
            )
            conn.commit()

        processing_ms = round((time.monotonic() - start) * 1000, 1)
        return AlertDispatchResult(
            alert_id=alert_id,
            event_id=classification.event_id,
            status="active",
            severity=classification.severity,
            channels_notified=successes,
            grace_period_seconds=classification.grace_period_seconds,
            dispatch_id=None,
            react_trace=trace,
            processing_ms=processing_ms,
        )

    def acknowledge(self, alert_id: str, acknowledged_by: str, note: str = "") -> bool:
        with sqlite3.connect(self._db) as conn:
            cur = conn.execute(
                "UPDATE alert_state SET status='acknowledged', acknowledged_by=?, "
                "note=?, updated_at=? WHERE alert_id=? AND status='active'",
                (acknowledged_by, note, time.time(), alert_id),
            )
            conn.commit()
        return cur.rowcount > 0

    def dismiss(self, alert_id: str, dismissed_by: str, reason: str) -> bool:
        status = "false_positive" if reason == "false_positive" else "dismissed"
        with sqlite3.connect(self._db) as conn:
            cur = conn.execute(
                "UPDATE alert_state SET status=?, dismissed_by=?, note=?, updated_at=? "
                "WHERE alert_id=? AND status NOT IN ('resolved', 'dismissed', 'false_positive')",
                (status, dismissed_by, reason, time.time(), alert_id),
            )
            conn.commit()
        return cur.rowcount > 0

    def escalate(self, alert_id: str, escalated_by: str, reason: str) -> bool:
        with sqlite3.connect(self._db) as conn:
            cur = conn.execute(
                "UPDATE alert_state SET status='escalated', escalated_by=?, note=?, "
                "updated_at=? WHERE alert_id=? AND status IN ('active', 'acknowledged')",
                (escalated_by, reason, time.time(), alert_id),
            )
            conn.commit()
        return cur.rowcount > 0

    def set_dispatch_id(self, alert_id: str, dispatch_id: str) -> None:
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                "UPDATE alert_state SET dispatch_id=?, status='escalated', updated_at=? "
                "WHERE alert_id=?",
                (dispatch_id, time.time(), alert_id),
            )
            conn.commit()

    def get_alert(self, alert_id: str) -> Optional[dict]:
        with sqlite3.connect(self._db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM alert_state WHERE alert_id = ?", (alert_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_alerts(
        self,
        device_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        query = "SELECT * FROM alert_state WHERE 1=1"
        params: list = []
        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += f" ORDER BY created_at DESC LIMIT {limit}"

        with sqlite3.connect(self._db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


_dispatcher: Optional[AlertDispatcherAgent] = None


def get_alert_dispatcher_agent() -> AlertDispatcherAgent:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = AlertDispatcherAgent()
    return _dispatcher

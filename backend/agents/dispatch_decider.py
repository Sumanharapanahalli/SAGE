"""
dispatch_decider.py — DispatchDeciderAgent

Manages the grace period between alert notification and emergency dispatch.
Each active alert runs as an independent asyncio background task.
Cancellation cancels the asyncio.Task — no polling, no threading.

State machine:
  ACTIVE → CANCELLED  (cancel() called within grace period)
  ACTIVE → DISPATCHED (grace period expires without cancellation)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

AuditCallback = Callable[..., None]
DispatchCallback = Callable[["GracePeriodState"], Awaitable[None]]


class GracePeriodStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    DISPATCHED = "DISPATCHED"


@dataclass
class GracePeriodState:
    alert_id: str
    user_id: str
    severity: str
    timeout_seconds: int
    started_at: float
    status: GracePeriodStatus = GracePeriodStatus.ACTIVE
    cancelled_at: Optional[float] = None
    dispatched_at: Optional[float] = None
    cancelled_by: Optional[str] = None


class DispatchDeciderAgent:
    """
    Orchestrates the 60-second (configurable) grace window.

    Usage:
        decider.start_grace_period(alert_id, user_id, severity, timeout_seconds=60)
        await decider.cancel(alert_id, cancelled_by="user")   # halts dispatch
    """

    def __init__(self, dispatch_callback: Optional[DispatchCallback] = None) -> None:
        self._states: dict[str, GracePeriodState] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._dispatch_callback: DispatchCallback = (
            dispatch_callback or self._default_dispatch
        )

    # ── public API ───────────────────────────────────────────────────────────

    def start_grace_period(
        self,
        alert_id: str,
        user_id: str,
        severity: str,
        timeout_seconds: int,
        audit_callback: Optional[AuditCallback] = None,
    ) -> GracePeriodState:
        """
        Start grace period. Non-blocking — spawns an asyncio background task.
        Safe to call from a sync context (the task runs in the event loop).
        """
        if alert_id in self._states:
            existing = self._states[alert_id]
            logger.warning(
                "DispatchDecider: grace period already active for %s (status=%s)",
                alert_id,
                existing.status,
            )
            return existing

        state = GracePeriodState(
            alert_id=alert_id,
            user_id=user_id,
            severity=severity,
            timeout_seconds=timeout_seconds,
            started_at=time.time(),
        )
        self._states[alert_id] = state

        task = asyncio.create_task(
            self._grace_period_task(alert_id, timeout_seconds, audit_callback),
            name=f"grace_{alert_id}",
        )
        self._tasks[alert_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(alert_id, None))

        logger.info(
            "DispatchDecider: grace period STARTED alert=%s user=%s severity=%s timeout=%ds",
            alert_id,
            user_id,
            severity,
            timeout_seconds,
        )
        return state

    async def cancel(self, alert_id: str, cancelled_by: str = "user") -> bool:
        """
        Cancel the grace period and halt emergency dispatch.

        Returns:
            True  — cancellation successful
            False — alert not found or already dispatched
        """
        state = self._states.get(alert_id)
        if not state:
            logger.warning(
                "DispatchDecider: cancel called for unknown alert %s", alert_id
            )
            return False

        if state.status != GracePeriodStatus.ACTIVE:
            logger.warning(
                "DispatchDecider: alert %s already in terminal state %s — cannot cancel",
                alert_id,
                state.status,
            )
            return False

        task = self._tasks.get(alert_id)
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass  # expected — task was cancelled

        state.status = GracePeriodStatus.CANCELLED
        state.cancelled_at = time.time()
        state.cancelled_by = cancelled_by

        elapsed = state.cancelled_at - state.started_at
        logger.info(
            "DispatchDecider: alert %s CANCELLED by=%s elapsed=%.1fs",
            alert_id,
            cancelled_by,
            elapsed,
        )
        return True

    def get_state(self, alert_id: str) -> Optional[GracePeriodState]:
        return self._states.get(alert_id)

    def get_remaining_seconds(self, alert_id: str) -> Optional[float]:
        state = self._states.get(alert_id)
        if not state or state.status != GracePeriodStatus.ACTIVE:
            return None
        elapsed = time.time() - state.started_at
        return max(0.0, state.timeout_seconds - elapsed)

    # ── internal ─────────────────────────────────────────────────────────────

    async def _grace_period_task(
        self,
        alert_id: str,
        timeout_seconds: int,
        audit_callback: Optional[AuditCallback],
    ) -> None:
        try:
            await asyncio.sleep(timeout_seconds)
        except asyncio.CancelledError:
            logger.debug("DispatchDecider: task cancelled for alert %s", alert_id)
            return

        state = self._states.get(alert_id)
        if not state or state.status != GracePeriodStatus.ACTIVE:
            return  # already handled (e.g. external cancellation race)

        state.status = GracePeriodStatus.DISPATCHED
        state.dispatched_at = time.time()

        logger.critical(
            "DispatchDecider: grace period EXPIRED alert=%s user=%s — dispatching emergency",
            alert_id,
            state.user_id,
        )

        if audit_callback:
            try:
                audit_callback(
                    alert_id=alert_id,
                    event="EMERGENCY_DISPATCHED",
                    actor="agent:dispatch_decider",
                    detail=(
                        f"Grace period expired after {timeout_seconds}s — "
                        "emergency services dispatched"
                    ),
                )
            except Exception as exc:
                logger.error(
                    "DispatchDecider: audit callback failed during dispatch: %s", exc
                )

        try:
            await self._dispatch_callback(state)
        except Exception as exc:
            logger.error("DispatchDecider: dispatch callback raised: %s", exc)

    async def _default_dispatch(self, state: GracePeriodState) -> None:
        """
        Default emergency dispatch handler.
        Replace with real integration: emergency services API, facility alert, etc.
        """
        logger.critical(
            "EMERGENCY DISPATCH: alert=%s user=%s severity=%s — contacting emergency services",
            state.alert_id,
            state.user_id,
            state.severity,
        )
        # TODO: integrate with 911/emergency dispatch API
        # TODO: notify facility on-call staff
        # TODO: record GPS coordinates in incident ticket

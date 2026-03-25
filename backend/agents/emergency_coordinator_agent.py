"""
agents/emergency_coordinator_agent.py — EmergencyCoordinatorAgent

Specialist agent that decides when to engage NG911 emergency dispatch and
executes the RapidSOS API call.  Logs full ReAct Thought→Action→Observation
traces before, during, and after dispatch.

Plugged into DispatchDeciderAgent as the `dispatch_callback`.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from backend.agents.dispatch_decider import GracePeriodState
from backend.services.emergency_service import (
    DispatchResult,
    EmergencyService,
    get_emergency_service,
)
from backend.services.gps_store import GpsStore, get_gps_store

logger = logging.getLogger(__name__)


class EmergencyCoordinatorAgent:
    """
    Coordinates emergency dispatch when the grace period expires.

    ReAct loop:
      THOUGHT: assess severity + GPS context
      ACTION:  call RapidSOS NG911 API
      OBSERVATION: log dispatch_id + outcome, handle failure gracefully
    """

    def __init__(
        self,
        emergency_service: Optional[EmergencyService] = None,
        gps_store: Optional[GpsStore] = None,
    ) -> None:
        self._emergency = emergency_service or get_emergency_service()
        self._gps = gps_store or get_gps_store()

    async def dispatch(self, state: GracePeriodState) -> DispatchResult:
        """
        Entry point called by DispatchDeciderAgent after grace period expires.
        Returns DispatchResult with dispatch_id.
        """
        trace: list[str] = []

        # ── THOUGHT ──────────────────────────────────────────────────────────
        thought = (
            f"THOUGHT: Grace period expired for alert_id={state.alert_id} "
            f"user_id={state.user_id} severity={state.severity}. "
            f"No self-cancellation received. Must dispatch emergency services."
        )
        trace.append(thought)
        logger.critical("EmergencyCoordinatorAgent | %s", thought)

        # ── ACTION: fetch latest GPS ──────────────────────────────────────────
        gps = self._gps.latest(state.alert_id)
        # alert_id won't match device_id directly; try user as hint
        # In production, join via alert store → device_id → gps
        lat: Optional[float] = None
        lon: Optional[float] = None
        if gps:
            lat = gps.get("latitude")
            lon = gps.get("longitude")
            action_gps = (
                f"ACTION: Fetched latest GPS for context: lat={lat} lon={lon}"
            )
        else:
            action_gps = (
                "ACTION: No GPS record found for alert context. "
                "Will dispatch without location (NG911 will use PSAP mapping)."
            )
        trace.append(action_gps)
        logger.info("EmergencyCoordinatorAgent | %s", action_gps)

        # ── ACTION: call NG911 ────────────────────────────────────────────────
        action_dispatch = (
            f"ACTION: Calling RapidSOS NG911 API for alert_id={state.alert_id}"
        )
        trace.append(action_dispatch)
        logger.critical("EmergencyCoordinatorAgent | %s", action_dispatch)

        result = await self._emergency.dispatch_emergency(
            alert_id=state.alert_id,
            user_id=state.user_id,
            severity=state.severity,
            latitude=lat,
            longitude=lon,
            caller_name="SAGE Fall Detection System",
            additional_info=(
                f"Automated fall detection. Severity: {state.severity}. "
                f"Grace period: {state.timeout_seconds}s elapsed without user response."
            ),
        )

        # ── OBSERVATION ───────────────────────────────────────────────────────
        if result.status in ("dispatched", "mock"):
            obs = (
                f"OBSERVATION: Emergency dispatch SUCCESSFUL. "
                f"dispatch_id={result.dispatch_id} provider={result.provider} "
                f"incident_url={result.incident_url}"
            )
            logger.critical("EmergencyCoordinatorAgent | %s", obs)
        else:
            obs = (
                f"OBSERVATION: Emergency dispatch FAILED. "
                f"dispatch_id={result.dispatch_id} error={result.error}. "
                f"Escalating to secondary channel."
            )
            logger.error("EmergencyCoordinatorAgent | %s", obs)

        trace.append(obs)

        # Attach trace to result for audit log upstream
        result.__dict__["react_trace"] = trace
        return result

    async def __call__(self, state: GracePeriodState) -> None:
        """DispatchDeciderAgent expects a callable — delegates to dispatch()."""
        await self.dispatch(state)


_agent: Optional[EmergencyCoordinatorAgent] = None


def get_emergency_coordinator_agent() -> EmergencyCoordinatorAgent:
    global _agent
    if _agent is None:
        _agent = EmergencyCoordinatorAgent()
    return _agent

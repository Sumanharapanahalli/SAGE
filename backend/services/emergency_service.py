"""
services/emergency_service.py — RapidSOS NG911 emergency dispatch integration.

RapidSOS ERG (Emergency Response Gateway) API flow:
  1. POST /oauth2/token  → obtain bearer token
  2. POST /emergency/call  → create an emergency call record
  3. Returns dispatch_id which is logged to audit trail

In mock mode (rapidsos_mock_mode=True), returns a realistic fake dispatch_id.
Set rapidsos_mock_mode=False with real credentials for production.
"""
from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

_DB_PATH = Path(".sage/dispatches.db")


@dataclass
class DispatchResult:
    dispatch_id: str
    provider: str  # "rapidsos" | "mock"
    status: str  # "dispatched" | "failed" | "mock"
    incident_url: Optional[str]
    location_lat: Optional[float]
    location_lon: Optional[float]
    dispatched_at: float
    error: Optional[str] = None


class EmergencyService:
    """
    Sends NG911 emergency dispatch request to RapidSOS and logs the result.
    """

    # RapidSOS API v2 endpoints
    _TOKEN_URL = "/oauth2/token"
    _EMERGENCY_URL = "/emergency/call"

    def __init__(self) -> None:
        self._settings = get_settings()
        self._db = _DB_PATH
        self._init_db()
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _init_db(self) -> None:
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dispatches (
                    dispatch_id   TEXT PRIMARY KEY,
                    alert_id      TEXT NOT NULL,
                    user_id       TEXT NOT NULL,
                    provider      TEXT NOT NULL,
                    status        TEXT NOT NULL,
                    location_lat  REAL,
                    location_lon  REAL,
                    incident_url  TEXT,
                    error         TEXT,
                    dispatched_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_dispatches_alert ON dispatches(alert_id)"
            )
            conn.commit()

    async def dispatch_emergency(
        self,
        alert_id: str,
        user_id: str,
        severity: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        caller_name: str = "Fall Detection System",
        additional_info: str = "",
    ) -> DispatchResult:
        """
        Dispatch emergency services via RapidSOS NG911.
        Logs dispatch_id to SQLite for audit.
        """
        logger.critical(
            "EmergencyService: DISPATCHING for alert=%s user=%s severity=%s lat=%s lon=%s",
            alert_id,
            user_id,
            severity,
            latitude,
            longitude,
        )

        settings = self._settings
        if settings.rapidsos_mock_mode:
            result = self._mock_dispatch(
                alert_id, user_id, severity, latitude, longitude
            )
        else:
            result = await self._rapidsos_dispatch(
                alert_id,
                user_id,
                severity,
                latitude,
                longitude,
                caller_name,
                additional_info,
            )

        self._persist(alert_id, user_id, result)
        return result

    def _mock_dispatch(
        self,
        alert_id: str,
        user_id: str,
        severity: str,
        lat: Optional[float],
        lon: Optional[float],
    ) -> DispatchResult:
        dispatch_id = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
        logger.info(
            "EmergencyService: MOCK dispatch_id=%s alert=%s", dispatch_id, alert_id
        )
        return DispatchResult(
            dispatch_id=dispatch_id,
            provider="mock",
            status="mock",
            incident_url=None,
            location_lat=lat,
            location_lon=lon,
            dispatched_at=time.time(),
        )

    async def _rapidsos_dispatch(
        self,
        alert_id: str,
        user_id: str,
        severity: str,
        lat: Optional[float],
        lon: Optional[float],
        caller_name: str,
        additional_info: str,
    ) -> DispatchResult:
        """
        Real RapidSOS ERG API call.
        Docs: https://developer.rapidsos.com/docs
        """
        settings = self._settings
        try:
            token = await self._get_token()
        except Exception as exc:
            logger.error("EmergencyService: token fetch failed: %s", exc)
            return DispatchResult(
                dispatch_id=f"FAILED-{uuid.uuid4().hex[:8]}",
                provider="rapidsos",
                status="failed",
                incident_url=None,
                location_lat=lat,
                location_lon=lon,
                dispatched_at=time.time(),
                error=str(exc),
            )

        payload: dict = {
            "externalIncidentId": alert_id,
            "additionalData": {
                "callerName": caller_name,
                "severity": severity,
                "userId": user_id,
                "fallDetectionSystem": "SAGE-FallGuard",
                "note": additional_info,
            },
        }
        if lat is not None and lon is not None:
            payload["location"] = {
                "type": "Point",
                "coordinates": [lon, lat],  # GeoJSON: [lon, lat]
                "accuracy": 15,
                "floor": None,
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{settings.rapidsos_base_url}{self._EMERGENCY_URL}",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "X-Agency-ID": settings.rapidsos_agency_id,
                    },
                )
                resp.raise_for_status()
                body = resp.json()

            dispatch_id = body.get("id") or body.get("callId") or str(uuid.uuid4())
            incident_url = body.get("incidentUrl")
            logger.info(
                "EmergencyService: RapidSOS dispatched dispatch_id=%s alert=%s",
                dispatch_id,
                alert_id,
            )
            return DispatchResult(
                dispatch_id=dispatch_id,
                provider="rapidsos",
                status="dispatched",
                incident_url=incident_url,
                location_lat=lat,
                location_lon=lon,
                dispatched_at=time.time(),
            )

        except httpx.HTTPStatusError as exc:
            logger.error(
                "EmergencyService: RapidSOS HTTP %d — %s",
                exc.response.status_code,
                exc.response.text[:200],
            )
            return DispatchResult(
                dispatch_id=f"FAILED-{uuid.uuid4().hex[:8]}",
                provider="rapidsos",
                status="failed",
                incident_url=None,
                location_lat=lat,
                location_lon=lon,
                dispatched_at=time.time(),
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except Exception as exc:
            logger.error("EmergencyService: unexpected error: %s", exc)
            return DispatchResult(
                dispatch_id=f"FAILED-{uuid.uuid4().hex[:8]}",
                provider="rapidsos",
                status="failed",
                incident_url=None,
                location_lat=lat,
                location_lon=lon,
                dispatched_at=time.time(),
                error=str(exc),
            )

    async def _get_token(self) -> str:
        """Obtain or refresh OAuth2 token from RapidSOS."""
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        settings = self._settings
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.rapidsos_base_url}{self._TOKEN_URL}",
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.rapidsos_client_id,
                    "client_secret": settings.rapidsos_client_secret,
                },
            )
            resp.raise_for_status()
            body = resp.json()

        self._token = body["access_token"]
        self._token_expires_at = time.time() + body.get("expires_in", 3600)
        logger.debug("EmergencyService: RapidSOS token refreshed")
        return self._token

    def _persist(self, alert_id: str, user_id: str, result: DispatchResult) -> None:
        try:
            with sqlite3.connect(self._db) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO dispatches "
                    "(dispatch_id, alert_id, user_id, provider, status, "
                    "location_lat, location_lon, incident_url, error, dispatched_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        result.dispatch_id,
                        alert_id,
                        user_id,
                        result.provider,
                        result.status,
                        result.location_lat,
                        result.location_lon,
                        result.incident_url,
                        result.error,
                        result.dispatched_at,
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.error("EmergencyService: failed to persist dispatch: %s", exc)

    def get_dispatch(self, dispatch_id: str) -> Optional[dict]:
        with sqlite3.connect(self._db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM dispatches WHERE dispatch_id = ?", (dispatch_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_dispatches_for_alert(self, alert_id: str) -> list[dict]:
        with sqlite3.connect(self._db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM dispatches WHERE alert_id = ? ORDER BY dispatched_at DESC",
                (alert_id,),
            ).fetchall()
        return [dict(r) for r in rows]


_emergency_service: Optional[EmergencyService] = None


def get_emergency_service() -> EmergencyService:
    global _emergency_service
    if _emergency_service is None:
        _emergency_service = EmergencyService()
    return _emergency_service

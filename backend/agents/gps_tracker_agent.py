"""
agents/gps_tracker_agent.py — GpsTrackerAgent

Specialist agent responsible for:
  - Validating and normalising incoming GPS telemetry
  - Persisting to gps_store
  - Detecting geofence violations (configurable safe zone per device)
  - Returning enriched GPS context for fall events

ReAct trace is logged via standard logging at INFO level.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.services.gps_store import GpsRecord, GpsStore, get_gps_store

logger = logging.getLogger(__name__)


@dataclass
class GpsTrackResult:
    device_id: str
    latitude: float
    longitude: float
    accuracy_meters: Optional[float]
    altitude_meters: Optional[float]
    timestamp: float
    is_geofence_violation: bool
    geofence_distance_m: Optional[float]
    react_trace: list[str]


class GpsTrackerAgent:
    """
    Validates, stores, and enriches GPS telemetry.

    ReAct loop:
      THOUGHT: assess incoming payload
      ACTION:  validate coords + persist
      OBSERVATION: check geofence, return enriched result
    """

    # Earth radius metres (Haversine)
    _EARTH_R = 6_371_000.0

    def __init__(self, gps_store: Optional[GpsStore] = None) -> None:
        self._store = gps_store or get_gps_store()
        # device_id → (lat, lon, radius_m) — per-device safe zones
        self._safe_zones: dict[str, tuple[float, float, float]] = {}

    def set_safe_zone(
        self, device_id: str, lat: float, lon: float, radius_m: float
    ) -> None:
        """Configure a geofence safe zone for a device."""
        self._safe_zones[device_id] = (lat, lon, radius_m)

    def process(
        self,
        device_id: str,
        latitude: float,
        longitude: float,
        accuracy_meters: Optional[float] = None,
        altitude_meters: Optional[float] = None,
        timestamp: Optional[float] = None,
        source: str = "device",
    ) -> GpsTrackResult:
        trace: list[str] = []
        ts = timestamp or time.time()

        # ── THOUGHT ──────────────────────────────────────────────────────────
        thought = (
            f"THOUGHT: Received GPS update for device={device_id} "
            f"lat={latitude:.6f} lon={longitude:.6f} acc={accuracy_meters}m. "
            f"Need to validate, persist, and check geofence."
        )
        trace.append(thought)
        logger.info("GpsTrackerAgent | %s", thought)

        # ── ACTION: validate ──────────────────────────────────────────────────
        action = f"ACTION: Validating coordinates: lat={latitude}, lon={longitude}"
        trace.append(action)
        logger.info("GpsTrackerAgent | %s", action)

        if not (-90 <= latitude <= 90):
            raise ValueError(f"Invalid latitude: {latitude}")
        if not (-180 <= longitude <= 180):
            raise ValueError(f"Invalid longitude: {longitude}")

        # ── ACTION: persist ───────────────────────────────────────────────────
        self._store.record(
            GpsRecord(
                device_id=device_id,
                latitude=latitude,
                longitude=longitude,
                accuracy_meters=accuracy_meters,
                altitude_meters=altitude_meters,
                timestamp=ts,
                source=source,
            )
        )
        persist_action = f"ACTION: GPS persisted to store for device={device_id}"
        trace.append(persist_action)
        logger.info("GpsTrackerAgent | %s", persist_action)

        # ── OBSERVATION: geofence check ───────────────────────────────────────
        is_violation = False
        geofence_dist: Optional[float] = None

        if device_id in self._safe_zones:
            zone_lat, zone_lon, zone_radius = self._safe_zones[device_id]
            dist = self._haversine(latitude, longitude, zone_lat, zone_lon)
            geofence_dist = dist
            is_violation = dist > zone_radius
            obs = (
                f"OBSERVATION: Geofence check — distance={dist:.1f}m "
                f"radius={zone_radius}m violation={is_violation}"
            )
        else:
            obs = f"OBSERVATION: No geofence configured for device={device_id}. GPS stored OK."

        trace.append(obs)
        logger.info("GpsTrackerAgent | %s", obs)

        if is_violation:
            logger.warning(
                "GpsTrackerAgent: GEOFENCE VIOLATION device=%s dist=%.1fm",
                device_id,
                geofence_dist,
            )

        return GpsTrackResult(
            device_id=device_id,
            latitude=latitude,
            longitude=longitude,
            accuracy_meters=accuracy_meters,
            altitude_meters=altitude_meters,
            timestamp=ts,
            is_geofence_violation=is_violation,
            geofence_distance_m=geofence_dist,
            react_trace=trace,
        )

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Return distance in metres between two GPS points."""
        import math
        r = 6_371_000.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))


_gps_agent: Optional[GpsTrackerAgent] = None


def get_gps_tracker_agent() -> GpsTrackerAgent:
    global _gps_agent
    if _gps_agent is None:
        _gps_agent = GpsTrackerAgent()
    return _gps_agent

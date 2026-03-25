"""
services/gps_store.py — Lightweight GPS history persistence (SQLite).

Production replacement: use the gps_history table in PostgreSQL (defined in
db/models.py) with the pgcrypto-encrypted lat/lon columns.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DB_PATH = Path(".sage/gps.db")


@dataclass
class GpsRecord:
    device_id: str
    latitude: float
    longitude: float
    timestamp: float  # unix epoch
    accuracy_meters: Optional[float] = None
    altitude_meters: Optional[float] = None
    source: str = "device"


class GpsStore:
    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self._db = db_path
        self._init_db()

    def _init_db(self) -> None:
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS gps_history (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id        TEXT NOT NULL,
                    latitude         REAL NOT NULL,
                    longitude        REAL NOT NULL,
                    accuracy_meters  REAL,
                    altitude_meters  REAL,
                    source           TEXT NOT NULL DEFAULT 'device',
                    recorded_at      REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_gps_device_ts ON gps_history(device_id, recorded_at)"
            )
            conn.commit()

    def record(self, rec: GpsRecord) -> None:
        with sqlite3.connect(self._db) as conn:
            conn.execute(
                "INSERT INTO gps_history "
                "(device_id, latitude, longitude, accuracy_meters, altitude_meters, source, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    rec.device_id,
                    rec.latitude,
                    rec.longitude,
                    rec.accuracy_meters,
                    rec.altitude_meters,
                    rec.source,
                    rec.timestamp,
                ),
            )
            conn.commit()

    def latest(self, device_id: str) -> Optional[dict]:
        with sqlite3.connect(self._db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM gps_history WHERE device_id = ? ORDER BY recorded_at DESC LIMIT 1",
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

    def history(
        self,
        device_id: str,
        from_ts: Optional[float] = None,
        to_ts: Optional[float] = None,
        limit: int = 500,
    ) -> list[dict]:
        query = "SELECT * FROM gps_history WHERE device_id = ?"
        params: list = [device_id]
        if from_ts:
            query += " AND recorded_at >= ?"
            params.append(from_ts)
        if to_ts:
            query += " AND recorded_at <= ?"
            params.append(to_ts)
        query += f" ORDER BY recorded_at DESC LIMIT {limit}"

        with sqlite3.connect(self._db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


_gps_store: Optional[GpsStore] = None


def get_gps_store() -> GpsStore:
    global _gps_store
    if _gps_store is None:
        _gps_store = GpsStore()
    return _gps_store

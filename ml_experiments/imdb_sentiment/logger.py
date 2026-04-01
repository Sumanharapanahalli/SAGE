"""
Lightweight experiment logger backed by SQLite.

Logs every run with:
  - timestamp, run_id
  - hyperparameters (JSON)
  - metrics (JSON)
  - dataset stats
  - any free-form notes

No external tracking dependency (MLflow / W&B) — zero infra required.
Swap the backend by subclassing ``ExperimentLogger``.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ExperimentLogger:
    """
    Append-only experiment log stored in a local SQLite file.

    Usage
    -----
    >>> log = ExperimentLogger("experiments.db")
    >>> run_id = log.start_run(params={"C": 1.0, "max_features": 50_000})
    >>> log.end_run(run_id, metrics={"accuracy": 0.89, "f1_macro": 0.89})
    """

    _CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS runs (
            run_id      TEXT PRIMARY KEY,
            started_at  TEXT NOT NULL,
            ended_at    TEXT,
            params      TEXT,   -- JSON
            metrics     TEXT,   -- JSON
            dataset     TEXT,   -- JSON
            notes       TEXT
        )
    """

    def __init__(self, db_path: str | Path = "experiments.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute(self._CREATE_TABLE)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_run(
        self,
        params: dict[str, Any] | None = None,
        dataset: dict[str, Any] | None = None,
        notes: str = "",
    ) -> str:
        """Insert a new run row and return its run_id."""
        run_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO runs (run_id, started_at, params, dataset, notes) VALUES (?,?,?,?,?)",
            (run_id, now, json.dumps(params or {}), json.dumps(dataset or {}), notes),
        )
        self._conn.commit()
        logger.info("Run %s started | params=%s", run_id, params)
        return run_id

    def end_run(self, run_id: str, metrics: dict[str, Any]) -> None:
        """Update the run row with metrics and end timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE runs SET ended_at=?, metrics=? WHERE run_id=?",
            (now, json.dumps(metrics), run_id),
        )
        self._conn.commit()
        logger.info("Run %s finished | metrics=%s", run_id, metrics)

    def list_runs(self, last_n: int = 20) -> list[dict[str, Any]]:
        """Return the ``last_n`` runs as dicts, newest first."""
        cur = self._conn.execute(
            "SELECT run_id, started_at, ended_at, params, metrics, dataset, notes "
            "FROM runs ORDER BY started_at DESC LIMIT ?",
            (last_n,),
        )
        cols = [d[0] for d in cur.description]
        rows = []
        for row in cur.fetchall():
            rec = dict(zip(cols, row))
            for field in ("params", "metrics", "dataset"):
                if rec[field]:
                    rec[field] = json.loads(rec[field])
            rows.append(rec)
        return rows

    def best_run(self, metric: str = "f1_macro") -> dict[str, Any] | None:
        """Return the run with the highest value for ``metric``."""
        runs = [r for r in self.list_runs(last_n=1000) if r.get("metrics")]
        if not runs:
            return None
        return max(runs, key=lambda r: r["metrics"].get(metric, float("-inf")))

    def close(self) -> None:
        self._conn.close()

"""
Lightweight experiment tracker — SQLite + JSON Lines.

Swap this module for MLflow / W&B / Comet without touching train_ddp.py:
  - Replace start_run / log_epoch / finish_run with SDK calls
  - Same function signatures, no other changes needed

Only called from rank 0.
"""

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_DB_PATH   = Path("logs/experiments.db")
_JSONL_PATH = Path("logs/experiments.jsonl")


# ── Internal DB helpers ──────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_DB_PATH, check_same_thread=False)
    con.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id       TEXT PRIMARY KEY,
            started_at   REAL,
            finished_at  REAL,
            world_size   INTEGER,
            scaled_lr    REAL,
            config       TEXT,
            final_metrics TEXT,
            status       TEXT DEFAULT 'running'
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS epoch_metrics (
            run_id     TEXT,
            epoch      INTEGER,
            metrics    TEXT,
            logged_at  REAL,
            PRIMARY KEY (run_id, epoch)
        )
    """)
    con.commit()
    return con


# ── Public API ───────────────────────────────────────────────────────────────

def start_run(
    config: Dict[str, Any],
    world_size: int,
    scaled_lr: float,
) -> str:
    """Create a new experiment run. Returns an 8-char run_id."""
    run_id = str(uuid.uuid4())[:8]
    con = _conn()
    con.execute(
        "INSERT INTO runs(run_id, started_at, world_size, scaled_lr, config) VALUES (?,?,?,?,?)",
        (run_id, time.time(), world_size, scaled_lr, json.dumps(config)),
    )
    con.commit()
    con.close()
    logger.info(
        f"Experiment started — run_id={run_id}  world_size={world_size}  scaled_lr={scaled_lr:.6f}"
    )
    return run_id


def log_epoch(run_id: str, epoch: int, metrics: Dict[str, Any]) -> None:
    """Persist per-epoch metrics to SQLite and append to JSONL."""
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO epoch_metrics(run_id, epoch, metrics, logged_at) VALUES (?,?,?,?)",
        (run_id, epoch, json.dumps(metrics), time.time()),
    )
    con.commit()
    con.close()

    _JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _JSONL_PATH.open("a") as f:
        f.write(json.dumps({"run_id": run_id, "epoch": epoch, **metrics}) + "\n")


def finish_run(run_id: str, final_metrics: Dict[str, Any]) -> None:
    """Mark run as finished and store final test metrics."""
    con = _conn()
    con.execute(
        "UPDATE runs SET finished_at=?, final_metrics=?, status='finished' WHERE run_id=?",
        (time.time(), json.dumps(final_metrics), run_id),
    )
    con.commit()
    con.close()
    logger.info(f"Run {run_id} finished — {final_metrics}")

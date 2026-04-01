"""
Lightweight JSON-based experiment tracker
==========================================
Appends one JSON record per run to a .jsonl file.
Structure mirrors MLflow / W&B for straightforward migration.

Usage
-----
    exp = ExperimentLogger("boston_linreg")
    run_id = exp.start_run(params={"lr": 0.1, "schedule": "cosine"})
    exp.log_metrics(run_id, {"rmse": 4.2, "r2": 0.74})
    record = exp.end_run(run_id)
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_EXPERIMENTS_DIR = Path("experiments")


class ExperimentLogger:
    """
    Parameters
    ----------
    experiment_name : str
        Logical grouping label (becomes the filename prefix).
    log_dir : Path
        Directory where .jsonl files are written.
    """

    def __init__(
        self,
        experiment_name: str,
        log_dir: Path = _EXPERIMENTS_DIR,
    ) -> None:
        self.experiment_name = experiment_name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.runs_file = self.log_dir / f"{experiment_name}_runs.jsonl"
        self._active: Dict[str, Dict[str, Any]] = {}

    # ── Run lifecycle ─────────────────────────────────────────────────────────

    def start_run(
        self,
        params: Dict[str, Any],
        tags: Optional[Dict[str, str]] = None,
    ) -> str:
        """Create a run record and return its 8-char hex run_id."""
        ts = time.time()
        fingerprint = f"{self.experiment_name}-{ts}-{json.dumps(params, sort_keys=True)}"
        run_id = hashlib.md5(fingerprint.encode()).hexdigest()[:8]
        self._active[run_id] = {
            "run_id": run_id,
            "experiment": self.experiment_name,
            "status": "running",
            "start_time": ts,
            "end_time": None,
            "duration_s": None,
            "params": dict(params),
            "metrics": {},
            "tags": tags or {},
        }
        logger.info("[%s] run=%s started | params=%s", self.experiment_name, run_id, params)
        return run_id

    def log_metrics(self, run_id: str, metrics: Dict[str, float]) -> None:
        """Merge metrics into an active run (values rounded to 6 d.p.)."""
        self._require_active(run_id)
        self._active[run_id]["metrics"].update(
            {k: round(float(v), 6) for k, v in metrics.items()}
        )

    def log_param(self, run_id: str, key: str, value: Any) -> None:
        """Add / overwrite a single param on an active run."""
        self._require_active(run_id)
        self._active[run_id]["params"][key] = value

    def end_run(self, run_id: str, status: str = "completed") -> Dict[str, Any]:
        """
        Finalise a run and flush it to disk.

        Returns the completed run record.
        """
        self._require_active(run_id)
        record = self._active.pop(run_id)
        record["status"] = status
        record["end_time"] = time.time()
        record["duration_s"] = round(record["end_time"] - record["start_time"], 3)

        with open(self.runs_file, "a") as fh:
            fh.write(json.dumps(record) + "\n")

        logger.info(
            "[%s] run=%s %s | metrics=%s | %.1fs",
            self.experiment_name,
            run_id,
            status,
            record["metrics"],
            record["duration_s"],
        )
        return record

    # ── Query ─────────────────────────────────────────────────────────────────

    def load_all_runs(self) -> List[Dict[str, Any]]:
        """Return all completed runs from disk."""
        if not self.runs_file.exists():
            return []
        runs = []
        with open(self.runs_file) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        runs.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning("Skipping malformed line in %s", self.runs_file)
        return runs

    def best_run(self, metric: str, mode: str = "min") -> Optional[Dict[str, Any]]:
        """
        Return the run with the best value of ``metric``.

        Parameters
        ----------
        metric : str  — key inside run["metrics"]
        mode   : "min" (lower is better) | "max" (higher is better)
        """
        candidates = [
            r for r in self.load_all_runs() if metric in r.get("metrics", {})
        ]
        if not candidates:
            return None
        fn = min if mode == "min" else max
        return fn(candidates, key=lambda r: r["metrics"][metric])

    def summary_table(self) -> str:
        """Return a human-readable summary of all runs."""
        runs = self.load_all_runs()
        if not runs:
            return "No completed runs found."
        lines = [
            f"{'run_id':>10}  {'val_rmse':>9}  {'test_rmse':>10}  "
            f"{'test_r2':>8}  {'schedule':>12}  {'lr':>8}  {'iters':>6}"
        ]
        lines.append("-" * 72)
        for r in sorted(runs, key=lambda x: x["metrics"].get("val_rmse", 9999)):
            m = r["metrics"]
            p = r["params"]
            lines.append(
                f"{r['run_id']:>10}  "
                f"{m.get('val_rmse', float('nan')):>9.4f}  "
                f"{m.get('test_rmse', float('nan')):>10.4f}  "
                f"{m.get('test_r2', float('nan')):>8.4f}  "
                f"{p.get('schedule', '?'):>12}  "
                f"{p.get('lr', float('nan')):>8.4f}  "
                f"{m.get('n_iter', '?'):>6}"
            )
        return "\n".join(lines)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _require_active(self, run_id: str) -> None:
        if run_id not in self._active:
            raise KeyError(f"run_id {run_id!r} not found in active runs.")

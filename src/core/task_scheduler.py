"""
SAGE Task Scheduler — submits YAML-declared tasks on a cron-like schedule.

Reads `scheduled` entries from tasks.yaml via project_config.
Each entry: {task_type, cron, payload, priority (optional)}.

Cron support is simplified: interval is derived from the first non-wildcard
field (minutes field). For full cron parsing, install `croniter` — the
scheduler uses it if available, otherwise falls back to minute-interval parsing.
"""

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


def _parse_interval_seconds(cron: str) -> int:
    """
    Simplified cron to interval conversion.
    '*/5 * * * *' -> 300s, '0 * * * *' -> 3600s, '* * * * *' -> 60s.
    Uses croniter if available for full cron support.
    """
    try:
        from croniter import croniter
        now = time.time()
        it = croniter(cron, now)
        next1 = it.get_next(float)
        next2 = it.get_next(float)
        return max(int(next2 - next1), 60)
    except ImportError:
        pass

    parts = cron.strip().split()
    if len(parts) < 1:
        return 3600
    minute = parts[0]
    if minute.startswith("*/"):
        try:
            return int(minute[2:]) * 60
        except ValueError:
            pass
    if minute == "0":
        return 3600
    return 60


class TaskScheduler:
    """Runs scheduled tasks declared in tasks.yaml."""

    def __init__(self, queue_manager=None, project_config=None):
        self._qm = queue_manager
        self._pc = project_config
        self._last_run: dict = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.logger = logging.getLogger("TaskScheduler")

    def _key(self, entry: dict) -> str:
        return f"{entry['task_type']}_{entry['cron']}"

    def _tick(self) -> None:
        """Check all scheduled tasks and submit any that are due."""
        try:
            tasks = self._pc.get_scheduled_tasks()
        except Exception as exc:
            self.logger.warning("Could not load scheduled tasks: %s", exc)
            return

        now = time.time()
        for entry in tasks:
            task_type = entry.get("task_type", "")
            cron      = entry.get("cron", "* * * * *")
            payload   = entry.get("payload", {})
            priority  = entry.get("priority", 8)
            key       = self._key(entry)

            interval = _parse_interval_seconds(cron)
            last     = self._last_run.get(key, 0.0)

            if now - last >= interval:
                try:
                    self._qm.submit(task_type, payload, priority=priority, source="scheduler")
                    self._last_run[key] = now
                    self.logger.info("Scheduled task submitted: %s (cron: %s)", task_type, cron)
                except Exception as exc:
                    self.logger.error("Scheduled task submit failed for %s: %s", task_type, exc)

    def start(self) -> None:
        """Start the scheduler background thread."""
        if self._running:
            return
        self._running = True

        def _loop():
            while self._running:
                self._tick()
                time.sleep(30)  # check every 30 s

        self._thread = threading.Thread(target=_loop, name="TaskScheduler", daemon=True)
        self._thread.start()
        self.logger.info("Task scheduler started.")

    def stop(self) -> None:
        self._running = False

    def status(self) -> dict:
        return {
            "running": self._running,
            "scheduled_count": len(self._last_run),
            "next_check_in_seconds": 30,
        }

"""
continuous_tester.py — Background service that runs the test suite on a schedule.
Surfaces failures via audit log. Part of SAGE's parallel AI test agent capability.
"""
import subprocess
import threading
import time
import logging
import os
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_SAGE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PYTEST = os.path.join(_SAGE_ROOT, ".venv", "bin", "pytest")
_TESTS_DIR = os.path.join(_SAGE_ROOT, "tests")


def _parse_pytest_output(output: str) -> dict:
    """Parse pytest summary line e.g. '383 passed, 1 skipped in 10.80s'"""
    passed = failed = skipped = errors = 0
    duration = 0.0

    m = re.search(r"(\d+) passed", output)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+) failed", output)
    if m:
        failed = int(m.group(1))
    m = re.search(r"(\d+) skipped", output)
    if m:
        skipped = int(m.group(1))
    m = re.search(r"(\d+) error", output)
    if m:
        errors = int(m.group(1))
    m = re.search(r"in ([\d.]+)s", output)
    if m:
        duration = float(m.group(1))

    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
        "duration_sec": duration,
        "status": "passed" if failed == 0 and errors == 0 else "failed",
    }


class ContinuousTester:
    def __init__(self, interval_seconds: int = 300):
        self.interval = interval_seconds
        self._thread: threading.Thread | None = None
        self._running = False
        self._last_result: dict | None = None
        self._last_run: str | None = None
        self._next_run: str | None = None
        self._total_runs = 0
        self._failure_streak = 0
        self._lock = threading.Lock()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ContinuousTester")
        self._thread.start()
        logger.info("ContinuousTester started (interval=%ds)", self.interval)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("ContinuousTester stopped")

    def _loop(self):
        while self._running:
            self._do_run("all")
            next_ts = time.time() + self.interval
            self._next_run = datetime.fromtimestamp(next_ts, tz=timezone.utc).isoformat()
            elapsed = 0
            while elapsed < self.interval and self._running:
                time.sleep(1)
                elapsed += 1

    def _do_run(self, suite: str):
        result = self._run_pytest(suite)
        with self._lock:
            self._last_result = result
            self._last_run = datetime.now(timezone.utc).isoformat()
            self._total_runs += 1
            if result.get("failed", 0) > 0 or result.get("errors", 0) > 0:
                self._failure_streak += 1
                self._notify_failure(result)
            else:
                self._failure_streak = 0

    def run_now(self, suite: str = "all") -> dict:
        """Run tests synchronously. Returns result immediately."""
        result = self._run_pytest(suite)
        with self._lock:
            self._last_result = result
            self._last_run = datetime.now(timezone.utc).isoformat()
            self._total_runs += 1
            if result.get("failed", 0) > 0 or result.get("errors", 0) > 0:
                self._failure_streak += 1
            else:
                self._failure_streak = 0
        return result

    def _run_pytest(self, suite: str) -> dict:
        pytest_bin = _PYTEST if os.path.exists(_PYTEST) else "pytest"
        if suite in ("all", "framework"):
            test_path = _TESTS_DIR
        else:
            candidate = os.path.join(_TESTS_DIR, f"test_{suite}.py")
            test_path = candidate if os.path.exists(candidate) else _TESTS_DIR

        cmd = [pytest_bin, test_path, "-q", "--tb=short", "--no-header"]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=_SAGE_ROOT,
                timeout=120,
            )
            output = proc.stdout + proc.stderr
            result = _parse_pytest_output(output)
            result["output"] = output[-2000:] if len(output) > 2000 else output
            result["suite"] = suite
            return result
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "passed": 0, "failed": 0, "errors": 1,
                    "duration_sec": 120, "suite": suite, "output": "Test run timed out"}
        except Exception as e:
            return {"status": "error", "passed": 0, "failed": 0, "errors": 1,
                    "duration_sec": 0, "suite": suite, "output": str(e)}

    def _notify_failure(self, result: dict):
        """Log test failures to the audit trail."""
        try:
            from src.memory.audit_logger import audit_logger
            audit_logger.log_event(
                actor="ContinuousTester",
                action_type="TEST_FAILURE",
                input_context=f"suite={result.get('suite', 'all')} failed={result.get('failed', 0)}",
                output_content=result.get("output", "")[-500:],
                metadata={"passed": result.get("passed"), "failed": result.get("failed"),
                          "failure_streak": self._failure_streak},
            )
        except Exception as e:
            logger.warning("Could not log test failure to audit: %s", e)

    def get_status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "last_run": self._last_run,
                "last_result": self._last_result,
                "next_run": self._next_run,
                "total_runs": self._total_runs,
                "failure_streak": self._failure_streak,
                "interval_seconds": self.interval,
            }


continuous_tester = ContinuousTester(interval_seconds=300)

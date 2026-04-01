"""
hil_controller.py — HIL UART test harness controller.

Wraps pyserial to provide a clean synchronous API for the pytest test suite.
All commands follow the firmware's ASCII protocol:
    Request : <CMD> [ARGS...]\n
    Response: OK <data>\n | ERR <code> <message>\n

Usage:
    from hil_controller import HILController
    hil = HILController(port="/dev/ttyACM0", baud=115200, timeout=5.0)
    hil.connect()
    hil.ping()
    ...
    hil.disconnect()

IEC 62304 traceability: STS-HIL-001 (communication layer)
"""

from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

import serial  # pyserial

log = logging.getLogger(__name__)


@dataclass
class HILResponse:
    """Parsed firmware response."""
    ok: bool
    raw: str
    error_code: Optional[int] = None
    error_msg: Optional[str] = None
    data: Dict[str, str] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        val = self.data.get(key)
        return int(val) if val is not None else default


@dataclass
class ReplayResult:
    detected: bool
    latency_ms: int
    raw: str


class HILController:
    """
    Serial controller for the nRF5340 HIL test interface.

    Thread safety: not thread-safe — use one instance per test worker.
    """

    _KV_RE = re.compile(r'(\w+)=(-?\w+)')

    def __init__(
        self,
        port: str = "/dev/ttyACM0",
        baud: int = 115200,
        timeout: float = 5.0,
        boot_wait: float = 2.0,
    ) -> None:
        self._port = port
        self._baud = baud
        self._timeout = timeout
        self._boot_wait = boot_wait
        self._ser: Optional[serial.Serial] = None

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Open serial port and wait for firmware boot banner."""
        self._ser = serial.Serial(
            port=self._port,
            baudrate=self._baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self._timeout,
            write_timeout=self._timeout,
        )
        log.info("HIL: opened %s @ %d baud", self._port, self._baud)
        # Drain boot banner
        time.sleep(self._boot_wait)
        self._ser.reset_input_buffer()
        # Verify comms
        self.ping()

    def disconnect(self) -> None:
        """Close serial port."""
        if self._ser and self._ser.is_open:
            self._ser.close()
            log.info("HIL: disconnected from %s", self._port)

    def __enter__(self) -> "HILController":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()

    # ── Low-level I/O ─────────────────────────────────────────────────────────

    def _send(self, cmd: str) -> None:
        assert self._ser is not None, "Not connected"
        line = cmd.rstrip("\n") + "\n"
        self._ser.write(line.encode("ascii"))
        log.debug("HIL TX: %r", line.rstrip())

    def _recv(self) -> str:
        assert self._ser is not None, "Not connected"
        raw = self._ser.readline()
        if not raw:
            raise TimeoutError(f"HIL: no response within {self._timeout}s")
        line = raw.decode("ascii", errors="replace").strip()
        log.debug("HIL RX: %r", line)
        return line

    def _cmd(self, cmd: str) -> HILResponse:
        self._send(cmd)
        raw = self._recv()
        return self._parse(raw)

    @classmethod
    def _parse(cls, raw: str) -> HILResponse:
        """Parse 'OK key=val key=val' or 'ERR code msg' into HILResponse."""
        if raw.startswith("OK"):
            kv = dict(cls._KV_RE.findall(raw))
            return HILResponse(ok=True, raw=raw, data=kv)
        if raw.startswith("ERR"):
            parts = raw.split(None, 2)
            code = int(parts[1]) if len(parts) > 1 else -1
            msg  = parts[2] if len(parts) > 2 else ""
            return HILResponse(ok=False, raw=raw, error_code=code, error_msg=msg)
        # Unexpected format
        return HILResponse(ok=False, raw=raw, error_code=-1,
                           error_msg=f"Unexpected: {raw!r}")

    # ── Command API ───────────────────────────────────────────────────────────

    def ping(self) -> None:
        resp = self._cmd("PING")
        assert resp.ok, f"PING failed: {resp.raw}"

    def version(self) -> Dict[str, str]:
        resp = self._cmd("VERSION")
        assert resp.ok, f"VERSION failed: {resp.raw}"
        return resp.data

    def get_state(self) -> Dict[str, int]:
        resp = self._cmd("GET_STATE")
        assert resp.ok, f"GET_STATE failed: {resp.raw}"
        return {k: int(v) for k, v in resp.data.items()}

    def get_power_state(self) -> Dict[str, Any]:
        resp = self._cmd("GET_POWER_STATE")
        assert resp.ok, f"GET_POWER_STATE failed: {resp.raw}"
        return {"power": resp.data.get("POWER", "UNKNOWN"),
                "tick_ms": resp.get_int("TICK")}

    def force_sleep(self) -> None:
        resp = self._cmd("FORCE_SLEEP")
        assert resp.ok, f"FORCE_SLEEP failed: {resp.raw}"

    def force_active(self) -> None:
        resp = self._cmd("FORCE_ACTIVE")
        assert resp.ok, f"FORCE_ACTIVE failed: {resp.raw}"

    def get_current_markers(self) -> Dict[str, int]:
        resp = self._cmd("GET_CURRENT_MARKERS")
        assert resp.ok, f"GET_CURRENT_MARKERS failed: {resp.raw}"
        return {"before_ms": resp.get_int("BEFORE"),
                "after_ms":  resp.get_int("AFTER")}

    def reset_fall_count(self) -> None:
        resp = self._cmd("RESET_FALL_COUNT")
        assert resp.ok, f"RESET_FALL_COUNT failed: {resp.raw}"

    def get_fall_count(self) -> int:
        resp = self._cmd("GET_FALL_COUNT")
        assert resp.ok, f"GET_FALL_COUNT failed: {resp.raw}"
        return resp.get_int("COUNT")

    def inject_accel(self, ax: int, ay: int, az: int,
                     gx: int = 0, gy: int = 0, gz: int = 0) -> None:
        """Inject a single accelerometer sample (values in mg / mdps)."""
        resp = self._cmd(f"INJECT_ACCEL {ax} {ay} {az} {gx} {gy} {gz}")
        assert resp.ok, f"INJECT_ACCEL failed: {resp.raw}"

    def replay_dataset(
        self,
        samples: List[Dict[str, int]],
        timeout_per_sample: float = 0.05,
    ) -> ReplayResult:
        """
        Replay a list of accel samples and return detection result.

        Args:
            samples: list of dicts with keys ax, ay, az (mg) and
                     optionally gx, gy, gz (mdps).
            timeout_per_sample: serial timeout per REPLAY_SAMPLE command.

        Returns:
            ReplayResult with detected flag and latency_ms.
        """
        n = len(samples)
        resp = self._cmd(f"REPLAY_START {n}")
        assert resp.ok, f"REPLAY_START failed: {resp.raw}"

        old_timeout = self._ser.timeout  # type: ignore[union-attr]
        self._ser.timeout = timeout_per_sample  # type: ignore[union-attr]
        try:
            for s in samples:
                ax = s.get("ax", 0)
                ay = s.get("ay", 0)
                az = s.get("az", 1000)  # default 1 g upright
                gx = s.get("gx", 0)
                gy = s.get("gy", 0)
                gz = s.get("gz", 0)
                r = self._cmd(f"REPLAY_SAMPLE {ax} {ay} {az} {gx} {gy} {gz}")
                assert r.ok, f"REPLAY_SAMPLE failed: {r.raw}"
        finally:
            self._ser.timeout = old_timeout  # type: ignore[union-attr]

        resp_end = self._cmd("REPLAY_END")
        assert resp_end.ok, f"REPLAY_END failed: {resp_end.raw}"
        detected   = resp_end.get_int("DETECTED") == 1
        latency_ms = resp_end.get_int("LATENCY_MS")
        return ReplayResult(detected=detected,
                            latency_ms=latency_ms,
                            raw=resp_end.raw)

    def get_lte_latency(self) -> int:
        """Return last end-to-end LTE alert latency in ms."""
        resp = self._cmd("GET_LTE_LATENCY")
        assert resp.ok, f"GET_LTE_LATENCY failed: {resp.raw}"
        return resp.get_int("LATENCY_MS")

    def get_gps_fix_time(self) -> int:
        """Return last GPS fix acquisition time in ms."""
        resp = self._cmd("GET_GPS_FIX_TIME")
        assert resp.ok, f"GET_GPS_FIX_TIME failed: {resp.raw}"
        return resp.get_int("FIX_MS")

    def trigger_watchdog_test(self) -> None:
        """Suspend WDG feed for 2 s — device resets; reconnect to verify."""
        self._cmd("TRIGGER_WATCHDOG_TEST")
        # Firmware resets — serial line drops; caller must reconnect
        self.disconnect()

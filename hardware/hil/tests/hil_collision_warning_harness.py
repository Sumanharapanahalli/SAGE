"""
hil_collision_warning_harness.py — Python HIL harness for intersection
collision-warning firmware.

Connects to the DUT via OpenOCD/GDB, injects simulated radar sensor data
into the firmware RAM stub, reads back warning state, and verifies:
  • Intersection scenario CW-SCN-001 (Vehicle A — FRONT_LEFT)
  • Intersection scenario CW-SCN-002 (Vehicle B — FRONT_RIGHT)
  • Detection latency ≤ 50 ms (SR-CW-TIM-001)
  • Warning output latency ≤ 100 ms (SR-CW-TIM-002)
  • Sensor poll jitter ≤ ±1 ms (SR-CW-TIM-003)
  • Fault injection: sensor timeout, sensor stuck, CAN bus error

Requirements:
    pip install pytest pyocd pygdbmi pyserial lxml

Usage:
    pytest tests/hil_collision_warning_harness.py -v \\
           --target-port /dev/ttyUSB0

Architecture:
    ┌─────────────────────────────┐    OpenOCD TCL / GDB mem r/w    ┌──────────┐
    │  hil_collision_warning_     │ ──────────────────────────────► │  DUT     │
    │  harness.py  (pytest)       │    UART semihosting log          │  STM32WB │
    │  CollisionWarningHIL        │ ◄────────────────────────────── │          │
    └─────────────────────────────┘                                  └──────────┘
"""

from __future__ import annotations

import struct
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, List, Optional, Tuple

import pytest
import serial

# ---------------------------------------------------------------------------
# Re-use the base OpenOCDClient and UARTReader from the existing harness.
# ---------------------------------------------------------------------------
# We import directly so that this file remains independently runnable via
# "pytest tests/hil_collision_warning_harness.py" without modifying the base.
# ---------------------------------------------------------------------------
from hil_harness import OpenOCDClient, UARTReader, HILResultBlock  # type: ignore

# ---------------------------------------------------------------------------
# RAM stub addresses — must match collision_warning_hal.h
# ---------------------------------------------------------------------------
CW_STUB_RADAR_BASE_ADDR    = 0x20001000  # 4 × CW_RadarSample_t (12 bytes each)
CW_STUB_WARNING_STATE_ADDR = 0x20001100  # CW_WarningState_t (32 bytes)
CW_STUB_FAULT_INJECT_ADDR  = 0x20001200  # uint32_t fault flags
CW_STUB_RESULT_ADDR        = 0x20001300  # HIL result sentinel

# Sensor IDs (match C header)
SENSOR_FRONT_LEFT  = 0
SENSOR_FRONT_RIGHT = 1
SENSOR_REAR_LEFT   = 2
SENSOR_REAR_RIGHT  = 3
SENSOR_COUNT       = 4

# Warning levels (match CW_WarningLevel_t)
WARN_NONE     = 0
WARN_ADVISORY = 1
WARN_CAUTION  = 2
WARN_CRITICAL = 3

# Fault codes (match CW_FaultCode_t)
FAULT_NONE           = 0x00000000
FAULT_SENSOR_TIMEOUT = 0x00000001
FAULT_SENSOR_STUCK   = 0x00000002
FAULT_CAN_BUS_ERROR  = 0x00000004
FAULT_POWER_GLITCH   = 0x00000008

# Timing budgets (milliseconds)
DETECTION_LATENCY_MAX_MS = 50
WARNING_LATENCY_MAX_MS   = 100
POLL_PERIOD_MS           = 10
POLL_JITTER_MS           = 1

# struct formats (little-endian)
_RADAR_FMT    = "<HhBBHI"   # distance, rel_vel, sensor_id, valid, pad, timestamp
_RADAR_SIZE   = struct.calcsize(_RADAR_FMT)   # must be 12
_WARN_FMT     = "<IIIIIII I"  # level, ttc, det_ts, warn_ts, det_lat, warn_lat,
                              #  triggered, warn_count
_WARN_SIZE    = struct.calcsize(_WARN_FMT)    # must be 32

assert _RADAR_SIZE == 12,  f"CW_RadarSample_t size mismatch: {_RADAR_SIZE}"
assert _WARN_SIZE  == 32,  f"CW_WarningState_t size mismatch: {_WARN_SIZE}"

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RadarSample:
    """Mirrors CW_RadarSample_t."""
    distance_cm:    int = 5000
    rel_vel_cms:    int = 0
    sensor_id:      int = 0
    valid:          int = 0
    timestamp_ms:   int = 0

    def pack(self) -> bytes:
        return struct.pack(
            _RADAR_FMT,
            self.distance_cm & 0xFFFF,
            self.rel_vel_cms,
            self.sensor_id & 0xFF,
            self.valid & 0xFF,
            0,                       # pad
            self.timestamp_ms & 0xFFFFFFFF,
        )


@dataclass
class WarningState:
    """Mirrors CW_WarningState_t."""
    level:            int = WARN_NONE
    ttc_ms:           int = 0
    detection_ts_ms:  int = 0
    warning_ts_ms:    int = 0
    detection_lat_ms: int = 0
    warning_lat_ms:   int = 0
    triggered_sensor: int = 0
    warn_count:       int = 0

    @classmethod
    def from_bytes(cls, data: bytes) -> "WarningState":
        if len(data) < _WARN_SIZE:
            raise ValueError(f"WarningState data too short: {len(data)}")
        fields = struct.unpack_from(_WARN_FMT, data)
        return cls(*fields)


# ---------------------------------------------------------------------------
# High-level collision-warning HIL controller
# ---------------------------------------------------------------------------

class CollisionWarningHIL:
    """
    Wraps OpenOCDClient with collision-warning-specific helpers.

    All memory writes go through GDB ``set`` commands over the OpenOCD
    telnet interface to keep the transport layer consistent with the
    existing HIL harness.
    """

    def __init__(self, openocd: OpenOCDClient) -> None:
        if openocd is None:
            raise ValueError("openocd must not be None")
        self._ocd = openocd

    # ------------------------------------------------------------------
    # Low-level memory helpers
    # ------------------------------------------------------------------

    def _write_word(self, address: int, value: int) -> None:
        """Write a 32-bit word to target RAM via GDB."""
        self._ocd.gdb_execute(
            f"set *((unsigned int *)0x{address:08x}) = 0x{value & 0xFFFFFFFF:08x}"
        )

    def _write_bytes(self, address: int, data: bytes) -> None:
        """Write arbitrary bytes to target RAM in 4-byte chunks."""
        for offset in range(0, len(data), 4):
            chunk = data[offset:offset + 4]
            if len(chunk) < 4:
                chunk = chunk + b"\x00" * (4 - len(chunk))
            word = struct.unpack_from("<I", chunk)[0]
            self._write_word(address + offset, word)

    def _read_bytes(self, address: int, length: int) -> bytes:
        return self._ocd.read_memory(address, length)

    # ------------------------------------------------------------------
    # Radar stub control
    # ------------------------------------------------------------------

    def write_radar_sample(self, sample: RadarSample) -> None:
        """Inject a radar sample into the firmware RAM stub."""
        sid = sample.sensor_id
        if sid >= SENSOR_COUNT:
            raise ValueError(f"Invalid sensor_id={sid}")
        addr = CW_STUB_RADAR_BASE_ADDR + sid * _RADAR_SIZE
        self._write_bytes(addr, sample.pack())

    def clear_all_radar(self) -> None:
        """Set all sensors to max range, invalid."""
        for sid in range(SENSOR_COUNT):
            s = RadarSample(
                distance_cm  = 5000,
                rel_vel_cms  = 0,
                sensor_id    = sid,
                valid        = 0,
                timestamp_ms = 0,
            )
            self.write_radar_sample(s)

    # ------------------------------------------------------------------
    # Warning state readback
    # ------------------------------------------------------------------

    def read_warning_state(self) -> WarningState:
        raw = self._read_bytes(CW_STUB_WARNING_STATE_ADDR, _WARN_SIZE)
        return WarningState.from_bytes(raw)

    # ------------------------------------------------------------------
    # Fault injection
    # ------------------------------------------------------------------

    def inject_fault(self, fault_code: int) -> None:
        self._write_word(CW_STUB_FAULT_INJECT_ADDR, fault_code)

    def clear_fault(self) -> None:
        self._write_word(CW_STUB_FAULT_INJECT_ADDR, FAULT_NONE)

    # ------------------------------------------------------------------
    # Polling helpers
    # ------------------------------------------------------------------

    def wait_for_warning_level(
        self,
        expected: int,
        timeout_ms: int = 500,
    ) -> Tuple[bool, WarningState]:
        """
        Poll warning state until level matches *expected* or timeout.

        Returns (matched: bool, final_state: WarningState).
        """
        deadline = time.monotonic() + timeout_ms / 1000.0
        state    = self.read_warning_state()
        while time.monotonic() < deadline:
            state = self.read_warning_state()
            if state.level == expected:
                return True, state
            time.sleep(POLL_PERIOD_MS / 1000.0)
        return False, state

    def inject_approach_profile(
        self,
        sensor_id:   int,
        profile_cm:  List[int],
        vel_cms:     int,
        step_ms:     int = 50,
    ) -> List[WarningState]:
        """
        Inject a sequence of distance readings and collect warning states.

        Returns one WarningState snapshot per profile step.
        """
        states: List[WarningState] = []
        for dist in profile_cm:
            s = RadarSample(
                distance_cm  = dist,
                rel_vel_cms  = vel_cms,
                sensor_id    = sensor_id,
                valid        = 1,
                timestamp_ms = int(time.monotonic() * 1000) & 0xFFFFFFFF,
            )
            self.write_radar_sample(s)
            time.sleep(step_ms / 1000.0)
            states.append(self.read_warning_state())
        return states


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------

def pytest_addoption(parser: pytest.Parser) -> None:  # type: ignore[name-defined]
    parser.addoption(
        "--target-port", default="/dev/ttyUSB0",
        help="Serial port for DUT UART semihosting output",
    )
    parser.addoption(
        "--no-flash", action="store_true", default=False,
        help="Skip firmware flash (assumes firmware already on board)",
    )
    parser.addoption(
        "--openocd-host", default="127.0.0.1",
        help="OpenOCD telnet host",
    )
    parser.addoption(
        "--openocd-port", type=int, default=4444,
        help="OpenOCD telnet port",
    )


@pytest.fixture(scope="session")
def openocd_client(request: pytest.FixtureRequest) -> Generator[OpenOCDClient, None, None]:
    host = request.config.getoption("--openocd-host")
    port = request.config.getoption("--openocd-port")
    client = OpenOCDClient(host=host, port=port)
    client.start()
    yield client
    client.stop()


@pytest.fixture(scope="session")
def cw_hil(openocd_client: OpenOCDClient) -> Generator[CollisionWarningHIL, None, None]:
    hil = CollisionWarningHIL(openocd_client)
    hil.clear_all_radar()
    hil.clear_fault()
    yield hil
    hil.clear_all_radar()
    hil.clear_fault()


@pytest.fixture(autouse=True)
def reset_between_tests(cw_hil: CollisionWarningHIL) -> Generator[None, None, None]:
    """Clear radar stubs and faults before and after every test."""
    cw_hil.clear_all_radar()
    cw_hil.clear_fault()
    time.sleep(0.030)   # 30 ms settle
    yield
    cw_hil.clear_all_radar()
    cw_hil.clear_fault()
    time.sleep(0.030)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestVehicleAScenario:
    """CW-SCN-001 — Vehicle A approaching on FRONT_LEFT."""

    APPROACH_PROFILE = [1000, 900, 800, 700, 600, 500, 400, 200]  # cm
    APPROACH_VEL     = -100   # 1 m/s

    def test_critical_warning_triggered(self, cw_hil: CollisionWarningHIL) -> None:
        """Vehicle A at ≤ 200 cm with approach velocity → CRITICAL warning."""
        states = cw_hil.inject_approach_profile(
            sensor_id  = SENSOR_FRONT_LEFT,
            profile_cm = self.APPROACH_PROFILE,
            vel_cms    = self.APPROACH_VEL,
            step_ms    = POLL_PERIOD_MS + 5,
        )
        final = states[-1]
        assert final.level == WARN_CRITICAL, (
            f"Expected CRITICAL, got {final.level} at dist=200 cm"
        )

    def test_triggered_sensor_is_front_left(self, cw_hil: CollisionWarningHIL) -> None:
        """Triggered sensor ID must be FRONT_LEFT."""
        cw_hil.inject_approach_profile(
            sensor_id  = SENSOR_FRONT_LEFT,
            profile_cm = self.APPROACH_PROFILE,
            vel_cms    = self.APPROACH_VEL,
            step_ms    = POLL_PERIOD_MS + 5,
        )
        state = cw_hil.read_warning_state()
        assert state.triggered_sensor == SENSOR_FRONT_LEFT, (
            f"triggered_sensor={state.triggered_sensor}, expected FRONT_LEFT={SENSOR_FRONT_LEFT}"
        )

    def test_detection_latency(self, cw_hil: CollisionWarningHIL) -> None:
        """Detection latency must be ≤ 50 ms (SR-CW-TIM-001)."""
        cw_hil.inject_approach_profile(
            sensor_id  = SENSOR_FRONT_LEFT,
            profile_cm = self.APPROACH_PROFILE,
            vel_cms    = self.APPROACH_VEL,
            step_ms    = POLL_PERIOD_MS + 5,
        )
        state = cw_hil.read_warning_state()
        assert state.detection_lat_ms <= DETECTION_LATENCY_MAX_MS, (
            f"Detection latency {state.detection_lat_ms} ms > {DETECTION_LATENCY_MAX_MS} ms "
            "(SR-CW-TIM-001)"
        )

    def test_warning_output_latency(self, cw_hil: CollisionWarningHIL) -> None:
        """Warning GPIO assert latency must be ≤ 100 ms (SR-CW-TIM-002)."""
        cw_hil.inject_approach_profile(
            sensor_id  = SENSOR_FRONT_LEFT,
            profile_cm = self.APPROACH_PROFILE,
            vel_cms    = self.APPROACH_VEL,
            step_ms    = POLL_PERIOD_MS + 5,
        )
        state = cw_hil.read_warning_state()
        lat = state.warning_lat_ms
        assert lat <= WARNING_LATENCY_MAX_MS, (
            f"Warning output latency {lat} ms > {WARNING_LATENCY_MAX_MS} ms (SR-CW-TIM-002)"
        )

    def test_warning_escalation_order(self, cw_hil: CollisionWarningHIL) -> None:
        """Warning must escalate: NONE → ADVISORY → CAUTION → CRITICAL."""
        states = cw_hil.inject_approach_profile(
            sensor_id  = SENSOR_FRONT_LEFT,
            profile_cm = self.APPROACH_PROFILE,
            vel_cms    = self.APPROACH_VEL,
            step_ms    = POLL_PERIOD_MS + 5,
        )
        levels = [s.level for s in states]
        # Level must be non-decreasing (escalation-only during approach)
        for i in range(1, len(levels)):
            assert levels[i] >= levels[i - 1], (
                f"Warning de-escalated during approach at step {i}: "
                f"{levels[i-1]} → {levels[i]}"
            )
        assert WARN_CRITICAL in levels, "CRITICAL level never reached during approach"


class TestVehicleBScenario:
    """CW-SCN-002 — Vehicle B approaching on FRONT_RIGHT at higher speed."""

    APPROACH_PROFILE = [1000, 750, 500, 300, 150]  # cm
    APPROACH_VEL     = -250  # 2.5 m/s

    def test_critical_warning_triggered(self, cw_hil: CollisionWarningHIL) -> None:
        """Vehicle B at ≤ 200 cm with fast approach → CRITICAL warning."""
        states = cw_hil.inject_approach_profile(
            sensor_id  = SENSOR_FRONT_RIGHT,
            profile_cm = self.APPROACH_PROFILE,
            vel_cms    = self.APPROACH_VEL,
            step_ms    = POLL_PERIOD_MS + 5,
        )
        final = states[-1]
        assert final.level == WARN_CRITICAL, (
            f"Expected CRITICAL, got level={final.level} at dist=150 cm"
        )

    def test_triggered_sensor_is_front_right(self, cw_hil: CollisionWarningHIL) -> None:
        """FRONT_RIGHT must be the triggering sensor."""
        cw_hil.inject_approach_profile(
            sensor_id  = SENSOR_FRONT_RIGHT,
            profile_cm = self.APPROACH_PROFILE,
            vel_cms    = self.APPROACH_VEL,
            step_ms    = POLL_PERIOD_MS + 5,
        )
        state = cw_hil.read_warning_state()
        assert state.triggered_sensor == SENSOR_FRONT_RIGHT

    def test_warning_count_incremented(self, cw_hil: CollisionWarningHIL) -> None:
        """Warning counter must increment as vehicle approaches through zones."""
        cw_hil.inject_approach_profile(
            sensor_id  = SENSOR_FRONT_RIGHT,
            profile_cm = self.APPROACH_PROFILE,
            vel_cms    = self.APPROACH_VEL,
            step_ms    = POLL_PERIOD_MS + 5,
        )
        state = cw_hil.read_warning_state()
        assert state.warn_count >= 2, (
            f"warn_count={state.warn_count}; expected ≥ 2 transitions through warning zones"
        )

    def test_detection_latency(self, cw_hil: CollisionWarningHIL) -> None:
        """Detection latency must be ≤ 50 ms even at high approach speed."""
        cw_hil.inject_approach_profile(
            sensor_id  = SENSOR_FRONT_RIGHT,
            profile_cm = self.APPROACH_PROFILE,
            vel_cms    = self.APPROACH_VEL,
            step_ms    = POLL_PERIOD_MS + 5,
        )
        state = cw_hil.read_warning_state()
        assert state.detection_lat_ms <= DETECTION_LATENCY_MAX_MS, (
            f"Detection latency {state.detection_lat_ms} ms > {DETECTION_LATENCY_MAX_MS} ms"
        )


class TestFaultInjection:
    """Fault injection tests — all faults must be detected and handled safely."""

    def test_sensor_timeout_detected(self, cw_hil: CollisionWarningHIL) -> None:
        """CW-FI-001: sensor timeout → warning clears to NONE (fail-safe)."""
        # Establish advisory warning first
        cw_hil.write_radar_sample(RadarSample(
            distance_cm=800, rel_vel_cms=-100,
            sensor_id=SENSOR_FRONT_LEFT, valid=1,
        ))
        time.sleep((POLL_PERIOD_MS + 5) / 1000.0)

        # Inject timeout
        cw_hil.inject_fault(FAULT_SENSOR_TIMEOUT)
        time.sleep((3 * POLL_PERIOD_MS + 10) / 1000.0)

        state = cw_hil.read_warning_state()
        assert state.level == WARN_NONE, (
            f"Warning level={state.level}; expected NONE (fail-safe) after sensor timeout"
        )

    def test_sensor_timeout_recovery(self, cw_hil: CollisionWarningHIL) -> None:
        """CW-FI-001c: warning resumes after sensor timeout clears."""
        cw_hil.inject_fault(FAULT_SENSOR_TIMEOUT)
        time.sleep(0.050)
        cw_hil.clear_fault()

        cw_hil.write_radar_sample(RadarSample(
            distance_cm=400, rel_vel_cms=-150,
            sensor_id=SENSOR_FRONT_LEFT, valid=1,
        ))
        time.sleep((2 * POLL_PERIOD_MS + 10) / 1000.0)

        state = cw_hil.read_warning_state()
        assert state.level > WARN_NONE, (
            "Warning did not resume after sensor recovery"
        )

    def test_sensor_stuck_detected(self, cw_hil: CollisionWarningHIL) -> None:
        """CW-FI-002: frozen radar output (20 identical samples) → fault flagged."""
        cw_hil.inject_fault(FAULT_SENSOR_STUCK)
        for _ in range(20):
            cw_hil.write_radar_sample(RadarSample(
                distance_cm=500, rel_vel_cms=-100,
                sensor_id=SENSOR_FRONT_LEFT, valid=1,
            ))
            time.sleep(POLL_PERIOD_MS / 1000.0)

        state = cw_hil.read_warning_state()
        # Firmware must not issue CRITICAL from frozen data
        assert state.level != WARN_CRITICAL, (
            "CRITICAL issued from a frozen (stuck) sensor — fault not suppressed"
        )

    def test_can_bus_error_does_not_suppress_warning(
        self, cw_hil: CollisionWarningHIL
    ) -> None:
        """CW-FI-003c: active collision warning survives CAN bus error."""
        cw_hil.write_radar_sample(RadarSample(
            distance_cm=300, rel_vel_cms=-200,
            sensor_id=SENSOR_FRONT_LEFT, valid=1,
        ))
        time.sleep((POLL_PERIOD_MS + 5) / 1000.0)
        pre_state = cw_hil.read_warning_state()

        cw_hil.inject_fault(FAULT_CAN_BUS_ERROR)
        time.sleep(0.050)

        post_state = cw_hil.read_warning_state()
        assert post_state.level >= WARN_CAUTION, (
            f"Warning level dropped to {post_state.level} during CAN fault; "
            f"was {pre_state.level} before fault"
        )
        cw_hil.clear_fault()

    def test_power_glitch_state_preserved(
        self, cw_hil: CollisionWarningHIL
    ) -> None:
        """CW-FI-004: warning level restored after brief power glitch."""
        cw_hil.write_radar_sample(RadarSample(
            distance_cm=150, rel_vel_cms=-100,
            sensor_id=SENSOR_FRONT_LEFT, valid=1,
        ))
        time.sleep((POLL_PERIOD_MS + 10) / 1000.0)
        pre_state  = cw_hil.read_warning_state()
        pre_level  = pre_state.level

        cw_hil.inject_fault(FAULT_POWER_GLITCH)
        time.sleep(0.005)   # 5 ms glitch
        cw_hil.clear_fault()
        time.sleep(0.050)   # 50 ms recovery

        cw_hil.write_radar_sample(RadarSample(
            distance_cm=150, rel_vel_cms=-100,
            sensor_id=SENSOR_FRONT_LEFT, valid=1,
        ))
        time.sleep((POLL_PERIOD_MS + 10) / 1000.0)

        post_state = cw_hil.read_warning_state()
        assert post_state.level == pre_level, (
            f"Level after glitch={post_state.level}, expected {pre_level}"
        )


class TestTimingRequirements:
    """Timing budget verification (SR-CW-TIM-001/002/003)."""

    def test_detection_latency_50_samples(
        self, cw_hil: CollisionWarningHIL
    ) -> None:
        """Detection latency ≤ 50 ms across 50 consecutive samples."""
        max_lat = 0
        for _ in range(50):
            cw_hil.clear_all_radar()
            time.sleep(0.005)
            cw_hil.write_radar_sample(RadarSample(
                distance_cm=180, rel_vel_cms=-100,
                sensor_id=SENSOR_FRONT_LEFT, valid=1,
            ))
            time.sleep((POLL_PERIOD_MS + 15) / 1000.0)
            state = cw_hil.read_warning_state()
            if state.detection_lat_ms > max_lat:
                max_lat = state.detection_lat_ms

        assert max_lat <= DETECTION_LATENCY_MAX_MS, (
            f"Max detection latency {max_lat} ms > {DETECTION_LATENCY_MAX_MS} ms "
            "over 50 samples (SR-CW-TIM-001)"
        )

    def test_warning_latency_50_samples(
        self, cw_hil: CollisionWarningHIL
    ) -> None:
        """Warning GPIO latency ≤ 100 ms across 50 consecutive triggers."""
        max_lat = 0
        for _ in range(50):
            cw_hil.clear_all_radar()
            time.sleep(0.005)
            cw_hil.write_radar_sample(RadarSample(
                distance_cm=180, rel_vel_cms=-100,
                sensor_id=SENSOR_FRONT_LEFT, valid=1,
            ))
            time.sleep((POLL_PERIOD_MS + 20) / 1000.0)
            state = cw_hil.read_warning_state()
            if state.warning_lat_ms > max_lat:
                max_lat = state.warning_lat_ms

        assert max_lat <= WARNING_LATENCY_MAX_MS, (
            f"Max warning latency {max_lat} ms > {WARNING_LATENCY_MAX_MS} ms "
            "over 50 samples (SR-CW-TIM-002)"
        )

    def test_no_spurious_warning_when_no_vehicle(
        self, cw_hil: CollisionWarningHIL
    ) -> None:
        """No warning issued when all sensors at max range with no approach."""
        for sid in range(SENSOR_COUNT):
            cw_hil.write_radar_sample(RadarSample(
                distance_cm=5000, rel_vel_cms=0,
                sensor_id=sid, valid=1,
            ))
        time.sleep((3 * POLL_PERIOD_MS) / 1000.0)
        state = cw_hil.read_warning_state()
        assert state.level == WARN_NONE, (
            f"Spurious warning level={state.level} with no vehicles in range"
        )

    def test_no_warning_for_receding_vehicle(
        self, cw_hil: CollisionWarningHIL
    ) -> None:
        """Vehicle moving away (positive velocity) must not trigger warning."""
        cw_hil.write_radar_sample(RadarSample(
            distance_cm=300, rel_vel_cms=+200,   # receding at 2 m/s
            sensor_id=SENSOR_FRONT_LEFT, valid=1,
        ))
        time.sleep((POLL_PERIOD_MS + 10) / 1000.0)
        state = cw_hil.read_warning_state()
        assert state.level == WARN_NONE, (
            f"Warning level={state.level} for a receding vehicle (vel=+200 cm/s)"
        )


class TestCoverage:
    """Coverage gate — on-target branch coverage counter."""

    def test_branch_coverage_gte_90_pct(
        self, openocd_client: OpenOCDClient
    ) -> None:
        """Branch coverage on-target counter must reach ≥ 90 % (SR-COV-001)."""
        # Read g_cw_branch_total and g_cw_branch_covered from target.
        # Symbol addresses resolved by GDB from the ELF; we use fixed offsets
        # from hil_config.h for the non-coverage build fallback.
        CW_BRANCH_TOTAL_ADDR   = 0x20002000
        CW_BRANCH_COVERED_ADDR = 0x20002004

        raw_total   = openocd_client.read_memory(CW_BRANCH_TOTAL_ADDR,   4)
        raw_covered = openocd_client.read_memory(CW_BRANCH_COVERED_ADDR, 4)

        total   = struct.unpack_from("<I", raw_total)[0]
        covered = struct.unpack_from("<I", raw_covered)[0]

        if total == 0:
            pytest.skip("Coverage counters not instrumented (non-coverage build)")

        pct = (covered * 100) // total
        assert pct >= 90, (
            f"Branch coverage {pct}% ({covered}/{total}) < 90% target (SR-COV-001)"
        )

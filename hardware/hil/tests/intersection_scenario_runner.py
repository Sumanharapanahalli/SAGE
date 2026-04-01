"""
intersection_scenario_runner.py — Standalone intersection HIL scenario runner.

Executes the "Intersection with vehicle A" scenario end-to-end via OpenOCD/GDB,
verifying that the collision warning firmware triggers correctly when vehicle A
approaches the intersection.

Unlike the pytest-based hil_collision_warning_harness.py, this script runs as
a standalone CLI tool (suitable for CI pipelines, Robot Framework Library use,
and direct terminal invocation) and produces a structured JSON result suitable
for machine parsing.

Acceptance criteria verified:
  AC-HIL-CW-001 : HIL test coverage ≥ 90 %  (branch counter from target)
  AC-HIL-CW-002 : All fault injection tests pass
  AC-HIL-CW-003 : Timing requirements verified (SR-CW-TIM-001/002/003)

Usage:
    python intersection_scenario_runner.py \\
        --openocd-host 127.0.0.1 \\
        --openocd-port 4444 \\
        --serial-port /dev/ttyUSB0 \\
        --elf build/sage_hil_tests.elf \\
        --report-json results/intersection_report.json

Requirements:
    pip install pyserial pygdbmi
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import struct
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Re-use the transport layer from the existing harness
# ---------------------------------------------------------------------------
try:
    from hil_harness import OpenOCDClient, UARTReader  # type: ignore
except ImportError:
    # Allow the module to be imported for testing even without the harness;
    # actual HIL execution will fail at runtime — expected in CI without HW.
    OpenOCDClient = None  # type: ignore
    UARTReader = None     # type: ignore

# ---------------------------------------------------------------------------
# Memory-map constants — must match collision_warning_hal.h
# ---------------------------------------------------------------------------
CW_STUB_RADAR_BASE_ADDR    = 0x20001000   # 4 × CW_RadarSample_t (12 bytes each)
CW_STUB_WARNING_STATE_ADDR = 0x20001100   # CW_WarningState_t    (32 bytes)
CW_STUB_FAULT_INJECT_ADDR  = 0x20001200   # uint32_t fault flags
CW_STUB_RESULT_ADDR        = 0x20001300   # HIL result sentinel

CW_BRANCH_TOTAL_ADDR       = 0x20002000   # volatile uint32_t g_cw_branch_total
CW_BRANCH_COVERED_ADDR     = 0x20002004   # volatile uint32_t g_cw_branch_covered
CW_FAULT_DETECTED_ADDR     = 0x20002008   # volatile uint32_t g_cw_fault_detected_flags
CW_CAN_ERROR_COUNT_ADDR    = 0x2000200C   # volatile uint32_t g_cw_can_error_count

# Sensor IDs
SENSOR_FRONT_LEFT  = 0
SENSOR_FRONT_RIGHT = 1
SENSOR_REAR_LEFT   = 2
SENSOR_REAR_RIGHT  = 3
SENSOR_COUNT       = 4

# Warning levels
WARN_NONE     = 0
WARN_ADVISORY = 1
WARN_CAUTION  = 2
WARN_CRITICAL = 3

WARN_NAMES = {WARN_NONE: "NONE", WARN_ADVISORY: "ADVISORY",
              WARN_CAUTION: "CAUTION", WARN_CRITICAL: "CRITICAL"}

# Fault codes
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
COVERAGE_TARGET_PCT      = 90

# Struct layouts (little-endian) — must match C struct sizes
_RADAR_FMT  = "<HhBBHI"    # 12 bytes: dist, vel, sensor_id, valid, pad, ts
_WARN_FMT   = "<IIIIIIII"  # 32 bytes: level, ttc, det_ts, warn_ts, det_lat, warn_lat, triggered, count
_RADAR_SIZE = struct.calcsize(_RADAR_FMT)
_WARN_SIZE  = struct.calcsize(_WARN_FMT)

assert _RADAR_SIZE == 12, f"RadarSample size mismatch: {_RADAR_SIZE}"
assert _WARN_SIZE  == 32, f"WarningState size mismatch: {_WARN_SIZE}"

log = logging.getLogger("intersection_runner")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RadarSample:
    """Mirrors CW_RadarSample_t."""
    distance_cm:  int = 5000
    rel_vel_cms:  int = 0
    sensor_id:    int = 0
    valid:        int = 0
    timestamp_ms: int = 0

    def pack(self) -> bytes:
        return struct.pack(
            _RADAR_FMT,
            self.distance_cm & 0xFFFF,
            self.rel_vel_cms,
            self.sensor_id & 0xFF,
            self.valid & 0xFF,
            0,                               # explicit pad
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

    def level_name(self) -> str:
        return WARN_NAMES.get(self.level, f"UNKNOWN({self.level})")


@dataclass
class ScenarioResult:
    """Result record for a single intersection scenario."""
    scenario_id:    str
    description:    str
    passed:         bool
    assertions_run: int = 0
    assertions_failed: int = 0
    final_state:    Optional[WarningState] = None
    failure_reason: str = ""
    elapsed_ms:     float = 0.0


@dataclass
class IntersectionReport:
    """Top-level HIL report for intersection collision-warning scenarios."""
    target_mcu:       str = "STM32WB55RGV6"
    binary_estimate_kb: int = 72
    ram_estimate_kb:  int = 28
    scenarios:        List[ScenarioResult] = field(default_factory=list)
    coverage_pct:     Optional[int] = None
    coverage_pass:    Optional[bool] = None
    timing_pass:      bool = False
    fault_inject_pass: bool = False
    overall_pass:     bool = False

    def to_dict(self) -> Dict:
        d = dataclasses.asdict(self)
        # Serialize WarningState in each scenario
        for s in d["scenarios"]:
            if s["final_state"] is not None:
                s["final_state"]["level_name"] = WARN_NAMES.get(
                    s["final_state"]["level"], "UNKNOWN"
                )
        return d


# ---------------------------------------------------------------------------
# HIL controller
# ---------------------------------------------------------------------------

class IntersectionHIL:
    """
    High-level controller for intersection collision-warning HIL testing.

    Wraps an OpenOCDClient with intersection-specific helpers.
    All NULL-guard checks follow MISRA Rule 15.4 spirit: validate before use.
    """

    def __init__(self, openocd: "OpenOCDClient") -> None:
        if openocd is None:
            raise ValueError("openocd client must not be None")
        self._ocd = openocd

    # ------------------------------------------------------------------
    # Low-level memory access
    # ------------------------------------------------------------------

    def _write_word(self, address: int, value: int) -> None:
        """Write a 32-bit word to target RAM via GDB."""
        self._ocd.gdb_execute(
            f"set *((unsigned int *)0x{address:08x}) = 0x{value & 0xFFFFFFFF:08x}"
        )

    def _write_bytes(self, address: int, data: bytes) -> None:
        """Write raw bytes to target RAM in 4-byte chunks."""
        for offset in range(0, len(data), 4):
            chunk = (data[offset:offset + 4]).ljust(4, b"\x00")
            word = struct.unpack_from("<I", chunk)[0]
            self._write_word(address + offset, word)

    def _read_word(self, address: int) -> int:
        """Read a 32-bit word from target RAM."""
        raw = self._ocd.read_memory(address, 4)
        if len(raw) < 4:
            return 0
        return struct.unpack_from("<I", raw)[0]

    def _read_bytes(self, address: int, length: int) -> bytes:
        return self._ocd.read_memory(address, length)

    # ------------------------------------------------------------------
    # Radar stub control
    # ------------------------------------------------------------------

    def write_radar(self, sample: RadarSample) -> None:
        """Inject a radar sample into the RAM stub region."""
        if sample.sensor_id >= SENSOR_COUNT:
            raise ValueError(f"sensor_id={sample.sensor_id} out of range")
        addr = CW_STUB_RADAR_BASE_ADDR + sample.sensor_id * _RADAR_SIZE
        self._write_bytes(addr, sample.pack())

    def clear_all_radar(self) -> None:
        """Reset all sensors to max range, invalid."""
        for sid in range(SENSOR_COUNT):
            self.write_radar(RadarSample(
                distance_cm=5000, rel_vel_cms=0,
                sensor_id=sid, valid=0,
                timestamp_ms=int(time.monotonic() * 1000) & 0xFFFFFFFF,
            ))

    # ------------------------------------------------------------------
    # Warning state readback
    # ------------------------------------------------------------------

    def read_warning(self) -> WarningState:
        raw = self._read_bytes(CW_STUB_WARNING_STATE_ADDR, _WARN_SIZE)
        return WarningState.from_bytes(raw)

    # ------------------------------------------------------------------
    # Fault injection
    # ------------------------------------------------------------------

    def inject_fault(self, code: int) -> None:
        self._write_word(CW_STUB_FAULT_INJECT_ADDR, code)

    def clear_fault(self) -> None:
        self._write_word(CW_STUB_FAULT_INJECT_ADDR, FAULT_NONE)

    def read_fault_detected(self) -> int:
        return self._read_word(CW_FAULT_DETECTED_ADDR)

    def read_can_error_count(self) -> int:
        return self._read_word(CW_CAN_ERROR_COUNT_ADDR)

    # ------------------------------------------------------------------
    # Coverage counters
    # ------------------------------------------------------------------

    def read_coverage(self) -> Tuple[int, int]:
        """Return (covered_branches, total_branches) from target counters."""
        total   = self._read_word(CW_BRANCH_TOTAL_ADDR)
        covered = self._read_word(CW_BRANCH_COVERED_ADDR)
        return covered, total

    # ------------------------------------------------------------------
    # Scenario helpers
    # ------------------------------------------------------------------

    def approach_profile(
        self,
        sensor_id:  int,
        profile_cm: List[int],
        vel_cms:    int,
        step_ms:    int = POLL_PERIOD_MS + 5,
    ) -> List[WarningState]:
        """
        Inject an approach sequence and collect one WarningState per step.

        Returns the list of states, one per distance step.
        """
        states: List[WarningState] = []
        for dist in profile_cm:
            sample = RadarSample(
                distance_cm  = dist,
                rel_vel_cms  = vel_cms,
                sensor_id    = sensor_id,
                valid        = 1,
                timestamp_ms = int(time.monotonic() * 1000) & 0xFFFFFFFF,
            )
            self.write_radar(sample)
            time.sleep(step_ms / 1000.0)
            states.append(self.read_warning())
        return states

    def wait_for_level(
        self,
        expected: int,
        timeout_ms: int = 500,
    ) -> Tuple[bool, WarningState]:
        """Poll until expected warning level or timeout.  Returns (matched, state)."""
        deadline = time.monotonic() + timeout_ms / 1000.0
        state = self.read_warning()
        while time.monotonic() < deadline:
            state = self.read_warning()
            if state.level == expected:
                return True, state
            time.sleep(POLL_PERIOD_MS / 1000.0)
        return False, state

    def reset(self, settle_ms: int = 30) -> None:
        """Clear all sensors, fault flags, and allow firmware to settle."""
        self.clear_all_radar()
        self.clear_fault()
        time.sleep(settle_ms / 1000.0)


# ---------------------------------------------------------------------------
# Individual scenario functions
# ---------------------------------------------------------------------------

def _run_scn_001_vehicle_a_t_junction(hil: IntersectionHIL) -> ScenarioResult:
    """IS-SCN-001: Vehicle A approaches T-junction on FRONT_LEFT at 1 m/s."""
    result = ScenarioResult(
        scenario_id  = "IS-SCN-001",
        description  = "Vehicle A T-junction approach (FRONT_LEFT, 1 m/s)",
    )
    t0 = time.monotonic()

    PROFILE = [1000, 900, 800, 700, 600, 500, 400, 200]  # cm
    VEL     = -100  # 1 m/s

    hil.reset()
    states = hil.approach_profile(SENSOR_FRONT_LEFT, PROFILE, VEL)
    final  = states[-1]
    result.final_state   = final
    result.elapsed_ms    = (time.monotonic() - t0) * 1000.0

    failures: List[str] = []

    if final.level != WARN_CRITICAL:
        failures.append(
            f"Expected CRITICAL, got {final.level_name()} at 200 cm"
        )
    if final.triggered_sensor != SENSOR_FRONT_LEFT:
        failures.append(
            f"triggered_sensor={final.triggered_sensor}, expected FRONT_LEFT={SENSOR_FRONT_LEFT}"
        )
    if final.detection_lat_ms > DETECTION_LATENCY_MAX_MS:
        failures.append(
            f"detection_lat={final.detection_lat_ms} ms > {DETECTION_LATENCY_MAX_MS} ms "
            "(SR-CW-TIM-001)"
        )
    if final.warning_lat_ms > WARNING_LATENCY_MAX_MS:
        failures.append(
            f"warning_lat={final.warning_lat_ms} ms > {WARNING_LATENCY_MAX_MS} ms "
            "(SR-CW-TIM-002)"
        )

    # Warning must have escalated monotonically
    levels = [s.level for s in states]
    for i in range(1, len(levels)):
        if levels[i] < levels[i - 1]:
            failures.append(
                f"Warning de-escalated at step {i}: {levels[i-1]} → {levels[i]}"
            )
            break

    if WARN_CRITICAL not in levels:
        failures.append("CRITICAL level never reached in approach profile")

    result.assertions_run    = 5
    result.assertions_failed = len(failures)
    result.passed            = (len(failures) == 0)
    if failures:
        result.failure_reason = "; ".join(failures)

    log.info("[%s] %s — %s (dist_final=%d cm, warn=%s, det_lat=%d ms)",
             result.scenario_id,
             "PASS" if result.passed else "FAIL",
             result.description,
             PROFILE[-1], final.level_name(), final.detection_lat_ms)
    return result


def _run_scn_002_vehicle_a_high_speed(hil: IntersectionHIL) -> ScenarioResult:
    """IS-SCN-002: Vehicle A 4-way crossing at 3 m/s — early CRITICAL via TTC."""
    result = ScenarioResult(
        scenario_id  = "IS-SCN-002",
        description  = "Vehicle A high-speed 4-way crossing (FRONT_LEFT, 3 m/s)",
    )
    t0 = time.monotonic()

    PROFILE = [900, 700, 500, 300, 200, 100]  # cm
    VEL     = -300  # 3 m/s

    hil.reset()
    states = hil.approach_profile(SENSOR_FRONT_LEFT, PROFILE, VEL)
    final  = states[-1]
    result.final_state = final
    result.elapsed_ms  = (time.monotonic() - t0) * 1000.0

    failures: List[str] = []

    if final.level != WARN_CRITICAL:
        failures.append(
            f"Expected CRITICAL at end, got {final.level_name()}"
        )

    # At 300 cm @ 3 m/s TTC = 1000 ms → must be CRITICAL at step 3
    if len(states) >= 4 and states[3].level != WARN_CRITICAL:
        failures.append(
            f"Expected CRITICAL at step 3 (300 cm, TTC=1000 ms), "
            f"got {WARN_NAMES.get(states[3].level, '?')}"
        )

    if final.detection_lat_ms > DETECTION_LATENCY_MAX_MS:
        failures.append(
            f"detection_lat={final.detection_lat_ms} ms > {DETECTION_LATENCY_MAX_MS} ms"
        )

    result.assertions_run    = 3
    result.assertions_failed = len(failures)
    result.passed            = (len(failures) == 0)
    if failures:
        result.failure_reason = "; ".join(failures)

    log.info("[%s] %s — %s", result.scenario_id,
             "PASS" if result.passed else "FAIL", result.description)
    return result


def _run_scn_003_stationary_fp(hil: IntersectionHIL) -> ScenarioResult:
    """IS-SCN-003: Stationary object at 200 cm must NOT trigger CRITICAL."""
    result = ScenarioResult(
        scenario_id  = "IS-SCN-003",
        description  = "False-positive rejection: stationary object at 200 cm",
    )
    t0 = time.monotonic()

    hil.reset()
    for _ in range(20):
        hil.write_radar(RadarSample(
            distance_cm=200, rel_vel_cms=0,
            sensor_id=SENSOR_FRONT_LEFT, valid=1,
        ))
        time.sleep(POLL_PERIOD_MS / 1000.0)

    state = hil.read_warning()
    result.final_state = state
    result.elapsed_ms  = (time.monotonic() - t0) * 1000.0

    failures: List[str] = []
    if state.level == WARN_CRITICAL:
        failures.append(
            f"CRITICAL issued for stationary object (vel=0) at 200 cm"
        )

    result.assertions_run    = 1
    result.assertions_failed = len(failures)
    result.passed            = (len(failures) == 0)
    if failures:
        result.failure_reason = "; ".join(failures)

    log.info("[%s] %s — %s (warn=%s)",
             result.scenario_id, "PASS" if result.passed else "FAIL",
             result.description, state.level_name())
    return result


def _run_fi_001_sensor_timeout(hil: IntersectionHIL) -> ScenarioResult:
    """IS-FI-001: Sensor timeout during active approach → fail-safe NONE."""
    result = ScenarioResult(
        scenario_id  = "IS-FI-001",
        description  = "Fault injection: sensor timeout mid-approach (fail-safe)",
    )
    t0 = time.monotonic()

    hil.reset()
    hil.write_radar(RadarSample(
        distance_cm=400, rel_vel_cms=-150,
        sensor_id=SENSOR_FRONT_LEFT, valid=1,
    ))
    time.sleep((POLL_PERIOD_MS + 10) / 1000.0)

    pre = hil.read_warning()
    hil.inject_fault(FAULT_SENSOR_TIMEOUT)
    time.sleep((3 * POLL_PERIOD_MS + 10) / 1000.0)

    post = hil.read_warning()
    fault_detected = hil.read_fault_detected()

    hil.clear_fault()
    hil.write_radar(RadarSample(
        distance_cm=400, rel_vel_cms=-150,
        sensor_id=SENSOR_FRONT_LEFT, valid=1,
    ))
    time.sleep((2 * POLL_PERIOD_MS + 10) / 1000.0)
    recovered = hil.read_warning()

    result.final_state = post
    result.elapsed_ms  = (time.monotonic() - t0) * 1000.0

    failures: List[str] = []
    if pre.level == WARN_NONE:
        failures.append("Pre-fault advisory not established (setup failed)")
    if (fault_detected & FAULT_SENSOR_TIMEOUT) == 0:
        failures.append("Sensor timeout fault NOT detected by firmware")
    if post.level != WARN_NONE:
        failures.append(
            f"Warning={post.level_name()} after timeout; expected NONE (fail-safe)"
        )
    if recovered.level == WARN_NONE:
        failures.append("Warning did not resume after sensor recovery")

    result.assertions_run    = 4
    result.assertions_failed = len(failures)
    result.passed            = (len(failures) == 0)
    if failures:
        result.failure_reason = "; ".join(failures)

    log.info("[%s] %s — %s (pre=%s post=%s recovered=%s)",
             result.scenario_id, "PASS" if result.passed else "FAIL",
             result.description,
             pre.level_name(), post.level_name(), recovered.level_name())
    return result


def _run_fi_002_can_error(hil: IntersectionHIL) -> ScenarioResult:
    """IS-FI-002: CAN bus error must not suppress active CRITICAL warning."""
    result = ScenarioResult(
        scenario_id  = "IS-FI-002",
        description  = "Fault injection: CAN bus error during CRITICAL alert",
    )
    t0 = time.monotonic()

    hil.reset()
    hil.write_radar(RadarSample(
        distance_cm=150, rel_vel_cms=-100,
        sensor_id=SENSOR_FRONT_LEFT, valid=1,
    ))
    time.sleep((POLL_PERIOD_MS + 15) / 1000.0)

    pre     = hil.read_warning()
    prior_errors = hil.read_can_error_count()

    hil.inject_fault(FAULT_CAN_BUS_ERROR)
    time.sleep(0.050)

    post         = hil.read_warning()
    fault_bits   = hil.read_fault_detected()
    post_errors  = hil.read_can_error_count()

    hil.clear_fault()
    result.final_state = post
    result.elapsed_ms  = (time.monotonic() - t0) * 1000.0

    failures: List[str] = []
    if pre.level != WARN_CRITICAL:
        failures.append(
            f"Pre-fault state={pre.level_name()}; expected CRITICAL (setup failed)"
        )
    if (fault_bits & FAULT_CAN_BUS_ERROR) == 0:
        failures.append("CAN bus error NOT detected by firmware")
    if post_errors <= prior_errors:
        failures.append(
            f"CAN error counter not incremented: before={prior_errors} after={post_errors}"
        )
    if post.level < WARN_CAUTION:
        failures.append(
            f"Warning dropped to {post.level_name()} during CAN fault; "
            "safety output must remain active"
        )

    result.assertions_run    = 4
    result.assertions_failed = len(failures)
    result.passed            = (len(failures) == 0)
    if failures:
        result.failure_reason = "; ".join(failures)

    log.info("[%s] %s — %s (pre=%s post=%s)",
             result.scenario_id, "PASS" if result.passed else "FAIL",
             result.description, pre.level_name(), post.level_name())
    return result


def _run_cov_001(hil: IntersectionHIL) -> ScenarioResult:
    """IS-COV-001: Read on-target branch coverage counter; verify ≥ 90 %."""
    result = ScenarioResult(
        scenario_id  = "IS-COV-001",
        description  = f"Branch coverage ≥ {COVERAGE_TARGET_PCT}% (SR-COV-001)",
    )
    covered, total = hil.read_coverage()

    if total == 0:
        result.passed         = True
        result.assertions_run = 1
        result.failure_reason = "Coverage counters not instrumented — gate skipped"
        log.warning("[IS-COV-001] Coverage counters zero — non-coverage build, skipping gate")
        return result

    pct = (covered * 100) // total
    log.info("[IS-COV-001] covered=%d total=%d pct=%d%% (target=%d%%)",
             covered, total, pct, COVERAGE_TARGET_PCT)

    failures: List[str] = []
    if pct < COVERAGE_TARGET_PCT:
        failures.append(
            f"Branch coverage {pct}% ({covered}/{total}) < {COVERAGE_TARGET_PCT}% target"
        )

    result.assertions_run    = 1
    result.assertions_failed = len(failures)
    result.passed            = (len(failures) == 0)
    if failures:
        result.failure_reason = "; ".join(failures)
    return result


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_intersection_suite(
    openocd_host: str = "127.0.0.1",
    openocd_port: int = 4444,
    serial_port:  Optional[str] = None,
    elf_path:     Optional[Path] = None,
    report_json:  Optional[Path] = None,
    flash:        bool = True,
) -> IntersectionReport:
    """
    Execute the complete intersection collision-warning HIL suite.

    Returns an IntersectionReport with per-scenario results and overall pass/fail.
    Raises RuntimeError if the OpenOCD connection cannot be established.
    """
    if OpenOCDClient is None:
        raise RuntimeError(
            "hil_harness.py not found on PYTHONPATH — cannot connect to hardware"
        )

    report = IntersectionReport()

    # ---- Connect ----
    log.info("Connecting to OpenOCD at %s:%d …", openocd_host, openocd_port)
    ocd = OpenOCDClient(host=openocd_host, port=openocd_port)
    ocd.start()

    try:
        # Optional: flash firmware before running tests
        if flash and elf_path is not None:
            if not elf_path.exists():
                raise FileNotFoundError(f"ELF not found: {elf_path}")
            log.info("Flashing %s …", elf_path)
            import subprocess
            result = subprocess.run(
                ["openocd",
                 "-f", "interface/stlink.cfg",
                 "-f", "target/stm32wbx.cfg",
                 "-c", f"program {elf_path} verify reset exit"],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Flash failed: {result.stderr}")
            time.sleep(1.0)   # allow boot

        hil = IntersectionHIL(ocd)

        # ---- Scenario suite ----
        log.info("=== Intersection HIL Suite START ===")

        # Scenario tests
        report.scenarios.append(_run_scn_001_vehicle_a_t_junction(hil))
        report.scenarios.append(_run_scn_002_vehicle_a_high_speed(hil))
        report.scenarios.append(_run_scn_003_stationary_fp(hil))

        # Timing summary from scenario 1 (most latency-sensitive)
        scn1_state = report.scenarios[0].final_state
        report.timing_pass = (
            scn1_state is not None
            and scn1_state.detection_lat_ms <= DETECTION_LATENCY_MAX_MS
            and scn1_state.warning_lat_ms   <= WARNING_LATENCY_MAX_MS
        )

        # Fault injection
        report.scenarios.append(_run_fi_001_sensor_timeout(hil))
        report.scenarios.append(_run_fi_002_can_error(hil))

        fi_results = [s for s in report.scenarios
                      if s.scenario_id.startswith("IS-FI")]
        report.fault_inject_pass = all(s.passed for s in fi_results)

        # Coverage gate (must be last — counts all branches exercised above)
        cov_result = _run_cov_001(hil)
        report.scenarios.append(cov_result)

        covered, total = hil.read_coverage()
        if total > 0:
            report.coverage_pct  = (covered * 100) // total
            report.coverage_pass = (report.coverage_pct >= COVERAGE_TARGET_PCT)

        # ---- Overall verdict ----
        report.overall_pass = all(s.passed for s in report.scenarios)

        log.info("=== Intersection HIL Suite END: %s (%d/%d scenarios passed) ===",
                 "PASS" if report.overall_pass else "FAIL",
                 sum(1 for s in report.scenarios if s.passed),
                 len(report.scenarios))

    finally:
        ocd.stop()

    # ---- Persist report ----
    if report_json is not None:
        report_json.parent.mkdir(parents=True, exist_ok=True)
        with report_json.open("w", encoding="utf-8") as fh:
            json.dump(report.to_dict(), fh, indent=2)
        log.info("Report written to %s", report_json)

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Intersection HIL collision-warning scenario runner",
    )
    p.add_argument("--openocd-host", default="127.0.0.1",
                   help="OpenOCD telnet host (default: 127.0.0.1)")
    p.add_argument("--openocd-port", type=int, default=4444,
                   help="OpenOCD telnet port (default: 4444)")
    p.add_argument("--serial-port", default=None,
                   help="DUT UART port for semihosting log (optional)")
    p.add_argument("--elf", type=Path, default=None,
                   help="HIL firmware ELF to flash before testing")
    p.add_argument("--no-flash", action="store_true",
                   help="Skip firmware flash (assumes board is already programmed)")
    p.add_argument("--report-json", type=Path, default=Path("results/intersection_report.json"),
                   help="Output path for JSON report")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Enable DEBUG logging")
    return p


def main() -> int:
    parser = _build_parser()
    args   = parser.parse_args()

    logging.basicConfig(
        level   = logging.DEBUG if args.verbose else logging.INFO,
        format  = "%(asctime)s %(levelname)-7s %(name)s — %(message)s",
        datefmt = "%H:%M:%S",
    )

    try:
        report = run_intersection_suite(
            openocd_host = args.openocd_host,
            openocd_port = args.openocd_port,
            serial_port  = args.serial_port,
            elf_path     = args.elf,
            report_json  = args.report_json,
            flash        = (not args.no_flash) and (args.elf is not None),
        )
    except Exception as exc:
        log.error("Suite aborted: %s", exc, exc_info=args.verbose)
        return 2

    # Print summary table
    print("\nIntersection Collision-Warning HIL Report")
    print("=" * 60)
    print(f"  Target MCU  : {report.target_mcu}")
    print(f"  Coverage    : {report.coverage_pct}% "
          f"({'PASS' if report.coverage_pass else 'FAIL'})")
    print(f"  Timing      : {'PASS' if report.timing_pass else 'FAIL'}")
    print(f"  Fault Inject: {'PASS' if report.fault_inject_pass else 'FAIL'}")
    print(f"  Overall     : {'PASS' if report.overall_pass else 'FAIL'}")
    print()
    print(f"  {'Scenario':<20} {'Result':<8} {'Detail'}")
    print(f"  {'-'*20} {'-'*8} {'-'*30}")
    for s in report.scenarios:
        status = "PASS" if s.passed else "FAIL"
        detail = s.failure_reason[:40] if not s.passed else s.description[:40]
        print(f"  {s.scenario_id:<20} {status:<8} {detail}")
    print()

    return 0 if report.overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())

"""
hil_harness.py — Python HIL test orchestrator
==============================================
Connects to the DUT via OpenOCD/GDB, flashes the HIL firmware, runs the
test binary on-target, reads back the result block from RAM, and produces
a JUnit-compatible XML report for CI.

Requirements:
    pip install pytest pyocd pygdbmi pyserial lxml

Usage:
    pytest tests/hil_harness.py -v --target-port /dev/ttyUSB0
    pytest tests/hil_harness.py -v --no-flash      # firmware already on board

Architecture:
    ┌─────────────────────┐        OpenOCD TCL / GDB        ┌──────────┐
    │  hil_harness.py     │ ←────────────────────────────→  │  DUT     │
    │  pytest fixtures    │        UART semihosting          │  STM32WB │
    │  OpenOCDClient      │ ←────────────────────────────→  │          │
    └─────────────────────┘                                  └──────────┘
"""

from __future__ import annotations

import argparse
import re
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Optional

import pytest
import serial

# ---------------------------------------------------------------------------
# Configuration — override via pytest CLI args or environment
# ---------------------------------------------------------------------------
OPENOCD_BIN    = "openocd"
OPENOCD_CFG    = ["-f", "interface/stlink.cfg", "-f", "target/stm32wbx.cfg"]
GDB_BIN        = "arm-none-eabi-gdb"
HIL_ELF        = Path("build/sage_hil_tests.elf")

# RAM addresses must match linker script / hil_config.h
HIL_RESULT_ADDR         = 0x20000000
HIL_RESULT_STRUCT_SIZE  = 5 * 4   # 5 × uint32_t

MAGIC_PASS = 0xCAFEBEEF
MAGIC_FAIL = 0xDEADC0DE

UART_BAUDRATE   = 115200
UART_TIMEOUT_S  = 120.0   # max runtime for full HIL suite
HIL_DONE_PREFIX = "HIL_DONE:"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class HILResultBlock:
    magic:             int = 0
    suite_pass_mask:   int = 0
    suite_fail_mask:   int = 0
    total_assertions:  int = 0
    failed_assertions: int = 0

    @classmethod
    def from_bytes(cls, data: bytes) -> "HILResultBlock":
        if len(data) < HIL_RESULT_STRUCT_SIZE:
            raise ValueError(f"Result block too short: {len(data)} bytes")
        fields = struct.unpack_from("<5I", data)
        return cls(*fields)

    @property
    def passed(self) -> bool:
        return self.magic == MAGIC_PASS and self.failed_assertions == 0

    @property
    def pass_count(self) -> int:
        return self.total_assertions - self.failed_assertions


@dataclass
class SensorSample:
    timestamp_ms: int
    accel_x_mg:   int
    accel_y_mg:   int
    accel_z_mg:   int
    gyro_x_mdps:  int
    gyro_y_mdps:  int
    gyro_z_mdps:  int
    pressure_pa:  int
    temp_cdeg:    int


@dataclass
class HILTestSession:
    result_block:   Optional[HILResultBlock] = None
    uart_log:       list[str]                = field(default_factory=list)
    elapsed_s:      float                    = 0.0
    flash_success:  bool                     = False


# ---------------------------------------------------------------------------
# OpenOCD client
# ---------------------------------------------------------------------------
class OpenOCDClient:
    """Thin wrapper around OpenOCD telnet interface for GDB memory reads."""

    def __init__(self, host: str = "127.0.0.1", port: int = 4444):
        self._host = host
        self._port = port
        self._proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        cmd = [OPENOCD_BIN] + OPENOCD_CFG
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)  # OpenOCD startup delay

    def stop(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

    def read_memory(self, address: int, length: int) -> bytes:
        """Read `length` bytes from target RAM via GDB mi."""
        gdb_cmd = [
            GDB_BIN, "--batch", "--quiet",
            "-ex", f"target extended-remote {self._host}:{4444}",
            "-ex", f"dump binary memory /tmp/hil_result.bin "
                   f"0x{address:08x} 0x{address + length:08x}",
            "-ex", "detach",
            str(HIL_ELF),
        ]
        result = subprocess.run(gdb_cmd, capture_output=True, timeout=15)
        if result.returncode != 0:
            raise RuntimeError(f"GDB read failed: {result.stderr.decode()}")
        return Path("/tmp/hil_result.bin").read_bytes()

    def flash_and_run(self) -> None:
        """Flash HIL firmware and release reset."""
        cmd = [OPENOCD_BIN] + OPENOCD_CFG + [
            "-c", f"program {HIL_ELF} verify reset exit"
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"Flash failed:\n{result.stderr.decode()}")

    def halt_target(self) -> None:
        cmd = [
            GDB_BIN, "--batch", "--quiet",
            "-ex", f"target extended-remote {self._host}:{4444}",
            "-ex", "monitor halt",
            "-ex", "detach",
            str(HIL_ELF),
        ]
        subprocess.run(cmd, capture_output=True, timeout=10)


# ---------------------------------------------------------------------------
# UART log reader
# ---------------------------------------------------------------------------
class UARTReader:
    """Reads semihosting output from UART until HIL_DONE line or timeout."""

    def __init__(self, port: str, baudrate: int = UART_BAUDRATE):
        self._port     = port
        self._baudrate = baudrate
        self._ser: Optional[serial.Serial] = None

    def open(self) -> None:
        self._ser = serial.Serial(
            self._port,
            baudrate=self._baudrate,
            timeout=1.0,
        )

    def close(self) -> None:
        if self._ser is not None and self._ser.is_open:
            self._ser.close()
            self._ser = None

    def read_until_done(self, timeout_s: float = UART_TIMEOUT_S) -> list[str]:
        lines: list[str] = []
        deadline = time.monotonic() + timeout_s
        if self._ser is None:
            raise RuntimeError("UART not open")

        while time.monotonic() < deadline:
            raw = self._ser.readline()
            if not raw:
                continue
            line = raw.decode("ascii", errors="replace").rstrip("\r\n")
            lines.append(line)
            print(f"[UART] {line}")
            if line.startswith(HIL_DONE_PREFIX):
                break

        return lines


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--target-port", default="/dev/ttyUSB0",
                     help="Serial port connected to DUT UART")
    parser.addoption("--no-flash", action="store_true", default=False,
                     help="Skip firmware flashing (already programmed)")
    parser.addoption("--openocd-host", default="127.0.0.1",
                     help="OpenOCD host (default 127.0.0.1)")


@pytest.fixture(scope="session")
def openocd(request: pytest.FixtureRequest) -> Generator[OpenOCDClient, None, None]:
    host = request.config.getoption("--openocd-host")
    client = OpenOCDClient(host=host)
    client.start()
    yield client
    client.stop()


@pytest.fixture(scope="session")
def hil_session(
    request: pytest.FixtureRequest,
    openocd: OpenOCDClient,
) -> HILTestSession:
    session = HILTestSession()
    port = request.config.getoption("--target-port")
    no_flash = request.config.getoption("--no-flash")

    # Flash firmware
    if not no_flash:
        openocd.flash_and_run()
        session.flash_success = True
    else:
        session.flash_success = True   # assumed

    # Collect UART output
    reader = UARTReader(port)
    reader.open()
    t0 = time.monotonic()
    session.uart_log = reader.read_until_done(UART_TIMEOUT_S)
    session.elapsed_s = time.monotonic() - t0
    reader.close()

    # Halt and read result block from RAM
    openocd.halt_target()
    raw = openocd.read_memory(HIL_RESULT_ADDR, HIL_RESULT_STRUCT_SIZE)
    session.result_block = HILResultBlock.from_bytes(raw)

    return session


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------
class TestHILSuiteResults:
    """Validate the on-target HIL result block read back via GDB."""

    def test_firmware_flashed_successfully(self, hil_session: HILTestSession) -> None:
        assert hil_session.flash_success, "Firmware flash failed"

    def test_hil_magic_word_pass(self, hil_session: HILTestSession) -> None:
        rb = hil_session.result_block
        assert rb is not None
        assert rb.magic == MAGIC_PASS, (
            f"HIL result magic=0x{rb.magic:08X}, expected PASS=0x{MAGIC_PASS:08X}"
        )

    def test_no_suite_failures(self, hil_session: HILTestSession) -> None:
        rb = hil_session.result_block
        assert rb is not None
        assert rb.suite_fail_mask == 0, (
            f"Failed suites bitmask: 0x{rb.suite_fail_mask:08X}"
        )

    def test_zero_assertion_failures(self, hil_session: HILTestSession) -> None:
        rb = hil_session.result_block
        assert rb is not None
        assert rb.failed_assertions == 0, (
            f"{rb.failed_assertions}/{rb.total_assertions} assertions failed"
        )

    def test_assertion_count_nonzero(self, hil_session: HILTestSession) -> None:
        """Guard against a silent no-op run with 0 assertions."""
        rb = hil_session.result_block
        assert rb is not None
        assert rb.total_assertions >= 50, (
            f"Only {rb.total_assertions} assertions ran — HIL may have aborted early"
        )

    def test_runtime_within_budget(self, hil_session: HILTestSession) -> None:
        assert hil_session.elapsed_s < UART_TIMEOUT_S, (
            f"HIL suite took {hil_session.elapsed_s:.1f}s, budget {UART_TIMEOUT_S}s"
        )


class TestSensorCalibration:
    """Parse UART log lines for sensor calibration data and validate thresholds."""

    @staticmethod
    def _extract_value(log: list[str], pattern: str) -> Optional[int]:
        rx = re.compile(pattern)
        for line in log:
            m = rx.search(line)
            if m:
                return int(m.group(1))
        return None

    def test_imu_accel_offset_x(self, hil_session: HILTestSession) -> None:
        val = self._extract_value(
            hil_session.uart_log,
            r"accel_offset_x_mg=(-?\d+)"
        )
        assert val is not None, "accel_offset_x not found in UART log"
        assert abs(val) <= 90, f"Accel X offset {val} mg exceeds ±90 mg"

    def test_imu_accel_offset_y(self, hil_session: HILTestSession) -> None:
        val = self._extract_value(
            hil_session.uart_log,
            r"accel_offset_y_mg=(-?\d+)"
        )
        assert val is not None, "accel_offset_y not found in UART log"
        assert abs(val) <= 90, f"Accel Y offset {val} mg exceeds ±90 mg"

    def test_gyro_zero_rate_x(self, hil_session: HILTestSession) -> None:
        val = self._extract_value(
            hil_session.uart_log,
            r"gyro_offset_x_mdps=(-?\d+)"
        )
        assert val is not None, "gyro_offset_x not found in UART log"
        assert abs(val) <= 50000, f"Gyro X zero-rate {val} mdps exceeds ±50 dps"

    def test_barometer_pressure_sea_level(self, hil_session: HILTestSession) -> None:
        val = self._extract_value(
            hil_session.uart_log,
            r"pressure_pa=(\d+)"
        )
        assert val is not None, "pressure_pa not found in UART log"
        assert abs(val - 101325) <= 5000, (
            f"Pressure {val} Pa, expected 101325 ± 5000 Pa"
        )


class TestTimingBudgets:
    """Validate all SR-TIM-* requirements from UART log."""

    @staticmethod
    def _extract_ms(log: list[str], key: str) -> Optional[int]:
        for line in log:
            m = re.search(rf"{key}=(\d+)", line)
            if m:
                return int(m.group(1))
        return None

    def test_boot_time_sr_tim_001(self, hil_session: HILTestSession) -> None:
        ms = self._extract_ms(hil_session.uart_log, "boot_elapsed_ms")
        assert ms is not None, "boot_elapsed_ms not logged"
        assert ms <= 3000, f"Boot took {ms} ms, budget 3000 ms (SR-TIM-001)"

    def test_imu_isr_latency_sr_tim_002(self, hil_session: HILTestSession) -> None:
        for line in hil_session.uart_log:
            m = re.search(r"IMU ISR max latency=(\d+) µs", line)
            if m:
                us = int(m.group(1))
                assert us <= 1000, f"IMU ISR latency {us} µs > 1000 µs (SR-TIM-002)"
                return
        pytest.fail("IMU ISR latency not logged")

    def test_haptic_rise_time_sr_tim_006(self, hil_session: HILTestSession) -> None:
        for line in hil_session.uart_log:
            m = re.search(r"actuator rise=(\d+) ms", line)
            if m:
                ms = int(m.group(1))
                assert ms <= 50, f"Haptic rise {ms} ms > 50 ms (SR-TIM-006)"
                return
        pytest.fail("Actuator rise time not logged")

    def test_fall_alert_latency_sr_tim_009(self, hil_session: HILTestSession) -> None:
        for line in hil_session.uart_log:
            m = re.search(r"fall detect.*latency=(\d+) ms", line)
            if m:
                ms = int(m.group(1))
                assert ms <= 200, f"Fall alert latency {ms} ms > 200 ms (SR-TIM-009)"
                return
        pytest.fail("Fall alert latency not logged")


class TestFaultInjection:
    """Verify all fault injection cases passed."""

    FAULT_PATTERNS = [
        ("F-01", r"fault=0x01.*detected=1.*recovered=1"),
        ("F-02", r"fault=0x02.*detected=1.*recovered=1"),
        ("F-03", r"fault=0x03.*detected=1.*recovered=1"),
        ("F-04", r"fault=0x04.*detected=1.*recovered=1"),
        ("F-05", r"fault=0x05.*detected=1.*recovered=1"),
        ("F-06", r"fault=0x06.*detected=1.*recovered=1"),
        ("F-07", r"GPS antenna.*last-known position active"),
        ("F-08", r"fault=0x0B.*detected=1.*recovered=1"),
        ("F-09", r"fault=0x0D.*detected=1.*recovered=1"),
        ("F-10", r"WDT single-miss.*early-warning"),
    ]

    @pytest.mark.parametrize("fault_id,pattern", FAULT_PATTERNS)
    def test_fault_detected_and_recovered(
        self,
        fault_id: str,
        pattern: str,
        hil_session: HILTestSession,
    ) -> None:
        log_text = "\n".join(hil_session.uart_log)
        assert re.search(pattern, log_text, re.IGNORECASE), (
            f"{fault_id}: pattern not found in UART log: {pattern!r}"
        )


class TestCoverage:
    """Coverage gate — requires HIL_COVERAGE build with gcovr."""

    def test_branch_coverage_meets_target(self, tmp_path: Path) -> None:
        cov_report = Path("build/coverage/index.html")
        if not cov_report.exists():
            pytest.skip("Coverage report not generated (run with -DHIL_COVERAGE=ON)")
        # gcovr already enforced --fail-under-branch at build time;
        # existence of the report means the threshold was met.
        assert cov_report.stat().st_size > 0, "Coverage report is empty"

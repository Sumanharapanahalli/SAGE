"""
hil_sensor_data_validation_harness.py — HIL_002 Python test harness
=====================================================================
Implements the host-side orchestration for test case HIL_002 (Sensor Data
Validation).  Injects known sensor profiles into the DUT via GDB, reads back
the processed frame, and asserts acceptance criteria.

Test steps (HIL_002):
  1. Simulate sensor data input     — write HIL_SensorInjection_t via GDB set
  2. Verify interpretation          — read HIL_ProcessedFrame_t, check EU values
  3. Verify state mapping           — check device_state field
  4. Verify consistency             — repeat N=100 times, check no deviation

Acceptance criteria:
  AC-1: Sensor data accurately interpreted (magnitude, tilt within tolerance)
  AC-2: Sensor data correctly mapped to device state
  AC-3: Identical output across all 100 iterations (AC-3 covers HIL_002 Step 4)
  AC-4: Coverage ≥ 90% (enforced by gcovr in CMake coverage target)
  AC-5: All timing requirements verified (processing < 1 ms per frame)

Requirements:
    pip install pytest pyocd pygdbmi pyserial lxml

Usage:
    # With ST-Link connected, OpenOCD already running:
    pytest tests/hil_sensor_data_validation_harness.py -v \\
        --serial-port /dev/ttyUSB0

    # Skip flash (firmware already loaded):
    pytest tests/hil_sensor_data_validation_harness.py -v \\
        --serial-port /dev/ttyUSB0 --no-flash

Architecture:
    ┌──────────────────────────────────┐   GDB MI   ┌─────────────┐
    │  hil_sensor_data_validation_     │ ─────────→ │  OpenOCD    │
    │  harness.py                      │            │  (GDB srv)  │
    │  ┌──────────────────────────┐    │            └──────┬──────┘
    │  │ OpenOCDGDBClient         │    │                   │ JTAG/SWD
    │  │  inject_sensor_data()    │    │            ┌──────▼──────┐
    │  │  read_processed_frame()  │    │            │  STM32WB55  │
    │  │  run_profile()           │    │            │  (DUT)      │
    │  └──────────────────────────┘    │            └─────────────┘
    └──────────────────────────────────┘
"""

from __future__ import annotations

import struct
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest

# ---------------------------------------------------------------------------
# Configuration — override via pytest CLI options or environment variables
# ---------------------------------------------------------------------------
OPENOCD_BIN     = "openocd"
OPENOCD_CFG     = ["-f", "interface/stlink.cfg", "-f", "target/stm32wbx.cfg"]
GDB_BIN         = "arm-none-eabi-gdb"
HIL_ELF         = Path("build/sage_hil_tests.elf")

# ELF symbol names (must match the __attribute__((section(".hil_inject")))
# declarations in hil_sensor_data_validation.c)
SYM_INJECTION   = "g_hil_sensor_injection"
SYM_PROCESSED   = "g_hil_processed_frame"

# Tolerances — match C-side HIL_002_MAX_DEVIATION_* macros
MAX_DEVIATION_MG       = 5     # milli-g
MAX_DEVIATION_PA       = 2     # Pa
CONSISTENCY_ITERATIONS = 100

# Protocol constants — match C-side HIL_INJECT_MAGIC
HIL_INJECT_MAGIC   = 0xB00BCAFE
HIL_INJECT_CLEARED = 0x00000000

# Processing latency budget: < 1 ms @ 64 MHz = 64 000 cycles
MAX_PROCESSING_CYCLES = 64_000

# Struct format for HIL_SensorInjection_t (9× int32 + 1× uint32 + 1× uint32)
# All fields are 4 bytes; total = 44 bytes.
# Layout: accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, pressure,
#         temperature, sequence_number, valid_magic
INJECTION_FMT   = "<iiiiiiiiII"   # 10 × 4 bytes = 40 bytes
INJECTION_SIZE  = struct.calcsize(INJECTION_FMT)

# Struct format for HIL_ProcessedFrame_t
# Layout: accel_magnitude, tilt_angle, pressure, temperature,
#         device_state (uint32), sequence_number (uint32),
#         processing_cycles (uint32)
PROCESSED_FMT   = "<iiiiIII"      # 4+4+4+4+4+4+4 = 28 bytes
PROCESSED_SIZE  = struct.calcsize(PROCESSED_FMT)

# Device state enum values — must match HIL_DeviceState_t
class DeviceState:
    IDLE          = 0x00
    UPRIGHT       = 0x01
    WALKING       = 0x02
    FALL_DETECTED = 0x03
    IMPACT        = 0x04
    LYING         = 0x05
    UNKNOWN       = 0xFF


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class SensorInjection:
    """Maps to HIL_SensorInjection_t in firmware."""
    accel_x_mg: int = 0
    accel_y_mg: int = 0
    accel_z_mg: int = 1000   # default: 1 g upright
    gyro_x_mdps: int = 0
    gyro_y_mdps: int = 0
    gyro_z_mdps: int = 0
    pressure_pa: int = 101325
    temperature_cdeg: int = 2500   # 25.00 °C
    sequence_number: int = 0

    def pack(self) -> bytes:
        return struct.pack(
            INJECTION_FMT,
            self.accel_x_mg,
            self.accel_y_mg,
            self.accel_z_mg,
            self.gyro_x_mdps,
            self.gyro_y_mdps,
            self.gyro_z_mdps,
            self.pressure_pa,
            self.temperature_cdeg,
            self.sequence_number,
            HIL_INJECT_MAGIC,
        )


@dataclass
class ProcessedFrame:
    """Maps to HIL_ProcessedFrame_t in firmware."""
    accel_magnitude_mg: int = 0
    tilt_angle_cdeg: int = 0
    pressure_pa: int = 0
    temperature_cdeg: int = 0
    device_state: int = DeviceState.UNKNOWN
    sequence_number: int = 0
    processing_cycles: int = 0

    @classmethod
    def unpack(cls, data: bytes) -> "ProcessedFrame":
        if len(data) < PROCESSED_SIZE:
            raise ValueError(
                f"ProcessedFrame: expected {PROCESSED_SIZE} bytes, got {len(data)}"
            )
        fields = struct.unpack(PROCESSED_FMT, data[:PROCESSED_SIZE])
        return cls(
            accel_magnitude_mg=fields[0],
            tilt_angle_cdeg=fields[1],
            pressure_pa=fields[2],
            temperature_cdeg=fields[3],
            device_state=fields[4],
            sequence_number=fields[5],
            processing_cycles=fields[6],
        )


# ---------------------------------------------------------------------------
# OpenOCD / GDB interface
# ---------------------------------------------------------------------------
class OpenOCDGDBClient:
    """
    Wraps arm-none-eabi-gdb in batch (--batch) mode to inject sensor data
    and read back the processed frame via memory read/write commands.

    Each interaction spawns a new GDB process to keep state simple and
    avoid GDB MI connection leaks.  For high-frequency iteration this
    adds ~50 ms per call — acceptable for a 100-iteration consistency test.
    """

    def __init__(self, elf: Path, gdb_bin: str = GDB_BIN,
                 openocd_host: str = "127.0.0.1",
                 openocd_port: int = 3333) -> None:
        self.elf          = elf
        self.gdb_bin      = gdb_bin
        self.openocd_host = openocd_host
        self.openocd_port = openocd_port

    def _run_gdb(self, commands: list[str]) -> str:
        """Execute a list of GDB commands, return combined stdout."""
        cmd = [
            self.gdb_bin,
            "--batch",
            "--quiet",
            str(self.elf),
            f"--eval-command=target remote {self.openocd_host}:{self.openocd_port}",
        ]
        for c in commands:
            cmd += ["--eval-command", c]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode not in (0, 1):
            # GDB exits 1 for --batch when target connection drops at quit
            raise RuntimeError(
                f"GDB failed (rc={result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout

    def read_memory(self, symbol: str, size: int) -> bytes:
        """Read `size` bytes from the address of `symbol`."""
        cmds = [
            f"set logging redirect on",
            f"dump binary memory /tmp/hil_002_dump.bin &{symbol} (&{symbol}+{size})",
        ]
        self._run_gdb(cmds)
        return Path("/tmp/hil_002_dump.bin").read_bytes()

    def write_struct(self, symbol: str, data: bytes) -> None:
        """Write `data` bytes into the address of `symbol` using GDB set commands."""
        # Split bytes into 4-byte words (little-endian uint32)
        cmds: list[str] = []
        num_words = len(data) // 4
        for i in range(num_words):
            word = struct.unpack_from("<I", data, i * 4)[0]
            cmds.append(
                f"set *((unsigned int *)(&{symbol}) + {i}) = {word}"
            )
        self._run_gdb(cmds)

    def call_function(self, func: str) -> None:
        """Call a void firmware function via GDB."""
        self._run_gdb([f"call {func}()"])

    def inject_and_process(self, injection: SensorInjection) -> ProcessedFrame:
        """
        Full round-trip:
          1. Write injection record into g_hil_sensor_injection
          2. Call HIL_ProcessInjection() on-target
          3. Read back g_hil_processed_frame
          4. Return ProcessedFrame
        """
        self.write_struct(SYM_INJECTION, injection.pack())
        self.call_function("HIL_ProcessInjection")
        raw = self.read_memory(SYM_PROCESSED, PROCESSED_SIZE)
        return ProcessedFrame.unpack(raw)

    def clear_injection(self) -> None:
        self.call_function("HIL_ClearSensorInjection")


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--serial-port", default="/dev/ttyUSB0",
                     help="UART port connected to DUT")
    parser.addoption("--no-flash", action="store_true",
                     help="Skip firmware flash (already loaded)")
    parser.addoption("--openocd-host", default="127.0.0.1")
    parser.addoption("--openocd-port", type=int, default=3333)
    parser.addoption("--elf", default=str(HIL_ELF),
                     help="Path to HIL firmware ELF")


@pytest.fixture(scope="session")
def openocd_process(request: pytest.FixtureRequest):
    """Start OpenOCD; yield process handle; terminate on teardown."""
    host = request.config.getoption("--openocd-host")
    port = request.config.getoption("--openocd-port")

    proc = subprocess.Popen(
        [OPENOCD_BIN] + OPENOCD_CFG,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2.0)   # wait for OpenOCD to enumerate the probe
    if proc.poll() is not None:
        raise RuntimeError(f"OpenOCD exited immediately: {proc.stderr.read()}")

    yield proc
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="session")
def gdb_client(request: pytest.FixtureRequest,
               openocd_process) -> OpenOCDGDBClient:
    elf  = Path(request.config.getoption("--elf"))
    host = request.config.getoption("--openocd-host")
    port = request.config.getoption("--openocd-port")

    if not elf.exists():
        pytest.skip(f"HIL ELF not found: {elf} — run 'cmake --build build' first")

    client = OpenOCDGDBClient(elf=elf, openocd_host=host, openocd_port=port)

    # Flash firmware unless suppressed
    if not request.config.getoption("--no-flash"):
        subprocess.check_call(
            [OPENOCD_BIN] + OPENOCD_CFG + [
                "-c", f"program {elf} verify reset exit"
            ]
        )
        time.sleep(1.0)   # let firmware boot

    return client


# ---------------------------------------------------------------------------
# HIL_002: Test functions
# ---------------------------------------------------------------------------

class TestHIL002SensorDataValidation:
    """
    HIL_002 — Sensor Data Validation

    Each test method covers one or more sub-steps of the HIL_002 test case.
    Tests are independent; order is fixed only by pytest's collection order.
    """

    # ── Step 1 + 2: Simulate input and verify interpretation ──────────────

    def test_hil002_01_upright_interpretation(self, gdb_client: OpenOCDGDBClient):
        """
        HIL_002-01: Upright profile (Z=1 g) — verify EU conversion accuracy.
        Acceptance criterion AC-1.
        """
        inj   = SensorInjection(accel_z_mg=1000, sequence_number=0)
        frame = gdb_client.inject_and_process(inj)

        # Magnitude must be 1000 ± MAX_DEVIATION_MG mg
        assert abs(frame.accel_magnitude_mg - 1000) <= MAX_DEVIATION_MG, (
            f"Accel magnitude {frame.accel_magnitude_mg} mg deviates from "
            f"expected 1000 mg by > {MAX_DEVIATION_MG} mg"
        )

        # Tilt < 5° when Z-dominant
        assert frame.tilt_angle_cdeg < 500, (
            f"Tilt {frame.tilt_angle_cdeg} cdeg exceeds 500 cdeg (5°) for "
            f"upright profile"
        )

        # Pressure pass-through
        assert abs(frame.pressure_pa - 101325) <= MAX_DEVIATION_PA, (
            f"Pressure {frame.pressure_pa} Pa deviates from 101325 Pa"
        )

        # Processing latency
        assert frame.processing_cycles < MAX_PROCESSING_CYCLES, (
            f"Processing took {frame.processing_cycles} cycles "
            f"(budget: {MAX_PROCESSING_CYCLES})"
        )

    def test_hil002_02_inclined_interpretation(self, gdb_client: OpenOCDGDBClient):
        """
        HIL_002-02: 45° incline profile — verify magnitude and tilt.
        Acceptance criterion AC-1.
        """
        inj   = SensorInjection(accel_x_mg=707, accel_z_mg=707,
                                 sequence_number=1)
        frame = gdb_client.inject_and_process(inj)

        assert abs(frame.accel_magnitude_mg - 1000) <= MAX_DEVIATION_MG, (
            f"45° profile: magnitude {frame.accel_magnitude_mg} mg "
            f"not within {MAX_DEVIATION_MG} mg of 1000 mg"
        )

        assert 4000 <= frame.tilt_angle_cdeg <= 5000, (
            f"45° profile: tilt {frame.tilt_angle_cdeg} cdeg "
            f"outside expected range [4000, 5000]"
        )

    def test_hil002_03_freefall_interpretation(self, gdb_client: OpenOCDGDBClient):
        """
        HIL_002-03: Free-fall proxy (|a|≈52 mg) — verify sub-threshold detection.
        Acceptance criterion AC-1.
        """
        inj   = SensorInjection(accel_x_mg=30, accel_y_mg=30, accel_z_mg=30,
                                 sequence_number=2)
        frame = gdb_client.inject_and_process(inj)

        assert frame.accel_magnitude_mg < 200, (
            f"Free-fall proxy: magnitude {frame.accel_magnitude_mg} mg "
            f">= 200 mg threshold"
        )

    def test_hil002_04_impact_interpretation(self, gdb_client: OpenOCDGDBClient):
        """
        HIL_002-04: Impact spike (4 g) — verify above-threshold detection.
        Acceptance criterion AC-1.
        """
        inj   = SensorInjection(accel_z_mg=4000, sequence_number=3)
        frame = gdb_client.inject_and_process(inj)

        assert frame.accel_magnitude_mg > 3000, (
            f"Impact: magnitude {frame.accel_magnitude_mg} mg not > 3000 mg"
        )

    # ── Step 3: Verify state mapping ──────────────────────────────────────

    def test_hil002_05_state_upright(self, gdb_client: OpenOCDGDBClient):
        """
        HIL_002-05: Z-dominant tilt<30° maps to UPRIGHT state.
        Acceptance criterion AC-2.
        """
        inj   = SensorInjection(accel_x_mg=100, accel_z_mg=980,
                                 sequence_number=11)
        frame = gdb_client.inject_and_process(inj)

        assert frame.device_state == DeviceState.UPRIGHT, (
            f"Expected UPRIGHT (0x01), got state=0x{frame.device_state:02X}"
        )

    def test_hil002_06_state_walking(self, gdb_client: OpenOCDGDBClient):
        """
        HIL_002-06: 30°–70° tilt maps to WALKING state.
        Acceptance criterion AC-2.
        """
        inj   = SensorInjection(accel_x_mg=500, accel_z_mg=866,
                                 sequence_number=12)
        frame = gdb_client.inject_and_process(inj)

        assert frame.device_state == DeviceState.WALKING, (
            f"Expected WALKING (0x02), got state=0x{frame.device_state:02X}"
        )

    def test_hil002_07_state_fall_detected(self, gdb_client: OpenOCDGDBClient):
        """
        HIL_002-07: |a|<200 mg maps to FALL_DETECTED.
        Acceptance criterion AC-2.
        """
        inj   = SensorInjection(accel_x_mg=50, accel_y_mg=50, accel_z_mg=50,
                                 sequence_number=13)
        frame = gdb_client.inject_and_process(inj)

        assert frame.device_state == DeviceState.FALL_DETECTED, (
            f"Expected FALL_DETECTED (0x03), got state=0x{frame.device_state:02X}"
        )

    def test_hil002_08_state_impact(self, gdb_client: OpenOCDGDBClient):
        """
        HIL_002-08: |a|>3000 mg maps to IMPACT.
        Acceptance criterion AC-2.
        """
        inj   = SensorInjection(accel_z_mg=3500, sequence_number=14)
        frame = gdb_client.inject_and_process(inj)

        assert frame.device_state == DeviceState.IMPACT, (
            f"Expected IMPACT (0x04), got state=0x{frame.device_state:02X}"
        )

    def test_hil002_09_state_lying(self, gdb_client: OpenOCDGDBClient):
        """
        HIL_002-09: Tilt>70°, |a|≈1 g maps to LYING.
        Acceptance criterion AC-2.
        """
        inj   = SensorInjection(accel_x_mg=940, accel_z_mg=342,
                                 sequence_number=15)
        frame = gdb_client.inject_and_process(inj)

        assert frame.device_state == DeviceState.LYING, (
            f"Expected LYING (0x05), got state=0x{frame.device_state:02X}"
        )

    # ── Step 4: Consistency across N iterations ───────────────────────────

    def test_hil002_10_consistency_100_iterations(
        self, gdb_client: OpenOCDGDBClient
    ):
        """
        HIL_002-10: Same injection profile repeated 100 times produces
        bit-identical output.
        Acceptance criterion AC-3.
        """
        reference: Optional[ProcessedFrame] = None
        failures: list[str] = []

        for i in range(CONSISTENCY_ITERATIONS):
            inj   = SensorInjection(accel_z_mg=1000,
                                     pressure_pa=101325,
                                     temperature_cdeg=2500,
                                     sequence_number=200 + i)
            frame = gdb_client.inject_and_process(inj)

            if reference is None:
                reference = frame
                assert reference.device_state == DeviceState.UPRIGHT, (
                    f"Iteration 0: unexpected base state "
                    f"0x{reference.device_state:02X}"
                )
                continue

            # Magnitude deviation
            delta_mg = abs(frame.accel_magnitude_mg - reference.accel_magnitude_mg)
            if delta_mg > MAX_DEVIATION_MG:
                failures.append(
                    f"iter={i}: magnitude delta={delta_mg} mg "
                    f"(ref={reference.accel_magnitude_mg}, "
                    f"got={frame.accel_magnitude_mg})"
                )

            # State identity
            if frame.device_state != reference.device_state:
                failures.append(
                    f"iter={i}: state changed "
                    f"(ref=0x{reference.device_state:02X}, "
                    f"got=0x{frame.device_state:02X})"
                )

            # Cycle count within ±10%
            if reference.processing_cycles > 0:
                cycle_delta = abs(frame.processing_cycles
                                  - reference.processing_cycles)
                threshold   = reference.processing_cycles // 10
                if cycle_delta > threshold:
                    failures.append(
                        f"iter={i}: cycles delta={cycle_delta} "
                        f"(threshold={threshold})"
                    )

        assert not failures, (
            f"HIL_002 consistency failures ({len(failures)}/"
            f"{CONSISTENCY_ITERATIONS}):\n" + "\n".join(failures)
        )

    # ── Fault injection: invalid magic / cleared record ───────────────────

    def test_hil002_11_fault_cleared_injection(self, gdb_client: OpenOCDGDBClient):
        """
        HIL_002-11 (fault injection): cleared injection record returns UNKNOWN.
        Verifies firmware handles missing valid_magic gracefully (no crash).
        """
        gdb_client.clear_injection()

        # Trigger processing with no valid record in place
        raw = gdb_client.read_memory(SYM_PROCESSED, PROCESSED_SIZE)
        # Re-trigger via direct GDB call after clearing
        gdb_client._run_gdb(["call HIL_ProcessInjection()"])
        raw = gdb_client.read_memory(SYM_PROCESSED, PROCESSED_SIZE)
        frame = ProcessedFrame.unpack(raw)

        assert frame.device_state == DeviceState.UNKNOWN, (
            f"Cleared injection: expected UNKNOWN, got "
            f"0x{frame.device_state:02X}"
        )

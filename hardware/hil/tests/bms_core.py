"""bms_core.py — Pure-Python model of BMS core logic.

Mirrors the thresholds and state machine defined in bms_types.h / bms_hal.h so
that fault-detection, SOC estimation, balancing, and state-transition rules can
be unit-tested without requiring the ARM toolchain or real hardware.

All constants match bms_types.h exactly — update both files together.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants (mirrors bms_types.h)
# ---------------------------------------------------------------------------
BMS_MAX_CELLS: int = 16
BMS_MAX_TEMP_SENSORS: int = 8

# Voltage thresholds (mV)
BMS_CELL_OV_THRESHOLD_MV: int = 4200
BMS_CELL_UV_THRESHOLD_MV: int = 2800

# Current threshold (mA, positive = discharge)
BMS_OC_THRESHOLD_MA: int = 50_000  # 50 A

# Temperature thresholds (degC × 10)
BMS_MAX_TEMP_DEGC_X10: int = 600   # 60.0 °C
BMS_MIN_TEMP_DEGC_X10: int = -200  # -20.0 °C

# Balancing delta (mV)
BMS_BAL_THRESHOLD_MV: int = 20

# ADC timeout (ms)
BMS_ADC_TIMEOUT_MS: int = 10


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class BMSState(enum.IntEnum):
    INIT        = 0x00
    IDLE        = 0x01
    CHARGING    = 0x02
    DISCHARGING = 0x03
    FAULT       = 0x04
    SHUTDOWN    = 0x05


class BMSFault(enum.IntFlag):
    NONE         = 0x000
    OVERVOLTAGE  = 0x001
    UNDERVOLTAGE = 0x002
    OVERCURRENT  = 0x004
    OVERTEMP     = 0x008
    UNDERTEMP    = 0x010
    COMM         = 0x020
    ADC          = 0x040
    INTERNAL     = 0x080
    BALANCER     = 0x100
    PRECHARGE    = 0x200


class BMSStatus(enum.IntEnum):
    OK      = 0x00
    ERROR   = 0x01
    BUSY    = 0x02
    TIMEOUT = 0x03


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class BMSConfig:
    num_cells: int = 4
    num_temp_sensors: int = 2
    cell_capacity_mah: int = 3000
    ov_threshold_mv: int = BMS_CELL_OV_THRESHOLD_MV
    uv_threshold_mv: int = BMS_CELL_UV_THRESHOLD_MV
    oc_threshold_ma: int = BMS_OC_THRESHOLD_MA
    max_temp_degc_x10: int = BMS_MAX_TEMP_DEGC_X10
    min_temp_degc_x10: int = BMS_MIN_TEMP_DEGC_X10
    balancing_threshold_mv: int = BMS_BAL_THRESHOLD_MV

    def validate(self) -> None:
        """Raise ValueError for any invalid configuration."""
        if not (1 <= self.num_cells <= BMS_MAX_CELLS):
            raise ValueError(
                f"num_cells {self.num_cells} out of range [1, {BMS_MAX_CELLS}]"
            )
        if not (1 <= self.num_temp_sensors <= BMS_MAX_TEMP_SENSORS):
            raise ValueError(
                f"num_temp_sensors {self.num_temp_sensors} out of range "
                f"[1, {BMS_MAX_TEMP_SENSORS}]"
            )
        if self.cell_capacity_mah <= 0:
            raise ValueError("cell_capacity_mah must be positive")
        if self.uv_threshold_mv >= self.ov_threshold_mv:
            raise ValueError(
                "uv_threshold_mv must be strictly less than ov_threshold_mv"
            )
        if self.min_temp_degc_x10 >= self.max_temp_degc_x10:
            raise ValueError(
                "min_temp_degc_x10 must be strictly less than max_temp_degc_x10"
            )
        if self.oc_threshold_ma <= 0:
            raise ValueError("oc_threshold_ma must be positive")
        if self.balancing_threshold_mv < 0:
            raise ValueError("balancing_threshold_mv must be non-negative")


@dataclass
class BMSData:
    cell_voltage_mv: List[int] = field(default_factory=list)
    temperature_degc_x10: List[int] = field(default_factory=list)
    pack_current_ma: int = 0   # positive = discharge
    pack_voltage_mv: int = 0
    soc_percent: int = 0       # 0-100
    soh_percent: int = 100     # 0-100
    state: BMSState = BMSState.INIT
    fault_flags: BMSFault = BMSFault.NONE
    timestamp_ms: int = 0


# ---------------------------------------------------------------------------
# Cell statistics
# ---------------------------------------------------------------------------
@dataclass
class CellStats:
    min_mv: int
    max_mv: int
    avg_mv: float
    delta_mv: int  # max - min

    @classmethod
    def from_voltages(cls, voltages: List[int]) -> "CellStats":
        if not voltages:
            raise ValueError("voltage list must not be empty")
        mn = min(voltages)
        mx = max(voltages)
        return cls(
            min_mv=mn,
            max_mv=mx,
            avg_mv=sum(voltages) / len(voltages),
            delta_mv=mx - mn,
        )


# ---------------------------------------------------------------------------
# BMSCore — fault detection, state machine, SOC, balancing
# ---------------------------------------------------------------------------
class BMSCore:
    """Pure-Python implementation of BMS core logic.

    Intended for unit testing and simulation.  All methods are stateless
    (or explicit about state) so they can be tested in isolation.
    """

    def __init__(self, config: BMSConfig) -> None:
        config.validate()
        self._cfg = config
        self._state: BMSState = BMSState.INIT
        self._fault_flags: BMSFault = BMSFault.NONE

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def state(self) -> BMSState:
        return self._state

    @property
    def fault_flags(self) -> BMSFault:
        return self._fault_flags

    @property
    def config(self) -> BMSConfig:
        return self._cfg

    # ------------------------------------------------------------------
    # Fault detection (pure — does not mutate state)
    # ------------------------------------------------------------------
    def detect_faults(self, data: BMSData) -> BMSFault:
        """Evaluate *data* against configured thresholds.

        Returns the combined fault flag set.  Does not mutate internal state.
        """
        faults = BMSFault.NONE

        # Cell voltage faults
        for v in data.cell_voltage_mv:
            if v > self._cfg.ov_threshold_mv:
                faults |= BMSFault.OVERVOLTAGE
            if v < self._cfg.uv_threshold_mv:
                faults |= BMSFault.UNDERVOLTAGE

        # Current fault (magnitude — both charge and discharge)
        if abs(data.pack_current_ma) > self._cfg.oc_threshold_ma:
            faults |= BMSFault.OVERCURRENT

        # Temperature faults
        for t in data.temperature_degc_x10:
            if t > self._cfg.max_temp_degc_x10:
                faults |= BMSFault.OVERTEMP
            if t < self._cfg.min_temp_degc_x10:
                faults |= BMSFault.UNDERTEMP

        return faults

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def transition(self, data: BMSData) -> BMSState:
        """Compute the next state from current state and data.

        Rules:
          INIT  → IDLE   always (after init call)
          IDLE  → CHARGING    if pack_current_ma < 0 (current flowing in)
          IDLE  → DISCHARGING if pack_current_ma > 0
          any   → FAULT  if fault_flags != NONE
          FAULT → IDLE   if fault_flags cleared externally
          any   → SHUTDOWN if requested explicitly via data.state
        """
        faults = self.detect_faults(data)
        self._fault_flags = faults

        if data.state == BMSState.SHUTDOWN:
            self._state = BMSState.SHUTDOWN
            return self._state

        if faults != BMSFault.NONE:
            self._state = BMSState.FAULT
            return self._state

        if self._state == BMSState.FAULT:
            # Allow recovery only when all faults cleared
            self._state = BMSState.IDLE
            return self._state

        if self._state == BMSState.INIT:
            self._state = BMSState.IDLE
            return self._state

        if self._state in (BMSState.IDLE, BMSState.CHARGING, BMSState.DISCHARGING):
            if data.pack_current_ma < 0:
                self._state = BMSState.CHARGING
            elif data.pack_current_ma > 0:
                self._state = BMSState.DISCHARGING
            else:
                self._state = BMSState.IDLE

        return self._state

    # ------------------------------------------------------------------
    # SOC estimation (voltage-based, simplified OCV curve)
    # ------------------------------------------------------------------
    @staticmethod
    def estimate_soc_percent(avg_cell_mv: float) -> int:
        """Map average open-circuit cell voltage to SOC (0-100%).

        Uses a piecewise-linear approximation of a typical Li-ion OCV curve.
        Replace with a lookup table or Coulomb counter for production.
        """
        # (mV, soc%) breakpoints — typical LFP/NMC blend
        breakpoints: List[Tuple[float, float]] = [
            (2800.0,  0.0),
            (3200.0, 10.0),
            (3500.0, 30.0),
            (3700.0, 60.0),
            (3900.0, 80.0),
            (4100.0, 95.0),
            (4200.0, 100.0),
        ]
        if avg_cell_mv <= breakpoints[0][0]:
            return 0
        if avg_cell_mv >= breakpoints[-1][0]:
            return 100

        for i in range(1, len(breakpoints)):
            v_lo, s_lo = breakpoints[i - 1]
            v_hi, s_hi = breakpoints[i]
            if v_lo <= avg_cell_mv <= v_hi:
                ratio = (avg_cell_mv - v_lo) / (v_hi - v_lo)
                soc = s_lo + ratio * (s_hi - s_lo)
                return max(0, min(100, round(soc)))

        return 0  # unreachable but satisfies type checker

    # ------------------------------------------------------------------
    # Balancing
    # ------------------------------------------------------------------
    def compute_balance_mask(self, voltages: List[int]) -> int:
        """Return a bitmask of cells that should be bled (bit N = cell N).

        A cell is marked for balancing when its voltage exceeds the minimum
        cell voltage by more than *balancing_threshold_mv*.
        """
        if not voltages:
            return 0
        v_min = min(voltages)
        mask = 0
        for i, v in enumerate(voltages):
            if (v - v_min) > self._cfg.balancing_threshold_mv:
                mask |= (1 << i)
        return mask

    # ------------------------------------------------------------------
    # Pack-level helpers
    # ------------------------------------------------------------------
    @staticmethod
    def compute_pack_voltage(cell_voltages: List[int]) -> int:
        """Sum series-connected cell voltages to produce pack voltage (mV)."""
        return sum(cell_voltages)

    @staticmethod
    def cell_stats(voltages: List[int]) -> CellStats:
        return CellStats.from_voltages(voltages)

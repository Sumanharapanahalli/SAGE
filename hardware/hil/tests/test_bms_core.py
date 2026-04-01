"""test_bms_core.py — Unit tests for BMS core logic (bms_core.py).

Coverage targets
----------------
* Happy paths  — nominal readings, correct fault detection, state transitions
* Error paths  — out-of-range inputs, invalid config, edge-case faults
* No hardcoded test data — all values derived from fixtures / factories

Run with::

    pytest hardware/hil/tests/test_bms_core.py -v
"""

from __future__ import annotations

import math
from typing import List

import pytest

from bms_core import (
    BMS_BAL_THRESHOLD_MV,
    BMS_CELL_OV_THRESHOLD_MV,
    BMS_CELL_UV_THRESHOLD_MV,
    BMS_MAX_CELLS,
    BMS_MAX_TEMP_DEGC_X10,
    BMS_MAX_TEMP_SENSORS,
    BMS_MIN_TEMP_DEGC_X10,
    BMS_OC_THRESHOLD_MA,
    BMSConfig,
    BMSCore,
    BMSData,
    BMSFault,
    BMSState,
    CellStats,
)


# ===========================================================================
# Factories — no hardcoded literals scattered through tests
# ===========================================================================

def make_config(
    num_cells: int = 4,
    num_temp_sensors: int = 2,
    cell_capacity_mah: int = 3000,
    ov_threshold_mv: int = BMS_CELL_OV_THRESHOLD_MV,
    uv_threshold_mv: int = BMS_CELL_UV_THRESHOLD_MV,
    oc_threshold_ma: int = BMS_OC_THRESHOLD_MA,
    max_temp_degc_x10: int = BMS_MAX_TEMP_DEGC_X10,
    min_temp_degc_x10: int = BMS_MIN_TEMP_DEGC_X10,
    balancing_threshold_mv: int = BMS_BAL_THRESHOLD_MV,
) -> BMSConfig:
    return BMSConfig(
        num_cells=num_cells,
        num_temp_sensors=num_temp_sensors,
        cell_capacity_mah=cell_capacity_mah,
        ov_threshold_mv=ov_threshold_mv,
        uv_threshold_mv=uv_threshold_mv,
        oc_threshold_ma=oc_threshold_ma,
        max_temp_degc_x10=max_temp_degc_x10,
        min_temp_degc_x10=min_temp_degc_x10,
        balancing_threshold_mv=balancing_threshold_mv,
    )


def nominal_voltages(num_cells: int, mv: int | None = None) -> List[int]:
    """Return a list of identical nominal voltages, defaulting to mid-range."""
    mid = (BMS_CELL_OV_THRESHOLD_MV + BMS_CELL_UV_THRESHOLD_MV) // 2
    return [mv if mv is not None else mid] * num_cells


def nominal_temps(num_sensors: int) -> List[int]:
    """Return nominal temperatures well within limits (in degC x10)."""
    nominal = (BMS_MAX_TEMP_DEGC_X10 + BMS_MIN_TEMP_DEGC_X10) // 2
    return [nominal] * num_sensors


def make_data(
    num_cells: int = 4,
    num_temp_sensors: int = 2,
    cell_mv: int | None = None,
    current_ma: int = 0,
    state: BMSState = BMSState.IDLE,
) -> BMSData:
    voltages = nominal_voltages(num_cells, cell_mv)
    return BMSData(
        cell_voltage_mv=voltages,
        temperature_degc_x10=nominal_temps(num_temp_sensors),
        pack_current_ma=current_ma,
        pack_voltage_mv=sum(voltages),
        soc_percent=50,
        soh_percent=100,
        state=state,
    )


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def default_config() -> BMSConfig:
    return make_config()


@pytest.fixture
def bms(default_config: BMSConfig) -> BMSCore:
    return BMSCore(default_config)


# ===========================================================================
# 1.  BMSConfig validation
# ===========================================================================

class TestBMSConfigValidation:
    """BMSConfig.validate() must accept valid configs and reject bad ones."""

    def test_valid_config_does_not_raise(self, default_config: BMSConfig) -> None:
        default_config.validate()  # must not raise

    @pytest.mark.parametrize("num_cells", [0, BMS_MAX_CELLS + 1, -1])
    def test_invalid_num_cells_raises(self, num_cells: int) -> None:
        cfg = make_config(num_cells=num_cells)
        with pytest.raises(ValueError, match="num_cells"):
            cfg.validate()

    @pytest.mark.parametrize("num_sensors", [0, BMS_MAX_TEMP_SENSORS + 1])
    def test_invalid_num_temp_sensors_raises(self, num_sensors: int) -> None:
        cfg = make_config(num_temp_sensors=num_sensors)
        with pytest.raises(ValueError, match="num_temp_sensors"):
            cfg.validate()

    def test_uv_equals_ov_raises(self) -> None:
        cfg = make_config(
            uv_threshold_mv=BMS_CELL_OV_THRESHOLD_MV,
            ov_threshold_mv=BMS_CELL_OV_THRESHOLD_MV,
        )
        with pytest.raises(ValueError, match="uv_threshold_mv"):
            cfg.validate()

    def test_uv_greater_than_ov_raises(self) -> None:
        cfg = make_config(
            uv_threshold_mv=BMS_CELL_OV_THRESHOLD_MV + 100,
            ov_threshold_mv=BMS_CELL_OV_THRESHOLD_MV,
        )
        with pytest.raises(ValueError, match="uv_threshold_mv"):
            cfg.validate()

    def test_zero_capacity_raises(self) -> None:
        cfg = make_config(cell_capacity_mah=0)
        with pytest.raises(ValueError, match="cell_capacity_mah"):
            cfg.validate()

    def test_negative_capacity_raises(self) -> None:
        cfg = make_config(cell_capacity_mah=-1)
        with pytest.raises(ValueError, match="cell_capacity_mah"):
            cfg.validate()

    def test_zero_oc_threshold_raises(self) -> None:
        cfg = make_config(oc_threshold_ma=0)
        with pytest.raises(ValueError, match="oc_threshold_ma"):
            cfg.validate()

    def test_inverted_temp_thresholds_raises(self) -> None:
        cfg = make_config(
            min_temp_degc_x10=BMS_MAX_TEMP_DEGC_X10,
            max_temp_degc_x10=BMS_MIN_TEMP_DEGC_X10,
        )
        with pytest.raises(ValueError, match="min_temp_degc_x10"):
            cfg.validate()

    def test_negative_balancing_threshold_raises(self) -> None:
        cfg = make_config(balancing_threshold_mv=-1)
        with pytest.raises(ValueError, match="balancing_threshold_mv"):
            cfg.validate()

    @pytest.mark.parametrize("num_cells", [1, 4, 8, BMS_MAX_CELLS])
    def test_boundary_cell_counts_accepted(self, num_cells: int) -> None:
        cfg = make_config(num_cells=num_cells)
        cfg.validate()  # must not raise


# ===========================================================================
# 2.  Fault detection — happy path (no faults)
# ===========================================================================

class TestFaultDetectionNominal:
    """detect_faults() must return NONE for readings within all thresholds."""

    def test_no_faults_nominal_readings(self, bms: BMSCore) -> None:
        data = make_data(num_cells=bms.config.num_cells)
        assert bms.detect_faults(data) == BMSFault.NONE

    def test_voltage_at_ov_boundary_is_ok(self, bms: BMSCore) -> None:
        """Voltage exactly at OV threshold must NOT trigger a fault."""
        data = make_data(
            num_cells=bms.config.num_cells,
            cell_mv=bms.config.ov_threshold_mv,
        )
        assert BMSFault.OVERVOLTAGE not in bms.detect_faults(data)

    def test_voltage_at_uv_boundary_is_ok(self, bms: BMSCore) -> None:
        """Voltage exactly at UV threshold must NOT trigger a fault."""
        data = make_data(
            num_cells=bms.config.num_cells,
            cell_mv=bms.config.uv_threshold_mv,
        )
        assert BMSFault.UNDERVOLTAGE not in bms.detect_faults(data)

    def test_current_at_oc_boundary_is_ok(self, bms: BMSCore) -> None:
        """Current exactly at OC threshold must NOT trigger a fault."""
        data = make_data(
            num_cells=bms.config.num_cells,
            current_ma=bms.config.oc_threshold_ma,
        )
        assert BMSFault.OVERCURRENT not in bms.detect_faults(data)

    def test_temp_at_max_boundary_is_ok(self, bms: BMSCore) -> None:
        data = make_data(num_cells=bms.config.num_cells)
        data.temperature_degc_x10 = [bms.config.max_temp_degc_x10] * bms.config.num_temp_sensors
        assert BMSFault.OVERTEMP not in bms.detect_faults(data)

    def test_temp_at_min_boundary_is_ok(self, bms: BMSCore) -> None:
        data = make_data(num_cells=bms.config.num_cells)
        data.temperature_degc_x10 = [bms.config.min_temp_degc_x10] * bms.config.num_temp_sensors
        assert BMSFault.UNDERTEMP not in bms.detect_faults(data)


# ===========================================================================
# 3.  Fault detection — individual fault types
# ===========================================================================

class TestFaultDetectionErrors:
    """detect_faults() must set the correct flag for each fault type."""

    def test_single_cell_overvoltage_detected(self, bms: BMSCore) -> None:
        data = make_data(num_cells=bms.config.num_cells)
        data.cell_voltage_mv[0] = bms.config.ov_threshold_mv + 1
        faults = bms.detect_faults(data)
        assert BMSFault.OVERVOLTAGE in faults
        assert BMSFault.UNDERVOLTAGE not in faults

    def test_single_cell_undervoltage_detected(self, bms: BMSCore) -> None:
        data = make_data(num_cells=bms.config.num_cells)
        data.cell_voltage_mv[0] = bms.config.uv_threshold_mv - 1
        faults = bms.detect_faults(data)
        assert BMSFault.UNDERVOLTAGE in faults
        assert BMSFault.OVERVOLTAGE not in faults

    def test_all_cells_overvoltage(self, bms: BMSCore) -> None:
        data = make_data(
            num_cells=bms.config.num_cells,
            cell_mv=bms.config.ov_threshold_mv + 50,
        )
        assert BMSFault.OVERVOLTAGE in bms.detect_faults(data)

    def test_all_cells_undervoltage(self, bms: BMSCore) -> None:
        data = make_data(
            num_cells=bms.config.num_cells,
            cell_mv=bms.config.uv_threshold_mv - 50,
        )
        assert BMSFault.UNDERVOLTAGE in bms.detect_faults(data)

    def test_overcurrent_discharge(self, bms: BMSCore) -> None:
        data = make_data(
            num_cells=bms.config.num_cells,
            current_ma=bms.config.oc_threshold_ma + 1,
        )
        assert BMSFault.OVERCURRENT in bms.detect_faults(data)

    def test_overcurrent_charge_side(self, bms: BMSCore) -> None:
        """Absolute value of charge current must also trip OC fault."""
        data = make_data(
            num_cells=bms.config.num_cells,
            current_ma=-(bms.config.oc_threshold_ma + 1),
        )
        assert BMSFault.OVERCURRENT in bms.detect_faults(data)

    def test_overtemperature_detected(self, bms: BMSCore) -> None:
        data = make_data(num_cells=bms.config.num_cells)
        data.temperature_degc_x10 = (
            [bms.config.max_temp_degc_x10 + 1]
            + [0] * (bms.config.num_temp_sensors - 1)
        )
        assert BMSFault.OVERTEMP in bms.detect_faults(data)

    def test_undertemperature_detected(self, bms: BMSCore) -> None:
        data = make_data(num_cells=bms.config.num_cells)
        data.temperature_degc_x10 = (
            [bms.config.min_temp_degc_x10 - 1]
            + [0] * (bms.config.num_temp_sensors - 1)
        )
        assert BMSFault.UNDERTEMP in bms.detect_faults(data)

    def test_simultaneous_ov_and_oc_faults(self, bms: BMSCore) -> None:
        data = make_data(
            num_cells=bms.config.num_cells,
            cell_mv=bms.config.ov_threshold_mv + 1,
            current_ma=bms.config.oc_threshold_ma + 1,
        )
        faults = bms.detect_faults(data)
        assert BMSFault.OVERVOLTAGE in faults
        assert BMSFault.OVERCURRENT in faults

    def test_detect_faults_is_pure(self, bms: BMSCore) -> None:
        """detect_faults() must not mutate bms.state."""
        data = make_data(
            num_cells=bms.config.num_cells,
            cell_mv=bms.config.ov_threshold_mv + 1,
        )
        state_before = bms.state
        bms.detect_faults(data)
        assert bms.state == state_before

    @pytest.mark.parametrize("cell_index", [0, 1, 2, 3])
    def test_fault_in_any_single_cell_triggers_flag(self, cell_index: int) -> None:
        cfg = make_config(num_cells=4)
        core = BMSCore(cfg)
        data = make_data(num_cells=4)
        data.cell_voltage_mv[cell_index] = cfg.ov_threshold_mv + 1
        assert BMSFault.OVERVOLTAGE in core.detect_faults(data)


# ===========================================================================
# 4.  State machine transitions
# ===========================================================================

class TestStateMachineTransitions:
    """BMSCore.transition() must follow the documented state diagram."""

    def test_init_to_idle(self, bms: BMSCore) -> None:
        data = make_data(num_cells=bms.config.num_cells, state=BMSState.INIT)
        assert bms.transition(data) == BMSState.IDLE

    def test_idle_to_discharging(self, bms: BMSCore) -> None:
        bms.transition(make_data(num_cells=bms.config.num_cells))  # reach IDLE
        data = make_data(
            num_cells=bms.config.num_cells,
            current_ma=1000,  # positive = discharge
        )
        assert bms.transition(data) == BMSState.DISCHARGING

    def test_idle_to_charging(self, bms: BMSCore) -> None:
        bms.transition(make_data(num_cells=bms.config.num_cells))  # reach IDLE
        data = make_data(
            num_cells=bms.config.num_cells,
            current_ma=-1000,  # negative = charge
        )
        assert bms.transition(data) == BMSState.CHARGING

    def test_discharging_to_idle_on_zero_current(self, bms: BMSCore) -> None:
        bms.transition(make_data(num_cells=bms.config.num_cells))
        bms.transition(make_data(num_cells=bms.config.num_cells, current_ma=500))
        data = make_data(num_cells=bms.config.num_cells, current_ma=0)
        assert bms.transition(data) == BMSState.IDLE

    def test_overvoltage_fault_drives_to_fault_state(self, bms: BMSCore) -> None:
        bms.transition(make_data(num_cells=bms.config.num_cells))  # IDLE
        data = make_data(
            num_cells=bms.config.num_cells,
            cell_mv=bms.config.ov_threshold_mv + 1,
        )
        assert bms.transition(data) == BMSState.FAULT

    def test_fault_state_persists_while_fault_active(self, bms: BMSCore) -> None:
        bms.transition(make_data(num_cells=bms.config.num_cells))
        fault_data = make_data(
            num_cells=bms.config.num_cells,
            cell_mv=bms.config.ov_threshold_mv + 1,
        )
        bms.transition(fault_data)
        assert bms.state == BMSState.FAULT
        assert bms.transition(fault_data) == BMSState.FAULT  # still faulted

    def test_fault_recovery_to_idle_when_fault_cleared(self, bms: BMSCore) -> None:
        bms.transition(make_data(num_cells=bms.config.num_cells))
        bms.transition(
            make_data(
                num_cells=bms.config.num_cells,
                cell_mv=bms.config.ov_threshold_mv + 1,
            )
        )
        assert bms.state == BMSState.FAULT
        nominal = make_data(num_cells=bms.config.num_cells)
        assert bms.transition(nominal) == BMSState.IDLE

    def test_shutdown_state_is_terminal(self, bms: BMSCore) -> None:
        bms.transition(make_data(num_cells=bms.config.num_cells))  # IDLE
        data = make_data(
            num_cells=bms.config.num_cells,
            state=BMSState.SHUTDOWN,
        )
        assert bms.transition(data) == BMSState.SHUTDOWN

    def test_fault_flags_set_on_fault_entry(self, bms: BMSCore) -> None:
        bms.transition(make_data(num_cells=bms.config.num_cells))
        data = make_data(
            num_cells=bms.config.num_cells,
            current_ma=bms.config.oc_threshold_ma + 1,
        )
        bms.transition(data)
        assert BMSFault.OVERCURRENT in bms.fault_flags

    def test_fault_flags_cleared_after_recovery(self, bms: BMSCore) -> None:
        bms.transition(make_data(num_cells=bms.config.num_cells))
        bms.transition(
            make_data(
                num_cells=bms.config.num_cells,
                current_ma=bms.config.oc_threshold_ma + 1,
            )
        )
        bms.transition(make_data(num_cells=bms.config.num_cells))
        assert bms.fault_flags == BMSFault.NONE


# ===========================================================================
# 5.  SOC estimation
# ===========================================================================

class TestSoCEstimation:
    """estimate_soc_percent() must map OCV values to valid 0-100 range."""

    def test_fully_discharged_returns_zero(self) -> None:
        assert BMSCore.estimate_soc_percent(BMS_CELL_UV_THRESHOLD_MV) == 0

    def test_below_minimum_voltage_clamped_to_zero(self) -> None:
        assert BMSCore.estimate_soc_percent(BMS_CELL_UV_THRESHOLD_MV - 100) == 0

    def test_fully_charged_returns_100(self) -> None:
        assert BMSCore.estimate_soc_percent(BMS_CELL_OV_THRESHOLD_MV) == 100

    def test_above_maximum_voltage_clamped_to_100(self) -> None:
        assert BMSCore.estimate_soc_percent(BMS_CELL_OV_THRESHOLD_MV + 100) == 100

    def test_midrange_voltage_returns_positive_soc(self) -> None:
        mid_mv = (BMS_CELL_OV_THRESHOLD_MV + BMS_CELL_UV_THRESHOLD_MV) / 2
        soc = BMSCore.estimate_soc_percent(mid_mv)
        assert 0 < soc < 100

    def test_soc_is_monotonically_increasing(self) -> None:
        """SOC must never decrease as voltage increases through the OCV curve."""
        step = 50
        voltages = range(
            BMS_CELL_UV_THRESHOLD_MV,
            BMS_CELL_OV_THRESHOLD_MV + step,
            step,
        )
        soc_values = [BMSCore.estimate_soc_percent(v) for v in voltages]
        for prev, curr in zip(soc_values, soc_values[1:]):
            assert curr >= prev, f"SOC decreased: {prev} -> {curr}"

    @pytest.mark.parametrize("mv", [2900, 3300, 3600, 3800, 4000, 4150])
    def test_soc_in_valid_range_for_typical_voltages(self, mv: int) -> None:
        soc = BMSCore.estimate_soc_percent(mv)
        assert 0 <= soc <= 100, f"SOC {soc} out of range for {mv} mV"


# ===========================================================================
# 6.  Cell balancing
# ===========================================================================

class TestCellBalancing:
    """compute_balance_mask() must identify cells that need bleeding."""

    def test_equal_cells_no_balancing_needed(self, bms: BMSCore) -> None:
        voltages = nominal_voltages(bms.config.num_cells)
        assert bms.compute_balance_mask(voltages) == 0

    def test_single_high_cell_flagged(self, bms: BMSCore) -> None:
        voltages = nominal_voltages(bms.config.num_cells)
        high_cell_index = 1
        voltages[high_cell_index] += bms.config.balancing_threshold_mv + 1
        mask = bms.compute_balance_mask(voltages)
        assert mask & (1 << high_cell_index), "High cell not flagged"
        for i, _ in enumerate(voltages):
            if i != high_cell_index:
                assert not (mask & (1 << i)), f"Cell {i} incorrectly flagged"

    def test_cell_at_exact_threshold_not_flagged(self, bms: BMSCore) -> None:
        """Delta exactly equal to threshold must NOT trigger balancing."""
        voltages = nominal_voltages(bms.config.num_cells)
        voltages[0] += bms.config.balancing_threshold_mv  # exactly at limit
        mask = bms.compute_balance_mask(voltages)
        assert mask == 0, "Cell at exact threshold should not be flagged"

    def test_multiple_high_cells_all_flagged(self, bms: BMSCore) -> None:
        voltages = nominal_voltages(bms.config.num_cells)
        high_indices = [0, 2]
        for i in high_indices:
            voltages[i] += bms.config.balancing_threshold_mv + 10
        mask = bms.compute_balance_mask(voltages)
        for i in high_indices:
            assert mask & (1 << i), f"High cell {i} not flagged"

    def test_empty_voltage_list_returns_zero_mask(self, bms: BMSCore) -> None:
        assert bms.compute_balance_mask([]) == 0

    @pytest.mark.parametrize("num_cells", [1, 4, 8, BMS_MAX_CELLS])
    def test_all_equal_cells_never_need_balancing(self, num_cells: int) -> None:
        cfg = make_config(num_cells=num_cells)
        core = BMSCore(cfg)
        voltages = nominal_voltages(num_cells)
        assert core.compute_balance_mask(voltages) == 0


# ===========================================================================
# 7.  Pack voltage
# ===========================================================================

class TestPackVoltage:
    """compute_pack_voltage() must correctly sum series cell voltages."""

    def test_single_cell_pack(self) -> None:
        v = [3700]
        assert BMSCore.compute_pack_voltage(v) == 3700

    def test_multi_cell_pack_sum(self) -> None:
        voltages = [3600, 3650, 3700, 3750]
        expected = sum(voltages)
        assert BMSCore.compute_pack_voltage(voltages) == expected

    def test_empty_cell_list_returns_zero(self) -> None:
        assert BMSCore.compute_pack_voltage([]) == 0

    @pytest.mark.parametrize("num_cells", [2, 4, 8, 12, BMS_MAX_CELLS])
    def test_uniform_cells_scale_linearly(self, num_cells: int) -> None:
        cell_mv = 3700
        voltages = [cell_mv] * num_cells
        assert BMSCore.compute_pack_voltage(voltages) == cell_mv * num_cells


# ===========================================================================
# 8.  CellStats
# ===========================================================================

class TestCellStats:
    """CellStats.from_voltages() must compute accurate statistics."""

    def test_single_cell_stats(self) -> None:
        v = [3700]
        stats = CellStats.from_voltages(v)
        assert stats.min_mv == 3700
        assert stats.max_mv == 3700
        assert stats.delta_mv == 0
        assert math.isclose(stats.avg_mv, 3700.0)

    def test_multi_cell_stats(self) -> None:
        voltages = [3600, 3700, 3800, 3750]
        stats = CellStats.from_voltages(voltages)
        assert stats.min_mv == min(voltages)
        assert stats.max_mv == max(voltages)
        assert stats.delta_mv == max(voltages) - min(voltages)
        assert math.isclose(stats.avg_mv, sum(voltages) / len(voltages))

    def test_all_equal_cells_zero_delta(self) -> None:
        mv = 3700
        stats = CellStats.from_voltages([mv] * 8)
        assert stats.delta_mv == 0

    def test_empty_voltage_list_raises(self) -> None:
        with pytest.raises(ValueError):
            CellStats.from_voltages([])

    def test_avg_is_float(self) -> None:
        stats = CellStats.from_voltages([3601, 3602])
        assert isinstance(stats.avg_mv, float)


# ===========================================================================
# 9.  BMSCore constructor error handling
# ===========================================================================

class TestBMSCoreInit:
    """BMSCore.__init__() must reject invalid configs."""

    def test_invalid_config_raises_at_construction(self) -> None:
        bad_cfg = make_config(num_cells=0)
        with pytest.raises(ValueError):
            BMSCore(bad_cfg)

    def test_initial_state_is_init(self, bms: BMSCore) -> None:
        assert bms.state == BMSState.INIT

    def test_initial_fault_flags_are_none(self, bms: BMSCore) -> None:
        assert bms.fault_flags == BMSFault.NONE

    def test_config_accessible_after_init(self, bms: BMSCore) -> None:
        assert bms.config is not None
        assert bms.config.num_cells >= 1


# ===========================================================================
# 10. Fault injection scenarios (mirrors fi_type_t from bms_fault_injection.h)
# ===========================================================================

class TestFaultInjectionScenarios:
    """Simulate the fault injection types from bms_fault_injection.h."""

    @pytest.fixture
    def core(self) -> BMSCore:
        return BMSCore(make_config(num_cells=4, num_temp_sensors=2))

    def test_fi_cell_ov_triggers_overvoltage_fault(self, core: BMSCore) -> None:
        """FI_CELL_OV: clamp one cell to 4300 mV — should trip OV fault."""
        data = make_data(num_cells=4)
        data.cell_voltage_mv[0] = core.config.ov_threshold_mv + 100  # 4300 mV
        assert BMSFault.OVERVOLTAGE in core.detect_faults(data)

    def test_fi_cell_uv_triggers_undervoltage_fault(self, core: BMSCore) -> None:
        """FI_CELL_UV: clamp one cell to 2700 mV — should trip UV fault."""
        data = make_data(num_cells=4)
        data.cell_voltage_mv[2] = core.config.uv_threshold_mv - 100  # 2700 mV
        assert BMSFault.UNDERVOLTAGE in core.detect_faults(data)

    def test_fi_overcurrent_triggers_oc_fault(self, core: BMSCore) -> None:
        """FI_OVERCURRENT: override pack current to 55 A — should trip OC."""
        data = make_data(
            num_cells=4,
            current_ma=core.config.oc_threshold_ma + 5_000,  # 55000 mA
        )
        assert BMSFault.OVERCURRENT in core.detect_faults(data)

    def test_fi_overtemp_triggers_overtemp_fault(self, core: BMSCore) -> None:
        """FI_OVERTEMP: sensor to 65.0 degC (650 degC x10) — should trip OVERTEMP."""
        data = make_data(num_cells=4)
        data.temperature_degc_x10 = [
            core.config.max_temp_degc_x10 + 50,  # 65.0 degC
            0,
        ]
        assert BMSFault.OVERTEMP in core.detect_faults(data)

    def test_fi_undertemp_triggers_undertemp_fault(self, core: BMSCore) -> None:
        """FI_UNDERTEMP: sensor to -25.0 degC (-250 degC x10) — should trip UNDERTEMP."""
        data = make_data(num_cells=4)
        data.temperature_degc_x10 = [
            core.config.min_temp_degc_x10 - 50,  # -25.0 degC
            0,
        ]
        assert BMSFault.UNDERTEMP in core.detect_faults(data)

    def test_fi_all_cleared_returns_no_fault(self, core: BMSCore) -> None:
        """After all faults cleared, nominal data must show NONE."""
        data = make_data(num_cells=4)
        assert core.detect_faults(data) == BMSFault.NONE


# ===========================================================================
# 11. HILResultBlock deserialization (from hil_harness.py)
# ===========================================================================

class TestHILResultBlockDeserialization:
    """Unit tests for HILResultBlock.from_bytes() in hil_harness.py."""

    def _build_raw_block(
        self,
        magic: int,
        pass_mask: int,
        fail_mask: int,
        total: int,
        failed: int,
    ) -> bytes:
        import struct
        return struct.pack("<5I", magic, pass_mask, fail_mask, total, failed)

    def test_passing_result_block(self) -> None:
        from hil_harness import HILResultBlock, MAGIC_PASS
        raw = self._build_raw_block(MAGIC_PASS, 0xFF, 0x00, 100, 0)
        block = HILResultBlock.from_bytes(raw)
        assert block.passed is True
        assert block.magic == MAGIC_PASS
        assert block.failed_assertions == 0
        assert block.pass_count == 100

    def test_failing_result_block(self) -> None:
        from hil_harness import HILResultBlock, MAGIC_FAIL
        raw = self._build_raw_block(MAGIC_FAIL, 0x0F, 0xF0, 50, 5)
        block = HILResultBlock.from_bytes(raw)
        assert block.passed is False
        assert block.failed_assertions == 5
        assert block.pass_count == 45

    def test_truncated_data_raises_value_error(self) -> None:
        from hil_harness import HILResultBlock
        with pytest.raises(ValueError, match="too short"):
            HILResultBlock.from_bytes(b"\x00" * 4)  # need 20 bytes

    def test_wrong_magic_means_not_passed(self) -> None:
        from hil_harness import HILResultBlock
        raw = self._build_raw_block(0xDEADBEEF, 0xFF, 0x00, 10, 0)
        block = HILResultBlock.from_bytes(raw)
        # magic != MAGIC_PASS so passed should be False even with 0 failures
        assert block.passed is False

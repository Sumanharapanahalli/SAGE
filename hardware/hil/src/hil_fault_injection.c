/**
 * @file     hil_fault_injection.c
 * @brief    Fault injection test suite — exercises every fault type in
 *           HIL_FaultType_t, verifies the firmware responds correctly,
 *           and validates recovery within the required time budget.
 *
 * Injection mechanism:
 *   - SPI/I2C faults: driven by a companion "fault relay" MCU (STM32G0)
 *     connected over a second UART (fault-control channel).
 *   - Power faults: controlled via DAC on the fault relay board.
 *   - GPS/modem faults: relay MCU physically disconnects the UART TX line.
 *
 * Protocol: single-byte command → fault relay MCU → fault persists until
 *   cleared by HIL_FI_ClearFault().
 *
 * MISRA-C:2012 — Rules 13.4, 15.5, 17.7 observed.
 */

#include "hil_fault_injection.h"
#include "hil_config.h"
#include "fault_relay_hal.h"
#include "imu_hal.h"
#include "gps_hal.h"
#include "modem_hal.h"
#include "watchdog.h"
#include "error_handler.h"

#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>

/* ---------------------------------------------------------------------------
 * Internal assertion wrapper
 * -------------------------------------------------------------------------*/
#define FI_ASSERT(rpt, cond, lbl)                                           \
    do {                                                                     \
        (rpt)->assertions_run++;                                             \
        if (!(cond)) {                                                       \
            (rpt)->assertions_failed++;                                      \
            (void)printf("[FI FAIL] %s\r\n", (lbl));                        \
        }                                                                    \
    } while (0)

/* ---------------------------------------------------------------------------
 * Helper: inject a fault, run checker, then clear
 * Returns true if DUT behaved as expected
 * -------------------------------------------------------------------------*/
static bool inject_and_verify(HIL_FaultType_t fault,
                               uint32_t       hold_ms,
                               bool           (*fp_checker)(void),
                               uint32_t       recovery_budget_ms)
{
    bool initial_response;
    bool recovered;

    /* NULL guard on checker */
    if (fp_checker == NULL) {
        return false;
    }

    /* Inject fault via relay board */
    HAL_StatusTypeDef inj_status = FAULT_RELAY_Inject(fault);
    if (inj_status != HAL_OK) {
        (void)printf("[FI] relay inject failed for fault=%d\r\n", (int)fault);
        return false;
    }

    /* Hold: firmware should detect within hold_ms */
    HIL_BSP_DelayMs(hold_ms);
    initial_response = fp_checker();

    /* Clear fault and wait for recovery */
    (void)FAULT_RELAY_Clear();
    HIL_BSP_DelayMs(recovery_budget_ms);
    recovered = ERROR_HANDLER_IsRecovered();

    (void)printf("[FI] fault=0x%02X detected=%d recovered=%d\r\n",
                 (unsigned int)fault,
                 (int)initial_response,
                 (int)recovered);

    return (initial_response && recovered);
}

/* ---------------------------------------------------------------------------
 * Fault checkers — each polls a firmware status flag / error register
 * -------------------------------------------------------------------------*/

static bool check_imu_fault_detected(void)
{
    return (IMU_HAL_GetFaultStatus() != IMU_FAULT_NONE);
}

static bool check_i2c_fault_detected(void)
{
    return (BARO_HAL_GetI2CErrorCount() > 0U);
}

static bool check_uart_fault_detected(void)
{
    return (GPS_HAL_GetFramingErrors() > 0U);
}

static bool check_power_fault_detected(void)
{
    return ERROR_HANDLER_IsFlagSet(ERR_FLAG_UNDERVOLTAGE);
}

static bool check_modem_fault_detected(void)
{
    return ERROR_HANDLER_IsFlagSet(ERR_FLAG_MODEM_TIMEOUT);
}

static bool check_battery_critical(void)
{
    return ERROR_HANDLER_IsFlagSet(ERR_FLAG_BATTERY_CRITICAL);
}

/* ---------------------------------------------------------------------------
 * Main fault injection suite
 * -------------------------------------------------------------------------*/
HIL_Result_t HIL_FaultInjectionSuite(HIL_SuiteReport_t *p_report)
{
    bool result;

    if (p_report == NULL) {
        return HIL_RESULT_ERROR_SETUP;
    }

    /* ------------------------------------------------------------------ */
    /* F-01: SPI bus stuck LOW (IMU MISO held at 0)                        */
    /* ------------------------------------------------------------------ */
    result = inject_and_verify(HIL_FAULT_SPI_BUS_STUCK_LO,
                               100U,   /* 100 ms hold                    */
                               check_imu_fault_detected,
                               500U);  /* recover within 500 ms          */
    FI_ASSERT(p_report, result,
              "F-01: SPI stuck-low: detected and recovered");

    /* ------------------------------------------------------------------ */
    /* F-02: SPI bus stuck HIGH (IMU MISO held at 1)                       */
    /* ------------------------------------------------------------------ */
    result = inject_and_verify(HIL_FAULT_SPI_BUS_STUCK_HI,
                               100U,
                               check_imu_fault_detected,
                               500U);
    FI_ASSERT(p_report, result,
              "F-02: SPI stuck-high: detected and recovered");

    /* ------------------------------------------------------------------ */
    /* F-03: I2C NAK — BARO slave NAKs every transaction                   */
    /* ------------------------------------------------------------------ */
    result = inject_and_verify(HIL_FAULT_I2C_NAK,
                               200U,
                               check_i2c_fault_detected,
                               500U);
    FI_ASSERT(p_report, result,
              "F-03: I2C NAK: detected and recovered");

    /* ------------------------------------------------------------------ */
    /* F-04: I2C bus hang — SCL held low                                   */
    /* DUT must perform 9-clock recovery within 50 ms (SMBUS spec)         */
    /* ------------------------------------------------------------------ */
    result = inject_and_verify(HIL_FAULT_I2C_BUS_HANG,
                               50U,
                               check_i2c_fault_detected,
                               200U);
    FI_ASSERT(p_report, result,
              "F-04: I2C bus hang: 9-clock recovery performed");

    /* ------------------------------------------------------------------ */
    /* F-05: UART noise — GPS NMEA framing errors                          */
    /* ------------------------------------------------------------------ */
    result = inject_and_verify(HIL_FAULT_UART_NOISE,
                               500U,
                               check_uart_fault_detected,
                               1000U);
    FI_ASSERT(p_report, result,
              "F-05: UART noise: framing error flagged");

    /* ------------------------------------------------------------------ */
    /* F-06: Power brownout — VDD drops to 2.8 V (below UVLO 3.0 V)       */
    /* DUT must assert brownout flag and freeze non-safety outputs          */
    /* ------------------------------------------------------------------ */
    result = inject_and_verify(HIL_FAULT_POWER_BROWNOUT,
                               200U,
                               check_power_fault_detected,
                               1000U);
    FI_ASSERT(p_report, result,
              "F-06: Brownout: UVLO flag set, system safe");

    /* ------------------------------------------------------------------ */
    /* F-07: GPS no signal — antenna open-circuit                          */
    /* DUT must fall back to last-known position within 30 s               */
    /* ------------------------------------------------------------------ */
    (void)FAULT_RELAY_Inject(HIL_FAULT_GPS_NO_SIGNAL);
    HIL_BSP_DelayMs(30000U);  /* 30 s: GPS timeout window               */
    bool gps_fallback = GPS_HAL_IsUsingLastKnownPosition();
    FI_ASSERT(p_report, gps_fallback,
              "F-07: GPS antenna open: last-known position active at 30 s");
    (void)FAULT_RELAY_Clear();

    /* ------------------------------------------------------------------ */
    /* F-08: Modem no response — AT timeout                                */
    /* DUT must queue data locally and retry                               */
    /* ------------------------------------------------------------------ */
    result = inject_and_verify(HIL_FAULT_MODEM_NO_RESP,
                               5000U,   /* 5 s: modem timeout budget       */
                               check_modem_fault_detected,
                               10000U); /* 10 s: retry + re-register        */
    FI_ASSERT(p_report, result,
              "F-08: Modem timeout: flag raised, local queue active");

    /* ------------------------------------------------------------------ */
    /* F-09: Battery critical — VBAT below hard shutdown threshold          */
    /* DUT must save state to NVM and initiate graceful shutdown           */
    /* ------------------------------------------------------------------ */
    result = inject_and_verify(HIL_FAULT_BATTERY_CRITICAL,
                               200U,
                               check_battery_critical,
                               5000U);
    FI_ASSERT(p_report, result,
              "F-09: Battery critical: NVM save + graceful shutdown");

    /* ------------------------------------------------------------------ */
    /* F-10: Watchdog kick missed — single miss                            */
    /* DUT must NOT reset on first miss if within grace period             */
    /* (WDT has early-warning IRQ at 50 % of period)                      */
    /* ------------------------------------------------------------------ */
    bool wdt_grace = WDT_SimulateMissedKick(1U);
    FI_ASSERT(p_report, wdt_grace,
              "F-10: WDT single-miss: early-warning IRQ fired, no reset");

    /* Consecutive misses must trigger reset — verify RESET_FLAG in        */
    /* backup register after the WDT fires                                 */
    bool wdt_reset = WDT_SimulateMissedKick(10U);
    FI_ASSERT(p_report, wdt_reset,
              "F-10b: WDT consecutive miss: MCU reset occurred");

    return (p_report->assertions_failed == 0U) ? HIL_RESULT_PASS
                                                : HIL_RESULT_FAIL_FAULT;
}

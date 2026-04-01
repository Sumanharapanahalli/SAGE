/**
 * @file battery_mgmt.h
 * @brief Battery management — SOC estimation, threshold alerts.
 *
 * SOC estimation uses a combined coulomb-counter + OCV (Open Circuit
 * Voltage) correction approach.  The coulomb counter (MAX17048 fuel gauge
 * over I2C) provides the primary measurement; OCV lookup table corrects
 * accumulated drift at rest intervals.
 *
 * SRS-004  SOC accuracy ±5 % vs coulomb counter reference.
 * SRS-005  Low-battery alert at SOC ≤ 20 %.
 * SRS-006  Critical shutdown at SOC ≤ 5 %.
 *
 * @version 1.0.0
 */

#ifndef BATTERY_MGMT_H
#define BATTERY_MGMT_H

#include <stdint.h>
#include <stdbool.h>
#include <zephyr/kernel.h>
#include "app_events.h"

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Threshold constants (matching payload spec)
 * ------------------------------------------------------------------------- */
#define BATT_SOC_LOW_PCT       20U   /**< Low battery alert threshold (%)      */
#define BATT_SOC_CRITICAL_PCT   5U   /**< Critical shutdown threshold (%)       */
#define BATT_POLL_INTERVAL_MS  10000U /**< SOC polling interval (10 s)          */

/* -------------------------------------------------------------------------
 * Fuel gauge device alias (from device tree)
 * DT alias: &max17048_i2c  (defined in board overlay)
 * ------------------------------------------------------------------------- */
#define FUEL_GAUGE_NODE    DT_NODELABEL(max17048)

/* -------------------------------------------------------------------------
 * Battery state (public, read-only via getter)
 * ------------------------------------------------------------------------- */
typedef struct batt_mgmt_state {
    uint8_t  soc_pct;          /**< Filtered SOC 0–100 %             */
    uint16_t voltage_mv;       /**< Cell voltage millivolts           */
    int16_t  current_ma;       /**< Signed charge current mA          */
    int8_t   temperature_c;    /**< NTC temperature °C                */
    bool     is_charging;      /**< True if PMIC reports charging     */
    bool     low_alert_sent;   /**< Prevents repeated low alerts      */
    bool     crit_alert_sent;  /**< Prevents repeated critical alerts */
} batt_mgmt_state_t;

/* -------------------------------------------------------------------------
 * Public API
 * ------------------------------------------------------------------------- */

/**
 * @brief Initialise battery management subsystem.
 *
 * Configures I2C fuel gauge, sets alert thresholds in hardware register,
 * starts periodic polling work item.
 *
 * @return 0 on success, negative errno on failure.
 */
int battery_mgmt_init(void);

/**
 * @brief Get current battery state snapshot.
 *
 * Thread-safe (copies under mutex).
 *
 * @param p_state  Output buffer; must not be NULL.
 * @return 0 on success.
 */
int battery_mgmt_get_state(batt_mgmt_state_t *p_state);

/**
 * @brief Force immediate SOC re-read from fuel gauge.
 *
 * Useful before entering sleep or after long idle period.
 * Blocks caller for up to 50 ms (I2C transaction).
 *
 * @return SOC percentage 0–100, or negative errno on I2C failure.
 */
int battery_mgmt_force_update(void);

/**
 * @brief Initiate graceful power-down sequence (called on critical SOC).
 *
 * Flushes audit log, disables LTE/GPS, then calls sys_poweroff().
 * This function does NOT return.
 */
void battery_mgmt_critical_shutdown(void);

#ifdef __cplusplus
}
#endif

#endif /* BATTERY_MGMT_H */

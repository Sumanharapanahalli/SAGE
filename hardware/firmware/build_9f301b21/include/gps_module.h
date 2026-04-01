/**
 * @file gps_module.h
 * @brief GPS module interface — u-blox M8 series over UART.
 *
 * GPS is powered off at rest (power gate controlled by GPIO).
 * On fall event the orchestrator calls gps_module_acquire().
 * Module parses NMEA GGA/RMC sentences, posts EVT_GPS_FIX_ACQUIRED or
 * EVT_GPS_FIX_TIMEOUT (after 30 s with no valid fix).
 *
 * SRS-002  GPS fix acquired within 30 s of fall event.
 * SRS-003  End-to-end alert within 10 s (GPS + LTE combined).
 *
 * @version 1.0.0
 */

#ifndef GPS_MODULE_H
#define GPS_MODULE_H

#include <stdint.h>
#include <stdbool.h>
#include "app_events.h"

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Timing parameters
 * ------------------------------------------------------------------------- */
#define GPS_FIX_TIMEOUT_MS      30000U  /**< Abort fix attempt after 30 s   */
#define GPS_POWER_ON_DELAY_MS     500U  /**< Stabilisation after power gate  */
#define GPS_UART_BAUD           9600U  /**< u-blox default baud rate        */

/* -------------------------------------------------------------------------
 * GPS module power states
 * ------------------------------------------------------------------------- */
typedef enum gps_power_state {
    GPS_POWER_OFF   = 0,
    GPS_POWER_ON    = 1,
    GPS_ACQUIRING   = 2,
    GPS_FIX_VALID   = 3,
} gps_power_state_t;

/* -------------------------------------------------------------------------
 * Public API
 * ------------------------------------------------------------------------- */

/**
 * @brief Initialise GPS module subsystem (UART + power GPIO; GPS stays OFF).
 * @return 0 on success, negative errno on UART/GPIO init failure.
 */
int gps_module_init(void);

/**
 * @brief Begin GPS fix acquisition.
 *
 * Powers on the GPS module, begins NMEA parsing.
 * Non-blocking: returns immediately; result posted as event.
 * If already acquiring, resets timeout timer.
 *
 * @return 0 on success, -EBUSY if module in unexpected state.
 */
int gps_module_acquire(void);

/**
 * @brief Power down GPS module immediately (cancel any active acquisition).
 */
void gps_module_power_off(void);

/**
 * @brief Get last valid fix (returns stale fix if cached).
 *
 * @param p_fix  Output buffer; must not be NULL.
 * @return 0 if fix is valid, -ENODATA if no fix acquired since boot.
 */
int gps_module_get_last_fix(gps_fix_t *p_fix);

/**
 * @brief Return current GPS power state.
 */
gps_power_state_t gps_module_get_state(void);

#ifdef __cplusplus
}
#endif

#endif /* GPS_MODULE_H */

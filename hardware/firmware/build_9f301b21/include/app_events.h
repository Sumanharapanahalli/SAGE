/**
 * @file app_events.h
 * @brief Application event definitions for inter-module message queues.
 *
 * IEC 62304 Software Class: C (safety-related, life-critical alert path)
 * SOUP: Zephyr RTOS v3.5.0 (https://zephyrproject.org)
 *
 * @version 1.0.0
 * @date 2026-03-27
 */

#ifndef APP_EVENTS_H
#define APP_EVENTS_H

#include <stdint.h>
#include <stdbool.h>
#include <zephyr/kernel.h>

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Event type enumeration
 * MISRA-C 2012 Rule 2.3: typedef shall not be used for enumeration names
 * ------------------------------------------------------------------------- */
typedef enum app_event_type {
    EVT_NONE              = 0x00U,
    EVT_FALL_DETECTED     = 0x01U,  /**< IMU detected fall event            */
    EVT_FALL_CANCELLED    = 0x02U,  /**< User cancelled fall alert           */
    EVT_GPS_FIX_ACQUIRED  = 0x03U,  /**< GPS module acquired position fix    */
    EVT_GPS_FIX_TIMEOUT   = 0x04U,  /**< GPS fix timed out (>30s)            */
    EVT_LTE_ALERT_SENT    = 0x05U,  /**< LTE alert transmitted successfully  */
    EVT_LTE_ALERT_FAILED  = 0x06U,  /**< LTE alert transmission failed       */
    EVT_BATT_LOW          = 0x07U,  /**< Battery SOC <= 20%                  */
    EVT_BATT_CRITICAL     = 0x08U,  /**< Battery SOC <= 5%, initiate shutdown */
    EVT_BLE_CONNECTED     = 0x09U,  /**< BLE caregiver client connected      */
    EVT_BLE_DISCONNECTED  = 0x0AU,  /**< BLE client disconnected             */
    EVT_OTA_START         = 0x0BU,  /**< OTA update session initiated        */
    EVT_OTA_COMPLETE      = 0x0CU,  /**< OTA image written, pending reboot   */
    EVT_OTA_FAILED        = 0x0DU,  /**< OTA image write/verify failed       */
    EVT_WDT_FEED          = 0x0EU,  /**< Watchdog feed acknowledgement       */
    EVT_SHUTDOWN_REQ      = 0x0FU,  /**< Graceful shutdown requested         */
    EVT_MAX               = 0x10U
} app_event_type_t;

/* -------------------------------------------------------------------------
 * GPS fix data
 * ------------------------------------------------------------------------- */
typedef struct gps_fix {
    int32_t  latitude_mdeg;   /**< Latitude  millidegrees, WGS-84  */
    int32_t  longitude_mdeg;  /**< Longitude millidegrees, WGS-84  */
    int32_t  altitude_mm;     /**< Altitude  millimetres            */
    uint8_t  hdop_tenths;     /**< HDOP * 10 (e.g. 12 = HDOP 1.2)  */
    uint8_t  satellites;      /**< Number of satellites used        */
    uint32_t timestamp_s;     /**< POSIX timestamp of fix           */
} gps_fix_t;

/* -------------------------------------------------------------------------
 * Battery state data
 * ------------------------------------------------------------------------- */
typedef struct battery_state {
    uint8_t  soc_pct;         /**< State of charge 0-100 %          */
    int16_t  voltage_mv;      /**< Terminal voltage millivolts       */
    int16_t  current_ma;      /**< Signed current milliamps          */
    int8_t   temperature_c;   /**< Cell temperature degrees C        */
} battery_state_t;

/* -------------------------------------------------------------------------
 * Application event message (fixed-size for K_MSGQ)
 * Keep <= 64 bytes to fit in one cache line.
 * ------------------------------------------------------------------------- */
typedef struct app_event {
    app_event_type_t  type;          /**< Event discriminant            */
    uint32_t          timestamp_ms;  /**< k_uptime_get_32() at posting  */
    union {
        gps_fix_t       gps;         /**< Valid for EVT_GPS_FIX_ACQUIRED */
        battery_state_t batt;        /**< Valid for EVT_BATT_*           */
        uint8_t         raw[52];     /**< Generic payload (pad to 64B)   */
    } payload;
} app_event_t;

BUILD_ASSERT(sizeof(app_event_t) <= 64U, "app_event_t exceeds cache line");

/* -------------------------------------------------------------------------
 * Shared message queues  (defined in main.c)
 * ------------------------------------------------------------------------- */
extern struct k_msgq g_orchestrator_q;  /**< Main orchestrator queue (depth 16) */
extern struct k_msgq g_ble_notify_q;    /**< BLE notification queue   (depth  8) */

/* -------------------------------------------------------------------------
 * Convenience: post event, never block
 * Returns 0 on success, -ENOMSG if queue full (caller should audit-log).
 * ------------------------------------------------------------------------- */
static inline int app_event_post(app_event_type_t type)
{
    app_event_t evt = {
        .type         = type,
        .timestamp_ms = k_uptime_get_32()
    };
    return k_msgq_put(&g_orchestrator_q, &evt, K_NO_WAIT);
}

static inline int app_event_post_full(const app_event_t *p_evt)
{
    if (p_evt == NULL) {
        return -EINVAL;
    }
    return k_msgq_put(&g_orchestrator_q, p_evt, K_NO_WAIT);
}

#ifdef __cplusplus
}
#endif

#endif /* APP_EVENTS_H */

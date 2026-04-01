/**
 * @file lte_module.h
 * @brief LTE-M/NB-IoT alert module interface — nRF9160 modem.
 *
 * Sends emergency alert payload (JSON over HTTPS) to cloud endpoint.
 * Uses nRF Connect SDK LTE link controller and nRF9160 socket API.
 *
 * SRS-003  LTE alert transmitted within 10 s of fall confirmation.
 *
 * @version 1.0.0
 */

#ifndef LTE_MODULE_H
#define LTE_MODULE_H

#include <stdint.h>
#include <stdbool.h>
#include "app_events.h"

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Alert payload parameters
 * ------------------------------------------------------------------------- */
#define LTE_ALERT_ENDPOINT_MAX  128U  /**< Max URL length                   */
#define LTE_CONNECT_TIMEOUT_MS 8000U  /**< LTE attach timeout               */
#define LTE_SEND_TIMEOUT_MS    5000U  /**< HTTP POST timeout                 */
#define LTE_RETRY_MAX            3U   /**< Max send retries on failure       */

/* -------------------------------------------------------------------------
 * Alert payload structure (serialised to JSON before send)
 * ------------------------------------------------------------------------- */
typedef struct lte_alert_payload {
    char     device_id[32];        /**< Device UUID                         */
    uint32_t timestamp_utc;        /**< POSIX UTC timestamp of fall         */
    int32_t  latitude_mdeg;        /**< WGS-84 latitude  millidegrees       */
    int32_t  longitude_mdeg;       /**< WGS-84 longitude millidegrees       */
    uint8_t  battery_soc_pct;      /**< Battery SOC at time of alert        */
    uint8_t  alert_type;           /**< 0=fall, 1=manual SOS, 2=low-batt   */
    uint8_t  retry_count;          /**< Populated by module on retries      */
} lte_alert_payload_t;

/* -------------------------------------------------------------------------
 * LTE module state
 * ------------------------------------------------------------------------- */
typedef enum lte_state {
    LTE_STATE_OFF         = 0,
    LTE_STATE_CONNECTING  = 1,
    LTE_STATE_CONNECTED   = 2,
    LTE_STATE_SENDING     = 3,
    LTE_STATE_SENT        = 4,
    LTE_STATE_ERROR       = 5,
} lte_state_t;

/* -------------------------------------------------------------------------
 * Public API
 * ------------------------------------------------------------------------- */

/**
 * @brief Initialise LTE module — configures nRF9160 modem library.
 *
 * Does NOT attach to network (lazy attach on first send to save power).
 * @return 0 on success, negative errno on modem init failure.
 */
int lte_module_init(void);

/**
 * @brief Send emergency alert asynchronously.
 *
 * Non-blocking: queues payload to LTE work item, returns immediately.
 * Result posted as EVT_LTE_ALERT_SENT or EVT_LTE_ALERT_FAILED.
 *
 * @param p_payload  Alert data; must not be NULL.
 * @return 0 if queued, -EBUSY if prior send pending, -EINVAL if NULL.
 */
int lte_module_send_alert(const lte_alert_payload_t *p_payload);

/**
 * @brief Get current LTE modem state.
 */
lte_state_t lte_module_get_state(void);

/**
 * @brief Disconnect and power down modem (call before sleep/shutdown).
 */
void lte_module_power_off(void);

#ifdef __cplusplus
}
#endif

#endif /* LTE_MODULE_H */

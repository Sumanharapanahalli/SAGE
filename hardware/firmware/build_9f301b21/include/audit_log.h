/**
 * @file audit_log.h
 * @brief NVM audit log interface — IEC 62304 §5.1.1 traceability.
 *
 * Entries are CBOR-encoded and written to a dedicated NVS (Non-Volatile
 * Storage) partition in internal flash.  Each entry is immutable after write.
 * The log uses a circular sector strategy: oldest sector erased when full.
 *
 * SRS-010  Audit log entries written to NVM for every state transition.
 * IEC 62304 Class C — safety-critical traceability record.
 *
 * @version 1.0.0
 */

#ifndef AUDIT_LOG_H
#define AUDIT_LOG_H

#include <stdint.h>
#include <stdbool.h>
#include "app_events.h"

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Log entry category codes
 * ------------------------------------------------------------------------- */
typedef enum audit_category {
    AUDIT_CAT_SYSTEM   = 0x01U,  /**< Power-on, shutdown, watchdog reset   */
    AUDIT_CAT_FALL     = 0x02U,  /**< Fall detection events                 */
    AUDIT_CAT_GPS      = 0x03U,  /**< GPS acquisition events                */
    AUDIT_CAT_LTE      = 0x04U,  /**< LTE alert transmit events             */
    AUDIT_CAT_BATTERY  = 0x05U,  /**< Battery threshold crossings           */
    AUDIT_CAT_BLE      = 0x06U,  /**< BLE connect/disconnect/pair events    */
    AUDIT_CAT_OTA      = 0x07U,  /**< OTA update start/complete/fail        */
    AUDIT_CAT_WDT      = 0x08U,  /**< Watchdog feed / reset events          */
    AUDIT_CAT_ERROR    = 0xFFU,  /**< Software fault / assertion failure    */
} audit_category_t;

/* -------------------------------------------------------------------------
 * Maximum lengths
 * ------------------------------------------------------------------------- */
#define AUDIT_MSG_MAX_LEN   64U   /**< UTF-8 message string max bytes  */
#define AUDIT_MAX_ENTRIES  512U   /**< Circular log capacity           */

/* -------------------------------------------------------------------------
 * On-flash log entry (CBOR-encoded; struct used for RAM staging only)
 * ------------------------------------------------------------------------- */
typedef struct audit_entry {
    uint32_t          seq;                    /**< Monotonic sequence number */
    uint32_t          timestamp_ms;           /**< k_uptime_get_32()         */
    audit_category_t  category;               /**< Entry category            */
    app_event_type_t  event;                  /**< Associated event type     */
    char              message[AUDIT_MSG_MAX_LEN]; /**< Human-readable detail */
    uint8_t           reserved[4];            /**< Pad to 80 bytes           */
} audit_entry_t;

BUILD_ASSERT(sizeof(audit_entry_t) <= 80U, "audit_entry_t too large");

/* -------------------------------------------------------------------------
 * Public API
 * ------------------------------------------------------------------------- */

/**
 * @brief Initialise audit log subsystem. Must be called before any write.
 * @return 0 on success, negative errno on failure.
 */
int audit_log_init(void);

/**
 * @brief Write an audit entry to NVM.
 *
 * Thread-safe (uses internal mutex). Non-blocking write to NVS.
 * If NVS is full, oldest sector is erased transparently.
 *
 * @param cat     Entry category.
 * @param evt     Associated application event (EVT_NONE if not applicable).
 * @param msg     NULL-terminated message string (truncated to AUDIT_MSG_MAX_LEN).
 * @return 0 on success, negative errno on failure.
 */
int audit_log_write(audit_category_t cat, app_event_type_t evt,
                    const char *msg);

/**
 * @brief Read the Nth most-recent audit entry.
 *
 * @param index   0 = most recent, 1 = second most recent, …
 * @param p_entry Output buffer; must not be NULL.
 * @return 0 on success, -ENOENT if index out of range.
 */
int audit_log_read(uint32_t index, audit_entry_t *p_entry);

/**
 * @brief Return total number of entries stored (capped at AUDIT_MAX_ENTRIES).
 */
uint32_t audit_log_count(void);

/**
 * @brief Erase all audit entries (requires explicit confirmation token).
 *
 * Only permitted during manufacturing / factory reset.
 * @param confirm_token  Must equal AUDIT_ERASE_CONFIRM_TOKEN.
 * @return 0 on success, -EACCES if token mismatch.
 */
int audit_log_erase(uint32_t confirm_token);

#define AUDIT_ERASE_CONFIRM_TOKEN  0xDEADFACEU

#ifdef __cplusplus
}
#endif

#endif /* AUDIT_LOG_H */

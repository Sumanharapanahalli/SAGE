/**
 * @file power_management.h
 * @brief Power management state machine for elder fall detection wearable.
 *
 * State transitions:
 *   ACTIVE <-> IDLE <-> SLEEP <-> DEEP_SLEEP -> SHUTDOWN
 *
 * IEC 62304 Classification: Class B software unit
 * Software Unit ID: SU-PWR-001
 */

#ifndef POWER_MANAGEMENT_H
#define POWER_MANAGEMENT_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Timeout constants (milliseconds)
 * ---------------------------------------------------------------------- */
#define POWER_IDLE_TIMEOUT_MS        10000U  /**< ACTIVE → IDLE after 10s no motion   */
#define POWER_SLEEP_TIMEOUT_MS       30000U  /**< IDLE → SLEEP after 30s              */
#define POWER_DEEP_SLEEP_TIMEOUT_MS 120000U  /**< SLEEP → DEEP_SLEEP after 2 min      */

/* -------------------------------------------------------------------------
 * Current consumption (mA, approximate)
 * ---------------------------------------------------------------------- */
#define POWER_CURRENT_ACTIVE_MA      12U
#define POWER_CURRENT_IDLE_MA         6U
#define POWER_CURRENT_SLEEP_MA        2U
#define POWER_CURRENT_DEEP_SLEEP_MA   0U  /**< ~50µA, rounds to 0 in mA */
#define POWER_CURRENT_SHUTDOWN_MA     0U

/* -------------------------------------------------------------------------
 * Types
 * ---------------------------------------------------------------------- */

typedef enum {
    POWER_STATE_ACTIVE      = 0,
    POWER_STATE_IDLE        = 1,
    POWER_STATE_SLEEP       = 2,
    POWER_STATE_DEEP_SLEEP  = 3,
    POWER_STATE_SHUTDOWN    = 4,
    POWER_STATE_COUNT       = 5,
} PowerState;

typedef enum {
    POWER_EVT_MOTION_DETECTED   = 0,
    POWER_EVT_MOTION_TIMEOUT    = 1,
    POWER_EVT_IDLE_TIMEOUT      = 2,
    POWER_EVT_SLEEP_TIMEOUT     = 3,
    POWER_EVT_WAKEUP_IRQ        = 4,
    POWER_EVT_BATTERY_LOW       = 5,  /**< < 20% → restrict background tasks */
    POWER_EVT_BATTERY_CRITICAL  = 6,  /**< < 5%  → force DEEP_SLEEP          */
    POWER_EVT_CHARGING_START    = 7,
    POWER_EVT_SOS_PRESSED       = 8,  /**< Always wake to ACTIVE             */
    POWER_EVT_BLE_CONNECTED     = 9,
    POWER_EVT_BLE_DISCONNECTED  = 10,
    POWER_EVT_FALL_DETECTED     = 11, /**< Always wake to ACTIVE             */
    POWER_EVT_SHUTDOWN_REQUEST  = 12,
    POWER_EVT_COUNT             = 13,
} PowerEvent;

/** Power management configuration */
typedef struct {
    uint32_t idle_timeout_ms;
    uint32_t sleep_timeout_ms;
    uint32_t deep_sleep_timeout_ms;
    bool     sos_always_wakes;
    bool     fall_always_wakes;
} PowerMgmtConfig;

/* -------------------------------------------------------------------------
 * API
 * ---------------------------------------------------------------------- */

/**
 * @brief Initialise power management module.
 * @param cfg  Configuration; pass NULL to use defaults.
 */
void power_mgmt_init(const PowerMgmtConfig *cfg);

/** @brief Get current power state. */
PowerState power_mgmt_get_state(void);

/**
 * @brief Process a power event and transition state if applicable.
 * @param evt  Event to process.
 * @return New power state after processing.
 */
PowerState power_mgmt_process_event(PowerEvent evt);

/** @brief Returns typical current draw for current state (mA). */
uint32_t power_mgmt_get_current_ma(void);

/** @brief Returns true if device can enter sleep from current state. */
bool power_mgmt_can_sleep(void);

/** @brief Returns number of state transitions since init. */
uint32_t power_mgmt_get_transition_count(void);

/** @brief Reset state machine to ACTIVE. */
void power_mgmt_reset(void);

#ifdef __cplusplus
}
#endif
#endif /* POWER_MANAGEMENT_H */

/**
 * @file watchdog.h
 * @brief Hardware + Software Watchdog Manager
 *
 * IEC 62304 Software Class B — ensures system liveness.
 *
 * Two-layer watchdog strategy:
 *
 *   Layer 1 — Hardware IWDG (Independent Watchdog):
 *     Driven by LSI oscillator (~32 kHz), fully independent of main clock.
 *     Timeout: configurable, default 4 s.
 *     Must be kicked by watchdog_hw_kick() every WDG_HW_TIMEOUT_MS / 2.
 *
 *   Layer 2 — Software task watchdog:
 *     Each RTOS task registers with watchdog_task_register().
 *     Must call watchdog_task_kick(task_id) within its configured deadline.
 *     A dedicated watchdog monitor task checks all tasks every WDG_SW_POLL_MS.
 *     On expiry: logs the offending task, then allows HW watchdog to trigger.
 *
 * Recovery:
 *   On reset, watchdog_check_reset_cause() reports if last reset was WDG-induced.
 *   This is logged to the audit trail for IEC 62304 compliance.
 *
 * @version 1.0.0
 * @date    2026-03-21
 */

#ifndef WATCHDOG_H
#define WATCHDOG_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* =========================================================================
 * Configuration
 * ========================================================================= */
#define WDG_HW_TIMEOUT_MS   4000u   /**< HW watchdog timeout (ms)            */
#define WDG_HW_KICK_PERIOD  2000u   /**< Kick interval: <= timeout/2         */
#define WDG_SW_POLL_MS      500u    /**< Software watchdog check interval     */
#define WDG_MAX_TASKS       16u     /**< Max registered tasks                 */

/* =========================================================================
 * Reset cause flags
 * ========================================================================= */
typedef enum {
    WDG_RESET_NONE        = 0x00,
    WDG_RESET_HW_WATCHDOG = 0x01,  /**< IWDG reset                          */
    WDG_RESET_SW_WATCHDOG = 0x02,  /**< Software watchdog expired            */
    WDG_RESET_POWER_ON    = 0x04,
    WDG_RESET_SOFT        = 0x08,  /**< Deliberate software reset            */
    WDG_RESET_UNKNOWN     = 0xFF,
} WdgResetCause;

/* =========================================================================
 * Error codes
 * ========================================================================= */
typedef enum {
    WDG_ERR_OK           =  0,
    WDG_ERR_NULL_PTR     = -1,
    WDG_ERR_ALREADY_INIT = -2,
    WDG_ERR_NOT_INIT     = -3,
    WDG_ERR_FULL         = -4,   /**< WDG_MAX_TASKS exceeded                 */
    WDG_ERR_BAD_ID       = -5,
    WDG_ERR_HAL          = -6,
} WdgErr;

/* =========================================================================
 * Public API — Hardware watchdog
 * ========================================================================= */

/**
 * @brief  Initialise and start the hardware IWDG.
 *         Call once at startup before RTOS scheduler.
 * @param  timeout_ms  Watchdog timeout in milliseconds.
 * @return WDG_ERR_OK or WDG_ERR_HAL.
 */
WdgErr watchdog_hw_init(uint32_t timeout_ms);

/**
 * @brief  Kick (feed) the hardware watchdog.
 *         Must be called at least every timeout_ms/2.
 *         Safe to call from any task or ISR.
 */
void watchdog_hw_kick(void);

/**
 * @brief  Permanently lock the IWDG (prevents disable after start).
 *         Call after init. IWDG cannot be stopped once locked on STM32.
 */
void watchdog_hw_lock(void);

/* =========================================================================
 * Public API — Software task watchdog
 * ========================================================================= */

/**
 * @brief  Initialise the software watchdog subsystem.
 * @return WDG_ERR_OK or WDG_ERR_ALREADY_INIT.
 */
WdgErr watchdog_sw_init(void);

/**
 * @brief  Register a task with the software watchdog.
 * @param  task_name   Short identifier string (for logging).
 * @param  deadline_ms Maximum allowed time between kicks (ms).
 * @param  task_id     Output: assigned ID (0..WDG_MAX_TASKS-1).
 * @return WDG_ERR_OK, WDG_ERR_FULL, or WDG_ERR_NULL_PTR.
 */
WdgErr watchdog_task_register(const char *task_name,
                               uint32_t    deadline_ms,
                               uint8_t    *task_id);

/**
 * @brief  Kick the software watchdog for a registered task.
 *         Call from within the monitored task's main loop.
 * @param  task_id  ID returned by watchdog_task_register.
 * @return WDG_ERR_OK or WDG_ERR_BAD_ID.
 */
WdgErr watchdog_task_kick(uint8_t task_id);

/**
 * @brief  Poll all registered tasks. Call from a dedicated monitor task.
 *         If any task has exceeded its deadline:
 *           - Logs the offending task name
 *           - Stops kicking the HW watchdog (triggers reset within timeout_ms)
 */
void watchdog_sw_poll(void);

/* =========================================================================
 * Public API — Reset cause
 * ========================================================================= */

/**
 * @brief  Read and clear the hardware reset cause flags.
 *         Call once at startup, before watchdog_hw_init.
 */
WdgResetCause watchdog_check_reset_cause(void);

/**
 * @brief  Returns true if the last reset was caused by either watchdog.
 */
bool watchdog_last_reset_was_watchdog(void);

/**
 * @brief  Trigger a deliberate software reset (e.g. after OTA).
 */
void watchdog_trigger_reset(void);

#ifdef __cplusplus
}
#endif

#endif /* WATCHDOG_H */

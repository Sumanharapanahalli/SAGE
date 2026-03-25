/**
 * @file watchdog.c
 * @brief Hardware + Software Watchdog Manager Implementation
 *
 * IEC 62304 Class B — see watchdog.h for specification.
 *
 * BSP hooks required (replace with your HAL):
 *   bsp_iwdg_init(timeout_ms)     -> int (0=ok)
 *   bsp_iwdg_kick()
 *   bsp_iwdg_lock()
 *   bsp_read_reset_flags()        -> uint32_t (hardware RCC CSR or equivalent)
 *   bsp_clear_reset_flags()
 *   bsp_system_reset()
 *   bsp_get_time_ms()             -> int64_t
 *   bsp_log(const char *msg)
 *
 * @version 1.0.0
 * @date    2026-03-21
 */

#include "watchdog.h"
#include <string.h>
#include <stdio.h>

/* =========================================================================
 * BSP forward declarations
 * ========================================================================= */
extern int      bsp_iwdg_init(uint32_t timeout_ms);
extern void     bsp_iwdg_kick(void);
extern void     bsp_iwdg_lock(void);
extern uint32_t bsp_read_reset_flags(void);   /* e.g. RCC->CSR on STM32 */
extern void     bsp_clear_reset_flags(void);
extern void     bsp_system_reset(void);
extern int64_t  bsp_get_time_ms(void);
extern void     bsp_log(const char *msg);

/* BSP reset flag bit masks (STM32 convention — adapt to your MCU) */
#define BSP_FLAG_IWDG_RESET  (1UL << 29)   /* IWDGRSTF in RCC_CSR */
#define BSP_FLAG_WWDG_RESET  (1UL << 30)   /* WWDGRSTF */
#define BSP_FLAG_SOFT_RESET  (1UL << 28)   /* SFTRSTF  */
#define BSP_FLAG_POR_RESET   (1UL << 27)   /* PORRSTF  */

/* =========================================================================
 * Internal state
 * ========================================================================= */
typedef struct {
    char     name[16];
    uint32_t deadline_ms;
    int64_t  last_kick_ms;
    bool     active;
    bool     expired;
} SwTask;

typedef struct {
    bool          hw_initialised;
    bool          sw_initialised;
    bool          hw_kicking;         /* false when deliberately stopped    */
    uint32_t      hw_timeout_ms;
    SwTask        tasks[WDG_MAX_TASKS];
    uint8_t       task_count;
    WdgResetCause last_reset;
    char          log_buf[128];
} WdgCtx;

static WdgCtx s_wdg;

/* =========================================================================
 * Hardware watchdog
 * ========================================================================= */

WdgErr watchdog_hw_init(uint32_t timeout_ms)
{
    if (s_wdg.hw_initialised) { return WDG_ERR_ALREADY_INIT; }
    if (timeout_ms == 0u)     { return WDG_ERR_NULL_PTR; }

    if (bsp_iwdg_init(timeout_ms) != 0) { return WDG_ERR_HAL; }

    s_wdg.hw_timeout_ms   = timeout_ms;
    s_wdg.hw_kicking      = true;
    s_wdg.hw_initialised  = true;
    return WDG_ERR_OK;
}

void watchdog_hw_kick(void)
{
    if (s_wdg.hw_initialised && s_wdg.hw_kicking) {
        bsp_iwdg_kick();
    }
}

void watchdog_hw_lock(void)
{
    if (s_wdg.hw_initialised) {
        bsp_iwdg_lock();
    }
}

/* =========================================================================
 * Software task watchdog
 * ========================================================================= */

WdgErr watchdog_sw_init(void)
{
    if (s_wdg.sw_initialised) { return WDG_ERR_ALREADY_INIT; }
    memset(s_wdg.tasks, 0, sizeof(s_wdg.tasks));
    s_wdg.task_count    = 0u;
    s_wdg.sw_initialised = true;
    return WDG_ERR_OK;
}

WdgErr watchdog_task_register(const char *task_name,
                               uint32_t    deadline_ms,
                               uint8_t    *task_id)
{
    if (!s_wdg.sw_initialised)       { return WDG_ERR_NOT_INIT; }
    if (task_name == NULL || task_id == NULL) { return WDG_ERR_NULL_PTR; }
    if (deadline_ms == 0u)           { return WDG_ERR_NULL_PTR; }
    if (s_wdg.task_count >= WDG_MAX_TASKS) { return WDG_ERR_FULL; }

    uint8_t id              = s_wdg.task_count;
    SwTask *t               = &s_wdg.tasks[id];
    strncpy(t->name, task_name, sizeof(t->name) - 1u);
    t->name[sizeof(t->name) - 1u] = '\0';
    t->deadline_ms           = deadline_ms;
    t->last_kick_ms          = bsp_get_time_ms();
    t->active                = true;
    t->expired               = false;

    s_wdg.task_count++;
    *task_id = id;
    return WDG_ERR_OK;
}

WdgErr watchdog_task_kick(uint8_t task_id)
{
    if (!s_wdg.sw_initialised)        { return WDG_ERR_NOT_INIT; }
    if (task_id >= s_wdg.task_count)  { return WDG_ERR_BAD_ID; }

    s_wdg.tasks[task_id].last_kick_ms = bsp_get_time_ms();
    s_wdg.tasks[task_id].expired      = false;
    return WDG_ERR_OK;
}

void watchdog_sw_poll(void)
{
    if (!s_wdg.sw_initialised) { return; }

    int64_t now = bsp_get_time_ms();
    bool    any_expired = false;

    for (uint8_t i = 0u; i < s_wdg.task_count; i++) {
        SwTask *t = &s_wdg.tasks[i];
        if (!t->active) { continue; }

        int64_t elapsed = now - t->last_kick_ms;
        if (elapsed < 0) { elapsed = 0; }

        if ((uint32_t)elapsed > t->deadline_ms) {
            if (!t->expired) {
                t->expired = true;
                snprintf(s_wdg.log_buf, sizeof(s_wdg.log_buf),
                         "[WDG] Task '%s' expired after %ldms (deadline %ums)",
                         t->name, (long)elapsed, (unsigned)t->deadline_ms);
                bsp_log(s_wdg.log_buf);
            }
            any_expired = true;
        }
    }

    if (any_expired) {
        /*
         * Deliberately stop kicking the HW watchdog.
         * The HW IWDG will fire within WDG_HW_TIMEOUT_MS and reset the MCU.
         * This is the correct recovery mechanism — do not call bsp_system_reset()
         * here as that could mask the watchdog reset cause in the RCC status.
         */
        s_wdg.hw_kicking = false;
        bsp_log("[WDG] SW watchdog: stopping HW kicks — awaiting IWDG reset");
    }
}

/* =========================================================================
 * Reset cause
 * ========================================================================= */

WdgResetCause watchdog_check_reset_cause(void)
{
    uint32_t flags = bsp_read_reset_flags();
    bsp_clear_reset_flags();

    WdgResetCause cause = WDG_RESET_NONE;

    if (flags & BSP_FLAG_IWDG_RESET) { cause = (WdgResetCause)(cause | WDG_RESET_HW_WATCHDOG); }
    if (flags & BSP_FLAG_WWDG_RESET) { cause = (WdgResetCause)(cause | WDG_RESET_SW_WATCHDOG); }
    if (flags & BSP_FLAG_SOFT_RESET) { cause = (WdgResetCause)(cause | WDG_RESET_SOFT); }
    if (flags & BSP_FLAG_POR_RESET)  { cause = (WdgResetCause)(cause | WDG_RESET_POWER_ON); }
    if (cause == WDG_RESET_NONE && flags != 0u) { cause = WDG_RESET_UNKNOWN; }

    s_wdg.last_reset = cause;
    return cause;
}

bool watchdog_last_reset_was_watchdog(void)
{
    return (s_wdg.last_reset & (WDG_RESET_HW_WATCHDOG | WDG_RESET_SW_WATCHDOG)) != 0u;
}

void watchdog_trigger_reset(void)
{
    bsp_system_reset();
}

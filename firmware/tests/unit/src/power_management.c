/**
 * @file power_management.c
 * @brief Power management state machine implementation.
 */

#include "power_management.h"
#include <string.h>

static PowerState      s_state;
static PowerMgmtConfig s_cfg;
static uint32_t        s_transition_count;

void power_mgmt_init(const PowerMgmtConfig *cfg)
{
    if (cfg != NULL) {
        s_cfg = *cfg;
    } else {
        s_cfg.idle_timeout_ms        = POWER_IDLE_TIMEOUT_MS;
        s_cfg.sleep_timeout_ms       = POWER_SLEEP_TIMEOUT_MS;
        s_cfg.deep_sleep_timeout_ms  = POWER_DEEP_SLEEP_TIMEOUT_MS;
        s_cfg.sos_always_wakes       = true;
        s_cfg.fall_always_wakes      = true;
    }
    s_state            = POWER_STATE_ACTIVE;
    s_transition_count = 0;
}

static void _transition(PowerState new_state)
{
    if (new_state != s_state) {
        s_state = new_state;
        s_transition_count++;
    }
}

PowerState power_mgmt_process_event(PowerEvent evt)
{
    switch (evt) {

    case POWER_EVT_SOS_PRESSED:
    case POWER_EVT_FALL_DETECTED:
        /* Always wake to ACTIVE regardless of current state */
        if (s_cfg.sos_always_wakes || evt == POWER_EVT_FALL_DETECTED) {
            _transition(POWER_STATE_ACTIVE);
        }
        break;

    case POWER_EVT_MOTION_DETECTED:
    case POWER_EVT_WAKEUP_IRQ:
    case POWER_EVT_CHARGING_START:
    case POWER_EVT_BLE_CONNECTED:
        if (s_state != POWER_STATE_ACTIVE) {
            _transition(POWER_STATE_ACTIVE);
        }
        break;

    case POWER_EVT_MOTION_TIMEOUT:
        if (s_state == POWER_STATE_ACTIVE) {
            _transition(POWER_STATE_IDLE);
        }
        break;

    case POWER_EVT_IDLE_TIMEOUT:
        if (s_state == POWER_STATE_IDLE) {
            _transition(POWER_STATE_SLEEP);
        }
        break;

    case POWER_EVT_SLEEP_TIMEOUT:
        if (s_state == POWER_STATE_SLEEP) {
            _transition(POWER_STATE_DEEP_SLEEP);
        }
        break;

    case POWER_EVT_BATTERY_CRITICAL:
        /* Force deep sleep from any state except ACTIVE (SOS must still work) */
        if (s_state != POWER_STATE_ACTIVE) {
            _transition(POWER_STATE_DEEP_SLEEP);
        }
        break;

    case POWER_EVT_BATTERY_LOW:
        /* Accelerate to SLEEP if currently IDLE */
        if (s_state == POWER_STATE_IDLE) {
            _transition(POWER_STATE_SLEEP);
        }
        break;

    case POWER_EVT_BLE_DISCONNECTED:
        /* Allow sleeping after disconnect if no motion */
        if (s_state == POWER_STATE_ACTIVE) {
            _transition(POWER_STATE_IDLE);
        }
        break;

    case POWER_EVT_SHUTDOWN_REQUEST:
        _transition(POWER_STATE_SHUTDOWN);
        break;

    default:
        break;
    }
    return s_state;
}

PowerState power_mgmt_get_state(void)
{
    return s_state;
}

uint32_t power_mgmt_get_current_ma(void)
{
    switch (s_state) {
    case POWER_STATE_ACTIVE:     return POWER_CURRENT_ACTIVE_MA;
    case POWER_STATE_IDLE:       return POWER_CURRENT_IDLE_MA;
    case POWER_STATE_SLEEP:      return POWER_CURRENT_SLEEP_MA;
    case POWER_STATE_DEEP_SLEEP: return POWER_CURRENT_DEEP_SLEEP_MA;
    case POWER_STATE_SHUTDOWN:   return POWER_CURRENT_SHUTDOWN_MA;
    default:                     return 0;
    }
}

bool power_mgmt_can_sleep(void)
{
    return s_state == POWER_STATE_IDLE || s_state == POWER_STATE_SLEEP;
}

uint32_t power_mgmt_get_transition_count(void)
{
    return s_transition_count;
}

void power_mgmt_reset(void)
{
    s_state            = POWER_STATE_ACTIVE;
    s_transition_count = 0;
}

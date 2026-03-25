/**
 * @file sos_button.c
 * @brief SOS button debounce and long-press detection implementation.
 */

#include "sos_button.h"

typedef enum {
    SOS_STATE_IDLE    = 0,
    SOS_STATE_PRESSED = 1,
    SOS_STATE_ARMED   = 2,
} SOSState;

static SOSState  s_state;
static uint32_t  s_press_start_ms;
static uint32_t  s_last_change_ms;
static bool      s_last_raw;

void sos_button_init(void)
{
    sos_button_reset();
}

SOSEvent sos_button_process(bool pressed, uint32_t timestamp_ms)
{
    uint32_t elapsed_since_change = timestamp_ms - s_last_change_ms;

    /* Debounce: ignore transitions within SOS_DEBOUNCE_MS */
    if (pressed != s_last_raw) {
        if (elapsed_since_change < SOS_DEBOUNCE_MS) {
            return SOS_EVENT_BOUNCE_FILTERED;
        }
        s_last_raw        = pressed;
        s_last_change_ms  = timestamp_ms;

        if (pressed && s_state == SOS_STATE_IDLE) {
            s_state          = SOS_STATE_PRESSED;
            s_press_start_ms = timestamp_ms;
        } else if (!pressed) {
            uint32_t dur = timestamp_ms - s_press_start_ms;
            if (s_state == SOS_STATE_PRESSED) {
                s_state = SOS_STATE_IDLE;
                return SOS_EVENT_SHORT_PRESS;
            } else if (s_state == SOS_STATE_ARMED) {
                /* Released after armed → confirm */
                s_state = SOS_STATE_IDLE;
                return SOS_EVENT_LONG_PRESS_CONFIRMED;
            }
            (void)dur;
        }
        return SOS_EVENT_NONE;
    }

    /* No state change — check hold duration */
    if (pressed && s_state == SOS_STATE_PRESSED) {
        uint32_t hold_ms = timestamp_ms - s_press_start_ms;
        if (hold_ms >= SOS_LONG_PRESS_ARMED_MS) {
            s_state = SOS_STATE_ARMED;
            return SOS_EVENT_LONG_PRESS_ARMED;
        }
    }

    /* Cancellation window: double-press after ARMED within cancel window */
    if (!pressed && s_state == SOS_STATE_IDLE &&
        (timestamp_ms - s_last_change_ms) < SOS_CANCEL_WINDOW_MS) {
        return SOS_EVENT_CANCELLED;
    }

    return SOS_EVENT_NONE;
}

bool sos_button_is_armed(void)
{
    return s_state == SOS_STATE_ARMED;
}

uint32_t sos_button_get_press_duration_ms(uint32_t current_time_ms)
{
    if (s_state == SOS_STATE_IDLE) return 0;
    return current_time_ms - s_press_start_ms;
}

void sos_button_reset(void)
{
    s_state          = SOS_STATE_IDLE;
    s_press_start_ms = 0;
    s_last_change_ms = 0;
    s_last_raw       = false;
}

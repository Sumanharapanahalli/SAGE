/**
 * @file sos_button.h
 * @brief SOS button debounce and long-press detection for elder fall detection wearable.
 *
 * IEC 62304 Classification: Class B software unit
 * Software Unit ID: SU-SOS-001
 */

#ifndef SOS_BUTTON_H
#define SOS_BUTTON_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SOS_DEBOUNCE_MS             50U
#define SOS_LONG_PRESS_ARMED_MS   3000U
#define SOS_LONG_PRESS_CONFIRM_MS 5000U
#define SOS_CANCEL_WINDOW_MS       500U

typedef enum {
    SOS_EVENT_NONE               = 0,
    SOS_EVENT_SHORT_PRESS        = 1,
    SOS_EVENT_LONG_PRESS_ARMED   = 2,
    SOS_EVENT_LONG_PRESS_CONFIRMED = 3,
    SOS_EVENT_CANCELLED          = 4,
    SOS_EVENT_BOUNCE_FILTERED    = 5,
} SOSEvent;

void     sos_button_init(void);
SOSEvent sos_button_process(bool pressed, uint32_t timestamp_ms);
bool     sos_button_is_armed(void);
void     sos_button_reset(void);
uint32_t sos_button_get_press_duration_ms(uint32_t current_time_ms);

#ifdef __cplusplus
}
#endif
#endif /* SOS_BUTTON_H */

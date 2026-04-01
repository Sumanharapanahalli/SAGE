/**
 * @file fall_detection.h
 * @brief Fall detection module interface — IMU-based algorithm.
 *
 * Uses LSM6DSO 6-axis IMU over SPI.  The algorithm combines:
 *   1. Free-fall detection (hardware threshold in IMU register)
 *   2. Impact detection (high-g threshold crossing)
 *   3. Post-impact stillness confirmation (inactivity > 2 s)
 *
 * On confirmed fall:  posts EVT_FALL_DETECTED to orchestrator queue.
 * On user cancel:     posts EVT_FALL_CANCELLED (button press within 15 s).
 *
 * SRS-001  Fall event detected within 200 ms of occurrence.
 *
 * @version 1.0.0
 */

#ifndef FALL_DETECTION_H
#define FALL_DETECTION_H

#include <stdint.h>
#include <stdbool.h>
#include <zephyr/kernel.h>

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Tunable parameters (in Kconfig / compile-time; not runtime-adjustable
 * without OTA to preserve IEC 62304 validation traceability)
 * ------------------------------------------------------------------------- */
#define FALL_FREE_FALL_THRESH_MG   400U   /**< Free-fall accel threshold (mg)  */
#define FALL_IMPACT_THRESH_MG     3000U   /**< Impact accel threshold (mg)     */
#define FALL_STILLNESS_THRESH_MG   100U   /**< Max accel for "still" (mg)      */
#define FALL_STILLNESS_DUR_MS     2000U   /**< Stillness duration to confirm   */
#define FALL_CANCEL_WINDOW_MS    15000U   /**< User cancel window after detect */

/* -------------------------------------------------------------------------
 * Module state (opaque to callers; exposed only for unit test access)
 * ------------------------------------------------------------------------- */
typedef enum fall_state {
    FALL_STATE_IDLE       = 0,
    FALL_STATE_FREE_FALL  = 1,
    FALL_STATE_IMPACT     = 2,
    FALL_STATE_STILLNESS  = 3,
    FALL_STATE_CONFIRMED  = 4,
    FALL_STATE_CANCELLED  = 5,
} fall_state_t;

/* -------------------------------------------------------------------------
 * Public API
 * ------------------------------------------------------------------------- */

/**
 * @brief Initialise fall detection subsystem.
 *
 * Configures LSM6DSO via SPI, enables hardware free-fall interrupt on
 * INT1 pin (GPIO interrupt configured with K_PRIO_PREEMPT(1)).
 * Spawns fall_detection_thread (stack 1024 B, priority 2).
 *
 * @return 0 on success, negative errno on SPI/GPIO init failure.
 */
int fall_detection_init(void);

/**
 * @brief Get current fall detection state (for diagnostics/BLE reporting).
 */
fall_state_t fall_detection_get_state(void);

/**
 * @brief Signal user cancel (e.g., button press from UI task).
 *
 * Only effective when in FALL_STATE_CONFIRMED within cancel window.
 * Posts EVT_FALL_CANCELLED to orchestrator queue.
 */
void fall_detection_cancel(void);

/**
 * @brief Return number of confirmed falls since boot (audit counter).
 */
uint32_t fall_detection_count(void);

#ifdef __cplusplus
}
#endif

#endif /* FALL_DETECTION_H */

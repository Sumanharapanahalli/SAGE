/**
 * @file fall_detection.h
 * @brief Fall detection algorithm for elder fall detection wearable.
 *
 * Algorithm: free-fall phase (|accel| < threshold_low for >= min_ms)
 *            → impact phase (|accel| > threshold_high spike)
 *            → post-fall orientation check (sustained non-upright tilt)
 *
 * IEC 62304 Classification: Class B software unit
 * Software Unit ID: SU-FALL-001
 */

#ifndef FALL_DETECTION_H
#define FALL_DETECTION_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* -------------------------------------------------------------------------
 * Constants
 * ---------------------------------------------------------------------- */
#define FALL_G_MS2              9.81f   /**< 1g in m/s^2 */
#define FALL_FREEFALL_THRESH_G  0.40f  /**< |accel| < 0.4g => free-fall   */
#define FALL_IMPACT_THRESH_G    2.00f  /**< |accel| > 2.0g => impact       */
#define FALL_FREEFALL_MIN_MS    80U    /**< min free-fall window (ms)       */
#define FALL_MONITOR_WINDOW_MS  2000U  /**< post-impact monitoring (ms)     */
#define FALL_UPRIGHT_MAX_DEG    45.0f  /**< max tilt angle for "upright"    */
#define FALL_SAMPLE_RATE_HZ     100U   /**< IMU sample rate                 */

/* -------------------------------------------------------------------------
 * Types
 * ---------------------------------------------------------------------- */

/** Raw IMU sample — values in SI units */
typedef struct {
    float    accel_x;       /**< m/s^2, X-axis (device forward)  */
    float    accel_y;       /**< m/s^2, Y-axis (device lateral)  */
    float    accel_z;       /**< m/s^2, Z-axis (device vertical) */
    float    gyro_x;        /**< deg/s, pitch rate               */
    float    gyro_y;        /**< deg/s, roll rate                */
    float    gyro_z;        /**< deg/s, yaw rate                 */
    uint32_t timestamp_ms;  /**< monotonic milliseconds          */
} IMUSample;

/** Fall detection algorithm configuration */
typedef struct {
    float    freefall_threshold_g;  /**< g units, default FALL_FREEFALL_THRESH_G */
    float    impact_threshold_g;    /**< g units, default FALL_IMPACT_THRESH_G   */
    uint32_t freefall_min_ms;       /**< ms,      default FALL_FREEFALL_MIN_MS   */
    uint32_t monitor_window_ms;     /**< ms,      default FALL_MONITOR_WINDOW_MS */
    float    upright_max_deg;       /**< degrees, default FALL_UPRIGHT_MAX_DEG   */
} FallDetectionConfig;

/** Result returned by fall_detection_process() */
typedef enum {
    FALL_RESULT_NONE      = 0,  /**< No fall event                    */
    FALL_RESULT_POSSIBLE  = 1,  /**< Free-fall phase detected, watching*/
    FALL_RESULT_DETECTED  = 2,  /**< Full fall pattern confirmed       */
} FallDetectionResult;

/** Internal FSM states (exposed for white-box testing) */
typedef enum {
    FALL_STATE_IDLE       = 0,
    FALL_STATE_FREEFALL   = 1,
    FALL_STATE_IMPACT     = 2,
    FALL_STATE_MONITORING = 3,
} FallDetectionState;

/** Cumulative statistics */
typedef struct {
    uint32_t total_samples;
    uint32_t freefall_events;
    uint32_t impact_events;
    uint32_t confirmed_falls;
    uint32_t stumbles;
} FallDetectionStats;

/* -------------------------------------------------------------------------
 * API
 * ---------------------------------------------------------------------- */

/**
 * @brief Initialise the fall detection module.
 * @param cfg  Configuration; pass NULL to use defaults.
 */
void fall_detection_init(const FallDetectionConfig *cfg);

/**
 * @brief Feed one IMU sample into the algorithm.
 * @param sample  Pointer to IMU sample (must not be NULL).
 * @return FALL_RESULT_DETECTED on confirmed fall, FALL_RESULT_POSSIBLE
 *         during free-fall phase, FALL_RESULT_NONE otherwise.
 */
FallDetectionResult fall_detection_process(const IMUSample *sample);

/** @brief Returns true when device orientation is upright (within threshold). */
bool fall_detection_is_upright(void);

/** @brief Returns the vector magnitude |accel| in m/s^2. */
float fall_detection_get_accel_magnitude(const IMUSample *sample);

/** @brief Returns current FSM state (for white-box unit tests). */
FallDetectionState fall_detection_get_state(void);

/** @brief Returns cumulative event statistics. */
void fall_detection_get_stats(FallDetectionStats *stats_out);

/** @brief Reset algorithm state and statistics. */
void fall_detection_reset(void);

#ifdef __cplusplus
}
#endif
#endif /* FALL_DETECTION_H */

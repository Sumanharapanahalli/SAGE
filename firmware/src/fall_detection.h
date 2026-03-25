/**
 * @file fall_detection.h
 * @brief Fall Detection Algorithm — IMU-based (accelerometer + gyroscope)
 *
 * IEC 62304 Classification : Software Class B
 *   - Not life-sustaining, but safety-relevant: incorrect operation can result
 *     in failure to alert caregivers of a fall, leading to prolonged injury.
 *   - Requires documented design, unit tests, integration tests, and risk analysis.
 *
 * Algorithm Overview:
 *   Phase 1 — Free-fall detection : |a| < FREEFALL_THRESHOLD_G for >= FREEFALL_MIN_MS
 *   Phase 2 — Impact detection    : |a| > IMPACT_THRESHOLD_G within IMPACT_WAIT_MS
 *   Phase 3 — Stillness detection : low accel + gyro variance for STILLNESS_WINDOW_MS
 *   Override— SOS button          : generates FALL_EVENT within SOS_RESPONSE_TIME_MS
 *
 * Confidence scoring (0-100):
 *   30% freefall duration  +  40% impact magnitude  +  30% post-impact stillness
 *
 * @version  1.0.0
 * @date     2026-03-21
 */

#ifndef FALL_DETECTION_H
#define FALL_DETECTION_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* =========================================================================
 * Version
 * ========================================================================= */
#define FALL_DETECTION_VERSION_MAJOR  1u
#define FALL_DETECTION_VERSION_MINOR  0u
#define FALL_DETECTION_VERSION_PATCH  0u

/* =========================================================================
 * Algorithm Thresholds (tuned against validated 200-event dataset)
 * ========================================================================= */
#define FREEFALL_THRESHOLD_G         0.5f   /**< |a| < this → free-fall         */
#define IMPACT_THRESHOLD_G           3.0f   /**< |a| > this → impact detected    */
#define STILLNESS_ACCEL_THRESHOLD_G  0.3f   /**< |a| variance < this → still     */
#define STILLNESS_GYRO_THRESHOLD_RS  0.5f   /**< |ω| < this rad/s → still        */

/* =========================================================================
 * Timing Parameters (at SAMPLE_RATE_HZ = 100 Hz)
 * ========================================================================= */
#define SAMPLE_RATE_HZ               100u   /**< IMU sample rate (Hz)            */
#define FREEFALL_MIN_MS              100u   /**< Min free-fall duration to count  */
#define FREEFALL_WINDOW_MS           500u   /**< Max free-fall window (sliding)   */
#define IMPACT_WAIT_MS               500u   /**< Max ms to wait for impact after  */
                                            /**< free-fall ends                   */
#define STILLNESS_WINDOW_MS          2000u  /**< Post-impact stillness check (ms) */
#define SOS_RESPONSE_TIME_MS         100u   /**< SOS → event max latency (ms)    */

/* Derived sample counts */
#define FREEFALL_MIN_SAMPLES  (FREEFALL_MIN_MS    * SAMPLE_RATE_HZ / 1000u)  /* 10  */
#define FREEFALL_MAX_SAMPLES  (FREEFALL_WINDOW_MS * SAMPLE_RATE_HZ / 1000u)  /* 50  */
#define IMPACT_WAIT_SAMPLES   (IMPACT_WAIT_MS     * SAMPLE_RATE_HZ / 1000u)  /* 50  */
#define STILLNESS_SAMPLES     (STILLNESS_WINDOW_MS* SAMPLE_RATE_HZ / 1000u)  /* 200 */

/* =========================================================================
 * Confidence
 * ========================================================================= */
#define CONFIDENCE_MIN_PERCENT       75u    /**< Minimum to emit FALL_EVENT       */

/* =========================================================================
 * Snapshot buffer : 1 second (50 pre-impact + 50 post-impact samples)
 * ========================================================================= */
#define SNAPSHOT_PRE_SAMPLES         50u
#define SNAPSHOT_POST_SAMPLES        50u
#define SNAPSHOT_TOTAL_SAMPLES       (SNAPSHOT_PRE_SAMPLES + SNAPSHOT_POST_SAMPLES)

/* =========================================================================
 * Error codes
 * ========================================================================= */
typedef enum {
    FALL_ERR_OK           =  0,  /**< Success                              */
    FALL_ERR_NULL_PTR     = -1,  /**< NULL pointer argument                */
    FALL_ERR_NOT_INIT     = -2,  /**< Module not initialised               */
    FALL_ERR_ALREADY_INIT = -3,  /**< Module already initialised           */
    FALL_ERR_INVALID_CFG  = -4,  /**< Configuration value out of range     */
    FALL_ERR_BUSY         = -5,  /**< SOS called while event in progress   */
} FallErr;

/* =========================================================================
 * Data types
 * ========================================================================= */

/** 3-axis floating-point vector */
typedef struct {
    float x;
    float y;
    float z;
} Vec3f;

/** Single IMU sample */
typedef struct {
    int64_t timestamp_ms;   /**< Monotonic timestamp in milliseconds      */
    Vec3f   accel_g;        /**< Accelerometer reading (g)                */
    Vec3f   gyro_rs;        /**< Gyroscope reading (rad/s)                */
} IMUSample;

/** Raw sensor snapshot captured at event time for post-hoc review */
typedef struct {
    IMUSample samples[SNAPSHOT_TOTAL_SAMPLES];
    uint16_t  count;        /**< Actual valid samples (≤ SNAPSHOT_TOTAL)  */
    uint16_t  impact_index; /**< Index within samples[] where impact hit  */
} SensorSnapshot;

/** FALL_EVENT output structure */
typedef struct {
    int64_t        timestamp_ms;        /**< When event was generated (ms)   */
    uint8_t        confidence_percent;  /**< 0-100; only emitted if ≥ min    */
    bool           sos_triggered;       /**< true if SOS button caused event  */
    float          peak_impact_g;       /**< Peak |a| during impact phase     */
    float          freefall_duration_ms;/**< Duration of free-fall phase (ms) */
    float          stillness_variance_g;/**< Post-impact accel variance       */
    SensorSnapshot snapshot;            /**< Raw sensor data around event     */
    char           source[16];          /**< "ALGORITHM" or "SOS_BUTTON"      */
} FallEvent;

/** Algorithm state (read-only via fall_detection_get_state) */
typedef enum {
    FALL_STATE_IDLE        = 0,
    FALL_STATE_FREEFALL    = 1,
    FALL_STATE_IMPACT_WAIT = 2,
    FALL_STATE_POST_IMPACT = 3,
    FALL_STATE_CONFIRMED   = 4,
} FallDetectionState;

/** Runtime statistics */
typedef struct {
    uint32_t total_events;   /**< Total FALL_EVENTs emitted                */
    uint32_t algo_events;    /**< Events from algorithm                    */
    uint32_t sos_events;     /**< Events from SOS button                   */
    uint32_t rejected_low_confidence; /**< Events suppressed (low conf)    */
} FallStats;

/** Configuration — pass to fall_detection_init; validated on init */
typedef struct {
    float    freefall_threshold_g;       /**< Default: FREEFALL_THRESHOLD_G  */
    float    impact_threshold_g;         /**< Default: IMPACT_THRESHOLD_G    */
    float    stillness_accel_threshold_g;/**< Default: STILLNESS_ACCEL_*     */
    float    stillness_gyro_threshold_rs;/**< Default: STILLNESS_GYRO_*      */
    uint16_t freefall_min_samples;       /**< Default: FREEFALL_MIN_SAMPLES  */
    uint16_t freefall_max_samples;       /**< Default: FREEFALL_MAX_SAMPLES  */
    uint16_t impact_wait_samples;        /**< Default: IMPACT_WAIT_SAMPLES   */
    uint16_t stillness_samples;          /**< Default: STILLNESS_SAMPLES     */
    uint8_t  confidence_min_percent;     /**< Default: CONFIDENCE_MIN_PERCENT */
} FallDetectionConfig;

/** Callback invoked when a FALL_EVENT is ready (from task or ISR context) */
typedef void (*FallEventCallback)(const FallEvent *event, void *user_data);

/* =========================================================================
 * Public API
 * ========================================================================= */

/**
 * @brief  Initialise the fall detection module.
 * @param  config   Algorithm configuration (NULL → use defaults).
 * @param  callback Function called on every FALL_EVENT (must be non-NULL).
 * @param  user_data Opaque pointer forwarded to callback.
 * @return FALL_ERR_OK on success, error code otherwise.
 */
FallErr fall_detection_init(const FallDetectionConfig *config,
                             FallEventCallback          callback,
                             void                      *user_data);

/**
 * @brief  Feed one IMU sample into the algorithm.
 *         Call at SAMPLE_RATE_HZ from your IMU task.
 *         Thread-safe; may be called from a FreeRTOS task.
 * @param  sample  Pointer to the current IMU reading.
 * @return FALL_ERR_OK or FALL_ERR_NOT_INIT.
 */
FallErr fall_detection_process(const IMUSample *sample);

/**
 * @brief  Trigger an immediate FALL_EVENT from SOS button press.
 *         Safe to call from GPIO ISR context.
 *         Guarantees event emission within SOS_RESPONSE_TIME_MS.
 * @return FALL_ERR_OK or FALL_ERR_NOT_INIT.
 */
FallErr fall_detection_sos_trigger(void);

/**
 * @brief  Reset state machine to IDLE (e.g. after false positive confirmed).
 * @return FALL_ERR_OK or FALL_ERR_NOT_INIT.
 */
FallErr fall_detection_reset(void);

/**
 * @brief  Return current algorithm state (for diagnostics).
 */
FallDetectionState fall_detection_get_state(void);

/**
 * @brief  Fill *stats with runtime counters.
 * @return FALL_ERR_OK or FALL_ERR_NOT_INIT.
 */
FallErr fall_detection_get_stats(FallStats *stats);

/**
 * @brief  Return default configuration values.
 */
FallDetectionConfig fall_detection_default_config(void);

#ifdef __cplusplus
}
#endif

#endif /* FALL_DETECTION_H */

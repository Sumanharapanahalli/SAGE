/**
 * @file fall_detection.c
 * @brief Fall detection algorithm implementation.
 *
 * Algorithm phases:
 *  1. IDLE:       Baseline monitoring, compute rolling |accel|
 *  2. FREEFALL:   |accel| < freefall_threshold * g, sustained for freefall_min_ms
 *  3. IMPACT:     |accel| > impact_threshold * g following free-fall
 *  4. MONITORING: Check orientation for post_fall_monitor_ms;
 *                 if non-upright → FALL_RESULT_DETECTED
 *                 if returns upright within window → FALL_RESULT_NONE (stumble)
 */

#include "fall_detection.h"
#include <math.h>
#include <string.h>

/* -------------------------------------------------------------------------
 * Private state
 * ---------------------------------------------------------------------- */

static FallDetectionConfig s_cfg;
static FallDetectionState  s_state;
static FallDetectionStats  s_stats;

static uint32_t s_freefall_start_ms;
static uint32_t s_impact_time_ms;
static float    s_tilt_angle_deg;   /* latest computed tilt from vertical */

/* -------------------------------------------------------------------------
 * Private helpers
 * ---------------------------------------------------------------------- */

static float _vec_magnitude(float x, float y, float z)
{
    return sqrtf(x * x + y * y + z * z);
}

/** Compute tilt angle from vertical using accel vector.
 *  0° = perfectly upright (az = +g), 90° = horizontal, 180° = inverted. */
static float _compute_tilt_deg(float ax, float ay, float az)
{
    float mag = _vec_magnitude(ax, ay, az);
    if (mag < 0.01f) {
        return 90.0f;  /* effectively horizontal / free-fall, undefined */
    }
    /* Angle between accel vector and +Z axis */
    float cos_theta = az / mag;
    /* Clamp to [-1, 1] to guard against floating-point rounding */
    if (cos_theta >  1.0f) cos_theta =  1.0f;
    if (cos_theta < -1.0f) cos_theta = -1.0f;
    return (float)(acos((double)cos_theta) * 180.0 / M_PI);
}

/* -------------------------------------------------------------------------
 * Public API
 * ---------------------------------------------------------------------- */

void fall_detection_init(const FallDetectionConfig *cfg)
{
    if (cfg != NULL) {
        s_cfg = *cfg;
    } else {
        s_cfg.freefall_threshold_g = FALL_FREEFALL_THRESH_G;
        s_cfg.impact_threshold_g   = FALL_IMPACT_THRESH_G;
        s_cfg.freefall_min_ms      = FALL_FREEFALL_MIN_MS;
        s_cfg.monitor_window_ms    = FALL_MONITOR_WINDOW_MS;
        s_cfg.upright_max_deg      = FALL_UPRIGHT_MAX_DEG;
    }
    fall_detection_reset();
}

FallDetectionResult fall_detection_process(const IMUSample *sample)
{
    if (sample == NULL) {
        return FALL_RESULT_NONE;
    }

    s_stats.total_samples++;

    float mag_ms2 = _vec_magnitude(sample->accel_x, sample->accel_y, sample->accel_z);
    float mag_g   = mag_ms2 / FALL_G_MS2;
    s_tilt_angle_deg = _compute_tilt_deg(sample->accel_x,
                                         sample->accel_y,
                                         sample->accel_z);

    switch (s_state) {

    case FALL_STATE_IDLE:
        if (mag_g < s_cfg.freefall_threshold_g) {
            s_state             = FALL_STATE_FREEFALL;
            s_freefall_start_ms = sample->timestamp_ms;
            s_stats.freefall_events++;
        }
        break;

    case FALL_STATE_FREEFALL:
        if (mag_g >= s_cfg.freefall_threshold_g) {
            /* Free-fall ended before minimum duration — reset */
            s_state = FALL_STATE_IDLE;
            break;
        }
        if (mag_g > s_cfg.impact_threshold_g) {
            /* Impact during free-fall phase (shouldn't normally happen, but handle) */
            uint32_t ff_dur = sample->timestamp_ms - s_freefall_start_ms;
            if (ff_dur >= s_cfg.freefall_min_ms) {
                s_state          = FALL_STATE_MONITORING;
                s_impact_time_ms = sample->timestamp_ms;
                s_stats.impact_events++;
            } else {
                s_state = FALL_STATE_IDLE;
            }
        }
        /* Otherwise: still in free-fall, return POSSIBLE */
        return FALL_RESULT_POSSIBLE;

    case FALL_STATE_IMPACT:
        /* Transition to monitoring once impact spike subsides */
        if (mag_g < s_cfg.impact_threshold_g) {
            s_state = FALL_STATE_MONITORING;
        }
        return FALL_RESULT_POSSIBLE;

    case FALL_STATE_MONITORING: {
        uint32_t elapsed = sample->timestamp_ms - s_impact_time_ms;

        if (elapsed > s_cfg.monitor_window_ms) {
            /* Window expired — person never recovered upright → confirmed fall */
            s_state = FALL_STATE_IDLE;
            if (s_tilt_angle_deg > s_cfg.upright_max_deg) {
                s_stats.confirmed_falls++;
                return FALL_RESULT_DETECTED;
            } else {
                /* Recovered → stumble */
                s_stats.stumbles++;
                return FALL_RESULT_NONE;
            }
        }

        if (s_tilt_angle_deg > s_cfg.upright_max_deg) {
            /* Non-upright within window — early detection */
            if (elapsed >= s_cfg.freefall_min_ms) {
                s_state = FALL_STATE_IDLE;
                s_stats.confirmed_falls++;
                return FALL_RESULT_DETECTED;
            }
        } else {
            /* Returned upright quickly → stumble, not fall */
            s_state = FALL_STATE_IDLE;
            s_stats.stumbles++;
            return FALL_RESULT_NONE;
        }
        return FALL_RESULT_POSSIBLE;
    }

    default:
        s_state = FALL_STATE_IDLE;
        break;
    }

    return FALL_RESULT_NONE;
}

bool fall_detection_is_upright(void)
{
    return s_tilt_angle_deg <= s_cfg.upright_max_deg;
}

float fall_detection_get_accel_magnitude(const IMUSample *sample)
{
    if (sample == NULL) {
        return 0.0f;
    }
    return _vec_magnitude(sample->accel_x, sample->accel_y, sample->accel_z);
}

FallDetectionState fall_detection_get_state(void)
{
    return s_state;
}

void fall_detection_get_stats(FallDetectionStats *stats_out)
{
    if (stats_out != NULL) {
        *stats_out = s_stats;
    }
}

void fall_detection_reset(void)
{
    s_state             = FALL_STATE_IDLE;
    s_freefall_start_ms = 0;
    s_impact_time_ms    = 0;
    s_tilt_angle_deg    = 0.0f;
    memset(&s_stats, 0, sizeof(s_stats));
}

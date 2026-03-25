/**
 * @file test_fall_detection.c
 * @brief Unity unit tests for fall detection algorithm.
 *
 * 50 test cases covering:
 *   FD_001-010: Forward fall (pitch-forward free-fall → impact → face-down)
 *   FD_011-020: Backward fall (pitch-back free-fall → impact → face-up)
 *   FD_021-030: Side fall (roll-left/right free-fall → impact → lateral)
 *   FD_031-040: Stumble — acceleration spike WITHOUT sustained free-fall
 *   FD_041-050: Sitting down — controlled, no free-fall, gradual orientation
 *
 * IEC 62304 Verification Reference: VR-SU-FALL-001
 */

#include "unity.h"
#include "fall_detection.h"
#include <math.h>
#include <string.h>

/* -------------------------------------------------------------------------
 * Test helpers — IMU sequence builders
 * ---------------------------------------------------------------------- */

#define G       9.81f
#define DT_MS   10U          /* 100 Hz sample interval                 */

/** Feed N idle (upright, no motion) samples starting at t=start_ms */
static uint32_t feed_idle(uint32_t start_ms, uint32_t count)
{
    IMUSample s;
    for (uint32_t i = 0; i < count; i++) {
        s.accel_x    =  0.0f;
        s.accel_y    =  0.0f;
        s.accel_z    =  G;      /* 1g up — standing still */
        s.gyro_x     =  0.0f;
        s.gyro_y     =  0.0f;
        s.gyro_z     =  0.0f;
        s.timestamp_ms = start_ms + i * DT_MS;
        fall_detection_process(&s);
    }
    return start_ms + count * DT_MS;
}

/** Feed free-fall phase: |accel| ~ 0.15g (weightless) for duration_ms */
static uint32_t feed_freefall(uint32_t start_ms, uint32_t duration_ms,
                               FallDetectionResult *last_result)
{
    IMUSample s;
    uint32_t  count = duration_ms / DT_MS;
    FallDetectionResult r = FALL_RESULT_NONE;
    for (uint32_t i = 0; i < count; i++) {
        s.accel_x    =  0.10f * G;
        s.accel_y    =  0.05f * G;
        s.accel_z    =  0.05f * G;   /* ~0.12g total */
        s.gyro_x     = 45.0f;        /* pitching */
        s.gyro_y     =  0.0f;
        s.gyro_z     =  0.0f;
        s.timestamp_ms = start_ms + i * DT_MS;
        r = fall_detection_process(&s);
    }
    if (last_result) *last_result = r;
    return start_ms + count * DT_MS;
}

/** Feed impact: spike of impact_g for 2 samples */
static uint32_t feed_impact(uint32_t start_ms, float impact_g,
                              float ax, float ay, float az_sign)
{
    IMUSample s;
    /* Spike sample 1 */
    s.accel_x    =  ax * impact_g * G;
    s.accel_y    =  ay * impact_g * G;
    s.accel_z    =  az_sign * impact_g * G;
    s.gyro_x     = 200.0f;
    s.gyro_y     =   0.0f;
    s.gyro_z     =   0.0f;
    s.timestamp_ms = start_ms;
    fall_detection_process(&s);
    /* Spike sample 2 */
    s.timestamp_ms = start_ms + DT_MS;
    fall_detection_process(&s);
    return start_ms + 2 * DT_MS;
}

/** Feed post-fall orientation: lying face-down (tilt > 90°) for duration_ms */
static uint32_t feed_face_down(uint32_t start_ms, uint32_t duration_ms,
                                FallDetectionResult *last_result)
{
    IMUSample s;
    uint32_t count = duration_ms / DT_MS;
    FallDetectionResult r = FALL_RESULT_NONE;
    for (uint32_t i = 0; i < count; i++) {
        s.accel_x    =  0.0f;
        s.accel_y    =  0.0f;
        s.accel_z    = -G;      /* inverted — face down */
        s.gyro_x     =  0.0f;
        s.gyro_y     =  0.0f;
        s.gyro_z     =  0.0f;
        s.timestamp_ms = start_ms + i * DT_MS;
        r = fall_detection_process(&s);
    }
    if (last_result) *last_result = r;
    return start_ms + count * DT_MS;
}

/** Feed face-up orientation (backward fall final position) */
static uint32_t feed_face_up(uint32_t start_ms, uint32_t duration_ms,
                               FallDetectionResult *last_result)
{
    IMUSample s;
    uint32_t count = duration_ms / DT_MS;
    FallDetectionResult r = FALL_RESULT_NONE;
    for (uint32_t i = 0; i < count; i++) {
        s.accel_x    =  0.0f;
        s.accel_y    =  0.0f;
        s.accel_z    =  G;     /* face up, horizontal  — tilt ≈ 0 but lying flat */
        /* Simulate lying on back: ay = G (side), az = 0 actually...
         * Real backward fall: person on back → az≈0, ay=G → tilt≈90° from +Z */
        s.accel_x    =  0.0f;
        s.accel_y    =  G;
        s.accel_z    =  0.0f;  /* lying on back, tilt = 90° */
        s.gyro_x     =  0.0f;
        s.gyro_y     =  0.0f;
        s.gyro_z     =  0.0f;
        s.timestamp_ms = start_ms + i * DT_MS;
        r = fall_detection_process(&s);
    }
    if (last_result) *last_result = r;
    return start_ms + count * DT_MS;
}

/** Feed lateral orientation (side fall) */
static uint32_t feed_lateral(uint32_t start_ms, uint32_t duration_ms,
                               FallDetectionResult *last_result)
{
    IMUSample s;
    uint32_t count = duration_ms / DT_MS;
    FallDetectionResult r = FALL_RESULT_NONE;
    for (uint32_t i = 0; i < count; i++) {
        s.accel_x    =  G;      /* lying on side, roll 90° */
        s.accel_y    =  0.0f;
        s.accel_z    =  0.0f;
        s.gyro_x     =  0.0f;
        s.gyro_y     =  0.0f;
        s.gyro_z     =  0.0f;
        s.timestamp_ms = start_ms + i * DT_MS;
        r = fall_detection_process(&s);
    }
    if (last_result) *last_result = r;
    return start_ms + count * DT_MS;
}

/** Feed upright recovery after stumble */
static uint32_t feed_upright_recovery(uint32_t start_ms, uint32_t duration_ms)
{
    IMUSample s;
    uint32_t count = duration_ms / DT_MS;
    for (uint32_t i = 0; i < count; i++) {
        s.accel_x    =  0.0f;
        s.accel_y    =  0.0f;
        s.accel_z    =  G;
        s.gyro_x     =  0.0f;
        s.gyro_y     =  0.0f;
        s.gyro_z     =  0.0f;
        s.timestamp_ms = start_ms + i * DT_MS;
        fall_detection_process(&s);
    }
    return start_ms + count * DT_MS;
}

/** Feed sitting-down: gradual tilt from 0° to ~30° (still within upright) */
static uint32_t feed_sit_down(uint32_t start_ms, uint32_t duration_ms,
                                FallDetectionResult *last_result)
{
    IMUSample s;
    uint32_t count = duration_ms / DT_MS;
    FallDetectionResult r = FALL_RESULT_NONE;
    for (uint32_t i = 0; i < count; i++) {
        float progress = (float)i / (float)count;
        float tilt_rad = progress * 30.0f * (float)M_PI / 180.0f;
        /* Simulate sitting: body leans forward ~30° */
        s.accel_x    =  sinf(tilt_rad) * G * 0.5f;
        s.accel_y    =  0.0f;
        s.accel_z    =  cosf(tilt_rad) * G;
        s.gyro_x     =  5.0f;   /* slow rotation */
        s.gyro_y     =  0.0f;
        s.gyro_z     =  0.0f;
        /* Magnitude stays close to 1g (no free-fall) */
        s.timestamp_ms = start_ms + i * DT_MS;
        r = fall_detection_process(&s);
    }
    if (last_result) *last_result = r;
    return start_ms + count * DT_MS;
}

/* -------------------------------------------------------------------------
 * setUp / tearDown
 * ---------------------------------------------------------------------- */

void setUp(void)
{
    fall_detection_init(NULL);  /* Reset with default config */
}

void tearDown(void)
{
    fall_detection_reset();
}

/* =========================================================================
 * GROUP 1: Forward fall (FD_001 – FD_010)
 * ========================================================================= */

/* FD_001: Full forward fall sequence produces FALL_RESULT_DETECTED */
void test_FD_001_forward_fall_detected(void)
{
    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 120, &r);               /* 120ms free-fall (> 80ms min) */
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_POSSIBLE, r);
    t = feed_impact(t, 3.5f, 0.0f, 0.0f, -1.0f);
    t = feed_face_down(t, 200, &r);
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_DETECTED, r);
}

/* FD_002: Forward fall confirmed — statistics counter increments */
void test_FD_002_forward_fall_stats_increment(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 120, NULL);
    t = feed_impact(t, 3.5f, 0.0f, 0.0f, -1.0f);
    feed_face_down(t, 200, NULL);

    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_EQUAL_UINT32(1, stats.confirmed_falls);
}

/* FD_003: Free-fall phase alone returns FALL_RESULT_POSSIBLE */
void test_FD_003_freefall_phase_returns_possible(void)
{
    FallDetectionResult r = FALL_RESULT_NONE;
    feed_freefall(0, 100, &r);
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_POSSIBLE, r);
}

/* FD_004: FSM enters FREEFALL state on free-fall detection */
void test_FD_004_fsm_enters_freefall_state(void)
{
    feed_freefall(0, 50, NULL);
    TEST_ASSERT_EQUAL_INT(FALL_STATE_FREEFALL, fall_detection_get_state());
}

/* FD_005: Forward fall — is_upright() returns false after impact */
void test_FD_005_not_upright_after_forward_fall(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 120, NULL);
    t = feed_impact(t, 3.5f, 0.0f, 0.0f, -1.0f);
    feed_face_down(t, 50, NULL);
    TEST_ASSERT_FALSE(fall_detection_is_upright());
}

/* FD_006: Forward fall with moderate impact (2.5g) still detected */
void test_FD_006_forward_fall_moderate_impact(void)
{
    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 100, NULL);
    t = feed_impact(t, 2.5f, 0.0f, 0.0f, -1.0f);
    t = feed_face_down(t, 200, &r);
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_DETECTED, r);
}

/* FD_007: Forward fall — freefall_events counter increments once */
void test_FD_007_freefall_event_counted(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 120, NULL);
    t = feed_impact(t, 3.5f, 0.0f, 0.0f, -1.0f);
    feed_face_down(t, 200, NULL);

    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_GREATER_OR_EQUAL_UINT32(1, stats.freefall_events);
}

/* FD_008: Two sequential forward falls each detected */
void test_FD_008_two_sequential_forward_falls(void)
{
    uint32_t t = 0;
    /* First fall */
    t = feed_idle(t, 10);
    t = feed_freefall(t, 120, NULL);
    t = feed_impact(t, 3.5f, 0.0f, 0.0f, -1.0f);
    t = feed_face_down(t, 200, NULL);
    t = feed_idle(t, 20);   /* person gets up */
    /* Second fall */
    t = feed_freefall(t, 120, NULL);
    t = feed_impact(t, 3.5f, 0.0f, 0.0f, -1.0f);
    FallDetectionResult r = FALL_RESULT_NONE;
    feed_face_down(t, 200, &r);

    TEST_ASSERT_EQUAL_INT(FALL_RESULT_DETECTED, r);
    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_EQUAL_UINT32(2, stats.confirmed_falls);
}

/* FD_009: Forward fall — accel magnitude during free-fall < 0.4g */
void test_FD_009_freefall_magnitude_below_threshold(void)
{
    IMUSample s = {0.10f * G, 0.05f * G, 0.05f * G, 0.0f, 0.0f, 0.0f, 0};
    float mag = fall_detection_get_accel_magnitude(&s);
    TEST_ASSERT_LESS_THAN_FLOAT(FALL_FREEFALL_THRESH_G * G, mag);
}

/* FD_010: Forward fall — accel magnitude during impact > 2g */
void test_FD_010_impact_magnitude_above_threshold(void)
{
    IMUSample s = {0.0f, 0.0f, 3.5f * G, 0.0f, 0.0f, 0.0f, 0};
    float mag = fall_detection_get_accel_magnitude(&s);
    TEST_ASSERT_GREATER_THAN_FLOAT(FALL_IMPACT_THRESH_G * G, mag);
}

/* =========================================================================
 * GROUP 2: Backward fall (FD_011 – FD_020)
 * ========================================================================= */

/* FD_011: Backward fall detected (lying on back) */
void test_FD_011_backward_fall_detected(void)
{
    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 110, NULL);
    t = feed_impact(t, 3.0f, 0.0f, 1.0f, 0.0f);   /* ax=0, ay=spike */
    t = feed_face_up(t, 200, &r);
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_DETECTED, r);
}

/* FD_012: Backward fall — body horizontal on back (tilt ~90°) not upright */
void test_FD_012_backward_fall_not_upright(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 110, NULL);
    t = feed_impact(t, 3.0f, 0.0f, 1.0f, 0.0f);
    feed_face_up(t, 50, NULL);
    TEST_ASSERT_FALSE(fall_detection_is_upright());
}

/* FD_013: Backward fall confirmation increments counter */
void test_FD_013_backward_fall_counter_increments(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 110, NULL);
    t = feed_impact(t, 3.0f, 0.0f, 1.0f, 0.0f);
    feed_face_up(t, 200, NULL);

    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_EQUAL_UINT32(1, stats.confirmed_falls);
}

/* FD_014: Backward fall FSM returns to IDLE after detection */
void test_FD_014_backward_fall_fsm_returns_idle(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 110, NULL);
    t = feed_impact(t, 3.0f, 0.0f, 1.0f, 0.0f);
    feed_face_up(t, 200, NULL);
    TEST_ASSERT_EQUAL_INT(FALL_STATE_IDLE, fall_detection_get_state());
}

/* FD_015: Backward fall at minimum impact threshold (exactly 2g) detected */
void test_FD_015_backward_fall_exact_impact_threshold(void)
{
    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 100, NULL);
    t = feed_impact(t, 2.01f, 0.0f, 0.0f, 1.0f);   /* just above threshold */
    t = feed_face_up(t, 200, &r);
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_DETECTED, r);
}

/* FD_016: Backward fall — total_samples counter includes all fed samples */
void test_FD_016_backward_fall_sample_count(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);             /* 10 samples */
    t = feed_freefall(t, 110, NULL);  /* 11 samples */
    t = feed_impact(t, 3.0f, 0.0f, 1.0f, 0.0f);  /* 2 samples */
    feed_face_up(t, 200, NULL);       /* 20 samples */

    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_GREATER_OR_EQUAL_UINT32(40, stats.total_samples);
}

/* FD_017: Backward fall — free-fall exactly at min duration (80ms) */
void test_FD_017_backward_fall_min_freefall_duration(void)
{
    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 0;
    t = feed_idle(t, 5);
    t = feed_freefall(t, 80, NULL);       /* exactly 80ms */
    t = feed_impact(t, 2.5f, 0.0f, 0.0f, -1.0f);
    t = feed_face_up(t, 200, &r);
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_DETECTED, r);
}

/* FD_018: Backward fall — null sample does not crash */
void test_FD_018_backward_fall_null_sample_safe(void)
{
    FallDetectionResult r = fall_detection_process(NULL);
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_NONE, r);
}

/* FD_019: Backward fall — reset clears confirmed_falls */
void test_FD_019_backward_fall_reset_clears_stats(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 110, NULL);
    t = feed_impact(t, 3.0f, 0.0f, 1.0f, 0.0f);
    feed_face_up(t, 200, NULL);

    fall_detection_reset();
    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_EQUAL_UINT32(0, stats.confirmed_falls);
}

/* FD_020: Init with custom config raises impact threshold, same sequence not detected */
void test_FD_020_custom_config_raises_threshold(void)
{
    FallDetectionConfig cfg = {
        .freefall_threshold_g = 0.40f,
        .impact_threshold_g   = 5.0f,    /* raised threshold */
        .freefall_min_ms      = 80,
        .monitor_window_ms    = 2000,
        .upright_max_deg      = 45.0f,
    };
    fall_detection_init(&cfg);

    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 120, NULL);
    t = feed_impact(t, 3.5f, 0.0f, 0.0f, -1.0f);  /* 3.5g < 5g threshold */
    t = feed_face_down(t, 200, &r);
    /* Impact below custom threshold — should NOT reach MONITORING phase,
     * monitoring window expires → stumble or none, not DETECTED */
    TEST_ASSERT_NOT_EQUAL(FALL_RESULT_DETECTED, r);
}

/* =========================================================================
 * GROUP 3: Side fall (FD_021 – FD_030)
 * ========================================================================= */

/* FD_021: Left side fall detected */
void test_FD_021_left_side_fall_detected(void)
{
    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 100, NULL);
    t = feed_impact(t, 3.2f, 1.0f, 0.0f, 0.0f);   /* lateral impact */
    t = feed_lateral(t, 200, &r);
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_DETECTED, r);
}

/* FD_022: Right side fall detected (ax negative) */
void test_FD_022_right_side_fall_detected(void)
{
    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 100, NULL);
    t = feed_impact(t, 3.2f, -1.0f, 0.0f, 0.0f);  /* ax negative */
    t = feed_lateral(t, 200, &r);
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_DETECTED, r);
}

/* FD_023: Side fall — lateral orientation not upright */
void test_FD_023_side_fall_not_upright(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 100, NULL);
    t = feed_impact(t, 3.2f, 1.0f, 0.0f, 0.0f);
    feed_lateral(t, 50, NULL);
    TEST_ASSERT_FALSE(fall_detection_is_upright());
}

/* FD_024: Side fall with free-fall of exactly 90ms detected */
void test_FD_024_side_fall_90ms_freefall(void)
{
    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 90, NULL);
    t = feed_impact(t, 3.0f, 1.0f, 0.0f, 0.0f);
    t = feed_lateral(t, 200, &r);
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_DETECTED, r);
}

/* FD_025: Side fall — statistics show 1 impact event */
void test_FD_025_side_fall_impact_event(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 100, NULL);
    t = feed_impact(t, 3.2f, 1.0f, 0.0f, 0.0f);
    feed_lateral(t, 200, NULL);

    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_GREATER_OR_EQUAL_UINT32(1, stats.impact_events);
}

/* FD_026: Side fall within monitoring window triggers early detection */
void test_FD_026_side_fall_early_detection(void)
{
    uint32_t t = 0;
    FallDetectionResult r = FALL_RESULT_NONE;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 100, NULL);
    t = feed_impact(t, 3.2f, 1.0f, 0.0f, 0.0f);
    /* Feed only 150ms into monitoring window (< 2000ms) but still non-upright */
    t = feed_lateral(t, 200, &r);
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_DETECTED, r);
}

/* FD_027: Side fall then recovery — second fall still detected */
void test_FD_027_side_fall_recovery_second_fall(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 100, NULL);
    t = feed_impact(t, 3.2f, 1.0f, 0.0f, 0.0f);
    t = feed_lateral(t, 200, NULL);
    t = feed_idle(t, 20);                /* person recovers */

    /* Second fall */
    FallDetectionResult r = FALL_RESULT_NONE;
    t = feed_freefall(t, 100, NULL);
    t = feed_impact(t, 3.2f, -1.0f, 0.0f, 0.0f);
    t = feed_lateral(t, 200, &r);
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_DETECTED, r);
}

/* FD_028: Side fall magnitude calculation for lateral impact vector */
void test_FD_028_side_fall_accel_magnitude(void)
{
    IMUSample s = {3.2f * G, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0};
    float mag = fall_detection_get_accel_magnitude(&s);
    TEST_ASSERT_FLOAT_WITHIN(0.1f, 3.2f * G, mag);
}

/* FD_029: Side fall — get_stats returns correct stumble count (0) */
void test_FD_029_side_fall_no_stumbles(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 100, NULL);
    t = feed_impact(t, 3.2f, 1.0f, 0.0f, 0.0f);
    feed_lateral(t, 200, NULL);

    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_EQUAL_UINT32(0, stats.stumbles);
}

/* FD_030: Side fall — state returns to IDLE post detection */
void test_FD_030_side_fall_fsm_idle_after(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 100, NULL);
    t = feed_impact(t, 3.2f, 1.0f, 0.0f, 0.0f);
    feed_lateral(t, 200, NULL);
    TEST_ASSERT_EQUAL_INT(FALL_STATE_IDLE, fall_detection_get_state());
}

/* =========================================================================
 * GROUP 4: Stumble — NOT a fall (FD_031 – FD_040)
 * ========================================================================= */

/* FD_031: Short acceleration spike without free-fall → FALL_RESULT_NONE */
void test_FD_031_stumble_no_freefall_no_detection(void)
{
    IMUSample s;
    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 500;
    /* Upright spike — large but no free-fall phase */
    s.accel_x    =  0.5f * G;
    s.accel_y    =  0.3f * G;
    s.accel_z    =  2.5f * G;   /* total ~2.7g but az dominant — upright */
    s.gyro_x     =  50.0f;
    s.gyro_y     =  20.0f;
    s.gyro_z     =  10.0f;
    s.timestamp_ms = t;
    r = fall_detection_process(&s);
    TEST_ASSERT_NOT_EQUAL(FALL_RESULT_DETECTED, r);
}

/* FD_032: Stumble — free-fall too short (< 80ms) → not a fall */
void test_FD_032_stumble_freefall_too_short(void)
{
    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 60, &r);           /* 60ms < 80ms minimum */
    TEST_ASSERT_NOT_EQUAL(FALL_RESULT_DETECTED, r);
}

/* FD_033: Stumble — free-fall then recovers upright quickly → stumble counted */
void test_FD_033_stumble_recovers_upright(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 90, NULL);
    t = feed_impact(t, 2.5f, 0.0f, 0.0f, -1.0f);
    t = feed_upright_recovery(t, 100);     /* quick recovery within monitor window */

    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_GREATER_OR_EQUAL_UINT32(1, stats.stumbles);
}

/* FD_034: Stumble — confirmed_falls stays 0 */
void test_FD_034_stumble_no_confirmed_fall(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 90, NULL);
    t = feed_impact(t, 2.5f, 0.0f, 0.0f, -1.0f);
    feed_upright_recovery(t, 100);

    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_EQUAL_UINT32(0, stats.confirmed_falls);
}

/* FD_035: Stumble — no free-fall, just walking vibration → NONE always */
void test_FD_035_stumble_walking_vibration(void)
{
    IMUSample s;
    FallDetectionResult r;
    for (int i = 0; i < 50; i++) {
        float noise = (i % 3 == 0) ? 0.3f : 0.0f;
        s.accel_x    =  noise * G;
        s.accel_y    =  noise * 0.5f * G;
        s.accel_z    =  G + noise * G;   /* still > 0.4g always */
        s.gyro_x     = 10.0f;
        s.gyro_y     = 5.0f;
        s.gyro_z     = 3.0f;
        s.timestamp_ms = (uint32_t)(i * DT_MS);
        r = fall_detection_process(&s);
        TEST_ASSERT_NOT_EQUAL(FALL_RESULT_DETECTED, r);
    }
}

/* FD_036: Stumble — FSM stays in IDLE when free-fall < min_ms */
void test_FD_036_stumble_fsm_stays_idle(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    feed_freefall(t, 60, NULL);             /* short free-fall exits back to IDLE */
    /* After short free-fall, magnitude returns above threshold */
    IMUSample s = {0.0f, 0.0f, G, 0.0f, 0.0f, 0.0f, (uint32_t)(t + 60 + 10)};
    fall_detection_process(&s);
    TEST_ASSERT_EQUAL_INT(FALL_STATE_IDLE, fall_detection_get_state());
}

/* FD_037: Stumble — accel_magnitude returns correct value for partial fall */
void test_FD_037_stumble_magnitude_calculation(void)
{
    IMUSample s = {3.0f, 4.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0};
    float mag = fall_detection_get_accel_magnitude(&s);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 5.0f, mag);  /* 3-4-5 Pythagorean */
}

/* FD_038: Stumble — multiple stumbles counted individually */
void test_FD_038_stumble_multiple_counted(void)
{
    uint32_t t = 0;
    for (int i = 0; i < 3; i++) {
        t = feed_idle(t, 10);
        t = feed_freefall(t, 90, NULL);
        t = feed_impact(t, 2.5f, 0.0f, 0.0f, -1.0f);
        t = feed_upright_recovery(t, 100);
    }
    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_GREATER_OR_EQUAL_UINT32(3, stats.stumbles);
    TEST_ASSERT_EQUAL_UINT32(0, stats.confirmed_falls);
}

/* FD_039: Stumble — impact below threshold → no monitoring phase */
void test_FD_039_stumble_sub_threshold_impact(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 90, NULL);
    /* Impact at exactly free-fall threshold (not an impact spike) */
    IMUSample s = {0.0f, 0.0f, 1.8f * G, 0.0f, 0.0f, 0.0f, t};
    fall_detection_process(&s);
    /* State should leave FREEFALL but not reach MONITORING */
    FallDetectionState st = fall_detection_get_state();
    TEST_ASSERT_NOT_EQUAL(FALL_STATE_MONITORING, st);
}

/* FD_040: Stumble — null config init uses defaults, stumble logic unchanged */
void test_FD_040_stumble_null_config_defaults(void)
{
    fall_detection_init(NULL);
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_freefall(t, 90, NULL);
    t = feed_impact(t, 2.5f, 0.0f, 0.0f, -1.0f);
    feed_upright_recovery(t, 100);

    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_EQUAL_UINT32(0, stats.confirmed_falls);
    TEST_ASSERT_GREATER_OR_EQUAL_UINT32(1, stats.stumbles);
}

/* =========================================================================
 * GROUP 5: Sitting down — controlled motion (FD_041 – FD_050)
 * ========================================================================= */

/* FD_041: Sitting down produces no fall detection */
void test_FD_041_sitting_down_no_detection(void)
{
    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_sit_down(t, 2000, &r);     /* slow 2-second sit */
    TEST_ASSERT_NOT_EQUAL(FALL_RESULT_DETECTED, r);
}

/* FD_042: Sitting down — FSM stays in IDLE throughout */
void test_FD_042_sitting_down_fsm_idle(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    feed_sit_down(t, 2000, NULL);
    TEST_ASSERT_EQUAL_INT(FALL_STATE_IDLE, fall_detection_get_state());
}

/* FD_043: Sitting down — confirmed_falls remains 0 */
void test_FD_043_sitting_down_no_confirmed_fall(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    feed_sit_down(t, 2000, NULL);
    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_EQUAL_UINT32(0, stats.confirmed_falls);
}

/* FD_044: Sitting down — freefall_events remains 0 */
void test_FD_044_sitting_down_no_freefall_event(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    feed_sit_down(t, 2000, NULL);
    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_EQUAL_UINT32(0, stats.freefall_events);
}

/* FD_045: Sitting down — accel magnitude stays close to 1g throughout */
void test_FD_045_sitting_down_magnitude_near_1g(void)
{
    for (int i = 0; i < 200; i++) {
        float progress = (float)i / 200.0f;
        float tilt_rad = progress * 30.0f * (float)M_PI / 180.0f;
        IMUSample s = {
            sinf(tilt_rad) * G * 0.5f,
            0.0f,
            cosf(tilt_rad) * G,
            5.0f, 0.0f, 0.0f,
            (uint32_t)(i * DT_MS)
        };
        float mag = fall_detection_get_accel_magnitude(&s);
        TEST_ASSERT_GREATER_THAN_FLOAT(FALL_FREEFALL_THRESH_G * G, mag);
    }
}

/* FD_046: Sitting down rapidly (0.5s) still no detection */
void test_FD_046_sitting_down_rapid_no_detection(void)
{
    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_sit_down(t, 500, &r);
    TEST_ASSERT_NOT_EQUAL(FALL_RESULT_DETECTED, r);
}

/* FD_047: Sitting then standing — no fall, is_upright correct after standing */
void test_FD_047_sit_stand_upright_restored(void)
{
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_sit_down(t, 2000, NULL);
    t = feed_idle(t, 20);           /* standing up (back to upright) */
    TEST_ASSERT_TRUE(fall_detection_is_upright());
}

/* FD_048: Sitting down — sample counter increments correctly */
void test_FD_048_sitting_down_sample_count(void)
{
    fall_detection_reset();
    uint32_t t = 0;
    t = feed_idle(t, 10);           /* 10 samples */
    feed_sit_down(t, 1000, NULL);   /* 100 samples at 100Hz */
    FallDetectionStats stats;
    fall_detection_get_stats(&stats);
    TEST_ASSERT_GREATER_OR_EQUAL_UINT32(110, stats.total_samples);
}

/* FD_049: Fall immediately after sitting detected correctly */
void test_FD_049_fall_after_sitting_detected(void)
{
    FallDetectionResult r = FALL_RESULT_NONE;
    uint32_t t = 0;
    t = feed_idle(t, 10);
    t = feed_sit_down(t, 2000, NULL);
    t = feed_idle(t, 10);           /* briefly upright */
    t = feed_freefall(t, 100, NULL);
    t = feed_impact(t, 3.0f, 0.0f, 0.0f, -1.0f);
    t = feed_face_down(t, 200, &r);
    TEST_ASSERT_EQUAL_INT(FALL_RESULT_DETECTED, r);
}

/* FD_050: get_accel_magnitude with null input returns 0 safely */
void test_FD_050_get_magnitude_null_safe(void)
{
    float mag = fall_detection_get_accel_magnitude(NULL);
    TEST_ASSERT_EQUAL_FLOAT(0.0f, mag);
}

/* =========================================================================
 * Test runner
 * ========================================================================= */

int run_fall_detection_tests(void)
{
    UNITY_BEGIN();

    /* Group 1: Forward fall */
    RUN_TEST(test_FD_001_forward_fall_detected);
    RUN_TEST(test_FD_002_forward_fall_stats_increment);
    RUN_TEST(test_FD_003_freefall_phase_returns_possible);
    RUN_TEST(test_FD_004_fsm_enters_freefall_state);
    RUN_TEST(test_FD_005_not_upright_after_forward_fall);
    RUN_TEST(test_FD_006_forward_fall_moderate_impact);
    RUN_TEST(test_FD_007_freefall_event_counted);
    RUN_TEST(test_FD_008_two_sequential_forward_falls);
    RUN_TEST(test_FD_009_freefall_magnitude_below_threshold);
    RUN_TEST(test_FD_010_impact_magnitude_above_threshold);

    /* Group 2: Backward fall */
    RUN_TEST(test_FD_011_backward_fall_detected);
    RUN_TEST(test_FD_012_backward_fall_not_upright);
    RUN_TEST(test_FD_013_backward_fall_counter_increments);
    RUN_TEST(test_FD_014_backward_fall_fsm_returns_idle);
    RUN_TEST(test_FD_015_backward_fall_exact_impact_threshold);
    RUN_TEST(test_FD_016_backward_fall_sample_count);
    RUN_TEST(test_FD_017_backward_fall_min_freefall_duration);
    RUN_TEST(test_FD_018_backward_fall_null_sample_safe);
    RUN_TEST(test_FD_019_backward_fall_reset_clears_stats);
    RUN_TEST(test_FD_020_custom_config_raises_threshold);

    /* Group 3: Side fall */
    RUN_TEST(test_FD_021_left_side_fall_detected);
    RUN_TEST(test_FD_022_right_side_fall_detected);
    RUN_TEST(test_FD_023_side_fall_not_upright);
    RUN_TEST(test_FD_024_side_fall_90ms_freefall);
    RUN_TEST(test_FD_025_side_fall_impact_event);
    RUN_TEST(test_FD_026_side_fall_early_detection);
    RUN_TEST(test_FD_027_side_fall_recovery_second_fall);
    RUN_TEST(test_FD_028_side_fall_accel_magnitude);
    RUN_TEST(test_FD_029_side_fall_no_stumbles);
    RUN_TEST(test_FD_030_side_fall_fsm_idle_after);

    /* Group 4: Stumble */
    RUN_TEST(test_FD_031_stumble_no_freefall_no_detection);
    RUN_TEST(test_FD_032_stumble_freefall_too_short);
    RUN_TEST(test_FD_033_stumble_recovers_upright);
    RUN_TEST(test_FD_034_stumble_no_confirmed_fall);
    RUN_TEST(test_FD_035_stumble_walking_vibration);
    RUN_TEST(test_FD_036_stumble_fsm_stays_idle);
    RUN_TEST(test_FD_037_stumble_magnitude_calculation);
    RUN_TEST(test_FD_038_stumble_multiple_counted);
    RUN_TEST(test_FD_039_stumble_sub_threshold_impact);
    RUN_TEST(test_FD_040_stumble_null_config_defaults);

    /* Group 5: Sitting down */
    RUN_TEST(test_FD_041_sitting_down_no_detection);
    RUN_TEST(test_FD_042_sitting_down_fsm_idle);
    RUN_TEST(test_FD_043_sitting_down_no_confirmed_fall);
    RUN_TEST(test_FD_044_sitting_down_no_freefall_event);
    RUN_TEST(test_FD_045_sitting_down_magnitude_near_1g);
    RUN_TEST(test_FD_046_sitting_down_rapid_no_detection);
    RUN_TEST(test_FD_047_sit_stand_upright_restored);
    RUN_TEST(test_FD_048_sitting_down_sample_count);
    RUN_TEST(test_FD_049_fall_after_sitting_detected);
    RUN_TEST(test_FD_050_get_magnitude_null_safe);

    return UNITY_END();
}

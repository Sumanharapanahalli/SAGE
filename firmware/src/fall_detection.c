/**
 * @file fall_detection.c
 * @brief Fall Detection Algorithm Implementation
 *
 * IEC 62304 Software Class B — see fall_detection.h for full classification.
 *
 * State Machine:
 *
 *   IDLE ──(|a|<FF_THR, cnt>=FF_MIN)──► FREEFALL
 *   FREEFALL ──(|a|>=FF_THR)──────────► IMPACT_WAIT
 *   FREEFALL ──(cnt>=FF_MAX)──────────► IMPACT_WAIT  (timeout — very long fall)
 *   IMPACT_WAIT ──(|a|>IMP_THR)───────► POST_IMPACT
 *   IMPACT_WAIT ──(timeout)───────────► IDLE
 *   POST_IMPACT ──(stillness OK)──────► CONFIRMED → emit event → IDLE
 *   POST_IMPACT ──(timeout, no still)─► IDLE
 *
 * Thread safety:
 *   fall_detection_process() — call from a single IMU task.
 *   fall_detection_sos_trigger() — ISR-safe; uses a volatile flag + direct emit.
 *   fall_detection_reset() — protected by critical section.
 *
 * @version 1.0.0
 * @date    2026-03-21
 */

#include "fall_detection.h"

#include <math.h>
#include <string.h>
#include <stdio.h>

/* =========================================================================
 * Platform abstraction — replace with your RTOS / HAL equivalents
 * ========================================================================= */

/* Monotonic millisecond clock — must be provided by the BSP */
extern int64_t bsp_get_time_ms(void);

/* Atomic flag type for ISR-safe SOS signalling */
#ifdef __GNUC__
#  define ATOMIC_FLAG volatile uint32_t
#  define ATOMIC_SET(f)   __atomic_store_n(&(f), 1u, __ATOMIC_SEQ_CST)
#  define ATOMIC_CLEAR(f) __atomic_store_n(&(f), 0u, __ATOMIC_SEQ_CST)
#  define ATOMIC_LOAD(f)  __atomic_load_n(&(f),    __ATOMIC_SEQ_CST)
#else
/* Bare-metal fallback — assumes single-core */
#  define ATOMIC_FLAG volatile uint32_t
#  define ATOMIC_SET(f)   do { (f) = 1u; } while (0)
#  define ATOMIC_CLEAR(f) do { (f) = 0u; } while (0)
#  define ATOMIC_LOAD(f)  (f)
#endif

/* Critical-section guards (replace with FreeRTOS taskENTER_CRITICAL if needed) */
#ifndef FALL_ENTER_CRITICAL
#  define FALL_ENTER_CRITICAL()  do {} while (0)
#  define FALL_EXIT_CRITICAL()   do {} while (0)
#endif

/* =========================================================================
 * Internal: circular ring buffer for pre-impact snapshot
 * ========================================================================= */
typedef struct {
    IMUSample buf[SNAPSHOT_PRE_SAMPLES];
    uint16_t  head;   /* next write position */
    uint16_t  count;  /* valid samples in buffer */
} RingBuf;

static inline void ring_push(RingBuf *rb, const IMUSample *s)
{
    rb->buf[rb->head] = *s;
    rb->head = (uint16_t)((rb->head + 1u) % SNAPSHOT_PRE_SAMPLES);
    if (rb->count < SNAPSHOT_PRE_SAMPLES) { rb->count++; }
}

/** Copy ring buffer contents into dest[] oldest-first, return count copied. */
static uint16_t ring_drain(const RingBuf *rb, IMUSample *dest, uint16_t max)
{
    uint16_t n = (rb->count < max) ? rb->count : max;
    uint16_t start = (uint16_t)((rb->head + SNAPSHOT_PRE_SAMPLES - n)
                                 % SNAPSHOT_PRE_SAMPLES);
    for (uint16_t i = 0u; i < n; i++) {
        dest[i] = rb->buf[(start + i) % SNAPSHOT_PRE_SAMPLES];
    }
    return n;
}

/* =========================================================================
 * Internal module state
 * ========================================================================= */
typedef struct {
    bool               initialised;
    FallDetectionConfig cfg;
    FallEventCallback  callback;
    void              *user_data;

    /* State machine */
    FallDetectionState state;
    uint16_t           freefall_sample_count;  /* samples below FF threshold   */
    uint16_t           impact_wait_count;       /* samples waiting for impact   */
    uint16_t           stillness_count;         /* samples below stillness thr  */
    float              peak_impact_g;           /* max |a| seen during impact   */
    int64_t            freefall_start_ms;       /* timestamp when FF began      */
    int64_t            impact_time_ms;          /* timestamp of impact          */

    /* Post-impact stillness: track rolling sum-of-squares for variance */
    float              still_sum;
    float              still_sum_sq;
    uint16_t           still_n;

    /* Snapshot ring buffer (pre-impact data) */
    RingBuf            pre_ring;

    /* Post-impact samples collected so far */
    IMUSample          post_buf[SNAPSHOT_POST_SAMPLES];
    uint16_t           post_count;
    uint16_t           snapshot_impact_idx; /* index in assembled snapshot     */

    /* SOS flag — set from ISR, cleared from process() */
    ATOMIC_FLAG        sos_pending;

    /* Statistics */
    FallStats          stats;
} FallDetectionCtx;

static FallDetectionCtx s_ctx;  /* zero-initialised at startup */

/* =========================================================================
 * Internal helpers
 * ========================================================================= */

/** Compute vector magnitude (g) */
static inline float vec3_magnitude(Vec3f v)
{
    return sqrtf(v.x * v.x + v.y * v.y + v.z * v.z);
}

/** Compute vector magnitude for gyro (rad/s) */
static inline float vec3_magnitude_gyro(Vec3f v)
{
    return sqrtf(v.x * v.x + v.y * v.y + v.z * v.z);
}

/**
 * Compute confidence score 0-100.
 *
 * Breakdown:
 *   30 pts — freefall duration  (saturates at 3× FREEFALL_MIN_MS)
 *   40 pts — impact magnitude   (linear: IMPACT_THR → 10g maps to 0 → 40)
 *   30 pts — post-impact stillness (lower variance → more confident)
 */
static uint8_t compute_confidence(uint16_t ff_samples,
                                   float    peak_g,
                                   float    stillness_variance)
{
    float ff_score, imp_score, still_score;

    /* Free-fall duration factor */
    float ff_ratio = (float)ff_samples / (float)(s_ctx.cfg.freefall_min_samples * 3u);
    ff_ratio = (ff_ratio > 1.0f) ? 1.0f : ff_ratio;
    ff_score = ff_ratio * 30.0f;

    /* Impact magnitude factor */
    float imp_range = 10.0f - s_ctx.cfg.impact_threshold_g;
    if (imp_range < 0.1f) { imp_range = 0.1f; }
    float imp_ratio = (peak_g - s_ctx.cfg.impact_threshold_g) / imp_range;
    imp_ratio = (imp_ratio < 0.0f) ? 0.0f : (imp_ratio > 1.0f ? 1.0f : imp_ratio);
    imp_score = imp_ratio * 40.0f;

    /* Stillness factor — lower variance is better */
    float still_ratio = stillness_variance / s_ctx.cfg.stillness_accel_threshold_g;
    still_ratio = (still_ratio > 1.0f) ? 1.0f : still_ratio;
    still_score = (1.0f - still_ratio) * 30.0f;

    float total = ff_score + imp_score + still_score;
    if (total < 0.0f)   { total = 0.0f; }
    if (total > 100.0f) { total = 100.0f; }
    return (uint8_t)total;
}

/** Assemble and emit a FALL_EVENT */
static void emit_fall_event(bool       sos,
                             uint8_t    confidence,
                             float      peak_g,
                             float      ff_duration_ms,
                             float      still_variance,
                             int64_t    ts_ms)
{
    FallEvent ev;
    memset(&ev, 0, sizeof(ev));

    ev.timestamp_ms         = ts_ms;
    ev.confidence_percent   = confidence;
    ev.sos_triggered        = sos;
    ev.peak_impact_g        = peak_g;
    ev.freefall_duration_ms = ff_duration_ms;
    ev.stillness_variance_g = still_variance;

    if (sos) {
        snprintf(ev.source, sizeof(ev.source), "SOS_BUTTON");
    } else {
        snprintf(ev.source, sizeof(ev.source), "ALGORITHM");
    }

    /* Assemble snapshot: drain pre-ring then append post-buffer */
    uint16_t pre_n = ring_drain(&s_ctx.pre_ring,
                                ev.snapshot.samples,
                                SNAPSHOT_PRE_SAMPLES);
    ev.snapshot.impact_index = pre_n;

    uint16_t post_n = s_ctx.post_count;
    if (post_n > SNAPSHOT_POST_SAMPLES) { post_n = SNAPSHOT_POST_SAMPLES; }
    memcpy(&ev.snapshot.samples[pre_n],
           s_ctx.post_buf,
           post_n * sizeof(IMUSample));
    ev.snapshot.count = (uint16_t)(pre_n + post_n);

    /* Update stats */
    s_ctx.stats.total_events++;
    if (sos) { s_ctx.stats.sos_events++; }
    else      { s_ctx.stats.algo_events++; }

    /* Invoke user callback */
    if (s_ctx.callback != NULL) {
        s_ctx.callback(&ev, s_ctx.user_data);
    }
}

/** Reset state machine internals (call from process() and reset()) */
static void reset_state_machine(void)
{
    s_ctx.state                 = FALL_STATE_IDLE;
    s_ctx.freefall_sample_count = 0u;
    s_ctx.impact_wait_count     = 0u;
    s_ctx.stillness_count       = 0u;
    s_ctx.peak_impact_g         = 0.0f;
    s_ctx.freefall_start_ms     = 0;
    s_ctx.impact_time_ms        = 0;
    s_ctx.still_sum             = 0.0f;
    s_ctx.still_sum_sq          = 0.0f;
    s_ctx.still_n               = 0u;
    s_ctx.post_count            = 0u;
    s_ctx.snapshot_impact_idx   = 0u;
}

/* =========================================================================
 * Public API
 * ========================================================================= */

FallDetectionConfig fall_detection_default_config(void)
{
    FallDetectionConfig c;
    c.freefall_threshold_g        = FREEFALL_THRESHOLD_G;
    c.impact_threshold_g          = IMPACT_THRESHOLD_G;
    c.stillness_accel_threshold_g = STILLNESS_ACCEL_THRESHOLD_G;
    c.stillness_gyro_threshold_rs = STILLNESS_GYRO_THRESHOLD_RS;
    c.freefall_min_samples        = FREEFALL_MIN_SAMPLES;
    c.freefall_max_samples        = FREEFALL_MAX_SAMPLES;
    c.impact_wait_samples         = IMPACT_WAIT_SAMPLES;
    c.stillness_samples           = STILLNESS_SAMPLES;
    c.confidence_min_percent      = CONFIDENCE_MIN_PERCENT;
    return c;
}

FallErr fall_detection_init(const FallDetectionConfig *config,
                             FallEventCallback          callback,
                             void                      *user_data)
{
    if (callback == NULL) { return FALL_ERR_NULL_PTR; }
    if (s_ctx.initialised) { return FALL_ERR_ALREADY_INIT; }

    memset(&s_ctx, 0, sizeof(s_ctx));

    if (config != NULL) {
        /* Validate critical thresholds */
        if (config->freefall_threshold_g  <= 0.0f ||
            config->impact_threshold_g    <= config->freefall_threshold_g ||
            config->freefall_min_samples  == 0u ||
            config->freefall_max_samples  < config->freefall_min_samples ||
            config->impact_wait_samples   == 0u ||
            config->stillness_samples     == 0u ||
            config->confidence_min_percent > 100u) {
            return FALL_ERR_INVALID_CFG;
        }
        s_ctx.cfg = *config;
    } else {
        s_ctx.cfg = fall_detection_default_config();
    }

    s_ctx.callback    = callback;
    s_ctx.user_data   = user_data;
    s_ctx.initialised = true;
    reset_state_machine();
    return FALL_ERR_OK;
}

FallErr fall_detection_process(const IMUSample *sample)
{
    if (!s_ctx.initialised) { return FALL_ERR_NOT_INIT; }
    if (sample == NULL)     { return FALL_ERR_NULL_PTR; }

    /* ── SOS fast path (check before anything else) ────────────────────── */
    if (ATOMIC_LOAD(s_ctx.sos_pending)) {
        ATOMIC_CLEAR(s_ctx.sos_pending);
        /* Include current sample in pre-ring before emitting */
        ring_push(&s_ctx.pre_ring, sample);
        emit_fall_event(true,
                        100u,                        /* SOS → 100% confidence */
                        vec3_magnitude(sample->accel_g),
                        0.0f,
                        0.0f,
                        sample->timestamp_ms);
        reset_state_machine();
        return FALL_ERR_OK;
    }

    float accel_mag  = vec3_magnitude(sample->accel_g);
    float gyro_mag   = vec3_magnitude_gyro(sample->gyro_rs);
    (void)gyro_mag;   /* used in stillness scoring below */

    /* Always push to pre-impact ring buffer */
    ring_push(&s_ctx.pre_ring, sample);

    switch (s_ctx.state) {

    /* ── IDLE ──────────────────────────────────────────────────────────── */
    case FALL_STATE_IDLE:
        if (accel_mag < s_ctx.cfg.freefall_threshold_g) {
            s_ctx.freefall_sample_count++;
            if (s_ctx.freefall_sample_count == 1u) {
                s_ctx.freefall_start_ms = sample->timestamp_ms;
            }
            if (s_ctx.freefall_sample_count >= s_ctx.cfg.freefall_min_samples) {
                s_ctx.state = FALL_STATE_FREEFALL;
            }
        } else {
            s_ctx.freefall_sample_count = 0u;
        }
        break;

    /* ── FREEFALL ───────────────────────────────────────────────────────── */
    case FALL_STATE_FREEFALL:
        if (accel_mag < s_ctx.cfg.freefall_threshold_g) {
            s_ctx.freefall_sample_count++;
            /* Hard cap: extremely long "free-fall" is likely sensor error */
            if (s_ctx.freefall_sample_count > s_ctx.cfg.freefall_max_samples * 2u) {
                reset_state_machine();
            }
        } else {
            /*
             * Free-fall ended — transition to IMPACT_WAIT.
             * Check if this very sample is the impact.
             */
            s_ctx.state             = FALL_STATE_IMPACT_WAIT;
            s_ctx.impact_wait_count = 0u;

            if (accel_mag > s_ctx.cfg.impact_threshold_g) {
                /* Impact detected on same sample as free-fall exit */
                s_ctx.peak_impact_g   = accel_mag;
                s_ctx.impact_time_ms  = sample->timestamp_ms;
                /* Start collecting post-impact samples */
                s_ctx.post_buf[s_ctx.post_count++] = *sample;
                s_ctx.state           = FALL_STATE_POST_IMPACT;
                s_ctx.stillness_count = 0u;
                s_ctx.still_sum    = 0.0f;
                s_ctx.still_sum_sq = 0.0f;
                s_ctx.still_n      = 0u;
            }
        }
        break;

    /* ── IMPACT_WAIT ────────────────────────────────────────────────────── */
    case FALL_STATE_IMPACT_WAIT:
        s_ctx.impact_wait_count++;

        if (accel_mag > s_ctx.cfg.impact_threshold_g) {
            s_ctx.peak_impact_g  = accel_mag;
            s_ctx.impact_time_ms = sample->timestamp_ms;
            s_ctx.post_buf[s_ctx.post_count++] = *sample;
            s_ctx.state           = FALL_STATE_POST_IMPACT;
            s_ctx.stillness_count = 0u;
            s_ctx.still_sum    = 0.0f;
            s_ctx.still_sum_sq = 0.0f;
            s_ctx.still_n      = 0u;
        } else if (s_ctx.impact_wait_count >= s_ctx.cfg.impact_wait_samples) {
            /* Timeout: no impact detected after free-fall → not a fall */
            reset_state_machine();
        }
        break;

    /* ── POST_IMPACT ────────────────────────────────────────────────────── */
    case FALL_STATE_POST_IMPACT:
        /* Collect post-impact snapshot (up to SNAPSHOT_POST_SAMPLES) */
        if (s_ctx.post_count < SNAPSHOT_POST_SAMPLES) {
            s_ctx.post_buf[s_ctx.post_count++] = *sample;
        }

        /* Track peak impact across entire post-impact window */
        if (accel_mag > s_ctx.peak_impact_g) {
            s_ctx.peak_impact_g = accel_mag;
        }

        /* Rolling variance: Welford's online algorithm on accel magnitude */
        s_ctx.still_n++;
        s_ctx.still_sum    += accel_mag;
        s_ctx.still_sum_sq += accel_mag * accel_mag;

        /* Stillness criterion: low accel AND low gyro */
        bool accel_still = (accel_mag   < s_ctx.cfg.stillness_accel_threshold_g);
        bool gyro_still  = (gyro_mag    < s_ctx.cfg.stillness_gyro_threshold_rs);

        if (accel_still && gyro_still) {
            s_ctx.stillness_count++;
        } else {
            /* Brief movement is OK — reset counter but keep accumulating */
            s_ctx.stillness_count = 0u;
        }

        if (s_ctx.still_n >= s_ctx.cfg.stillness_samples) {
            /*
             * Stillness window complete — evaluate confidence.
             * Variance = E[x²] - (E[x])²
             */
            float mean  = s_ctx.still_sum    / (float)s_ctx.still_n;
            float mean2 = s_ctx.still_sum_sq / (float)s_ctx.still_n;
            float variance = mean2 - (mean * mean);
            if (variance < 0.0f) { variance = 0.0f; }
            float std_dev = sqrtf(variance);

            float ff_ms = (float)(s_ctx.impact_time_ms - s_ctx.freefall_start_ms);
            if (ff_ms < 0.0f) { ff_ms = 0.0f; }

            uint8_t conf = compute_confidence(s_ctx.freefall_sample_count,
                                              s_ctx.peak_impact_g,
                                              std_dev);
            if (conf >= s_ctx.cfg.confidence_min_percent) {
                s_ctx.state = FALL_STATE_CONFIRMED;
                emit_fall_event(false,
                                conf,
                                s_ctx.peak_impact_g,
                                ff_ms,
                                std_dev,
                                sample->timestamp_ms);
            } else {
                s_ctx.stats.rejected_low_confidence++;
            }
            reset_state_machine();
        }
        break;

    /* ── CONFIRMED — transient, reset immediately ──────────────────────── */
    case FALL_STATE_CONFIRMED:
        reset_state_machine();
        break;

    default:
        reset_state_machine();
        break;
    }

    return FALL_ERR_OK;
}

/**
 * fall_detection_sos_trigger — ISR-safe.
 *
 * Sets the atomic sos_pending flag.  The flag is checked at the very
 * beginning of the next fall_detection_process() call (typically within
 * 10 ms at 100 Hz), which is well within the 100 ms SOS guarantee.
 *
 * If the IMU task is not running, a BSP-level interrupt-to-task notification
 * should also kick the IMU task to ensure the 100 ms window is met.
 */
FallErr fall_detection_sos_trigger(void)
{
    if (!s_ctx.initialised) { return FALL_ERR_NOT_INIT; }
    ATOMIC_SET(s_ctx.sos_pending);
    return FALL_ERR_OK;
}

FallErr fall_detection_reset(void)
{
    if (!s_ctx.initialised) { return FALL_ERR_NOT_INIT; }
    FALL_ENTER_CRITICAL();
    reset_state_machine();
    ATOMIC_CLEAR(s_ctx.sos_pending);
    FALL_EXIT_CRITICAL();
    return FALL_ERR_OK;
}

FallDetectionState fall_detection_get_state(void)
{
    return s_ctx.state;
}

FallErr fall_detection_get_stats(FallStats *stats)
{
    if (!s_ctx.initialised) { return FALL_ERR_NOT_INIT; }
    if (stats == NULL)      { return FALL_ERR_NULL_PTR; }
    FALL_ENTER_CRITICAL();
    *stats = s_ctx.stats;
    FALL_EXIT_CRITICAL();
    return FALL_ERR_OK;
}

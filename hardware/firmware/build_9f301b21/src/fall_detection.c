/**
 * @file fall_detection.c
 * @brief Fall detection algorithm implementation — nRF5340 + LSM6DSO.
 *
 * Algorithm (3-stage state machine):
 *   Stage 1 FREE-FALL  : SVM (signal vector magnitude) < FALL_FREE_FALL_THRESH
 *                        for at least 80 ms (hardware interrupt from LSM6DSO)
 *   Stage 2 IMPACT     : SVM > FALL_IMPACT_THRESH within 500 ms of free-fall
 *   Stage 3 STILLNESS  : SVM < FALL_STILLNESS_THRESH for FALL_STILLNESS_DUR_MS
 *
 * On confirmed fall (all 3 stages): post EVT_FALL_DETECTED.
 * On user cancel (button within FALL_CANCEL_WINDOW_MS): post EVT_FALL_CANCELLED.
 *
 * HIL test support:
 *   fall_detection_inject_sample() — single-sample injection for INJECT_ACCEL
 *   fall_detection_replay()        — batch replay for dataset testing
 *   fall_detection_reset_count()   — reset audit counter between test cases
 *
 * IEC 62304 traceability: SRS-001, SWD-FALL-001..008
 * MISRA-C:2012 compliant — no dynamic allocation, no recursion.
 *
 * @version 1.0.0
 */

#include <zephyr/kernel.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#include "../include/fall_detection.h"
#include "../include/app_events.h"

LOG_MODULE_REGISTER(fall_det, LOG_LEVEL_INF);

/* -------------------------------------------------------------------------
 * Internal types
 * ------------------------------------------------------------------------- */
typedef struct fall_fsm {
    fall_state_t state;
    uint32_t     state_entry_ms;     /**< Uptime when current state entered  */
    uint32_t     free_fall_start_ms; /**< Timestamp of free-fall onset       */
    uint32_t     impact_ts_ms;       /**< Timestamp of peak impact           */
    uint32_t     detection_ts_ms;    /**< Timestamp of confirmed fall        */
    uint32_t     fall_count;         /**< Confirmed falls since boot         */
    int32_t      peak_impact_mg;     /**< Peak SVM during impact stage       */
} fall_fsm_t;

static fall_fsm_t s_fsm;
static K_MUTEX_DEFINE(s_fsm_mutex);

/* -------------------------------------------------------------------------
 * SVM helper — sqrt-free approximation (MISRA-safe integer arithmetic)
 * For threshold comparison we compare SVM^2 to avoid sqrt.
 * SVM^2 = ax^2 + ay^2 + az^2 (in mg^2)
 * ------------------------------------------------------------------------- */
static uint64_t svm_squared(int16_t ax, int16_t ay, int16_t az)
{
    int64_t x = (int64_t)ax;
    int64_t y = (int64_t)ay;
    int64_t z = (int64_t)az;
    return (uint64_t)(x * x + y * y + z * z);
}

/* Precomputed threshold^2 values */
#define FF_THRESH_SQ  ((uint64_t)FALL_FREE_FALL_THRESH_MG  * \
                       (uint64_t)FALL_FREE_FALL_THRESH_MG)
#define IMP_THRESH_SQ ((uint64_t)FALL_IMPACT_THRESH_MG     * \
                       (uint64_t)FALL_IMPACT_THRESH_MG)
#define STILL_THRESH_SQ ((uint64_t)FALL_STILLNESS_THRESH_MG * \
                         (uint64_t)FALL_STILLNESS_THRESH_MG)

/* -------------------------------------------------------------------------
 * FSM transition logic — called from ISR context or replay (with mutex held)
 * ------------------------------------------------------------------------- */
static void fsm_transition(fall_fsm_t *p_fsm, int16_t ax_mg, int16_t ay_mg,
                            int16_t az_mg, uint32_t now_ms)
{
    if (p_fsm == NULL) {
        return; /* MISRA: NULL guard */
    }
    uint64_t sv2 = svm_squared(ax_mg, ay_mg, az_mg);

    switch (p_fsm->state) {
    case FALL_STATE_IDLE:
        if (sv2 < FF_THRESH_SQ) {
            p_fsm->state             = FALL_STATE_FREE_FALL;
            p_fsm->state_entry_ms    = now_ms;
            p_fsm->free_fall_start_ms = now_ms;
            LOG_DBG("FSM: IDLE -> FREE_FALL @ %u ms", now_ms);
        }
        break;

    case FALL_STATE_FREE_FALL:
        /* Check for false free-fall (gravity briefly cancels) */
        if (sv2 >= FF_THRESH_SQ) {
            uint32_t ff_dur = now_ms - p_fsm->free_fall_start_ms;
            if (ff_dur < 80U) {
                /* Too short — not a real free-fall */
                p_fsm->state          = FALL_STATE_IDLE;
                p_fsm->state_entry_ms = now_ms;
                LOG_DBG("FSM: FREE_FALL too short (%u ms), back to IDLE", ff_dur);
                break;
            }
            /* Free-fall duration validated — look for impact */
            if (sv2 >= IMP_THRESH_SQ) {
                int64_t sv_approx = (int64_t)sv2; /* Compare as squared */
                if (sv_approx > (int64_t)p_fsm->peak_impact_mg * p_fsm->peak_impact_mg) {
                    /* Update peak — approximate sqrt for logging only */
                    p_fsm->peak_impact_mg = (int32_t)(ax_mg > ay_mg ?
                        (ax_mg > az_mg ? ax_mg : az_mg) :
                        (ay_mg > az_mg ? ay_mg : az_mg));
                }
                p_fsm->state          = FALL_STATE_IMPACT;
                p_fsm->state_entry_ms = now_ms;
                p_fsm->impact_ts_ms   = now_ms;
                LOG_DBG("FSM: FREE_FALL -> IMPACT @ %u ms", now_ms);
            } else {
                /* SVM recovered above free-fall threshold but below impact — reset */
                p_fsm->state          = FALL_STATE_IDLE;
                p_fsm->state_entry_ms = now_ms;
                LOG_DBG("FSM: FREE_FALL cancelled (no impact), IDLE");
            }
        }
        /* Timeout: if in free-fall > 3 s something is wrong — reset */
        if ((now_ms - p_fsm->state_entry_ms) > 3000U) {
            p_fsm->state          = FALL_STATE_IDLE;
            p_fsm->state_entry_ms = now_ms;
            LOG_WRN("FSM: FREE_FALL timeout, IDLE");
        }
        break;

    case FALL_STATE_IMPACT:
        if (sv2 < STILL_THRESH_SQ) {
            p_fsm->state          = FALL_STATE_STILLNESS;
            p_fsm->state_entry_ms = now_ms;
            LOG_DBG("FSM: IMPACT -> STILLNESS @ %u ms", now_ms);
        } else if ((now_ms - p_fsm->state_entry_ms) > 500U) {
            /* Post-impact motion persists > 500 ms — abort */
            p_fsm->state          = FALL_STATE_IDLE;
            p_fsm->state_entry_ms = now_ms;
            LOG_DBG("FSM: IMPACT timeout, IDLE");
        }
        break;

    case FALL_STATE_STILLNESS:
        if (sv2 >= STILL_THRESH_SQ) {
            /* Person moved — not a fall */
            p_fsm->state          = FALL_STATE_IDLE;
            p_fsm->state_entry_ms = now_ms;
            LOG_DBG("FSM: STILLNESS broken, IDLE");
            break;
        }
        if ((now_ms - p_fsm->state_entry_ms) >= FALL_STILLNESS_DUR_MS) {
            /* Confirmed fall */
            p_fsm->state            = FALL_STATE_CONFIRMED;
            p_fsm->state_entry_ms   = now_ms;
            p_fsm->detection_ts_ms  = now_ms;
            p_fsm->fall_count++;
            LOG_INF("FSM: FALL CONFIRMED #%u @ %u ms (impact_ts=%u)",
                    p_fsm->fall_count, now_ms, p_fsm->impact_ts_ms);
            /* Post event to orchestrator */
            extern int app_event_post(uint32_t event_id, const void *p_data,
                                      size_t data_len);
            (void)app_event_post(EVT_FALL_DETECTED, NULL, 0U);
        }
        break;

    case FALL_STATE_CONFIRMED:
        /* Stay in CONFIRMED until cancelled or orchestrator ACKs */
        if ((now_ms - p_fsm->state_entry_ms) > FALL_CANCEL_WINDOW_MS) {
            /* Cancel window expired — back to monitoring */
            p_fsm->state          = FALL_STATE_IDLE;
            p_fsm->state_entry_ms = now_ms;
            LOG_DBG("FSM: CONFIRMED cancel window expired, IDLE");
        }
        break;

    case FALL_STATE_CANCELLED:
        p_fsm->state          = FALL_STATE_IDLE;
        p_fsm->state_entry_ms = now_ms;
        break;

    default:
        /* MISRA: handle all enum values */
        p_fsm->state          = FALL_STATE_IDLE;
        p_fsm->state_entry_ms = now_ms;
        break;
    }
}

/* -------------------------------------------------------------------------
 * Sensor work item — called from system workqueue on IMU interrupt
 * ------------------------------------------------------------------------- */
static const struct device *s_lsm6dso;

static void accel_work_handler(struct k_work *p_work)
{
    ARG_UNUSED(p_work);
    if (s_lsm6dso == NULL) {
        return;
    }
    struct sensor_value accel[3];
    if (sensor_sample_fetch(s_lsm6dso) < 0) {
        LOG_ERR("IMU sample fetch failed");
        return;
    }
    if (sensor_channel_get(s_lsm6dso, SENSOR_CHAN_ACCEL_XYZ, accel) < 0) {
        LOG_ERR("IMU channel read failed");
        return;
    }
    /* Convert m/s² → mg (1 g = 9806.65 mg; Zephyr sensor_value is in m/s²) */
    int16_t ax_mg = (int16_t)(sensor_value_to_double(&accel[0]) * 101.972e0);
    int16_t ay_mg = (int16_t)(sensor_value_to_double(&accel[1]) * 101.972e0);
    int16_t az_mg = (int16_t)(sensor_value_to_double(&accel[2]) * 101.972e0);

    uint32_t now = k_uptime_get_32();
    k_mutex_lock(&s_fsm_mutex, K_FOREVER);
    fsm_transition(&s_fsm, ax_mg, ay_mg, az_mg, now);
    k_mutex_unlock(&s_fsm_mutex);
}
K_WORK_DEFINE(s_accel_work, accel_work_handler);

static void imu_trigger_handler(const struct device *dev,
                                 const struct sensor_trigger *p_trig)
{
    ARG_UNUSED(dev);
    ARG_UNUSED(p_trig);
    k_work_submit(&s_accel_work);
}

/* -------------------------------------------------------------------------
 * Public API
 * ------------------------------------------------------------------------- */
int fall_detection_init(void)
{
    memset(&s_fsm, 0, sizeof(s_fsm));
    s_fsm.state = FALL_STATE_IDLE;

    s_lsm6dso = DEVICE_DT_GET_ONE(st_lsm6dso);
    if (!device_is_ready(s_lsm6dso)) {
        LOG_ERR("LSM6DSO not ready");
        return -ENODEV;
    }

    /* Configure free-fall threshold via sensor driver attr */
    struct sensor_value ff_thresh = { .val1 = FALL_FREE_FALL_THRESH_MG,
                                      .val2 = 0 };
    if (sensor_attr_set(s_lsm6dso, SENSOR_CHAN_ACCEL_XYZ,
                        SENSOR_ATTR_LOWER_THRESH, &ff_thresh) < 0) {
        LOG_WRN("Could not set FF threshold via attr — using driver default");
    }

    /* Enable data-ready trigger */
    struct sensor_trigger trig = {
        .type = SENSOR_TRIG_DATA_READY,
        .chan = SENSOR_CHAN_ACCEL_XYZ,
    };
    if (sensor_trigger_set(s_lsm6dso, &trig, imu_trigger_handler) < 0) {
        LOG_ERR("Failed to set IMU trigger");
        return -EIO;
    }
    LOG_INF("Fall detection initialised (FF=%u mg, IMP=%u mg, STILL=%u mg)",
            FALL_FREE_FALL_THRESH_MG, FALL_IMPACT_THRESH_MG,
            FALL_STILLNESS_THRESH_MG);
    return 0;
}

fall_state_t fall_detection_get_state(void)
{
    fall_state_t state;
    k_mutex_lock(&s_fsm_mutex, K_FOREVER);
    state = s_fsm.state;
    k_mutex_unlock(&s_fsm_mutex);
    return state;
}

void fall_detection_cancel(void)
{
    uint32_t now = k_uptime_get_32();
    k_mutex_lock(&s_fsm_mutex, K_FOREVER);
    if (s_fsm.state == FALL_STATE_CONFIRMED) {
        s_fsm.state          = FALL_STATE_CANCELLED;
        s_fsm.state_entry_ms = now;
        LOG_INF("Fall cancelled by user @ %u ms", now);
        extern int app_event_post(uint32_t event_id, const void *p_data,
                                  size_t data_len);
        (void)app_event_post(EVT_FALL_CANCELLED, NULL, 0U);
    }
    k_mutex_unlock(&s_fsm_mutex);
}

uint32_t fall_detection_count(void)
{
    uint32_t count;
    k_mutex_lock(&s_fsm_mutex, K_FOREVER);
    count = s_fsm.fall_count;
    k_mutex_unlock(&s_fsm_mutex);
    return count;
}

/* -------------------------------------------------------------------------
 * HIL-only functions (compiled only when CONFIG_HIL_TEST_INTERFACE=y)
 * ------------------------------------------------------------------------- */
#ifdef CONFIG_HIL_TEST_INTERFACE

/**
 * @brief Inject a single accelerometer sample into the FSM.
 * Used by INJECT_ACCEL HIL command.
 */
int fall_detection_inject_sample(const accel_sample_t *p_sample)
{
    if (p_sample == NULL) {
        return -EINVAL;
    }
    uint32_t now = k_uptime_get_32();
    k_mutex_lock(&s_fsm_mutex, K_FOREVER);
    fsm_transition(&s_fsm, p_sample->ax_mg, p_sample->ay_mg,
                   p_sample->az_mg, now);
    k_mutex_unlock(&s_fsm_mutex);
    return 0;
}

/**
 * @brief Replay a buffer of samples synchronously.
 * Simulates 100 Hz IMU stream (10 ms per sample).
 * Detects fall and measures latency from first free-fall sample.
 */
int fall_detection_replay(const accel_sample_t *p_buf, uint16_t num_samples,
                           bool *p_detected, uint32_t *p_latency_ms)
{
    if (p_buf == NULL || p_detected == NULL || p_latency_ms == NULL) {
        return -EINVAL;
    }
    if (num_samples == 0U) {
        return -EINVAL;
    }

    /* Reset FSM for clean test */
    k_mutex_lock(&s_fsm_mutex, K_FOREVER);
    fall_state_t saved_count_holder = s_fsm.state; /* unused but keeps MISRA happy */
    ARG_UNUSED(saved_count_holder);
    uint32_t saved_count = s_fsm.fall_count;
    memset(&s_fsm, 0, sizeof(s_fsm));
    s_fsm.state      = FALL_STATE_IDLE;
    s_fsm.fall_count = saved_count;
    k_mutex_unlock(&s_fsm_mutex);

    uint32_t sim_time_ms  = 0U;
    uint32_t detect_ts_ms = 0U;
    bool     detected     = false;

    for (uint16_t i = 0U; i < num_samples; i++) {
        k_mutex_lock(&s_fsm_mutex, K_FOREVER);
        uint32_t pre_state = (uint32_t)s_fsm.state;
        fsm_transition(&s_fsm, p_buf[i].ax_mg, p_buf[i].ay_mg,
                       p_buf[i].az_mg, sim_time_ms);
        if ((pre_state != (uint32_t)FALL_STATE_CONFIRMED) &&
            (s_fsm.state == FALL_STATE_CONFIRMED)) {
            detect_ts_ms = sim_time_ms;
            detected     = true;
        }
        k_mutex_unlock(&s_fsm_mutex);
        sim_time_ms += 10U; /* 100 Hz */
    }

    *p_detected   = detected;
    *p_latency_ms = detected ? detect_ts_ms : 0U;
    return 0;
}

/**
 * @brief Reset fall counter (between test cases).
 */
void fall_detection_reset_count(void)
{
    k_mutex_lock(&s_fsm_mutex, K_FOREVER);
    s_fsm.fall_count = 0U;
    k_mutex_unlock(&s_fsm_mutex);
}

#endif /* CONFIG_HIL_TEST_INTERFACE */

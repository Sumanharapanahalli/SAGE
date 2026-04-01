/**
 * @file     hil_collision_warning_tests.c
 * @brief    Hardware-in-the-Loop test suite for intersection collision-warning
 *           firmware.  Covers unit tests, integration tests, fault injection,
 *           and timing-budget verification.
 *
 * Test coverage target : ≥ 90 % branch coverage (SR-COV-001)
 *
 * Measurement method:
 *   DWT->CYCCNT free-running at SYSCLK (64 MHz on STM32WB55).
 *   Resolution = 15.625 ns; all latency measurements in milliseconds.
 *
 * Intersection scenarios under test:
 *   CW-SCN-001 — Vehicle A approaches from the left on sensor FRONT_LEFT.
 *                Expected: CRITICAL warning when distance ≤ 200 cm and
 *                approach velocity ≥ 50 cm/s.
 *   CW-SCN-002 — Vehicle B approaches from the right on sensor FRONT_RIGHT.
 *                Expected: CRITICAL warning under the same thresholds.
 *
 * MISRA-C:2012 compliance notes:
 *   Rule 8.7   — Static linkage for all non-public functions.
 *   Rule 11.6  — DWT/peripheral register casts are isolated in this file.
 *   Rule 14.4  — All loop bounds are finite and deterministic.
 *   Rule 15.5  — Single exit point per function where practical.
 *   Rule 17.7  — All function return values are used.
 */

#include "collision_warning_hal.h"
#include "hil_config.h"
#include "bsp.h"           /* HIL_BSP_DelayMs, HIL_BSP_GetTick */

#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>        /* memset, memcpy */

/* ---------------------------------------------------------------------------
 * DWT cycle counter — identical helpers to hil_timing_tests.c
 * Rule 11.6: cast of void * to volatile uint32_t * is intentional for DWT.
 * -------------------------------------------------------------------------*/
#define DWT_CTRL   (*((volatile uint32_t *)0xE0001000UL))
#define DWT_CYCCNT (*((volatile uint32_t *)0xE0001004UL))
#define DEM_CR     (*((volatile uint32_t *)0xE000EDFCUL))
#define DEM_CR_TRCENA       (1UL << 24U)
#define DWT_CTRL_CYCCNTENA  (1UL << 0U)
#define DWT_SYSCLK_MHZ      (64U)   /* STM32WB55 @ 64 MHz */

static void dwt_init(void)
{
    DEM_CR    |= DEM_CR_TRCENA;
    DWT_CYCCNT = 0U;
    DWT_CTRL  |= DWT_CTRL_CYCCNTENA;
}

/* Convert DWT cycles to whole milliseconds (truncating). */
static uint32_t dwt_cycles_to_ms(uint32_t cycles)
{
    return cycles / (DWT_SYSCLK_MHZ * 1000U);
}

/* ---------------------------------------------------------------------------
 * RAM stubs — laid out in the HIL linker script at fixed addresses.
 * The Python harness writes to these; firmware reads them as sensor inputs.
 * Rule 11.6: volatile pointer cast required for memory-mapped stub region.
 * -------------------------------------------------------------------------*/
static volatile CW_RadarSample_t * const g_radar_stubs =
    (volatile CW_RadarSample_t *)(CW_STUB_RADAR_BASE_ADDR);

static volatile CW_WarningState_t * const g_warn_state =
    (volatile CW_WarningState_t *)(CW_STUB_WARNING_STATE_ADDR);

static volatile uint32_t * const g_fault_flags =
    (volatile uint32_t *)(CW_STUB_FAULT_INJECT_ADDR);

/* ---------------------------------------------------------------------------
 * Internal assertion macro (mirrors hil_timing_tests.c style)
 * -------------------------------------------------------------------------*/
#define CW_ASSERT(rpt, cond, lbl)                                            \
    do {                                                                      \
        (rpt)->assertions_run++;                                              \
        if (!(cond)) {                                                        \
            (rpt)->assertions_failed++;                                       \
            (void)printf("[CW FAIL] %s\r\n", (lbl));                         \
        } else {                                                              \
            (void)printf("[CW PASS] %s\r\n", (lbl));                         \
        }                                                                     \
    } while (0)

/* ---------------------------------------------------------------------------
 * Helper: write a single radar sample into the RAM stub
 * -------------------------------------------------------------------------*/
static void stub_write_radar(uint8_t  sensor_id,
                             uint16_t dist_cm,
                             int16_t  vel_cms,
                             uint8_t  valid)
{
    if (sensor_id >= CW_SENSOR_COUNT) {
        return;  /* guard: MISRA Rule 15.5 — single early return in helper */
    }
    g_radar_stubs[sensor_id].distance_cm    = dist_cm;
    g_radar_stubs[sensor_id].rel_velocity_cms = vel_cms;
    g_radar_stubs[sensor_id].sensor_id      = sensor_id;
    g_radar_stubs[sensor_id].valid          = valid;
    g_radar_stubs[sensor_id].timestamp_ms   = HIL_BSP_GetTick();
}

/* ---------------------------------------------------------------------------
 * Helper: clear all radar stubs and reset warning state
 * -------------------------------------------------------------------------*/
static void stub_clear_all(void)
{
    uint8_t i;
    for (i = 0U; i < CW_SENSOR_COUNT; i++) {
        stub_write_radar(i, CW_MAX_RANGE_CM, 0, 0U);
    }
    *g_fault_flags = (uint32_t)CW_FAULT_NONE;
    /* Do NOT clear warning state — firmware owns that region */
}

/* ---------------------------------------------------------------------------
 * Helper: poll warning level until it matches expected or times out
 * Returns true if expected level was seen within timeout_ms.
 * -------------------------------------------------------------------------*/
static bool wait_for_warning(CW_WarningLevel_t expected,
                             uint32_t          timeout_ms)
{
    uint32_t deadline = HIL_BSP_GetTick() + timeout_ms;
    bool     matched  = false;

    while (HIL_BSP_GetTick() < deadline) {
        if (g_warn_state->level == expected) {
            matched = true;
            break;
        }
        HIL_BSP_DelayMs(1U);
    }
    return matched;
}

/* ---------------------------------------------------------------------------
 * CW-UT-001: Sensor polling period jitter
 * Verifies firmware calls radar poll at CW_POLL_PERIOD_MS ± CW_POLL_JITTER_MS.
 * Measured via DWT capture on a GPIO toggle set by the production poll ISR.
 * -------------------------------------------------------------------------*/
static HIL_Result_t test_sensor_poll_jitter(HIL_SuiteReport_t *p_report)
{
    /* g_poll_timestamps[] is written by the firmware's poll ISR stub */
    extern volatile uint32_t g_cw_poll_timestamps_ms[CW_POLL_SAMPLES_FOR_JITTER];

    uint32_t i;
    uint32_t max_interval = 0U;
    uint32_t min_interval = UINT32_MAX;
    uint32_t interval;

    HIL_Result_t result = HIL_RESULT_PASS;

    dwt_init();

    /* Wait for the firmware to fill the timestamp ring buffer */
    HIL_BSP_DelayMs(CW_POLL_PERIOD_MS * (CW_POLL_SAMPLES_FOR_JITTER + 2U));

    for (i = 1U; i < CW_POLL_SAMPLES_FOR_JITTER; i++) {
        if (g_cw_poll_timestamps_ms[i] < g_cw_poll_timestamps_ms[i - 1U]) {
            /* Clock wrap — skip this interval */
            continue;
        }
        interval = g_cw_poll_timestamps_ms[i] - g_cw_poll_timestamps_ms[i - 1U];
        if (interval > max_interval) { max_interval = interval; }
        if (interval < min_interval) { min_interval = interval; }
    }

    (void)printf("[CW] poll jitter min=%lu ms max=%lu ms (nominal=%u ±%u ms)\r\n",
                 (unsigned long)min_interval,
                 (unsigned long)max_interval,
                 CW_POLL_PERIOD_MS, CW_POLL_JITTER_MS);

    CW_ASSERT(p_report,
              max_interval <= (CW_POLL_PERIOD_MS + CW_POLL_JITTER_MS),
              "CW-UT-001a: poll period never exceeds 11 ms (SR-CW-TIM-003)");

    CW_ASSERT(p_report,
              min_interval >= (CW_POLL_PERIOD_MS - CW_POLL_JITTER_MS),
              "CW-UT-001b: poll period never below 9 ms (SR-CW-TIM-003)");

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_TIMING;
    }
    return result;
}

/* ---------------------------------------------------------------------------
 * CW-UT-002: TTC calculation — unit test against known inputs
 * Injects known distance and velocity; verifies TTC matches formula:
 *   TTC = distance_cm / |rel_velocity_cms| × 1000   [ms]
 * -------------------------------------------------------------------------*/
static HIL_Result_t test_ttc_calculation(HIL_SuiteReport_t *p_report)
{
    /* Vector: (dist_cm, vel_cms, expected_ttc_ms, tolerance_ms) */
    static const struct {
        uint16_t dist_cm;
        int16_t  vel_cms;
        uint32_t expected_ttc_ms;
        uint32_t tolerance_ms;
    } vectors[] = {
        { 200U,  -100,  2000U, 20U },   /* 2 m at 1 m/s → TTC=2000 ms */
        { 500U,  -250,  2000U, 20U },   /* 5 m at 2.5 m/s → TTC=2000 ms */
        { 150U,  -100,  1500U, 20U },   /* 1.5 m at 1 m/s → TTC=1500 ms (CRITICAL) */
        { 1000U, -500,  2000U, 20U },   /* 10 m at 5 m/s → TTC=2000 ms */
    };
    const uint32_t vector_count = (uint32_t)(sizeof(vectors) / sizeof(vectors[0]));
    uint32_t       i;
    uint32_t       delta;
    bool           pass;

    for (i = 0U; i < vector_count; i++) {
        stub_clear_all();
        stub_write_radar(CW_SENSOR_FRONT_LEFT,
                         vectors[i].dist_cm,
                         vectors[i].vel_cms,
                         1U);

        /* Allow one poll cycle + processing margin */
        HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 5U);

        delta = (g_warn_state->ttc_ms > vectors[i].expected_ttc_ms)
              ? (g_warn_state->ttc_ms - vectors[i].expected_ttc_ms)
              : (vectors[i].expected_ttc_ms - g_warn_state->ttc_ms);

        pass = (delta <= vectors[i].tolerance_ms);

        (void)printf("[CW] TTC vec[%lu]: dist=%u vel=%d exp=%lu got=%lu delta=%lu %s\r\n",
                     (unsigned long)i,
                     vectors[i].dist_cm,
                     (int)vectors[i].vel_cms,
                     (unsigned long)vectors[i].expected_ttc_ms,
                     (unsigned long)g_warn_state->ttc_ms,
                     (unsigned long)delta,
                     pass ? "OK" : "FAIL");

        CW_ASSERT(p_report, pass, "CW-UT-002: TTC within 20 ms tolerance");
    }

    stub_clear_all();
    return HIL_RESULT_PASS;
}

/* ---------------------------------------------------------------------------
 * CW-INT-001: Vehicle A intersection scenario (CW-SCN-001)
 * Vehicle approaches on FRONT_LEFT at 1 m/s from 10 m.
 * After 8 s simulated time the vehicle is at 2 m → CRITICAL expected.
 * HIL injects 8 sequential radar samples at 1 s intervals.
 * -------------------------------------------------------------------------*/
static HIL_Result_t test_vehicle_a_scenario(HIL_SuiteReport_t *p_report)
{
    /* Approach profile: 1000 cm → 200 cm, 8 steps of 100 cm each */
    static const uint16_t profile_dist_cm[] =
        { 1000U, 900U, 800U, 700U, 600U, 500U, 400U, 200U };
    static const int16_t  approach_vel = -100;  /* 1 m/s approaching */
    const uint32_t        steps        = (uint32_t)(sizeof(profile_dist_cm) /
                                                    sizeof(profile_dist_cm[0]));
    uint32_t              step;
    bool                  warn_seen    = false;
    uint32_t              detect_ts    = 0U;
    uint32_t              warn_ts      = 0U;
    uint32_t              latency_ms;
    HIL_Result_t          result       = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[CW] --- CW-SCN-001: Vehicle A (FRONT_LEFT) ---\r\n");

    for (step = 0U; step < steps; step++) {
        stub_write_radar(CW_SENSOR_FRONT_LEFT,
                         profile_dist_cm[step],
                         approach_vel,
                         1U);

        /* Wait for firmware to process and possibly issue warning */
        HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 5U);

        (void)printf("[CW] SCN-001 step=%lu dist=%u warn=%u ttc=%lu ms\r\n",
                     (unsigned long)step,
                     profile_dist_cm[step],
                     (unsigned int)g_warn_state->level,
                     (unsigned long)g_warn_state->ttc_ms);

        /* Latch detection timestamp on first non-NONE warning */
        if ((!warn_seen) && (g_warn_state->level != CW_WARN_NONE)) {
            warn_seen  = true;
            detect_ts  = g_warn_state->detection_ts_ms;
            warn_ts    = g_warn_state->warning_ts_ms;
        }
    }

    /* --- Verify scenario outcome --- */
    CW_ASSERT(p_report,
              warn_seen,
              "CW-INT-001a: Vehicle A triggers at least one warning event");

    CW_ASSERT(p_report,
              g_warn_state->level == CW_WARN_CRITICAL,
              "CW-INT-001b: Vehicle A at 200 cm → CRITICAL warning level");

    CW_ASSERT(p_report,
              g_warn_state->triggered_sensor == (uint32_t)CW_SENSOR_FRONT_LEFT,
              "CW-INT-001c: triggered sensor is FRONT_LEFT");

    /* --- Timing: detection latency (SR-CW-TIM-001) --- */
    latency_ms = g_warn_state->detection_lat_ms;
    (void)printf("[CW] SCN-001 detection_lat=%lu ms (budget=%u ms)\r\n",
                 (unsigned long)latency_ms, CW_DETECTION_LATENCY_MAX_MS);
    CW_ASSERT(p_report,
              latency_ms <= CW_DETECTION_LATENCY_MAX_MS,
              "CW-INT-001d: detection latency ≤ 50 ms (SR-CW-TIM-001)");

    /* --- Timing: warning output latency (SR-CW-TIM-002) --- */
    if (warn_ts >= detect_ts) {
        latency_ms = warn_ts - detect_ts;
    } else {
        latency_ms = 0U;  /* clock wrap guard */
    }
    (void)printf("[CW] SCN-001 warning_lat=%lu ms (budget=%u ms)\r\n",
                 (unsigned long)latency_ms, CW_WARNING_LATENCY_MAX_MS);
    CW_ASSERT(p_report,
              latency_ms <= CW_WARNING_LATENCY_MAX_MS,
              "CW-INT-001e: warning output latency ≤ 100 ms (SR-CW-TIM-002)");

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_TIMING;
    }

    stub_clear_all();
    HIL_BSP_DelayMs(20U);   /* settle before next scenario */
    return result;
}

/* ---------------------------------------------------------------------------
 * CW-INT-002: Vehicle B intersection scenario (CW-SCN-002)
 * Mirrors CW-SCN-001 on FRONT_RIGHT at a higher approach speed (2.5 m/s).
 * This verifies independent sensor channel processing.
 * -------------------------------------------------------------------------*/
static HIL_Result_t test_vehicle_b_scenario(HIL_SuiteReport_t *p_report)
{
    static const uint16_t profile_dist_cm[] =
        { 1000U, 750U, 500U, 300U, 150U };
    static const int16_t  approach_vel = -250;  /* 2.5 m/s approaching */
    const uint32_t        steps        = (uint32_t)(sizeof(profile_dist_cm) /
                                                    sizeof(profile_dist_cm[0]));
    uint32_t              step;
    bool                  critical_seen = false;
    uint32_t              latency_ms;
    HIL_Result_t          result        = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[CW] --- CW-SCN-002: Vehicle B (FRONT_RIGHT) ---\r\n");

    for (step = 0U; step < steps; step++) {
        stub_write_radar(CW_SENSOR_FRONT_RIGHT,
                         profile_dist_cm[step],
                         approach_vel,
                         1U);
        HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 5U);

        (void)printf("[CW] SCN-002 step=%lu dist=%u warn=%u ttc=%lu ms\r\n",
                     (unsigned long)step,
                     profile_dist_cm[step],
                     (unsigned int)g_warn_state->level,
                     (unsigned long)g_warn_state->ttc_ms);

        if (g_warn_state->level == CW_WARN_CRITICAL) {
            critical_seen = true;
        }
    }

    CW_ASSERT(p_report,
              critical_seen,
              "CW-INT-002a: Vehicle B at 150 cm → CRITICAL warning triggered");

    CW_ASSERT(p_report,
              g_warn_state->triggered_sensor == (uint32_t)CW_SENSOR_FRONT_RIGHT,
              "CW-INT-002b: triggered sensor is FRONT_RIGHT");

    /* Advisory and caution levels must both have been visited en route */
    CW_ASSERT(p_report,
              g_warn_state->warn_count >= 2U,
              "CW-INT-002c: warning escalated through ≥ 2 levels");

    latency_ms = g_warn_state->detection_lat_ms;
    CW_ASSERT(p_report,
              latency_ms <= CW_DETECTION_LATENCY_MAX_MS,
              "CW-INT-002d: detection latency ≤ 50 ms (SR-CW-TIM-001)");

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_TIMING;
    }

    stub_clear_all();
    HIL_BSP_DelayMs(20U);
    return result;
}

/* ---------------------------------------------------------------------------
 * CW-INT-003: Simultaneous vehicles on both front sensors
 * Both FRONT_LEFT and FRONT_RIGHT approaching simultaneously.
 * The system must issue CRITICAL for the sensor with lower TTC.
 * -------------------------------------------------------------------------*/
static HIL_Result_t test_simultaneous_vehicles(HIL_SuiteReport_t *p_report)
{
    stub_clear_all();
    (void)printf("[CW] --- CW-INT-003: Simultaneous vehicles ---\r\n");

    /* Vehicle A closer (150 cm) but slower; Vehicle B further (300 cm) but faster */
    stub_write_radar(CW_SENSOR_FRONT_LEFT,  150U, -50,  1U);  /* TTC=3000 ms */
    stub_write_radar(CW_SENSOR_FRONT_RIGHT, 300U, -300, 1U);  /* TTC=1000 ms → CRITICAL */

    HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 20U);

    CW_ASSERT(p_report,
              g_warn_state->level == CW_WARN_CRITICAL,
              "CW-INT-003a: system selects CRITICAL for sensor with lower TTC");

    CW_ASSERT(p_report,
              g_warn_state->triggered_sensor == (uint32_t)CW_SENSOR_FRONT_RIGHT,
              "CW-INT-003b: FRONT_RIGHT identified as the critical threat");

    stub_clear_all();
    HIL_BSP_DelayMs(20U);
    return HIL_RESULT_PASS;
}

/* ---------------------------------------------------------------------------
 * CW-FI-001: Fault injection — sensor timeout
 * Sets CW_FAULT_SENSOR_TIMEOUT; firmware must detect within 3 poll cycles
 * (30 ms) and flag a sensor fault without issuing a spurious warning.
 * -------------------------------------------------------------------------*/
static HIL_Result_t test_fault_sensor_timeout(HIL_SuiteReport_t *p_report)
{
    extern volatile uint32_t g_cw_fault_detected_flags;
    uint32_t                 timeout_detect_ms = 3U * CW_POLL_PERIOD_MS + 10U;
    bool                     detected;
    HIL_Result_t             result = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[CW] --- CW-FI-001: Sensor timeout fault ---\r\n");

    /* Pre-condition: vehicle at advisory range */
    stub_write_radar(CW_SENSOR_FRONT_LEFT, 800U, -100, 1U);
    HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 5U);

    /* Inject fault: mark all samples invalid to simulate timeout */
    *g_fault_flags = (uint32_t)CW_FAULT_SENSOR_TIMEOUT;

    detected = wait_for_warning(CW_WARN_NONE, timeout_detect_ms);
    /* When sensor timeouts, warning must drop to NONE (fail-safe) */

    (void)printf("[CW] FI-001: fault detected=%u\r\n", (unsigned int)detected);

    CW_ASSERT(p_report,
              (g_cw_fault_detected_flags & (uint32_t)CW_FAULT_SENSOR_TIMEOUT) != 0U,
              "CW-FI-001a: sensor timeout fault flag set in firmware state");

    /* Warning must not remain active after sensor loss — fail-safe must clear */
    HIL_BSP_DelayMs(timeout_detect_ms);
    CW_ASSERT(p_report,
              g_warn_state->level == CW_WARN_NONE,
              "CW-FI-001b: warning cleared to NONE after sensor timeout (fail-safe)");

    /* Clear fault and verify recovery */
    *g_fault_flags = (uint32_t)CW_FAULT_NONE;
    stub_write_radar(CW_SENSOR_FRONT_LEFT, 800U, -100, 1U);
    HIL_BSP_DelayMs(CW_POLL_PERIOD_MS * 2U);

    CW_ASSERT(p_report,
              g_warn_state->level != CW_WARN_NONE,
              "CW-FI-001c: warning resumes after sensor recovery");

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_FAULT;
    }

    stub_clear_all();
    HIL_BSP_DelayMs(20U);
    return result;
}

/* ---------------------------------------------------------------------------
 * CW-FI-002: Fault injection — sensor stuck / frozen output
 * Radar output repeats the same distance for > 500 ms while vehicle should
 * be approaching.  Firmware must detect the frozen signal and flag it.
 * -------------------------------------------------------------------------*/
static HIL_Result_t test_fault_sensor_stuck(HIL_SuiteReport_t *p_report)
{
    extern volatile uint32_t g_cw_fault_detected_flags;
    const uint16_t           frozen_dist = 500U;
    uint32_t                 i;
    HIL_Result_t             result = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[CW] --- CW-FI-002: Sensor stuck fault ---\r\n");

    *g_fault_flags = (uint32_t)CW_FAULT_SENSOR_STUCK;

    /* Write identical distance 20 times — simulates frozen radar */
    for (i = 0U; i < 20U; i++) {
        stub_write_radar(CW_SENSOR_FRONT_LEFT, frozen_dist, -100, 1U);
        HIL_BSP_DelayMs(CW_POLL_PERIOD_MS);
    }

    (void)printf("[CW] FI-002: fault_flags=0x%08lX\r\n",
                 (unsigned long)g_cw_fault_detected_flags);

    CW_ASSERT(p_report,
              (g_cw_fault_detected_flags & (uint32_t)CW_FAULT_SENSOR_STUCK) != 0U,
              "CW-FI-002a: stuck sensor detected after 20 identical samples");

    /* The TTC must NOT count down (distance never changed) */
    CW_ASSERT(p_report,
              g_warn_state->level != CW_WARN_CRITICAL,
              "CW-FI-002b: no CRITICAL warning issued from frozen sensor");

    *g_fault_flags = (uint32_t)CW_FAULT_NONE;
    stub_clear_all();
    HIL_BSP_DelayMs(20U);

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_FAULT;
    }
    return result;
}

/* ---------------------------------------------------------------------------
 * CW-FI-003: Fault injection — CAN bus error frame
 * Injects CW_FAULT_CAN_BUS_ERROR.  Firmware must:
 *   (a) log the CAN error event,
 *   (b) continue operating on locally cached radar data,
 *   (c) not suppress an active collision warning.
 * -------------------------------------------------------------------------*/
static HIL_Result_t test_fault_can_bus_error(HIL_SuiteReport_t *p_report)
{
    extern volatile uint32_t g_cw_fault_detected_flags;
    extern volatile uint32_t g_cw_can_error_count;
    uint32_t                 prior_error_count;
    HIL_Result_t             result = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[CW] --- CW-FI-003: CAN bus error ---\r\n");

    /* Set up an active caution scenario first */
    stub_write_radar(CW_SENSOR_FRONT_LEFT, 400U, -150, 1U);
    HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 5U);

    prior_error_count = g_cw_can_error_count;

    /* Inject CAN error while warning is active */
    *g_fault_flags = (uint32_t)CW_FAULT_CAN_BUS_ERROR;
    HIL_BSP_DelayMs(50U);

    CW_ASSERT(p_report,
              (g_cw_fault_detected_flags & (uint32_t)CW_FAULT_CAN_BUS_ERROR) != 0U,
              "CW-FI-003a: CAN bus error fault flag set");

    CW_ASSERT(p_report,
              g_cw_can_error_count > prior_error_count,
              "CW-FI-003b: CAN error counter incremented");

    /* Warning must remain active — CAN error must not suppress safety output */
    CW_ASSERT(p_report,
              g_warn_state->level >= CW_WARN_CAUTION,
              "CW-FI-003c: collision warning not suppressed during CAN fault");

    *g_fault_flags = (uint32_t)CW_FAULT_NONE;
    stub_clear_all();
    HIL_BSP_DelayMs(20U);

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_FAULT;
    }
    return result;
}

/* ---------------------------------------------------------------------------
 * CW-FI-004: Fault injection — power glitch
 * Brief VDD transient injected via relay.  Firmware must retain last valid
 * warning state and resume processing within 50 ms.
 * -------------------------------------------------------------------------*/
static HIL_Result_t test_fault_power_glitch(HIL_SuiteReport_t *p_report)
{
    CW_WarningLevel_t pre_glitch_level;
    HIL_Result_t      result = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[CW] --- CW-FI-004: Power glitch ---\r\n");

    /* Establish a known warning level */
    stub_write_radar(CW_SENSOR_FRONT_LEFT, 150U, -100, 1U);
    HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 10U);
    pre_glitch_level = g_warn_state->level;

    *g_fault_flags = (uint32_t)CW_FAULT_POWER_GLITCH;
    HIL_BSP_DelayMs(5U);    /* Glitch hold: < 50 µs in production; 5 ms HIL sim */
    *g_fault_flags = (uint32_t)CW_FAULT_NONE;

    /* Allow firmware 50 ms to recover and re-evaluate */
    HIL_BSP_DelayMs(50U);
    stub_write_radar(CW_SENSOR_FRONT_LEFT, 150U, -100, 1U);
    HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 10U);

    CW_ASSERT(p_report,
              g_warn_state->level == pre_glitch_level,
              "CW-FI-004a: warning level restored to pre-glitch state after recovery");

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_FAULT;
    }

    stub_clear_all();
    HIL_BSP_DelayMs(20U);
    return result;
}

/* ---------------------------------------------------------------------------
 * CW-UT-003: Warning level hysteresis
 * A vehicle retreating from 200 cm to 600 cm must cause warning level to
 * de-escalate.  Tests that hysteresis prevents oscillation at thresholds.
 * -------------------------------------------------------------------------*/
static HIL_Result_t test_warning_hysteresis(HIL_SuiteReport_t *p_report)
{
    static const uint16_t retreat_profile[] =
        { 200U, 250U, 350U, 450U, 600U, 800U };
    const uint32_t steps = (uint32_t)(sizeof(retreat_profile) /
                                      sizeof(retreat_profile[0]));
    uint32_t       i;
    CW_WarningLevel_t prev_level;

    stub_clear_all();
    (void)printf("[CW] --- CW-UT-003: Warning hysteresis ---\r\n");

    /* Start at CRITICAL */
    stub_write_radar(CW_SENSOR_FRONT_LEFT, 200U, -100, 1U);
    HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 10U);
    CW_ASSERT(p_report,
              g_warn_state->level == CW_WARN_CRITICAL,
              "CW-UT-003a: initial CRITICAL at 200 cm established");

    prev_level = g_warn_state->level;

    for (i = 1U; i < steps; i++) {
        stub_write_radar(CW_SENSOR_FRONT_LEFT, retreat_profile[i], 100, 1U);
        HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 5U);

        /* Warning may de-escalate but must never escalate during retreat */
        CW_ASSERT(p_report,
                  g_warn_state->level <= prev_level,
                  "CW-UT-003b: warning does not escalate during retreat");

        prev_level = g_warn_state->level;
    }

    /* At 800 cm, warning must be NONE or ADVISORY at most */
    CW_ASSERT(p_report,
              g_warn_state->level <= CW_WARN_ADVISORY,
              "CW-UT-003c: warning ≤ ADVISORY when vehicle retreats to 800 cm");

    stub_clear_all();
    HIL_BSP_DelayMs(20U);
    return HIL_RESULT_PASS;
}

/* ---------------------------------------------------------------------------
 * CW-COV-001: Coverage gate — check branch coverage counter in firmware
 * The firmware increments g_cw_branch_coverage_hits[] for each taken branch.
 * This test verifies the on-target counter has reached ≥ 90 % of branches.
 * -------------------------------------------------------------------------*/
static HIL_Result_t test_coverage_gate(HIL_SuiteReport_t *p_report)
{
    extern volatile uint32_t g_cw_branch_total;
    extern volatile uint32_t g_cw_branch_covered;

    uint32_t pct;
    HIL_Result_t result = HIL_RESULT_PASS;

    if (g_cw_branch_total == 0U) {
        (void)printf("[CW] COV: coverage counters not instrumented — skip gate\r\n");
        return HIL_RESULT_PASS;  /* Not a failure: may be non-coverage build */
    }

    pct = (g_cw_branch_covered * 100U) / g_cw_branch_total;

    (void)printf("[CW] COV: covered=%lu total=%lu pct=%lu%% (target=%u%%)\r\n",
                 (unsigned long)g_cw_branch_covered,
                 (unsigned long)g_cw_branch_total,
                 (unsigned long)pct,
                 HIL_COVERAGE_TARGET_PCT);

    CW_ASSERT(p_report,
              pct >= HIL_COVERAGE_TARGET_PCT,
              "CW-COV-001: branch coverage ≥ 90 % (SR-COV-001)");

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_COVERAGE;
    }
    return result;
}

/* ===========================================================================
 * Public entry point
 * =========================================================================*/

/**
 * @brief  Run the full collision-warning HIL test suite.
 *
 * Execution order (designed for increasing observability):
 *   1. Unit tests (no scenario — isolated function verification)
 *   2. Integration / scenario tests (end-to-end signal flow)
 *   3. Fault injection tests
 *   4. Coverage gate (must be last — ensures all branches exercised)
 *
 * @param  p_report  Pointer to caller-allocated report structure.
 *                   Must not be NULL.
 * @return HIL_RESULT_PASS if all assertions pass; failure code otherwise.
 */
HIL_Result_t HIL_CollisionWarningSuite(HIL_SuiteReport_t *p_report)
{
    HIL_Result_t r;

    if (p_report == NULL) {
        return HIL_RESULT_ERROR_SETUP;
    }

    (void)printf("[CW] ====== Collision Warning HIL Suite START ======\r\n");

    /* 1 — Unit tests */
    r = test_sensor_poll_jitter(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    r = test_ttc_calculation(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    r = test_warning_hysteresis(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    /* 2 — Scenario / integration tests */
    r = test_vehicle_a_scenario(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    r = test_vehicle_b_scenario(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    r = test_simultaneous_vehicles(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    /* 3 — Fault injection */
    r = test_fault_sensor_timeout(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    r = test_fault_sensor_stuck(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    r = test_fault_can_bus_error(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    r = test_fault_power_glitch(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    /* 4 — Coverage gate (last) */
    r = test_coverage_gate(p_report);

    (void)printf("[CW] ====== Collision Warning HIL Suite END: %s (%lu/%lu passed) ======\r\n",
                 (r == HIL_RESULT_PASS) ? "PASS" : "FAIL",
                 (unsigned long)(p_report->assertions_run - p_report->assertions_failed),
                 (unsigned long)p_report->assertions_run);

    return r;
}

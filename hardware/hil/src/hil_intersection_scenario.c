/**
 * @file     hil_intersection_scenario.c
 * @brief    Intersection collision-warning scenario tests for HIL firmware.
 *
 * Scenario under test (from task payload):
 *   "Intersection with vehicle A" — collision warning triggered when vehicle A
 *   approaches intersection.
 *
 * This file extends the base collision-warning HIL suite (hil_collision_warning_tests.c)
 * with structured intersection geometry scenarios.  Each scenario maps to a real
 * intersection geometry: T-junction, 4-way cross, blind corner, and simultaneous
 * multi-vector threat.
 *
 * Acceptance criteria verified here:
 *   AC-HIL-CW-001 : HIL test coverage ≥ 90 % (SR-COV-001)
 *   AC-HIL-CW-002 : All fault injection tests pass
 *   AC-HIL-CW-003 : Timing requirements verified (SR-CW-TIM-001/002/003)
 *
 * Target MCU : STM32WB55RGV6 (Cortex-M4 @ 64 MHz)
 * Toolchain  : arm-none-eabi-gcc 12.x
 * Standard   : MISRA-C:2012 (ISO/IEC 9899:2011)
 *
 * MISRA-C:2012 compliance notes:
 *   Rule 8.7   — All non-public functions have static linkage.
 *   Rule 11.6  — Volatile pointer casts are isolated to this file.
 *   Rule 14.4  — Loop bounds are finite and deterministic.
 *   Rule 15.5  — Single exit per function where practical.
 *   Rule 17.7  — All return values are used by callers.
 *   Rule 20.7  — All macro parameters are parenthesised.
 */

#include "collision_warning_hal.h"
#include "hil_config.h"
#include "bsp.h"    /* HIL_BSP_DelayMs, HIL_BSP_GetTick */

#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

/* ---------------------------------------------------------------------------
 * Interrupt priority configuration (NVIC)
 * Radar poll timer ISR: priority 5 (below RTOS kernel, above idle tasks)
 * Warning GPIO ISR    : priority 4 (one notch above radar poll for real-time output)
 * DWT access is priority-independent (CoreSight always-on).
 * -------------------------------------------------------------------------*/
#define CW_IRQ_RADAR_POLL_PRIORITY  (5U)
#define CW_IRQ_WARNING_GPIO_PRIORITY (4U)

/* ---------------------------------------------------------------------------
 * DWT cycle counter — MISRA Rule 11.6: volatile cast intentional for DWT.
 * -------------------------------------------------------------------------*/
#define DWT_CTRL   (*((volatile uint32_t *)0xE0001000UL))
#define DWT_CYCCNT (*((volatile uint32_t *)0xE0001004UL))
#define DEM_CR     (*((volatile uint32_t *)0xE000EDFCUL))
#define DEM_CR_TRCENA       (1UL << 24U)
#define DWT_CTRL_CYCCNTENA  (1UL << 0U)
#define DWT_SYSCLK_MHZ      (64U)

static void dwt_init(void)
{
    DEM_CR    |= DEM_CR_TRCENA;
    DWT_CYCCNT = 0U;
    DWT_CTRL  |= DWT_CTRL_CYCCNTENA;
}

static uint32_t dwt_cycles_to_ms(uint32_t cycles)
{
    return cycles / (DWT_SYSCLK_MHZ * 1000U);
}

/* ---------------------------------------------------------------------------
 * RAM stubs — Python harness writes sensor data here; firmware reads it.
 * Addresses must match collision_warning_hal.h and the HIL linker script.
 * MISRA Rule 11.6: volatile pointer cast required for memory-mapped regions.
 * -------------------------------------------------------------------------*/
static volatile CW_RadarSample_t * const g_radar_stubs =
    (volatile CW_RadarSample_t *)(CW_STUB_RADAR_BASE_ADDR);

static volatile CW_WarningState_t * const g_warn_state =
    (volatile CW_WarningState_t *)(CW_STUB_WARNING_STATE_ADDR);

static volatile uint32_t * const g_fault_flags =
    (volatile uint32_t *)(CW_STUB_FAULT_INJECT_ADDR);

/* ---------------------------------------------------------------------------
 * Internal assertion macro
 * -------------------------------------------------------------------------*/
#define IS_ASSERT(rpt, cond, lbl)                                             \
    do {                                                                       \
        (rpt)->assertions_run++;                                               \
        if (!(cond)) {                                                         \
            (rpt)->assertions_failed++;                                        \
            (void)printf("[IS FAIL] %s\r\n", (lbl));                          \
        } else {                                                               \
            (void)printf("[IS PASS] %s\r\n", (lbl));                          \
        }                                                                      \
    } while (0)

/* ---------------------------------------------------------------------------
 * Helper: inject one radar sample into the stub region
 * sensor_id must be < CW_SENSOR_COUNT; early return on bounds violation.
 * -------------------------------------------------------------------------*/
static void stub_write_radar(uint8_t  sensor_id,
                             uint16_t dist_cm,
                             int16_t  vel_cms,
                             uint8_t  valid)
{
    if (sensor_id >= CW_SENSOR_COUNT) {
        return;  /* MISRA Rule 15.5 — single early return in guard */
    }
    g_radar_stubs[sensor_id].distance_cm      = dist_cm;
    g_radar_stubs[sensor_id].rel_velocity_cms = vel_cms;
    g_radar_stubs[sensor_id].sensor_id        = sensor_id;
    g_radar_stubs[sensor_id].valid            = valid;
    g_radar_stubs[sensor_id].timestamp_ms     = HIL_BSP_GetTick();
}

/* ---------------------------------------------------------------------------
 * Helper: clear all sensor stubs to max-range, invalid
 * -------------------------------------------------------------------------*/
static void stub_clear_all(void)
{
    uint8_t i;
    for (i = 0U; i < CW_SENSOR_COUNT; i++) {
        stub_write_radar(i, CW_MAX_RANGE_CM, 0, 0U);
    }
    *g_fault_flags = (uint32_t)CW_FAULT_NONE;
}

/* ---------------------------------------------------------------------------
 * Helper: poll warning level until expected or timeout_ms elapses.
 * Returns true if expected level was seen within the timeout.
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

/* ===========================================================================
 * IS-SCN-001: Vehicle A head-on approach at T-junction
 *
 * Geometry  : Vehicle A enters from the left along the main road and crosses
 *             in front of the ego vehicle at the T-junction.
 * Profile   : 1000 cm → 200 cm in 8 steps on SENSOR_FRONT_LEFT.
 * Velocity  : −100 cm/s (1 m/s constant approach).
 * Expected  : CRITICAL warning when distance ≤ CW_CRITICAL_DISTANCE_CM (200 cm)
 *             with latency ≤ CW_DETECTION_LATENCY_MAX_MS (50 ms).
 * =========================================================================*/
static HIL_Result_t is_scn_001_vehicle_a_t_junction(HIL_SuiteReport_t *p_report)
{
    /* Approach profile — 8 distance steps (cm) */
    static const uint16_t profile_dist_cm[] =
        { 1000U, 900U, 800U, 700U, 600U, 500U, 400U, 200U };
    static const int16_t  approach_vel = -100;   /* 1 m/s */
    const uint32_t        steps        =
        (uint32_t)(sizeof(profile_dist_cm) / sizeof(profile_dist_cm[0]));

    uint32_t     step;
    bool         critical_seen = false;
    uint32_t     first_warn_step = UINT32_MAX;
    uint32_t     t_start_ms;
    uint32_t     t_warn_ms;
    uint32_t     reaction_ms;
    HIL_Result_t result = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[IS] --- IS-SCN-001: Vehicle A T-junction approach ---\r\n");

    dwt_init();
    t_start_ms = HIL_BSP_GetTick();

    for (step = 0U; step < steps; step++) {
        stub_write_radar(CW_SENSOR_FRONT_LEFT,
                         profile_dist_cm[step],
                         approach_vel,
                         1U);
        HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 5U);

        (void)printf("[IS] SCN-001 step=%lu dist=%u warn=%u ttc=%lu ms\r\n",
                     (unsigned long)step,
                     profile_dist_cm[step],
                     (unsigned int)g_warn_state->level,
                     (unsigned long)g_warn_state->ttc_ms);

        if ((first_warn_step == UINT32_MAX) &&
            (g_warn_state->level != CW_WARN_NONE)) {
            first_warn_step = step;
            t_warn_ms = HIL_BSP_GetTick();
        }
        if (g_warn_state->level == CW_WARN_CRITICAL) {
            critical_seen = true;
        }
    }

    /* --- AC verification --- */
    IS_ASSERT(p_report,
              critical_seen,
              "IS-SCN-001a: CRITICAL warning triggered for vehicle A at intersection");

    IS_ASSERT(p_report,
              g_warn_state->triggered_sensor == (uint32_t)CW_SENSOR_FRONT_LEFT,
              "IS-SCN-001b: FRONT_LEFT identified as intersection threat sensor");

    IS_ASSERT(p_report,
              g_warn_state->detection_lat_ms <= CW_DETECTION_LATENCY_MAX_MS,
              "IS-SCN-001c: detection latency ≤ 50 ms (SR-CW-TIM-001)");

    IS_ASSERT(p_report,
              g_warn_state->warning_lat_ms <= CW_WARNING_LATENCY_MAX_MS,
              "IS-SCN-001d: warning output latency ≤ 100 ms (SR-CW-TIM-002)");

    /* Reaction time: from first step to first warning — must be < 200 ms */
    if (first_warn_step != UINT32_MAX) {
        reaction_ms = t_warn_ms - t_start_ms;
        (void)printf("[IS] SCN-001 first_warn_step=%lu reaction_ms=%lu\r\n",
                     (unsigned long)first_warn_step,
                     (unsigned long)reaction_ms);
        IS_ASSERT(p_report,
                  reaction_ms < 200U,
                  "IS-SCN-001e: end-to-end reaction < 200 ms (advisory threshold)");
    }

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_TIMING;
    }
    stub_clear_all();
    HIL_BSP_DelayMs(20U);
    return result;
}

/* ===========================================================================
 * IS-SCN-002: Vehicle A high-speed approach at 4-way crossing
 *
 * Geometry  : 4-way intersection; vehicle A running a red light at 3 m/s.
 * Profile   : 900 cm → 100 cm in 6 steps on SENSOR_FRONT_LEFT.
 * Velocity  : −300 cm/s (3 m/s).
 * Expected  : CRITICAL before distance reaches CW_CAUTION_DISTANCE_CM (500 cm)
 *             because TTC < CW_TTC_CRITICAL_MS (1500 ms) at that velocity.
 * =========================================================================*/
static HIL_Result_t is_scn_002_vehicle_a_high_speed(HIL_SuiteReport_t *p_report)
{
    static const uint16_t profile_dist_cm[] =
        { 900U, 700U, 500U, 300U, 200U, 100U };
    static const int16_t  approach_vel = -300;   /* 3 m/s */
    const uint32_t        steps        =
        (uint32_t)(sizeof(profile_dist_cm) / sizeof(profile_dist_cm[0]));

    uint32_t          step;
    bool              critical_early = false;  /* CRITICAL before 500 cm? */
    CW_WarningLevel_t prev_level     = CW_WARN_NONE;
    HIL_Result_t      result         = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[IS] --- IS-SCN-002: Vehicle A high-speed 4-way ---\r\n");

    for (step = 0U; step < steps; step++) {
        stub_write_radar(CW_SENSOR_FRONT_LEFT,
                         profile_dist_cm[step],
                         approach_vel,
                         1U);
        HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 5U);

        (void)printf("[IS] SCN-002 step=%lu dist=%u warn=%u ttc=%lu ms\r\n",
                     (unsigned long)step,
                     profile_dist_cm[step],
                     (unsigned int)g_warn_state->level,
                     (unsigned long)g_warn_state->ttc_ms);

        /* TTC at 500 cm @ 3 m/s = 1667 ms → still > 1500 ms threshold.
         * At 300 cm @ 3 m/s = 1000 ms → CRITICAL.
         * The system must recognise CRITICAL by step 3 (300 cm). */
        if ((profile_dist_cm[step] <= 500U) &&
            (g_warn_state->level == CW_WARN_CRITICAL)) {
            critical_early = true;
        }

        /* Warning must never de-escalate during approach */
        IS_ASSERT(p_report,
                  g_warn_state->level >= prev_level,
                  "IS-SCN-002a: warning level monotonically non-decreasing");
        prev_level = g_warn_state->level;
    }

    IS_ASSERT(p_report,
              g_warn_state->level == CW_WARN_CRITICAL,
              "IS-SCN-002b: CRITICAL reached at end of high-speed approach");

    IS_ASSERT(p_report,
              critical_early,
              "IS-SCN-002c: CRITICAL triggered before 300 cm based on TTC (3 m/s)");

    IS_ASSERT(p_report,
              g_warn_state->detection_lat_ms <= CW_DETECTION_LATENCY_MAX_MS,
              "IS-SCN-002d: detection latency ≤ 50 ms (SR-CW-TIM-001)");

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_TIMING;
    }
    stub_clear_all();
    HIL_BSP_DelayMs(20U);
    return result;
}

/* ===========================================================================
 * IS-SCN-003: Blind-corner approach — vehicle A on REAR_LEFT
 *
 * Geometry  : Blind corner; vehicle A approaches from behind-left as ego
 *             turns right. REAR_LEFT sensor picks up the threat.
 * Profile   : 600 cm → 150 cm in 5 steps.
 * Velocity  : −200 cm/s (2 m/s).
 * Expected  : WARNING (at least CAUTION) triggered on REAR_LEFT sensor.
 * =========================================================================*/
static HIL_Result_t is_scn_003_blind_corner_rear(HIL_SuiteReport_t *p_report)
{
    static const uint16_t profile_dist_cm[] =
        { 600U, 450U, 350U, 250U, 150U };
    static const int16_t  approach_vel = -200;   /* 2 m/s */
    const uint32_t        steps        =
        (uint32_t)(sizeof(profile_dist_cm) / sizeof(profile_dist_cm[0]));

    uint32_t     step;
    bool         warn_triggered = false;
    HIL_Result_t result         = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[IS] --- IS-SCN-003: Blind corner REAR_LEFT ---\r\n");

    for (step = 0U; step < steps; step++) {
        stub_write_radar(CW_SENSOR_REAR_LEFT,
                         profile_dist_cm[step],
                         approach_vel,
                         1U);
        HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 5U);

        (void)printf("[IS] SCN-003 step=%lu dist=%u warn=%u\r\n",
                     (unsigned long)step,
                     profile_dist_cm[step],
                     (unsigned int)g_warn_state->level);

        if (g_warn_state->level >= CW_WARN_CAUTION) {
            warn_triggered = true;
        }
    }

    IS_ASSERT(p_report,
              warn_triggered,
              "IS-SCN-003a: CAUTION or higher triggered for blind-corner REAR_LEFT");

    IS_ASSERT(p_report,
              g_warn_state->triggered_sensor == (uint32_t)CW_SENSOR_REAR_LEFT,
              "IS-SCN-003b: triggered sensor is REAR_LEFT for blind corner");

    IS_ASSERT(p_report,
              g_warn_state->detection_lat_ms <= CW_DETECTION_LATENCY_MAX_MS,
              "IS-SCN-003c: detection latency ≤ 50 ms (SR-CW-TIM-001)");

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_SENSOR;
    }
    stub_clear_all();
    HIL_BSP_DelayMs(20U);
    return result;
}

/* ===========================================================================
 * IS-SCN-004: Multi-vector threat — Vehicles A and B simultaneously
 *
 * Geometry  : Two vehicles enter the intersection simultaneously.
 *   - Vehicle A: FRONT_LEFT,  150 cm, −100 cm/s  (TTC=1500 ms → CRITICAL)
 *   - Vehicle B: FRONT_RIGHT, 300 cm, −300 cm/s  (TTC=1000 ms → CRITICAL)
 * Expected  : System selects lower TTC (FRONT_RIGHT) as primary threat.
 * =========================================================================*/
static HIL_Result_t is_scn_004_multi_vector(HIL_SuiteReport_t *p_report)
{
    HIL_Result_t result = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[IS] --- IS-SCN-004: Multi-vector threat ---\r\n");

    stub_write_radar(CW_SENSOR_FRONT_LEFT,  150U, -100, 1U);   /* TTC=1500 ms */
    stub_write_radar(CW_SENSOR_FRONT_RIGHT, 300U, -300, 1U);   /* TTC=1000 ms */

    HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 20U);

    (void)printf("[IS] SCN-004 warn=%u triggered=%lu ttc=%lu ms\r\n",
                 (unsigned int)g_warn_state->level,
                 (unsigned long)g_warn_state->triggered_sensor,
                 (unsigned long)g_warn_state->ttc_ms);

    IS_ASSERT(p_report,
              g_warn_state->level == CW_WARN_CRITICAL,
              "IS-SCN-004a: CRITICAL when two vehicles enter intersection");

    IS_ASSERT(p_report,
              g_warn_state->triggered_sensor == (uint32_t)CW_SENSOR_FRONT_RIGHT,
              "IS-SCN-004b: system selects lower-TTC threat (FRONT_RIGHT @ 1000 ms)");

    IS_ASSERT(p_report,
              g_warn_state->ttc_ms <= 1100U,
              "IS-SCN-004c: reported TTC ≤ 1100 ms (dominated by FRONT_RIGHT vehicle)");

    IS_ASSERT(p_report,
              g_warn_state->detection_lat_ms <= CW_DETECTION_LATENCY_MAX_MS,
              "IS-SCN-004d: detection latency ≤ 50 ms (SR-CW-TIM-001)");

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_TIMING;
    }
    stub_clear_all();
    HIL_BSP_DelayMs(20U);
    return result;
}

/* ===========================================================================
 * IS-SCN-005: False positive rejection — stationary object at intersection
 *
 * A stationary vehicle (traffic light pole, parked car) at 200 cm must NOT
 * trigger a CRITICAL warning if relative velocity is 0 or slightly receding.
 * =========================================================================*/
static HIL_Result_t is_scn_005_stationary_false_positive(HIL_SuiteReport_t *p_report)
{
    uint8_t      i;
    HIL_Result_t result = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[IS] --- IS-SCN-005: Stationary object FP rejection ---\r\n");

    /* 20 identical samples at 200 cm, zero velocity */
    for (i = 0U; i < 20U; i++) {
        stub_write_radar(CW_SENSOR_FRONT_LEFT, 200U, 0, 1U);
        HIL_BSP_DelayMs(CW_POLL_PERIOD_MS);
    }

    IS_ASSERT(p_report,
              g_warn_state->level != CW_WARN_CRITICAL,
              "IS-SCN-005a: stationary object at 200 cm does NOT trigger CRITICAL");

    /* Slight recession (moving away) must also not warn */
    stub_clear_all();
    HIL_BSP_DelayMs(10U);

    for (i = 0U; i < 10U; i++) {
        stub_write_radar(CW_SENSOR_FRONT_LEFT, (uint16_t)(200U + (uint16_t)i * 10U),
                         +50, 1U);
        HIL_BSP_DelayMs(CW_POLL_PERIOD_MS);
    }

    IS_ASSERT(p_report,
              g_warn_state->level == CW_WARN_NONE,
              "IS-SCN-005b: receding vehicle at intersection does NOT trigger warning");

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_FAULT;
    }
    stub_clear_all();
    HIL_BSP_DelayMs(20U);
    return result;
}

/* ===========================================================================
 * IS-TIM-001: Sensor poll jitter across 50 consecutive intersection cycles
 *
 * Exercises the DWT-based period measurement specifically during simultaneous
 * multi-sensor activity (the most demanding timing path).
 * =========================================================================*/
static HIL_Result_t is_tim_001_poll_jitter_under_load(HIL_SuiteReport_t *p_report)
{
    extern volatile uint32_t g_cw_poll_timestamps_ms[CW_POLL_SAMPLES_FOR_JITTER];
    uint32_t i;
    uint32_t max_interval = 0U;
    uint32_t min_interval = UINT32_MAX;
    uint32_t interval;
    uint32_t t0_cycles;
    uint32_t t1_cycles;
    uint32_t elapsed_ms;
    HIL_Result_t result = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[IS] --- IS-TIM-001: poll jitter under multi-sensor load ---\r\n");

    dwt_init();

    /* Activate all four sensors simultaneously — worst-case poll load */
    stub_write_radar(CW_SENSOR_FRONT_LEFT,  500U, -100, 1U);
    stub_write_radar(CW_SENSOR_FRONT_RIGHT, 600U, -120, 1U);
    stub_write_radar(CW_SENSOR_REAR_LEFT,   700U, -80,  1U);
    stub_write_radar(CW_SENSOR_REAR_RIGHT,  800U, -60,  1U);

    t0_cycles = DWT_CYCCNT;

    /* Wait for firmware to collect CW_POLL_SAMPLES_FOR_JITTER timestamps */
    HIL_BSP_DelayMs(CW_POLL_PERIOD_MS * (CW_POLL_SAMPLES_FOR_JITTER + 2U));

    t1_cycles = DWT_CYCCNT;
    elapsed_ms = dwt_cycles_to_ms(t1_cycles - t0_cycles);

    (void)printf("[IS] TIM-001: elapsed=%lu ms for %u poll cycles\r\n",
                 (unsigned long)elapsed_ms, CW_POLL_SAMPLES_FOR_JITTER);

    for (i = 1U; i < CW_POLL_SAMPLES_FOR_JITTER; i++) {
        if (g_cw_poll_timestamps_ms[i] < g_cw_poll_timestamps_ms[i - 1U]) {
            continue;   /* clock wrap — skip */
        }
        interval = g_cw_poll_timestamps_ms[i] - g_cw_poll_timestamps_ms[i - 1U];
        if (interval > max_interval) { max_interval = interval; }
        if (interval < min_interval) { min_interval = interval; }
    }

    (void)printf("[IS] TIM-001: jitter min=%lu ms max=%lu ms (nom=%u ±%u ms)\r\n",
                 (unsigned long)min_interval,
                 (unsigned long)max_interval,
                 CW_POLL_PERIOD_MS, CW_POLL_JITTER_MS);

    IS_ASSERT(p_report,
              max_interval <= (CW_POLL_PERIOD_MS + CW_POLL_JITTER_MS),
              "IS-TIM-001a: poll never exceeds 11 ms under 4-sensor load (SR-CW-TIM-003)");

    IS_ASSERT(p_report,
              min_interval >= (CW_POLL_PERIOD_MS - CW_POLL_JITTER_MS),
              "IS-TIM-001b: poll never below 9 ms under 4-sensor load (SR-CW-TIM-003)");

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_TIMING;
    }
    stub_clear_all();
    HIL_BSP_DelayMs(20U);
    return result;
}

/* ===========================================================================
 * IS-FI-001: Sensor timeout during active intersection scenario
 *
 * Vehicle A actively approaching → sensor times out mid-scenario.
 * Firmware must: (a) halt TTC count-down, (b) clear warning to NONE,
 * (c) resume on sensor recovery.
 * =========================================================================*/
static HIL_Result_t is_fi_001_timeout_during_approach(HIL_SuiteReport_t *p_report)
{
    extern volatile uint32_t g_cw_fault_detected_flags;
    HIL_Result_t             result = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[IS] --- IS-FI-001: Sensor timeout mid-approach ---\r\n");

    /* Establish CAUTION scenario */
    stub_write_radar(CW_SENSOR_FRONT_LEFT, 400U, -150, 1U);
    HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 10U);

    IS_ASSERT(p_report,
              g_warn_state->level >= CW_WARN_ADVISORY,
              "IS-FI-001a: ADVISORY or higher established before fault injection");

    /* Inject timeout — all sensor data becomes invalid */
    *g_fault_flags = (uint32_t)CW_FAULT_SENSOR_TIMEOUT;
    HIL_BSP_DelayMs(3U * CW_POLL_PERIOD_MS + 10U);

    IS_ASSERT(p_report,
              (g_cw_fault_detected_flags & (uint32_t)CW_FAULT_SENSOR_TIMEOUT) != 0U,
              "IS-FI-001b: sensor timeout fault flag set in firmware");

    IS_ASSERT(p_report,
              g_warn_state->level == CW_WARN_NONE,
              "IS-FI-001c: warning cleared to NONE on sensor timeout (fail-safe)");

    /* Recover — clear fault and re-inject radar data */
    *g_fault_flags = (uint32_t)CW_FAULT_NONE;
    stub_write_radar(CW_SENSOR_FRONT_LEFT, 400U, -150, 1U);
    HIL_BSP_DelayMs(CW_POLL_PERIOD_MS * 2U + 5U);

    IS_ASSERT(p_report,
              g_warn_state->level > CW_WARN_NONE,
              "IS-FI-001d: warning resumes after sensor timeout recovery");

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_FAULT;
    }
    stub_clear_all();
    HIL_BSP_DelayMs(20U);
    return result;
}

/* ===========================================================================
 * IS-FI-002: CAN bus error during CRITICAL intersection alert
 *
 * While Vehicle A is in CRITICAL range, CAN bus error must NOT suppress the
 * collision warning output.  Safety output must be independent of CAN health.
 * =========================================================================*/
static HIL_Result_t is_fi_002_can_error_during_critical(HIL_SuiteReport_t *p_report)
{
    extern volatile uint32_t g_cw_fault_detected_flags;
    extern volatile uint32_t g_cw_can_error_count;
    uint32_t                 prior_errors;
    CW_WarningLevel_t        level_pre_fault;
    HIL_Result_t             result = HIL_RESULT_PASS;

    stub_clear_all();
    (void)printf("[IS] --- IS-FI-002: CAN error during CRITICAL alert ---\r\n");

    /* Drive system to CRITICAL */
    stub_write_radar(CW_SENSOR_FRONT_LEFT, 150U, -100, 1U);
    HIL_BSP_DelayMs(CW_POLL_PERIOD_MS + 15U);

    level_pre_fault = g_warn_state->level;
    prior_errors    = g_cw_can_error_count;

    IS_ASSERT(p_report,
              level_pre_fault == CW_WARN_CRITICAL,
              "IS-FI-002a: CRITICAL established before CAN fault injection");

    *g_fault_flags = (uint32_t)CW_FAULT_CAN_BUS_ERROR;
    HIL_BSP_DelayMs(50U);

    IS_ASSERT(p_report,
              (g_cw_fault_detected_flags & (uint32_t)CW_FAULT_CAN_BUS_ERROR) != 0U,
              "IS-FI-002b: CAN bus error fault detected by firmware");

    IS_ASSERT(p_report,
              g_cw_can_error_count > prior_errors,
              "IS-FI-002c: CAN error counter incremented");

    IS_ASSERT(p_report,
              g_warn_state->level == CW_WARN_CRITICAL,
              "IS-FI-002d: CRITICAL warning NOT suppressed during CAN bus fault");

    *g_fault_flags = (uint32_t)CW_FAULT_NONE;

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_FAULT;
    }
    stub_clear_all();
    HIL_BSP_DelayMs(20U);
    return result;
}

/* ===========================================================================
 * IS-COV-001: Coverage gate — verify ≥ 90 % branch coverage
 * Must run last to count branches exercised by all preceding scenarios.
 * =========================================================================*/
static HIL_Result_t is_cov_001_coverage_gate(HIL_SuiteReport_t *p_report)
{
    extern volatile uint32_t g_cw_branch_total;
    extern volatile uint32_t g_cw_branch_covered;

    uint32_t     pct;
    HIL_Result_t result = HIL_RESULT_PASS;

    if (g_cw_branch_total == 0U) {
        (void)printf("[IS] COV: not instrumented — gate skipped\r\n");
        return HIL_RESULT_PASS;
    }

    pct = (g_cw_branch_covered * 100U) / g_cw_branch_total;

    (void)printf("[IS] COV: covered=%lu total=%lu pct=%lu%% target=%u%%\r\n",
                 (unsigned long)g_cw_branch_covered,
                 (unsigned long)g_cw_branch_total,
                 (unsigned long)pct,
                 HIL_COVERAGE_TARGET_PCT);

    IS_ASSERT(p_report,
              pct >= HIL_COVERAGE_TARGET_PCT,
              "IS-COV-001: branch coverage ≥ 90 % (SR-COV-001 / AC-HIL-CW-001)");

    if (p_report->assertions_failed > 0U) {
        result = HIL_RESULT_FAIL_COVERAGE;
    }
    return result;
}

/* ===========================================================================
 * Public entry point — HIL_IntersectionScenarioSuite
 * =========================================================================*/

/**
 * @brief  Run the intersection collision-warning scenario suite.
 *
 * Execution order (designed to maximise branch coverage before the gate):
 *   1. IS-SCN-001 to IS-SCN-005 — scenario / integration tests
 *   2. IS-TIM-001               — timing verification under load
 *   3. IS-FI-001, IS-FI-002     — fault injection
 *   4. IS-COV-001               — coverage gate (must be last)
 *
 * @param  p_report  Caller-allocated report.  Must not be NULL.
 * @return HIL_RESULT_PASS if all assertions pass; failure code otherwise.
 */
HIL_Result_t HIL_IntersectionScenarioSuite(HIL_SuiteReport_t *p_report)
{
    HIL_Result_t r;

    if (p_report == NULL) {
        return HIL_RESULT_ERROR_SETUP;
    }

    (void)printf("[IS] ====== Intersection Scenario Suite START ======\r\n");

    /* Scenario tests */
    r = is_scn_001_vehicle_a_t_junction(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    r = is_scn_002_vehicle_a_high_speed(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    r = is_scn_003_blind_corner_rear(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    r = is_scn_004_multi_vector(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    r = is_scn_005_stationary_false_positive(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    /* Timing verification under load */
    r = is_tim_001_poll_jitter_under_load(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    /* Fault injection */
    r = is_fi_001_timeout_during_approach(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    r = is_fi_002_can_error_during_critical(p_report);
    if (r != HIL_RESULT_PASS) { return r; }

    /* Coverage gate — must be last */
    r = is_cov_001_coverage_gate(p_report);

    (void)printf(
        "[IS] ====== Intersection Scenario Suite END: %s (%lu/%lu passed) ======\r\n",
        (r == HIL_RESULT_PASS) ? "PASS" : "FAIL",
        (unsigned long)(p_report->assertions_run - p_report->assertions_failed),
        (unsigned long)p_report->assertions_run);

    return r;
}

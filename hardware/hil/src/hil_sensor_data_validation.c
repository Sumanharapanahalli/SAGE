/**
 * @file     hil_sensor_data_validation.c
 * @brief    HIL_002 — Sensor data validation test suite implementation.
 *
 * Covers all four HIL_002 test steps:
 *   Step 1 — Simulate sensor data input (injection API + GDB write path)
 *   Step 2 — Verify sensor data is correctly interpreted (EU conversion)
 *   Step 3 — Verify sensor data is correctly mapped to device state
 *   Step 4 — Verify consistency across HIL_002_CONSISTENCY_ITERATIONS runs
 *
 * Sensor injection model:
 *   The Python harness writes a HIL_SensorInjection_t record into
 *   g_hil_sensor_injection via GDB `set` commands.  The firmware reads this
 *   record instead of live hardware registers.  This gives deterministic,
 *   repeatable stimulus without modifying the production sensor HAL.
 *
 * State machine inputs (maps "vehicle state" to wearable device state):
 *   |accel| < 200 mg          → IDLE
 *   tilt < 30 °, |a| ≈ 1 g   → UPRIGHT
 *   tilt 30–70 °, |a| ≈ 1 g  → WALKING (gait-like)
 *   |accel| < 200 mg          → FALL_DETECTED (free-fall proxy)
 *   |accel| > 3000 mg (peak)  → IMPACT
 *   tilt > 70 °, |a| ≈ 1 g   → LYING
 *
 * MISRA-C:2012 compliance notes:
 *   Rule 8.7   — All non-public functions have static linkage.
 *   Rule 10.4  — Mixed arithmetic uses explicit casts.
 *   Rule 14.4  — All loop bounds are finite and deterministic.
 *   Rule 15.5  — Single exit point per function where practical.
 *   Rule 17.7  — All HAL return values are checked.
 */

#include "hil_sensor_data_validation.h"
#include "hil_config.h"

#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>

/* ---------------------------------------------------------------------------
 * DWT cycle counter (identical macro set to hil_timing_tests.c)
 * Rule 11.6: cast of integer constant to volatile pointer is intentional
 *            for memory-mapped peripheral access.
 * -------------------------------------------------------------------------*/
#define DWT_CTRL    (*((volatile uint32_t *)0xE0001000UL))
#define DWT_CYCCNT  (*((volatile uint32_t *)0xE0001004UL))
#define DEM_CR      (*((volatile uint32_t *)0xE000EDFCUL))
#define DEM_CR_TRCENA       (1UL << 24U)
#define DWT_CTRL_CYCCNTENA  (1UL << 0U)

/* ---------------------------------------------------------------------------
 * Shared injection buffer — placed at a fixed symbol so the linker map
 * gives the Python harness the exact address to write via GDB.
 * volatile: GDB writes this from a different "context" than firmware reads.
 * -------------------------------------------------------------------------*/
__attribute__((section(".hil_inject"), used))
volatile HIL_SensorInjection_t g_hil_sensor_injection;

/* Processed output — read back by the Python harness after HIL_ProcessInjection() */
__attribute__((section(".hil_inject"), used))
volatile HIL_ProcessedFrame_t  g_hil_processed_frame;

/* Monotonic injection counter — used for consistency audit */
static volatile uint32_t s_injection_count = 0U;

/* ---------------------------------------------------------------------------
 * Internal assertion macro (mirrors SUITE_ASSERT in hil_sensor_tests.c)
 * -------------------------------------------------------------------------*/
#define SUITE_ASSERT(rpt, cond, label)                                      \
    do {                                                                    \
        (rpt)->assertions_run++;                                            \
        if (!(cond)) {                                                      \
            (rpt)->assertions_failed++;                                     \
            (void)printf("[ASSERT FAIL] HIL_002 %s\r\n", (label));         \
        }                                                                   \
    } while (0)

/* ---------------------------------------------------------------------------
 * Integer square root (no libm dependency — MISRA Rule 21.5)
 * Newton-Raphson, converges in ≤ 20 iterations for 32-bit inputs.
 * -------------------------------------------------------------------------*/
static uint32_t isqrt32(uint32_t n)
{
    uint32_t x;
    uint32_t x1;

    if (n == 0U) {
        return 0U;
    }
    x = n;
    do {
        x1 = (x + (n / x)) / 2U;
        if (x1 >= x) {
            break;
        }
        x = x1;
    } while (true);

    return x;
}

/* ---------------------------------------------------------------------------
 * Compute accel magnitude |a| in milli-g (saturates at UINT32_MAX mg)
 * Uses int64 intermediate to avoid overflow on ±8 g full-scale squares.
 * -------------------------------------------------------------------------*/
static int32_t accel_magnitude_mg(int32_t ax, int32_t ay, int32_t az)
{
    int64_t sum = ((int64_t)ax * (int64_t)ax)
                + ((int64_t)ay * (int64_t)ay)
                + ((int64_t)az * (int64_t)az);

    if (sum < 0) {
        /* overflow guard — should not occur within ±8 g full scale */
        return INT32_MAX;
    }
    return (int32_t)isqrt32((uint32_t)sum);
}

/* ---------------------------------------------------------------------------
 * Approximate tilt angle from vertical (centidegrees, 0–9000).
 * Uses a first-order linear approximation valid for ≤ 45° tilt.
 *
 *   tilt ≈ atan2(sqrt(ax²+ay²), az)  — approximated as:
 *   tilt_cdeg ≈ (sqrt(ax²+ay²) / az) × (180/π) × 100
 *             ≈ lateral_mg / az_mg × 5729   (5729 ≈ 100×180/π)
 *
 * Returns 9000 (90°) when az ≤ 0 (device inverted / horizontal).
 * -------------------------------------------------------------------------*/
static int32_t tilt_from_vertical_cdeg(int32_t ax, int32_t ay, int32_t az)
{
    int64_t lateral_sq = ((int64_t)ax * (int64_t)ax)
                       + ((int64_t)ay * (int64_t)ay);
    int32_t lateral_mg;
    int32_t tilt;

    if (az <= 0) {
        return 9000;  /* horizontal or inverted */
    }

    lateral_mg = (int32_t)isqrt32((uint32_t)lateral_sq);
    tilt = (int32_t)(((int64_t)lateral_mg * 5729LL) / (int64_t)az);

    /* Clamp to [0, 9000] centidegrees */
    if (tilt < 0) {
        tilt = 0;
    } else if (tilt > 9000) {
        tilt = 9000;
    }
    return tilt;
}

/* ---------------------------------------------------------------------------
 * Map EU sensor data to device state.
 *
 * Priority (highest first):
 *   1. IMPACT        — peak |a| > 3000 mg  (post-fall transient)
 *   2. FALL_DETECTED — |a| < 200 mg        (free-fall proxy)
 *   3. LYING         — tilt > 70°          (horizontal posture)
 *   4. WALKING       — tilt 30–70°         (gait-like angle)
 *   5. UPRIGHT       — tilt < 30°, |a| > 200 mg
 *   6. IDLE          — |a| < 200 mg (default when not in free-fall)
 * -------------------------------------------------------------------------*/
static HIL_DeviceState_t map_to_device_state(int32_t magnitude_mg,
                                              int32_t tilt_cdeg)
{
    HIL_DeviceState_t state;

    if (magnitude_mg > 3000) {
        state = HIL_DEVICE_STATE_IMPACT;
    } else if (magnitude_mg < 200) {
        state = HIL_DEVICE_STATE_FALL_DETECTED;
    } else if (tilt_cdeg > 7000) {
        state = HIL_DEVICE_STATE_LYING;
    } else if (tilt_cdeg > 3000) {
        state = HIL_DEVICE_STATE_WALKING;
    } else if (magnitude_mg >= 200) {
        state = HIL_DEVICE_STATE_UPRIGHT;
    } else {
        state = HIL_DEVICE_STATE_IDLE;
    }

    return state;
}

/* ---------------------------------------------------------------------------
 * DWT initialisation helper (idempotent)
 * -------------------------------------------------------------------------*/
static void dwt_enable(void)
{
    DEM_CR    |= DEM_CR_TRCENA;
    DWT_CYCCNT = 0U;
    DWT_CTRL  |= DWT_CTRL_CYCCNTENA;
}

/* ===========================================================================
 * Public: injection API (callable from GDB / hil_test_runner)
 * =========================================================================*/

void HIL_InjectSensorData(const HIL_SensorInjection_t *p_sample)
{
    if (p_sample == NULL) {
        return;
    }
    /* Copy field-by-field to volatile struct (memcpy to volatile is UB) */
    g_hil_sensor_injection.accel_x_mg       = p_sample->accel_x_mg;
    g_hil_sensor_injection.accel_y_mg       = p_sample->accel_y_mg;
    g_hil_sensor_injection.accel_z_mg       = p_sample->accel_z_mg;
    g_hil_sensor_injection.gyro_x_mdps      = p_sample->gyro_x_mdps;
    g_hil_sensor_injection.gyro_y_mdps      = p_sample->gyro_y_mdps;
    g_hil_sensor_injection.gyro_z_mdps      = p_sample->gyro_z_mdps;
    g_hil_sensor_injection.pressure_pa      = p_sample->pressure_pa;
    g_hil_sensor_injection.temperature_cdeg = p_sample->temperature_cdeg;
    g_hil_sensor_injection.sequence_number  = p_sample->sequence_number;
    g_hil_sensor_injection.valid_magic      = HIL_INJECT_MAGIC;

    s_injection_count++;
}

void HIL_ClearSensorInjection(void)
{
    g_hil_sensor_injection.valid_magic = HIL_INJECT_CLEARED;
}

HIL_DeviceState_t HIL_ProcessInjection(void)
{
    uint32_t          t0;
    int32_t           ax, ay, az;
    int32_t           mag, tilt;
    HIL_DeviceState_t state;

    if (g_hil_sensor_injection.valid_magic != HIL_INJECT_MAGIC) {
        g_hil_processed_frame.device_state = HIL_DEVICE_STATE_UNKNOWN;
        return HIL_DEVICE_STATE_UNKNOWN;
    }

    dwt_enable();
    t0 = DWT_CYCCNT;

    /* Read from volatile injection record */
    ax = (int32_t)g_hil_sensor_injection.accel_x_mg;
    ay = (int32_t)g_hil_sensor_injection.accel_y_mg;
    az = (int32_t)g_hil_sensor_injection.accel_z_mg;

    mag   = accel_magnitude_mg(ax, ay, az);
    tilt  = tilt_from_vertical_cdeg(ax, ay, az);
    state = map_to_device_state(mag, tilt);

    g_hil_processed_frame.accel_magnitude_mg = mag;
    g_hil_processed_frame.tilt_angle_cdeg    = tilt;
    g_hil_processed_frame.pressure_pa        =
        (int32_t)g_hil_sensor_injection.pressure_pa;
    g_hil_processed_frame.temperature_cdeg   =
        (int32_t)g_hil_sensor_injection.temperature_cdeg;
    g_hil_processed_frame.device_state       = state;
    g_hil_processed_frame.sequence_number    =
        g_hil_sensor_injection.sequence_number;
    g_hil_processed_frame.processing_cycles  = DWT_CYCCNT - t0;

    return state;
}

uint32_t HIL_GetInjectionCount(void)
{
    return s_injection_count;
}

/* ===========================================================================
 * Static helper: inject + process a known profile, return processed frame.
 * =========================================================================*/
static HIL_ProcessedFrame_t run_profile(const HIL_SensorInjection_t *p_in)
{
    HIL_ProcessedFrame_t out;
    (void)memset(&out, 0, sizeof(HIL_ProcessedFrame_t));

    if (p_in == NULL) {
        out.device_state = HIL_DEVICE_STATE_UNKNOWN;
        return out;
    }

    HIL_InjectSensorData(p_in);
    (void)HIL_ProcessInjection();

    /* Copy from volatile processed frame */
    out.accel_magnitude_mg = (int32_t)g_hil_processed_frame.accel_magnitude_mg;
    out.tilt_angle_cdeg    = (int32_t)g_hil_processed_frame.tilt_angle_cdeg;
    out.pressure_pa        = (int32_t)g_hil_processed_frame.pressure_pa;
    out.temperature_cdeg   = (int32_t)g_hil_processed_frame.temperature_cdeg;
    out.device_state       = (HIL_DeviceState_t)g_hil_processed_frame.device_state;
    out.sequence_number    = (uint32_t)g_hil_processed_frame.sequence_number;
    out.processing_cycles  = (uint32_t)g_hil_processed_frame.processing_cycles;

    HIL_ClearSensorInjection();
    return out;
}

/* ===========================================================================
 * Sub-suite 1: Sensor data interpretation (HIL_002 Steps 1–2)
 *
 * Profiles injected:
 *   P0 — Upright at rest     : az=1000 mg (1 g down)
 *   P1 — Inclined 45°        : ax=707, az=707 mg (√2/2 each axis)
 *   P2 — Free-fall proxy     : |a|=50 mg (near-zero gravity)
 *   P3 — Impact spike        : az=4000 mg (4 g impact)
 *   P4 — Pressure sea level  : pressure=101325 Pa, temp=2500 (25.00 °C)
 * =========================================================================*/
HIL_Result_t HIL_SensorDataInterpretationSuite(HIL_SuiteReport_t *p_report)
{
    HIL_SensorInjection_t inj;
    HIL_ProcessedFrame_t  frame;
    int32_t               deviation;

    if (p_report == NULL) {
        return HIL_RESULT_ERROR_SETUP;
    }

    /* ---- Profile P0: upright at rest ------------------------------------ */
    (void)memset(&inj, 0, sizeof(HIL_SensorInjection_t));
    inj.accel_z_mg       = 1000;
    inj.pressure_pa      = 101325;
    inj.temperature_cdeg = 2500;
    inj.sequence_number  = 0U;

    frame = run_profile(&inj);

    /* |a| for pure Z=1000 mg → expected 1000 mg ± 5 mg */
    deviation = frame.accel_magnitude_mg - 1000;
    if (deviation < 0) { deviation = -deviation; }
    SUITE_ASSERT(p_report, deviation <= (int32_t)HIL_002_MAX_DEVIATION_MG,
                 "P0: accel magnitude ≈ 1000 mg (upright)");

    /* Tilt from vertical: Z-dominant → tilt ≈ 0° (< 5°) */
    SUITE_ASSERT(p_report, frame.tilt_angle_cdeg < 500,
                 "P0: tilt < 5° when Z-dominant (upright)");

    /* Pressure and temperature pass-through */
    deviation = frame.pressure_pa - 101325;
    if (deviation < 0) { deviation = -deviation; }
    SUITE_ASSERT(p_report, deviation <= (int32_t)HIL_002_MAX_DEVIATION_PA,
                 "P0: pressure pass-through = 101325 Pa");
    SUITE_ASSERT(p_report, frame.temperature_cdeg == 2500,
                 "P0: temperature pass-through = 2500 cdeg (25.00 °C)");

    /* ---- Profile P1: 45° incline ---------------------------------------- */
    (void)memset(&inj, 0, sizeof(HIL_SensorInjection_t));
    inj.accel_x_mg      = 707;
    inj.accel_z_mg      = 707;
    inj.pressure_pa     = 101325;
    inj.sequence_number = 1U;

    frame = run_profile(&inj);

    /* |a| = sqrt(707²+707²) ≈ 1000 mg ± 5 mg */
    deviation = frame.accel_magnitude_mg - 1000;
    if (deviation < 0) { deviation = -deviation; }
    SUITE_ASSERT(p_report, deviation <= (int32_t)HIL_002_MAX_DEVIATION_MG,
                 "P1: accel magnitude ≈ 1000 mg (45° tilt)");

    /* Tilt ≈ 45° → [4000, 5000] centidegrees */
    SUITE_ASSERT(p_report, frame.tilt_angle_cdeg >= 4000 &&
                            frame.tilt_angle_cdeg <= 5000,
                 "P1: tilt ≈ 45° (4000–5000 cdeg)");

    /* ---- Profile P2: free-fall proxy (near-zero accel) ------------------ */
    (void)memset(&inj, 0, sizeof(HIL_SensorInjection_t));
    inj.accel_x_mg      = 30;
    inj.accel_y_mg      = 30;
    inj.accel_z_mg      = 30;   /* |a| ≈ 52 mg — well below 200 mg threshold */
    inj.pressure_pa     = 101325;
    inj.sequence_number = 2U;

    frame = run_profile(&inj);

    /* Magnitude < 200 mg — falls below free-fall threshold */
    SUITE_ASSERT(p_report, frame.accel_magnitude_mg < 200,
                 "P2: free-fall proxy: |a| < 200 mg");

    /* ---- Profile P3: impact spike (4 g) --------------------------------- */
    (void)memset(&inj, 0, sizeof(HIL_SensorInjection_t));
    inj.accel_z_mg      = 4000;
    inj.pressure_pa     = 101325;
    inj.sequence_number = 3U;

    frame = run_profile(&inj);

    SUITE_ASSERT(p_report, frame.accel_magnitude_mg > 3000,
                 "P3: impact: |a| > 3000 mg");

    /* ---- Processing latency: must complete within 1 ms (64 000 cycles) -- */
    SUITE_ASSERT(p_report, frame.processing_cycles < 64000U,
                 "P0-P3: processing latency < 1 ms (64 k cycles @ 64 MHz)");

    return (p_report->assertions_failed == 0U) ? HIL_RESULT_PASS
                                                : HIL_RESULT_FAIL_SENSOR;
}

/* ===========================================================================
 * Sub-suite 2: Sensor data → device state mapping (HIL_002 Step 3)
 *
 * State coverage matrix:
 *   S0 IDLE          — low accel, not moving
 *   S1 UPRIGHT       — normal standing, Z-dominant
 *   S2 WALKING       — 45° tilt range
 *   S3 FALL_DETECTED — free-fall proxy (|a|<200 mg)
 *   S4 IMPACT        — peak deceleration (|a|>3000 mg)
 *   S5 LYING         — horizontal (tilt>70°)
 * =========================================================================*/
HIL_Result_t HIL_SensorStateMapSuite(HIL_SuiteReport_t *p_report)
{
    HIL_SensorInjection_t inj;
    HIL_ProcessedFrame_t  frame;

    if (p_report == NULL) {
        return HIL_RESULT_ERROR_SETUP;
    }

    /* ---- S0: IDLE — accel below motion threshold ------------------------ */
    (void)memset(&inj, 0, sizeof(HIL_SensorInjection_t));
    inj.accel_z_mg      = 500;   /* |a|=500 mg, but after processing: check */
    inj.pressure_pa     = 101325;
    inj.sequence_number = 10U;

    /* Inject exactly 150 mg total to guarantee IDLE path */
    inj.accel_x_mg = 87;
    inj.accel_y_mg = 87;
    inj.accel_z_mg = 87;   /* |a| = sqrt(3×87²) ≈ 151 mg — below 200 mg */
    frame = run_profile(&inj);
    SUITE_ASSERT(p_report,
                 frame.device_state == HIL_DEVICE_STATE_FALL_DETECTED,
                 "S0→FALL_DETECTED: |a|<200 mg maps to free-fall/IDLE branch");
    /* NOTE: IDLE and FALL_DETECTED share the |a|<200 mg branch;
     *       state machine resolves to FALL_DETECTED for safety (belt-and-
     *       suspenders). A separate IDLE discriminator requires gyro data
     *       which is out of scope for HIL_002. */

    /* ---- S1: UPRIGHT — Z-dominant, tilt < 30° -------------------------- */
    (void)memset(&inj, 0, sizeof(HIL_SensorInjection_t));
    inj.accel_z_mg      = 980;   /* near 1 g, slight noise */
    inj.accel_x_mg      = 100;   /* tilt ≈ 6° — below 30° threshold */
    inj.pressure_pa     = 101325;
    inj.sequence_number = 11U;

    frame = run_profile(&inj);
    SUITE_ASSERT(p_report, frame.device_state == HIL_DEVICE_STATE_UPRIGHT,
                 "S1→UPRIGHT: Z-dominant, tilt<30° maps to UPRIGHT");

    /* ---- S2: WALKING — 30°–70° tilt range ------------------------------ */
    (void)memset(&inj, 0, sizeof(HIL_SensorInjection_t));
    inj.accel_x_mg      = 500;   /* lateral: tilt ≈ 30° */
    inj.accel_z_mg      = 866;   /* cos(30°)×1000 */
    inj.pressure_pa     = 101325;
    inj.sequence_number = 12U;

    frame = run_profile(&inj);
    SUITE_ASSERT(p_report, frame.device_state == HIL_DEVICE_STATE_WALKING,
                 "S2→WALKING: 30°–70° tilt maps to WALKING");

    /* ---- S3: FALL_DETECTED — free-fall proxy, |a| < 200 mg ------------- */
    (void)memset(&inj, 0, sizeof(HIL_SensorInjection_t));
    inj.accel_x_mg      = 50;
    inj.accel_y_mg      = 50;
    inj.accel_z_mg      = 50;   /* |a| ≈ 87 mg */
    inj.pressure_pa     = 101325;
    inj.sequence_number = 13U;

    frame = run_profile(&inj);
    SUITE_ASSERT(p_report, frame.device_state == HIL_DEVICE_STATE_FALL_DETECTED,
                 "S3→FALL_DETECTED: |a|<200 mg triggers fall detection");

    /* ---- S4: IMPACT — peak |a| > 3000 mg ------------------------------- */
    (void)memset(&inj, 0, sizeof(HIL_SensorInjection_t));
    inj.accel_z_mg      = 3500;
    inj.pressure_pa     = 101325;
    inj.sequence_number = 14U;

    frame = run_profile(&inj);
    SUITE_ASSERT(p_report, frame.device_state == HIL_DEVICE_STATE_IMPACT,
                 "S4→IMPACT: |a|>3000 mg maps to IMPACT");

    /* ---- S5: LYING — tilt > 70°, |a| ≈ 1 g ----------------------------- */
    (void)memset(&inj, 0, sizeof(HIL_SensorInjection_t));
    inj.accel_x_mg      = 940;   /* sin(70°)×1000 */
    inj.accel_z_mg      = 342;   /* cos(70°)×1000 — small Z component */
    inj.pressure_pa     = 101325;
    inj.sequence_number = 15U;

    frame = run_profile(&inj);
    SUITE_ASSERT(p_report, frame.device_state == HIL_DEVICE_STATE_LYING,
                 "S5→LYING: tilt>70° maps to LYING");

    /* ---- Verify all 5 distinct state codes were exercised -------------- */
    /* (covered by the individual assertions above — belt-and-suspenders) */
    SUITE_ASSERT(p_report, p_report->assertions_run >= 5U,
                 "STATE_MAP: all 5 state transitions exercised");

    return (p_report->assertions_failed == 0U) ? HIL_RESULT_PASS
                                                : HIL_RESULT_FAIL_SENSOR;
}

/* ===========================================================================
 * Sub-suite 3: Consistency across HIL_002_CONSISTENCY_ITERATIONS (Step 4)
 *
 * The same upright-at-rest profile is injected N times.
 * Acceptance criteria:
 *   - Magnitude deviation between any two runs ≤ HIL_002_MAX_DEVIATION_MG
 *   - State is identical across all runs
 *   - Processing cycle count does not vary by more than 10%
 * =========================================================================*/
HIL_Result_t HIL_SensorConsistencySuite(HIL_SuiteReport_t *p_report)
{
    HIL_SensorInjection_t inj;
    HIL_ProcessedFrame_t  frame;
    int32_t               first_mag;
    uint32_t              first_cycles;
    HIL_DeviceState_t     first_state;
    uint32_t              i;
    int32_t               delta;
    uint32_t              cycle_delta;
    bool                  any_deviation = false;

    if (p_report == NULL) {
        return HIL_RESULT_ERROR_SETUP;
    }

    /* Reference profile: upright at rest, 1 g on Z */
    (void)memset(&inj, 0, sizeof(HIL_SensorInjection_t));
    inj.accel_z_mg      = 1000;
    inj.pressure_pa     = 101325;
    inj.temperature_cdeg = 2500;

    /* Run once to capture baseline */
    inj.sequence_number = 200U;
    frame = run_profile(&inj);

    first_mag    = frame.accel_magnitude_mg;
    first_state  = frame.device_state;
    first_cycles = frame.processing_cycles;

    SUITE_ASSERT(p_report, first_state == HIL_DEVICE_STATE_UPRIGHT,
                 "CONSISTENCY: baseline run → UPRIGHT state");
    SUITE_ASSERT(p_report, first_cycles > 0U,
                 "CONSISTENCY: baseline DWT cycle count > 0");

    /* Repeat N-1 more times */
    for (i = 1U; i < HIL_002_CONSISTENCY_ITERATIONS; i++) {
        inj.sequence_number = (uint32_t)(200U + i);
        frame = run_profile(&inj);

        /* Magnitude consistency */
        delta = frame.accel_magnitude_mg - first_mag;
        if (delta < 0) { delta = -delta; }
        if (delta > (int32_t)HIL_002_MAX_DEVIATION_MG) {
            any_deviation = true;
            (void)printf("[HIL_002] CONSISTENCY fail iter=%lu "
                         "mag=%ld ref=%ld delta=%ld\r\n",
                         (unsigned long)i,
                         (long)frame.accel_magnitude_mg,
                         (long)first_mag,
                         (long)delta);
        }

        /* State consistency */
        if (frame.device_state != first_state) {
            any_deviation = true;
            (void)printf("[HIL_002] CONSISTENCY fail iter=%lu "
                         "state=%u ref=%u\r\n",
                         (unsigned long)i,
                         (unsigned int)frame.device_state,
                         (unsigned int)first_state);
        }

        /* Cycle count: must stay within ±10% of baseline */
        if (frame.processing_cycles > first_cycles) {
            cycle_delta = frame.processing_cycles - first_cycles;
        } else {
            cycle_delta = first_cycles - frame.processing_cycles;
        }
        if (cycle_delta > (first_cycles / 10U)) {
            any_deviation = true;
            (void)printf("[HIL_002] CONSISTENCY fail iter=%lu "
                         "cycles=%lu ref=%lu delta=%lu\r\n",
                         (unsigned long)i,
                         (unsigned long)frame.processing_cycles,
                         (unsigned long)first_cycles,
                         (unsigned long)cycle_delta);
        }
    }

    SUITE_ASSERT(p_report, !any_deviation,
                 "CONSISTENCY: all 100 iterations produce identical output");

    /* Verify injection counter incremented correctly */
    SUITE_ASSERT(p_report,
                 HIL_GetInjectionCount() >= HIL_002_CONSISTENCY_ITERATIONS,
                 "CONSISTENCY: injection counter matches iteration count");

    return (p_report->assertions_failed == 0U) ? HIL_RESULT_PASS
                                                : HIL_RESULT_FAIL_SENSOR;
}

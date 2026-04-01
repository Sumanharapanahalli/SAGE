/**
 * @file     collision_warning_hal.h
 * @brief    HAL types, constants, and prototypes for the intersection
 *           collision-warning HIL test suite.
 *
 * Target MCU : STM32WB55RGV6 (HIL host, 64 MHz Cortex-M4)
 * Toolchain  : arm-none-eabi-gcc 12.x
 * Standard   : MISRA-C:2012 (ISO/IEC 9899:2011)
 *
 * Timing requirements (SR-CW-TIM):
 *   SR-CW-TIM-001 : sensor-read  → detection decision  ≤  50 ms
 *   SR-CW-TIM-002 : detection    → warning GPIO assert  ≤ 100 ms
 *   SR-CW-TIM-003 : radar sensor polling period          =  10 ms ± 1 ms
 *
 * MISRA-C:2012 compliance notes:
 *   Rule 2.5  — Every macro defined here is used in at least one TU.
 *   Rule 11.6 — Volatile pointer casts (DWT, peripheral regs) are localised
 *               to the single .c file that needs them.
 *   Rule 20.7 — All macro parameters are parenthesised.
 *   Rule 17.7 — All function return values are checked by callers.
 */

#ifndef COLLISION_WARNING_HAL_H
#define COLLISION_WARNING_HAL_H

#include <stdint.h>
#include <stdbool.h>
#include "hil_config.h"   /* HIL_Result_t, HIL_SuiteReport_t, shared constants */

#ifdef __cplusplus
extern "C" {
#endif

/* ---------------------------------------------------------------------------
 * Timing requirements — SR-CW-TIM
 * -------------------------------------------------------------------------*/
#define CW_DETECTION_LATENCY_MAX_MS   (50U)    /**< SR-CW-TIM-001 */
#define CW_WARNING_LATENCY_MAX_MS    (100U)    /**< SR-CW-TIM-002 */
#define CW_POLL_PERIOD_MS             (10U)    /**< SR-CW-TIM-003 nominal */
#define CW_POLL_JITTER_MS              (1U)    /**< SR-CW-TIM-003 tolerance */
#define CW_POLL_SAMPLES_FOR_JITTER    (50U)    /**< sample count for jitter test */

/* ---------------------------------------------------------------------------
 * Range and velocity thresholds
 * -------------------------------------------------------------------------*/
#define CW_MAX_RANGE_CM             (5000U)   /**< Radar max range 50 m */
#define CW_ADVISORY_DISTANCE_CM     (1000U)   /**< 10 m — advisory zone */
#define CW_CAUTION_DISTANCE_CM       (500U)   /**< 5 m  — caution zone  */
#define CW_CRITICAL_DISTANCE_CM      (200U)   /**< 2 m  — critical zone */
#define CW_MIN_APPROACH_VEL_CMS       (50)    /**< 0.5 m/s min approach speed */
#define CW_TTC_CRITICAL_MS          (1500U)   /**< TTC < 1.5 s → CRITICAL   */
#define CW_TTC_CAUTION_MS           (3000U)   /**< TTC < 3.0 s → CAUTION    */

/* ---------------------------------------------------------------------------
 * Sensor and bus identifiers
 * -------------------------------------------------------------------------*/
#define CW_SENSOR_COUNT               (4U)    /**< Front-left, front-right,
                                                   rear-left, rear-right */
#define CW_SENSOR_FRONT_LEFT          (0U)
#define CW_SENSOR_FRONT_RIGHT         (1U)
#define CW_SENSOR_REAR_LEFT           (2U)
#define CW_SENSOR_REAR_RIGHT          (3U)

/* ---------------------------------------------------------------------------
 * HIL RAM-stub addresses
 * These must match the linker-script sections used by the HIL firmware stub.
 * The Python harness writes here via GDB; the firmware reads these as inputs.
 * -------------------------------------------------------------------------*/
#define CW_STUB_RADAR_BASE_ADDR     (0x20001000UL)  /**< 4 × CW_RadarSample_t */
#define CW_STUB_WARNING_STATE_ADDR  (0x20001100UL)  /**< CW_WarningState_t     */
#define CW_STUB_FAULT_INJECT_ADDR   (0x20001200UL)  /**< uint32_t fault flags  */
#define CW_STUB_RESULT_ADDR         (0x20001300UL)  /**< HIL result sentinel   */

/* ---------------------------------------------------------------------------
 * Warning level enumeration
 * -------------------------------------------------------------------------*/
typedef enum {
    CW_WARN_NONE     = 0U,   /**< No risk — no warning output               */
    CW_WARN_ADVISORY = 1U,   /**< Informational — TTC > CW_TTC_CAUTION_MS   */
    CW_WARN_CAUTION  = 2U,   /**< Alerting     — TTC ≤ CW_TTC_CAUTION_MS    */
    CW_WARN_CRITICAL = 3U    /**< Emergency    — TTC ≤ CW_TTC_CRITICAL_MS   */
} CW_WarningLevel_t;

/* ---------------------------------------------------------------------------
 * Radar sensor sample (one per physical sensor channel)
 * -------------------------------------------------------------------------*/
typedef struct {
    uint16_t distance_cm;       /**< Distance to detected object [0..65535 cm] */
    int16_t  rel_velocity_cms;  /**< Relative velocity [cm/s]; negative = approach */
    uint8_t  sensor_id;         /**< Channel ID — CW_SENSOR_* */
    uint8_t  valid;             /**< Non-zero when sample is fresh and checksum OK */
    uint16_t _pad;              /**< Explicit padding — MISRA Rule 6.7 */
    uint32_t timestamp_ms;      /**< HAL tick at sample capture */
} CW_RadarSample_t;

/* Compile-time size check: struct must be exactly 12 bytes for stub alignment */
HIL_STATIC_ASSERT(sizeof(CW_RadarSample_t) == 12U, cw_radar_sample_size);

/* ---------------------------------------------------------------------------
 * Collision warning output state (written by firmware, read by harness)
 * -------------------------------------------------------------------------*/
typedef struct {
    CW_WarningLevel_t level;            /**< Current warning level          */
    uint32_t          ttc_ms;           /**< Estimated time-to-collision     */
    uint32_t          detection_ts_ms;  /**< HAL tick when threat detected   */
    uint32_t          warning_ts_ms;    /**< HAL tick when GPIO asserted     */
    uint32_t          detection_lat_ms; /**< detection_ts - sensor timestamp */
    uint32_t          warning_lat_ms;   /**< warning_ts  - detection_ts      */
    uint32_t          triggered_sensor; /**< Sensor ID that triggered warn   */
    uint32_t          warn_count;       /**< Cumulative warning events       */
} CW_WarningState_t;

HIL_STATIC_ASSERT(sizeof(CW_WarningState_t) == 32U, cw_warning_state_size);

/* ---------------------------------------------------------------------------
 * Fault injection codes (OR-able bitmask)
 * -------------------------------------------------------------------------*/
typedef enum {
    CW_FAULT_NONE            = 0x00000000UL, /**< Normal operation           */
    CW_FAULT_SENSOR_TIMEOUT  = 0x00000001UL, /**< Radar not responding       */
    CW_FAULT_SENSOR_STUCK    = 0x00000002UL, /**< Radar output frozen        */
    CW_FAULT_CAN_BUS_ERROR   = 0x00000004UL, /**< CAN error frame injected   */
    CW_FAULT_POWER_GLITCH    = 0x00000008UL, /**< VDD transient (< 50 µs)    */
    CW_FAULT_RADAR_ALL_MASK  = 0x00000003UL  /**< Both radar faults active   */
} CW_FaultCode_t;

/* ---------------------------------------------------------------------------
 * Intersection scenario descriptor (used in HIL test setup)
 * -------------------------------------------------------------------------*/
typedef struct {
    const char       *label;            /**< Human-readable scenario name   */
    uint8_t           sensor_id;        /**< Which sensor observes the vehicle */
    uint16_t          initial_dist_cm;  /**< Starting distance              */
    int16_t           approach_vel_cms; /**< Approach velocity (negative)   */
    CW_WarningLevel_t expected_warn;    /**< Expected worst-case warning     */
    uint32_t          settle_ms;        /**< Time to run before sampling     */
} CW_Scenario_t;

/* ---------------------------------------------------------------------------
 * Public HIL test suite entry point
 * -------------------------------------------------------------------------*/
HIL_Result_t HIL_CollisionWarningSuite(HIL_SuiteReport_t *p_report);

#ifdef __cplusplus
}
#endif

#endif /* COLLISION_WARNING_HAL_H */

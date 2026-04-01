/**
 * @file     hil_sensor_data_validation.h
 * @brief    HIL_002 — Sensor data validation test suite interface.
 *
 *           Three sub-suites cover all HIL_002 acceptance criteria:
 *             1. HIL_SensorDataInterpretationSuite — raw-to-EU conversion
 *             2. HIL_SensorStateMapSuite           — EU data → device state
 *             3. HIL_SensorConsistencySuite        — 100-iteration repeatability
 *
 * Test case  : HIL_002 (sensor_data_validation)
 * Target MCU : STM32WB55RGV6
 * Toolchain  : arm-none-eabi-gcc 12.x
 * Standard   : IEC 62304 Software Class B
 *
 * MISRA-C:2012 compliance notes:
 *   Rule 2.5  — All macros are used by at least one translation unit.
 *   Rule 5.8  — All identifiers are unique within their scope.
 *   Rule 20.7 — All macro parameters are parenthesised.
 */
#ifndef HIL_SENSOR_DATA_VALIDATION_H
#define HIL_SENSOR_DATA_VALIDATION_H

#include "hil_config.h"
#include <stdint.h>
#include <stdbool.h>

/* ---------------------------------------------------------------------------
 * HIL_SuiteReport_t — shared across all HIL test suites.
 * NOTE: intentionally defined here (not in hil_config.h) because hil_config.h
 *       is included by both the firmware and the Python stub generator. Keeping
 *       the struct here avoids pulling C struct syntax into the stub generator.
 * -------------------------------------------------------------------------*/
#ifndef HIL_SUITE_REPORT_DEFINED
#define HIL_SUITE_REPORT_DEFINED

typedef struct {
    const char *p_suite_name;      /**< Suite identifier string (static storage) */
    uint32_t    assertions_run;    /**< Total assertions executed in this suite   */
    uint32_t    assertions_failed; /**< Number of assertions that evaluated false */
} HIL_SuiteReport_t;

#endif /* HIL_SUITE_REPORT_DEFINED */

/* ---------------------------------------------------------------------------
 * Consistency test parameters
 * -------------------------------------------------------------------------*/
#define HIL_002_CONSISTENCY_ITERATIONS   (100U)  /**< HIL_002 step 4: N iterations */
#define HIL_002_MAX_DEVIATION_PA         (2U)    /**< Baro: ≤ 2 Pa run-to-run drift */
#define HIL_002_MAX_DEVIATION_MG         (5U)    /**< Accel: ≤ 5 mg inter-run delta  */

/* ---------------------------------------------------------------------------
 * Sensor injection record — written by GDB from the Python harness.
 * All fields use fixed-width types to guarantee identical memory layout
 * on host and target (MISRA-C Rule 4.6: only fixed-width types in
 * externally-visible structs).
 *
 * The struct is placed in a named linker section (.hil_inject) so the
 * linker script guarantees a fixed address that the Python harness can
 * compute at build time from the ELF symbol table.
 * -------------------------------------------------------------------------*/
typedef struct {
    int32_t  accel_x_mg;        /**< X-axis acceleration, milli-g               */
    int32_t  accel_y_mg;        /**< Y-axis acceleration, milli-g               */
    int32_t  accel_z_mg;        /**< Z-axis acceleration, milli-g               */
    int32_t  gyro_x_mdps;       /**< X-axis angular rate, milli-dps             */
    int32_t  gyro_y_mdps;       /**< Y-axis angular rate, milli-dps             */
    int32_t  gyro_z_mdps;       /**< Z-axis angular rate, milli-dps             */
    int32_t  pressure_pa;       /**< Barometric pressure, Pa                    */
    int32_t  temperature_cdeg;  /**< Temperature, 0.01 °C units (centidegrees)  */
    uint32_t sequence_number;   /**< Monotonic counter — incremented per inject  */
    uint32_t valid_magic;       /**< Set to HIL_INJECT_MAGIC when record is live */
} HIL_SensorInjection_t;

#define HIL_INJECT_MAGIC   (0xB00BCAFEU)  /**< Sentinel: injection record is valid */
#define HIL_INJECT_CLEARED (0x00000000U)  /**< Sentinel: injection slot is empty   */

/* ---------------------------------------------------------------------------
 * Device state — outcome of the fall-detection state machine after processing
 * one injection record.  "Vehicle state" in HIL_002 terminology maps to this
 * enum for the wearable fall-detection platform (STM32WB55).
 * -------------------------------------------------------------------------*/
typedef enum {
    HIL_DEVICE_STATE_IDLE          = 0x00U, /**< No motion, device at rest         */
    HIL_DEVICE_STATE_UPRIGHT       = 0x01U, /**< Normal upright orientation        */
    HIL_DEVICE_STATE_WALKING       = 0x02U, /**< Periodic step-gait detected       */
    HIL_DEVICE_STATE_FALL_DETECTED = 0x03U, /**< Free-fall phase in progress       */
    HIL_DEVICE_STATE_IMPACT        = 0x04U, /**< Post-fall impact transient        */
    HIL_DEVICE_STATE_LYING         = 0x05U, /**< Sustained horizontal posture      */
    HIL_DEVICE_STATE_UNKNOWN       = 0xFFU  /**< Processing error / uninitialised  */
} HIL_DeviceState_t;

/* ---------------------------------------------------------------------------
 * Processed sensor frame — populated by HIL_ProcessInjection().
 * The Python harness reads this struct from RAM after triggering processing.
 * -------------------------------------------------------------------------*/
typedef struct {
    int32_t          accel_magnitude_mg;  /**< |a| = sqrt(ax²+ay²+az²), mg        */
    int32_t          tilt_angle_cdeg;     /**< Tilt from vertical, centidegrees   */
    int32_t          pressure_pa;         /**< Pass-through from injection record  */
    int32_t          temperature_cdeg;    /**< Pass-through from injection record  */
    HIL_DeviceState_t device_state;       /**< State machine output               */
    uint32_t         sequence_number;     /**< Matches injection record            */
    uint32_t         processing_cycles;   /**< DWT cycles consumed by processing  */
} HIL_ProcessedFrame_t;

/* ---------------------------------------------------------------------------
 * Public API — callable from test runner and via GDB expressions
 * -------------------------------------------------------------------------*/

/**
 * @brief  Sub-suite 1: raw ADC → engineering-unit interpretation.
 *         Injects three known sensor profiles (upright, inclined, zero-g)
 *         and verifies the EU output matches the expected value within tolerance.
 *
 * @param[in,out] p_report  Suite report accumulator (must not be NULL).
 * @return HIL_RESULT_PASS or HIL_RESULT_FAIL_SENSOR.
 */
HIL_Result_t HIL_SensorDataInterpretationSuite(HIL_SuiteReport_t *p_report);

/**
 * @brief  Sub-suite 2: EU data → device state machine transitions.
 *         Covers IDLE, UPRIGHT, FALL_DETECTED, IMPACT, and LYING states.
 *
 * @param[in,out] p_report  Suite report accumulator (must not be NULL).
 * @return HIL_RESULT_PASS or HIL_RESULT_FAIL_SENSOR.
 */
HIL_Result_t HIL_SensorStateMapSuite(HIL_SuiteReport_t *p_report);

/**
 * @brief  Sub-suite 3: output consistency across HIL_002_CONSISTENCY_ITERATIONS.
 *         Same injection record repeated N times; output must be bit-identical.
 *
 * @param[in,out] p_report  Suite report accumulator (must not be NULL).
 * @return HIL_RESULT_PASS or HIL_RESULT_FAIL_SENSOR.
 */
HIL_Result_t HIL_SensorConsistencySuite(HIL_SuiteReport_t *p_report);

/**
 * @brief  Write a sensor injection record into the shared buffer.
 *         Called by GDB `call HIL_InjectSensorData(...)` from the harness.
 *
 * @param[in] p_sample  Sensor injection record (must not be NULL).
 */
void HIL_InjectSensorData(const HIL_SensorInjection_t *p_sample);

/**
 * @brief  Clear the active injection record (set valid_magic to 0).
 */
void HIL_ClearSensorInjection(void);

/**
 * @brief  Trigger processing of the current injection record.
 *         Populates g_hil_processed_frame and returns the device state.
 *
 * @return Computed HIL_DeviceState_t.
 */
HIL_DeviceState_t HIL_ProcessInjection(void);

/**
 * @brief  Return the monotonic injection sequence counter.
 */
uint32_t HIL_GetInjectionCount(void);

#endif /* HIL_SENSOR_DATA_VALIDATION_H */

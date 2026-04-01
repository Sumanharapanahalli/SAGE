/**
 * @file     hil_sensor_tests.c
 * @brief    Sensor HIL test suite — init, WHO_AM_I, calibration offsets,
 *           sample-rate verification, and self-test modes.
 *
 * Sensors under test (per board BOM):
 *   - IMU  : LSM6DSO (accel + gyro) on SPI1
 *   - BARO : LPS22HH (pressure + temp) on I2C1
 *   - GPS  : u-blox M8N on UART2
 *
 * MISRA-C:2012 — no dynamic memory, no recursion, all returns checked.
 */

#include "hil_sensor_tests.h"
#include "hil_config.h"
#include "imu_hal.h"
#include "baro_hal.h"
#include "gps_hal.h"

#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>

/* ---------------------------------------------------------------------------
 * IMU register map (subset — for direct HIL verification)
 * -------------------------------------------------------------------------*/
#define LSM6DSO_REG_WHO_AM_I    (0x0FU)
#define LSM6DSO_REG_CTRL1_XL    (0x10U)
#define LSM6DSO_REG_CTRL2_G     (0x11U)
#define LSM6DSO_REG_STATUS      (0x1EU)
#define LSM6DSO_REG_OUTX_L_A    (0x28U)
#define LSM6DSO_REG_SELF_TEST   (0x14U)

/* ---------------------------------------------------------------------------
 * BARO register map
 * -------------------------------------------------------------------------*/
#define LPS22HH_REG_WHO_AM_I    (0x0FU)
#define LPS22HH_REG_CTRL_REG1   (0x10U)
#define LPS22HH_REG_STATUS      (0x27U)
#define LPS22HH_REG_PRESS_OUT_L (0x28U)

/* ---------------------------------------------------------------------------
 * Internal assertion wrapper (tracks counts in suite report)
 * -------------------------------------------------------------------------*/
#define SUITE_ASSERT(report_ptr, cond, label)                           \
    do {                                                                \
        (report_ptr)->assertions_run++;                                 \
        if (!(cond)) {                                                  \
            (report_ptr)->assertions_failed++;                          \
            (void)printf("[ASSERT FAIL] %s\r\n", (label));             \
        }                                                               \
    } while (0)

/* ---------------------------------------------------------------------------
 * Suite 1: Sensor power-on and WHO_AM_I identity check
 * -------------------------------------------------------------------------*/
HIL_Result_t HIL_SensorInitSuite(HIL_SuiteReport_t *p_report)
{
    uint8_t who_am_i = 0U;

    if (p_report == NULL) {
        return HIL_RESULT_ERROR_SETUP;
    }

    /* ---- IMU identity --------------------------------------------------- */
    HAL_StatusTypeDef status = IMU_HAL_ReadRegister(LSM6DSO_REG_WHO_AM_I,
                                                     &who_am_i);
    SUITE_ASSERT(p_report, status == HAL_OK,
                 "IMU_WHO_AM_I: SPI transfer OK");
    SUITE_ASSERT(p_report, who_am_i == HIL_IMU_WHO_AM_I_EXPECTED,
                 "IMU_WHO_AM_I: device identity correct");

    /* ---- BARO identity -------------------------------------------------- */
    who_am_i = 0U;
    status = BARO_HAL_ReadRegister(LPS22HH_REG_WHO_AM_I, &who_am_i);
    SUITE_ASSERT(p_report, status == HAL_OK,
                 "BARO_WHO_AM_I: I2C transfer OK");
    SUITE_ASSERT(p_report, who_am_i == HIL_BARO_WHO_AM_I_EXPECTED,
                 "BARO_WHO_AM_I: device identity correct");

    /* ---- GPS UART RX alive (any byte within 2 s) ----------------------- */
    bool gps_alive = GPS_HAL_WaitForByte(2000U);
    SUITE_ASSERT(p_report, gps_alive,
                 "GPS_UART: data received within 2 s");

    /* ---- IMU output data rate ------------------------------------------- */
    uint8_t ctrl1 = 0U;
    status = IMU_HAL_ReadRegister(LSM6DSO_REG_CTRL1_XL, &ctrl1);
    SUITE_ASSERT(p_report, status == HAL_OK,
                 "IMU_CTRL1_XL: register readable");
    /* ODR bits [7:4] — 0110 = 416 Hz */
    SUITE_ASSERT(p_report, ((ctrl1 >> 4U) & 0x0FU) != 0U,
                 "IMU_CTRL1_XL: ODR is non-zero (sensor active)");

    return (p_report->assertions_failed == 0U) ? HIL_RESULT_PASS
                                                : HIL_RESULT_FAIL_SENSOR;
}

/* ---------------------------------------------------------------------------
 * Suite 2: Sensor calibration — offset verification
 * -------------------------------------------------------------------------*/
HIL_Result_t HIL_SensorCalSuite(HIL_SuiteReport_t *p_report)
{
    IMU_CalData_t  imu_cal;
    BARO_CalData_t baro_cal;

    if (p_report == NULL) {
        return HIL_RESULT_ERROR_SETUP;
    }

    (void)memset(&imu_cal,  0, sizeof(IMU_CalData_t));
    (void)memset(&baro_cal, 0, sizeof(BARO_CalData_t));

    /* ---- Collect 1000-sample static average (device must be still) ------ */
    HAL_StatusTypeDef status = IMU_HAL_CollectCalibration(&imu_cal, 1000U);
    SUITE_ASSERT(p_report, status == HAL_OK,
                 "IMU_CAL: collection completed without error");

    /* Accel offset: each axis ≤ 90 mg when flat */
    uint32_t ax_abs = (uint32_t)((imu_cal.accel_offset_x_mg < 0)
                                 ? -imu_cal.accel_offset_x_mg
                                 :  imu_cal.accel_offset_x_mg);
    uint32_t ay_abs = (uint32_t)((imu_cal.accel_offset_y_mg < 0)
                                 ? -imu_cal.accel_offset_y_mg
                                 :  imu_cal.accel_offset_y_mg);
    uint32_t az_deviation;
    /* Z axis: net = gravity − 1000 mg */
    int32_t az_net = imu_cal.accel_offset_z_mg - 1000;
    az_deviation   = (uint32_t)((az_net < 0) ? -az_net : az_net);

    SUITE_ASSERT(p_report, ax_abs <= HIL_ACCEL_OFFSET_MAX_MG,
                 "IMU_CAL: accel X offset within tolerance");
    SUITE_ASSERT(p_report, ay_abs <= HIL_ACCEL_OFFSET_MAX_MG,
                 "IMU_CAL: accel Y offset within tolerance");
    SUITE_ASSERT(p_report, az_deviation <= HIL_ACCEL_OFFSET_MAX_MG,
                 "IMU_CAL: accel Z offset (gravity-corrected) within tolerance");

    /* Gyro zero-rate offset: each axis ≤ 50 000 mdps */
    uint32_t gx_abs = (uint32_t)((imu_cal.gyro_offset_x_mdps < 0)
                                 ? -imu_cal.gyro_offset_x_mdps
                                 :  imu_cal.gyro_offset_x_mdps);
    uint32_t gy_abs = (uint32_t)((imu_cal.gyro_offset_y_mdps < 0)
                                 ? -imu_cal.gyro_offset_y_mdps
                                 :  imu_cal.gyro_offset_y_mdps);
    uint32_t gz_abs = (uint32_t)((imu_cal.gyro_offset_z_mdps < 0)
                                 ? -imu_cal.gyro_offset_z_mdps
                                 :  imu_cal.gyro_offset_z_mdps);

    SUITE_ASSERT(p_report, gx_abs <= HIL_GYRO_OFFSET_MAX_MDPS,
                 "IMU_CAL: gyro X zero-rate offset within spec");
    SUITE_ASSERT(p_report, gy_abs <= HIL_GYRO_OFFSET_MAX_MDPS,
                 "IMU_CAL: gyro Y zero-rate offset within spec");
    SUITE_ASSERT(p_report, gz_abs <= HIL_GYRO_OFFSET_MAX_MDPS,
                 "IMU_CAL: gyro Z zero-rate offset within spec");

    /* ---- Barometer calibration ----------------------------------------- */
    status = BARO_HAL_CollectCalibration(&baro_cal, 100U);
    SUITE_ASSERT(p_report, status == HAL_OK,
                 "BARO_CAL: collection completed");
    /* Sea-level reference: 101325 Pa ± 5000 Pa acceptable for HIL bench */
    int32_t baro_delta = baro_cal.pressure_pa - 101325;
    uint32_t baro_abs  = (uint32_t)((baro_delta < 0) ? -baro_delta : baro_delta);
    SUITE_ASSERT(p_report, baro_abs <= 5000U,
                 "BARO_CAL: pressure within ±5 kPa of sea level");

    return (p_report->assertions_failed == 0U) ? HIL_RESULT_PASS
                                                : HIL_RESULT_FAIL_SENSOR;
}

/* ---------------------------------------------------------------------------
 * IMU self-test (LSM6DSO application note AN5004 procedure)
 * Positive self-test: output must shift ≥ 70 mg (accel), ≥ 150 dps (gyro)
 * -------------------------------------------------------------------------*/
HIL_Result_t HIL_IMUSelfTestSuite(HIL_SuiteReport_t *p_report)
{
    IMU_SelfTestResult_t st;

    if (p_report == NULL) {
        return HIL_RESULT_ERROR_SETUP;
    }

    (void)memset(&st, 0, sizeof(IMU_SelfTestResult_t));

    HAL_StatusTypeDef status = IMU_HAL_RunSelfTest(&st);
    SUITE_ASSERT(p_report, status == HAL_OK,
                 "IMU_SELFTEST: procedure completed");

    /* Accel: min 70 mg, max 1500 mg per AN5004 §3.2 */
    SUITE_ASSERT(p_report, st.accel_x_delta_mg >= 70 && st.accel_x_delta_mg <= 1500,
                 "IMU_SELFTEST: accel X within ST limits");
    SUITE_ASSERT(p_report, st.accel_y_delta_mg >= 70 && st.accel_y_delta_mg <= 1500,
                 "IMU_SELFTEST: accel Y within ST limits");
    SUITE_ASSERT(p_report, st.accel_z_delta_mg >= 70 && st.accel_z_delta_mg <= 1500,
                 "IMU_SELFTEST: accel Z within ST limits");

    /* Gyro: min 150 dps, max 700 dps per AN5004 §3.3 */
    SUITE_ASSERT(p_report, st.gyro_x_delta_dps >= 150 && st.gyro_x_delta_dps <= 700,
                 "IMU_SELFTEST: gyro X within ST limits");
    SUITE_ASSERT(p_report, st.gyro_y_delta_dps >= 150 && st.gyro_y_delta_dps <= 700,
                 "IMU_SELFTEST: gyro Y within ST limits");
    SUITE_ASSERT(p_report, st.gyro_z_delta_dps >= 150 && st.gyro_z_delta_dps <= 700,
                 "IMU_SELFTEST: gyro Z within ST limits");

    return (p_report->assertions_failed == 0U) ? HIL_RESULT_PASS
                                                : HIL_RESULT_FAIL_SENSOR;
}

/**
 * @file     hil_config.h
 * @brief    HIL test suite configuration — timing budgets, coverage targets,
 *           fault injection parameters, and hardware channel mappings.
 *
 * Target MCU : STM32WB55 (wearable main SoC)
 * Toolchain  : arm-none-eabi-gcc 12.x
 * Standard   : IEC 62304 Software Class B
 *
 * MISRA-C:2012 compliance notes:
 *   Rule 2.5  — All macros are used by at least one translation unit.
 *   Rule 20.7 — All macro parameters are parenthesised.
 */
#ifndef HIL_CONFIG_H
#define HIL_CONFIG_H

#include <stdint.h>
#include <stdbool.h>

/* ---------------------------------------------------------------------------
 * Build-time assertions (static analysis helpers)
 * -------------------------------------------------------------------------*/
#define HIL_STATIC_ASSERT(cond, msg)  typedef char hil_sa_##msg[(cond) ? 1 : -1]

/* ---------------------------------------------------------------------------
 * MCU identity
 * -------------------------------------------------------------------------*/
#define HIL_TARGET_MCU          "STM32WB55RGV6"
#define HIL_FLASH_SIZE_KB       (1024U)
#define HIL_RAM_SIZE_KB         (256U)
#define HIL_SYSCLK_HZ           (64000000UL)

/* ---------------------------------------------------------------------------
 * Coverage requirement
 * -------------------------------------------------------------------------*/
#define HIL_COVERAGE_TARGET_PCT (90U)   /* ≥ 90 % branch coverage required  */

/* ---------------------------------------------------------------------------
 * Timing budgets (milliseconds) — derived from system requirements doc SR-TIM
 * -------------------------------------------------------------------------*/
#define HIL_BOOT_MAX_MS         (3000U) /* SR-TIM-001: boot-to-operational   */
#define HIL_IMU_SAMPLE_MAX_US   (1000U) /* SR-TIM-002: IMU ISR latency       */
#define HIL_GPS_FIX_MAX_MS      (60000U)/* SR-TIM-003: cold-start TTFF       */
#define HIL_BLE_ADV_PERIOD_MS   (1000U) /* SR-TIM-004: BLE advertisement     */
#define HIL_OTA_CHUNK_MAX_MS    (500U)  /* SR-TIM-005: OTA block write       */
#define HIL_ACTUATOR_RISE_MS    (50U)   /* SR-TIM-006: haptic rise time      */
#define HIL_ACTUATOR_FALL_MS    (50U)   /* SR-TIM-007: haptic fall time      */
#define HIL_WDT_KICK_PERIOD_MS  (1000U) /* SR-TIM-008: watchdog feed period  */
#define HIL_ALERT_LATENCY_MAX_MS (200U) /* SR-TIM-009: fall-detect → alert   */

/* ---------------------------------------------------------------------------
 * Sensor acceptance thresholds
 * -------------------------------------------------------------------------*/
#define HIL_IMU_WHO_AM_I_EXPECTED   (0x6BU) /* LSM6DSO WHO_AM_I register     */
#define HIL_BARO_WHO_AM_I_EXPECTED  (0x50U) /* LPS22HH WHO_AM_I register     */
#define HIL_ACCEL_FULL_SCALE_G      (8)     /* ±8 g range                    */
#define HIL_GYRO_FULL_SCALE_DPS     (2000)  /* ±2000 dps range               */
#define HIL_BARO_RESOLUTION_PA      (1)     /* 1 Pa resolution               */
#define HIL_TEMP_ACCURACY_CDEG      (100)   /* ±1 °C (0.01 °C units)         */

/* Calibration offset tolerances */
#define HIL_ACCEL_OFFSET_MAX_MG     (90U)   /* max static offset after cal   */
#define HIL_GYRO_OFFSET_MAX_MDPS    (50000U)/* 50 dps max zero-rate offset   */

/* ---------------------------------------------------------------------------
 * Fault injection channels
 * -------------------------------------------------------------------------*/
typedef enum {
    HIL_FAULT_NONE              = 0x00U,
    HIL_FAULT_SPI_BUS_STUCK_LO  = 0x01U,  /* SPI MISO stuck at 0           */
    HIL_FAULT_SPI_BUS_STUCK_HI  = 0x02U,  /* SPI MISO stuck at 1           */
    HIL_FAULT_I2C_NAK           = 0x03U,  /* I2C slave NAK                 */
    HIL_FAULT_I2C_BUS_HANG      = 0x04U,  /* I2C SCL stuck low             */
    HIL_FAULT_UART_NOISE        = 0x05U,  /* UART framing/parity errors    */
    HIL_FAULT_POWER_BROWNOUT    = 0x06U,  /* VDD drops below UVLO          */
    HIL_FAULT_POWER_SPIKE       = 0x07U,  /* VDD overvoltage transient     */
    HIL_FAULT_IMU_DISCONNECT    = 0x08U,  /* IMU CS deasserted mid-read    */
    HIL_FAULT_GPS_NO_SIGNAL     = 0x09U,  /* GPS antenna open-circuit      */
    HIL_FAULT_GPS_NMEA_CORRUPT  = 0x0AU,  /* NMEA checksum errors          */
    HIL_FAULT_MODEM_NO_RESP     = 0x0BU,  /* Modem UART silent             */
    HIL_FAULT_BATTERY_LOW       = 0x0CU,  /* VBAT below cutoff             */
    HIL_FAULT_BATTERY_CRITICAL  = 0x0DU,  /* VBAT below hard shutdown lvl  */
    HIL_FAULT_WDT_MISS          = 0x0EU,  /* Watchdog kick missed once     */
    HIL_FAULT_FLASH_ECC         = 0x0FU,  /* Flash ECC single-bit error    */
    HIL_FAULT_STACK_OVERFLOW    = 0x10U,  /* Task stack canary corrupted   */
    HIL_FAULT_COUNT
} HIL_FaultType_t;

/* ---------------------------------------------------------------------------
 * Test result codes
 * -------------------------------------------------------------------------*/
typedef enum {
    HIL_RESULT_PASS             = 0,
    HIL_RESULT_FAIL_TIMING      = 1,
    HIL_RESULT_FAIL_COVERAGE    = 2,
    HIL_RESULT_FAIL_SENSOR      = 3,
    HIL_RESULT_FAIL_FAULT       = 4,
    HIL_RESULT_FAIL_COMMS       = 5,
    HIL_RESULT_ERROR_SETUP      = 6
} HIL_Result_t;

/* ---------------------------------------------------------------------------
 * OpenOCD / GDB probe connection (for Python harness)
 * -------------------------------------------------------------------------*/
#define HIL_OPENOCD_HOST        "127.0.0.1"
#define HIL_OPENOCD_PORT        (3333)
#define HIL_GDB_PORT            (3333)
#define HIL_TCL_PORT            (6666)
#define HIL_TELNET_PORT         (4444)

/* ---------------------------------------------------------------------------
 * UART semihosting log channel
 * -------------------------------------------------------------------------*/
#define HIL_LOG_UART_BAUDRATE   (115200U)
#define HIL_LOG_MAGIC_PASS      (0xCAFEBEEFUL)
#define HIL_LOG_MAGIC_FAIL      (0xDEADC0DEUL)

/* ---------------------------------------------------------------------------
 * Data logging
 * -------------------------------------------------------------------------*/
#define HIL_LOG_SAMPLE_HZ       (100U)
#define HIL_LOG_BUFFER_SAMPLES  (1000U)

#endif /* HIL_CONFIG_H */

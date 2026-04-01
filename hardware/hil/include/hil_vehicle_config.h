/**
 * @file     hil_vehicle_config.h
 * @brief    Vehicle HIL test configuration — timing budgets, fault injection
 *           channels, CAN signal maps, and ECU interface definitions for
 *           Vehicle Start, Engine Operation, and Brake System test suites.
 *
 * Target MCU : STM32F469NI (automotive body-domain ECU)
 * Toolchain  : arm-none-eabi-gcc 12.x
 * Standard   : ISO 26262 ASIL-B
 *
 * MISRA-C:2012 compliance notes:
 *   Rule 2.5  — All macros referenced in at least one translation unit.
 *   Rule 20.7 — All macro parameters parenthesised.
 *   Rule 14.4 — Boolean expressions used for controlling code.
 */
#ifndef HIL_VEHICLE_CONFIG_H
#define HIL_VEHICLE_CONFIG_H

#include <stdint.h>
#include <stdbool.h>
#include "hil_config.h"   /* inherit base timing types and result codes */

/* ---------------------------------------------------------------------------
 * MCU identity (overrides wearable target for vehicle domain)
 * -------------------------------------------------------------------------*/
#define HIL_VEH_TARGET_MCU       "STM32F469NIH6"
#define HIL_VEH_FLASH_SIZE_KB    (2048U)
#define HIL_VEH_RAM_SIZE_KB      (384U)
#define HIL_VEH_SYSCLK_HZ        (180000000UL)

/* ---------------------------------------------------------------------------
 * Timing budgets (milliseconds) — from ISO 26262 SR-VEH-TIM document
 * -------------------------------------------------------------------------*/
#define HIL_VEH_IGNITION_SETTLE_MS     (50U)    /* SR-VEH-TIM-001: ignition line debounce    */
#define HIL_VEH_START_CRANK_MAX_MS     (3000U)  /* SR-VEH-TIM-002: engine crank timeout      */
#define HIL_VEH_ENGINE_IDLE_STABLE_MS  (2000U)  /* SR-VEH-TIM-003: idle RPM within ±50 RPM  */
#define HIL_VEH_ECU_BOOT_MAX_MS        (500U)   /* SR-VEH-TIM-004: ECU operational readiness */
#define HIL_VEH_CAN_MSG_PERIOD_MS      (10U)    /* SR-VEH-TIM-005: engine status CAN frame   */
#define HIL_VEH_CAN_TIMEOUT_MS         (100U)   /* SR-VEH-TIM-006: CAN bus silence threshold */
#define HIL_VEH_BRAKE_APPLY_MAX_MS     (150U)   /* SR-VEH-TIM-007: brake apply to pressure   */
#define HIL_VEH_BRAKE_RELEASE_MAX_MS   (200U)   /* SR-VEH-TIM-008: brake release time        */
#define HIL_VEH_ABS_ACTIVATION_MAX_MS  (50U)    /* SR-VEH-TIM-009: ABS engage latency        */
#define HIL_VEH_BRAKE_FADE_TEST_MS     (30000U) /* SR-VEH-TIM-010: fade simulation window    */
#define HIL_VEH_FAULT_DETECT_MAX_MS    (500U)   /* SR-VEH-TIM-011: fault code set latency    */
#define HIL_VEH_LIMP_HOME_ENTER_MS     (1000U)  /* SR-VEH-TIM-012: limp-home engagement      */

/* ---------------------------------------------------------------------------
 * Engine operating parameters
 * -------------------------------------------------------------------------*/
#define HIL_VEH_RPM_IDLE_MIN           (650U)   /* RPM — idle floor                          */
#define HIL_VEH_RPM_IDLE_MAX           (850U)   /* RPM — idle ceiling                        */
#define HIL_VEH_RPM_REDLINE            (7000U)  /* RPM — redline limit                       */
#define HIL_VEH_RPM_LIMITER            (6800U)  /* RPM — rev limiter cut                     */
#define HIL_VEH_THROTTLE_MAX_PCT       (100U)   /* % throttle open                           */
#define HIL_VEH_MAP_IDLE_KPA           (30U)    /* kPa — manifold pressure at idle           */
#define HIL_VEH_MAP_WOT_KPA            (101U)   /* kPa — wide-open throttle                  */
#define HIL_VEH_COOLANT_WARN_CDEG      (10500)  /* 0.01 °C units — 105 °C warning            */
#define HIL_VEH_COOLANT_CRIT_CDEG      (11500)  /* 0.01 °C units — 115 °C critical           */
#define HIL_VEH_OIL_PRESS_MIN_KPA      (200U)   /* kPa — minimum oil pressure at idle        */
#define HIL_VEH_LAMBDA_MIN             (90U)    /* λ×100 — 0.90 lean limit                  */
#define HIL_VEH_LAMBDA_MAX             (110U)   /* λ×100 — 1.10 rich limit                  */

/* ---------------------------------------------------------------------------
 * Brake system parameters
 * -------------------------------------------------------------------------*/
#define HIL_VEH_BRAKE_PRESSURE_MAX_BAR (160U)   /* bar — max hydraulic line pressure         */
#define HIL_VEH_BRAKE_PRESSURE_MIN_BAR (2U)     /* bar — residual pressure threshold         */
#define HIL_VEH_BRAKE_PEDAL_ADC_FULL   (3800U)  /* ADC counts — fully depressed              */
#define HIL_VEH_BRAKE_PEDAL_ADC_IDLE   (200U)   /* ADC counts — fully released               */
#define HIL_VEH_WHEEL_SLIP_THRESHOLD   (15U)    /* % — slip ratio triggering ABS             */
#define HIL_VEH_ABS_PRESSURE_CYCLES    (3U)     /* minimum pressure modulation cycles        */
#define HIL_VEH_BRAKE_TEMP_MAX_CDEG    (70000)  /* 0.01 °C units — 700 °C pad limit          */
#define HIL_VEH_EBD_REAR_LIMIT_BAR     (80U)    /* bar — EBD rear channel limit              */

/* ---------------------------------------------------------------------------
 * CAN bus identifiers (29-bit extended frame, ISO 15765-4)
 * -------------------------------------------------------------------------*/
#define HIL_CAN_ID_ENGINE_STATUS       (0x0C9U) /* Engine status — 10 ms period              */
#define HIL_CAN_ID_ENGINE_TEMP         (0x130U) /* Coolant + oil temp — 100 ms               */
#define HIL_CAN_ID_BRAKE_PRESSURE      (0x1A0U) /* Hydraulic line pressures — 10 ms          */
#define HIL_CAN_ID_WHEEL_SPEED         (0x1B0U) /* 4-channel wheel speed — 10 ms             */
#define HIL_CAN_ID_ABS_STATUS          (0x220U) /* ABS control state — 20 ms                 */
#define HIL_CAN_ID_FAULT_CODES         (0x7DFU) /* OBD-II request                            */
#define HIL_CAN_ID_FAULT_RESPONSE      (0x7E8U) /* OBD-II response (ECU1)                    */
#define HIL_CAN_ID_IGNITION_STATUS     (0x100U) /* Ignition key position — 50 ms             */
#define HIL_CAN_ID_THROTTLE_PEDAL      (0x0D9U) /* Accelerator pedal position — 10 ms        */

/* ---------------------------------------------------------------------------
 * Fault injection channels (vehicle domain — extends HIL_FaultType_t)
 * -------------------------------------------------------------------------*/
typedef enum {
    HIL_VEH_FAULT_NONE                = 0x00U,
    HIL_VEH_FAULT_CAN_BUS_OFF         = 0x01U, /* CAN bus-off error state                  */
    HIL_VEH_FAULT_CAN_MSG_LOST        = 0x02U, /* Specific CAN frame drop (ID-targeted)    */
    HIL_VEH_FAULT_IGNITION_GLITCH     = 0x03U, /* 50 ms ignition line dropout              */
    HIL_VEH_FAULT_CRANK_NO_START      = 0x04U, /* Starter motor active but no RPM rise     */
    HIL_VEH_FAULT_ENGINE_STALL        = 0x05U, /* RPM forced to 0 mid-run                  */
    HIL_VEH_FAULT_MAP_SENSOR_OC       = 0x06U, /* MAP sensor open circuit (>4.8 V)         */
    HIL_VEH_FAULT_MAP_SENSOR_SC       = 0x07U, /* MAP sensor short to ground (<0.2 V)      */
    HIL_VEH_FAULT_COOLANT_OVERHEAT    = 0x08U, /* Coolant temp injected above critical     */
    HIL_VEH_FAULT_OIL_PRESSURE_LOW    = 0x09U, /* Oil pressure forced below minimum        */
    HIL_VEH_FAULT_BRAKE_PRESSURE_LOW  = 0x0AU, /* Brake line pressure below safe floor     */
    HIL_VEH_FAULT_WHEEL_SPEED_DROPOUT = 0x0BU, /* One wheel speed sensor disconnected      */
    HIL_VEH_FAULT_ABS_MODULE_FAIL     = 0x0CU, /* ABS control module silent                */
    HIL_VEH_FAULT_BRAKE_FLUID_LOW     = 0x0DU, /* Brake fluid level sensor fault           */
    HIL_VEH_FAULT_THROTTLE_STUCK_OPEN = 0x0EU, /* TPS reports >80 % with pedal released    */
    HIL_VEH_FAULT_ECU_POWER_LOSS      = 0x0FU, /* ECU 12 V rail removed (soft power off)   */
    HIL_VEH_FAULT_COUNT
} HIL_VehFaultType_t;

/* ---------------------------------------------------------------------------
 * Test suite identifiers (bit positions in pass/fail mask)
 * -------------------------------------------------------------------------*/
#define HIL_VEH_SUITE_BIT_VEHICLE_START  (8U)  /* extends base 8-suite mask               */
#define HIL_VEH_SUITE_BIT_ENGINE_OPS     (9U)
#define HIL_VEH_SUITE_BIT_BRAKE_SYS      (10U)

/* ---------------------------------------------------------------------------
 * Coverage sentinel addresses (GDB reads at these fixed RAM locations)
 * -------------------------------------------------------------------------*/
#define HIL_VEH_RESULT_RAM_ADDR          (0x20000020UL) /* after base HIL_ResultBlock       */

#endif /* HIL_VEHICLE_CONFIG_H */

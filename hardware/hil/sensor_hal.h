/**
 * @file    sensor_hal.h
 * @brief   HAL abstraction for vehicle sensor interface (HIL-ready)
 * @target  STM32F4xx (Cortex-M4)
 * @std     MISRA-C:2012 compliant where practical
 */
#ifndef SENSOR_HAL_H
#define SENSOR_HAL_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* ── Version ──────────────────────────────────────────────────────────────── */
#define SENSOR_HAL_VERSION_MAJOR  (1U)
#define SENSOR_HAL_VERSION_MINOR  (0U)
#define SENSOR_HAL_VERSION_PATCH  (0U)

/* ── Limits ───────────────────────────────────────────────────────────────── */
#define SENSOR_MAX_CHANNELS        (8U)
#define SENSOR_SAMPLE_RATE_HZ      (1000U)
#define SENSOR_TIMEOUT_MS          (10U)
#define SENSOR_CONSISTENCY_ITERS   (5U)

/* ── Status codes ─────────────────────────────────────────────────────────── */
typedef enum {
    SENSOR_OK               = 0x00U,
    SENSOR_ERR_NULL         = 0x01U,
    SENSOR_ERR_TIMEOUT      = 0x02U,
    SENSOR_ERR_RANGE        = 0x03U,
    SENSOR_ERR_CONSISTENCY  = 0x04U,
    SENSOR_ERR_BUS          = 0x05U,
    SENSOR_ERR_UNINIT       = 0x06U
} SensorStatus_t;

/* ── Raw reading from hardware FIFO ──────────────────────────────────────── */
typedef struct {
    uint16_t raw_adc[SENSOR_MAX_CHANNELS]; /**< 12-bit ADC values        */
    uint32_t timestamp_ms;                  /**< Captured at IRQ time     */
    uint8_t  channel_count;                 /**< Valid entries in raw_adc */
    bool     data_valid;                    /**< CRC / parity passed      */
} SensorRawFrame_t;

/* ── Mapped vehicle state ────────────────────────────────────────────────── */
typedef struct {
    float    velocity_mps;           /**< Vehicle speed (m/s)             */
    float    acceleration_mps2;      /**< Longitudinal accel (m/s²)       */
    float    yaw_rate_radps;         /**< Yaw rate (rad/s)                */
    float    steering_angle_rad;     /**< Steering wheel angle (rad)      */
    float    throttle_pct;           /**< Throttle position [0.0–100.0]   */
    float    brake_pressure_kpa;     /**< Brake pressure (kPa)            */
    uint32_t timestamp_ms;           /**< Inherited from raw frame        */
} VehicleState_t;

/* ── HAL handle ──────────────────────────────────────────────────────────── */
typedef struct {
    bool          initialised;
    uint32_t      read_count;
    uint32_t      error_count;
    SensorRawFrame_t last_raw;
    VehicleState_t   last_state;
} SensorHandle_t;

/* ── Memory-mapped peripheral registers (volatile, MISRA 11.4 exception) ── */
typedef struct {
    volatile uint32_t SR;    /**< Status register   */
    volatile uint32_t DR;    /**< Data register     */
    volatile uint32_t CR1;   /**< Control register  */
    volatile uint32_t CR2;   /**< Control register2 */
} SensorPeriphRegs_t;

#define SENSOR_PERIPH_BASE  (0x40011000UL)
#define SENSOR_REGS         ((SensorPeriphRegs_t *)(SENSOR_PERIPH_BASE))

/* ── API ─────────────────────────────────────────────────────────────────── */
SensorStatus_t SENSOR_Init(SensorHandle_t *handle);
SensorStatus_t SENSOR_ReadRaw(SensorHandle_t *handle, SensorRawFrame_t *frame);
SensorStatus_t SENSOR_MapToVehicleState(const SensorRawFrame_t *raw,
                                         VehicleState_t *state);
SensorStatus_t SENSOR_ValidateConsistency(SensorHandle_t *handle,
                                           uint8_t iterations,
                                           bool *consistent);
SensorStatus_t SENSOR_InjectFault(SensorHandle_t *handle,
                                   uint8_t channel, uint16_t injected_raw);
void           SENSOR_IRQHandler(SensorHandle_t *handle);
void           SENSOR_ConfigureIRQ(uint8_t preempt_prio, uint8_t sub_prio);

#endif /* SENSOR_HAL_H */

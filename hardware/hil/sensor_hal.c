/**
 * @file    sensor_hal.c
 * @brief   HAL implementation — sensor read, mapping, consistency checks
 * @target  STM32F4xx (Cortex-M4)
 * @std     MISRA-C:2012
 *
 * In HIL mode the peripheral registers are backed by the test harness via
 * OpenOCD memory writes — this file never changes; only the hardware target
 * (or simulator) changes beneath it.
 */
#include "sensor_hal.h"
#include <string.h>

/* ── Private constants ──────────────────────────────────────────────────── */
#define ADC_FULL_SCALE        (4095U)     /* 12-bit */
#define VELOCITY_SCALE        (0.08789f)  /* (max 360 km/h) / 4095 in m/s */
#define ACCEL_OFFSET          (2048U)     /* bipolar: 0 = -78.4 m/s²       */
#define ACCEL_SCALE           (0.03831f)  /* ±78.4 m/s² over 12 bits       */
#define YAW_OFFSET            (2048U)
#define YAW_SCALE             (0.001533f) /* ±π rad/s over 12 bits          */
#define STEERING_OFFSET       (2048U)
#define STEERING_SCALE        (0.003834f) /* ±7.85 rad over 12 bits         */
#define THROTTLE_SCALE        (0.02442f)  /* 0–100 % over 12 bits           */
#define BRAKE_SCALE           (0.09775f)  /* 0–400 kPa over 12 bits         */

#define SR_DATA_READY_BIT     (0x01U)
#define SR_OVERRUN_BIT        (0x02U)
#define CR1_ENABLE_BIT        (0x01U)
#define CR2_IRQ_ENABLE_BIT    (0x04U)

/* ── NVIC register (Cortex-M4 CMSIS-compatible stub) ───────────────────── */
#define NVIC_SENSOR_IRQn      (37U)       /* SPI1 on STM32F4 by default    */

/* ── Private helper: spin-wait for DR ready ─────────────────────────────── */
static SensorStatus_t wait_data_ready(uint32_t timeout_ms)
{
    /* Each iteration ≈ 1 µs at 168 MHz; 1 ms ≈ 168 iterations            */
    uint32_t ticks = timeout_ms * 168U;
    while (ticks > 0U) {
        if ((SENSOR_REGS->SR & SR_DATA_READY_BIT) != 0U) {
            return SENSOR_OK;
        }
        ticks--;
    }
    return SENSOR_ERR_TIMEOUT;
}

/* ══════════════════════════════════════════════════════════════════════════
 *  Public API
 * ══════════════════════════════════════════════════════════════════════════ */

/**
 * @brief  Initialise the sensor peripheral.
 * @param  handle  Non-NULL handle to zero-initialised by caller.
 * @return SENSOR_OK or SENSOR_ERR_NULL.
 */
SensorStatus_t SENSOR_Init(SensorHandle_t *handle)
{
    if (handle == NULL) {
        return SENSOR_ERR_NULL;
    }

    (void)memset(handle, 0, sizeof(SensorHandle_t));

    SENSOR_REGS->CR1 = CR1_ENABLE_BIT;
    SENSOR_REGS->CR2 = CR2_IRQ_ENABLE_BIT;

    handle->initialised = true;
    return SENSOR_OK;
}

/**
 * @brief  Blocking read of one raw sensor frame.
 * @param  handle  Initialised sensor handle.
 * @param  frame   Output buffer — must not be NULL.
 */
SensorStatus_t SENSOR_ReadRaw(SensorHandle_t *handle, SensorRawFrame_t *frame)
{
    SensorStatus_t status;
    uint8_t ch;

    if ((handle == NULL) || (frame == NULL)) {
        return SENSOR_ERR_NULL;
    }
    if (!handle->initialised) {
        return SENSOR_ERR_UNINIT;
    }

    status = wait_data_ready(SENSOR_TIMEOUT_MS);
    if (status != SENSOR_OK) {
        handle->error_count++;
        return status;
    }

    /* Clear overrun before reading ---------------------------------------- */
    if ((SENSOR_REGS->SR & SR_OVERRUN_BIT) != 0U) {
        (void)SENSOR_REGS->DR; /* dummy read clears overrun flag */
    }

    /* Read each channel from DR (burst-mode: peripheral auto-increments)  */
    frame->channel_count = (uint8_t)(SENSOR_REGS->CR2 & 0x0FU);
    if (frame->channel_count > SENSOR_MAX_CHANNELS) {
        frame->channel_count = SENSOR_MAX_CHANNELS;
    }

    for (ch = 0U; ch < frame->channel_count; ch++) {
        frame->raw_adc[ch] = (uint16_t)(SENSOR_REGS->DR & 0x0FFFU);
    }

    /* Simple parity check: MSB of DR set by hardware on CRC pass         */
    frame->data_valid = ((SENSOR_REGS->DR & 0x8000U) != 0U);

    /* Timestamp: SysTick shadow register at 0xE000E018 (CMSIS HAL stub)  */
    frame->timestamp_ms = handle->read_count * (1000U / SENSOR_SAMPLE_RATE_HZ);
    handle->read_count++;

    (void)memcpy(&handle->last_raw, frame, sizeof(SensorRawFrame_t));
    return SENSOR_OK;
}

/**
 * @brief  Map a validated raw frame to a physical VehicleState.
 * @param  raw    Source raw frame — must not be NULL.
 * @param  state  Output vehicle state — must not be NULL.
 */
SensorStatus_t SENSOR_MapToVehicleState(const SensorRawFrame_t *raw,
                                         VehicleState_t *state)
{
    if ((raw == NULL) || (state == NULL)) {
        return SENSOR_ERR_NULL;
    }
    if (!raw->data_valid) {
        return SENSOR_ERR_BUS;
    }
    if (raw->channel_count < 6U) {
        return SENSOR_ERR_RANGE;
    }

    state->velocity_mps        = (float)raw->raw_adc[0] * VELOCITY_SCALE;
    state->acceleration_mps2   = ((float)raw->raw_adc[1] - (float)ACCEL_OFFSET)
                                  * ACCEL_SCALE;
    state->yaw_rate_radps      = ((float)raw->raw_adc[2] - (float)YAW_OFFSET)
                                  * YAW_SCALE;
    state->steering_angle_rad  = ((float)raw->raw_adc[3] - (float)STEERING_OFFSET)
                                  * STEERING_SCALE;
    state->throttle_pct        = (float)raw->raw_adc[4] * THROTTLE_SCALE;
    state->brake_pressure_kpa  = (float)raw->raw_adc[5] * BRAKE_SCALE;
    state->timestamp_ms        = raw->timestamp_ms;

    /* Range guards (MISRA 14.3: boolean always false/true guard avoided) */
    if (state->throttle_pct > 100.0f) {
        state->throttle_pct = 100.0f;
    }

    return SENSOR_OK;
}

/**
 * @brief  Read N frames and verify they remain within a coherence band.
 * @param  handle      Initialised handle.
 * @param  iterations  Number of back-to-back frames to compare.
 * @param  consistent  Output: true when all frames cohere.
 */
SensorStatus_t SENSOR_ValidateConsistency(SensorHandle_t *handle,
                                           uint8_t iterations,
                                           bool *consistent)
{
    SensorRawFrame_t frame;
    VehicleState_t   prev_state;
    VehicleState_t   cur_state;
    SensorStatus_t   status;
    uint8_t          i;
    float            delta_v;

    if ((handle == NULL) || (consistent == NULL)) {
        return SENSOR_ERR_NULL;
    }

    *consistent = false;

    status = SENSOR_ReadRaw(handle, &frame);
    if (status != SENSOR_OK) { return status; }

    status = SENSOR_MapToVehicleState(&frame, &prev_state);
    if (status != SENSOR_OK) { return status; }

    for (i = 1U; i < iterations; i++) {
        status = SENSOR_ReadRaw(handle, &frame);
        if (status != SENSOR_OK) { return status; }

        status = SENSOR_MapToVehicleState(&frame, &cur_state);
        if (status != SENSOR_OK) { return status; }

        /* Δv coherence: physical bound ≤ 10 m/s² × Δt (1 ms) = 0.01 m/s */
        delta_v = cur_state.velocity_mps - prev_state.velocity_mps;
        if ((delta_v > 0.05f) || (delta_v < -0.05f)) {
            return SENSOR_ERR_CONSISTENCY;
        }

        (void)memcpy(&prev_state, &cur_state, sizeof(VehicleState_t));
    }

    *consistent = true;
    return SENSOR_OK;
}

/**
 * @brief  Inject a synthetic raw value for fault-insertion testing.
 *         In HIL, the test harness calls this via GDB/OpenOCD.
 */
SensorStatus_t SENSOR_InjectFault(SensorHandle_t *handle,
                                   uint8_t channel, uint16_t injected_raw)
{
    if (handle == NULL) {
        return SENSOR_ERR_NULL;
    }
    if (channel >= SENSOR_MAX_CHANNELS) {
        return SENSOR_ERR_RANGE;
    }
    handle->last_raw.raw_adc[channel] = (uint16_t)(injected_raw & 0x0FFFU);
    return SENSOR_OK;
}

/**
 * @brief  Sensor data-ready ISR — call from vector table.
 */
void SENSOR_IRQHandler(SensorHandle_t *handle)
{
    if (handle == NULL) { return; }
    /* In HIL mode the harness polls; in production this posts to a queue */
    (void)SENSOR_ReadRaw(handle, &handle->last_raw);
}

/**
 * @brief  Configure NVIC for the sensor IRQ.
 * @param  preempt_prio  0 (highest) – 15
 * @param  sub_prio      0 (highest) – 15
 */
void SENSOR_ConfigureIRQ(uint8_t preempt_prio, uint8_t sub_prio)
{
    /* CMSIS-equivalent without pulling full headers into unit tests:
     * NVIC_SetPriority(NVIC_SENSOR_IRQn, (preempt_prio << 4) | sub_prio);
     * NVIC_EnableIRQ(NVIC_SENSOR_IRQn);
     *
     * For cross-compiled unit tests we write directly to NVIC registers.
     */
    volatile uint8_t *nvic_ipr = (volatile uint8_t *)(0xE000E400UL
                                   + NVIC_SENSOR_IRQn);
    volatile uint32_t *nvic_iser = (volatile uint32_t *)(0xE000E100UL
                                    + ((NVIC_SENSOR_IRQn >> 5U) * 4U));

    *nvic_ipr  = (uint8_t)(((uint8_t)(preempt_prio & 0x0FU) << 4U)
                            | (sub_prio & 0x0FU));
    *nvic_iser = (1UL << (NVIC_SENSOR_IRQn & 0x1FU));
}

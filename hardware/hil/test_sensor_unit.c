/**
 * @file    test_sensor_unit.c
 * @brief   Firmware unit tests for HIL_004 — Sensor Data Validation
 *          Framework: Unity (lightweight, MISRA-friendly)
 *          Coverage target: ≥ 90 % line + branch
 *
 * Build:
 *   arm-none-eabi-gcc -DUNIT_TEST -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 \
 *       -mfloat-abi=hard -Os -Wall -Wextra -Wpedantic              \
 *       sensor_hal.c test_sensor_unit.c unity/unity.c              \
 *       -o test_sensor_unit.elf
 */
#include "sensor_hal.h"
#include "unity/unity.h"
#include <string.h>
#include <math.h>

/* ── Test fixture ────────────────────────────────────────────────────────── */
static SensorHandle_t  g_handle;
static SensorRawFrame_t g_frame;
static VehicleState_t   g_state;

/* ── Simulated peripheral memory (replaces hardware in unit test) ────────── */
static uint32_t g_fake_sr  = 0x0001U;   /* data ready */
static uint32_t g_fake_dr  = 0x8000U;   /* CRC-OK bit set, 0 data */
static uint32_t g_fake_cr1 = 0U;
static uint32_t g_fake_cr2 = 0x0006U;   /* 6 channels */

/* Override peripheral base to point at our fake registers:
 * In the unit-test build, SENSOR_REGS expands to &g_sensor_regs_sim         */
SensorPeriphRegs_t g_sensor_regs_sim = {0};

/* ── Unity lifecycle ─────────────────────────────────────────────────────── */
void setUp(void)
{
    (void)memset(&g_handle, 0, sizeof(g_handle));
    (void)memset(&g_frame,  0, sizeof(g_frame));
    (void)memset(&g_state,  0, sizeof(g_state));

    /* Prime fake peripheral */
    g_sensor_regs_sim.SR  = 0x0001U; /* data ready   */
    g_sensor_regs_sim.DR  = 0x8006U; /* CRC-OK, ch=6 */
    g_sensor_regs_sim.CR1 = 0U;
    g_sensor_regs_sim.CR2 = 0x0006U;
}

void tearDown(void) { /* nothing */ }

/* ══════════════════════════════════════════════════════════════════════════
 *  GROUP 1 — SENSOR_Init
 * ══════════════════════════════════════════════════════════════════════════ */

void test_init_null_handle_returns_err(void)
{
    SensorStatus_t s = SENSOR_Init(NULL);
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL, s);
}

void test_init_valid_handle_ok(void)
{
    SensorStatus_t s = SENSOR_Init(&g_handle);
    TEST_ASSERT_EQUAL(SENSOR_OK, s);
    TEST_ASSERT_TRUE(g_handle.initialised);
    TEST_ASSERT_EQUAL_UINT32(0U, g_handle.read_count);
    TEST_ASSERT_EQUAL_UINT32(0U, g_handle.error_count);
}

void test_init_clears_previous_state(void)
{
    g_handle.read_count  = 999U;
    g_handle.error_count = 5U;
    (void)SENSOR_Init(&g_handle);
    TEST_ASSERT_EQUAL_UINT32(0U, g_handle.read_count);
}

/* ══════════════════════════════════════════════════════════════════════════
 *  GROUP 2 — SENSOR_ReadRaw
 * ══════════════════════════════════════════════════════════════════════════ */

void test_read_null_handle_returns_err(void)
{
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL, SENSOR_ReadRaw(NULL, &g_frame));
}

void test_read_null_frame_returns_err(void)
{
    (void)SENSOR_Init(&g_handle);
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL, SENSOR_ReadRaw(&g_handle, NULL));
}

void test_read_uninitialised_returns_err(void)
{
    TEST_ASSERT_EQUAL(SENSOR_ERR_UNINIT, SENSOR_ReadRaw(&g_handle, &g_frame));
}

void test_read_increments_read_count(void)
{
    (void)SENSOR_Init(&g_handle);
    g_sensor_regs_sim.SR = 0x0001U;
    (void)SENSOR_ReadRaw(&g_handle, &g_frame);
    TEST_ASSERT_EQUAL_UINT32(1U, g_handle.read_count);
}

void test_read_data_valid_when_crc_bit_set(void)
{
    (void)SENSOR_Init(&g_handle);
    g_sensor_regs_sim.DR = 0x8000U; /* CRC-OK bit */
    (void)SENSOR_ReadRaw(&g_handle, &g_frame);
    TEST_ASSERT_TRUE(g_frame.data_valid);
}

void test_read_data_invalid_when_crc_bit_clear(void)
{
    (void)SENSOR_Init(&g_handle);
    g_sensor_regs_sim.DR = 0x0000U; /* no CRC-OK */
    (void)SENSOR_ReadRaw(&g_handle, &g_frame);
    TEST_ASSERT_FALSE(g_frame.data_valid);
}

void test_read_channel_count_capped_at_max(void)
{
    (void)SENSOR_Init(&g_handle);
    g_sensor_regs_sim.CR2 = 0xFFU; /* > SENSOR_MAX_CHANNELS */
    (void)SENSOR_ReadRaw(&g_handle, &g_frame);
    TEST_ASSERT_LESS_OR_EQUAL(SENSOR_MAX_CHANNELS, g_frame.channel_count);
}

/* ══════════════════════════════════════════════════════════════════════════
 *  GROUP 3 — SENSOR_MapToVehicleState  (HIL_004 core)
 * ══════════════════════════════════════════════════════════════════════════ */

static void build_valid_frame(SensorRawFrame_t *f,
                               uint16_t v, uint16_t a, uint16_t y,
                               uint16_t s, uint16_t t, uint16_t b)
{
    (void)memset(f, 0, sizeof(*f));
    f->raw_adc[0]    = v;
    f->raw_adc[1]    = a;
    f->raw_adc[2]    = y;
    f->raw_adc[3]    = s;
    f->raw_adc[4]    = t;
    f->raw_adc[5]    = b;
    f->channel_count = 6U;
    f->data_valid    = true;
}

void test_map_null_raw_returns_err(void)
{
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL, SENSOR_MapToVehicleState(NULL, &g_state));
}

void test_map_null_state_returns_err(void)
{
    build_valid_frame(&g_frame, 0, 2048, 2048, 2048, 0, 0);
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL, SENSOR_MapToVehicleState(&g_frame, NULL));
}

void test_map_invalid_data_returns_bus_err(void)
{
    build_valid_frame(&g_frame, 0, 2048, 2048, 2048, 0, 0);
    g_frame.data_valid = false;
    TEST_ASSERT_EQUAL(SENSOR_ERR_BUS, SENSOR_MapToVehicleState(&g_frame, &g_state));
}

void test_map_too_few_channels_returns_range_err(void)
{
    build_valid_frame(&g_frame, 0, 2048, 2048, 2048, 0, 0);
    g_frame.channel_count = 3U; /* below minimum 6 */
    TEST_ASSERT_EQUAL(SENSOR_ERR_RANGE, SENSOR_MapToVehicleState(&g_frame, &g_state));
}

void test_map_zero_velocity_raw_gives_zero_mps(void)
{
    build_valid_frame(&g_frame, 0U, 2048U, 2048U, 2048U, 0U, 0U);
    (void)SENSOR_MapToVehicleState(&g_frame, &g_state);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.0f, g_state.velocity_mps);
}

void test_map_full_scale_velocity(void)
{
    build_valid_frame(&g_frame, 4095U, 2048U, 2048U, 2048U, 0U, 0U);
    (void)SENSOR_MapToVehicleState(&g_frame, &g_state);
    /* 4095 × 0.08789 ≈ 360 km/h = 100 m/s */
    TEST_ASSERT_FLOAT_WITHIN(0.5f, 100.0f, g_state.velocity_mps);
}

void test_map_midscale_accel_gives_zero(void)
{
    build_valid_frame(&g_frame, 0U, 2048U, 2048U, 2048U, 0U, 0U);
    (void)SENSOR_MapToVehicleState(&g_frame, &g_state);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.0f, g_state.acceleration_mps2);
}

void test_map_full_scale_accel_positive(void)
{
    build_valid_frame(&g_frame, 0U, 4095U, 2048U, 2048U, 0U, 0U);
    (void)SENSOR_MapToVehicleState(&g_frame, &g_state);
    TEST_ASSERT_GREATER_THAN_FLOAT(0.0f, g_state.acceleration_mps2);
}

void test_map_throttle_capped_at_100(void)
{
    /* ADC value that would exceed 100% due to scaling */
    build_valid_frame(&g_frame, 0U, 2048U, 2048U, 2048U, 4095U, 0U);
    (void)SENSOR_MapToVehicleState(&g_frame, &g_state);
    TEST_ASSERT_LESS_OR_EQUAL_FLOAT(100.0f, g_state.throttle_pct);
}

void test_map_zero_throttle(void)
{
    build_valid_frame(&g_frame, 0U, 2048U, 2048U, 2048U, 0U, 0U);
    (void)SENSOR_MapToVehicleState(&g_frame, &g_state);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.0f, g_state.throttle_pct);
}

void test_map_timestamp_propagated(void)
{
    build_valid_frame(&g_frame, 0U, 2048U, 2048U, 2048U, 0U, 0U);
    g_frame.timestamp_ms = 12345U;
    (void)SENSOR_MapToVehicleState(&g_frame, &g_state);
    TEST_ASSERT_EQUAL_UINT32(12345U, g_state.timestamp_ms);
}

/* ══════════════════════════════════════════════════════════════════════════
 *  GROUP 4 — SENSOR_ValidateConsistency (HIL_004 multi-iteration)
 * ══════════════════════════════════════════════════════════════════════════ */

void test_consistency_null_handle(void)
{
    bool ok = false;
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL, SENSOR_ValidateConsistency(NULL, 3U, &ok));
}

void test_consistency_null_output(void)
{
    (void)SENSOR_Init(&g_handle);
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL,
                      SENSOR_ValidateConsistency(&g_handle, 3U, NULL));
}

/* ══════════════════════════════════════════════════════════════════════════
 *  GROUP 5 — SENSOR_InjectFault
 * ══════════════════════════════════════════════════════════════════════════ */

void test_fault_inject_null_handle(void)
{
    TEST_ASSERT_EQUAL(SENSOR_ERR_NULL, SENSOR_InjectFault(NULL, 0U, 0U));
}

void test_fault_inject_invalid_channel(void)
{
    (void)SENSOR_Init(&g_handle);
    TEST_ASSERT_EQUAL(SENSOR_ERR_RANGE,
                      SENSOR_InjectFault(&g_handle, SENSOR_MAX_CHANNELS, 0U));
}

void test_fault_inject_value_stored(void)
{
    (void)SENSOR_Init(&g_handle);
    (void)SENSOR_InjectFault(&g_handle, 0U, 1234U);
    TEST_ASSERT_EQUAL_UINT16(1234U, g_handle.last_raw.raw_adc[0]);
}

void test_fault_inject_only_12_bits_stored(void)
{
    (void)SENSOR_Init(&g_handle);
    (void)SENSOR_InjectFault(&g_handle, 1U, 0xFFFFU);
    TEST_ASSERT_EQUAL_UINT16(0x0FFFU, g_handle.last_raw.raw_adc[1]);
}

/* ══════════════════════════════════════════════════════════════════════════
 *  GROUP 6 — IRQ / NVIC config (timing / priority)
 * ══════════════════════════════════════════════════════════════════════════ */

void test_irq_handler_null_safe(void)
{
    /* Must not crash */
    SENSOR_IRQHandler(NULL);
    TEST_PASS();
}

void test_configure_irq_does_not_fault(void)
{
    /* Verify no hard-fault; in unit-test build NVIC mem is mapped to host */
    SENSOR_ConfigureIRQ(5U, 0U);
    TEST_PASS();
}

/* ══════════════════════════════════════════════════════════════════════════
 *  main
 * ══════════════════════════════════════════════════════════════════════════ */
int main(void)
{
    UNITY_BEGIN();

    /* Init */
    RUN_TEST(test_init_null_handle_returns_err);
    RUN_TEST(test_init_valid_handle_ok);
    RUN_TEST(test_init_clears_previous_state);

    /* ReadRaw */
    RUN_TEST(test_read_null_handle_returns_err);
    RUN_TEST(test_read_null_frame_returns_err);
    RUN_TEST(test_read_uninitialised_returns_err);
    RUN_TEST(test_read_increments_read_count);
    RUN_TEST(test_read_data_valid_when_crc_bit_set);
    RUN_TEST(test_read_data_invalid_when_crc_bit_clear);
    RUN_TEST(test_read_channel_count_capped_at_max);

    /* Map (HIL_004 core) */
    RUN_TEST(test_map_null_raw_returns_err);
    RUN_TEST(test_map_null_state_returns_err);
    RUN_TEST(test_map_invalid_data_returns_bus_err);
    RUN_TEST(test_map_too_few_channels_returns_range_err);
    RUN_TEST(test_map_zero_velocity_raw_gives_zero_mps);
    RUN_TEST(test_map_full_scale_velocity);
    RUN_TEST(test_map_midscale_accel_gives_zero);
    RUN_TEST(test_map_full_scale_accel_positive);
    RUN_TEST(test_map_throttle_capped_at_100);
    RUN_TEST(test_map_zero_throttle);
    RUN_TEST(test_map_timestamp_propagated);

    /* Consistency */
    RUN_TEST(test_consistency_null_handle);
    RUN_TEST(test_consistency_null_output);

    /* Fault injection */
    RUN_TEST(test_fault_inject_null_handle);
    RUN_TEST(test_fault_inject_invalid_channel);
    RUN_TEST(test_fault_inject_value_stored);
    RUN_TEST(test_fault_inject_only_12_bits_stored);

    /* IRQ */
    RUN_TEST(test_irq_handler_null_safe);
    RUN_TEST(test_configure_irq_does_not_fault);

    return UNITY_END();
}

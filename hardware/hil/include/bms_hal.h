#ifndef BMS_HAL_H
#define BMS_HAL_H

#include "bms_types.h"

/* ── HAL initialisation ─────────────────────────────────────────────── */
bms_status_t bms_hal_init(const bms_config_t *cfg);
bms_status_t bms_hal_deinit(void);

/* ── ADC / measurement ──────────────────────────────────────────────── */
bms_status_t bms_hal_read_cell_voltages(uint16_t *out_mv, uint8_t count);
bms_status_t bms_hal_read_temperatures(int16_t *out_degc_x10, uint8_t count);
bms_status_t bms_hal_read_pack_current(int32_t *out_ma);

/* ── Contactor / balancer control ───────────────────────────────────── */
bms_status_t bms_hal_set_main_contactor(bool enable);
bms_status_t bms_hal_set_precharge_relay(bool enable);
bms_status_t bms_hal_set_cell_balance(uint16_t cell_mask);

/* ── Timing ─────────────────────────────────────────────────────────── */
uint32_t     bms_hal_get_tick_ms(void);
void         bms_hal_delay_ms(uint32_t ms);

/* ── Fault latch ────────────────────────────────────────────────────── */
void         bms_hal_assert_fault(bms_fault_t fault);
void         bms_hal_clear_fault(bms_fault_t fault);
uint32_t     bms_hal_get_fault_flags(void);

/* ── CAN transport ──────────────────────────────────────────────────── */
bms_status_t bms_hal_can_send(uint32_t id, const uint8_t *data, uint8_t len);
bms_status_t bms_hal_can_recv(uint32_t *id, uint8_t *data, uint8_t *len,
                              uint32_t timeout_ms);

/* ── Watchdog ────────────────────────────────────────────────────────── */
void         bms_hal_watchdog_kick(void);

#endif /* BMS_HAL_H */

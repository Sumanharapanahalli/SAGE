/**
 * @file bsp_stub.c
 * @brief BSP (Board Support Package) stubs for host-native unit tests.
 *
 * These replace the real hardware HAL calls so the algorithm can be tested
 * on a development machine without target hardware.
 *
 * Do NOT ship this file in device firmware.
 */

#include <stdint.h>
#include <string.h>
#include <stdio.h>

/* =========================================================================
 * fall_detection.c BSP
 * ========================================================================= */
/* bsp_get_time_ms is provided by each test file via a static override */

/* =========================================================================
 * ota_update.c BSP stubs
 * ========================================================================= */
static uint8_t s_flash[2][512 * 1024]; /* 512KB × 2 banks */
static uint8_t s_boot_bank = 0u;
static uint8_t s_rollback_count = 0u;

int bsp_flash_erase_bank(uint8_t bank)
{
    if (bank > 1u) { return -1; }
    memset(s_flash[bank], 0xFF, sizeof(s_flash[bank]));
    return 0;
}

int bsp_flash_write(uint8_t bank, uint32_t offset,
                     const uint8_t *data, uint32_t len)
{
    if (bank > 1u) { return -1; }
    if (offset + len > sizeof(s_flash[bank])) { return -1; }
    memcpy(&s_flash[bank][offset], data, len);
    return 0;
}

int bsp_flash_read(uint8_t bank, uint32_t offset,
                    uint8_t *buf, uint32_t len)
{
    if (bank > 1u) { return -1; }
    if (offset + len > sizeof(s_flash[bank])) { return -1; }
    memcpy(buf, &s_flash[bank][offset], len);
    return 0;
}

void    bsp_set_boot_bank(uint8_t bank)     { s_boot_bank = bank; }
uint8_t bsp_get_boot_bank(void)             { return s_boot_bank; }
uint8_t bsp_get_rollback_count(void)        { return s_rollback_count; }
void    bsp_set_rollback_count(uint8_t n)   { s_rollback_count = n; }
void    bsp_reboot(void)                    { /* no-op in tests */ }

/* =========================================================================
 * watchdog.c BSP stubs
 * ========================================================================= */
static uint32_t s_reset_flags = 0u;
static int      s_reset_triggered = 0;

int     bsp_iwdg_init(uint32_t timeout_ms)  { (void)timeout_ms; return 0; }
void    bsp_iwdg_kick(void)                 { /* no-op */ }
void    bsp_iwdg_lock(void)                 { /* no-op */ }

uint32_t bsp_read_reset_flags(void)         { return s_reset_flags; }
void     bsp_clear_reset_flags(void)        { s_reset_flags = 0u; }
void     bsp_system_reset(void)             { s_reset_triggered = 1; }

void bsp_log(const char *msg)
{
    printf("[BSP LOG] %s\n", msg);
}

/* =========================================================================
 * Test helpers (callable from test files)
 * ========================================================================= */
void bsp_stub_set_reset_flags(uint32_t flags) { s_reset_flags = flags; }
int  bsp_stub_was_reset_triggered(void)       { return s_reset_triggered; }
void bsp_stub_clear_reset_triggered(void)     { s_reset_triggered = 0; }

/**
 * @file hil_test_interface.c
 * @brief Hardware-in-the-Loop UART test command interface.
 *
 * Provides a line-oriented ASCII command protocol over UART1 (115200 8N1)
 * used by the pytest/pyserial HIL test harness.  Commands are idempotent
 * and do NOT affect the production code paths — they inject stimuli and
 * query state only through the existing module APIs.
 *
 * Protocol:
 *   Request : <CMD> [ARGS...]\n
 *   Response: OK <data>\n   | ERR <code> <message>\n
 *
 * Command set (see hil_cmd_table[]):
 *   PING                     -> OK PONG
 *   INJECT_ACCEL <ax> <ay> <az> <gx> <gy> <gz>
 *                            -> OK INJECTED
 *   REPLAY_START <num_samples> -> OK READY
 *   REPLAY_SAMPLE <ax> <ay> <az> <gx> <gy> <gz>
 *                            -> OK | ERR
 *   REPLAY_END               -> OK DONE <detected:0|1> <latency_ms>
 *   GET_STATE                -> OK FALL_STATE=<n> LTE_STATE=<n> GPS_STATE=<n>
 *   GET_POWER_STATE          -> OK POWER=<SLEEP|ACTIVE> TICK=<uptime_ms>
 *   FORCE_SLEEP              -> OK
 *   FORCE_ACTIVE             -> OK
 *   GET_CURRENT_MARKERS      -> OK BEFORE=<tick_ms> AFTER=<tick_ms>
 *   RESET_FALL_COUNT         -> OK
 *   GET_FALL_COUNT           -> OK COUNT=<n>
 *   TRIGGER_WATCHDOG_TEST    -> OK (watchdog feed suspended for 2 s)
 *   GET_LTE_LATENCY          -> OK LATENCY_MS=<n>   (last alert round-trip)
 *   GET_GPS_FIX_TIME         -> OK FIX_MS=<n>        (last acquisition time)
 *   VERSION                  -> OK HW=<str> FW=<str>
 *
 * IEC 62304 traceability: STS-HIL-001 .. STS-HIL-014
 *
 * @version 1.0.0
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/logging/log.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>

#include "../include/fall_detection.h"
#include "../include/lte_module.h"
#include "../include/gps_module.h"
#include "../include/app_events.h"

LOG_MODULE_REGISTER(hil_iface, LOG_LEVEL_DBG);

/* -------------------------------------------------------------------------
 * Build-time guard — HIL interface compiled only in test builds
 * ------------------------------------------------------------------------- */
#ifndef CONFIG_HIL_TEST_INTERFACE
#error "hil_test_interface.c must not be included in production builds. " \
       "Enable CONFIG_HIL_TEST_INTERFACE=y in test prj.conf only."
#endif

/* -------------------------------------------------------------------------
 * UART configuration
 * ------------------------------------------------------------------------- */
#define HIL_UART_NODE         DT_ALIAS(hil_uart)
#define HIL_UART_BAUD         115200U
#define HIL_RX_BUF_SIZE       256U
#define HIL_TX_BUF_SIZE       256U
#define HIL_CMD_MAX_ARGS      8U
#define HIL_REPLAY_MAX_SAMPLES 1024U

static const struct device *s_hil_uart;

/* -------------------------------------------------------------------------
 * Receive state machine
 * ------------------------------------------------------------------------- */
static volatile char     s_rx_buf[HIL_RX_BUF_SIZE];
static volatile uint16_t s_rx_idx;
static volatile bool     s_line_ready;

/* -------------------------------------------------------------------------
 * Replay buffer (populated by REPLAY_SAMPLE commands)
 * ------------------------------------------------------------------------- */
typedef struct accel_sample {
    int16_t ax_mg;
    int16_t ay_mg;
    int16_t az_mg;
    int16_t gx_mdps; /* milli-degrees/s */
    int16_t gy_mdps;
    int16_t gz_mdps;
} accel_sample_t;

static accel_sample_t s_replay_buf[HIL_REPLAY_MAX_SAMPLES];
static uint16_t       s_replay_expected;
static uint16_t       s_replay_received;
static bool           s_replay_active;

/* Detection result from last REPLAY_END */
static bool     s_last_detected;
static uint32_t s_last_latency_ms;

/* -------------------------------------------------------------------------
 * Power state markers (for current probe synchronisation)
 * ------------------------------------------------------------------------- */
static volatile uint32_t s_marker_before_ms;
static volatile uint32_t s_marker_after_ms;

/* -------------------------------------------------------------------------
 * Forward declarations
 * ------------------------------------------------------------------------- */
static void hil_uart_isr(const struct device *dev, void *user_data);
static void hil_process_line(char *line);
static void hil_send(const char *fmt, ...);

/* -------------------------------------------------------------------------
 * Command handlers
 * ------------------------------------------------------------------------- */
static void cmd_ping(char **argv, int argc)
{
    ARG_UNUSED(argv);
    ARG_UNUSED(argc);
    hil_send("OK PONG\n");
}

static void cmd_version(char **argv, int argc)
{
    ARG_UNUSED(argv);
    ARG_UNUSED(argc);
    hil_send("OK HW=nRF5340-WFD-v1 FW=%s\n", CONFIG_APP_VERSION);
}

static void cmd_inject_accel(char **argv, int argc)
{
    if (argc < 7) {
        hil_send("ERR 1 INJECT_ACCEL requires 6 args: ax ay az gx gy gz\n");
        return;
    }
    accel_sample_t s = {
        .ax_mg   = (int16_t)atoi(argv[1]),
        .ay_mg   = (int16_t)atoi(argv[2]),
        .az_mg   = (int16_t)atoi(argv[3]),
        .gx_mdps = (int16_t)atoi(argv[4]),
        .gy_mdps = (int16_t)atoi(argv[5]),
        .gz_mdps = (int16_t)atoi(argv[6]),
    };
    /* Inject directly into fall detection processing queue */
    extern int fall_detection_inject_sample(const accel_sample_t *p_sample);
    int rc = fall_detection_inject_sample(&s);
    if (rc == 0) {
        hil_send("OK INJECTED\n");
    } else {
        hil_send("ERR %d INJECT_FAILED\n", rc);
    }
}

static void cmd_replay_start(char **argv, int argc)
{
    if (argc < 2) {
        hil_send("ERR 1 REPLAY_START requires num_samples\n");
        return;
    }
    uint16_t n = (uint16_t)atoi(argv[1]);
    if (n == 0U || n > HIL_REPLAY_MAX_SAMPLES) {
        hil_send("ERR 2 num_samples out of range [1..%u]\n",
                 HIL_REPLAY_MAX_SAMPLES);
        return;
    }
    s_replay_expected = n;
    s_replay_received = 0U;
    s_replay_active   = true;
    s_last_detected   = false;
    s_last_latency_ms = 0U;
    hil_send("OK READY\n");
}

static void cmd_replay_sample(char **argv, int argc)
{
    if (!s_replay_active) {
        hil_send("ERR 3 REPLAY_START not called\n");
        return;
    }
    if (argc < 7) {
        hil_send("ERR 1 REPLAY_SAMPLE requires 6 args\n");
        return;
    }
    if (s_replay_received >= s_replay_expected) {
        hil_send("ERR 4 Buffer full — call REPLAY_END first\n");
        return;
    }
    accel_sample_t *p = &s_replay_buf[s_replay_received];
    p->ax_mg   = (int16_t)atoi(argv[1]);
    p->ay_mg   = (int16_t)atoi(argv[2]);
    p->az_mg   = (int16_t)atoi(argv[3]);
    p->gx_mdps = (int16_t)atoi(argv[4]);
    p->gy_mdps = (int16_t)atoi(argv[5]);
    p->gz_mdps = (int16_t)atoi(argv[6]);
    s_replay_received++;
    hil_send("OK\n");
}

static void cmd_replay_end(char **argv, int argc)
{
    ARG_UNUSED(argv);
    ARG_UNUSED(argc);
    if (!s_replay_active) {
        hil_send("ERR 3 REPLAY_START not called\n");
        return;
    }
    s_replay_active = false;

    extern int fall_detection_replay(const accel_sample_t *p_buf,
                                     uint16_t              num_samples,
                                     bool                 *p_detected,
                                     uint32_t             *p_latency_ms);
    int rc = fall_detection_replay(s_replay_buf,
                                   s_replay_received,
                                   &s_last_detected,
                                   &s_last_latency_ms);
    if (rc != 0) {
        hil_send("ERR %d REPLAY_EXEC_FAILED\n", rc);
        return;
    }
    hil_send("OK DONE DETECTED=%d LATENCY_MS=%u\n",
             (int)s_last_detected, (unsigned)s_last_latency_ms);
}

static void cmd_get_state(char **argv, int argc)
{
    ARG_UNUSED(argv);
    ARG_UNUSED(argc);
    hil_send("OK FALL_STATE=%d LTE_STATE=%d GPS_STATE=%d\n",
             (int)fall_detection_get_state(),
             (int)lte_module_get_state(),
             (int)gps_module_get_state());
}

static void cmd_get_power_state(char **argv, int argc)
{
    ARG_UNUSED(argv);
    ARG_UNUSED(argc);
    extern bool power_mgr_is_sleep_active(void);
    bool sleeping = power_mgr_is_sleep_active();
    hil_send("OK POWER=%s TICK=%u\n",
             sleeping ? "SLEEP" : "ACTIVE",
             (unsigned)k_uptime_get_32());
}

static void cmd_force_sleep(char **argv, int argc)
{
    ARG_UNUSED(argv);
    ARG_UNUSED(argc);
    extern int power_mgr_force_sleep(void);
    s_marker_before_ms = k_uptime_get_32();
    int rc = power_mgr_force_sleep();
    s_marker_after_ms  = k_uptime_get_32();
    if (rc == 0) {
        hil_send("OK\n");
    } else {
        hil_send("ERR %d FORCE_SLEEP_FAILED\n", rc);
    }
}

static void cmd_force_active(char **argv, int argc)
{
    ARG_UNUSED(argv);
    ARG_UNUSED(argc);
    extern int power_mgr_force_active(void);
    s_marker_before_ms = k_uptime_get_32();
    int rc = power_mgr_force_active();
    s_marker_after_ms  = k_uptime_get_32();
    if (rc == 0) {
        hil_send("OK\n");
    } else {
        hil_send("ERR %d FORCE_ACTIVE_FAILED\n", rc);
    }
}

static void cmd_get_current_markers(char **argv, int argc)
{
    ARG_UNUSED(argv);
    ARG_UNUSED(argc);
    hil_send("OK BEFORE=%u AFTER=%u\n",
             (unsigned)s_marker_before_ms,
             (unsigned)s_marker_after_ms);
}

static void cmd_reset_fall_count(char **argv, int argc)
{
    ARG_UNUSED(argv);
    ARG_UNUSED(argc);
    extern void fall_detection_reset_count(void);
    fall_detection_reset_count();
    hil_send("OK\n");
}

static void cmd_get_fall_count(char **argv, int argc)
{
    ARG_UNUSED(argv);
    ARG_UNUSED(argc);
    hil_send("OK COUNT=%u\n", (unsigned)fall_detection_count());
}

static void cmd_trigger_watchdog_test(char **argv, int argc)
{
    ARG_UNUSED(argv);
    ARG_UNUSED(argc);
    extern void watchdog_test_suspend_feed(uint32_t duration_ms);
    /* Suspend WDG feed for 2 s — device should reset; HIL verifies recovery */
    watchdog_test_suspend_feed(2000U);
    hil_send("OK\n");
}

static void cmd_get_lte_latency(char **argv, int argc)
{
    ARG_UNUSED(argv);
    ARG_UNUSED(argc);
    extern uint32_t lte_module_get_last_alert_latency_ms(void);
    hil_send("OK LATENCY_MS=%u\n",
             (unsigned)lte_module_get_last_alert_latency_ms());
}

static void cmd_get_gps_fix_time(char **argv, int argc)
{
    ARG_UNUSED(argv);
    ARG_UNUSED(argc);
    extern uint32_t gps_module_get_last_fix_time_ms(void);
    hil_send("OK FIX_MS=%u\n",
             (unsigned)gps_module_get_last_fix_time_ms());
}

/* -------------------------------------------------------------------------
 * Command dispatch table
 * ------------------------------------------------------------------------- */
typedef struct hil_cmd {
    const char *name;
    void (*handler)(char **argv, int argc);
} hil_cmd_t;

static const hil_cmd_t s_cmd_table[] = {
    { "PING",                 cmd_ping                },
    { "VERSION",              cmd_version             },
    { "INJECT_ACCEL",         cmd_inject_accel        },
    { "REPLAY_START",         cmd_replay_start        },
    { "REPLAY_SAMPLE",        cmd_replay_sample       },
    { "REPLAY_END",           cmd_replay_end          },
    { "GET_STATE",            cmd_get_state           },
    { "GET_POWER_STATE",      cmd_get_power_state     },
    { "FORCE_SLEEP",          cmd_force_sleep         },
    { "FORCE_ACTIVE",         cmd_force_active        },
    { "GET_CURRENT_MARKERS",  cmd_get_current_markers },
    { "RESET_FALL_COUNT",     cmd_reset_fall_count    },
    { "GET_FALL_COUNT",       cmd_get_fall_count      },
    { "TRIGGER_WATCHDOG_TEST",cmd_trigger_watchdog_test },
    { "GET_LTE_LATENCY",      cmd_get_lte_latency     },
    { "GET_GPS_FIX_TIME",     cmd_get_gps_fix_time    },
};
#define HIL_CMD_COUNT (sizeof(s_cmd_table) / sizeof(s_cmd_table[0]))

/* -------------------------------------------------------------------------
 * Line parser
 * ------------------------------------------------------------------------- */
static void hil_process_line(char *line)
{
    if (line == NULL) {
        return;
    }
    /* Trim CR */
    size_t len = strlen(line);
    if (len > 0U && line[len - 1U] == '\r') {
        line[len - 1U] = '\0';
    }
    if (line[0] == '\0') {
        return;
    }

    char  *argv[HIL_CMD_MAX_ARGS];
    int    argc = 0;
    char  *tok  = strtok(line, " \t");
    while (tok != NULL && argc < (int)HIL_CMD_MAX_ARGS) {
        argv[argc++] = tok;
        tok = strtok(NULL, " \t");
    }
    if (argc == 0) {
        return;
    }

    for (uint32_t i = 0U; i < HIL_CMD_COUNT; i++) {
        if (strcmp(argv[0], s_cmd_table[i].name) == 0) {
            s_cmd_table[i].handler(argv, argc);
            return;
        }
    }
    hil_send("ERR 99 UNKNOWN_CMD %s\n", argv[0]);
}

/* -------------------------------------------------------------------------
 * UART ISR — accumulate bytes until '\n'
 * ------------------------------------------------------------------------- */
static void hil_uart_isr(const struct device *dev, void *user_data)
{
    ARG_UNUSED(user_data);
    if (dev == NULL) {
        return;
    }
    uart_irq_update(dev);
    if (!uart_irq_rx_ready(dev)) {
        return;
    }
    uint8_t byte;
    while (uart_fifo_read(dev, &byte, 1) == 1) {
        if (s_rx_idx < (HIL_RX_BUF_SIZE - 1U)) {
            s_rx_buf[s_rx_idx++] = (char)byte;
        }
        if (byte == (uint8_t)'\n') {
            s_rx_buf[s_rx_idx] = '\0';
            s_line_ready = true;
            break;
        }
    }
}

/* -------------------------------------------------------------------------
 * TX helper
 * ------------------------------------------------------------------------- */
static void hil_send(const char *fmt, ...)
{
    char   buf[HIL_TX_BUF_SIZE];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintk(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (n <= 0) {
        return;
    }
    for (int i = 0; i < n; i++) {
        uart_poll_out(s_hil_uart, (unsigned char)buf[i]);
    }
}

/* -------------------------------------------------------------------------
 * Thread
 * ------------------------------------------------------------------------- */
#define HIL_THREAD_STACK_SIZE 2048U
#define HIL_THREAD_PRIORITY   5

K_THREAD_STACK_DEFINE(s_hil_stack, HIL_THREAD_STACK_SIZE);
static struct k_thread s_hil_thread;

static void hil_thread_fn(void *p1, void *p2, void *p3)
{
    ARG_UNUSED(p1);
    ARG_UNUSED(p2);
    ARG_UNUSED(p3);
    LOG_INF("HIL test interface ready");
    hil_send("OK BOOT FW=%s\n", CONFIG_APP_VERSION);

    for (;;) {
        if (s_line_ready) {
            char local_buf[HIL_RX_BUF_SIZE];
            unsigned int key = irq_lock();
            memcpy(local_buf, (const char *)s_rx_buf, s_rx_idx + 1U);
            s_rx_idx    = 0U;
            s_line_ready = false;
            irq_unlock(key);
            hil_process_line(local_buf);
        }
        k_sleep(K_MSEC(1));
    }
}

/* -------------------------------------------------------------------------
 * Public init
 * ------------------------------------------------------------------------- */
int hil_test_interface_init(void)
{
    s_hil_uart = DEVICE_DT_GET(HIL_UART_NODE);
    if (!device_is_ready(s_hil_uart)) {
        LOG_ERR("HIL UART device not ready");
        return -ENODEV;
    }

    uart_irq_callback_user_data_set(s_hil_uart, hil_uart_isr, NULL);
    uart_irq_rx_enable(s_hil_uart);

    k_thread_create(&s_hil_thread,
                    s_hil_stack,
                    K_THREAD_STACK_SIZEOF(s_hil_stack),
                    hil_thread_fn,
                    NULL, NULL, NULL,
                    HIL_THREAD_PRIORITY,
                    0,
                    K_NO_WAIT);
    k_thread_name_set(&s_hil_thread, "hil_iface");
    return 0;
}

SYS_INIT(hil_test_interface_init, APPLICATION, CONFIG_APPLICATION_INIT_PRIORITY + 1);

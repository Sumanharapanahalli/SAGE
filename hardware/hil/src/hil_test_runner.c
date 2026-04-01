/**
 * @file     hil_test_runner.c
 * @brief    HIL test orchestrator — runs all test suites sequentially,
 *           reports per-suite pass/fail, emits a binary result word over
 *           UART (magic word + JSON summary) readable by the Python harness.
 *
 * Execution model:
 *   main() → HIL_RunAllSuites() → per-suite runners
 *   Each suite returns HIL_Result_t; final word written to
 *   a well-known RAM address so GDB can read it without UART.
 *
 * Memory map sentinel (linker script symbol __hil_result__):
 *   0x2000_0000 : uint32_t hil_magic  (HIL_LOG_MAGIC_PASS / FAIL)
 *   0x2000_0004 : uint32_t suite_pass_mask
 *   0x2000_0008 : uint32_t suite_fail_mask
 *   0x2000_000C : uint32_t total_assertions
 *   0x2000_0010 : uint32_t failed_assertions
 *
 * MISRA-C:2012 — Rules 15.5, 17.7 observed.
 */

#include "hil_config.h"
#include "hil_test_runner.h"
#include "hil_sensor_tests.h"
#include "hil_actuator_tests.h"
#include "hil_fault_injection.h"
#include "hil_timing_tests.h"
#include "hil_comms_tests.h"

#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>

/* ---------------------------------------------------------------------------
 * Result sentinel — placed at a fixed RAM address for GDB readout
 * -------------------------------------------------------------------------*/
__attribute__((section(".hil_result"), used))
volatile HIL_ResultBlock_t g_hil_result_block;

/* ---------------------------------------------------------------------------
 * Internal counters (all 32-bit to avoid MISRA essential-type violations)
 * -------------------------------------------------------------------------*/
static uint32_t s_total_assertions  = 0U;
static uint32_t s_failed_assertions = 0U;
static uint32_t s_pass_mask         = 0U;
static uint32_t s_fail_mask         = 0U;

/* ---------------------------------------------------------------------------
 * Assertion helper — records result, emits UART diagnostic
 * -------------------------------------------------------------------------*/
void HIL_Assert(bool condition, const char *p_test_name, uint32_t line)
{
    if (p_test_name == NULL) {
        return; /* MISRA 15.5 — single exit point deferred to caller */
    }
    s_total_assertions++;
    if (!condition) {
        s_failed_assertions++;
        /* Semihosting / UART log */
        (void)printf("[FAIL] %s  line=%lu\r\n", p_test_name, (unsigned long)line);
    }
}

/* ---------------------------------------------------------------------------
 * Suite registration table
 * -------------------------------------------------------------------------*/
typedef HIL_Result_t (*HIL_SuiteFn_t)(HIL_SuiteReport_t *p_report);

typedef struct {
    const char      *p_name;
    HIL_SuiteFn_t    fn;
    uint32_t         bit;       /* bit index in pass/fail mask */
} HIL_SuiteEntry_t;

static const HIL_SuiteEntry_t k_suites[] = {
    { "sensor_init",     HIL_SensorInitSuite,     0U },
    { "sensor_cal",      HIL_SensorCalSuite,      1U },
    { "actuator_resp",   HIL_ActuatorRespSuite,   2U },
    { "fault_inject",    HIL_FaultInjectionSuite, 3U },
    { "timing_budget",   HIL_TimingBudgetSuite,   4U },
    { "comms_ble",       HIL_CommsBleSuite,       5U },
    { "comms_modem",     HIL_CommsModemSuite,     6U },
    { "power_mgmt",      HIL_PowerMgmtSuite,      7U },
};

#define HIL_SUITE_COUNT  ((uint32_t)(sizeof(k_suites) / sizeof(k_suites[0U])))

/* ---------------------------------------------------------------------------
 * Public: run every suite, populate result block
 * -------------------------------------------------------------------------*/
HIL_Result_t HIL_RunAllSuites(void)
{
    HIL_Result_t     final_result = HIL_RESULT_PASS;
    HIL_SuiteReport_t report;
    uint32_t          i;

    /* Zero the sentinel block before starting */
    (void)memset((void *)&g_hil_result_block, 0,
                 sizeof(HIL_ResultBlock_t));

    for (i = 0U; i < HIL_SUITE_COUNT; i++) {
        if (k_suites[i].fn == NULL) {
            continue;
        }

        (void)memset(&report, 0, sizeof(HIL_SuiteReport_t));
        report.p_suite_name = k_suites[i].p_name;

        HIL_Result_t suite_result = k_suites[i].fn(&report);

        if (suite_result == HIL_RESULT_PASS) {
            s_pass_mask |= (1U << k_suites[i].bit);
            (void)printf("[SUITE PASS] %s  assertions=%lu\r\n",
                         k_suites[i].p_name,
                         (unsigned long)report.assertions_run);
        } else {
            s_fail_mask  |= (1U << k_suites[i].bit);
            final_result  = suite_result;
            (void)printf("[SUITE FAIL] %s  result=%d  failed=%lu/%lu\r\n",
                         k_suites[i].p_name,
                         (int)suite_result,
                         (unsigned long)report.assertions_failed,
                         (unsigned long)report.assertions_run);
        }

        s_total_assertions  += report.assertions_run;
        s_failed_assertions += report.assertions_failed;
    }

    /* Populate GDB-readable sentinel */
    g_hil_result_block.magic             =
        (final_result == HIL_RESULT_PASS) ? HIL_LOG_MAGIC_PASS
                                          : HIL_LOG_MAGIC_FAIL;
    g_hil_result_block.suite_pass_mask   = s_pass_mask;
    g_hil_result_block.suite_fail_mask   = s_fail_mask;
    g_hil_result_block.total_assertions  = s_total_assertions;
    g_hil_result_block.failed_assertions = s_failed_assertions;

    /* Final summary line — Python harness parses "HIL_DONE:" prefix */
    (void)printf("HIL_DONE: pass=%lu fail=%lu suites_ok=0x%08lX suites_fail=0x%08lX\r\n",
                 (unsigned long)(s_total_assertions - s_failed_assertions),
                 (unsigned long)s_failed_assertions,
                 (unsigned long)s_pass_mask,
                 (unsigned long)s_fail_mask);

    return final_result;
}

/* ---------------------------------------------------------------------------
 * Main entry point (runs standalone on target, bypasses RTOS for HIL)
 * -------------------------------------------------------------------------*/
int main(void)
{
    /* Minimal HAL init — clocks, SysTick, UART for semihosting */
    HIL_BSP_Init();

    HIL_Result_t result = HIL_RunAllSuites();

    /* Spin — GDB reads result block via 'x/5xw &g_hil_result_block' */
    for (;;) {
        if (result == HIL_RESULT_PASS) {
            HIL_BSP_LedSet(HIL_LED_GREEN, true);
        } else {
            HIL_BSP_LedSet(HIL_LED_RED, true);
        }
        HIL_BSP_DelayMs(500U);
        HIL_BSP_LedSet(HIL_LED_GREEN, false);
        HIL_BSP_LedSet(HIL_LED_RED,   false);
        HIL_BSP_DelayMs(500U);
    }

    /* Unreachable — satisfies MISRA Rule 15.5 */
    return (result == HIL_RESULT_PASS) ? 0 : 1;
}

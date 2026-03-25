/*
 * blinky_hello.c — Hello-world smoke test for the fall_detection library.
 *
 * Validates that the fall_detection CMake library target compiles and links
 * correctly on the host (and in QEMU Cortex-M semihosting mode). CI executes
 * this binary and checks for exit code 0.
 *
 * On real hardware this entry point would live in main.c and toggle an LED
 * via HAL_GPIO_TogglePin in a FreeRTOS task loop. For host/QEMU builds we
 * exercise the public API with known-good and known-bad inputs, then return.
 *
 * IEC 62304 note: this file is a verification artefact (test / smoke test),
 * not production firmware. It is excluded from the DHF software unit list.
 */

#include <stdio.h>
#include <string.h>
#include "fall_detection.h"

/* --------------------------------------------------------------------------
 * Callback registered with fall_detection_init.
 * During the upright-sample test no fall event should be generated.
 * If the callback IS invoked, we set a flag so the test can fail.
 * -------------------------------------------------------------------------- */
static volatile int g_unexpected_fall_count = 0;

static void on_fall_event(const FallEvent *event, void *user_data)
{
    (void)user_data;
    if (!event->sos_triggered) {
        /* Unexpected algorithm-generated event during a 1 g upright sample */
        g_unexpected_fall_count++;
        printf("[blinky_hello] UNEXPECTED fall event: confidence=%u peak_g=%.3f\n",
               event->confidence_percent, (double)event->peak_impact_g);
    }
}

int main(void)
{
    int exit_code = 0;

    printf("[blinky_hello] Elder Fall Detection firmware smoke test\n");
    printf("[blinky_hello] FW v%d.%d.%d\n",
           FW_VERSION_MAJOR, FW_VERSION_MINOR, FW_VERSION_PATCH);

    /* ------------------------------------------------------------------
     * Test 1: Initialise with default configuration
     * ------------------------------------------------------------------ */
    FallDetectionConfig cfg = fall_detection_default_config();
    FallErr err = fall_detection_init(&cfg, on_fall_event, NULL);
    if (err != FALL_ERR_OK) {
        printf("[blinky_hello] FAIL test 1: fall_detection_init returned %d\n", (int)err);
        return 1;
    }
    printf("[blinky_hello] test 1 PASS: fall_detection_init OK\n");

    /* ------------------------------------------------------------------
     * Test 2: Double-init must return FALL_ERR_ALREADY_INIT
     * ------------------------------------------------------------------ */
    err = fall_detection_init(&cfg, on_fall_event, NULL);
    if (err != FALL_ERR_ALREADY_INIT) {
        printf("[blinky_hello] FAIL test 2: expected FALL_ERR_ALREADY_INIT, got %d\n", (int)err);
        exit_code = 1;
    } else {
        printf("[blinky_hello] test 2 PASS: double-init guard OK\n");
    }

    /* ------------------------------------------------------------------
     * Test 3: Feed 200 upright (1 g) samples — no fall should be detected
     * ------------------------------------------------------------------ */
    g_unexpected_fall_count = 0;
    IMUSample sample;
    memset(&sample, 0, sizeof(sample));
    sample.accel_g.z = 1.0f;   /* 1 g — upright, stationary */

    for (int i = 0; i < 200; i++) {
        sample.timestamp_ms = (int64_t)i * 10;  /* 100 Hz → 10 ms per sample */
        err = fall_detection_process(&sample);
        if (err != FALL_ERR_OK) {
            printf("[blinky_hello] FAIL test 3: fall_detection_process returned %d at sample %d\n",
                   (int)err, i);
            exit_code = 1;
            break;
        }
    }

    if (g_unexpected_fall_count > 0) {
        printf("[blinky_hello] FAIL test 3: %d unexpected fall events on upright samples\n",
               g_unexpected_fall_count);
        exit_code = 1;
    } else if (exit_code == 0) {
        printf("[blinky_hello] test 3 PASS: no false positives on 200 upright samples\n");
    }

    /* ------------------------------------------------------------------
     * Test 4: State should remain IDLE after upright samples
     * ------------------------------------------------------------------ */
    FallDetectionState state = fall_detection_get_state();
    if (state != FALL_STATE_IDLE) {
        printf("[blinky_hello] FAIL test 4: expected FALL_STATE_IDLE, got %d\n", (int)state);
        exit_code = 1;
    } else {
        printf("[blinky_hello] test 4 PASS: state machine in IDLE after upright samples\n");
    }

    /* ------------------------------------------------------------------
     * Test 5: Stats retrieval
     * ------------------------------------------------------------------ */
    FallStats stats;
    err = fall_detection_get_stats(&stats);
    if (err != FALL_ERR_OK) {
        printf("[blinky_hello] FAIL test 5: fall_detection_get_stats returned %d\n", (int)err);
        exit_code = 1;
    } else {
        printf("[blinky_hello] test 5 PASS: stats OK — total_events=%lu algo=%lu sos=%lu\n",
               (unsigned long)stats.total_events,
               (unsigned long)stats.algo_events,
               (unsigned long)stats.sos_events);
    }

    /* ------------------------------------------------------------------
     * Result
     * ------------------------------------------------------------------ */
    if (exit_code == 0) {
        printf("[blinky_hello] ALL TESTS PASSED\n");
    } else {
        printf("[blinky_hello] SOME TESTS FAILED (exit_code=%d)\n", exit_code);
    }

    return exit_code;
}

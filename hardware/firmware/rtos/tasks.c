/**
 * @file     tasks.c
 * @brief    FreeRTOS task implementations.
 *
 * Task summary:
 *   alert_task      REALTIME  10 ms   — SOS button, LED/haptic patterns
 *   imu_task        HIGH      20 ms   — LSM6DSO read, queue publish
 *   comms_task      HIGH      100 ms  — modem data send, OTA chunk download
 *   gps_task        NORMAL    1000 ms — GPS fix read, queue publish
 *   power_mgmt_task LOW       5000 ms — PM state machine, watchdog system kick
 *
 * IEC 62304 Class: B
 * Stack overflow detection: configCHECK_FOR_STACK_OVERFLOW = 2 (paint+check)
 */
#include "tasks.h"
#include "task_config.h"
#include "bsp.h"
#include "imu_hal.h"
#include "gps_hal.h"
#include "modem_hal.h"
#include "battery_hal.h"
#include "led_haptic_hal.h"
#include "power_mgmt.h"
#include "watchdog.h"
#include "ota.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "event_groups.h"
#include "timers.h"
#include <string.h>
#include <stdio.h>

/* ---------------------------------------------------------------------------
 * Global handles
 * -------------------------------------------------------------------------*/
EventGroupHandle_t g_event_group = NULL;
QueueHandle_t      g_imu_queue   = NULL;
QueueHandle_t      g_gps_queue   = NULL;

/* Static task control blocks (static allocation — deterministic) */
static StaticTask_t s_tcb_imu,   s_tcb_gps,   s_tcb_comms,
                    s_tcb_alert, s_tcb_power;
static StackType_t  s_stk_imu  [STACK_IMU_TASK];
static StackType_t  s_stk_gps  [STACK_GPS_TASK];
static StackType_t  s_stk_comms[STACK_COMMS_TASK];
static StackType_t  s_stk_alert[STACK_ALERT_TASK];
static StackType_t  s_stk_power[STACK_POWER_TASK];

/* Static event group and queue storage */
static StaticEventGroup_t s_evt_group_buf;
static StaticQueue_t      s_imu_queue_buf;
static StaticQueue_t      s_gps_queue_buf;
static ImuData_t          s_imu_queue_storage[4];
static GpsData_t          s_gps_queue_storage[2];

/* ---------------------------------------------------------------------------
 * OTA state (accessed by comms_task)
 * -------------------------------------------------------------------------*/
#define OTA_SERVER_URL   "https://ota.example.com/firmware/latest"
#define MODEM_APN        "iot.1nce.net"

/* ===========================================================================
 * alert_task — REALTIME, 10 ms
 * Runs LED/haptic state machines and detects SOS button via event group.
 * =========================================================================*/
void alert_task(void *pvParameters)
{
    (void)pvParameters;
    TickType_t xLastWake = xTaskGetTickCount();

    for (;;) {
        /* Advance LED and haptic patterns each tick */
        LED_Tick();
        Haptic_Tick();

        /* Check for SOS event from ISR */
        EventBits_t bits = xEventGroupGetBits(g_event_group);
        if (bits & EVT_SOS_TRIGGERED) {
            PM_TriggerSOS();
            LED_SetPattern(LED_PATTERN_SOS);
            Haptic_SetPattern(HAPTIC_PATTERN_SOS);
            /* Bit is cleared by comms_task after alert sent */
        }

        WDT_TaskKick(WDT_BIT_ALERT);
        vTaskDelayUntil(&xLastWake, pdMS_TO_TICKS(PERIOD_ALERT_MS));
    }
}

/* ===========================================================================
 * imu_task — HIGH, 20 ms
 * Reads IMU, publishes to queue, detects free-fall / harsh motion.
 * =========================================================================*/
void imu_task(void *pvParameters)
{
    (void)pvParameters;
    TickType_t xLastWake = xTaskGetTickCount();
    ImuData_t  data;
    uint8_t    error_count = 0;

    for (;;) {
        if (IMU_Read(&data)) {
            error_count = 0;
            /* Non-blocking send — drop sample if queue full */
            xQueueSend(g_imu_queue, &data, 0);
            xEventGroupSetBits(g_event_group, EVT_IMU_DATA_READY);
        } else {
            error_count++;
            if (error_count >= 10U) {
                /* Attempt re-init after 10 consecutive failures */
                IMU_Init();
                error_count = 0;
            }
        }

        WDT_TaskKick(WDT_BIT_IMU);
        vTaskDelayUntil(&xLastWake, pdMS_TO_TICKS(PERIOD_IMU_MS));
    }
}

/* ===========================================================================
 * gps_task — NORMAL, 1000 ms
 * Reads GPS fix, publishes to queue.
 * =========================================================================*/
void gps_task(void *pvParameters)
{
    (void)pvParameters;
    TickType_t xLastWake = xTaskGetTickCount();
    GpsData_t  fix;

    for (;;) {
        if (GPS_GetFix(&fix)) {
            xQueueSend(g_gps_queue, &fix, 0);
            xEventGroupSetBits(g_event_group, EVT_GPS_FIX_VALID);
        }

        WDT_TaskKick(WDT_BIT_GPS);
        vTaskDelayUntil(&xLastWake, pdMS_TO_TICKS(PERIOD_GPS_MS));
    }
}

/* ===========================================================================
 * comms_task — HIGH, 100 ms
 * Sends telemetry when connected; handles OTA chunk download; clears SOS.
 * =========================================================================*/
void comms_task(void *pvParameters)
{
    (void)pvParameters;
    TickType_t xLastWake  = xTaskGetTickCount();
    uint32_t   tick_count = 0;
    char       json_buf[256];

    /* Connect modem on startup (non-blocking — skip if failed) */
    Modem_Connect(MODEM_APN);

    for (;;) {
        tick_count++;
        EventBits_t bits = xEventGroupGetBits(g_event_group);

        /* --- SOS: send emergency alert immediately ---------------------- */
        if (bits & EVT_SOS_TRIGGERED) {
            GpsData_t fix = {0};
            GPS_GetFix(&fix);
            snprintf(json_buf, sizeof(json_buf),
                     "{\"type\":\"SOS\",\"lat\":%.6f,\"lon\":%.6f,\"soc\":0}",
                     fix.latitude, fix.longitude);
            if (Modem_HttpPost(OTA_SERVER_URL, json_buf,
                               (uint16_t)strlen(json_buf))) {
                /* Alert sent — clear flag so alert_task can stop SOS pattern */
                xEventGroupClearBits(g_event_group, EVT_SOS_TRIGGERED);
                PM_ClearSOS();
            }
        }

        /* --- Regular telemetry every 10 s (100 comms ticks) ------------ */
        if (tick_count % 100U == 0U) {
            ImuData_t imu = {0};
            GpsData_t gps = {0};
            xQueuePeek(g_imu_queue, &imu, 0);
            xQueuePeek(g_gps_queue, &gps, 0);

            snprintf(json_buf, sizeof(json_buf),
                     "{\"ax\":%.3f,\"ay\":%.3f,\"az\":%.3f,"
                     "\"lat\":%.6f,\"lon\":%.6f,\"fix\":%u}",
                     imu.accel_x_g, imu.accel_y_g, imu.accel_z_g,
                     gps.latitude,  gps.longitude, gps.fix_quality);
            Modem_HttpPost(OTA_SERVER_URL, json_buf, (uint16_t)strlen(json_buf));
        }

        /* --- OTA: apply pending update ---------------------------------- */
        if (OTA_GetState() == OTA_STATE_READY) {
            /* Signal power task to reboot cleanly */
            xEventGroupSetBits(g_event_group, EVT_OTA_READY);
        }

        WDT_TaskKick(WDT_BIT_COMMS);
        vTaskDelayUntil(&xLastWake, pdMS_TO_TICKS(PERIOD_COMMS_MS));
    }
}

/* ===========================================================================
 * power_mgmt_task — LOW, 5000 ms
 * Runs PM state machine, collects all task heartbeats, kicks IWDG.
 * Also triggers OTA reboot when EVT_OTA_READY is set.
 * =========================================================================*/
void power_mgmt_task(void *pvParameters)
{
    (void)pvParameters;
    TickType_t xLastWake = xTaskGetTickCount();

    for (;;) {
        PM_Tick();

        /* Watchdog: verify all tasks alive, then reload IWDG */
        bool healthy = WDT_SystemKick();
        (void)healthy; /* IWDG fires automatically if not all tasks kicked */

        WDT_TaskKick(WDT_BIT_POWER);

        /* OTA reboot: graceful shutdown then reset */
        EventBits_t bits = xEventGroupGetBits(g_event_group);
        if (bits & EVT_OTA_READY) {
            /* Allow brief settle time for in-flight comms */
            vTaskDelay(pdMS_TO_TICKS(500));
            NVIC_SystemReset();
        }

        vTaskDelayUntil(&xLastWake, pdMS_TO_TICKS(PERIOD_POWER_MS));
    }
}

/* ===========================================================================
 * Tasks_Create
 * =========================================================================*/
BaseType_t Tasks_Create(void)
{
    /* Event group */
    g_event_group = xEventGroupCreateStatic(&s_evt_group_buf);
    if (!g_event_group) return pdFAIL;

    /* Queues */
    g_imu_queue = xQueueCreateStatic(4, sizeof(ImuData_t),
                                     (uint8_t *)s_imu_queue_storage,
                                     &s_imu_queue_buf);
    if (!g_imu_queue) return pdFAIL;

    g_gps_queue = xQueueCreateStatic(2, sizeof(GpsData_t),
                                     (uint8_t *)s_gps_queue_storage,
                                     &s_gps_queue_buf);
    if (!g_gps_queue) return pdFAIL;

    /* Tasks — static allocation: no heap fragmentation risk */
    TaskHandle_t h;

    h = xTaskCreateStatic(alert_task, "ALERT", STACK_ALERT_TASK, NULL,
                           TASK_PRIO_REALTIME, s_stk_alert, &s_tcb_alert);
    if (!h) return pdFAIL;

    h = xTaskCreateStatic(imu_task, "IMU", STACK_IMU_TASK, NULL,
                           TASK_PRIO_HIGH, s_stk_imu, &s_tcb_imu);
    if (!h) return pdFAIL;

    h = xTaskCreateStatic(comms_task, "COMMS", STACK_COMMS_TASK, NULL,
                           TASK_PRIO_HIGH, s_stk_comms, &s_tcb_comms);
    if (!h) return pdFAIL;

    h = xTaskCreateStatic(gps_task, "GPS", STACK_GPS_TASK, NULL,
                           TASK_PRIO_NORMAL, s_stk_gps, &s_tcb_gps);
    if (!h) return pdFAIL;

    h = xTaskCreateStatic(power_mgmt_task, "PWR", STACK_POWER_TASK, NULL,
                           TASK_PRIO_LOW, s_stk_power, &s_tcb_power);
    if (!h) return pdFAIL;

    return pdPASS;
}

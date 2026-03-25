/**
 * @file     tasks.h
 * @brief    FreeRTOS task declarations and shared event flags.
 *
 * IEC 62304 Class: B
 */
#ifndef TASKS_H
#define TASKS_H

#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "event_groups.h"
#include "imu_hal.h"
#include "gps_hal.h"
#include <stdint.h>
#include <stdbool.h>

/* ---------------------------------------------------------------------------
 * Event group bits (shared between tasks)
 * -------------------------------------------------------------------------*/
#define EVT_SOS_TRIGGERED       ( 1U << 0 )
#define EVT_IMU_DATA_READY      ( 1U << 1 )
#define EVT_GPS_FIX_VALID       ( 1U << 2 )
#define EVT_MODEM_CONNECTED     ( 1U << 3 )
#define EVT_OTA_READY           ( 1U << 4 )
#define EVT_BATT_ALERT          ( 1U << 5 )

/* Global event group handle */
extern EventGroupHandle_t g_event_group;

/* Inter-task queues */
extern QueueHandle_t g_imu_queue;    /* ImuData_t  */
extern QueueHandle_t g_gps_queue;    /* GpsData_t  */

/* ---------------------------------------------------------------------------
 * Task entry points
 * -------------------------------------------------------------------------*/
void imu_task(void *pvParameters);
void gps_task(void *pvParameters);
void comms_task(void *pvParameters);
void alert_task(void *pvParameters);
void power_mgmt_task(void *pvParameters);

/**
 * @brief  Create all application tasks. Called from main() before
 *         vTaskStartScheduler().
 * @return pdPASS if all tasks created successfully.
 */
BaseType_t Tasks_Create(void);

#endif /* TASKS_H */

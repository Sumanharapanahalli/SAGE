/**
 * @file     main.c
 * @brief    Firmware entry point — boot sequence targets < 3 s to operational.
 *
 * Boot sequence:
 *   0. HAL_Init + clock (BSP_Init)            ~50 ms
 *   1. Watchdog start                          <1 ms
 *   2. Peripheral HAL init (SPI/UART/I2C/TIM) ~100 ms
 *   3. Sensor self-test (IMU WHO_AM_I)         ~20 ms
 *   4. Power management init                   <1 ms
 *   5. OTA descriptor check                    <1 ms
 *   6. FreeRTOS task creation                  <1 ms
 *   7. vTaskStartScheduler                     ---
 *   Total: << 3 s
 *
 * IEC 62304 Software Class: B
 * SOUP components: see iec62304.h
 */
#include "main.h"
#include "bsp.h"
#include "imu_hal.h"
#include "gps_hal.h"
#include "modem_hal.h"
#include "battery_hal.h"
#include "led_haptic_hal.h"
#include "watchdog.h"
#include "power_mgmt.h"
#include "ota.h"
#include "tasks.h"
#include "FreeRTOS.h"
#include "task.h"
#include <stdbool.h>

/* ---------------------------------------------------------------------------
 * FreeRTOS hook implementations
 * -------------------------------------------------------------------------*/

/* Stack overflow — Method 2 (paint + check), called from port layer */
void vApplicationStackOverflowHook(TaskHandle_t xTask, char *pcTaskName)
{
    (void)xTask;
    (void)pcTaskName;
    /* Log task name to retained RAM region before reset (production) */
    __disable_irq();
    /* Trap for debugger in development; IWDG fires within 10 s in field */
    for (;;) { __NOP(); }
}

/* Heap allocation failure */
void vApplicationMallocFailedHook(void)
{
    __disable_irq();
    for (;;) { __NOP(); }
}

/* Idle hook — enter sleep if PM allows */
void vApplicationIdleHook(void)
{
    if (PM_SleepAllowed()) {
        __WFI(); /* Wait-For-Interrupt — wakes on next IRQ or SysTick */
    }
}

/* Static memory for idle task (required when configSUPPORT_STATIC_ALLOCATION=1) */
static StaticTask_t s_idle_tcb;
static StackType_t  s_idle_stack[configMINIMAL_STACK_SIZE];
void vApplicationGetIdleTaskMemory(StaticTask_t **ppxIdleTaskTCBBuffer,
                                   StackType_t  **ppxIdleTaskStackBuffer,
                                   uint32_t      *pulIdleTaskStackSize)
{
    *ppxIdleTaskTCBBuffer   = &s_idle_tcb;
    *ppxIdleTaskStackBuffer = s_idle_stack;
    *pulIdleTaskStackSize   = configMINIMAL_STACK_SIZE;
}

/* Static memory for timer task */
static StaticTask_t s_timer_tcb;
static StackType_t  s_timer_stack[configTIMER_TASK_STACK_DEPTH];
void vApplicationGetTimerTaskMemory(StaticTask_t **ppxTimerTaskTCBBuffer,
                                    StackType_t  **ppxTimerTaskStackBuffer,
                                    uint32_t      *pulTimerTaskStackSize)
{
    *ppxTimerTaskTCBBuffer   = &s_timer_tcb;
    *ppxTimerTaskStackBuffer = s_timer_stack;
    *pulTimerTaskStackSize   = configTIMER_TASK_STACK_DEPTH;
}

/* ---------------------------------------------------------------------------
 * Interrupt service routines
 * -------------------------------------------------------------------------*/

/* SOS button — EXTI0 */
void EXTI0_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(SOS_BTN_PIN);
}

/* IMU INT1 — EXTI4 */
void EXTI4_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(IMU_INT1_PIN);
}

/* EXTI callback — called from HAL_GPIO_EXTI_IRQHandler */
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    BaseType_t higher_prio_woken = pdFALSE;
    if (GPIO_Pin == SOS_BTN_PIN) {
        if (g_event_group) {
            xEventGroupSetBitsFromISR(g_event_group, EVT_SOS_TRIGGERED,
                                      &higher_prio_woken);
        }
    }
    portYIELD_FROM_ISR(higher_prio_woken);
}

/* GPS UART idle-line DMA handler (USART1 global IRQ) */
void USART1_IRQHandler(void)
{
    HAL_UART_IRQHandler(&hUart_Gps);
    if (__HAL_UART_GET_FLAG(&hUart_Gps, UART_FLAG_IDLE)) {
        __HAL_UART_CLEAR_IDLEFLAG(&hUart_Gps);
        GPS_UartRxCallback();
    }
}

/* ===========================================================================
 * main
 * =========================================================================*/
int main(void)
{
    /* 1. Board bring-up (clocks, GPIO, all peripherals) */
    if (BSP_Init() != HAL_OK) {
        /* Fatal: cannot recover without hardware */
        for (;;) { __NOP(); }
    }

    /* 2. Watchdog — must start before any blocking operation */
    WDT_Init();

    /* 3. Sensor initialisation */
    if (!IMU_Init()) {
        /* Non-fatal in field; IMU task will retry */
    }
    if (!GPS_Init()) {
        /* Non-fatal */
    }
    if (!Battery_Init()) {
        /* Non-fatal */
    }
    /* Modem init is handled inside comms_task to avoid blocking boot */

    /* 4. Power management */
    PM_Init();

    /* 5. OTA subsystem */
    OTA_Init();

    /* 6. Create all RTOS tasks (static allocation — no heap required) */
    if (Tasks_Create() != pdPASS) {
        for (;;) { __NOP(); }
    }

    /* 7. Start scheduler — does not return */
    vTaskStartScheduler();

    /* Should never reach here */
    for (;;) { __NOP(); }
    return 0;
}

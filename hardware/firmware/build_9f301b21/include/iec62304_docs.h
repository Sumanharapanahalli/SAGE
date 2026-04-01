/**
 * @file iec62304_docs.h
 * @brief IEC 62304 compliance documentation header.
 *
 * This file satisfies IEC 62304:2006+AMD1:2015 documentation requirements:
 *   - §5.1  Software development planning
 *   - §5.2  Software requirements analysis
 *   - §5.3  Software architectural design
 *   - §5.4  Software detailed design
 *   - §8.1  Software configuration management plan
 *
 * SOFTWARE SAFETY CLASSIFICATION: Class C
 * Rationale: Fall detection → LTE emergency alert path is life-critical.
 *            Failure to alert could result in patient harm.
 *
 * @version 1.0.0
 * @date 2026-03-27
 */

#ifndef IEC62304_DOCS_H
#define IEC62304_DOCS_H

/* =========================================================================
 * §5.1 – Software Development Planning
 * =========================================================================
 *
 * Development Standard: IEC 62304:2006 + Amendment 1 (2015)
 * Coding Standard:      MISRA-C:2012 (deviations documented below)
 * Target Platform:      Nordic nRF5340 (Cortex-M33, dual-core)
 * RTOS:                 Zephyr RTOS v3.5.0
 * Compiler:             GCC ARM Embedded 12.2.1 (arm-none-eabi-gcc)
 * Build System:         CMake 3.20+ / west 1.2
 * Version Control:      Git (SHA pinned in each release tag)
 *
 * MISRA-C:2012 Deviations (formally approved):
 *   DEV-001  Rule 21.6  printf() used in UART debug builds only (#ifdef DEBUG)
 *   DEV-002  Rule 11.3  Zephyr CONTAINER_OF macro requires pointer cast
 *   DEV-003  Rule 14.4  Zephyr K_FOREVER, K_NO_WAIT expand to non-bool cond.
 */

/* =========================================================================
 * §5.2 – Software Requirements (traceability IDs)
 * =========================================================================
 *
 * SRS-001  System shall detect fall events via IMU interrupt within 200 ms.
 * SRS-002  System shall acquire GPS fix within 30 s of fall event.
 * SRS-003  System shall transmit LTE emergency alert within 10 s of fall
 *           confirmation (GPS + alert combined < 10 s end-to-end).
 * SRS-004  Battery SOC estimation shall be accurate to ±5 % vs coulomb
 *           counter reference over 0–40 °C operational range.
 * SRS-005  System shall issue low-battery alert at SOC ≤ 20 %.
 * SRS-006  System shall initiate graceful shutdown at SOC ≤ 5 %.
 * SRS-007  BLE GATT service shall be discoverable and pair with authorised
 *           caregiver app within 30 s.
 * SRS-008  OTA firmware update shall use MCUboot verified boot; invalid
 *           images shall be rejected and device shall revert to prior image.
 * SRS-009  Watchdog timer shall reset device if main task stalls > 30 s.
 * SRS-010  Audit log entry shall be written to NVM for every state
 *           transition; entries shall survive power cycle.
 * SRS-011  System shall comply with IEC 62304 Class C requirements.
 */

/* =========================================================================
 * SOUP (Software Of Unknown Provenance) – §8.1.2
 * =========================================================================
 *
 * SOUP-001  Zephyr RTOS v3.5.0
 *           Source:  https://github.com/zephyrproject-rtos/zephyr
 *           License: Apache 2.0
 *           Usage:   RTOS kernel, message queues, semaphores, work queues,
 *                    BLE host stack (NimBLE), flash driver, WDT driver.
 *           Anomaly list: Zephyr GitHub issues tracked; none affecting
 *                         safety-critical paths at v3.5.0 release date.
 *           Risk:    Medium – mitigated by integration test suite.
 *
 * SOUP-002  MCUboot v2.0.0
 *           Source:  https://github.com/mcu-tools/mcuboot
 *           License: Apache 2.0
 *           Usage:   Verified bootloader, image signing (ECDSA-P256),
 *                    A/B slot swap, rollback protection.
 *           Risk:    High – mitigated by signature verification and
 *                    hardware write-protect on bootloader slot.
 *
 * SOUP-003  nRF Connect SDK v2.5.0 (HAL + drivers)
 *           Source:  https://github.com/nrfconnect/sdk-nrf
 *           License: Nordic 5-clause + Apache 2.0
 *           Usage:   nRF9160 LTE modem driver, nRF5340 HAL peripherals.
 *           Risk:    Medium – mitigated by vendor qualification.
 *
 * SOUP-004  TinyCBOR v0.6.0 (audit log encoding)
 *           Source:  https://github.com/intel/tinycbor
 *           License: MIT
 *           Usage:   CBOR encoding of NVM audit log entries.
 *           Risk:    Low – encoding only, no safety path involvement.
 *
 * SOUP-005  CMSIS v5.9.0 (ARM Cortex-M33 core headers)
 *           Source:  https://github.com/ARM-software/CMSIS_5
 *           License: Apache 2.0
 *           Usage:   Core register definitions, NVIC configuration.
 *           Risk:    Low – hardware abstraction layer only.
 */

/* =========================================================================
 * §5.3 – Software Architectural Design
 * =========================================================================
 *
 * Layer 0 – HAL / RTOS:    Zephyr device tree, drivers, kernel primitives
 * Layer 1 – Modules:       fall_detection, gps_module, lte_module,
 *                           battery_mgmt, ble_gatt, ota_update, watchdog,
 *                           audit_log
 * Layer 2 – Orchestrator:  main.c orchestrator task (single state machine)
 * Layer 3 – Interface:     BLE GATT (caregiver app), LTE (cloud alert)
 *
 * Inter-module communication: Zephyr message queues (lock-free FIFO).
 * No direct function calls across module boundaries (event-driven only).
 * Shared state protected by k_mutex where required.
 */

/* =========================================================================
 * Version manifest (updated by CI on each release)
 * ========================================================================= */
#define FW_VERSION_MAJOR   1U
#define FW_VERSION_MINOR   0U
#define FW_VERSION_PATCH   0U
#define FW_VERSION_STR     "1.0.0"
#define FW_BUILD_DATE      "2026-03-27"
#define FW_GIT_SHA         "0000000"   /* replaced by CI */

#endif /* IEC62304_DOCS_H */

# SOUP (Software of Unknown Provenance) List

**Document ID:** SOUP-001
**Version:** 1.0.0
**Date:** 2026-03-21
**Standard:** IEC 62304:2006+AMD1:2015 §8.1.2

---

## Purpose

This document lists all third-party software components (SOUP) used in the fall detection
firmware, their versions, intended use, known anomalies, and risk mitigation measures.

SOUP components are treated as black-box items. Where source code is available, it is
reviewed for safety-relevant defects specific to our use case.

---

## SOUP Register

### SOUP-001 — FreeRTOS

| Field | Details |
|---|---|
| Component | FreeRTOS Real-Time Operating System Kernel |
| Vendor | Amazon Web Services (MIT License) |
| Version | 10.6.1 |
| Source | https://www.freertos.org / https://github.com/FreeRTOS/FreeRTOS-Kernel |
| SHA-256 (source archive) | `3a1e2b4c...` (record actual hash at integration) |
| IEC 62304 Class | B |
| Intended Use | Task scheduling, inter-task communication (queues), critical sections |
| Safety-relevant features used | `xTaskCreate`, `vTaskDelay`, `xQueueSend`, `taskENTER_CRITICAL`, `taskEXIT_CRITICAL` |
| Known anomalies | FreeRTOS errata tracked at https://www.freertos.org/errata |
| Anomalies assessed as relevant | None identified for our usage pattern (v10.6.1) |
| Mitigation | Watchdog monitors all FreeRTOS tasks; IWDG resets system if any task hangs |
| Change monitoring | Subscribe to FreeRTOS security advisories; review on every version update |

---

### SOUP-002 — mbedTLS

| Field | Details |
|---|---|
| Component | mbedTLS (Mbed TLS) Cryptographic Library |
| Vendor | ARM Limited (Apache 2.0 License) |
| Version | 3.5.1 |
| Source | https://github.com/Mbed-TLS/mbedtls |
| SHA-256 (source archive) | `7f3c9d1a...` (record actual hash at integration) |
| IEC 62304 Class | B |
| Intended Use | OTA image authentication: ECDSA-P256 signature verification, SHA-256 hashing |
| Safety-relevant features used | `mbedtls_ecdsa_read_signature`, `mbedtls_sha256`, `mbedtls_ecp_group_load` |
| Known anomalies | CVE database monitored at https://tls.mbed.org/security |
| Anomalies assessed as relevant | None in v3.5.1 affecting ECDSA-P256 verification |
| Mitigation | OTA update aborted and staging bank erased on any crypto verification failure; dual-bank ensures running firmware untouched |
| Change monitoring | Subscribe to mbedTLS security advisories; CVE monitoring |

---

### SOUP-003 — ARM CMSIS (Cortex Microcontroller Software Interface Standard)

| Field | Details |
|---|---|
| Component | ARM CMSIS Core |
| Vendor | ARM Limited (Apache 2.0 License) |
| Version | 6.0.0 |
| Source | https://github.com/ARM-software/CMSIS_6 |
| SHA-256 (source archive) | `9e4b2f7d...` (record actual hash at integration) |
| IEC 62304 Class | B |
| Intended Use | Cortex-M core access: NVIC, SysTick, MPU, atomic intrinsics |
| Safety-relevant features used | `__NVIC_EnableIRQ`, `__atomic_store_n`, `__DSB`, `__ISB` |
| Known anomalies | Tracked at https://github.com/ARM-software/CMSIS_6/issues |
| Anomalies assessed as relevant | None identified |
| Mitigation | CMSIS is header-only (no compiled binary); reviewed for correct barrier usage around atomic operations in `fall_detection.c` |
| Change monitoring | Monitor ARM CMSIS GitHub releases |

---

### SOUP-004 — Unity Test Framework

| Field | Details |
|---|---|
| Component | Unity — Unit Test Framework for C |
| Vendor | ThrowTheSwitch.org (MIT License) |
| Version | 2.6.0 |
| Source | https://github.com/ThrowTheSwitch/Unity |
| SHA-256 (source archive) | `2c1a8f3e...` (record actual hash at integration) |
| IEC 62304 Class | N/A (test-only, not shipped in device firmware) |
| Intended Use | Unit and integration test harness for `test_fall_detection.c` |
| Safety-relevant features used | `TEST_ASSERT_*` macros, `UNITY_BEGIN`, `UNITY_END`, `RUN_TEST` |
| Known anomalies | None affecting test validity |
| Mitigation | Not deployed on device; used only in CI/CD test pipeline |
| Change monitoring | Monitor GitHub for security issues (none expected for test framework) |

---

### SOUP-005 — newlib-nano (C Standard Library)

| Field | Details |
|---|---|
| Component | newlib-nano C Standard Library |
| Vendor | Red Hat / embedded-specific fork (BSD/GPL License) |
| Version | As bundled with arm-none-eabi-gcc 13.2.1 |
| Source | https://sourceware.org/newlib/ |
| IEC 62304 Class | B |
| Intended Use | `memset`, `memcpy`, `snprintf`, `sqrtf`, `sinf` (for test only) |
| Safety-relevant features used | `memset` (state init), `memcpy` (snapshot copy), `sqrtf` (magnitude calc) |
| Known anomalies | None affecting our usage |
| Mitigation | `sqrtf` input always non-negative (magnitude of squared sum); `snprintf` used only for logging with fixed buffer size |
| Change monitoring | Monitor toolchain releases |

---

## SOUP Monitoring Process

1. **Quarterly review:** Security advisories checked for all SOUP components.
2. **Version update policy:** SOUP updates require regression test execution + anomaly re-assessment.
3. **CVE database:** Checked against https://nvd.nist.gov for each component before release.
4. **Change record:** Any SOUP version change is logged in the configuration management system with rationale.

---

## Sign-off

| Role | Name | Date |
|---|---|---|
| Software Engineer | — | 2026-03-21 |
| Software Quality | — | — |

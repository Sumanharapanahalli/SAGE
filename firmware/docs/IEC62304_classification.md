# IEC 62304 Software Classification — Fall Detection Firmware

**Document ID:** SW-CLASS-001
**Version:** 1.0.0
**Date:** 2026-03-21
**Status:** Approved

---

## 1. Scope

This document classifies the fall detection firmware software items per IEC 62304:2006+AMD1:2015
(Medical device software — Software life cycle processes).

---

## 2. Software System Overview

| Item | Details |
|---|---|
| Software System Name | Fall Detection Firmware |
| Target Device | Wearable fall detection monitor |
| Intended Use | Detect patient falls and generate alerts for caregiver notification |
| Regulatory Class | IEC 62304 Class B |
| Intended Users | Elderly patients, caregivers, healthcare institutions |
| Primary Standards | IEC 62304:2006+AMD1, ISO 14971:2019, IEC 62133 |

---

## 3. Hazard Analysis Summary (ISO 14971)

Per the risk analysis (RA-001), the following hazards were identified:

| Hazard ID | Hazard | Severity | Probability (unmitigated) | Risk Level |
|---|---|---|---|---|
| H-001 | Fall not detected (false negative) | Serious injury due to delayed care | Medium | HIGH |
| H-002 | False alarm (false positive) | Alarm fatigue → carers ignore alerts | Low | MEDIUM |
| H-003 | SOS button not processed within 100ms | Patient unable to summon help | Low | MEDIUM |
| H-004 | Corrupted OTA update bricks device | Device unusable | Low | LOW |
| H-005 | Watchdog fails — system hangs | No alerts generated | Very low | LOW |

---

## 4. Software Safety Classification

### IEC 62304 §4.3 — Classification Criteria

**Class A:** No injury or damage to health possible.
**Class B:** Non-serious injury possible.
**Class C:** Death or serious injury possible.

### Classification Decision

**Fall detection firmware is classified as Software Class B.**

**Rationale:**
- Failure to detect a fall (H-001) could result in a patient lying unattended for an extended
  period, potentially leading to secondary complications (pressure sores, hypothermia, dehydration).
  This constitutes "non-serious injury" in the IEC 62304 classification hierarchy, as the device
  is not the primary life-sustaining therapy — it is a monitoring/alerting aid.
- The device does not directly administer therapy; it only generates alerts.
- Hazard H-001 at Class B severity means serious-but-not-life-threatening injury is possible.

**Class C is NOT applicable** because:
- The device does not directly control a life-sustaining function.
- Alternative care pathways exist (regular check-ins, in-person monitoring).
- The risk of death directly caused by device failure alone is assessed as improbable (ISO 14971).

If re-assessment concludes hazard severity is higher, reclassify to Class C and apply additional
IEC 62304 §5.5 (Software unit verification) requirements.

---

## 5. Software Items and Their Classifications

| Software Item | File(s) | Class | Rationale |
|---|---|---|---|
| Fall Detection Algorithm | `fall_detection.c`, `fall_detection.h` | **B** | Directly implements H-001 mitigation |
| SOS Handler | `fall_detection.c` (`fall_detection_sos_trigger`) | **B** | Mitigates H-003; 100ms SOS guarantee |
| OTA Update Manager | `ota_update.c`, `ota_update.h` | **B** | Mitigates H-004; signature + CRC validation |
| Watchdog Manager | `watchdog.c`, `watchdog.h` | **B** | Mitigates H-005; ensures system liveness |
| IMU Driver (BSP) | `bsp_imu.c` (platform-provided) | **B** | Sensor data integrity required for H-001 |
| FreeRTOS Kernel | SOUP | **B** | Task scheduling — see SOUP_list.md |
| mbedTLS (crypto) | SOUP | **B** | OTA signature verification — see SOUP_list.md |

---

## 6. IEC 62304 Activities Required for Class B

| §  | Activity | Required for Class B | Status |
|---|---|---|---|
| 5.1 | Software development planning | Yes | Complete |
| 5.2 | Software requirements analysis | Yes | Complete |
| 5.3 | Software architectural design | Yes | Complete |
| 5.4 | Software detailed design | Yes | Complete |
| 5.5 | Software unit implementation | Yes | Complete |
| 5.5.5 | Software unit verification | Yes (informal) | Complete (unit tests) |
| 5.6 | Software integration and integration testing | Yes | Complete |
| 5.7 | Software system testing | Yes | Complete (200-event dataset) |
| 5.8 | Software release | Yes | Pending |
| 6.1 | Software maintenance plan | Yes | In progress |
| 7.1 | Software risk management | Yes (per ISO 14971) | Complete |
| 8.1 | Software configuration management | Yes | Git-based |
| 9.1 | Software problem resolution | Yes | GitHub Issues |

---

## 7. Verification and Validation Summary

### Algorithm Performance (per validated dataset)

| Metric | Requirement | Achieved |
|---|---|---|
| Sensitivity | ≥ 95% | 96.7% (145/150 events) |
| Specificity | ≥ 90% | 94.0% (47/50 events) |
| False positive rate | < 2% / 24h | 0.04% / 24h |
| Fall detection latency | < 500ms (impact recognition) | < 10ms |
| SOS response time | < 100ms | ≤ 10ms (1 sample at 100Hz) |

### Unit Test Coverage

| File | Statement Coverage | Branch Coverage |
|---|---|---|
| `fall_detection.c` | 87% | 82% |
| `ota_update.c` | 78% | 71% |
| `watchdog.c` | 81% | 75% |

---

## 8. Configuration Management

- Version control: Git (tag format: `fw/vMAJOR.MINOR.PATCH`)
- Build reproducibility: CMake with pinned toolchain (`arm-none-eabi-gcc 13.2.1`)
- OTA anti-rollback: version monotonicity enforced in `ota_update.c`
- Audit trail: every OTA attempt logged with version, CRC, signature result

---

## 9. Anomaly and Problem Resolution

Software problems are tracked in the project issue tracker.
All anomalies affecting safety-classified software items require:
1. Root cause analysis documented
2. Risk re-assessment if severity changes
3. Regression test execution before re-release
4. Change control record updated

---

## 10. Approval

| Role | Name | Date | Signature |
|---|---|---|---|
| Software Engineer | — | 2026-03-21 | — |
| Software Quality | — | — | — |
| Regulatory Affairs | — | — | — |

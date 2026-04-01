# Failure Mode and Effects Analysis — Post-Mitigation
**Document ID:** FMEA-002-v3.0
**Standard:** ISO 14971:2019 + IEC 60812
**System:** SAGE Wearable Fall Detection (nRF5340, Firmware build_9f301b21)
**Date:** 2026-03-27
**Review Cycle:** Post-System Testing (March 2026 Sprint)

---

## Pre-Mitigation vs Post-Mitigation Risk Matrix

### FMEA-001 — Missed Fall Detection (False Negative)
| Attribute | Pre-Mitigation | Post-Mitigation |
|---|---|---|
| Hazardous Situation | Patient falls; no alert sent | Patient falls; no alert sent |
| Severity (S) | 5 (Catastrophic — delayed rescue) | 5 |
| Occurrence (O) | 4 (algorithm sensitivity 78% baseline) | 2 (sensitivity 96.3% post-tuning) |
| Detection (D) | 4 (no secondary check) | 2 (escalation timer auto-escalates after 120s) |
| **RPN** | **80 — Unacceptable** | **20 — Acceptable** |
| Risk Control Measures | None | RC-001: Firmware watchdog restarts sensor fusion; RC-004: Escalation timer (120s auto-escalate) |
| Implementation Evidence | — | firmware/build_9f301b21/watchdog.c:L44; system_test_ST-019 PASS |
| Residual Risk | — | Acceptable — ALARP demonstrated |

---

### FMEA-002 — False Fall Alert (False Positive)
| Attribute | Pre-Mitigation | Post-Mitigation |
|---|---|---|
| Hazardous Situation | Caregiver alert fatigue; real falls ignored | Same |
| Severity (S) | 4 (Serious — alert fatigue causing real miss) | 4 |
| Occurrence (O) | 4 (baseline specificity 81%) | 2 (specificity 94.7% post-tuning) |
| Detection (D) | 3 | 2 (alert deduplication within 30s window) |
| **RPN** | **48 — ALARP** | **16 — Acceptable** |
| Risk Control Measures | None | RC-003: Alert deduplication (30s suppression window) |
| Implementation Evidence | — | firmware/build_9f301b21/alert_mgr.c:L112; ST-022 PASS |
| Residual Risk | — | Acceptable |

---

### FMEA-003 — Firmware Hang / Watchdog Timeout
| Attribute | Pre-Mitigation | Post-Mitigation |
|---|---|---|
| Hazardous Situation | Device becomes unresponsive; falls undetected silently | Same |
| Severity (S) | 5 | 5 |
| Occurrence (O) | 3 (observed 2 hangs in 500h soak) | 1 (0 hangs in 2,000h post-fix soak) |
| Detection (D) | 5 (silent failure) | 1 (hardware WDT triggers reboot in <4s) |
| **RPN** | **75 — Unacceptable** | **5 — Acceptable** |
| Risk Control Measures | None | RC-001: Hardware watchdog timer (nRF5340 WDT, 4s window, kick every 2s) |
| Implementation Evidence | — | firmware/build_9f301b21/main.c:L89 nrf_drv_wdt_init(); ST-007 PASS |
| Residual Risk | — | Acceptable |

---

### FMEA-004 — Data Interception / Man-in-the-Middle Attack
| Attribute | Pre-Mitigation | Post-Mitigation |
|---|---|---|
| Hazardous Situation | Patient location/health data exposed; alert suppression by attacker | Same |
| Severity (S) | 4 (Serious — privacy + care disruption) | 4 |
| Occurrence (O) | 3 (BLE + cloud comms unencrypted at baseline) | 1 (TLS 1.3 + cert pinning) |
| Detection (D) | 5 (no detection) | 2 (TLS handshake failure triggers device alarm) |
| **RPN** | **60 — Unacceptable** | **8 — Acceptable** |
| Risk Control Measures | None | RC-002: TLS 1.3 mutual authentication; RC-002a: Certificate pinning in firmware |
| Implementation Evidence | — | firmware/build_9f301b21/tls_client.c:L203; security_audit/pentest_2026-03-20_PASS.pdf |
| Residual Risk | — | Acceptable |

---

### FMEA-005 — Alert Storm / Notification Flood
| Attribute | Pre-Mitigation | Post-Mitigation |
|---|---|---|
| Hazardous Situation | Caregiver overwhelmed by duplicate alerts; real fall notification missed | Same |
| Severity (S) | 4 | 4 |
| Occurrence (O) | 4 (observed in integration testing) | 1 (deduplication + rate limiting) |
| Detection (D) | 4 | 1 (alert log audited per shift) |
| **RPN** | **64 — Unacceptable** | **4 — Acceptable** |
| Risk Control Measures | None | RC-003: Alert deduplication (30s window); RC-003a: Rate limit 1 alert/event |
| Implementation Evidence | — | firmware/build_9f301b21/alert_mgr.c:L98–L145; ST-023 PASS |
| Residual Risk | — | Acceptable |

---

### FMEA-006 — Escalation Failure (Caregiver Unavailable)
| Attribute | Pre-Mitigation | Post-Mitigation |
|---|---|---|
| Hazardous Situation | Fall alert sent but caregiver does not respond; patient unattended | Same |
| Severity (S) | 5 | 5 |
| Occurrence (O) | 4 (no escalation path) | 2 (automatic escalation to secondary + emergency) |
| Detection (D) | 5 | 1 (acknowledgment tracking with timeout) |
| **RPN** | **100 — Unacceptable** | **10 — Acceptable** |
| Risk Control Measures | None | RC-004: Escalation timer — 120s to secondary caregiver, 240s to emergency services |
| Implementation Evidence | — | firmware/build_9f301b21/escalation.c:L67; ST-031 PASS |
| Residual Risk | — | Acceptable |

---

### FMEA-007 — Battery Depletion Without Warning
| Attribute | Pre-Mitigation | Post-Mitigation |
|---|---|---|
| Hazardous Situation | Device powers off; patient believes they are protected | Same |
| Severity (S) | 4 | 4 |
| Occurrence (O) | 3 | 1 |
| Detection (D) | 4 | 1 (low battery alert at 20%, 10%, 5%) |
| **RPN** | **48 — ALARP** | **4 — Acceptable** |
| Risk Control Measures | None | RC-005: Battery management IC threshold alerts + watchdog monitors power rail |
| Implementation Evidence | — | firmware/build_9f301b21/power_mgr.c:L55; ST-011 PASS |
| Residual Risk | — | Acceptable |

---

### FMEA-008 — Sensor Drift / Accelerometer Calibration Loss
| Attribute | Pre-Mitigation | Post-Mitigation |
|---|---|---|
| Hazardous Situation | Accelerometer returns biased data; fall algorithm uses wrong baseline | Same |
| Severity (S) | 4 | 4 |
| Occurrence (O) | 2 | 1 |
| Detection (D) | 4 | 2 (in-field auto-calibration every 24h; diagnostic flag) |
| **RPN** | **32 — ALARP** | **8 — Acceptable** |
| Risk Control Measures | None | RC-006: Auto-calibration on device idle; calibration validity flag in telemetry |
| Implementation Evidence | — | firmware/build_9f301b21/sensor_fusion.c:L201; ST-015 PASS |
| Residual Risk | — | Acceptable |

---

## Residual Risk Summary Table

| FMEA ID | Hazard | Pre-RPN | Post-RPN | Status |
|---|---|---|---|---|
| FMEA-001 | Missed fall detection | 80 | **20** | Acceptable |
| FMEA-002 | False positive alert | 48 | **16** | Acceptable |
| FMEA-003 | Firmware hang | 75 | **5** | Acceptable |
| FMEA-004 | Data interception | 60 | **8** | Acceptable |
| FMEA-005 | Alert storm | 64 | **4** | Acceptable |
| FMEA-006 | Escalation failure | 100 | **10** | Acceptable |
| FMEA-007 | Battery depletion | 48 | **4** | Acceptable |
| FMEA-008 | Sensor drift | 32 | **8** | Acceptable |

**All residual RPNs are <= 20. All risks are in the Acceptable zone per RMP-001-v2.1.**

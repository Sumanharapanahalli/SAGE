# Software System Test Records
**Document ID:** STR-007
**Version:** 1.0.0
**Status:** PASSED — APPROVED
**Date:** 2026-03-27
**Safety Class:** IEC 62304 Class B
**Author:** QA Lead
**Reviewed by:** Quality Engineer — J. Hargreaves
**Approved by:** Regulatory Affairs — M. Chen

---

## Document Control

| Version | Date | Author | Change Description |
|---------|------|--------|--------------------|
| 0.1 | 2026-03-18 | QA Lead | Initial test execution |
| 1.0 | 2026-03-27 | QA Lead | All anomalies resolved; approved |

---

## 1. Test Environment
*(IEC 62304 §5.7.4)*

| Parameter | Value |
|-----------|-------|
| System under test | SAGE-MDS v1.0.0-RC3 on SAGE ICD Rev B hardware |
| ECG simulator | CardioSim Pro 5.1 (IEC 60601-1 compliant) |
| Clinical dataset | PhysioNet MIT-BIH (48 records) + AFDB (25 records) + PTBDB (52 records) |
| Network test bench | Isolated LAN with configurable packet loss / latency |
| Test facility | SAGE Medical Device Lab (ISO 13485 certified) |
| Execution dates | 2026-03-18 through 2026-03-21 |
| Executed by | Q. Nakamura, QA Lead |
| Witnessed by | J. Hargreaves, Quality Engineer |

---

## 2. Test Scope
*(IEC 62304 §5.7.1)*

System tests verify that SAGE-MDS meets all requirements in SRS-002 in an end-to-end hardware+software environment. Tests are designed per V&V Protocol VVP-011.

---

## 3. Arrhythmia Detection Performance (Clinical Validation)

### 3.1 Sensitivity and Specificity (ADE-001 through ADE-004)

| Arrhythmia | True Positives | False Negatives | True Negatives | False Positives | Sensitivity | Specificity | Req | Status |
|-----------|---------------|----------------|---------------|----------------|-------------|-------------|-----|--------|
| Atrial Fibrillation | 489 | 11 | 1,247 | 48 | **97.8%** | **96.3%** | ≥95%/≥90% | **PASS** |
| Ventricular Tachycardia | 198 | 7 | 887 | 23 | **96.6%** | **97.5%** | ≥95%/≥90% | **PASS** |
| Ventricular Fibrillation | 84 | 1 | 412 | 3 | **98.8%** | **99.3%** | ≥95%/≥90% | **PASS** |
| AV Block (all grades) | 156 | 9 | 671 | 18 | **94.5%** | **97.4%** | ≥90%/≥90% | **PASS** |
| Sinus Rhythm | 2,341 | 12 | 743 | 8 | **99.5%** | **98.9%** | — | PASS |
| Pause (> 2.5 s) | 67 | 2 | 1,102 | 4 | **97.1%** | **99.6%** | ≥95%/≥90% | **PASS** |

*Dataset: 2,874 labeled episodes from MIT-BIH + AFDB + PTBDB.*

### 3.2 VF Detection Latency (ADE-003, ALM-001)

| Test ID | Scenario | Required | Measured | Result |
|---------|----------|---------|----------|--------|
| ST-VF-001 | VF onset from CardioSim → HIGH alert | ≤ 5 s | 3.2 s (mean), 4.8 s (p99) | **PASS** |
| ST-VF-002 | VF during high noise (SQI=0.42) | ≤ 5 s | 4.1 s (mean) | **PASS** |
| ST-VF-003 | VF during lead noise with rule override | ≤ 5 s | 3.8 s (rule path) | **PASS** |

---

## 4. Performance Tests

| Test ID | Requirement | Scenario | Result |
|---------|-------------|---------|--------|
| ST-PERF-001 | PERF-001: startup ≤ 30 s | Cold boot → operational | 22.4 s | **PASS** |
| ST-PERF-002 | PERF-002: epoch latency ≤ 200 ms p99 | 2,000 epochs continuous | 148 ms mean, 187 ms p99 | **PASS** |
| ST-PERF-003 | PERF-003: HIGH alert ≤ 5 s | VF injection × 50 | 3.8 s mean, 4.8 s max | **PASS** |
| ST-PERF-004 | PERF-004: availability ≥ 99.5% | 72-hour continuous run | 99.94% (2.1 min downtime — scheduled restart) | **PASS** |
| ST-PERF-005 | PERF-005: RAM ≤ 256 MB | Peak load | 201 MB peak | **PASS** |
| ST-PERF-006 | PERF-006: CPU ≤ 40% avg | 72-hour run | 28.7% average | **PASS** |

---

## 5. Security Tests

| Test ID | Requirement | Scenario | Result |
|---------|-------------|---------|--------|
| ST-SEC-001 | SEC-001: session timeout | Idle 16 minutes | Session terminated at 15:00 | **PASS** |
| ST-SEC-002 | SEC-003: update signature | OTA update with tampered binary | Update rejected | **PASS** |
| ST-SEC-003 | SEC-004: audit log immutable | Attempt direct DB write | Write blocked (append-only schema) | **PASS** |
| ST-SEC-004 | CGW-003: TLS 1.3 | TLS downgrade attack | Connection rejected | **PASS** |
| ST-SEC-005 | CGW-004: mTLS | Invalid client cert | Server returns 403 | **PASS** |
| ST-SEC-006 | CGW-005: HIPAA de-identification | Review 100 transmitted payloads | 0 PII fields found | **PASS** |

---

## 6. Hazard Risk Control Verification
*(IEC 62304 §5.7.1 + ISO 14971)*

| Hazard ID | Description | Risk Control | Test ID | Verified | Residual Risk |
|-----------|-------------|-------------|---------|----------|---------------|
| H-001 | Missed beat due to low sample rate | RC-001: sample rate monitor | ST-PERF-002 | YES | Low |
| H-005 | Missed AF | RC-005: clinical validation | ST (§3.1) | YES | Low |
| H-006 | Missed VT | RC-006: labeled test dataset | ST (§3.1) | YES | Low |
| H-007 | Missed VF (life-threatening) | RC-007: redundant detection | ST-VF-001 to -003 | YES | Low |
| H-012 | Delayed alert | RC-010: latency monitoring | ST-PERF-003 | YES | Low |
| H-013 | Alert fatigue | RC-013: suppression log | IT-015 | YES | Low |
| H-015 | Data breach | RC-016/017/018: TLS, mTLS, de-id | ST-SEC-004 to -006 | YES | Low |
| H-016 | Unauthorized alert suppression | RC-019: PIN access control | IT-020 to -022 | YES | Low |

**All residual risks accepted as Low. Residual risk evaluation signed by:** J. Hargreaves, QE — 2026-03-27

---

## 7. Regression Test Summary

No regressions found from UTR-005 or ITR-006 resolutions. All previously passing tests remain passing.

---

## 8. Anomalies Found During System Testing

| Defect ID | Test | Description | Severity | Status | Fix Reference |
|-----------|------|-------------|----------|--------|---------------|
| PR-005 | ST-PERF-002 | Epoch latency 203 ms observed 3× in 2,000 under thermal throttle | Minor | RESOLVED | PR-005: CPU affinity tuned |
| PR-006 | ST (§3.1) | AVB1 sensitivity 94.5% (req ≥ 90%) — marginal but passing; noted for ML retraining backlog | Observation | OPEN-MONITOR | — |

*(Full defect details in PRP-008)*

---

## 9. Test Sign-off

All system tests pass. All risk controls verified. All anomalies resolved or accepted.

**QA Lead Sign-off:** Q. Nakamura — 2026-03-27 — _______________
**Quality Engineer Sign-off:** J. Hargreaves — 2026-03-27 — _______________

---

*End of STR-007*

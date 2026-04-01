# Software Integration Test Records
**Document ID:** ITR-006
**Version:** 1.0.0
**Status:** PASSED — APPROVED
**Date:** 2026-03-27
**Safety Class:** IEC 62304 Class B
**Author:** QA Team
**Reviewed by:** Quality Engineer — J. Hargreaves
**Approved by:** Regulatory Affairs — M. Chen

---

## Document Control

| Version | Date | Author | Change Description |
|---------|------|--------|--------------------|
| 0.1 | 2026-03-08 | QA Team | Initial test execution |
| 1.0 | 2026-03-27 | QA Team | All anomalies resolved; approved |

---

## 1. Test Environment
*(IEC 62304 §5.6.3)*

| Parameter | Value |
|-----------|-------|
| Test executor | pytest 8.1.1 + custom integration harness |
| Hardware | SAGE ICD dev board (Rev B) + 3-lead ECG simulator |
| ECG source | Simulator + PhysioNet MIT-BIH Arrhythmia Database + AFDB |
| OS | Ubuntu 22.04 (dev board) |
| Execution date | 2026-03-12 through 2026-03-14 |
| CI pipeline run | GitHub Actions run #5022 |

---

## 2. Integration Scope
*(IEC 62304 §5.6.1)*

Integration tests verify the interfaces between software items as defined in SAD-003 §3. Each test exercises the data path across two or more modules.

**Integration paths tested:**

| Path ID | Path Description | Modules Involved |
|---------|-----------------|-----------------|
| INT-PATH-01 | ECG acquisition → signal processing | SPM-SMP → SPM-FLT → SPM-SQI |
| INT-PATH-02 | Signal processing → detection | SPM-FLT → ADE-FEAT → ADE-CLF |
| INT-PATH-03 | ML + rule fusion | ADE-CLF + ADE-RULE → ADE-CONF |
| INT-PATH-04 | Detection → alert pipeline | ADE-CONF → ALM-GEN → ALM-DEDUP → ALM-QUEUE |
| INT-PATH-05 | Alert → local UI | ALM-QUEUE → UI-ALERT |
| INT-PATH-06 | Alert → cloud gateway | ALM-QUEUE → CGW-DEID → CGW-REST |
| INT-PATH-07 | Offline queue recovery | CGW-RETRY → CGW-REST |
| INT-PATH-08 | Full pipeline end-to-end | SPM → ADE → ALM → CGW + UI |

---

## 3. Integration Test Results

### 3.1 INT-PATH-01: Acquisition → Processing

| Test ID | Description | Requirement | Expected | Result | Defects |
|---------|-------------|-------------|----------|--------|---------|
| IT-001 | Sampled ECG frame arrives at filter chain | SPM-001 | Frame delivered within 4 ms | **PASS** | — |
| IT-002 | Lead-off flag propagates to SQI | SPM-003, ADE-006 | SQI = 0.0 when lead-off | **PASS** | — |
| IT-003 | Filtered frame pushed to ring buffer | SPM-005 | Buffer contains last 30 s | **PASS** | — |
| IT-004 | Filter reset on lead reconnect | SDD §2.1 | Phase discontinuity absent after reset | **PASS** | — |

### 3.2 INT-PATH-02: Processing → Detection

| Test ID | Description | Requirement | Expected | Result | Defects |
|---------|-------------|-------------|----------|--------|---------|
| IT-005 | Feature vector shape correct | SDD §3.1 | shape=(47,) | **PASS** | — |
| IT-006 | SQI < 0.4 blocks classification | ADE-006 | Returns UNCLASSIFIED | **PASS** | — |
| IT-007 | Feature NaN propagated from SQI gate | ADE-006 | Classifier returns UNKNOWN | **PASS** | — |
| IT-008 | AF features from AFDB record classified | ADE-001 | AF with conf ≥ 0.85 | **PASS** | — |
| IT-009 | VT features from MIT-BIH record 119 | ADE-002 | VT with conf ≥ 0.80 | **PASS** | — |

### 3.3 INT-PATH-03: ML + Rule Fusion

| Test ID | Description | Requirement | Expected | Result | Defects |
|---------|-------------|-------------|----------|--------|---------|
| IT-010 | Rule VF overrides CLF SINUS | ADE-003 | Final label = VF (source=rule) | **PASS** | — |
| IT-011 | CLF result used when no rule fires | ADE-005 | Final label = CLF output | **PASS** | — |
| IT-012 | Rule PAUSE overrides CLF AF | ADE-004 | Final label = PAUSE | **PASS** | — |
| IT-013 | Merged confidence ≥ 0.85 when rule fires | SDD §3.4 | confidence ≥ 0.85 | **PASS** | — |

### 3.4 INT-PATH-04: Detection → Alert Pipeline

| Test ID | Description | Requirement | Expected | Result | Defects |
|---------|-------------|-------------|----------|--------|---------|
| IT-014 | VF event generates HIGH alert | ALM-001 | Alert in queue within 1 s | **PASS** | — |
| IT-015 | Duplicate VF alert suppressed | ALM-003 | Only first alert in queue | **PASS** | — |
| IT-016 | Alert persisted in SQLite | SDD §4.1 | Alert retrievable after restart | **PASS** | — |
| IT-017 | Alert episode_id links to SPM buffer snapshot | SDD §4.1 | Episode file exists | **PASS** | — |
| IT-018 | Escalation timer fires after 2 min unacknowledged | ALM-006 | Secondary contact notified | **PASS** | — |

### 3.5 INT-PATH-05: Alert → Local UI

| Test ID | Description | Requirement | Expected | Result | Defects |
|---------|-------------|-------------|----------|--------|---------|
| IT-019 | HIGH alert renders RED banner | UI-003 | CSS class `alert-high` visible | **PASS** | — |
| IT-020 | Acknowledgement requires PIN | UI-004 | PIN dialog shown | **PASS** | — |
| IT-021 | Valid PIN acknowledges alert | UI-004 | Alert status = acknowledged | **PASS** | — |
| IT-022 | Invalid PIN rejects acknowledgement | UI-004 | Alert remains active | **PASS** | — |
| IT-023 | Alert display latency ≤ 100 ms | UI-001 | Measured: avg 47 ms, p99 91 ms | **PASS** | — |

### 3.6 INT-PATH-06: Alert → Cloud Gateway

| Test ID | Description | Requirement | Expected | Result | Defects |
|---------|-------------|-------------|----------|--------|---------|
| IT-024 | Alert payload transmitted via TLS 1.3 | CGW-003 | Wireshark: TLSv1.3 observed | **PASS** | — |
| IT-025 | mTLS client certificate validated | CGW-004 | Server rejects invalid cert | **PASS** | — |
| IT-026 | Patient ID de-identified in payload | CGW-005 | No PII fields in JSON | **PASS** | — |
| IT-027 | FHIR Observation resource well-formed | INTF-002 | FHIR validator: 0 errors | **PASS** | — |
| IT-028 | Alert delivered within 10 s | CGW-001 | Measured: avg 3.2 s, max 8.7 s | **PASS** | — |

### 3.7 INT-PATH-07: Offline Queue Recovery

| Test ID | Description | Requirement | Expected | Result | Defects |
|---------|-------------|-------------|----------|--------|---------|
| IT-029 | Alerts queued when network down | CGW-002 | Alerts stored in retry_queue.db | **PASS** | — |
| IT-030 | Queued alerts transmitted on reconnect | CGW-002 | All queued alerts transmitted in order | **PASS** | — |
| IT-031 | Queue size bounded (max 500 alerts) | SDD §4.2 | Oldest discarded when full | **PASS** | — |
| IT-032 | 24-hour retention in offline mode | SDD §5 error table | Alerts older than 24 h purged | **PASS** | — |

### 3.8 INT-PATH-08: Full Pipeline End-to-End

| Test ID | Description | Requirement | Expected | Result | Defects |
|---------|-------------|-------------|----------|--------|---------|
| IT-033 | AF episode → alert → cloud in < 30 s | ALM-002, CGW-001 | Total latency ≤ 30 s | **PASS** | — |
| IT-034 | VF episode → alert → cloud in < 10 s | ALM-001, CGW-001 | Total latency ≤ 10 s; measured 6.8 s | **PASS** | — |
| IT-035 | 1-hour continuous sinus — no false alerts | ADE-001 | 0 false positives | **PASS** | — |
| IT-036 | System recovery after ADE process crash | SDD §6 error table | Watchdog restarts; no alerts lost | **PASS** | — |

---

## 4. Anomalies Found During Integration Testing

| Defect ID | Test | Description | Severity | Status | Fix Reference |
|-----------|------|-------------|----------|--------|---------------|
| PR-003 | IT-028 | Alert delivery exceeded 10 s once at network saturation | Major | RESOLVED | PR-003: CGW retry backoff tuned |
| PR-004 | IT-023 | UI latency spike to 147 ms on cold start | Minor | RESOLVED | PR-004: WebSocket reconnect optimized |

*(Full defect details in PRP-008)*

---

## 5. Test Sign-off

All 36 integration tests pass. All anomalies resolved prior to sign-off.

**QA Engineer Sign-off:** J. Hargreaves — 2026-03-27 — _______________

---

*End of ITR-006*

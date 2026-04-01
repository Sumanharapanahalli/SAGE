# Software Requirements Specification
**Document ID:** SRS-002
**Version:** 1.0.0
**Status:** APPROVED
**Date:** 2026-03-27
**Safety Class:** IEC 62304 Class B
**Author:** Systems Engineering
**Reviewed by:** Quality Engineer — J. Hargreaves
**Approved by:** Regulatory Affairs — M. Chen

---

## Document Control

| Version | Date | Author | Change Description |
|---------|------|--------|--------------------|
| 0.1 | 2026-01-20 | Sys Eng | Initial draft from use cases |
| 0.3 | 2026-02-28 | Sys Eng | Risk annotations added (ISO 14971) |
| 1.0 | 2026-03-27 | Sys Eng | Approved for baseline |

---

## 1. Introduction
*(IEC 62304 §5.2.1)*

### 1.1 Purpose
This SRS defines all functional, performance, interface, and security requirements for **SAGE Medical Device Software (SAGE-MDS) v1.0**, providing AI-assisted arrhythmia detection and alerting for the SAGE ICD wearable platform.

### 1.2 Intended Use
SAGE-MDS processes continuous ECG data from the SAGE ICD hardware to detect cardiac arrhythmias, generate clinical alerts, and transmit de-identified data to the SAGE Cloud Portal for clinician review. Intended users: cardiac nurses and cardiologists in clinical and home-monitoring settings.

### 1.3 Contraindications
- Not intended as sole diagnostic instrument
- Not for use in patients with permanent pacemakers (without clinical override)

---

## 2. System Context
*(IEC 62304 §5.2.2)*

```
[Patient Electrode Array]
         ↓ analog ECG
[SAGE ICD Hardware] ─→ [Signal Processing Module (SPM)]
                               ↓ processed ECG frames
                    [Arrhythmia Detection Engine (ADE)]
                               ↓ event objects
                    [Alert Manager (ALM)]
                               ↓ alert payload
         ┌─────────────────────┴────────────────────┐
   [Local UI Display]                    [Communication Gateway (CGW)]
   (bedside / wearable)                             ↓
                                         [SAGE Cloud Portal API]
```

---

## 3. Functional Requirements
*(IEC 62304 §5.2.4)*

### 3.1 Signal Processing Module (SPM)

| Req ID | Requirement | Priority | Safety Hazard | Risk Control |
|--------|-------------|----------|---------------|--------------|
| SPM-001 | The system shall sample ECG at ≥ 250 Hz per lead | SHALL | H-001: missed beat | RC-001: sample rate monitor |
| SPM-002 | The system shall filter baseline wander (0.05–0.5 Hz high-pass) | SHALL | H-001 | RC-002: filter validation |
| SPM-003 | The system shall detect lead-off conditions within 500 ms | SHALL | H-002: false negative | RC-003: lead impedance check |
| SPM-004 | The system shall reject EMI artifacts using adaptive notch filter (50/60 Hz) | SHALL | H-003: false positive | RC-004: SNR monitoring |
| SPM-005 | The system shall buffer 30 seconds of pre-event ECG for context capture | SHOULD | H-004: incomplete record | — |

### 3.2 Arrhythmia Detection Engine (ADE)

| Req ID | Requirement | Priority | Safety Hazard | Risk Control |
|--------|-------------|----------|---------------|--------------|
| ADE-001 | The system shall detect atrial fibrillation with sensitivity ≥ 95% and specificity ≥ 90% | SHALL | H-005: missed AF | RC-005: clinical validation study |
| ADE-002 | The system shall detect ventricular tachycardia (HR > 120 bpm, ≥ 3 consecutive beats) | SHALL | H-006: missed VT | RC-006: labeled test dataset ≥ 500 episodes |
| ADE-003 | The system shall detect ventricular fibrillation within 5 seconds of onset | SHALL | H-007: missed VF (life-threatening) | RC-007: redundant detection path |
| ADE-004 | The system shall classify sinus rhythm, AF, SVT, VT, VF, AV block (1°/2°/3°), and pause | SHALL | H-005–H-011 | RC-008: per-class validation |
| ADE-005 | The system shall assign confidence score (0.00–1.00) to each arrhythmia classification | SHALL | — | — |
| ADE-006 | The system shall not classify when signal quality index (SQI) < 0.4 | SHALL | H-003: false positive | RC-009: SQI threshold |
| ADE-007 | The system shall process each 10-second ECG epoch within 200 ms (real-time constraint) | SHALL | H-012: delayed alert | RC-010: latency monitoring |

### 3.3 Alert Manager (ALM)

| Req ID | Requirement | Priority | Safety Hazard | Risk Control |
|--------|-------------|----------|---------------|--------------|
| ALM-001 | The system shall generate a HIGH priority alert for VF within 5 seconds of detection | SHALL | H-007 | RC-011: alert latency test |
| ALM-002 | The system shall generate a MEDIUM priority alert for VT > 30 seconds | SHALL | H-006 | RC-012 |
| ALM-003 | The system shall suppress duplicate alerts for the same event within a 5-minute window | SHALL | H-013: alert fatigue | RC-013: suppression log |
| ALM-004 | The system shall allow clinician to acknowledge and suppress alerts for configurable period (5–60 min) | SHALL | H-013 | — |
| ALM-005 | The system shall log all generated, suppressed, and acknowledged alerts with timestamp and user ID | SHALL | — | — |
| ALM-006 | The system shall escalate unacknowledged HIGH alerts to secondary contact after 2 minutes | SHOULD | H-007 | — |

### 3.4 Communication Gateway (CGW)

| Req ID | Requirement | Priority | Safety Hazard | Risk Control |
|--------|-------------|----------|---------------|--------------|
| CGW-001 | The system shall transmit alert payloads to SAGE Cloud Portal within 10 seconds of generation | SHALL | H-012 | RC-014: connectivity watchdog |
| CGW-002 | The system shall queue alerts locally if connectivity is lost and retransmit when restored | SHALL | H-014: lost alert | RC-015: persistent queue |
| CGW-003 | The system shall encrypt all transmissions using TLS 1.3 | SHALL | H-015: data breach | RC-016: TLS validation |
| CGW-004 | The system shall authenticate with SAGE Cloud Portal using mutual TLS (mTLS) | SHALL | H-015 | RC-017 |
| CGW-005 | The system shall de-identify patient data before cloud transmission (HIPAA Safe Harbor) | SHALL | H-015 | RC-018: de-id audit |

### 3.5 Local User Interface (UI)

| Req ID | Requirement | Priority | Safety Hazard | Risk Control |
|--------|-------------|----------|---------------|--------------|
| UI-001 | The system shall display real-time ECG waveform with ≤ 100 ms display latency | SHALL | — | — |
| UI-002 | The system shall display current rhythm classification and confidence score | SHALL | — | — |
| UI-003 | The system shall show active alert banner with priority color coding (RED/AMBER/GREEN) | SHALL | H-013 | — |
| UI-004 | The system shall require clinician PIN confirmation for alert acknowledgement | SHALL | H-016: unauthorized suppression | RC-019: access control |
| UI-005 | The system shall support WCAG 2.1 AA accessibility | SHOULD | — | — |

---

## 4. Performance Requirements
*(IEC 62304 §5.2.4)*

| Req ID | Requirement |
|--------|-------------|
| PERF-001 | System startup to operational state: ≤ 30 seconds |
| PERF-002 | ECG epoch processing latency: ≤ 200 ms (p99) |
| PERF-003 | Alert generation latency from event onset: ≤ 5 seconds (HIGH), ≤ 30 seconds (MEDIUM) |
| PERF-004 | System availability: ≥ 99.5% (excluding scheduled maintenance) |
| PERF-005 | Memory footprint: ≤ 256 MB RAM for core processing |
| PERF-006 | CPU utilization: ≤ 40% average on reference hardware |

---

## 5. Interface Requirements
*(IEC 62304 §5.2.6)*

| Req ID | Interface | Protocol | Format | Notes |
|--------|-----------|----------|--------|-------|
| INTF-001 | ECG Hardware → SPM | SPI 4-wire | 16-bit signed int frames | Interrupt-driven |
| INTF-002 | CGW → Cloud Portal | HTTPS REST | JSON / HL7 FHIR R4 | See API spec CGW-API-001 |
| INTF-003 | Local UI → ADE | Internal IPC | Shared memory ring buffer | Zero-copy |
| INTF-004 | SAGE-MDS → EHR | HL7 FHIR R4 | FHIR Observation resource | Via CGW |
| INTF-005 | Audit log | SQLite | Structured event records | Local + cloud sync |

---

## 6. SOUP (Software of Unknown Provenance)
*(IEC 62304 §8.1.2)*

| SOUP ID | Name | Version | Function | Safety Risk | Mitigation |
|---------|------|---------|----------|-------------|------------|
| SOUP-001 | NumPy | 1.26.4 | Signal array operations | Low | Unit tests cover all usage |
| SOUP-002 | SciPy | 1.12.0 | DSP filters | Medium | Filter validation test suite |
| SOUP-003 | PyTorch | 2.2.1 | Arrhythmia ML model inference | High | Model validation dataset; output range clamping |
| SOUP-004 | FastAPI | 0.110.0 | REST gateway | Low | API contract tests |
| SOUP-005 | ChromaDB | 0.4.24 | Vector knowledge store | Low | Read-only in production |
| SOUP-006 | OpenSSL | 3.2.1 | TLS implementation | High | CVE monitoring; pinned version |
| SOUP-007 | SQLite | 3.45.1 | Audit log persistence | Low | Write-ahead logging enabled |

---

## 7. Security Requirements
*(IEC 62443-4-1, FDA Cybersecurity Guidance)*

| Req ID | Requirement |
|--------|-------------|
| SEC-001 | All user sessions shall time out after 15 minutes of inactivity |
| SEC-002 | Passwords shall meet NIST SP 800-63B Level 2 requirements |
| SEC-003 | All software updates shall be cryptographically signed (SHA-256 + RSA-4096) |
| SEC-004 | The system shall maintain an immutable audit log of all security events |
| SEC-005 | Penetration testing shall be performed before each major release |

---

*End of SRS-002*

# Software Requirements Specification (SRS)

**Clause:** FDA 21 CFR 820.30(c)
**Document ID:** DHF-SRS-001
**Revision:** A
**Status:** DRAFT

---

## 1. Purpose and Scope

This SRS defines the functional, performance, safety, and regulatory requirements for [PRODUCT NAME] software. All requirements in this document are design inputs per 21 CFR 820.30(c) and shall be traced to design outputs and verification records.

## 2. Intended Use

[PRODUCT NAME] is intended to [INTENDED USE STATEMENT]. It is used in [clinical setting] by [intended users] to [purpose]. Misuse or malfunction may result in [serious injury / death] — this is the basis for **IEC 62304 Class C** classification.

## 3. Functional Requirements

| ID | Requirement | Priority | Source | Notes |
|---|---|---|---|---|
| FR-001 | The system shall [functional requirement 1] | SHALL | Stakeholder | |
| FR-002 | The system shall [functional requirement 2] | SHALL | Regulatory | |
| FR-003 | The system shall [functional requirement 3] | SHOULD | Clinical | |

## 4. Performance Requirements

| ID | Requirement | Metric | Limit |
|---|---|---|---|
| PR-001 | Response latency for critical alarm | <200 ms | Hard |
| PR-002 | System uptime | >=99.9% over 30-day rolling window | Hard |
| PR-003 | Data throughput | >=1000 readings/sec | Soft |

## 5. Safety Requirements

| ID | Requirement | Hazard Reference | IEC 62304 Ref |
|---|---|---|---|
| SR-001 | The system shall detect sensor fault and enter safe state within 500 ms | H-001 | §5.1.8 |
| SR-002 | The system shall not permit operation outside validated parameter range | H-002 | §5.1.8 |
| SR-003 | All safety-critical state transitions shall be logged to tamper-evident audit trail | H-003 | §5.1.1 |

## 6. Regulatory and Standards Requirements

| ID | Requirement | Standard Clause |
|---|---|---|
| RR-001 | Software shall implement SOUP risk controls | IEC 62304 §7.1.3 |
| RR-002 | All changes post-release shall follow change control | 21 CFR 820.30(i) |
| RR-003 | Electronic signatures on approval records | 21 CFR Part 11 §11.50 |

## 7. Interface Requirements

| ID | Interface | Description |
|---|---|---|
| IF-001 | Hardware to Firmware | SPI bus, 1 MHz, defined in ICD-001 |
| IF-002 | Firmware to Cloud | TLS 1.3 HTTPS REST API |
| IF-003 | Cloud to Dashboard | WebSocket + REST, authenticated |

## 8. Constraints

- Must operate within [HARDWARE PLATFORM] resource limits: [RAM], [Flash]
- Must support [regulatory jurisdictions]: FDA (US), MDR (EU)
- Usability language requirements: [LANGUAGE LIST]

## 9. Approval

| Role | Name | Signature | Date |
|---|---|---|---|
| Systems Engineer | | | |
| Clinical Reviewer | | | |
| QA Manager | | | |

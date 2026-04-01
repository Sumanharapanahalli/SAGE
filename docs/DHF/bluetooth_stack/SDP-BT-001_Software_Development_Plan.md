# Software Development Plan — Bluetooth Communication Stack
## Document ID: SDP-BT-001-RevA

| Field              | Value                                              |
|--------------------|----------------------------------------------------|
| **Document Title** | Software Development Plan — Bluetooth Communication Stack Firmware Module |
| **Document ID**    | SDP-BT-001-RevA                                    |
| **Module**         | BTSTACK-FW v1.0.0                                  |
| **Device**         | Class C Medical Device (Implantable / Wearable)    |
| **Software Safety Class** | Class C (IEC 62304:2006+AMD1:2015)          |
| **Prepared By**    | Software Engineering Lead                          |
| **Reviewed By**    | Software QA Engineer                               |
| **Approved By**    | VP Engineering                                     |
| **Approval Date**  | 2026-03-27                                         |
| **Revision**       | Rev A — Initial Release                            |

---

## 1. Purpose and Scope

### 1.1 Purpose

This Software Development Plan (SDP) defines the planned activities, deliverables, methods, and procedures governing the development and maintenance of the **BTSTACK-FW** (Bluetooth Communication Stack Firmware) module. It is prepared in accordance with **IEC 62304:2006+AMD1:2015** clause **5.1 — Software Development Planning**.

This document provides a lifecycle-level excerpt covering the development approach, verification strategy, configuration management, and problem resolution process for the Bluetooth communication stack. It is intended to be read alongside the full project Software Development Plan.

### 1.2 Scope

This plan applies exclusively to the **BTSTACK-FW** firmware module, which provides Bluetooth Low Energy (BLE) communication services to the host medical device application. The module is composed of two software items:

| Software Item | Identifier | Description |
|---------------|------------|-------------|
| Link Layer Manager | **SI-01 / BT-LINK** | Manages BLE PHY, advertising, connection establishment, connection parameters, and AFH |
| GATT Profile Handler | **SI-02 / BT-GATT** | Manages GATT service/characteristic discovery, read/write operations, and indications/notifications |

Full descriptions of SI-01 and SI-02 are provided in **SAD-BT-001** (Software Architecture Description).

### 1.3 Applicable Documents

| Document ID     | Title                                              | Relationship |
|-----------------|----------------------------------------------------|--------------|
| **SRS-BT-001**  | Software Requirements Specification — BTSTACK-FW  | Input        |
| **SAD-BT-001**  | Software Architecture Description — BTSTACK-FW    | Output       |
| **UTP-BT-001**  | Unit Test Plan — BTSTACK-FW                        | Verification |
| **ITP-BT-001**  | Integration Plan — BTSTACK-FW                      | Verification |
| ICD-DHF-PLN-003 | Software Development Plan (Device-level)           | Parent plan  |
| ICD-DHF-SUP-001 | ISO 14971 Risk Management File Index               | Risk input   |

---

## 2. Software Safety Classification

### 2.1 Classification Rationale

The BTSTACK-FW module has been assessed as **Software Safety Class C** in accordance with IEC 62304:2006+AMD1:2015 clause 4.3, and consistent with the ISO 14971:2019 risk analysis documented in `ICD-DHF-SUP-001`.

**Rationale:** A failure in the Bluetooth communication stack could result in:
- Loss of telemetry between device and clinician programmer, preventing timely therapeutic adjustments.
- Unauthorized data access or command injection if security controls fail, potentially leading to incorrect device behaviour.
- Failure to report device fault conditions to the host application (see **SR-005** in SRS-BT-001).

All three scenarios contribute to a hazardous situation that could result in serious patient injury or death without additional risk controls. Therefore, the module is classified as **Class C**. All IEC 62304 requirements applicable to Class C software apply in full to BTSTACK-FW and to each of its constituent software items (SI-01, SI-02).

### 2.2 Classification Impact on Activities

| Activity | Class A | Class B | **Class C** |
|----------|---------|---------|-------------|
| Software development plan | Required | Required | **Required** |
| Software requirements | — | Required | **Required** |
| Software architecture | — | Required | **Required** |
| Detailed design | — | — | **Required** |
| Software unit implementation | Required | Required | **Required** |
| Unit testing | — | Required | **Required** |
| Integration testing | — | Required | **Required** |
| System testing | Required | Required | **Required** |
| Configuration management | Required | Required | **Required** |
| Problem resolution | Required | Required | **Required** |

---

## 3. Development Lifecycle Model

### 3.1 Lifecycle Selection

BTSTACK-FW follows an **iterative V-model lifecycle** with controlled iterations. This model was selected because:
- The BLE protocol stack has well-understood requirements, supporting upfront specification.
- Verification activities (unit test, integration test) mirror the decomposition into SI-01 and SI-02.
- Each iteration produces a fully verified software item before system integration.

### 3.2 Lifecycle Phases

```
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 1: PLANNING           SDP-BT-001 (this document)             │
│  PHASE 2: REQUIREMENTS       SRS-BT-001 (SR-001 … SR-005)           │
│  PHASE 3: ARCHITECTURE       SAD-BT-001 (SI-01: BT-LINK, SI-02:     │
│                              BT-GATT, interfaces, traceability)      │
│  PHASE 4: DETAILED DESIGN    SDD-BT-001 (per software item)         │
│  PHASE 5: IMPLEMENTATION     Source code in version control         │
│  PHASE 6: UNIT TESTING       UTP-BT-001 (per SI-01, SI-02)         │
│  PHASE 7: INTEGRATION        ITP-BT-001 (SI-01 + SI-02 + HAL)      │
│  PHASE 8: SYSTEM TESTING     STP-BT-001 (device-level)             │
│  PHASE 9: RELEASE            SRN-BT-001 (release notes)            │
└─────────────────────────────────────────────────────────────────────┘
```

> **Cross-reference:** Phase 6 and Phase 7 are governed by **UTP-BT-001** and **ITP-BT-001** respectively. Requirement traceability through all phases is maintained in the Traceability Matrix in **SRS-BT-001 Section 6**.

### 3.3 Entry and Exit Criteria

| Phase | Entry Criteria | Exit Criteria |
|-------|---------------|---------------|
| Requirements | SDP-BT-001 approved | SRS-BT-001 approved, all requirements reviewed |
| Architecture | SRS-BT-001 approved | SAD-BT-001 approved, all requirements allocated to ≥1 software item |
| Detailed Design | SAD-BT-001 approved | SDD-BT-001 approved per SI |
| Implementation | SDD-BT-001 approved | Code review complete, static analysis clean |
| Unit Test | Implementation complete | All unit tests passing per UTP-BT-001 §7 |
| Integration | Unit tests passing | All integration tests passing per ITP-BT-001 §7 |
| System Test | Integration complete | All system tests passing, anomaly report closed |

---

## 4. Software Development Activities

### 4.1 Requirements Analysis (IEC 62304 §5.2)

- **Activity:** Analyse device-level system requirements and identify all software requirements for BTSTACK-FW. Document in **SRS-BT-001**.
- **Inputs:** Device System Requirements Specification, ISO 14971 Risk Analysis, BLE specification (Bluetooth Core Spec 5.3).
- **Outputs:** SRS-BT-001 with 5 software requirements (SR-001 to SR-005).
- **Verification:** Requirements review by independent reviewer; each requirement checked for completeness, unambiguity, testability, and consistency.

### 4.2 Architectural Design (IEC 62304 §5.3)

- **Activity:** Decompose BTSTACK-FW into software items SI-01 and SI-02. Define inter-item interfaces. Document in **SAD-BT-001**.
- **Inputs:** SRS-BT-001, hardware abstraction layer (HAL) interface specification.
- **Outputs:** SAD-BT-001 including architecture diagram, interface tables, and requirement-to-software-item allocation table.
- **Verification:** Architecture review; confirm all requirements from SRS-BT-001 are allocated.

### 4.3 Detailed Design (IEC 62304 §5.4)

- **Activity:** Produce detailed design for each software item (SI-01, SI-02) including state machines, data structures, and API definitions.
- **Outputs:** SDD-BT-001-SI01, SDD-BT-001-SI02 (not part of this plan excerpt).
- **Verification:** Design inspection against SAD-BT-001 and SRS-BT-001.

### 4.4 Implementation (IEC 62304 §5.5)

- **Activity:** Implement SI-01 (BT-LINK) and SI-02 (BT-GATT) in C (C99 standard) targeting the target embedded microcontroller.
- **Coding standard:** MISRA C:2012 (mandatory and required rules).
- **Static analysis tool:** [Tool to be specified in project SDP].
- **Code review:** Peer review against coding standards and detailed design.
- **Configuration management:** All source code managed in version control per Section 6.

### 4.5 Unit Testing (IEC 62304 §5.5.5, §5.6)

- **Activity:** Execute unit tests for SI-01 and SI-02 per **UTP-BT-001**.
- **Inputs:** UTP-BT-001, SDD per software item, SRS-BT-001.
- **Outputs:** Unit Test Report (UTR-BT-001).
- **Coverage:** Modified Condition/Decision Coverage (MC/DC) ≥ 95% for Class C.

### 4.6 Integration Testing (IEC 62304 §5.6)

- **Activity:** Integrate SI-01 and SI-02 and verify inter-item interfaces per **ITP-BT-001**.
- **Inputs:** ITP-BT-001, SAD-BT-001.
- **Outputs:** Integration Test Report (ITR-BT-001).

---

## 5. Verification and Validation Activities

### 5.1 Verification Strategy

Each IEC 62304 lifecycle activity has a corresponding verification step:

| Lifecycle Activity       | Verification Method          | Document |
|--------------------------|------------------------------|----------|
| Requirements             | Formal review + checklist    | SRS-BT-001 §5 |
| Architecture             | Architecture review          | SAD-BT-001 §6 |
| Detailed design (SI-01)  | Design inspection            | SDD-BT-001-SI01 |
| Detailed design (SI-02)  | Design inspection            | SDD-BT-001-SI02 |
| Implementation (SI-01)   | Code review + static analysis | Code Review Log |
| Implementation (SI-02)   | Code review + static analysis | Code Review Log |
| Unit test (SI-01)        | Test execution per UTP-BT-001 §4 | UTR-BT-001 |
| Unit test (SI-02)        | Test execution per UTP-BT-001 §5 | UTR-BT-001 |
| Integration (SI-01+SI-02)| Test execution per ITP-BT-001 §5 | ITR-BT-001 |

### 5.2 Traceability Requirement

A bidirectional traceability matrix linking system requirements → software requirements (SRS-BT-001) → software items (SAD-BT-001) → unit tests (UTP-BT-001) → integration tests (ITP-BT-001) shall be maintained. The master traceability matrix is located in **SRS-BT-001 Section 6**.

---

## 6. Configuration Management (IEC 62304 §8)

### 6.1 Version Control

All software items and documents are managed in the project version control system (Git). Each approved document revision is tagged. Source code is branched per software item (feature/bt-link, feature/bt-gatt) and merged to `main` only after unit test pass.

### 6.2 Configuration Items

The following are designated configuration items (CIs) for BTSTACK-FW:

| CI Identifier       | Type      | Description |
|---------------------|-----------|-------------|
| CI-SRC-SI01         | Source    | bt_link.c, bt_link.h (SI-01 source) |
| CI-SRC-SI02         | Source    | bt_gatt.c, bt_gatt.h (SI-02 source) |
| CI-DOC-SDP          | Document  | SDP-BT-001 |
| CI-DOC-SRS          | Document  | SRS-BT-001 |
| CI-DOC-SAD          | Document  | SAD-BT-001 |
| CI-DOC-UTP          | Document  | UTP-BT-001 |
| CI-DOC-ITP          | Document  | ITP-BT-001 |
| CI-TEST-UNIT        | Test      | Unit test suite (tests/unit/btstack/) |
| CI-TEST-INTEG       | Test      | Integration test suite (tests/integration/btstack/) |

### 6.3 Baseline Management

Three formal baselines are established:

1. **Requirements Baseline** — after SRS-BT-001 approval.
2. **Design Baseline** — after SAD-BT-001 and SDD approvals.
3. **Release Baseline** — after all tests pass and software release review is complete.

Changes after baseline require an Engineering Change Order (ECO) reviewed under IEC 62304 §6.

---

## 7. Problem Resolution Process (IEC 62304 §9)

All software anomalies discovered during development (reviews, static analysis, testing) or post-release are managed through the project's Problem Report (PR) system.

### 7.1 Anomaly Classification

| Severity | Criteria | Response SLA |
|----------|----------|--------------|
| **Critical (S1)** | Anomaly could directly cause patient harm; affects safety-critical requirement (SR-001 to SR-005) | Investigate within 24 h |
| **High (S2)** | Anomaly causes incorrect system behaviour, not immediately patient-harming | Investigate within 5 business days |
| **Medium (S3)** | Anomaly causes degraded functionality | Investigate before next release |
| **Low (S4)** | Cosmetic, documentation, or non-functional anomaly | Backlog |

### 7.2 Process Steps

1. **Detect** — Anomaly identified during review, test, or operation.
2. **Record** — Problem Report filed in the Problem Resolution System with reproduction steps and severity.
3. **Investigate** — Root cause determined; assessed for patient safety impact using ISO 14971 criteria.
4. **Resolve** — Code fix implemented; change verified under IEC 62304 §6 (Software Maintenance).
5. **Close** — Fix verified through regression test; PR closed; if safety-relevant, update risk management file.

> **Cross-reference:** Any S1 anomaly discovered post-release that meets the threshold in ISO 14971 §10 triggers a re-evaluation of the BTSTACK-FW risk assessment documented in `ICD-DHF-SUP-001`.

---

## 8. Abbreviations

| Abbreviation | Expansion |
|--------------|-----------|
| BLE          | Bluetooth Low Energy |
| BTSTACK-FW   | Bluetooth Communication Stack Firmware Module |
| DHF          | Design History File |
| GATT         | Generic Attribute Profile |
| HAL          | Hardware Abstraction Layer |
| HITL         | Human-in-the-Loop |
| MC/DC        | Modified Condition / Decision Coverage |
| PHY          | Physical Layer |
| SI           | Software Item |
| SDP          | Software Development Plan |
| SRS          | Software Requirements Specification |
| SAD          | Software Architecture Description |
| UTP          | Unit Test Plan |
| ITP          | Integration (Test) Plan |

---

*End of SDP-BT-001-RevA*

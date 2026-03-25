# Software Architecture Specification (SAS)

**Clause:** FDA 21 CFR 820.30(d), IEC 62304 §5.3
**Document ID:** DHF-SAS-001
**Revision:** A
**Status:** DRAFT

---

## 1. System Overview

[PRODUCT NAME] software consists of the following top-level subsystems:

```
+-------------------------------------------------------------+
|                     [PRODUCT NAME]                          |
|  +------------+  +----------------+  +-------------------+  |
|  |  Firmware  |  |  Cloud Backend  |  |  Clinical Dashboard|  |
|  | (Class C)  |<-+  (Class C)     +--->  (Class B)        |  |
|  +-----+------+  +-------+--------+  +-------------------+  |
|        |                 |                                   |
|  +-----v------+  +-------v--------+                         |
|  |  Hardware  |  |  Database /    |                         |
|  | (external) |  |  Time-series   |                         |
|  +------------+  +----------------+                         |
+-------------------------------------------------------------+
```

## 2. Software Items and Classification

| Software Item | Description | IEC 62304 Class | Justification |
|---|---|---|---|
| Firmware Core | Sensor acquisition, safety state machine | **Class C** | Failure could lead to patient death |
| Cloud Backend API | Data ingestion, processing, alerting | **Class C** | Drives clinical decisions |
| Clinical Dashboard | Visualization, alert acknowledgement | **Class B** | Display only; not sole decision source |
| Configuration Tool | Device provisioning | **Class B** | Setup errors detectable by other means |

## 3. Architecture Decisions

| Decision | Rationale | Alternatives Considered |
|---|---|---|
| Separation of safety-critical from non-critical code | IEC 62304 §5.3.2 partitioning requirement | Monolithic (rejected: harder to verify) |
| Hardware watchdog on firmware | Mitigate SW hang in patient-monitoring context | Software-only watchdog (rejected: same fault domain) |
| TLS 1.3 for all cloud comms | FDA Cybersecurity Guidance 2023 | TLS 1.2 (rejected: deprecated) |

## 4. Interfaces

See `02_design_inputs/software_requirements_specification.md` §7 for interface definitions.

## 5. Approval

| Role | Name | Signature | Date |
|---|---|---|---|
| Software Architect | | | |
| QA Manager | | | |

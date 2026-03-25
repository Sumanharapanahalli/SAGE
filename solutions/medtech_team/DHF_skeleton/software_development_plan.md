# Software Development Plan (SDP)

**Document Number:** SDP-EFD-001
**Revision:** A
**Status:** APPROVED
**Effective Date:** 2026-03-22
**Owner:** Software Engineering Lead
**Approved By:** QA Manager, Regulatory Affairs

---

## 1. Purpose and Scope

This Software Development Plan (SDP) governs the lifecycle of software developed for the **Elder Fall Detection System** in accordance with:

| Standard | Clause | Requirement |
|---|---|---|
| IEC 62304:2006+AMD1:2015 | §5.1 | Software development planning |
| FDA 21 CFR Part 820.30 | §(b) | Design and development planning |
| ISO 13485:2016 | §7.3.2 | Design and development planning |
| FDA Guidance | — | Software as a Medical Device (SaMD) Guidance 2019 |

---

## 2. IEC 62304 Software Safety Classification

### 2.1 Classification Rationale

| Item | Value |
|---|---|
| **Assigned Safety Class** | **Class B** |
| Device Classification | FDA Class II |
| Potential for Patient Harm | SERIOUS INJURY possible if software fails (missed fall = delayed emergency response) |
| Potential for Death | Not directly causing death, but delayed response may contribute |
| Classification Basis | IEC 62304:2006+AMD1:2015 §4.3 — injury possible but not death or serious injury as direct result |

> **NOTE:** Although Class B is the minimum assigned class, the project team has elected to apply **Class B requirements throughout**, with Class C documentation practices for the fall-detection algorithm (SWI-FD-CORE-001) given its direct safety relevance. Any reclassification requires QA Manager approval and a documented rationale.

### 2.2 Software Items and Their Safety Classes

| Software Item ID | Description | Safety Class | Rationale |
|---|---|---|---|
| SWI-FD-CORE-001 | Fall detection algorithm (on-device) | **Class B** | Missed detection = delayed alert |
| SWI-FW-001 | Device firmware — sensor acquisition, power management | **Class B** | Device non-function affects safety |
| SWI-CLOUD-001 | Alert pipeline — cloud backend services | **Class B** | Alert delivery failure affects safety |
| SWI-APP-001 | Caregiver mobile application (iOS/Android) | **Class B** | Alert display failure affects safety |
| SWI-ADMIN-001 | Device provisioning and configuration tool | **Class A** | Configuration errors not directly safety-critical |
| SWI-DIAG-001 | Manufacturing diagnostic utility | **Class A** | Factory use only; not deployed to field |

---

## 3. Software Development Lifecycle (SDLC) Model

The project follows an **iterative V-model** with phase gates aligned to design control phases defined in SOP-DC-EFD-001.

```
Requirements          <->  Validation (VAL)
   Architecture       <->  Integration Test
      Detailed Design <->  Unit Test
         Implementation
```

### 3.1 Lifecycle Phases

| Phase | IEC 62304 Clause | Key Activities | Exit Criteria |
|---|---|---|---|
| **P1** Software Planning | §5.1 | SDP approved, safety class assigned, SOUP identified | SDP reviewed and signed |
| **P2** Software Requirements | §5.2 | SRS authored, requirements reviewed, traceability started | SRS approved by QA and RA |
| **P3** Software Architecture | §5.3 | SAS authored, architecture reviewed, SOUP integration planned | Architecture review passed |
| **P4** Detailed Design | §5.4 | Software unit design documented | Design review passed |
| **P5** Implementation | §5.5 | Coding per standards, peer review, unit test | Unit test coverage >= 80% (Class B); zero critical static analysis violations |
| **P6** Integration & Testing | §5.6 | Integration test plan executed | All integration tests pass; traceability complete |
| **P7** System Testing | §5.7 | System-level functional and safety tests | All system tests pass; defect log reviewed |
| **P8** Software Release | §5.8 | Release checklist, build verification, CM lock | Release authorized by QA |
| **P9** Maintenance | §6 | Anomaly tracking, SOUP monitoring, change control | Ongoing — anomaly response per §9 |

---

## 4. Software Requirements (Class B — Mandatory Activities)

Per IEC 62304:2006+AMD1:2015 §5.2 for Class B:

- [ ] All software requirements documented in Software Requirements Specification (SRS)
- [ ] Safety requirements explicitly identified and marked
- [ ] SOUP items identified with version and publisher
- [ ] Requirements reviewed for completeness, consistency, and testability
- [ ] Traceability from system requirements to software requirements established

---

## 5. Software Architecture (Class B — Mandatory Activities)

Per IEC 62304 §5.3 for Class B:

- [ ] Software architecture document identifies all software items
- [ ] Each software item assigned a safety class
- [ ] Segregation of safety-critical software items documented
- [ ] SOUP integration architecture specified
- [ ] Architecture reviewed before detailed design begins

---

## 6. Coding Standards

| Language | Standard | Enforcement Tool |
|---|---|---|
| C (firmware) | MISRA C:2012 (mandatory rules) | PC-lint Plus / cppcheck |
| Python (backend) | PEP 8 + Bandit security linter | Ruff + Bandit |
| TypeScript (app) | AirBnB ESLint config | ESLint |

All safety-classified software items (Class B) require:
- Peer code review before merge — minimum one reviewer
- Static analysis with zero **error-level** violations before integration
- All peer review comments resolved or documented with rationale

---

## 7. Software Unit Testing (Class B — Mandatory)

| Metric | Class B Minimum | Project Target |
|---|---|---|
| Statement coverage | Not mandated (Class B) | >= 80% |
| Branch coverage | Not mandated (Class B) | >= 75% |
| Unit test execution | All units | All units |
| Test framework | Documented | pytest / Unity |

> **Class C note:** If any software item is upgraded to Class C, branch coverage >= 85% becomes mandatory per IEC 62304 §5.5.5.

---

## 8. Software Integration Testing (Class B — Mandatory)

Per IEC 62304 §5.6:

- Integration test plan (ITP) documents all interface tests
- Tests execute at subsystem boundaries: device <-> cloud, cloud <-> app
- Integration test report summarizes pass/fail with anomaly log
- All Class B software items verified in integrated context

---

## 9. SOUP (Software of Unknown Provenance) Management

Per IEC 62304 §8.1.2:

| SOUP Item | Version | Publisher | Safety Class | Functional Use | Verification Method |
|---|---|---|---|---|---|
| FreeRTOS | 10.6.x | AWS / FreeRTOS | Class B | RTOS kernel for firmware | Integration test + known anomaly review |
| TensorFlow Lite | 2.15.x | Google | Class B | On-device ML inference | Algorithm performance test (VER-EFD-006) |
| AWS IoT Core SDK | Latest | AWS | Class B | MQTT alert delivery | Integration test (VER-EFD-003) |
| React Native | 0.74.x | Meta | Class A | Caregiver app UI framework | Functional system test |
| FastAPI | 0.111.x | Sebastián Ramírez | Class B | Cloud API gateway | Integration test |

Known anomalies for each SOUP item documented and reviewed at each design review gate.

---

## 10. Configuration Management

Per IEC 62304 §8:

| Item | Tool | Policy |
|---|---|---|
| Source code | Git (GitHub) | Protected `main` branch — PR required; no direct push |
| Release artifacts | GitHub Releases + S3 | Signed releases; SHA-256 checksums stored in DHF |
| Build system | Docker + Makefile | Reproducible builds from CM-controlled source |
| Issue tracking | GitHub Issues | All anomalies logged with IEC 62304 §9 fields |

Baseline identifiers stored in DHF section `12_configuration_management/`.

---

## 11. Problem Resolution (Anomaly Management)

Per IEC 62304 §9:

1. All anomalies logged in GitHub Issues with labels: `severity:critical`, `severity:high`, `severity:medium`, `severity:low`
2. Safety impact assessment performed for every anomaly before disposition
3. Anomalies affecting safety requirements: QA Manager review required before close
4. Anomaly log reviewed at every design review gate
5. Open anomalies at release require documented risk acceptance by QA Manager

---

## 12. Software Release Process

Release checklist (per IEC 62304 §5.8):

- [ ] All planned software items implemented and code-reviewed
- [ ] Unit test suite passing — coverage meets targets
- [ ] Integration tests passing
- [ ] System tests passing
- [ ] Open anomalies: zero Critical; High anomalies risk-accepted by QA Manager
- [ ] SOUP known anomaly review complete
- [ ] Traceability matrix complete and approved
- [ ] Software verification report signed by QA
- [ ] Build reproducible from CM-controlled revision tag
- [ ] Release artifact SHA-256 checksum archived in DHF
- [ ] QA Manager sign-off on release

---

## 13. Roles and Responsibilities

| Role | IEC 62304 Responsibility | Name | Qualification |
|---|---|---|---|
| Software Engineering Lead | Overall SDP compliance; architecture approval | [NAME] | [DEGREE + EXPERIENCE] |
| Firmware Engineer | Class B firmware development and unit test | [NAME] | [DEGREE + EXPERIENCE] |
| Backend Engineer | Cloud software development and integration test | [NAME] | [DEGREE + EXPERIENCE] |
| Mobile Engineer | Caregiver app development and test | [NAME] | [DEGREE + EXPERIENCE] |
| QA Engineer | Test plan review; verification report approval | [NAME] | [DEGREE + EXPERIENCE] |
| Regulatory Affairs | IEC 62304 compliance audit; SDP approval | [NAME] | [DEGREE + EXPERIENCE] |

---

## 14. Maintenance and Monitoring

Post-release, per IEC 62304 §6 and §9:

- SOUP publisher security advisories monitored monthly
- Field anomalies from complaint handling (SOP-CAPA-001) fed back into anomaly log
- Each maintenance release follows the same SDLC (sections 3-12)
- Software version incremented per semantic versioning: MAJOR.MINOR.PATCH

---

## 15. Document Approval

| Role | Name | Signature | Date |
|---|---|---|---|
| Software Engineering Lead | [NAME] | | |
| QA Manager | [NAME] | | |
| Regulatory Affairs | [NAME] | | |

---

## 16. Revision History

| Rev | Date | Author | Description |
|---|---|---|---|
| A | 2026-03-22 | Software Engineering Lead | Initial release — IEC 62304 Class B SDP |

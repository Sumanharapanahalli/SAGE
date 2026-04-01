# DHF Section Register
## ICD-DHF-DHF-003-RevA

**Document Title:** Design History File Section Register
**Document ID:** ICD-DHF-DHF-003-RevA
**Device:** CardioSync CRT-D Model CS-9000
**Manufacturer:** NovaCor Medical Devices Inc.
**Prepared By:** R. Torres (Regulatory Affairs) / M. Chen (Quality Systems)
**Approved By:** S. Johnson (VP Regulatory Affairs)
**Approval Date:** 2024-11-15
**Revision:** Rev A

---

## Section 1: Design Planning

### 1.1 Section Identification
- **Section Number:** DHF-01
- **Section Title:** Design and Development Planning
- **Regulatory Citation:** 21 CFR 820.30(a)
- **FDA PMA Technical Section Cross-Reference:** PMA Section 4 (Manufacturing Information); PMA Section 10 (Summary of Studies — Planning evidence)

### 1.2 Regulatory Requirement
21 CFR 820.30(a) requires each manufacturer to establish and maintain plans that describe or reference the design and development activities and define responsibility for implementation. The plans shall identify and describe the interfaces with different groups or activities that provide, or result in, input to the design and development process. The plans shall be reviewed, updated, and approved as design and development evolves.

### 1.3 Required Documents

| Document ID | Title | Document Type | Status |
|---|---|---|---|
| ICD-DHF-PLN-001-RevA | Design and Development Plan | PLAN | APPROVED |
| ICD-DHF-PLN-002-RevB | Risk Management Plan (ISO 14971:2019) | PLAN | APPROVED |
| ICD-DHF-PLN-003-RevA | Software Development Plan (IEC 62304) | PLAN | APPROVED |
| ICD-DHF-PLN-004-RevA | Usability Engineering Plan (IEC 62366) | PLAN | APPROVED |
| ICD-DHF-PLN-005-RevA | Clinical Evaluation Plan | PLAN | APPROVED |
| ICD-DHF-PLN-006-RevA | Biocompatibility Evaluation Plan (ISO 10993-1) | PLAN | APPROVED |
| ICD-DHF-PLN-007-RevA | Sterilization Validation Plan | PLAN | APPROVED |
| ICD-DHF-PLN-008-RevA | Design Verification and Validation Master Plan | PLAN | APPROVED |
| ICD-DHF-PLN-009-RevA | Team Roles and Responsibilities Matrix | FORM | APPROVED |
| ICD-DHF-PLN-010-RevA | Project Schedule Baseline (MS Project file reference) | LOG | APPROVED |
| ICD-DHF-PLN-011-RevA | Design Interface Control Plan | PLAN | APPROVED |
| ICD-DHF-PLN-012-RevA | Supplier Control Plan for Critical Components | PLAN | APPROVED |

### 1.4 Document Descriptions
- **ICD-DHF-PLN-001-RevA:** Master design and development plan covering all project phases (Feasibility, Design Input, Detailed Design, V&V, Transfer, Launch), phase gates, milestones, resource plan, and design review schedule. Living document updated at each phase gate.
- **ICD-DHF-PLN-002-RevB:** Risk management plan per ISO 14971:2019 defining risk management process, risk acceptability criteria, team, and relationship to design activities. Updated at Rev B to include cybersecurity hazards.
- **ICD-DHF-PLN-003-RevA:** Software development lifecycle plan per IEC 62304 Class C (life-supporting software). Defines development process, change management, problem resolution, and maintenance activities.
- **ICD-DHF-PLN-004-RevA:** Usability engineering plan per IEC 62366-1 defining summative and formative evaluations, known use scenarios, and intended user populations.

### 1.5 Responsible Party
- **Document Owner:** VP Research & Development (A. Patel)
- **Contributing Functions:** R&D Engineering, Quality Assurance, Regulatory Affairs, Clinical, Manufacturing, Software Engineering

### 1.6 Review and Approval Requirements
- All planning documents require approval by VP R&D and QA Director
- Risk Management Plan additionally requires approval by VP Regulatory Affairs
- Plans are reviewed and updated at each phase gate review

### 1.7 Acceptance Criteria
- All plans are reviewed and approved prior to initiation of activities they govern
- Plans are updated when scope, schedule, or technical approach changes
- Risk Management Plan is maintained as a living document throughout device lifecycle
- All plans reference applicable regulatory requirements and standards

---

## Section 2: Design Input

### 2.1 Section Identification
- **Section Number:** DHF-02
- **Section Title:** Design Input
- **Regulatory Citation:** 21 CFR 820.30(c)
- **FDA PMA Technical Section Cross-Reference:** PMA Section 3 (Device Description); PMA Section 5 (Summary of Nonclinical/Preclinical Studies)

### 2.2 Regulatory Requirement
21 CFR 820.30(c) requires that procedures ensure the design requirements relating to a device are appropriate and address the intended use of the device. The requirements shall include applicable statutory and regulatory requirements. Design input requirements shall be reviewed and approved by a designated individual(s). The approval, including the date and signature of the individual(s) approving the requirements, shall be documented.

### 2.3 Required Documents

| Document ID | Title | Document Type | Status |
|---|---|---|---|
| ICD-DHF-DI-001-RevA | Design Input Requirements Specification (DIRS) | SPEC | APPROVED |
| ICD-DHF-DI-002-RevA | Intended Use and Indications for Use Statement | SPEC | APPROVED |
| ICD-DHF-DI-003-RevB | User Needs Analysis and Stakeholder Input Record | RPT | APPROVED |
| ICD-DHF-DI-004-RevA | Regulatory Requirements Analysis — 21 CFR 870, ISO 14708-3 | RPT | APPROVED |
| ICD-DHF-DI-005-RevA | Predicate Device Comparison (CS-8500 vs CS-9000) | RPT | APPROVED |
| ICD-DHF-DI-006-RevA | Design Input Review Record and Approval | LOG | APPROVED |
| ICD-DHF-DI-007-RevA | Customer Requirements Input — KOL Survey Summary | RPT | APPROVED |
| ICD-DHF-DI-008-RevA | Complaint Analysis from CS-8500 (Previous Generation) | RPT | APPROVED |
| ICD-DHF-DI-009-RevA | Labeling Requirements and Standards Analysis | SPEC | APPROVED |

### 2.4 Document Descriptions
- **ICD-DHF-DI-001-RevA:** Master requirements specification containing all quantified design requirements organized by category (Performance, Safety, Reliability, Software, EMC, Biocompatibility). All requirements carry unique REQ-IDs. Includes traceability from user needs to requirements.
- **ICD-DHF-DI-002-RevA:** Formal intended use statement as it will appear in the Instructions for Use, plus indications for use with patient population description and clinical conditions.
- **ICD-DHF-DI-003-RevB:** Documented output of Key Opinion Leader (KOL) advisory board, implanting physician surveys, and patient focus group inputs translated into design requirements.
- **ICD-DHF-DI-005-RevA:** Side-by-side comparison of CS-8500 (predicate) and CS-9000, identifying new features, modified features, and unchanged features as inputs to the risk management and V&V planning activities.

### 2.5 Responsible Party
- **Document Owner:** Principal R&D Engineer (J. Ramírez)
- **Contributing Functions:** R&D Engineering, Clinical Affairs, Regulatory Affairs, Quality Assurance

### 2.6 Review and Approval Requirements
- DIRS (ICD-DHF-DI-001) requires approval by VP R&D, QA Director, and VP Regulatory Affairs
- Intended Use document requires approval by VP Regulatory Affairs
- All design input documents reviewed at Phase Gate 2 (Design Input Complete) review

### 2.7 Acceptance Criteria
- All design input requirements are specific, measurable, achievable, and testable
- Requirements address intended use and all applicable regulatory requirements
- User needs are fully captured and traceable to design requirements
- Conflicting requirements are identified and resolved with documented rationale
- Design input is formally reviewed and signed off prior to initiation of detailed design

---

## Section 3: Design Output

### 3.1 Section Identification
- **Section Number:** DHF-03
- **Section Title:** Design Output
- **Regulatory Citation:** 21 CFR 820.30(d)
- **FDA PMA Technical Section Cross-Reference:** PMA Section 3 (Device Description); PMA Section 7 (Manufacturing Information); PMA Section 9 (Software)

### 3.2 Regulatory Requirement
21 CFR 820.30(d) requires that procedures ensure the total finished design output consists of the device, its packaging and labeling, and the Device Master Record. The total finished design output shall meet design input requirements. Design output shall be documented, reviewed, and approved before release.

### 3.3 Required Documents

| Document ID | Title | Document Type | Status |
|---|---|---|---|
| ICD-DHF-DO-001-RevA | Design Output Index and Device Master Record Index | LOG | APPROVED |
| ICD-DHF-DO-002-RevB | Device Description Document — System and Subsystem Architecture | SPEC | APPROVED |
| ICD-DHF-DO-003-RevA | Top-Level Assembly Drawing CS9000-ASSY-001 | DRAW | APPROVED |
| ICD-DHF-DO-004-RevA | Hybrid Circuit Assembly Drawing CS9000-HCA-001 | DRAW | APPROVED |
| ICD-DHF-DO-005-RevA | Device Header Assembly Drawing CS9000-HDR-001 | DRAW | APPROVED |
| ICD-DHF-DO-006-RevA | Lead Connector Drawing CS9000-CONN-001 | DRAW | APPROVED |
| ICD-DHF-DO-007-RevB | Bill of Materials — CS-9000 Top Assembly (Levels 0–3) | BOM | APPROVED |
| ICD-DHF-DO-008-RevA | Software Architecture Document (SAD) | SPEC | APPROVED |
| ICD-DHF-DO-009-RevA | Software Requirements Specification (SRS) | SPEC | APPROVED |
| ICD-DHF-DO-010-RevA | Software Detailed Design Document (SDD) | SPEC | APPROVED |
| ICD-DHF-DO-011-RevA | Firmware Source Code Baseline — Tag CS9000-FW-v3.1.0 | LOG | APPROVED |
| ICD-DHF-DO-012-RevA | Manufacturing Process Specification — Final Assembly | SOP | APPROVED |
| ICD-DHF-DO-013-RevA | Manufacturing Process Specification — Hybrid Circuit Assembly | SOP | APPROVED |
| ICD-DHF-DO-014-RevA | Manufacturing Process Specification — Header Molding and Assembly | SOP | APPROVED |
| ICD-DHF-DO-015-RevA | Acceptance Test Criteria (Device Acceptance Testing) | SPEC | APPROVED |
| ICD-DHF-DO-016-RevA | Labeling Master — Instructions for Use and Device Label | SPEC | APPROVED |
| ICD-DHF-DO-017-RevA | Packaging Specification | SPEC | APPROVED |
| ICD-DHF-DO-018-RevA | Sterilization Specification (EO Sterilization) | SPEC | APPROVED |

### 3.4 Document Descriptions
- **ICD-DHF-DO-002-RevB:** Comprehensive device description covering overall system architecture, hardware subsystems (high-voltage output, LV and RV pacing, biventricular sensing, battery management, telemetry/programming interface, device header), software architecture overview, and intended use in the clinical context.
- **ICD-DHF-DO-007-RevB:** Full BOM from Level 0 (finished device) through Level 3 (purchased components and raw materials), with part numbers, revision levels, supplier IDs, and critical component designations.
- **ICD-DHF-DO-008-RevA:** System-level software architecture defining software item decomposition, SOUP (Software Of Unknown Provenance) list, hardware/software interfaces, and hazard-related software requirements per IEC 62304.

### 3.5 Responsible Party
- **Document Owner:** Principal R&D Engineer (J. Ramírez) for hardware; Software Engineering Lead (P. Williams) for software
- **Contributing Functions:** R&D Engineering, Software Engineering, Manufacturing Engineering, Regulatory Affairs, Quality Assurance

### 3.6 Review and Approval Requirements
- Engineering drawings require approval per SOP-RD-0010 (Engineering Drawing Release)
- Device Description Document requires VP R&D, QA Director, and VP RA approval
- All design output reviewed at Phase Gate 3 (Design Freeze) review prior to V&V initiation
- BOM updates require ECO process per SOP-QMS-0030

### 3.7 Acceptance Criteria
- Design output addresses each design input requirement (traceability confirmed in RTM)
- All drawings meet NovaCor drafting standard NDS-001
- BOM is complete and accurate; all components have approved supplier qualifications
- Software architecture documents are complete prior to initiation of software V&V
- Labeling complies with 21 CFR 801 and device-specific labeling requirements

---

## Section 4: Design Review

### 4.1 Section Identification
- **Section Number:** DHF-04
- **Section Title:** Design Review
- **Regulatory Citation:** 21 CFR 820.30(e)
- **FDA PMA Technical Section Cross-Reference:** PMA Section 4 (Manufacturing Information — quality system evidence)

### 4.2 Regulatory Requirement
21 CFR 820.30(e) requires that formal documented reviews of the design results be planned and conducted at appropriate stages of the device's design development. The procedures shall ensure that participants at each design review include representatives of all functions concerned with the design stage being reviewed, as well as an individual who does not have direct responsibility for the design stage being reviewed. The results of a design review, including identification of the design, the date, and the individual(s) performing the review, shall be documented in the DHF.

### 4.3 Required Documents

| Document ID | Title | Document Type | Status |
|---|---|---|---|
| ICD-DHF-DR-001-RevA | Phase Gate 1 Review Record — Feasibility Complete | LOG | APPROVED |
| ICD-DHF-DR-002-RevA | Phase Gate 2 Review Record — Design Input Complete | LOG | APPROVED |
| ICD-DHF-DR-003-RevA | Phase Gate 3 Review Record — Design Output / Design Freeze | LOG | APPROVED |
| ICD-DHF-DR-004-RevA | Phase Gate 4 Review Record — Verification Complete | LOG | APPROVED |
| ICD-DHF-DR-005-RevA | Phase Gate 5 Review Record — Validation Complete | LOG | APPROVED |
| ICD-DHF-DR-006-RevA | Phase Gate 6 Review Record — Transfer and Pre-Launch | LOG | APPROVED |
| ICD-DHF-DR-007-RevA | Interim Design Review — HV Output Circuit (DR-IR-001) | LOG | APPROVED |
| ICD-DHF-DR-008-RevA | Interim Design Review — Sensing Algorithm (DR-IR-002) | LOG | APPROVED |
| ICD-DHF-DR-009-RevA | Interim Design Review — Software Architecture (DR-IR-003) | LOG | APPROVED |
| ICD-DHF-DR-010-RevA | Interim Design Review — Battery / Power Management (DR-IR-004) | LOG | APPROVED |
| ICD-DHF-DR-011-RevA | Design Review Action Item Log (All Reviews) | LOG | APPROVED |
| ICD-DHF-DR-012-RevA | Independent Reviewer Qualification Records | FORM | APPROVED |
| ICD-DHF-DR-013-RevA | Design Review Attendance Records | FORM | APPROVED |
| ICD-DHF-DR-014-RevA | Final Design Review Summary and Disposition | RPT | APPROVED |

### 4.4 Responsible Party
- **Design Review Chair:** QA Director (M. Chen) for phase gate reviews; R&D Lead for interim reviews
- **Independent Reviewers:** Identified in ICD-DHF-DR-012-RevA
- **Contributing Functions:** All design functions; independent reviewer per 820.30(e)

### 4.5 Review and Approval Requirements
- Phase gate review records signed by all participants including independent reviewer
- Open action items from each review tracked to closure before proceeding to next phase
- Final Design Review disposition documented with go/no-go decision and rationale

### 4.6 Acceptance Criteria
- Each phase gate review includes representative from each design function
- An individual without direct design responsibility participates as independent reviewer
- All review records document design identity, date, participants, findings, and action items
- No phase gate is passed with unresolved safety- or compliance-related action items

---

## Section 5: Design Verification

### 5.1 Section Identification
- **Section Number:** DHF-05
- **Section Title:** Design Verification
- **Regulatory Citation:** 21 CFR 820.30(f)
- **FDA PMA Technical Section Cross-Reference:** PMA Section 5 (Summary of Nonclinical/Preclinical Studies)

### 5.2 Regulatory Requirement
21 CFR 820.30(f) requires that each manufacturer shall establish and maintain procedures for verifying the device design. Design verification shall confirm that the design output meets the design input requirements. The results of the design verification, including identification of the design, method(s), the date, and the individual(s) performing the verification, shall be documented in the DHF.

### 5.3 Required Documents

| Document ID | Title | Document Type | Status |
|---|---|---|---|
| ICD-DHF-DV-001-RevA | Design Verification Plan | PLAN | APPROVED |
| ICD-DHF-DV-002-RevA | Verification Requirements Traceability Matrix | LOG | APPROVED |
| ICD-DHF-DV-003-RevA | Test Protocol: Electrical Performance — Pacing Output | PROTO | APPROVED |
| ICD-DHF-DV-003-RPT-RevA | Test Report: Electrical Performance — Pacing Output | RPT | APPROVED |
| ICD-DHF-DV-004-RevA | Test Protocol: Electrical Performance — Sensing | PROTO | APPROVED |
| ICD-DHF-DV-004-RPT-RevA | Test Report: Electrical Performance — Sensing | RPT | APPROVED |
| ICD-DHF-DV-005-RevA | Test Protocol: Defibrillation Efficacy (HV Shock Output) | PROTO | APPROVED |
| ICD-DHF-DV-005-RPT-RevA | Test Report: Defibrillation Efficacy (HV Shock Output) | RPT | APPROVED |
| ICD-DHF-DV-006-RevA | Test Protocol: Mechanical Integrity (Vibration, Shock, Drop) | PROTO | APPROVED |
| ICD-DHF-DV-006-RPT-RevA | Test Report: Mechanical Integrity | RPT | APPROVED |
| ICD-DHF-DV-007-RevA | Test Protocol: Hermetic Seal Integrity (Helium Leak) | PROTO | APPROVED |
| ICD-DHF-DV-007-RPT-RevA | Test Report: Hermetic Seal Integrity | RPT | APPROVED |
| ICD-DHF-DV-008-RevA | Test Protocol: Header Connector Force/Torque | PROTO | APPROVED |
| ICD-DHF-DV-008-RPT-RevA | Test Report: Header Connector Force/Torque | RPT | APPROVED |
| ICD-DHF-DV-009-RevA | Test Protocol: Battery Longevity Modeling and Accelerated Life | PROTO | APPROVED |
| ICD-DHF-DV-009-RPT-RevA | Test Report: Battery Longevity | RPT | APPROVED |
| ICD-DHF-DV-010-RevA | Test Protocol: Telemetry Performance | PROTO | APPROVED |
| ICD-DHF-DV-010-RPT-RevA | Test Report: Telemetry Performance | RPT | APPROVED |
| ICD-DHF-DV-011-RevA | Test Protocol: EMC Testing per IEC 60601-1-2 | PROTO | APPROVED |
| ICD-DHF-DV-011-RPT-RevA | Test Report: EMC Testing | RPT | APPROVED |
| ICD-DHF-DV-012-RevA | Test Protocol: Electrical Safety per IEC 60601-1 | PROTO | APPROVED |
| ICD-DHF-DV-012-RPT-RevA | Test Report: Electrical Safety | RPT | APPROVED |
| ICD-DHF-DV-013-RevA | Software Testing Summary — Unit, Integration, System | RPT | APPROVED |
| ICD-DHF-DV-014-RevA | Software Anomaly Report Log | LOG | APPROVED |
| ICD-DHF-DV-015-RevA | Accelerated Aging / Reliability Testing Report | RPT | APPROVED |
| ICD-DHF-DV-016-RevA | Biocompatibility Testing Summary (ISO 10993 series) | RPT | APPROVED |
| ICD-DHF-DV-020-RevA | Design Verification Summary Report | RPT | APPROVED |

### 5.4 Responsible Party
- **Document Owner:** Verification Test Engineer (L. Garcia) / Software QA Engineer (T. Nguyen)
- **Test Laboratory:** NovaCor internal test labs (ISO 17025 accredited) plus external labs (Intertek, Element)
- **Contributing Functions:** R&D Engineering, Software Engineering, Quality Assurance, Regulatory Affairs

### 5.5 Review and Approval Requirements
- Each test protocol approved by Test Engineer, QA Engineer, and R&D Lead before test execution
- Test reports approved by Test Engineer and QA Engineer; deviations reviewed by QA Director
- Verification Summary Report approved by VP R&D and QA Director
- All verification testing performed on design-frozen devices (post Design Freeze gate)

### 5.6 Acceptance Criteria
- All design input requirements (REQ-IDs in DI-001) verified by at least one verification method
- No open critical or major non-conformances at verification completion
- All verification test reports show pass status against defined pass/fail criteria
- Verification traceability matrix is complete with no unverified requirements (except those deferred to validation with documented rationale)

---

## Section 6: Design Validation

### 6.1 Section Identification
- **Section Number:** DHF-06
- **Section Title:** Design Validation
- **Regulatory Citation:** 21 CFR 820.30(g)
- **FDA PMA Technical Section Cross-Reference:** PMA Section 5 (Nonclinical Studies); PMA Section 6 (Clinical Studies)

### 6.2 Regulatory Requirement
21 CFR 820.30(g) requires that each manufacturer shall establish and maintain procedures for validating the device design. Design validation shall be performed under defined operating conditions on initial production units, lots, or their equivalents. Design validation shall ensure that devices conform to defined user needs and intended uses and shall include testing of production units under actual or simulated use conditions. Design validation shall include software validation and risk analysis, where appropriate.

### 6.3 Required Documents

| Document ID | Title | Document Type | Status |
|---|---|---|---|
| ICD-DHF-DVL-001-RevA | Design Validation Plan | PLAN | APPROVED |
| ICD-DHF-DVL-002-RevA | Simulated Use Test Protocol — Implant and Programming | PROTO | APPROVED |
| ICD-DHF-DVL-002-RPT-RevA | Simulated Use Test Report — Implant and Programming | RPT | APPROVED |
| ICD-DHF-DVL-003-RevA | Simulated Use Test Protocol — Emergency Shock Delivery | PROTO | APPROVED |
| ICD-DHF-DVL-003-RPT-RevA | Simulated Use Test Report — Emergency Shock Delivery | RPT | APPROVED |
| ICD-DHF-DVL-010-RevA | Animal Study Protocol — Acute Canine Defibrillation Threshold | PROTO | APPROVED |
| ICD-DHF-DVL-010-RPT-RevA | Animal Study Report — Acute Canine DFT | RPT | APPROVED |
| ICD-DHF-DVL-011-RevA | Animal Study Protocol — Chronic Ovine 90-day Implant | PROTO | APPROVED |
| ICD-DHF-DVL-011-RPT-RevA | Animal Study Report — Chronic Ovine 90-day Implant | RPT | APPROVED |
| ICD-DHF-DVL-012-RevA | Animal Study Protocol — Pacing Efficacy (Canine, CRT) | PROTO | APPROVED |
| ICD-DHF-DVL-012-RPT-RevA | Animal Study Report — Pacing Efficacy CRT | RPT | APPROVED |
| ICD-DHF-DVL-020-RevA | Clinical Study Reference: CARDIAC-SYNC Pivotal Trial IDE G240001 | RPT | APPROVED |
| ICD-DHF-DVL-021-RevA | Clinical Evaluation Report (per EU MDR guidance, referenced for FDA) | RPT | APPROVED |
| ICD-DHF-DVL-025-RevA | Usability/Human Factors Validation Report (IEC 62366) | RPT | APPROVED |
| ICD-DHF-DVL-026-RevA | Software Validation Plan and Report (IEC 62304 Class C) | RPT | APPROVED |
| ICD-DHF-DVL-027-RevA | Cybersecurity Validation Report | RPT | APPROVED |
| ICD-DHF-DVL-030-RevA | Risk Management Report (ISO 14971) — Residual Risk Acceptability | RPT | APPROVED |
| ICD-DHF-DVL-031-RevA | Benefit-Risk Determination | RPT | APPROVED |
| ICD-DHF-DVL-035-RevA | Design Validation Summary Report | RPT | APPROVED |

### 6.4 Responsible Party
- **Document Owner:** Clinical Affairs Director (C. Huang); R&D Lead (A. Patel) for preclinical
- **Contributing Functions:** Clinical Affairs, R&D Engineering, Software Engineering, Regulatory Affairs, Quality Assurance, Biostatistics

### 6.5 Review and Approval Requirements
- All validation protocols approved before study initiation
- Animal study protocols reviewed by IACUC and approved before conduct
- Clinical study IDE approved by FDA (G240001) before study initiation
- Validation Summary Report approved by VP R&D, VP Clinical, QA Director, and VP RA

### 6.6 Acceptance Criteria
- Simulated use testing confirms device can be implanted and programmed as intended without critical use errors
- Animal studies demonstrate defibrillation and CRT pacing efficacy and safety
- Clinical study (CARDIAC-SYNC) meets pre-specified endpoints: ≥50% responder rate (primary), all-cause mortality hazard ratio, safety endpoint (major complications rate ≤15%)
- Human factors validation confirms no unacceptable use errors for critical tasks
- Software validation confirms all safety-critical software functions perform as specified
- Risk Management Report confirms overall residual risk is acceptable

---

## Section 7: Design Transfer

### 7.1 Section Identification
- **Section Number:** DHF-07
- **Section Title:** Design Transfer
- **Regulatory Citation:** 21 CFR 820.30(h)
- **FDA PMA Technical Section Cross-Reference:** PMA Section 4 (Manufacturing Information)

### 7.2 Regulatory Requirement
21 CFR 820.30(h) requires that each manufacturer shall establish and maintain procedures to ensure that the device design is correctly translated into production specifications. These specifications shall address all aspects of device production.

### 7.3 Required Documents

| Document ID | Title | Document Type | Status |
|---|---|---|---|
| ICD-DHF-DT-001-RevA | Design Transfer Plan | PLAN | APPROVED |
| ICD-DHF-DT-002-RevA | Device Master Record (DMR) Completeness Checklist | FORM | APPROVED |
| ICD-DHF-DT-003-RevA | Manufacturing Process Validation Summary | RPT | APPROVED |
| ICD-DHF-DT-004-RevA | Process FMEA (pFMEA) Summary | RPT | APPROVED |
| ICD-DHF-DT-005-RevA | First Article Inspection Records | LOG | APPROVED |
| ICD-DHF-DT-006-RevA | Transfer Review Meeting Record | LOG | APPROVED |
| ICD-DHF-DT-007-RevA | Production Readiness Assessment | RPT | APPROVED |
| ICD-DHF-DT-008-RevA | Post-Transfer Audit Report (Manufacturing Readiness) | RPT | APPROVED |

### 7.4 Responsible Party
- **Document Owner:** VP Manufacturing (D. Kim)
- **Contributing Functions:** Manufacturing Engineering, Quality Assurance, R&D Engineering, Supply Chain

### 7.5 Review and Approval Requirements
- Design Transfer Plan approved by VP Manufacturing, VP R&D, and QA Director
- DMR Completeness Checklist verified by QA Director
- Production Readiness Assessment approved by VP Manufacturing and QA Director before first production lot

### 7.6 Acceptance Criteria
- All design output documents (drawings, BOMs, specifications) released to manufacturing
- DMR is complete and all referenced documents are approved and released
- Process validation demonstrates manufacturing processes produce devices within specification
- First Article Inspection confirms production devices match design output specifications
- No unresolved manufacturing non-conformances at transfer completion

---

## Section 8: Design Changes

### 8.1 Section Identification
- **Section Number:** DHF-08
- **Section Title:** Design Changes
- **Regulatory Citation:** 21 CFR 820.30(i)
- **FDA PMA Technical Section Cross-Reference:** PMA Supplement process if applicable

### 8.2 Regulatory Requirement
21 CFR 820.30(i) requires that each manufacturer shall establish and maintain procedures for the identification, documentation, validation or where appropriate verification, review, and approval of design changes before their implementation.

### 8.3 Required Documents

| Document ID | Title | Document Type | Status |
|---|---|---|---|
| ICD-DHF-DC-001-RevA | ECO-2023-0047: Header Connector Geometry Change — Impact Assessment | LOG | APPROVED |
| ICD-DHF-DC-002-RevA | ECO-2024-0012: Firmware Update — Sensing Algorithm Rev 3.1 | LOG | APPROVED |
| ICD-DHF-DC-003-RevA | ECO-2024-0031: Battery Anode Material Specification Update | LOG | APPROVED |
| ICD-DHF-DC-004-RevA | Design Change Procedure (SOP-RD-0015) Reference | SOP | APPROVED |
| ICD-DHF-DC-005-RevA | Design Change Log Summary (All ECOs through PMA submission) | LOG | APPROVED |
| ICD-DHF-DC-006-RevA | PMA Supplement Assessment — Determination Checklist | FORM | APPROVED |

### 8.4 Responsible Party
- **Document Owner:** QA Director (M. Chen)
- **Contributing Functions:** R&D Engineering, Regulatory Affairs, Manufacturing, Quality Assurance

### 8.5 Review and Approval Requirements
- All design changes documented via Engineering Change Order (ECO) form
- Each ECO includes impact assessment covering: safety, regulatory (PMA supplement trigger assessment), re-verification/re-validation need, labeling
- Design changes approved by VP R&D, QA Director, and VP RA for changes affecting safety or regulatory compliance

### 8.6 Acceptance Criteria
- All design changes are documented and approved before implementation
- Impact assessments confirm whether re-verification or re-validation is required and this is completed
- PMA supplement trigger assessment completed for each change; supplements filed where required per 21 CFR 814.39
- No unapproved design changes implemented in the production device

---

## Section 9: DHF Compilation

### 9.1 Section Identification
- **Section Number:** DHF-09
- **Section Title:** DHF Index and Compilation
- **Regulatory Citation:** 21 CFR 820.30(j)
- **FDA PMA Technical Section Cross-Reference:** All PMA Sections (DHF is foundation for PMA)

### 9.2 Regulatory Requirement
21 CFR 820.30(j) requires each manufacturer to establish and maintain a DHF for each type of device. The DHF shall contain or reference the records necessary to demonstrate that the design was developed in accordance with the approved design plan and the requirements of 21 CFR 820.30.

### 9.3 Required Documents

| Document ID | Title | Document Type | Status |
|---|---|---|---|
| ICD-DHF-DHF-001-RevA | Document Numbering Scheme | SPEC | APPROVED |
| ICD-DHF-DHF-002-RevA | DHF Compilation Checklist and Completeness Verification | FORM | APPROVED |
| ICD-DHF-DHF-003-RevA | DHF Section Register (this document) | LOG | APPROVED |
| ICD-DHF-DHF-004-RevA | PMA Cross-Reference Map | LOG | APPROVED |
| ICD-DHF-DHF-005-RevA | Requirements Traceability Matrix (RTM) — Full | LOG | APPROVED |

### 9.4 Responsible Party
- **Document Owner:** VP Regulatory Affairs (S. Johnson)
- **Contributing Functions:** Regulatory Affairs, Quality Assurance, R&D Engineering

### 9.5 Review and Approval Requirements
- DHF Compilation Checklist reviewed by QA Director to confirm completeness
- Final DHF approved by QA Director and VP RA before PMA submission
- All cross-references verified for internal consistency

### 9.6 Acceptance Criteria
- DHF contains or references all records required by 21 CFR 820.30 subsections (a) through (i)
- All referenced documents are approved and available in NDCS
- Cross-reference map confirms all PMA technical sections are supported by DHF evidence
- Requirements traceability matrix is complete and reviewed

---

*End of Document ICD-DHF-DHF-003-RevA*

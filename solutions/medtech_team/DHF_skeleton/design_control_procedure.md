# Design Control Procedure
## Elder Fall Detection System

**Document Number:** SOP-DC-EFD-001
**Revision:** A
**Status:** APPROVED
**Effective Date:** 2026-03-22
**Owner:** Quality Assurance
**Approved By:** regulatory_specialist

---

## 1. Purpose

This procedure defines the design control process for the Elder Fall Detection System in compliance with:
- **FDA 21 CFR Part 820.30** — Design Controls
- **ISO 13485:2016 Section 7.3** — Design and Development
- **IEC 62304:2006+A1:2015** — Medical Device Software Lifecycle Processes

## 2. Scope

Applies to all design and development activities for the Elder Fall Detection System, including hardware, firmware, software, and system integration.

## 3. Definitions

| Term | Definition |
|---|---|
| Design Input | Physical and performance requirements derived from user needs and regulatory requirements |
| Design Output | Results of each design phase — drawings, specifications, source code, test procedures |
| Design Review | Formal, documented review of design results against design input requirements |
| Design Verification | Objective evidence that design outputs meet design input requirements |
| Design Validation | Objective evidence that the device meets user needs and intended uses |
| Design Transfer | Process of translating final design to production specifications |
| DHF | Design History File — collection of records describing the design history |
| DMR | Device Master Record — compilation of records for finished device manufacture |
| HITL | Human-in-the-Loop — mandatory human review and approval gate |

## 4. Design and Development Phases

### 4.1 Phase 0 — Design Planning

**Activities:**
- Define project scope, objectives, and schedule
- Identify and assign qualified team members
- Establish design control procedures and tools
- Identify applicable regulations and standards
- Define design review schedule and participants

**Deliverables:** Design and Development Plan (DDP-EFD-001)

**Entry Criteria:** Project charter approved by management
**Exit Criteria:** Design plan reviewed and approved by QA and Project Manager

### 4.2 Phase 1 — Design Input

**Activities:**
- Capture and document user needs from intended users and use environment
- Translate user needs into measurable design input requirements
- Identify regulatory requirements (performance, safety, labeling)
- Conduct initial risk analysis to inform requirements
- Review and approve Design Input Requirements Specification

**Deliverables:**
- User Needs Specification (DI-EFD-001)
- Design Input Requirements Specification (DI-EFD-002)
- Regulatory Requirements Summary (DI-EFD-003)

**Entry Criteria:** Design plan approved
**Exit Criteria:** Preliminary Design Review (PDR) completed and all action items resolved

**HITL Gate:** regulatory_specialist must approve Design Input Requirements before Phase 2 begins.

### 4.3 Phase 2 — Design Output

**Activities:**
- Develop system architecture and allocate requirements to subsystems
- Produce hardware design (schematics, PCB, mechanical drawings)
- Develop software architecture and detailed design
- Write firmware and embedded software per IEC 62304
- Generate labeling and Instructions for Use (IFU)
- Maintain and update risk management file

**Deliverables:**
- System Architecture Specification (DO-EFD-001)
- Hardware Design Specification (DO-EFD-002)
- Software Architecture Document (DO-EFD-003)
- Software Requirements Specification (DO-EFD-004)
- Detailed Software Design (DO-EFD-005)
- Firmware Release (DO-EFD-008)

**Entry Criteria:** Design Inputs approved
**Exit Criteria:** Critical Design Review (CDR) completed

### 4.4 Phase 3 — Design Review

**Review Types:**

| Review | Timing | Participants | Purpose |
|---|---|---|---|
| Preliminary Design Review (PDR) | End of Phase 1 | All engineering leads + QA + Regulatory | Validate design inputs, confirm feasibility |
| Critical Design Review (CDR) | Mid Phase 2 | All engineering leads + QA + Regulatory + Clinical | Confirm design outputs are complete and meet inputs |
| Final Design Review (FDR) | Pre-transfer | Full team + Manufacturing | Confirm readiness for design transfer |

**Review Record Requirements:**
- Meeting agenda distributed 5 business days before review
- Attendance list with signatures
- Presentation materials archived in DHF
- Action item log with owners and due dates
- Formal sign-off by all required reviewers

**HITL Gate:** No phase may progress until all prior review action items are formally closed by QA.

### 4.5 Phase 4 — Design Verification

**Activities:**
- Develop and approve Design Verification Plan (VER-EFD-001)
- Execute unit tests per IEC 62304 software unit testing requirements
- Execute integration tests — hardware-software integration
- Conduct hardware bench testing against electrical/mechanical specifications
- Perform EMC and electrical safety testing to applicable standards
- Evaluate fall detection algorithm performance against specification
- Document all test results with pass/fail determination

**Objective:** Demonstrate design outputs meet design inputs (does the device work as designed?)

**Deliverables:** Design Verification Summary Report (VER-EFD-007)

**Entry Criteria:** CDR completed, Design Verification Plan approved
**Exit Criteria:** All verification tests pass; open anomalies dispositioned and risk-assessed

### 4.6 Phase 5 — Design Validation

**Activities:**
- Develop and approve Design Validation Plan (VAL-EFD-001)
- Conduct usability / human factors studies with representative users
- Perform simulated use testing in representative use environment
- Validate software per 21 CFR Part 820.70(i) requirements
- Conduct environmental and stress testing
- Document all validation results

**Objective:** Demonstrate device meets user needs and intended uses under actual or simulated use conditions (does the device work for the user?)

**Deliverables:** Design Validation Summary Report (VAL-EFD-006)

**Entry Criteria:** Verification complete, Validation Plan approved
**Exit Criteria:** All validation tests pass; clinical reviewer approves validation summary

**HITL Gate:** clinical_specialist and regulatory_specialist must both approve Design Validation Summary before design transfer.

### 4.7 Phase 6 — Design Transfer

**Activities:**
- Develop Design Transfer Plan (DT-EFD-001)
- Create manufacturing process specifications and work instructions
- Compile Device Master Record (DMR)
- Train manufacturing staff on production processes
- Conduct Production Readiness Review
- Verify manufactured units meet specifications

**Entry Criteria:** Validation complete and approved; Final Design Review passed
**Exit Criteria:** Production Readiness Review approved; DMR complete and released

---

## 5. Traceability Requirements

Bidirectional traceability must be maintained from user needs through validation:

```
User Need → Design Input → Design Output → Verification Test → Validation Test
```

The Traceability Matrix (TM-EFD-001) must be updated at each phase gate and reviewed at every design review. No design input may be unverified at phase exit.

---

## 6. Document Control Integration

All DHF documents are controlled per Document Control SOP (SOP-DC-001). Requirements:
- All documents in DRAFT status before review
- Review and approval workflow per Section 3 of SOP-DC-001
- No document proceeds to production without APPROVED status
- Superseded revisions retained in DHF archive, never deleted

---

## 7. Revision History

| Rev | Date | Author | Description |
|---|---|---|---|
| A | 2026-03-22 | QA | Initial release |

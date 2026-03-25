# Design and Development Plan

**Clause:** FDA 21 CFR 820.30(b)
**Document ID:** DHF-PLAN-001
**Revision:** A
**Status:** DRAFT

---

## 1. Scope

This plan governs the design and development of [PRODUCT NAME], a [CLASS IIa/IIb] medical device software system classified as **IEC 62304 Class C**.

## 2. Design Team and Responsibilities

| Role | Name | Responsibilities |
|---|---|---|
| Project Lead | [NAME] | Overall technical direction, phase gate approval |
| Software Architect | [NAME] | Architecture baseline, IEC 62304 compliance |
| Embedded Engineer | [NAME] | Firmware development and unit tests |
| Verification Engineer | [NAME] | V&V planning and execution |
| Quality Assurance | [NAME] | DHF completeness, audit readiness |
| Regulatory Affairs | [NAME] | Submission strategy, labeling review |
| Clinical / UX | [NAME] | Usability engineering (IEC 62366) |

## 3. Design Phases

| Phase | Description | Deliverables | Entry Criteria | Exit Criteria |
|---|---|---|---|---|
| **P1** Planning | Requirements baseline, risk plan, SDLC plan | SRS draft, Risk Plan, SDLC | Project charter approved | SRS baselined, team assigned |
| **P2** Architecture | Software architecture, SOUP inventory | SAS, SOUP list | SRS approved | Architecture review passed |
| **P3** Detailed Design | Module design, interface specs | SDS, ICD | SAS approved | Design review passed |
| **P4** Implementation | Coding, code review, unit test | Source code, unit test report | SDS approved | Code coverage >= 85% (Class C) |
| **P5** Verification | Integration test, system test, SOUP verification | Test reports, traceability update | P4 exit | All P1 requirements verified |
| **P6** Validation | Clinical/simulated-use validation, usability | Validation report | V&V plan approved | All acceptance criteria met |
| **P7** Transfer | Build instructions, installation qualification | Transfer record, IQ/OQ | Validation passed | Manufacturing sign-off |
| **P8** Release | Regulatory submission, labeling | 510(k) / CE dossier | Transfer complete | RA sign-off |

## 4. Review Gates

Every phase gate requires formal design review per 820.30(e):
- Minutes recorded with attendees, issues raised, and disposition
- Open action items tracked to closure before phase exit
- QA and RA sign-off required at P5, P6, P8 gates

## 5. Dependencies and Assumptions

- Hardware design is provided by [HARDWARE TEAM] and is under separate DHF
- SOUP (Software of Unknown Provenance) inventory maintained in `02_design_inputs/soup_inventory.md`
- Risk management follows ISO 14971 process documented in `09_risk_management/`

## 6. Approval

| Role | Name | Signature | Date |
|---|---|---|---|
| Project Lead | | | |
| QA Manager | | | |

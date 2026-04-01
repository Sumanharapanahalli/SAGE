# Document Numbering Scheme
## ICD-DHF-DHF-001-RevA

**Document Title:** Design History File Document Numbering Scheme
**Document ID:** ICD-DHF-DHF-001-RevA
**Device:** CardioSync CRT-D Model CS-9000
**Manufacturer:** NovaCor Medical Devices Inc.
**Prepared By:** R. Torres (Regulatory Affairs)
**Reviewed By:** M. Chen (Quality Systems)
**Approved By:** S. Johnson (VP Regulatory Affairs)
**Approval Date:** 2022-03-01
**Revision:** Rev A

---

## 1. Purpose

This document defines the document numbering and identification system for all documents comprising the Design History File (DHF) for the CardioSync CRT-D Model CS-9000. Consistent document identification is required by 21 CFR 820.40 (Document Controls) and 21 CFR 820.30(j) (DHF) to ensure all DHF records are uniquely identifiable, traceable, and retrievable.

---

## 2. Document Identifier Format

All DHF documents use the following standardized format:

```
ICD-DHF-[SECTION_CODE]-[SEQUENCE]-Rev[VERSION]
```

### 2.1 Field Definitions

| Field | Description | Rules |
|---|---|---|
| **ICD** | Device family prefix (Implantable Cardiac Device) | Fixed prefix for all CS-9000 DHF documents |
| **DHF** | File type prefix (Design History File) | Fixed for all DHF documents; distinguishes from DMR, CAPA, etc. |
| **[SECTION_CODE]** | 2–3 character code identifying the DHF section | See Section 3 below |
| **[SEQUENCE]** | 3-digit zero-padded sequential number | 001, 002, 003 … 999; unique within each section code |
| **Rev[VERSION]** | Single uppercase letter indicating document revision | Rev A = initial release; increments through alphabet |

### 2.2 Format Examples

- `ICD-DHF-PLN-001-RevA` — First document in Planning section, initial release
- `ICD-DHF-DI-003-RevB` — Third document in Design Input, first revision
- `ICD-DHF-DV-012-RevC` — Twelfth Verification document, second revision

---

## 3. Section Codes

| Section Code | DHF Section | 21 CFR 820.30 Subsection | Full Section Title |
|---|---|---|---|
| **PLN** | Design Planning | 820.30(a) | Design and Development Planning |
| **DI** | Design Input | 820.30(c) | Design Input |
| **DO** | Design Output | 820.30(d) | Design Output |
| **DR** | Design Review | 820.30(e) | Design Review |
| **DV** | Design Verification | 820.30(f) | Design Verification |
| **DVL** | Design Validation | 820.30(g) | Design Validation |
| **DT** | Design Transfer | 820.30(h) | Design Transfer |
| **DC** | Design Changes | 820.30(i) | Design Changes |
| **DHF** | DHF Compilation | 820.30(j) | DHF Index and Compilation Documents |
| **SUP** | Supporting Documents | — | Supporting and Reference Documents |

---

## 4. Document Type Suffixes

In addition to the standard numbering format, all DHF documents carry a document type descriptor in their title for classification. The following standard document type suffixes are used in document titles and filing:

| Suffix | Document Type | Description |
|---|---|---|
| **PLAN** | Plan | Project plans, test plans, validation plans, risk management plans |
| **SPEC** | Specification | Requirements specifications, design specifications, performance specs |
| **RPT** | Report | Test reports, study reports, audit reports, summary reports |
| **PROTO** | Protocol | Test protocols, study protocols, validation protocols |
| **LOG** | Log | Review logs, action item logs, deviation logs, test logs |
| **SOP** | Standard Operating Procedure | Procedures referenced in or generated as design output |
| **FORM** | Form/Template | Blank forms, checklists, templates used in the design process |
| **DRAW** | Drawing | Engineering drawings, schematics, assembly drawings |
| **BOM** | Bill of Materials | Material lists at any level of the device BOM structure |
| **TEST** | Test Record | Completed test records, raw data files, instrument calibration records |

---

## 5. Version Control Rules

### 5.1 Revision Levels

| Revision | Meaning | Change Type |
|---|---|---|
| **Rev A** | Initial release | Document issued for first time after approval |
| **Rev B** | First revision | First substantive change to an approved document |
| **Rev C** | Second revision | Second substantive change |
| **Rev D** | Third revision | Third substantive change |
| *(continues alphabetically)* | *(subsequent revisions)* | *(subsequent changes)* |

### 5.2 What Constitutes a Revision

A new revision is required when:
- Any technical requirement, specification, or test parameter changes
- A test protocol is amended after initiation
- A design output drawing or BOM is updated
- A report requires correction of a documented result
- Regulatory feedback requires document updates

Administrative corrections (typographic errors that do not affect technical content) may be addressed via an Errata Notice linked to the document without creating a new revision, at the discretion of the Document Control Manager with concurrence of the QA Director.

### 5.3 Draft Status

Documents under preparation but not yet approved carry the status **DRAFT-[Revision]** (e.g., DRAFT-A). Draft documents are not part of the official DHF record and are not submitted in PMA applications. Upon signature approval, status changes to the assigned revision letter.

### 5.4 Superseded Documents

When a document is revised, the prior revision is superseded. Superseded revisions are retained in the NovaCor Document Control System (NDCS) with status SUPERSEDED and the superseding document ID noted. Superseded documents are not removed from the DHF; the complete revision history for each document is part of the DHF record per 21 CFR 820.40.

---

## 6. Change Control Requirements

All changes to approved DHF documents are subject to:

- **SOP-QMS-0025** — Document and Record Control
- **SOP-QMS-0030** — Engineering Change Order (ECO) Process
- **SOP-RD-0015** — Design Change Assessment per 21 CFR 820.30(i)

Changes to design outputs (drawings, BOMs, specifications) that constitute a design change require completion of an Engineering Change Order (ECO) form `ICD-DHF-DC-[seq]-RevA` and a design change assessment to determine whether re-verification or re-validation is required.

---

## 7. Document Register and Traceability

The master document register for all DHF documents is maintained in the NDCS under Project Number PRJ-24-001 (CardioSync CS-9000). The register provides:

- Current approved revision for each document ID
- Document title and type
- Document owner (responsible party)
- Approval date and approving signatories
- Related document links (parent/child relationships)
- PMA section cross-reference

---

## 8. Complete Example Document ID List

The following lists at least 15 example document IDs spanning all sections to illustrate correct application of the numbering scheme:

### Planning Section (PLN)
| Document ID | Title | Type |
|---|---|---|
| ICD-DHF-PLN-001-RevA | Design and Development Plan | PLAN |
| ICD-DHF-PLN-002-RevB | Risk Management Plan | PLAN |
| ICD-DHF-PLN-003-RevA | Software Development Plan (IEC 62304) | PLAN |
| ICD-DHF-PLN-004-RevA | Usability Engineering Plan (IEC 62366) | PLAN |
| ICD-DHF-PLN-005-RevA | Clinical Evaluation Plan | PLAN |

### Design Input Section (DI)
| Document ID | Title | Type |
|---|---|---|
| ICD-DHF-DI-001-RevA | Design Input Requirements Specification | SPEC |
| ICD-DHF-DI-002-RevA | Intended Use and Indications for Use Statement | SPEC |
| ICD-DHF-DI-003-RevB | User Needs Analysis and Stakeholder Input Record | RPT |

### Design Output Section (DO)
| Document ID | Title | Type |
|---|---|---|
| ICD-DHF-DO-001-RevA | Design Output Index and Device Master Record Index | LOG |
| ICD-DHF-DO-002-RevB | Device Description Document | SPEC |
| ICD-DHF-DO-003-RevA | Top-Level Assembly Drawing CS9000-ASSY-001 | DRAW |
| ICD-DHF-DO-007-RevA | Bill of Materials — Level 0 to Level 3 | BOM |
| ICD-DHF-DO-010-RevA | Software Architecture Document | SPEC |

### Design Review Section (DR)
| Document ID | Title | Type |
|---|---|---|
| ICD-DHF-DR-001-RevA | Phase Gate 1 Review Record — Feasibility Complete | LOG |
| ICD-DHF-DR-004-RevA | Phase Gate 3 Review Record — Design Output Approved | LOG |

### Design Verification Section (DV)
| Document ID | Title | Type |
|---|---|---|
| ICD-DHF-DV-001-RevA | Design Verification Plan | PLAN |
| ICD-DHF-DV-005-RevA | Test Protocol: Defibrillation Efficacy Testing | PROTO |
| ICD-DHF-DV-005-RPT-RevA | Test Report: Defibrillation Efficacy Testing | RPT |
| ICD-DHF-DV-011-RevA | Test Protocol: EMC Testing per IEC 60601-1-2 | PROTO |
| ICD-DHF-DV-020-RevA | Verification Summary Report | RPT |

### Design Validation Section (DVL)
| Document ID | Title | Type |
|---|---|---|
| ICD-DHF-DVL-001-RevA | Design Validation Plan | PLAN |
| ICD-DHF-DVL-010-RevA | Animal Study Summary — Chronic Ovine Model 90-day | RPT |
| ICD-DHF-DVL-020-RevA | Clinical Study Reference: CARDIAC-SYNC Pivotal Trial (IDE G240001) | RPT |
| ICD-DHF-DVL-025-RevA | Human Factors Validation Report (IEC 62366) | RPT |

### Design Transfer Section (DT)
| Document ID | Title | Type |
|---|---|---|
| ICD-DHF-DT-001-RevA | Design Transfer Plan | PLAN |
| ICD-DHF-DT-003-RevA | Manufacturing Process Validation Summary | RPT |

### Design Changes Section (DC)
| Document ID | Title | Type |
|---|---|---|
| ICD-DHF-DC-001-RevA | ECO-2023-0047: Header Connector Geometry Change | LOG |
| ICD-DHF-DC-002-RevA | ECO-2024-0012: Firmware Update — Sensing Algorithm Revision | LOG |

### DHF Compilation (DHF)
| Document ID | Title | Type |
|---|---|---|
| ICD-DHF-DHF-001-RevA | Document Numbering Scheme (this document) | SPEC |
| ICD-DHF-DHF-002-RevA | DHF Compilation Checklist and Completeness Verification | FORM |

### Supporting Documents (SUP)
| Document ID | Title | Type |
|---|---|---|
| ICD-DHF-SUP-001-RevA | ISO 14971 Risk Management File Index | LOG |
| ICD-DHF-SUP-005-RevA | Predicate Device Comparison — CS-8500 vs CS-9000 | RPT |
| ICD-DHF-SUP-008-RevA | Regulatory Submission Correspondence Log | LOG |

---

## 9. Document Retention

All DHF documents are retained for the lifetime of the device plus two (2) years per 21 CFR 820.180(b), and for a minimum period not less than the expected device service life following the date of manufacture, typically interpreted as device commercial life plus two years. For the CS-9000, expected service life is 10 years; therefore, minimum retention is 12 years from date of manufacture of the last unit.

Documents are stored in:
1. **Primary:** NovaCor Document Control System (NDCS) — electronic, 21 CFR Part 11 compliant
2. **Backup:** Encrypted offsite document archive, synchronized quarterly
3. **Physical:** Selected records with original wet-ink signatures retained in the QA records room, Building 3, Minneapolis facility

---

*End of Document ICD-DHF-DHF-001-RevA*

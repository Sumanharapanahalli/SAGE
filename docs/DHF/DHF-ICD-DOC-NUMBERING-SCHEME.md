# DHF DOCUMENT NUMBERING SCHEME
## CardioGuard™ ICD — Design History File
### Document ID: DHF-ICD-000-000-SPC-002-A

---

## DOCUMENT CONTROL

| Field | Value |
|---|---|
| Document ID | DHF-ICD-000-000-SPC-002-A |
| Title | DHF Document Numbering Scheme |
| Revision | A |
| Status | APPROVED |
| Effective Date | 2026-03-27 |
| Author | Document Control Specialist |
| Approved By | QA Director |

---

## 1. NUMBERING SCHEME PATTERN

All documents within the CardioGuard™ ICD Design History File follow this mandatory pattern:

```
DHF-ICD-[SECT]-[SUBSECT]-[DOCTYPE]-[SEQ]-[REV]
```

### 1.1 Field Definitions

| Position | Field | Length | Format | Description |
|---|---|---|---|---|
| 1 | Fixed Prefix | 3 | DHF | Design History File identifier |
| 2 | Program Code | 3 | ICD | Device program (ICD = CardioGuard ICD family) |
| 3 | SECT | 3 | NNN | DHF Section number (see Section 2) |
| 4 | SUBSECT | 3 | NNN | Subsection within section (001–999) |
| 5 | DOCTYPE | 3 | AAA | Document type code (see Section 3) |
| 6 | SEQ | 3 | NNN | Sequential number within [SECT]-[SUBSECT]-[DOCTYPE] group |
| 7 | REV | 1 | A | Revision letter (A=Initial release) |

**Separator:** Hyphens (-) between all fields.

**Example:** `DHF-ICD-005-003-PRT-002-B`
- DHF = Design History File
- ICD = ICD Program
- 005 = Section 5 (Design Verification)
- 003 = Subsection 3 within Section 5
- PRT = Protocol document
- 002 = Second protocol in this subsection-type grouping
- B = Second revision (first revision after initial release)

---

## 2. SECTION (SECT) CODES

| SECT Code | Section Name | 21 CFR 820.30 Mapping | Document Scope |
|---|---|---|---|
| 000 | Master / Administrative | N/A — Administrative | DHF index, numbering scheme, admin docs |
| 001 | Design and Development Planning | 820.30(b) | Plans, schedules, team charters |
| 002 | Design Input | 820.30(c) | Requirements documents, specifications |
| 003 | Design Output | 820.30(d) | Drawings, DMR, labeling, software architecture |
| 004 | Design Review | 820.30(e) | Review minutes, action item logs |
| 005 | Design Verification | 820.30(f) | Test protocols, test reports, test data |
| 006 | Design Validation | 820.30(g) | Validation protocols, validation reports, clinical data |
| 007 | Design Transfer | 820.30(h) | Transfer plans, DMR approval, first article inspection |
| 008 | Design Changes | 820.30(i) | ECOs, change logs, change impact assessments |
| 009 | Risk Management | ISO 14971:2019 | Risk plans, FMEAs, hazard logs, benefit-risk |
| 010 | Supporting Documentation | 820.30(j) | Certifications, compliance checklists, literature reviews |

---

## 3. DOCUMENT TYPE (DOCTYPE) CODES

| DOCTYPE Code | Document Type | Description | Typical Authors |
|---|---|---|---|
| PLN | Plan | Formal plan documents (design plan, V&V plan, risk plan) | Engineering, QA |
| REQ | Requirement | Requirements documents, specifications with traceable requirements | Systems Eng., Software |
| RPT | Report | Completed test/study/analysis reports with conclusions | Test Engineers, R&D |
| PRT | Protocol | Test or study protocols before execution | Test Engineers, QA |
| REC | Record | Records of activities (review minutes, inspection records) | QA, Project Managers |
| DWG | Drawing | Engineering drawings, schematics, layouts | Mechanical/EE Engineers |
| SPC | Specification | Technical specifications (component, system, process) | Engineering |
| TST | Test | Test scripts, test cases, automated test suites | Software QA |
| LOG | Log | Running log files (change log, calibration log, incident log) | QA, Engineering |
| MEM | Memo | Technical memoranda, engineering notes, decisions records | Engineering |
| CER | Certificate | Third-party certificates, accreditation letters, compliance certificates | Regulatory Affairs |
| SOP | SOP | Standard Operating Procedures | QA, Engineering |
| LBL | Label | Device labels, Instructions for Use, packaging text | Regulatory Affairs |
| IDX | Index | Section index documents, master indexes | Document Control |
| SUM | Summary | Executive summaries, section summaries | Regulatory Affairs |

---

## 4. SUBSECTION (SUBSECT) NUMBERING RULES

Subsections provide a second level of grouping within a section. The rules are:

1. **000** — Reserved for section-level administrative documents (section index, section summary)
2. **001–099** — Primary subsections (major topic areas within the section)
3. **100–199** — Attachment subsections for SUBSECT 001 primary documents
4. **200–299** — Attachment subsections for SUBSECT 002 primary documents
5. **N00–N99** — General rule: attachments of SUBSECT N use range N×100 to N×100+99 (up to N=9)
6. **900–999** — Reserved for superseded/obsolete documents (retained for traceability)

### Subsection Examples for Section 005 (Verification):

| SUBSECT | Topic |
|---|---|
| 001 | V&V Master Plan |
| 002 | Electrical Characterization Testing |
| 003 | Defibrillation Waveform Testing |
| 004 | Battery and Longevity Testing |
| 005 | EMI/EMC Testing |
| 006 | Mechanical Integrity Testing |
| 007 | Software Verification |
| 008 | Biocompatibility Test Protocols |
| 200 | Attachments to Electrical Characterization (test data tables, raw data) |
| 300 | Attachments to Defibrillation Waveform Testing |

---

## 5. SEQUENTIAL NUMBER (SEQ) RULES

1. SEQ starts at 001 for each unique combination of [SECT]-[SUBSECT]-[DOCTYPE].
2. Multiple documents of the same type within the same subsection are numbered sequentially: 001, 002, 003...
3. SEQ numbers are never reused, even if a document is superseded (superseded documents move to SUBSECT 900+ range).
4. For sub-documents and appendices, use the parent SEQ number with an appended letter: `DHF-ICD-005-002-PRT-001-A-APP-A` (Appendix A to the first protocol in 005-002).

---

## 6. REVISION (REV) RULES

| Revision | Meaning | Trigger |
|---|---|---|
| A | Initial release | First approved version of a new document |
| B | First revision | Any change to an approved document via ECO |
| C | Second revision | Second change event |
| ... | Subsequent revisions | Each subsequent ECO-driven change |

**Rules:**
- Draft documents use the notation `[REV]-DRAFT-[n]` (e.g., A-DRAFT-3) and are NOT controlled documents.
- Only approved documents receive a clean revision letter.
- Revision letters skip I, O, and Q to avoid confusion with numerals (1, 0) and letters.
- If a document undergoes a complete rewrite (>50% content change), it receives a new document number (new SEQ) and references the superseded document ID.

---

## 7. ANNEX AND ATTACHMENT NUMBERING

For documents with formal annexes or appendices:

**Pattern:** `[Parent-Document-ID]-[TYPE]-[ANNEX-ID]`

| Annex Type | Code | Example |
|---|---|---|
| Appendix | APP | DHF-ICD-005-002-PRT-001-A-APP-A |
| Annex | ANX | DHF-ICD-009-003-REC-001-B-ANX-01 |
| Attachment | ATT | DHF-ICD-002-001-REQ-001-B-ATT-01 |
| Exhibit | EXH | DHF-ICD-006-010-RPT-001-A-EXH-03 |

---

## 8. COMPLETE SAMPLE DOCUMENT ID TABLE — 30+ EXAMPLES

The following table provides 30 representative sample document IDs across all DHF sections to illustrate correct application of the numbering scheme.

| # | Document ID | Section | Type | Document Title |
|---|---|---|---|---|
| 1 | DHF-ICD-000-000-IDX-001-A | Master | Index | Design History File Master Index |
| 2 | DHF-ICD-000-000-SPC-002-A | Master | Specification | Document Numbering Scheme (this document) |
| 3 | DHF-ICD-001-001-PLN-001-A | Planning | Plan | Design and Development Plan |
| 4 | DHF-ICD-001-002-PLN-001-A | Planning | Plan | Phase Gate Review Procedure |
| 5 | DHF-ICD-001-003-REC-001-A | Planning | Record | Team Roles and Responsibilities Matrix |
| 6 | DHF-ICD-001-004-LOG-001-A | Planning | Log | Project Schedule and Milestone Log |
| 7 | DHF-ICD-001-005-PLN-001-A | Planning | Plan | Interface Control and Communication Procedure |
| 8 | DHF-ICD-002-001-REQ-001-B | Design Input | Requirement | Design Input Requirements Document (DIRD) |
| 9 | DHF-ICD-002-002-REQ-001-A | Design Input | Requirement | Software Requirements Specification (SRS) |
| 10 | DHF-ICD-002-003-REQ-001-A | Design Input | Requirement | Electrical Systems Requirements Specification |
| 11 | DHF-ICD-002-004-REQ-001-A | Design Input | Requirement | Mechanical Design Requirements |
| 12 | DHF-ICD-002-006-REC-001-A | Design Input | Record | Design Input Approval Review Record |
| 13 | DHF-ICD-003-001-SPC-001-C | Design Output | Specification | Device Master Record Index |
| 14 | DHF-ICD-003-002-DWG-001-C | Design Output | Drawing | Assembly Drawing — CG-7001 Can Assembly |
| 15 | DHF-ICD-003-005-LBL-001-B | Design Output | Label | Device Labeling Package (IFU + Can Label) |
| 16 | DHF-ICD-004-003-REC-001-A | Design Review | Record | Design Review #3 — Design Phase Minutes |
| 17 | DHF-ICD-004-006-REC-001-A | Design Review | Record | Final Design Review — Transfer Readiness |
| 18 | DHF-ICD-005-001-PLN-001-A | Verification | Plan | V&V Master Plan |
| 19 | DHF-ICD-005-002-PRT-001-A | Verification | Protocol | Electrical Characterization Test Protocol |
| 20 | DHF-ICD-005-002-RPT-001-A | Verification | Report | Electrical Characterization Test Report |
| 21 | DHF-ICD-005-004-PRT-001-A | Verification | Protocol | Defibrillation Waveform Verification Protocol |
| 22 | DHF-ICD-005-005-RPT-001-A | Verification | Report | Defibrillation Waveform Verification Report |
| 23 | DHF-ICD-005-006-PRT-001-A | Verification | Protocol | EMI/EMC Test Protocol (IEC 60601-1-2) |
| 24 | DHF-ICD-005-010-TST-001-A | Verification | Test | Software Unit Test Suite — Detection Algorithm |
| 25 | DHF-ICD-006-001-PRT-001-A | Validation | Protocol | Simulated Use Validation Protocol |
| 26 | DHF-ICD-006-003-PRT-001-A | Validation | Protocol | Human Factors Validation Protocol (IEC 62366) |
| 27 | DHF-ICD-006-005-PRT-001-A | Validation | Protocol | EO Sterilization Validation Protocol |
| 28 | DHF-ICD-006-009-PRT-001-A | Validation | Protocol | Clinical Validation Protocol (IDE Study CG-IDE-001) |
| 29 | DHF-ICD-007-001-PLN-001-A | Transfer | Plan | Design Transfer Plan |
| 30 | DHF-ICD-007-003-REC-001-A | Transfer | Record | First Article Inspection Report |
| 31 | DHF-ICD-008-001-SOP-001-A | Changes | SOP | Design Change Control Procedure |
| 32 | DHF-ICD-008-002-LOG-001-A | Changes | Log | Engineering Change Order (ECO) Register |
| 33 | DHF-ICD-009-001-PLN-001-A | Risk Mgmt | Plan | Risk Management Plan (ISO 14971:2019) |
| 34 | DHF-ICD-009-003-REC-001-B | Risk Mgmt | Record | Risk Estimation and Evaluation Matrix (FMEA) |
| 35 | DHF-ICD-009-006-RPT-001-A | Risk Mgmt | Report | Benefit-Risk Analysis Report |
| 36 | DHF-ICD-009-008-RPT-001-A | Risk Mgmt | Report | Risk Management Report |
| 37 | DHF-ICD-010-001-CER-001-A | Supporting | Certificate | Biocompatibility Assessment Certificate (ISO 10993) |
| 38 | DHF-ICD-010-002-CER-001-A | Supporting | Certificate | IEC 60601-1 Electrical Safety Test Certificate |
| 39 | DHF-ICD-010-003-CER-001-A | Supporting | Certificate | IEC 62304 Software Safety Classification Certificate |
| 40 | DHF-ICD-005-002-PRT-001-A-APP-A | Verification | Appendix | Appendix A: Bench Test Setup Photographs |

---

## 9. LOOKUP QUICK REFERENCE

**To find all verification protocols:** Filter on SECT=005, DOCTYPE=PRT
**To find all approved plans:** Filter on DOCTYPE=PLN, Status=APPROVED
**To find all risk management records:** Filter on SECT=009
**To find all test reports for EMC:** Filter on SECT=005, SUBSECT=006, DOCTYPE=RPT

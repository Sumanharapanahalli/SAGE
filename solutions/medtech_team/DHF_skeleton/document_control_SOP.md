# Document Control Standard Operating Procedure
## Elder Fall Detection System

**Document Number:** SOP-DC-001
**Revision:** A
**Status:** APPROVED
**Effective Date:** 2026-03-22
**Owner:** Quality Assurance
**Approved By:** regulatory_specialist

---

## 1. Purpose

This SOP defines the document control system for all Design History File (DHF) documents and quality system records for the Elder Fall Detection System. It ensures compliance with:
- **FDA 21 CFR Part 820.40** — Document Controls
- **ISO 13485:2016 Section 4.2.4** — Control of Documents
- **FDA 21 CFR Part 820.180** — General Requirements for Records

## 2. Scope

All controlled documents including: specifications, procedures, drawings, test protocols, test reports, review records, and forms associated with the Elder Fall Detection System DHF.

## 3. Version Numbering Scheme

### 3.1 Revision Levels

| Revision Type | Format | When Used |
|---|---|---|
| Major revision | A, B, C, ... | Significant content change; requires full review and approval cycle |
| Minor revision | A1, A2, B1, ... | Editorial corrections, clarifications that do not change intent or requirements |
| Draft | DRAFT-01, DRAFT-02 | Pre-approval working versions; not controlled |
| Obsolete | Rev + [OBSOLETE] | Superseded revisions retained for DHF completeness |

### 3.2 Document Numbering

```
[TYPE]-[SOLUTION]-[SEQUENCE]

Examples:
  DI-EFD-001   — Design Input document #001 for Elder Fall Detection
  VER-EFD-003  — Verification document #003
  SOP-DC-001   — Standard Operating Procedure, Document Control, #001
```

**Type Codes:**

| Code | Document Type |
|---|---|
| DDP | Design and Development Plan |
| DI | Design Input |
| DO | Design Output |
| DR | Design Review Record |
| VER | Verification |
| VAL | Validation |
| RM | Risk Management |
| DT | Design Transfer |
| CC | Change Control |
| SOP | Standard Operating Procedure |
| TM | Traceability Matrix |
| IEC | IEC Classification Record |

## 4. Review and Approval Workflow

### 4.1 Standard Approval Workflow

```
AUTHOR creates DRAFT
    |
PEER REVIEW (technical reviewer — same discipline)
    |  [reviewer comments addressed]
QA REVIEW (Quality Assurance — process compliance check)
    |  [QA comments addressed]
REGULATORY REVIEW (regulatory_specialist — for DI, VAL, design review records)
    |  [regulatory comments addressed]
APPROVAL (Department Manager or designated approver)
    |
DOCUMENT RELEASED (status -> APPROVED, effective date set)
    |
DISTRIBUTION to controlled copy holders
```

### 4.2 Required Reviewers by Document Type

| Document Type | Author | Peer Reviewer | QA Review | Regulatory Review | Final Approver |
|---|---|---|---|---|---|
| Design Input Requirements | Systems Eng | Technical Lead | QA Manager | regulatory_specialist | Chief Engineer |
| Software Requirements Spec | Software Eng | Software Lead | QA Manager | Optional | Software Manager |
| Hardware Design Spec | Hardware Eng | Hardware Lead | QA Manager | Optional | Hardware Manager |
| Design Review Records | QA | All attendees | QA Manager | regulatory_specialist | Project Manager |
| Verification Protocols | V&V Eng | Technical Lead | QA Manager | Optional | V&V Manager |
| Verification Reports | V&V Eng | Technical Lead | QA Manager | regulatory_specialist | V&V Manager |
| Validation Protocols | V&V / Clinical | Clinical Lead | QA Manager | regulatory_specialist | V&V Manager |
| Validation Reports | V&V / Clinical | Clinical Lead | QA Manager | regulatory_specialist | Chief Engineer |
| Risk Management File | Systems / QA | Safety Eng | QA Manager | regulatory_specialist | Chief Engineer |
| SOPs | QA | Department Lead | QA Manager | N/A | QA Manager |

### 4.3 Review Timeframes

| Review Stage | Maximum Duration |
|---|---|
| Peer Review | 5 business days |
| QA Review | 5 business days |
| Regulatory Review | 10 business days |
| Final Approval | 3 business days |
| Total (standard) | <= 23 business days |
| Expedited (justified) | <= 10 business days — requires QA Manager authorization |

### 4.4 HITL Approval Gate

The following documents require **explicit approval by regulatory_specialist** before any downstream phase activity may begin:

1. Design Input Requirements Specification (DI-EFD-002)
2. All Design Review Records (DR-EFD-001 through DR-EFD-004)
3. Design Verification Summary Report (VER-EFD-007)
4. Design Validation Plan (VAL-EFD-001)
5. Design Validation Summary Report (VAL-EFD-006)

No exceptions. No conditional approvals. regulatory_specialist signature = gate cleared.

## 5. Document Status Definitions

| Status | Definition | Permitted Actions |
|---|---|---|
| DRAFT | Under preparation or revision | Author and designated reviewers only |
| IN REVIEW | Circulated for formal review | Reviewers may comment; no implementation |
| APPROVED | Formally approved and effective | Implementation authorized |
| OBSOLETE | Superseded by new revision | Archived; reference only |
| VOID | Withdrawn without replacement | Archived; must not be used |

## 6. Document Storage and Retrieval

### 6.1 Master Location
All controlled documents stored in: `/DHF/` directory tree as indexed in DHF-EFD-001

### 6.2 Backup
All DHF documents backed up daily to off-site location. Backup integrity verified quarterly.

### 6.3 Retention
All DHF records retained for the lifetime of the device plus 2 years (FDA requirement: 21 CFR 820.180(b)) or as required by applicable regulations, whichever is longer.

### 6.4 Access Control

| Role | Read | Create Draft | Review | Approve |
|---|---|---|---|---|
| All engineering staff | Yes | Yes | Yes (own discipline) | No |
| QA staff | Yes | Yes | Yes | QA docs only |
| QA Manager | Yes | Yes | Yes | Yes (per matrix) |
| regulatory_specialist | Yes | Yes | Yes | Yes (per matrix) |
| Department Managers | Yes | Yes | Yes | Yes (per matrix) |
| External auditors | Read-only (controlled) | No | No | No |

## 7. Change Control

### 7.1 Change Request Process

```
1. Originator submits Design Change Request (DCR)
2. QA assigns DCR number and logs in CC-EFD-002
3. Impact assessment: affected documents, tests, risk management
4. Classification: Minor (editorial) or Major (content/requirement change)
5. For Major changes: full review/approval cycle per Section 4
6. Updated document released; superseded revision archived as OBSOLETE
7. Affected downstream documents flagged for review
```

### 7.2 Emergency Changes
In the event a safety-critical change is required during production: QA Manager may authorize immediate implementation with documented rationale, followed by formal DCR within 5 business days.

## 8. Revision History

| Rev | Date | Author | Description |
|---|---|---|---|
| A | 2026-03-22 | QA | Initial release |

# Design History File (DHF) Index
## SAGE[ai] — Autonomous Manufacturing Intelligence System

**Document ID:** SAGE-DHF-001
**Version:** 2.0.0
**Status:** Approved
**Date:** 2026-03-11

---

## 1. Purpose

This Design History File (DHF) Index provides the complete list of design control documents for SAGE[ai], in accordance with:
- **ISO 13485:2016 §7.3** — Design and Development
- **FDA 21 CFR Part 820.30** — Design Controls
- **IEC 62304:2006+AMD1:2015** — Medical Device Software Lifecycle

The DHF demonstrates that the design was developed in accordance with the approved design plan and that the device conforms to its design specifications.

---

## 2. DHF Document Registry

### 2.1 Planning Documents

| Doc ID | Document Title | File Path | Version | Date | Status |
|---|---|---|---|---|---|
| SAGE-DPL-001 | Software Development Plan | `ARCHITECTURE.md` | 2.0.0 | 2026-03-11 | Approved |
| SAGE-SRS-001 | Software Requirements Specification | `docs/regulatory/SRS.md` | 2.0.0 | 2026-03-11 | Approved |
| SAGE-VVP-001 | Verification & Validation Plan | `docs/regulatory/VV_PLAN.md` | 2.0.0 | 2026-03-11 | Approved |
| SAGE-CMP-001 | Configuration Management Plan | `docs/regulatory/CONFIG_MGMT_PLAN.md` | 2.0.0 | 2026-03-11 | Approved |

### 2.2 Risk Management Documents

| Doc ID | Document Title | File Path | Version | Date | Status |
|---|---|---|---|---|---|
| SAGE-RM-001 | Risk Management Report (ISO 14971) | `docs/regulatory/RISK_MANAGEMENT.md` | 2.0.0 | 2026-03-11 | Approved |

### 2.3 Design Output Documents

| Doc ID | Document Title | File Path | Version | Date | Status |
|---|---|---|---|---|---|
| SAGE-ARCH-001 | System Architecture | `ARCHITECTURE.md` | 2.0.0 | 2026-03-11 | Approved |
| SAGE-API-001 | REST API Specification | Auto-generated at `/docs` | 2.0.0 | Live | Auto-generated |
| SAGE-SOUP-001 | SOUP Inventory | `docs/regulatory/SOUP_INVENTORY.md` | 2.0.0 | 2026-03-11 | Approved |

### 2.4 Verification and Validation Records

| Doc ID | Document Title | File Path | Version | Date | Status |
|---|---|---|---|---|---|
| SAGE-RTM-001 | Requirements Traceability Matrix | `docs/regulatory/RTM.md` | 2.0.0 | 2026-03-11 | Approved |
| SAGE-VVR-001 | Unit Test Results | `reports/unit_test_results.html` | Per run | Generated | Generated |
| SAGE-VVR-002 | Integration Test Results | `reports/integration_results.html` | Per run | Generated | Generated |
| SAGE-VVR-003 | IQ/OQ/PQ Qualification Report | `reports/qualification_report.html` | Per release | Generated | Generated |
| SAGE-TR-001 | Software Testing Report Template | `docs/regulatory/TEST_REPORT_TEMPLATE.md` | 2.0.0 | 2026-03-11 | Approved |

### 2.5 Compliance Documents

| Doc ID | Document Title | File Path | Version | Date | Status |
|---|---|---|---|---|---|
| SAGE-COMP-001 | ISO 13485 / FDA 21 CFR Part 11 Compliance | `docs/COMPLIANCE.md` | 2.0.0 | 2026-03-11 | Approved |
| SAGE-SEC-001 | Security Plan | `docs/regulatory/SECURITY_PLAN.md` | 2.0.0 | 2026-03-11 | Approved |

### 2.6 Change Control Records

| Doc ID | Document Title | File Path | Version | Date | Status |
|---|---|---|---|---|---|
| SAGE-CCR-001 | Change Control Procedure | `docs/regulatory/CHANGE_CONTROL.md` | 2.0.0 | 2026-03-11 | Approved |
| SAGE-CCR-LOG | Change Control Log | `data/audit_log.db` (MR_CREATED entries) | N/A | Continuous | Active |

---

## 3. Document Control

### 3.1 Document Lifecycle States

| State | Definition |
|---|---|
| **Draft** | Under development; not for use |
| **In Review** | Submitted for peer/QA review |
| **Approved** | Reviewed and approved; current version |
| **Obsolete** | Superseded by a newer version |

### 3.2 Review and Approval Requirements

All DHF documents require:
- **Author** — Creates and owns the document
- **Technical Reviewer** — Peer engineer review
- **QA Reviewer** — Quality Assurance sign-off
- **Approval Authority** — Engineering Manager or QA Manager

### 3.3 Version Control

All DHF source documents are version-controlled in the Git repository. The Git commit hash associated with each approved version is recorded in the audit trail (`DOCUMENT_APPROVED` event type).

---

## 4. DHF Completeness Checklist

| Requirement | Document Present | Status |
|---|---|---|
| Design plan exists | SAGE-DPL-001 (ARCHITECTURE.md) | ✓ |
| Design inputs documented | SAGE-SRS-001 | ✓ |
| Risk analysis performed | SAGE-RM-001 | ✓ |
| Design outputs documented | SAGE-ARCH-001, SAGE-API-001 | ✓ |
| V&V plan exists | SAGE-VVP-001 | ✓ |
| V&V results recorded | SAGE-VVR-001/002/003 | Generated per release |
| Traceability matrix | SAGE-RTM-001 | ✓ |
| SOUP documented | SAGE-SOUP-001 | ✓ |
| Change control procedure | SAGE-CCR-001 | ✓ |
| Configuration management | SAGE-CMP-001 | ✓ |
| Security assessment | SAGE-SEC-001 | ✓ |

---

## 5. Release History

| Version | Date | Description | Change Control Ref |
|---|---|---|---|
| 1.0.0 | 2025-06-01 | Initial release — Core CLI, analyst agent, audit trail | CCR-2025-001 |
| 2.0.0 | 2026-03-11 | Phase 2 — Developer agent, monitor, REST API, web UI, ReAct loop, planner agent, persistent queue | CCR-2026-001 |

---

*Document Owner: Quality Assurance Manager*
*Next Review Date: 2026-09-11*

# Change Control Procedure
## SAGE[ai] — Autonomous Manufacturing Intelligence System

**Document ID:** SAGE-CCR-001
**Version:** 2.0.0
**Status:** Approved
**Date:** 2026-03-11

---

## 1. Purpose

This document defines the Change Control Procedure for SAGE[ai] software changes, ensuring that all modifications are properly evaluated, approved, implemented, and verified in accordance with:
- **ISO 13485:2016 §7.3.9** — Control of Design and Development Changes
- **FDA 21 CFR Part 820.30(i)** — Design Changes
- **IEC 62304:2006+AMD1:2015 §6.2** — Software Maintenance Process

---

## 2. Scope

This procedure applies to ALL changes to:
- Source code (`src/`, `mcp_servers/`, `web/src/`)
- Configuration (`config/config.yaml`)
- Infrastructure scripts (`scripts/`)
- DHF documents (`docs/regulatory/`)
- AI models or LLM providers
- SOUP versions (see SOUP_INVENTORY.md)

---

## 3. Change Classification

| Class | Description | Examples | Approval Required |
|---|---|---|---|
| **Class I — Minor** | Low-risk, no safety impact; documentation or cosmetic | Typo fix, log message change, comment update | Engineering Lead |
| **Class II — Standard** | Moderate risk; functional change with limited scope; no safety impact | New API endpoint, UI component, config option | Engineering Lead + QA |
| **Class III — Major** | High risk; new feature, architectural change, safety-impacting | New agent, ReAct loop, persistent queue, new SOUP | Engineering Lead + QA + Management |
| **Class IV — Emergency** | Critical safety or compliance issue requiring immediate fix | Audit trail corruption, HITL bypass discovered | QA + Management (retrospective review) |

---

## 4. Change Control Process

```
Initiate Change Request (CR)
         │
         ▼
   Impact Assessment
   ├── Safety impact?
   ├── Regulatory impact?
   ├── Test coverage impact?
   └── SOUP changes?
         │
         ▼
   Change Classification
         │
         ▼
   Design Review (for Class II-IV)
         │
         ▼
   Implementation
   └── Code change in feature branch
         │
         ▼
   Verification Testing
   ├── Unit tests pass
   ├── Integration tests pass (if applicable)
   └── IQ/OQ/PQ re-run (for Class III-IV)
         │
         ▼
   Peer Code Review (GitLab MR)
   └── AI-assisted review (SAGE[ai] itself)
         │
         ▼
   QA Review and Approval
         │
         ▼
   Merge and Release
         │
         ▼
   Post-Change Verification
   └── Audit trail entry: CHANGE_IMPLEMENTED
```

---

## 5. Change Request Form

Each change shall be initiated as a GitLab issue with the following information:

**Required Fields:**
- **CR ID:** Auto-assigned GitLab issue number
- **Title:** Concise description of the change
- **Requested By:** Name and role
- **Date Requested:** YYYY-MM-DD
- **Change Classification:** Class I / II / III / IV
- **Problem Statement:** What issue is being solved?
- **Proposed Solution:** High-level description of the change
- **Affected Components:** Which files/modules will change?
- **Safety Impact Assessment:** Could this change affect patient safety?
- **Regulatory Impact:** Does this affect ISO 13485 / FDA compliance?
- **SOUP Changes:** Are any SOUP items being added, removed, or updated?
- **Verification Plan:** What tests will verify the change?

---

## 6. Version Numbering

SAGE[ai] uses **Semantic Versioning (SemVer)**: `MAJOR.MINOR.PATCH`

| Increment | Trigger |
|---|---|
| **MAJOR** | Breaking API change; architectural redesign; Class III or IV change |
| **MINOR** | New feature; new agent; new endpoint; backward-compatible (Class II-III) |
| **PATCH** | Bug fix; documentation; SOUP patch update (Class I-II) |

---

## 7. SOUP Version Change Procedure

When a SOUP item version changes:
1. Update `requirements.txt` (Python) or `web/package.json` (Node.js)
2. Update `docs/regulatory/SOUP_INVENTORY.md` with new version
3. Re-execute affected test cases from the V&V Plan
4. Record the change in the audit log as `SOUP_VERSION_CHANGE`
5. Update the DHF Index (SAGE-DHF-001) with new document versions

---

## 8. Emergency Change Procedure

For Class IV emergency changes:
1. Engineering Lead and QA Manager jointly authorize the change verbally
2. Change implemented immediately in a hotfix branch
3. Abbreviated testing: unit tests + specific regression tests
4. MR created, AI-reviewed by SAGE[ai], merged after QA verbal approval
5. **Within 48 hours**: Full change control documentation completed retrospectively
6. Formal QA sign-off within 5 business days

---

## 9. Change Control Log

The master change control log is maintained in the compliance audit trail (`data/audit_log.db`) via `MR_CREATED` and `MR_REVIEW` action types. Each approved MR corresponds to a controlled change.

Additionally, significant architectural changes are summarised in this table:

| CR ID | Version | Date | Description | Class | Approval |
|---|---|---|---|---|---|
| CCR-2025-001 | 1.0.0 | 2025-06-01 | Initial release — core analyst, CLI, audit trail | III | QA Manager |
| CCR-2025-002 | 1.1.0 | 2025-08-15 | Developer agent, GitLab integration | III | QA Manager |
| CCR-2025-003 | 1.2.0 | 2025-10-20 | Monitor agent, Teams/Metabase polling | III | QA Manager |
| CCR-2026-001 | 2.0.0 | 2026-03-11 | Web UI, ReAct loop, Planner agent, persistent queue, regulatory docs | III | QA Manager |

---

## 10. Post-Market Surveillance

After each release, the following monitoring activities apply:
- Review audit trail entries weekly for anomalies
- Review SOUP vulnerability notifications monthly
- Track user-reported issues in GitLab
- Annual review of risk management (RISK_MANAGEMENT.md)

---

*Document Owner: Quality Assurance Manager*
*Next Review Date: 2026-09-11*

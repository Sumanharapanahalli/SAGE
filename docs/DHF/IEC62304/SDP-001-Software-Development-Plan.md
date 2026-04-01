# Software Development Plan
**Document ID:** SDP-001
**Version:** 1.0.0
**Status:** APPROVED
**Date:** 2026-03-27
**Classification:** IEC 62304 Class B
**Author:** Software Development Lead
**Reviewed by:** Quality Engineer — J. Hargreaves
**Approved by:** Regulatory Affairs — M. Chen

---

## Document Control

| Version | Date | Author | Change Description |
|---------|------|--------|--------------------|
| 0.1 | 2026-01-10 | Dev Lead | Initial draft |
| 0.2 | 2026-02-14 | Dev Lead | Incorporated QE review comments |
| 1.0 | 2026-03-27 | Dev Lead | Approved for regulatory submission |

---

## 1. Purpose and Scope
*(IEC 62304 §5.1.1)*

This Software Development Plan (SDP) defines the policies, processes, standards, tools, responsibilities, and schedule governing the development of the **SAGE Medical Device Software (SAGE-MDS)**, a Class B software item per IEC 62304:2006+AMD1:2015.

SAGE-MDS provides AI-assisted clinical decision support and patient monitoring functions embedded in the SAGE ICD wearable device. This plan applies to all software deliverables from concept through release and post-market maintenance.

### 1.1 Software Safety Classification
*(IEC 62304 §4.3)*

| Software Item | Safety Class | Justification |
|---------------|-------------|---------------|
| SAGE-MDS Core | **Class B** | A failure could result in patient harm (missed alert), but no direct injury mechanism exists; no hazard leads to death or serious injury without other independent failures |
| Signal Processing Module | Class B | Incorrect signal processing may produce erroneous alerts |
| Communication Gateway | Class A | Failure does not lead to unacceptable risk; loss of comms triggers safe fail-state |
| UI Presentation Layer | Class A | Informational display only; clinical decisions are independent |

**Safety class reviewed and accepted by:** J. Hargreaves, Quality Engineer — 2026-03-27
**Signature:** _______________

---

## 2. References

- IEC 62304:2006+AMD1:2015 — Medical device software — Software life cycle processes
- IEC 62443-4-1:2018 — Security by design
- ISO 14971:2019 — Application of risk management
- ISO 13485:2016 — Quality management systems
- FDA Guidance: Content of Premarket Submissions (2023)
- FDA Guidance: Software as Medical Device (SaMD) — Clinical Evaluation (2017)
- SOUP List: SOUPv1.0 (see SRS-002 §6)
- Project Risk Management Plan: RMP-SAGE-001

---

## 3. Lifecycle Model
*(IEC 62304 §5.1.1(a))*

SAGE-MDS uses a **spiral V-model** with two-week development sprints and quarterly integration milestones. The lifecycle phases are:

```
Requirements → Architecture → Detailed Design → Implementation
     ↑                                                    ↓
System Test ← Integration Test ← Unit Test ← Code Review
     ↓
Release → Post-Market Surveillance
```

Each phase gate requires completion and sign-off of the corresponding IEC 62304 document artifact before proceeding.

---

## 4. Deliverables and Schedule
*(IEC 62304 §5.1.1(b))*

| Phase | Deliverable | Document ID | Target Date | Responsible |
|-------|-------------|-------------|-------------|-------------|
| Planning | Software Development Plan | SDP-001 | 2026-03-27 | Dev Lead |
| Requirements | Software Requirements Specification | SRS-002 | 2026-04-10 | Systems Eng |
| Architecture | Software Architecture Document | SAD-003 | 2026-04-25 | Architect |
| Design | Software Detailed Design | SDD-004 | 2026-05-15 | Dev Team |
| Unit Test | Unit Test Records | UTR-005 | 2026-06-05 | Dev Team |
| Integration | Integration Test Records | ITR-006 | 2026-06-20 | QA Team |
| System Test | System Test Records | STR-007 | 2026-07-10 | QA Lead |
| Problem Mgmt | Problem Resolution Process | PRP-008 | 2026-03-27 | QA Team |
| Release | Software Release Record | SRR-009 | 2026-07-25 | Reg Affairs |
| Traceability | Traceability Matrix | TRM-010 | Rolling | Dev/QA |

---

## 5. Standards and Procedures
*(IEC 62304 §5.1.1(c))*

### 5.1 Coding Standards
- Language: Python 3.11+ (backend), TypeScript 5.x (UI)
- Style: PEP 8 (Python), ESLint + Prettier (TypeScript)
- Complexity: Cyclomatic complexity ≤ 10 per function
- Coverage target: ≥ 90% statement coverage for Class B modules
- Static analysis: Bandit (Python), SonarQube (all)

### 5.2 Version Control
- System: Git with GitHub Enterprise
- Branch strategy: GitFlow (main, develop, feature/*, hotfix/*)
- Commit policy: Signed commits, linked to issue tracker
- Tag format: `v{major}.{minor}.{patch}-{build}`

### 5.3 Code Review
- All Class B code requires two-reviewer approval
- Review checklist: CR-CHK-001 (stored in QMS)
- Security review required for all network-facing modules

### 5.4 Documentation Standards
- All documents authored in Markdown, version-controlled in Git
- PDF exports for regulatory submission generated via Pandoc
- Document IDs follow schema: `{TYPE}-{SEQ}-{Title}`

---

## 6. Tools
*(IEC 62304 §5.1.1(d))*

| Tool | Version | Purpose | Qualification Status |
|------|---------|---------|---------------------|
| Python | 3.11.9 | Implementation | COTS — inherent trust |
| pytest | 8.1.1 | Unit/integration testing | Validated per TVR-001 |
| GitHub Enterprise | 3.12 | SCM, CI/CD | Validated per TVR-002 |
| SonarQube | 10.4 | Static analysis | Validated per TVR-003 |
| Bandit | 1.7.8 | Security static analysis | Validated per TVR-004 |
| Pandoc | 3.2 | Document generation | COTS — inherent trust |
| Docker | 25.0 | Build isolation | Validated per TVR-005 |

---

## 7. Risk Management Integration
*(IEC 62304 §4.2)*

Software risk activities are governed by ISO 14971 Risk Management Plan RMP-SAGE-001. Software-specific risk activities include:

- Identification of software failure modes → SRS hazard annotations
- SOUP risk assessment → SOUPv1.0 (referenced in SRS §6)
- Residual risk sign-off required before release (see SRR-009 §4)
- Risk control measures verified in system test (STR-007)

---

## 8. Configuration Management
*(IEC 62304 §8.1)*

- All software items under Git version control
- Release baselines tagged and immutable after QA sign-off
- Change control via GitHub PRs with mandatory review
- Configuration audit performed at each phase gate
- SBOM (Software Bill of Materials) generated at each release

---

## 9. Problem Resolution
*(IEC 62304 §9)*

All software anomalies discovered during development or post-market are managed per Problem Resolution Process PRP-008. Severity classification follows FDA/IEC 62304 §9.1 guidelines.

---

## 10. Maintenance Plan
*(IEC 62304 §6.1)*

Post-release maintenance follows a documented Maintenance Plan MP-SAGE-001, including:
- Correction of defects within SLA by severity class
- Post-market surveillance feedback loop to requirements
- Change impact analysis for all modifications
- Re-validation scope determination per change risk

---

*End of SDP-001*

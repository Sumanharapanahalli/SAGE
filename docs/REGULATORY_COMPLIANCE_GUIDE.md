# SAGE Framework — Regulatory Compliance Readiness Guide

> **Version 1.0** | April 2026
> **Audience:** Teams evaluating SAGE for regulated product development

---

## Disclaimer

**SAGE provides compliance TOOLING, not compliance CERTIFICATION.** The framework implements computational engines, gap analysis, and workflow governance that support regulatory processes. However, using SAGE output directly in regulatory submissions without domain expert review and additional engineering is not recommended. SAGE is a tool that helps teams work toward compliance — it does not make a product compliant by itself.

---

## What SAGE Actually Provides

### Fully Implemented (Production-Ready Computation)

| Capability | Status | Details |
|---|---|---|
| **FMEA** (Failure Mode & Effects Analysis) | **IMPLEMENTED** | RPN = Severity x Occurrence x Detection. Correct formula, risk level determination, sorted by priority. |
| **FTA** (Fault Tree Analysis) | **IMPLEMENTED** | AND/OR gate probability computation, minimal cut set identification, recursive nested gates. |
| **ASIL Classification** (ISO 26262) | **IMPLEMENTED** | Exact ISO 26262:2018 matrix: Severity (S0-S3) x Exposure (E1-E4) x Controllability (C1-C3) → QM/A/B/C/D. |
| **SIL Classification** (IEC 61508) | **IMPLEMENTED** | SIL 1-4 based on PFH (Probability of Hazardous Failure per hour). Fixed thresholds per standard. |
| **IEC 62304 Software Safety Class** | **IMPLEMENTED** | Risk-level to class mapping: Class A (no injury), B (serious injury), C (death possible). |
| **Safety Requirements Generation** | **IMPLEMENTED** | 3 requirements per hazard (detection, mitigation, notification) with verification methods. |
| **Immutable Audit Log** | **IMPLEMENTED** | SQLite append-only log with UUID trace IDs, ISO 8601 timestamps, per-solution isolation. |
| **HITL Approval Gates** | **IMPLEMENTED** | Risk-tiered proposals (INFORMATIONAL → DESTRUCTIVE), rejection feedback stored in vector memory. |
| **PII Detection** | **IMPLEMENTED** | Presidio NLP + regex fallback. Modes: flag, redact, mask. Data residency enforcement. |

### Reference & Gap Analysis (Good for Planning, Not Submission)

| Capability | Status | Details |
|---|---|---|
| **Standards Registry** | **REFERENCE** | 50+ standards documented with clause references (IEC 62304, ISO 14971, FDA guidance, EU MDR, ISO 26262, DO-178C, etc.). Lookup table, not validation engine. |
| **Compliance Assessment** | **PARTIAL** | Scores artifact presence (not content quality). Good for initial gap identification. |
| **Gap Analysis** | **PARTIAL** | Lists missing artifacts and suggests remediation per standard. Doesn't validate content. |
| **Submission Roadmap** | **PARTIAL** | 4-phase plan with estimated weeks. Generic — teams need domain experts to customize. |
| **CDS Classification** (FDA) | **PARTIAL** | 4-criterion classification per FDA Jan 2026 guidance. Deterministic but context may vary. |
| **Systems Engineering** | **PARTIAL** | LLM-based requirements derivation and architecture design. No traceability validation. |

### Recently Implemented (Compliance Engineering Modules)

| Capability | Status | Details |
|---|---|---|
| **Document Generation** (Markdown) | **IMPLEMENTED** | SRS, Risk Management, RTM, V&V Plan, SOUP Inventory. Generates structured Markdown from live data via `/compliance/documents/generate`. |
| **Cryptographic Audit Integrity** (21 CFR Part 11) | **IMPLEMENTED** | HMAC-SHA256 hash chain on audit log entries. Tamper detection via `/compliance/audit/integrity/verify`. |
| **Bidirectional Traceability Matrix** | **IMPLEMENTED** | Requirement-to-design-to-test linking with coverage analysis and gap detection via `/compliance/traceability/*`. |
| **Change Control Workflow** | **IMPLEMENTED** | Version-tracked change requests: DRAFT -> SUBMITTED -> IMPACT_ASSESSED -> APPROVED -> IMPLEMENTED -> VERIFIED -> CLOSED via `/compliance/change-control/*`. |
| **Multi-Standard Compliance Verifier** | **IMPLEMENTED** | Automated verification against IEC 62304, ISO 26262, DO-178C, EN 50128, 21 CFR Part 11 via `/compliance/verify`. |

### Not Yet Implemented (Remaining Gaps)

| Capability | Status | Impact |
|---|---|---|
| **PDF/Word Export** | NOT IMPLEMENTED | Document generation produces Markdown. PDF conversion requires external tooling (pandoc). |
| **Electronic Signatures** | NOT IMPLEMENTED | HMAC integrity verified but no e-signature workflow (OIDC/PKI). |
| **IQ/OQ/PQ Validation** | PARTIAL | Validation framework exists but test protocols need domain-specific content. |
| **Post-Market Surveillance** | NOT IMPLEMENTED | No adverse event tracking or PMCF/PMPF plan generation. |
| **MC/DC Structural Coverage** | NOT IMPLEMENTED | Required for DO-178C DAL A. No integration with coverage tools. |

---

## Per-Domain Compliance Coverage

### Medical Devices (IEC 62304 / ISO 14971 / FDA)

| Requirement | SAGE Coverage | Gap |
|---|---|---|
| Software Development Plan (IEC 62304 §5.1) | Template in `SRS.md` | No automated plan generation |
| Software Requirements (IEC 62304 §5.2) | LLM-assisted derivation | No formal review workflow |
| Software Architecture (IEC 62304 §5.3) | LLM-assisted design | No validation against requirements |
| Software Detailed Design (IEC 62304 §5.4) | Not covered | Manual process required |
| Software Unit Implementation (IEC 62304 §5.5) | Agent code generation | No traceability to design |
| Software Integration Testing (IEC 62304 §5.6) | pytest framework | No test plan linked to requirements |
| Software System Testing (IEC 62304 §5.7) | Playwright E2E tests | No formal V&V protocol |
| Software Maintenance (IEC 62304 §6) | **Change control workflow** | Full CR lifecycle implemented |
| SOUP Management (IEC 62304 §8.1.2) | **SOUP inventory generator** | Automated from dependency list |
| Risk Management (ISO 14971) | FMEA + FTA + **risk doc generation** | Mitigation tracking via change control |
| Electronic Records (21 CFR Part 11) | **HMAC hash chain + audit log** | Cryptographic integrity verified |
| Design Controls (21 CFR 820.30) | **Change control + traceability** | Full CR workflow with impact assessment |
| Requirements Traceability (§5.1.1) | **Bidirectional RTM** | Forward + backward links with coverage report |

**Overall IEC 62304 Coverage: ~70%** — Computation, traceability, change control, and document generation implemented. PDF export and e-signatures remain.

### Automotive (ISO 26262)

| Requirement | SAGE Coverage | Gap |
|---|---|---|
| ASIL Classification | **Full** — Exact ISO 26262 matrix | — |
| Hazard Analysis & Risk Assessment | FMEA + ASIL computation | No HARA document generation |
| Safety Requirements | Generated from hazards | No allocation to HW/SW |
| Functional Safety Concept | Not covered | Manual process |
| Technical Safety Concept | Not covered | Manual process |
| Software Safety Requirements | IEC 62304 Class via ASIL | No ISO 26262 Part 6 specifics |
| TARA (Cybersecurity) | Not covered | ISO/SAE 21434 not implemented |

**Overall ISO 26262 Coverage: ~45%** — ASIL classification, change management, traceability, and compliance verification implemented.

### Avionics (DO-178C)

| Requirement | SAGE Coverage | Gap |
|---|---|---|
| DAL Classification | Referenced in standards registry | No automated classification |
| Planning Process | Not covered | Manual process |
| Development Process | Agent-based code generation | No DO-178C process compliance |
| Verification Process | pytest framework | No MC/DC coverage analysis |
| Configuration Management | Git-based | No formal CM plan |
| Quality Assurance | Not covered | No DER/ODA workflow |

**Overall DO-178C Coverage: ~30%** — Standards registry, compliance verification, traceability, and change control. MC/DC coverage analysis not yet integrated.

### Railway (EN 50128 / IEC 61508)

| Requirement | SAGE Coverage | Gap |
|---|---|---|
| SIL Classification | **Full** — IEC 61508 thresholds | — |
| Safety Requirements Specification | Template-based | No formal derivation |
| Software Architecture | LLM-assisted | No formal methods |
| Software Design | Not covered | Manual process |
| Validation & Verification | pytest framework | No SIL-appropriate V&V |

**Overall EN 50128 Coverage: ~35%** — SIL classification, traceability, compliance verification, and change control. No formal methods or SIL-specific V&V.

### Clinical Decision Support (FDA CDS Guidance)

| Requirement | SAGE Coverage | Gap |
|---|---|---|
| 4-Criterion Classification | **Full** — Deterministic logic | Context may vary |
| Input Data Taxonomy | **Full** — Image/signal/pattern/discrete | — |
| Data Source Validation | **Full** — Provenance checking | — |
| Transparency Report | **Full** — Clinician-facing summary | Not FDA submission format |
| Automation Bias Assessment | **Full** — Risk scoring | No post-market monitoring |
| Clinical Limitations Disclosure | **Full** — Labeling content | Not in IFU format |
| Labeling | **Partial** — Content generated | Not FDA format |

**Overall CDS Coverage: ~70%** — Classification and assessment are strong. Document formatting and post-market features missing.

---

## How SAGE Ensures Compliance in Practice

### What SAGE Does Automatically

1. **Every agent proposal goes through HITL approval** — No AI-generated change executes without human review. This satisfies the fundamental principle of human oversight in regulated environments.

2. **Immutable audit trail** — Every decision (approval, rejection, analysis) is logged with trace IDs, timestamps, and actor identity. This provides the compliance record foundation.

3. **Rejection feedback compounds** — When a human rejects an agent proposal with feedback, that feedback is stored in vector memory and used to improve future proposals. This creates a measurable quality improvement loop.

4. **Per-solution isolation** — Each solution gets its own `.sage/` directory with isolated databases. No data leakage between domains.

5. **Functional safety computation** — FMEA, FTA, ASIL, SIL calculations are deterministic and standards-compliant. They produce correct numerical results.

### What Teams Must Do Manually

1. **Create regulatory documents** — SAGE generates JSON; teams must create Word/PDF submissions.
2. **Maintain traceability** — RTM must be manually maintained (use the template in `RTM.md`).
3. **Conduct formal reviews** — SAGE doesn't replace design review meetings or QA sign-off.
4. **Validate with domain experts** — LLM-generated requirements and architectures must be reviewed by qualified engineers.
5. **Implement electronic signatures** — For FDA submissions, teams need external signing infrastructure.
6. **Run IQ/OQ/PQ** — Validation protocols must be written and executed per-deployment.

---

## Roadmap to Production-Grade Compliance

### Phase 1: Document Generation (Q2 2026)
- PDF/Word export for regulatory documents
- FDA submission format templates
- EU Technical File generation

### Phase 2: Traceability Automation (Q3 2026)
- Requirement-to-test linking
- Coverage gap detection
- Change impact analysis

### Phase 3: Electronic Records (Q3-Q4 2026)
- Cryptographic audit log integrity (HMAC hash chain)
- Electronic signature workflow
- 21 CFR Part 11 compliance validation

### Phase 4: Validation Framework (Q4 2026)
- IQ/OQ/PQ protocol templates
- Automated test report generation
- Post-market surveillance integration

---

## Standards Reference

SAGE's standards registry covers 50+ standards across these domains:

| Domain | Standards |
|---|---|
| Medical Devices | IEC 62304, ISO 14971, IEC 82304, ISO 13485, FDA 21 CFR Part 11/820, EU MDR 2017/745 |
| Clinical Decision Support | FDA CDS Guidance (Jan 2026), EU AI Act |
| Automotive | ISO 26262, ISO/SAE 21434, UN ECE WP.29 |
| Avionics | DO-178C, DO-254, ARP4754A |
| Railway | EN 50128, IEC 61508, IEC 61511 |
| Nuclear | IEC 61513 |
| Space | ECSS-E-ST-40C |
| Defense | MIL-STD-882E |
| Industrial | IEC 61508, IEC 62443 |
| Data Privacy | GDPR, HIPAA |
| AI/ML | FDA AI/ML Guidance, EU AI Act, IMDRF AI/ML |

Each standard entry includes clause references, required artifacts, and risk classification criteria.

---

## API Endpoints for Compliance

```bash
# Functional Safety
POST /safety/fmea              # FMEA risk priority calculation
POST /safety/fta               # Fault tree analysis
POST /safety/asil              # ASIL classification (ISO 26262)
POST /safety/sil               # SIL classification (IEC 61508)
POST /safety/iec62304-class    # Software safety class
POST /safety/analysis          # End-to-end safety lifecycle

# Regulatory Assessment
GET  /regulatory/standards     # List all 50+ standards
POST /regulatory/assess        # Compliance assessment
POST /regulatory/gap-analysis  # Gap analysis
GET  /regulatory/checklist/{id}# Per-standard checklist
POST /regulatory/roadmap       # Submission roadmap
POST /regulatory/full-report   # Full compliance report

# CDS Compliance (FDA)
POST /cds/classify             # 4-criterion classification
POST /cds/transparency-report  # Clinician-facing summary
POST /cds/compliance-package   # Full CDS compliance package

# Audit & Governance
GET  /audit                    # Query audit log
GET  /proposals/pending        # Pending HITL proposals
POST /approve/{trace_id}       # Approve with feedback
POST /reject/{trace_id}        # Reject with learning
```

---

*SAGE Framework — MIT License — github.com/Sumanharapanahalli/SAGE*

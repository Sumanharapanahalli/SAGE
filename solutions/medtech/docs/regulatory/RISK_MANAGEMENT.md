# Risk Management Report
## SAGE[ai] — Autonomous Manufacturing Intelligence System
### ISO 14971:2019 Compliant

**Document ID:** SAGE-RM-001
**Version:** 2.0.0
**Status:** Approved
**Date:** 2026-03-11

---

## 1. Introduction

This Risk Management Report documents the risk analysis, evaluation, control, and residual risk assessment for the SAGE[ai] software system in accordance with **ISO 14971:2019** — Application of Risk Management to Medical Devices.

### 1.1 Scope
Risk management applies to all software components of SAGE[ai] that could influence the safety, efficacy, or regulatory compliance of medical device manufacturing operations, including:
- AI-generated analysis proposals and code changes
- Automated merge request creation and review
- Continuous monitoring and alert generation
- Audit trail integrity

### 1.2 Risk Management Process Overview
```
Hazard Identification → Risk Estimation → Risk Evaluation
        ↓                                        ↓
Risk Control Measures ←──────── Acceptable? ──► Document
        ↓
Residual Risk Assessment → Overall Residual Risk Evaluation
```

---

## 2. Risk Acceptability Criteria

### 2.1 Severity Levels
| Level | Severity | Definition |
|---|---|---|
| 5 | Catastrophic | Patient death or permanent serious injury due to bad firmware/code change |
| 4 | Critical | Serious device malfunction causing production halt or patient harm potential |
| 3 | Major | Significant quality/compliance issue; regulatory reportable event |
| 2 | Moderate | Minor device malfunction; correctable before release; no patient harm |
| 1 | Negligible | Inconvenience; no device impact; no patient harm |

### 2.2 Probability Levels
| Level | Probability | Approximate Frequency |
|---|---|---|
| 5 | Frequent | > 1 in 100 events |
| 4 | Probable | 1 in 100 to 1 in 1,000 |
| 3 | Occasional | 1 in 1,000 to 1 in 10,000 |
| 2 | Remote | 1 in 10,000 to 1 in 100,000 |
| 1 | Improbable | < 1 in 100,000 |

### 2.3 Risk Acceptability Matrix
| | **S1** | **S2** | **S3** | **S4** | **S5** |
|---|---|---|---|---|---|
| **P5** | Low | Medium | High | Critical | Critical |
| **P4** | Low | Medium | High | High | Critical |
| **P3** | Low | Low | Medium | High | High |
| **P2** | Acceptable | Low | Low | Medium | High |
| **P1** | Acceptable | Acceptable | Low | Low | Medium |

- **Acceptable:** No action required
- **Low:** Monitor; no immediate action
- **Medium:** Risk controls required
- **High:** Risk controls mandatory; residual risk must be re-evaluated
- **Critical:** Design change required; release blocker

---

## 3. Hazard Identification and Risk Analysis

### RISK-001: AI Hallucination Leading to Incorrect Code Patch

| Field | Value |
|---|---|
| **Hazard** | LLM generates an incorrect code patch that, if applied, introduces a latent defect in medical device firmware |
| **Hazardous Situation** | Engineer approves an AI-suggested patch without independent verification |
| **Harm** | Device malfunction; incorrect sensor readings; patient harm |
| **Initial Severity** | 5 (Catastrophic) |
| **Initial Probability** | 3 (Occasional — LLMs hallucinate ~5-15% of the time) |
| **Initial Risk** | **High** |
| **Control Measure 1** | Mandatory HITL gate: AI patch proposals require explicit human approval before application |
| **Control Measure 2** | All patches are proposals only (unified diff format); no auto-apply mechanism exists |
| **Control Measure 3** | Full audit trail with trace_id records the AI output and engineer's approval |
| **Control Measure 4** | MR review process with CI/CD pipeline verification before merge |
| **Residual Severity** | 5 |
| **Residual Probability** | 1 (Improbable — multiple human gates + CI/CD) |
| **Residual Risk** | **Low** |

---

### RISK-002: False Positive Alert Causing Production Disruption

| Field | Value |
|---|---|
| **Hazard** | MonitorAgent raises a false positive alert from Metabase/Teams polling |
| **Hazardous Situation** | Engineers halt production or initiate unnecessary corrective actions |
| **Harm** | Manufacturing downtime; resource waste; opportunity cost |
| **Initial Severity** | 2 (Moderate) |
| **Initial Probability** | 4 (Probable) |
| **Initial Risk** | **Medium** |
| **Control Measure 1** | Severity classification (RED/AMBER/GREEN) helps engineers triage |
| **Control Measure 2** | Root cause hypothesis provides context for decision-making |
| **Control Measure 3** | Reject & Teach feedback improves future accuracy via RAG |
| **Residual Severity** | 2 |
| **Residual Probability** | 3 |
| **Residual Risk** | **Low** |

---

### RISK-003: Audit Trail Corruption or Loss

| Field | Value |
|---|---|
| **Hazard** | SQLite audit database becomes corrupted or deleted |
| **Hazardous Situation** | Compliance audit trail is unavailable for regulatory inspection |
| **Harm** | Regulatory non-compliance; loss of 21 CFR Part 11 records; warning letter risk |
| **Initial Severity** | 4 (Critical) |
| **Initial Probability** | 2 (Remote) |
| **Initial Risk** | **Medium** |
| **Control Measure 1** | Append-only write pattern; no DELETE operations in codebase |
| **Control Measure 2** | Backup strategy documented in CONFIG_MGMT_PLAN.md |
| **Control Measure 3** | Database integrity checks in IQ/OQ tests |
| **Control Measure 4** | Separate audit DB from operational data |
| **Residual Severity** | 4 |
| **Residual Probability** | 1 |
| **Residual Risk** | **Low** |

---

### RISK-004: Unauthorized Access to AI Agent API

| Field | Value |
|---|---|
| **Hazard** | Unauthorized party calls `/analyze`, `/approve`, or `/mr/create` endpoints |
| **Hazardous Situation** | Malicious or accidental approval of harmful proposals |
| **Harm** | Incorrect code changes submitted to GitLab; compliance record pollution |
| **Initial Severity** | 3 (Major) |
| **Initial Probability** | 3 (Occasional) |
| **Initial Risk** | **Medium** |
| **Control Measure 1** | Deploy FastAPI behind VPN or internal network only |
| **Control Measure 2** | Add authentication middleware (API key or OAuth) before production |
| **Control Measure 3** | CORS restricted to known frontend origins in production |
| **Control Measure 4** | All actions audited with actor field |
| **Residual Severity** | 3 |
| **Residual Probability** | 1 |
| **Residual Risk** | **Low** |

---

### RISK-005: LLM Provider Unavailability

| Field | Value |
|---|---|
| **Hazard** | Gemini CLI (cloud) or Local Llama becomes unavailable |
| **Hazardous Situation** | Engineers cannot obtain AI analysis; manual workload increases |
| **Harm** | Manufacturing delays; missed error detections |
| **Initial Severity** | 2 (Moderate) |
| **Initial Probability** | 3 (Occasional) |
| **Initial Risk** | **Low** |
| **Control Measure 1** | Two configurable providers (cloud + air-gapped local) |
| **Control Measure 2** | Graceful error handling returns structured error responses |
| **Control Measure 3** | Manual analysis fallback process documented in SETUP.md |
| **Residual Severity** | 2 |
| **Residual Probability** | 2 |
| **Residual Risk** | **Acceptable** |

---

### RISK-006: AI Code Review Misses Safety-Critical Defect

| Field | Value |
|---|---|
| **Hazard** | DeveloperAgent marks an MR as `approved: true` but misses a safety-critical bug |
| **Hazardous Situation** | Engineer relies solely on AI review without independent human review |
| **Harm** | Defective code merged; device firmware defect; patient harm |
| **Initial Severity** | 5 (Catastrophic) |
| **Initial Probability** | 3 (Occasional) |
| **Initial Risk** | **High** |
| **Control Measure 1** | AI review is advisory only — human reviewer must independently review |
| **Control Measure 2** | ReAct loop checks pipeline status (CI/CD tests) before recommendation |
| **Control Measure 3** | Review result includes explicit `issues` list for human assessment |
| **Control Measure 4** | GitLab branch protection rules require ≥1 human approval |
| **Residual Severity** | 5 |
| **Residual Probability** | 1 |
| **Residual Risk** | **Low** |

---

### RISK-007: Data Privacy — Log Entry Contains PHI/PII

| Field | Value |
|---|---|
| **Hazard** | Manufacturing log entries sent to AI contain Protected Health Information |
| **Hazardous Situation** | PHI transmitted to cloud LLM (Gemini CLI) violates data protection regulations |
| **Harm** | HIPAA/GDPR violation; regulatory penalty; patient privacy breach |
| **Initial Severity** | 3 (Major) |
| **Initial Probability** | 2 (Remote — manufacturing logs typically don't contain PHI) |
| **Initial Risk** | **Low** |
| **Control Measure 1** | Process guidelines prohibit submitting PHI to the system |
| **Control Measure 2** | Air-gapped Local Llama option for sensitive environments |
| **Control Measure 3** | Training for all system users on data classification |
| **Residual Severity** | 3 |
| **Residual Probability** | 1 |
| **Residual Risk** | **Low** |

---

## 4. Overall Residual Risk Evaluation

| Risk ID | Description | Residual Risk |
|---|---|---|
| RISK-001 | AI patch hallucination | Low |
| RISK-002 | False positive alerts | Low |
| RISK-003 | Audit trail corruption | Low |
| RISK-004 | Unauthorized API access | Low |
| RISK-005 | LLM unavailability | Acceptable |
| RISK-006 | AI review misses defect | Low |
| RISK-007 | PHI in log entries | Low |

**Overall Residual Risk Conclusion:** All identified risks have been reduced to Low or Acceptable levels through implemented control measures. The overall residual risk of SAGE[ai] is judged to be **acceptable** for use in a medical device manufacturing support context, provided that:
1. All HITL gates are enforced operationally
2. The system is deployed on an internal network
3. AI outputs are treated as advisory inputs, not final decisions

---

## 5. Risk Management Review Schedule

| Review Trigger | Responsible Party |
|---|---|
| New software version release | Systems Engineering |
| New LLM provider or model | Systems Engineering + QA |
| Reported adverse event or near-miss | QA Manager |
| Annual periodic review | QA Manager |

---

*Document Owner: Systems Engineering / Quality Assurance*
*Next Scheduled Review: 2027-03-11*

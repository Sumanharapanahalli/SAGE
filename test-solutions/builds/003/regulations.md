# Regulatory Compliance — Telehealth Platform

**Domain:** medtech
**Solution ID:** 003
**Generated:** 2026-03-22T11:53:39.306857
**HITL Level:** strict

---

## 1. Applicable Standards

- **HIPAA**
- **HITECH**
- **HL7 FHIR**
- **SOC 2**

## 2. Domain Detection Results

- medtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 2 | SECURITY | Produce HIPAA Security Rule threat model: PHI data flow diagram, threat catalog, | Threat modeling, penetration testing |
| Step 3 | LEGAL | Draft legal documents: Terms of Service, Privacy Policy (HIPAA Notice of Privacy | Privacy, licensing, contracts |
| Step 4 | COMPLIANCE | Build HIPAA compliance framework: risk assessment (per 45 CFR §164.308(a)(1)), p | Standards mapping, DHF, traceability |
| Step 19 | REGULATORY | Prepare HIPAA compliance evidence package: completed risk assessment, policies a | Submission preparation, audit readiness |
| Step 20 | QA | Develop comprehensive QA test plan: test strategy, test cases for all critical c | Verification & validation |
| Step 22 | SYSTEM_TEST | Execute end-to-end system test suite: full patient journey (register→symptom che | End-to-end validation, performance |

**Total tasks:** 25 | **Compliance tasks:** 6 | **Coverage:** 24%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | HIPAA compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 2 | HITECH compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | HL7 FHIR compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 4 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |

## 5. Risk Assessment Summary

**Risk Level:** HIGH — Safety-critical domain requiring strict HITL gates

| Risk Category | Mitigation in Plan |
|--------------|-------------------|
| Patient/User Safety | SAFETY tasks with FMEA and hazard analysis |
| Data Integrity | DATABASE tasks with audit trail requirements |
| Cybersecurity | SECURITY tasks with threat modeling |
| Regulatory Non-compliance | REGULATORY + COMPLIANCE tasks |
| Software Defects | QA + SYSTEM_TEST + EMBEDDED_TEST tasks |

## 6. Agent Team Assignment

| Agent Role | Tasks Assigned | Team |
|-----------|---------------|------|
| developer | 10 | Engineering |
| regulatory_specialist | 3 | Compliance |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| data_scientist | 1 | Analysis |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This plan is impressively detailed in scope and correctly identifies most of the HIPAA compliance surface area — the threat model, BAA tracking, audit logging, RBAC design, and operational runbooks are all well-conceived. However, it has two critical showstoppers that would block a legal launch: (1) the AI symptom checker is almost certainly an FDA-regulated SaMD and no regulatory pathway is planned, and (2) the MIMIC-III training dataset cannot be legally used without IRB approval and a PhysioNet DUA, and the trained model may inherit PHI restrictions. Beyond the legal blockers, several technical decisions will cause serious production failures: pgcrypto field-level encryption on queryable PHI columns will make the database unusable at scale, the Twilio 'E2E' video claim is architecturally false, and Surescripts certification is a 6–18 month external dependency being treated as a sprint task. The plan also has no Anthropic BAA for LLM usage, no FDA SaMD pathway, no patient identity matching strategy for multi-EHR sync, and no PCI-DSS scoping for billing. For a regulated medical domain, I would not approve this plan for build without resolving the FDA SaMD question, replacing MIMIC-III, redesigning the PHI encryption layer, and adding the LLM provider BAA. Fundamental rework is needed on 4–5 critical items before this is production-credible.

### Flaws Identified

1. MIMIC-III is listed as a training dataset in Step 14 — this dataset contains real PHI and requires PhysioNet credentialing, a signed Data Use Agreement, and likely IRB approval. A model trained on it may itself be considered PHI-derived under HIPAA. This is not a data science task you can put in a sprint.
2. FDA Software as a Medical Device (SaMD) classification is entirely absent. An AI triage system returning 'emergency|urgent|routine' recommendations is almost certainly a Class II medical device requiring 510(k) clearance or De Novo classification under FDA 21 CFR Part 820. Launching without this is a federal enforcement risk, not just a compliance gap.
3. Twilio Video Group Rooms route media through Twilio's infrastructure — media is decrypted on their servers. Calling this 'E2E SRTP' in the acceptance criteria is technically false. True E2E requires Twilio Peer-to-Peer Rooms (limited to 2 participants, no recording) or a different architecture. The BAA covers this legally but the 'E2E' claim in your security model is wrong.
4. pgcrypto AES-256 field-level encryption on PostgreSQL (Step 6) makes encrypted PHI columns unsearchable and non-indexable. Patient search, appointment lookups, and FHIR queries that join across encrypted fields will be catastrophically slow at scale. The plan has no mitigation (envelope encryption with separate search tokens, deterministic encryption for lookup fields, or a KMS-managed approach).
5. Surescripts network certification takes 6–18 months minimum, requires extensive conformance testing, a separate legal agreement, and Surescripts must approve your use case. Step 12 treats this as a backend sprint task. This single dependency could block the entire e-prescription feature for over a year.
6. Epic and Cerner production API access (not sandbox) requires going through Epic App Orchard or Cerner Code programs — multi-month review, legal agreements, and technical certification. Step 13 acceptance criteria only require one sandbox to work. The gap between sandbox and production EHR access is where the feature actually breaks.
7. Sending patient-described symptoms to Claude (Anthropic) via API requires Anthropic to sign a Business Associate Agreement. Anthropic offers BAAs for Enterprise tier only. This is not mentioned anywhere in the plan. Without a signed BAA, transmitting symptom descriptions that could constitute PHI to the LLM is a HIPAA violation.
8. Step 14's de-identification before LLM transmission ('PHI inputs anonymized') is described as if it is a solved problem. De-identification to HIPAA Safe Harbor standard (18 identifiers removed) or Expert Determination is technically non-trivial — age >89, rare conditions, geographic data at zip-code level, and combinations of quasi-identifiers all fail naive scrubbing. A flawed de-identification layer is worse than no de-identification because it creates false compliance confidence.
9. The plan has no Master Patient Index (MPI) or patient matching strategy. When syncing from multiple EHRs (Epic, Cerner, Athena), you will inevitably receive duplicate patient records. Without a probabilistic matching layer, you will create duplicate charts, merge PHI incorrectly, or route prescriptions to the wrong patient.
10. Provider licensing validation at the point of care is mentioned only as 'NPI lookup and state license validation' in Step 10. In US telehealth law, the provider must be licensed in the state where the PATIENT is physically located at the time of the visit — not where the provider is licensed. Real-time license verification against 50 state medical board databases (most of which have no public API) is a separate engineering problem that is not scoped.

### Suggestions

1. Add a Step 0 (pre-build): FDA SaMD risk classification workshop. Get an FDA regulatory consultant to classify the symptom checker before writing a line of ML code. If it needs 510(k), that process runs in parallel with development and takes 6–12 months minimum.
2. Replace MIMIC-III with the publicly available Symptom2Disease dataset, NHANES public-use files, or proprietary clinical NLP datasets (Infermedica API, Isabel DDx) that come with commercial licenses and no PHI. If fine-tuning is required, use a HIPAA-eligible ML platform (AWS SageMaker with BAA) and synthetic clinical data.
3. For field-level encryption, adopt envelope encryption: store an encrypted data key per row in the database, use AWS KMS to decrypt the data key at application layer, and keep plaintext only in application memory. This preserves indexability for non-sensitive fields while protecting PHI. Do not use pgcrypto for queryable columns.
4. Replace SMS MFA with TOTP-only or hardware security keys (FIDO2/WebAuthn) for provider and admin accounts. SMS OTP is deprecated in NIST SP 800-63B for AAL2 and higher — HIPAA auditors increasingly flag it. Keep SMS as a fallback for patients only.
5. Scope the Surescripts integration as a Phase 2 feature with a realistic 12-month runway. For MVP launch, implement e-prescribing for non-controlled substances only via a simpler path (DrFirst or DoseSpot, which offer faster certification than direct Surescripts integration), then upgrade.
6. Add a patient matching service (Step 6.5): implement a probabilistic MPI using a library like Splink or a commercial service (Verato, MPI from CommonWell) before building the EHR sync layer. This prevents chart fragmentation at scale.
7. Step 9 should remove the 90-day mandatory password rotation requirement — NIST SP 800-63B explicitly recommends against periodic rotation without evidence of compromise. Replace with breach-detection-triggered rotation and long minimum length (16+ chars) with no complexity rules.
8. Add a legal step to obtain Anthropic Enterprise BAA before any PHI touches the LLM layer. Build the symptom checker's prompt pipeline to work with any HIPAA-BAA-covered LLM provider (AWS Bedrock Claude, Azure OpenAI) as primary, with Anthropic direct as secondary only after BAA is in place.
9. For EHR integrations, explicitly split acceptance criteria into sandbox acceptance (Step 13) and production go-live (post-launch backlog). Do not put Epic/Cerner production API access on the critical path for launch — it will slip.
10. Add a Step 3.5: state telehealth prescribing restrictions enforcement layer. The legal document (Step 3) identifies restrictions — but someone has to build the runtime enforcement that blocks a Florida-licensed provider from prescribing to a patient in Texas if that combination is prohibited. This needs a maintained policy rules database, not just a legal doc.

### Missing Elements

1. FDA SaMD classification and regulatory strategy for the AI symptom checker — not optional, not deferrable after launch.
2. Anthropic (or equivalent LLM provider) BAA procurement step before any symptom checker development begins.
3. PCI-DSS scoping and compliance path — Step 17 mentions billing and claims management. If the platform processes copayments or subscription fees directly, PCI-DSS applies and is not in the compliance scope at all.
4. Patient right of access implementation (HIPAA 45 CFR §164.524) — patients have a right to receive their PHI within 30 days of request. The plan has a health records viewer but no formal 'patient data export / portability' workflow with the defined SLA.
5. Minimum necessary enforcement at the API response layer — RBAC prevents wrong-role access, but minimum necessary requires that even authorized users get only the PHI fields required for their task. No plan for this at the API design level.
6. HIPAA Notice of Privacy Practices delivery acknowledgment tracking — the NPP must be provided at first service delivery and acknowledgment tracked. This is a data model and workflow gap.
7. Business continuity plan distinct from DR runbook — HIPAA §164.308(a)(7) requires a documented contingency plan covering emergency mode operations, not just RTO/RPO targets.
8. Cross-region disaster recovery architecture — Step 7 provisions a single-region VPC. If the entire AWS region goes down, there is no failover. For 99.9% uptime SLA and 24h RTO, a warm standby in a second region is required.
9. Workforce HIPAA training delivery platform and completion tracking system — Step 24 says 'completion certificate with date' but no platform is specified. LMS selection and integration with HR systems is not scoped.
10. Legal review of AI-generated medical recommendations liability — the plan has AI consent forms but no framework for limiting liability when the symptom checker output contributes to an adverse event. This is a product liability question that needs legal opinion before launch, not after.

### Security Risks

1. INDIRECT OBJECT REFERENCE on FHIR endpoints: FHIR resource IDs (Patient/123, Encounter/456) are typically sequential or guessable. Without per-request RBAC verification at the resource ID level (not just at the route level), a patient who discovers another patient's encounter ID can request their PHI. Step 10 mentions auth middleware but does not specify IDOR-specific controls on FHIR resource access.
2. LLM prompt injection in symptom checker: Patient-supplied symptom descriptions are used directly in LLM prompts. A malicious user can attempt to exfiltrate system prompts, override safety guardrails, or extract other users' session data if sessions share context. The safety guardrails in Step 8 do not mention prompt injection defenses.
3. WebSocket signaling server (Step 11) is a high-value attack target: if an attacker can inject a malicious SDP offer into the signaling channel, they can redirect video streams or conduct a man-in-the-middle on video calls. WSS alone is insufficient — the signaling messages must be authenticated and bound to the session tokens of the specific patient-provider pair.
4. Terraform state file contains all infrastructure secrets and resource IDs — storing it in S3 with state locking is correct, but the plan does not specify IAM policies restricting who can read the state file. A developer with S3 read access to the state bucket can extract KMS key ARNs, RDS connection strings, and Cognito pool IDs.
5. KMS key policy misconfiguration is the most common cause of HIPAA breaches in AWS environments — the plan specifies KMS CMK creation but does not define key policy: who can administer the key, who can use it, and critically, whether key deletion is protected. An admin with kms:ScheduleKeyDeletion can destroy all encrypted PHI irreversibly.
6. Surescripts network integration creates a direct pharmaceutical supply chain attack surface — a compromised provider account that can submit prescriptions to Surescripts is a high-value target for drug diversion. The DEA EPCS two-factor requirement is noted, but the audit trail for detecting anomalous prescribing patterns (same provider, many controlled substances, many patients in short time) is not specified.
7. EHR SMART on FHIR OAuth token storage in the patient portal: SMART launch tokens with offline_access scope can be used to continuously pull PHI from the EHR. If these tokens are stored in browser localStorage (common React pattern), XSS vulnerabilities become PHI exfiltration vulnerabilities. Token storage strategy is not specified.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.306908
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

# Regulatory Compliance — Clinical Trial Manager

**Domain:** medtech
**Solution ID:** 006
**Generated:** 2026-03-22T11:53:39.308060
**HITL Level:** strict

---

## 1. Applicable Standards

- **21 CFR Part 11**
- **ICH GCP**
- **HIPAA**
- **GDPR**

## 2. Domain Detection Results

- medtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 2 | REGULATORY | Produce a regulatory standards mapping document for 21 CFR Part 11, ICH E6 GCP,  | Submission preparation, audit readiness |
| Step 3 | SECURITY | Produce a threat model (STRIDE) and security architecture plan for the clinical  | Threat modeling, penetration testing |
| Step 4 | COMPLIANCE | Create the Design History File (DHF) skeleton, risk matrix (ISO 14971-style adap | Standards mapping, DHF, traceability |
| Step 5 | LEGAL | Draft terms of service, data processing agreements (DPA), privacy policy (HIPAA  | Privacy, licensing, contracts |
| Step 19 | QA | Design and execute the quality assurance test plan: unit test coverage targets,  | Verification & validation |
| Step 21 | SYSTEM_TEST | Execute system-level integration testing: end-to-end clinical trial lifecycle si | End-to-end validation, performance |
| Step 24 | SECURITY | Execute security validation: penetration test against staging environment (OWASP | Threat modeling, penetration testing |
| Step 25 | COMPLIANCE | Execute IQ/OQ/PQ validation protocols: Installation Qualification (verify system | Standards mapping, DHF, traceability |
| Step 26 | REGULATORY | Prepare regulatory submission package: compile DHF summary for FDA review, prepa | Submission preparation, audit readiness |

**Total tasks:** 27 | **Compliance tasks:** 9 | **Coverage:** 33%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | 21 CFR Part 11 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | ICH GCP compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | HIPAA compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 4 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |

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
| developer | 11 | Engineering |
| regulatory_specialist | 4 | Compliance |
| safety_engineer | 2 | Compliance |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| business_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 61/100 (FAIL) — 1 iteration(s)

**Summary:** This is a technically ambitious and well-structured plan that demonstrates genuine familiarity with clinical trial processes, 21 CFR Part 11, and HIPAA. The dependency graph is logical, the acceptance criteria are specific, and the inclusion of DHF, IQ/OQ/PQ, and HITL gates shows regulatory awareness. However, it has several production-blocking gaps that would cause real-world failure before FDA inspection: MedDRA requires a paid MSSO license that is not addressed anywhere; actual electronic FDA submissions require ESG registration and E2B(R3) XML format, not FDA-3500A field population; IRB workflow is completely absent despite IRB being listed as a stakeholder; and data lock procedures are missing from every layer of the design. The cryptographic audit trail and pgcrypto encryption designs are conceptually correct but incomplete — the key management lifecycle between Vault and the database is the single most dangerous unresolved dependency in the security architecture. For a regulated-domain build targeting production clinical use, this plan needs the missing modules (IRB, protocol deviations, data lock, ESG registration) designed and the key management architecture resolved before implementation begins. As an MVP for internal validation and stakeholder demonstration, it is solid. As a submission-ready clinical system, it will fail at the first FDA 21 CFR Part 11 inspection on audit trail forensic integrity and at first contact with FDA's actual electronic submission infrastructure.

### Flaws Identified

1. MedDRA licensing is entirely absent from the plan. MedDRA terminology requires a separate paid subscription agreement with MSSO (~$10K+/year for commercial use). The UMLS API in Step 11 provides NLM-licensed content, not MedDRA. These are different systems. Step 5 (Legal) never addresses MedDRA licensing, which is a hard blocker for deployment.
2. FDA Electronic Submissions Gateway (ESG) registration is missing. Step 13 specifies a POST /submit-to-fda endpoint, but actual electronic regulatory submissions require prior FDA ESG account registration and validation testing with FDA's test environment. This is a multi-week process with FDA that cannot be coded around.
3. E2B XML format for adverse event reporting is missing. Step 11 says 'populate FDA-3500A fields' but electronic SAE submissions to FDA MedWatch require ICH E2B(R3) XML format, not PDF form population. FDA-3500A is the paper form equivalent. Building the wrong output format means the submission module cannot actually submit electronically to FDA.
4. IRB (Institutional Review Board) is listed as a stakeholder in Step 1 but never appears in any subsequent design step. IRB initial submissions, protocol amendments, continuing review reminders, and IRB approval tracking are core CTMS functions. This is an entire missing module.
5. Protocol deviation and violation tracking is absent. Protocol deviations are one of the most common data entry workflows in a CTMS and a primary FDA inspection focus area. No module, no schema tables, no UI component anywhere in 27 steps.
6. pgcrypto encryption key management lifecycle is undesigned. Step 7 specifies column-level AES-256 via pgcrypto, Step 22 specifies HashiCorp Vault for secrets — but there is no design for how Vault manages pgcrypto keys, how they are rotated without decrypting and re-encrypting all PHI rows, or what happens during key rotation when trial data must remain accessible. This is a production-blocking gap in a HIPAA system.
7. Audit log cryptographic chain seed and key management is undefined. Step 7 specifies SHA-256 chaining but does not address: what seeds the first hash, where the chain key is stored, how chain verification works after Vault rotation, and how a backup-restored database proves chain continuity. Without this, the 'immutable audit trail' claim cannot be demonstrated to FDA.
8. SMART on FHIR authorization is not specified. All FHIR endpoints are defined throughout the plan but Step 3 security only mentions 'HL7 FHIR API security' generically. SMART on FHIR (OAuth2 + SMART scopes) is the industry standard for FHIR API authorization and is expected by any health system integration partner. Without it, the FHIR layer is not interoperable.
9. PQ protocol specifies a '90-day data integrity' test in Step 25 but the plan timeline implies this runs concurrently with other steps. A 90-day PQ observation period is calendar time — it adds a mandatory 3-month gate before DHF closure that is completely unaccounted for in the dependency graph.
10. GAMP 5 Computer System Validation (CSV) approach is never mentioned. FDA expects pharmaceutical software to follow GAMP 5 guidelines. The plan uses IQ/OQ/PQ (correct) but does not reference GAMP 5 category classification (this system is Category 4 or 5), supplier assessment documentation, or the CSV master plan — all expected artifacts at FDA inspection.
11. Data lock and database freeze procedures are entirely missing. Every clinical trial requires a formal data lock at study close-out. No module, no workflow, no schema support for locking records to prevent post-lock modification. This is a regulatory requirement per ICH E6 GCP.
12. The SAGE proposal_store dependency in Step 14 introduces an unvalidated external system into the 21 CFR Part 11 compliance boundary. If the CTMS uses SAGE's proposal store for agent approvals, FDA requires that SAGE itself be validated as part of the CTMS validation package. This substantially expands the validation scope and may be impractical.
13. 21 CFR 312.32 IND safety reporting timelines are collapsed into a single '15-day' rule. Unexpected fatal or life-threatening SADRs require 7-day telephone/fax notification to FDA followed by a written 15-day report. The plan only models the 15-day written report. Missing the 7-day expedited path is a regulatory violation.
14. The SaMD / 510(k) regulatory pathway analysis in Step 2 may be entirely misdirected effort. A CTMS used purely for trial management and data capture is not typically an FDA-regulated medical device. Unless the system includes clinical decision support that influences diagnosis/treatment, FDA regulation as SaMD does not apply. Investing regulatory effort in a De Novo/510(k) analysis for a standard CTMS misallocates resources and creates false compliance obligations.
15. Step 20 sets an 8-minute CI test suite target for a system requiring real PostgreSQL, Playwright E2E across five modules, Hypothesis property tests with 10,000 trial simulations, and 90% coverage. This is unrealistic by a factor of 3-4x. CI pipelines for systems of this complexity typically run 25-40 minutes. An unrealistic target will be abandoned or gamed.

### Suggestions

1. Add a Step 1.5 or sub-task in Step 5 (Legal) explicitly for MedDRA MSSO licensing procurement and UMLS license verification. Identify whether to use UMLS API (free but NLM-licensed) or a self-hosted MedDRA browser (requires separate MSSO commercial license). This must be resolved before Step 11 can be implemented.
2. Add FDA ESG registration as a prerequisite task before Step 13. Include FDA test environment validation testing in the acceptance criteria for the submissions module. Budget 4-8 weeks for FDA ESG onboarding.
3. Replace FDA-3500A field population in Step 11 with ICH E2B(R3) XML generation. The E2B(R3) schema is publicly available from ICH. This is the actual electronic submission format for MedWatch gateway submissions.
4. Add an IRB module (Steps 9-13 equivalent scope) covering: IRB submission package assembly, continuing review reminders, IRB approval upload/versioning, and IRB correspondence tracking. Add IRB workflow to UX Step 6.
5. Add protocol deviation/violation module with: deviation capture form, severity classification (minor/major), CAPA linkage, investigator notification, and sponsor reporting. This likely requires its own backend step between Steps 9-11.
6. Design the pgcrypto + Vault integration explicitly: Vault stores the AES-256 key, application retrieves it at startup via Vault AppRole auth, pgcrypto functions receive the key as a parameter. Define the key rotation procedure: dual-write period, re-encryption job, key version tagging on encrypted columns.
7. Specify SMART on FHIR in Step 3 security architecture and Step 8 scaffold. Define FHIR server authorization scopes per resource type (e.g., patient/*.read for sponsor, patient/*.write for coordinator). Use an established FHIR server (HAPI FHIR or Medplum) rather than building FHIR endpoints from scratch in FastAPI.
8. Add GAMP 5 CSV master plan as a deliverable in Step 4 (Compliance). Classify the system as GAMP Category 5 (custom software). Add supplier qualification documentation for PostgreSQL, MinIO, Redis, and any third-party libraries used in validated workflows.
9. Explicitly design data lock functionality: a database-level lock flag per trial, a lock/unlock workflow requiring QA Lead e-signature, and post-lock modification prevention at the API layer with exception handling for data corrections (which require documented deviation from lock).
10. Remove or scope-gate the SaMD/510(k) analysis in Step 2. Add an explicit decision gate: if the system includes no clinical decision support algorithms, document the rationale for non-device classification and skip 510(k) preparation. This saves significant regulatory overhead.
11. Split the 8-minute CI target in Step 20 into tiers: fast suite (unit + static analysis, <5 min, runs on every PR), full suite (integration + E2E, <30 min, runs on merge to main), nightly suite (Hypothesis property tests, performance smoke, no time gate). This is the standard pattern for systems of this complexity.
12. Add a dedicated 'System Close-Out' task covering: data lock procedures, final audit log export, long-term archive format (HL7 FHIR Bundle export), and the 15-year record retention requirement for clinical trial data under 21 CFR 312.62.

### Missing Elements

1. MedDRA MSSO licensing agreement and procurement workflow
2. FDA Electronic Submissions Gateway (ESG) registration and test environment validation
3. ICH E2B(R3) XML format for electronic adverse event reporting to FDA
4. IRB workflow module: submission package, continuing review, approval tracking
5. Protocol deviation and violation tracking module
6. Data lock and study close-out procedures
7. pgcrypto encryption key lifecycle design (Vault integration path, rotation procedure, key versioning on columns)
8. SMART on FHIR authorization framework specification
9. GAMP 5 CSV Master Plan and supplier qualification documentation
10. 7-day IND safety report pathway for fatal/life-threatening unexpected SADRs (21 CFR 312.32(c)(1))
11. DSMB/DSMC formal data access and reporting interface (Step 14 mentions dsmc_notification but no module exists)
12. HL7 FHIR server selection decision — building FHIR endpoints in FastAPI from scratch vs. using validated FHIR server
13. Long-term archive format and 15-year data retention strategy per 21 CFR 312.62
14. IND Annual Safety Report module (21 CFR 312.33) — separate from SAE expedited reports
15. Study close-out and database lock workflow
16. Audit log chain verification endpoint and forensic recovery procedure post-backup-restore

### Security Risks

1. pgcrypto key in environment variable or config file: if Vault integration is not explicitly implemented, the AES-256 key will likely end up hardcoded or in an env var, creating a HIPAA Technical Safeguard failure and an encryption-at-rest control that is trivially bypassed by anyone with shell access.
2. FHIR endpoints without SMART on FHIR authorization: without FHIR-native OAuth2 scopes, any authenticated user with a valid session token could potentially query any FHIR resource type. Role-based filtering at the application layer (noted in Step 9) is insufficient if the FHIR base URL is accessible without resource-level scope enforcement.
3. Audit log chain seed exposure: if the SHA-256 chain hash seed is stored in the same database as the audit log (the default naive implementation), an attacker with DB write access can reconstruct a valid chain for tampered records. The seed must be stored externally (Vault) and the verification algorithm must be documented as part of the security architecture.
4. PKI certificate rotation during active trial: revoking and reissuing PKI certificates while a trial has in-flight e-signatures requires a certificate archive/escrow mechanism. If old certificates are revoked without an archive, previously signed records will fail verification. This is not addressed in the certificate rotation runbook (Step 23).
5. MinIO HIPAA compliance boundary is undefined: MinIO is not inherently HIPAA-compliant. The plan must specify whether MinIO is self-hosted or cloud-hosted, which cloud provider holds the BAA, and how MinIO bucket encryption keys are managed separately from application-layer encryption.
6. Redis session store without TLS and at-rest encryption: Redis 7 in Docker Compose is configured in plaintext by default. Session tokens stored in Redis are PHI-adjacent — a compromised Redis instance allows session hijacking for any active user. TLS and Redis AUTH with strong passwords must be enforced from Day 1, not added later.
7. SAGE proposal store as unvalidated system in compliance boundary: if agent proposals requiring e-signatures flow through SAGE's SQLite proposal store, that store becomes part of the 21 CFR Part 11 audit trail. SQLite is not designed for multi-process concurrent writes in a production environment and has no row-level access controls — this is a compliance risk if SAGE's store handles any approved regulatory action records.
8. Randomization allocation table write-once constraint enforcement: Step 10 specifies 'DB constraint + service layer check' for allocation immutability but does not specify REVOKE UPDATE/DELETE on the allocation table at the database role level. A service layer check alone is insufficient — a developer with DB credentials or a compromised service account can still modify allocations. Database-level REVOKE is the only reliable control.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.308102
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

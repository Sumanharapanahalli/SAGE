# Regulatory Compliance — Ehr Interop Gateway

**Domain:** medtech
**Solution ID:** 009
**Generated:** 2026-03-22T11:53:39.309292
**HITL Level:** strict

---

## 1. Applicable Standards

- **ONC Certification**
- **HL7 FHIR**
- **HIPAA**
- **HITECH**

## 2. Domain Detection Results

- medtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 2 | REGULATORY | Map product to ONC Health IT Certification Program requirements (21st Century Cu | Submission preparation, audit readiness |
| Step 3 | COMPLIANCE | Draft HIPAA/HITECH compliance framework: PHI data flow inventory, Business Assoc | Standards mapping, DHF, traceability |
| Step 4 | SECURITY | Produce threat model (STRIDE), PHI threat landscape analysis, penetration test p | Threat modeling, penetration testing |
| Step 5 | LEGAL | Draft Terms of Service, Data Processing Agreement (DPA), Privacy Policy, open-so | Privacy, licensing, contracts |
| Step 24 | QA | Produce QA test plan: test case design for all translation scenarios, EHR connec | Verification & validation |
| Step 25 | SYSTEM_TEST | Execute end-to-end integration test suite against all three EHR sandboxes: Epic  | End-to-end validation, performance |
| Step 26 | SECURITY | Execute security assessment: penetration test (OWASP API Top 10), PHI exfiltrati | Threat modeling, penetration testing |
| Step 27 | COMPLIANCE | Produce ONC certification evidence package: Inferno test results, USCDI conforma | Standards mapping, DHF, traceability |
| Step 30 | REGULATORY | Prepare and submit ONC certification application to ONC-ACB (e.g., Drummond Grou | Submission preparation, audit readiness |

**Total tasks:** 30 | **Compliance tasks:** 9 | **Coverage:** 30%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | ONC Certification compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | HL7 FHIR compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | HIPAA compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 4 | HITECH compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 13 | Engineering |
| regulatory_specialist | 6 | Compliance |
| ux_designer | 2 | Design |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| business_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 58/100 (FAIL) — 1 iteration(s)

**Summary:** This is one of the more thorough build plans I've seen for a healthcare interoperability product — the regulatory sequencing is thoughtful, the standards coverage is accurate, and the acceptance criteria are specific enough to be testable. However, it contains a load-bearing architectural contradiction that invalidates the performance requirements: you cannot run an LLM review_and_critique loop on every message translation and achieve 500 messages/second throughput. These two commitments are physically incompatible and one must go. Beyond this, the plan carries three serious risks that would likely block ONC certification or cause a PHI breach in production: a custom-built SMART authorization server (replace with Keycloak), absence of MLLP/TLS negotiation strategy with real hospital IT departments (this alone kills production timelines), and Z-segment ignorance across all three EHR connectors (data loss in every real-world message). For a regulated system requiring ONC certification, I score this 58 — impressive in scope, but the performance/agent contradiction and the custom auth server decision need to be resolved before any development work begins, and the ONC-ACB engagement must start now, not at step 30.

### Flaws Identified

1. FUNDAMENTAL CONTRADICTION — review_and_critique LLM loop (step 12) on every translation is irreconcilable with the 500 msg/sec throughput target (step 25). A single LLM inference call takes 1-10 seconds minimum. Three refinement cycles per message means the agent loop alone consumes 3-30 seconds per message. You cannot do 500/sec with this architecture. One of these requirements must be dropped or the critic agent must be a deterministic rule engine, not an LLM.
2. CUSTOM SMART AUTH SERVER IS A CRITICAL SECURITY RISK — step 17 says 'Authlib or custom JOSE implementation' for a PHI-bearing OAuth2+SMART server. Custom JOSE in healthcare is how PHI breaches happen. Authlib is a library, not a hardened OAuth server. You need Keycloak + SMART on FHIR plugin, or Auth0, or Okta, with FHIR-specific scopes pre-validated. Rolling your own JOSE for ePHI is malpractice.
3. MLLP TRANSPORT SECURITY GAP — step 9 defines MLLP on port 2575 and step 4 mandates TLS 1.3 minimum for all PHI transmission paths, but MLLP over plain TCP is the default in every real-world HL7 v2 deployment. Getting Epic, Cerner, and Allscripts hospital IT to configure MLLP/TLS (not standard) adds months of negotiation. The plan has no fallback and no mention of VPN tunnels as an alternative. This will block production go-live.
4. VSAC/TERMINOLOGY LICENSING NOT HANDLED — step 10 references a 'local VSAC snapshot' for LOINC, SNOMED CT, RxNorm, UCUM, ICD-10 lookups. SNOMED CT US Edition requires an NLM UMLS license (annual renewal, usage restrictions). VSAC access requires NLM credentials. Step 5 (Legal) mentions HL7 licensing but omits NLM/UMLS licensing entirely. Using SNOMED CT commercially without resolving this is an IP violation.
5. ONC CERTIFICATION SCOPE UNDERSTATED — step 30 lists only 3 criteria: §170.315(g)(10), (d)(1), (d)(2). A standalone interoperability gateway seeking ONC certification as a 'Health IT Module' under the 21st Century Cures Act must also address: (b)(1) transitions of care, (e)(1) view/download/transmit, (g)(6) consolidated CDA creation, and potentially (b)(2)/(b)(3) clinical information reconciliation depending on how the product is positioned. Three criteria will not get you a CHP.
6. ONC-ACB QUEUE TIME NOT ACCOUNTED FOR — step 30 is sequential and positioned as the final step. Drummond Group and ICSA Labs have 6-12 month backlogs for testing slots. Pre-submission engagement with the ONC-ACB should start at step 2, not step 30. Projects that treat ONC submission as a late-stage event routinely miss product launch deadlines by 12+ months.
7. Z-SEGMENT CUSTOMIZATION COMPLETELY IGNORED — step 9 handles HL7 v2 segments (MSH, PID, PV1, OBX, etc.) but Epic, Cerner, and Allscripts all use proprietary Z-segments (ZEP, ZPI, ZCE, etc.) that carry clinically critical data not in standard segments. Ignoring Z-segments means data loss on every Epic/Cerner/Allscripts message. This is a known failure mode for HL7 v2 gateway projects.
8. MLLP PERSISTENT CONNECTION MANAGEMENT ABSENT — the plan has no specification for MLLP connection pooling, reconnection backoff, message queuing on disconnect, or duplicate detection (MLLP has no built-in idempotency). In production, EHR MLLP endpoints drop connections during maintenance windows. Without reconnection logic and sequence number tracking, messages are silently lost.
9. ALLSCRIPTS/VERADIGM FRAGMENTATION UNDERESTIMATED — step 15 treats Allscripts as a monolithic integration target. Allscripts (now Veradigm) has Professional EHR, TouchWorks, Enterprise EHR, and Sunrise — each with different API surface areas, different versions of Unity API, and different MedBridge configurations. Unity v7.5 EOL timeline is unclear post-rebranding. 'Allscripts' is not one integration; it's 4+ distinct integrations.
10. AUDIT LOG WRITE THROUGHPUT NOT VALIDATED — step 16 requires 4+ TimescaleDB writes per message (received, translation_started, translation_completed, delivered) with nanosecond timestamps and hash chain computation. At 500 msg/sec that is 2,000+ sequential writes/sec to TimescaleDB with cryptographic dependency chaining (each row must complete before the next can start). The hash chain requirement makes parallelization impossible. This will be the bottleneck, not CPU.

### Suggestions

1. Replace the LLM review_and_critique loop on the hot path with a deterministic FHIR validator (HAPI FHIR validator is the gold standard, runs in-process in milliseconds). Reserve the LLM critic for async quality sampling — run it on 1-5% of messages post-delivery, not inline. This resolves the performance/accuracy contradiction without sacrificing quality.
2. Use Keycloak 23+ with the keycloak-fhir-mapper extension instead of building a SMART auth server. It has SMART App Launch 2.0 support, PKCE, JWKS, and token introspection out of the box. Add this to the infrastructure stack in step 21 and reference it in step 17.
3. Add a dedicated 'EHR Integration Profiling' step before step 13 that documents vendor-specific Z-segment catalogs, version matrices, and non-standard extension inventories for each target EHR. This should be negotiated with integration engineers at each vendor's partner portal.
4. Engage ONC-ACB (Drummond Group) for a pre-submission consultation immediately after step 2. Add a step 2.1 'ONC-ACB Pre-Submission Engagement' that documents the product's certification path, criteria scope, and testing schedule. This is the single highest-impact scheduling change.
5. For MLLP resilience, add a step specifying message queueing middleware (RabbitMQ or Kafka) between the MLLP listener and the translation engine. MLLP receives and ACKs; the queue handles retry, deduplication (MSH-10 control ID as idempotency key), and backpressure. This is industry-standard architecture for HL7 v2 at scale.
6. Resolve NLM UMLS licensing in step 5 (Legal). The UMLS Metathesaurus license is free but requires annual attestation and restricts redistribution. If the product ships with embedded SNOMED CT or RxNorm data, the deployment model (SaaS vs. on-prem) affects license compliance. This needs explicit legal review.
7. Add mTLS certificate lifecycle management to step 4 and step 21: automated certificate rotation (cert-manager in Kubernetes), OCSP stapling, and a certificate revocation procedure for compromised EHR connection credentials. Without this, you will have production outages when certificates expire.
8. Add explicit MLLP/TLS requirement negotiation to each EHR connector step (13, 14, 15). Include a fallback path: IPSec VPN tunnel from EHR to gateway DMZ when the EHR cannot support MLLP/TLS natively. Document the network topology requirement in the integration guide (step 29).
9. The CDA 'semantic equivalence' acceptance criterion in step 11 is too strong for a first build. C-CDA round-trips lose information at the nullFlavor/originalText/reference boundaries. Replace 'semantically equivalent' with a concrete scoring rubric: specific section-level comparison with defined tolerance for nullFlavor expansion.
10. Add terminology version management as a separate operational concern: LOINC releases twice yearly, SNOMED CT quarterly, RxNorm monthly. The capacity plan (step 28) must include automated terminology update pipelines with regression testing against the translation test suite.

### Missing Elements

1. No message deduplication / idempotency design. HL7 MSH-10 (Message Control ID) must be used to detect and suppress duplicate messages at every ingestion point. Retried messages from EHR systems are common and will cause duplicate audit entries and double-processing without this.
2. No key management lifecycle specification. Step 4 mandates AES-256-GCM and KMS key references but never defines: key rotation schedule, key compromise response procedure, key escrow for regulatory access, or what happens to encrypted audit logs after key rotation.
3. No FHIR Subscription / notification architecture. Reactive interoperability (push-based) is increasingly required by ONC and payers. The plan is entirely request-response. At minimum, document FHIR R4 topic-based subscriptions as out-of-scope with a roadmap note.
4. No rate limiting or backpressure specification. The API has no documented rate limits per client, per EHR system, or per patient. FHIR Bulk Export jobs can consume all available I/O. Without rate limiting, a runaway export job will degrade real-time translation SLAs.
5. No DR drill requirement. The SLA specifies RPO 1h / RTO 4h but there is no acceptance criterion requiring a validated DR test. For HIPAA-regulated systems this is required by §164.308(a)(7)(ii)(D) — the plan documents the SLA but never tests it.
6. No patient identity matching (MPI) strategy. Cross-EHR patient matching (same patient in Epic, Cerner, and Allscripts) requires probabilistic or deterministic MPI logic. Without it, the gateway will create duplicate patient records or misroute data. EMPI is table-stakes for a multi-EHR gateway.
7. No versioning strategy for EHR API changes. Epic, Cerner, and Allscripts ship API updates multiple times per year. There is no connector version pinning, change monitoring, or compatibility test automation when vendors update their FHIR implementations.
8. No consent management layer. HIPAA minimum necessary is mentioned in step 16 but there is no consent enforcement model — specifically, 42 CFR Part 2 (substance use disorder data), HIV-specific state laws, and mental health data all require stricter consent than standard HIPAA. These are legally distinct from HIPAA and affect what can be translated and delivered.
9. Missing third-party penetration test requirement. Step 26 describes internal security testing. ONC certification and most enterprise healthcare customers require an independent third-party penetration test report from a qualified firm (CREST, GIAC, or equivalent credentialed). Self-assessment does not satisfy this.
10. No HL7 v2 message validation before translation. Step 9 parses HL7 v2 but there is no pre-translation conformance validation step. Invalid HL7 messages (wrong segment order, missing required fields per HL7 conformance profile) should be rejected with structured ACK/NACK before entering the translation pipeline, not after.

### Security Risks

1. CUSTOM JOSE/SMART AUTH SERVER — building token signing, PKCE verification, and scope enforcement from scratch for a PHI system is the highest-risk security decision in this plan. One implementation error in PKCE verification or scope enforcement exposes all patient data to unauthorized access. Use a certified OAuth2 server.
2. TRANSLATION ENGINE AS PHI INJECTION SURFACE — HL7 v2 fields are free-text and can contain metacharacters that, if not sanitized before SQL persistence or audit logging, create injection vectors. Step 26 mentions HL7 injection testing but the parser (step 9) has no explicit sanitization acceptance criteria. The test plan tests for the vulnerability after it exists instead of preventing it.
3. AUDIT LOG HASH CHAIN TIMING ATTACK — sequential SHA-256 chaining with nanosecond timestamps at 500 msg/sec means the chain computation is on the critical path. If an attacker can predict or delay log writes, they may be able to insert fabricated entries in the ordering gaps. Consider append-only Merkle tree structure instead of linear chaining.
4. PRESIGNED S3 URLS FOR BULK EXPORT PHI — step 18 uses presigned S3 URLs for FHIR Bulk Export file download. Presigned URLs are not revocable once issued. If a token is revoked mid-download, the presigned URL remains valid for the expiry window (1 hour). For PHI bulk files this is a data exposure risk. Add S3 Object Lambda or a signed proxy download endpoint instead.
5. VAULT DYNAMIC SECRETS COLD START RACE — step 8 configures Vault for dynamic DB credentials but does not specify behavior during Vault unavailability. If Vault is unreachable at startup, does the gateway fail closed (correct for PHI) or fall back to static credentials (catastrophic)? Fail-closed behavior must be an explicit acceptance criterion.
6. SSRF VIA EHR CONNECTOR — step 26 includes 'SSRF via EHR connector' in the test scope but the connector design in steps 13-15 configures EHR endpoint URLs from a database table (ehr_connections). If that table can be modified by an authenticated admin user, an attacker with admin access can redirect connector calls to internal metadata services (AWS IMDS, Vault API). Require URL allowlisting with schema validation on the connection config table.
7. MLLP PORT EXPOSURE — MLLP on port 2575 must not be exposed to the public internet. The Kubernetes NetworkPolicy in step 21 must explicitly restrict MLLP listener pods to inbound connections from known EHR IP ranges only. The plan does not specify this constraint in the NetworkPolicy acceptance criteria.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.309345
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

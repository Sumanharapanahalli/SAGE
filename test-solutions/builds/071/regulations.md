# Regulatory Compliance — Lms Platform

**Domain:** edtech
**Solution ID:** 071
**Generated:** 2026-03-22T11:53:39.328237
**HITL Level:** standard

---

## 1. Applicable Standards

- **FERPA**
- **COPPA**
- **WCAG 2.1**
- **SCORM/xAPI**

## 2. Domain Detection Results

- edtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | COMPLIANCE | Produce compliance analysis and evidence artifacts for FERPA, COPPA, and WCAG 2. | Standards mapping, DHF, traceability |
| Step 5 | SECURITY | Build a threat model for lms_platform covering authentication, video content acc | Threat modeling, penetration testing |
| Step 26 | SECURITY | Conduct security review of the built system. Perform OWASP Top 10 verification,  | Threat modeling, penetration testing |
| Step 27 | COMPLIANCE | Produce final compliance evidence artifacts. WCAG 2.1 AA: automated axe-core sca | Standards mapping, DHF, traceability |
| Step 28 | QA | Execute full QA test plan. Produce test execution report covering: functional te | Verification & validation |
| Step 29 | SYSTEM_TEST | Execute system-level integration and performance tests. Load test with k6: 500 c | End-to-end validation, performance |

**Total tasks:** 31 | **Compliance tasks:** 6 | **Coverage:** 19%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | FERPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | COPPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | WCAG 2.1 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 4 | SCORM/xAPI compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

## 5. Risk Assessment Summary

**Risk Level:** STANDARD — Compliance focus on data protection and quality

| Risk Category | Mitigation in Plan |
|--------------|-------------------|
| Data Privacy | SECURITY + LEGAL tasks |
| Service Quality | QA + SYSTEM_TEST tasks |
| Compliance Gap | REGULATORY tasks (if applicable) |

## 6. Agent Team Assignment

| Agent Role | Tasks Assigned | Team |
|-----------|---------------|------|
| developer | 16 | Engineering |
| qa_engineer | 3 | Engineering |
| regulatory_specialist | 2 | Compliance |
| analyst | 2 | Analysis |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| localization_engineer | 1 | Engineering |
| devops_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 62/100 (FAIL) — 1 iteration(s)

**Summary:** This is an impressively detailed 31-step plan that covers the full SDLC for a complex LMS. The coverage of SCORM, LTI, xAPI, FERPA, COPPA, and WCAG in a single coherent plan is genuinely rare and commendable. However, there are three critical architectural failures that will block production readiness regardless of how well the rest is executed: (1) the SCORM JavaScript API bridge design is fundamentally incompatible with the synchronous contract SCORM content expects — the ADL test suite will not pass; (2) SCORM package serving from the same origin creates a critical XSS vulnerability that undermines all authentication and FERPA controls; and (3) the PDF signing scheme specifies WeasyPrint as both the renderer and signer, a library that has no signing capability. Beyond these blockers, the absence of GDPR for what will inevitably be an international product, the underscoped QTI 2.1 importer, the missing HLS segment-level access control, and the xAPI table write scalability gap represent significant rework items before a production launch. The score of 62 reflects solid engineering intent with critical implementation gaps that require architectural decisions, not just code fixes.

### Flaws Identified

1. CRITICAL — SCORM JS API synchronous/async mismatch: Step 19 proposes proxying LMSInitialize/LMSGetValue/LMSSetValue to the backend via fetch(). SCORM 1.2 and 2004 JavaScript APIs are synchronous — the calling SCO expects an immediate return value. Async fetch breaks this contract entirely. The ADL conformance test suite will fail. The bridge must use synchronous postMessage with a SharedArrayBuffer or run in the same JavaScript context as the SCO content, not a fetch proxy.
2. CRITICAL — SCORM package XSS via same-origin serving: Steps 14 and 19 never specify where extracted SCORM packages are served from. If served from the same origin as the LMS application, arbitrary SCORM package JavaScript runs in the LMS origin and can make fully-authenticated requests as the logged-in user (despite httpOnly cookies protecting against document.cookie access). SCORM content must be sandboxed to a separate origin (subdomain + CSP) with postMessage-only communication to the bridge.
3. CRITICAL — WeasyPrint cannot cryptographically sign PDFs: Step 16 specifies 'RSA SHA-256 signature embedded in PDF metadata' using WeasyPrint. WeasyPrint is an HTML-to-PDF renderer with no PDF signing capability. Achieving verifiable tamper-evidence requires a separate signing layer (PyHanko, pdfrw, or an external signing service). The acceptance criteria ('tampered PDF returns valid: false') cannot be met with WeasyPrint alone. This is a fundamental library mismatch.
4. CRITICAL — COPPA 'verifiable parental consent' is not just an email flow: Step 9's COPPA implementation sends a parental consent email. The FTC's COPPA Rule (16 CFR 312.5) requires 'verifiable' consent — a credit card transaction, video call, signed form, or government ID in many cases. An email link does not meet the verifiable consent standard for operators collecting personal data from under-13 users. This exposes the platform to FTC enforcement action.
5. HIGH — HLS video signed URLs do not protect content: Step 11 generates 1-hour signed URLs per video. HLS streams consist of a manifest (.m3u8) plus hundreds of individual .ts segment files. A learner can download the manifest and all segments within the 1-hour window and retain them indefinitely, or share the segment URLs. Token-authenticated streaming (per-segment signed URLs or a streaming proxy that validates enrollment on each request) is required for meaningful access control.
6. HIGH — SCORM 2004 conformance test suite completely absent: Step 23 acceptance criteria cover 'SCORM ADL test suite scenarios' but only explicitly reference 1.2. Step 28 mentions 'ADL SCORM 1.2 and 2004 conformance test suites' but Step 14 acceptance criteria only validate '1.2 ADL test suite passes.' SCORM 2004 has a separate API (Initialize('') vs LMSInitialize(''), cmi.completion_status vs cmi.core.lesson_status) requiring its own test execution. Treating them as equivalent will produce a non-conformant 2004 implementation.
7. HIGH — GDPR entirely absent: FERPA and COPPA are US-specific. Any LMS deployed to EU learners (or processing EU resident data from a US institution) requires GDPR compliance: lawful basis for processing, data subject access requests, right to erasure (beyond just COPPA deletion), data portability, DPA agreements with all processors, and breach notification within 72 hours. The traceability matrix in Step 4 has no GDPR row. This is a blocking issue for any European deployment or institution with EU students.
8. HIGH — No dedicated transcoding infrastructure: Step 11 runs ffmpeg via Celery on shared workers alongside email, certificate, and grade passback tasks. A single 10 GB video upload can pin a worker thread for 30-60 minutes, starving time-sensitive tasks (LTI grade passback has a 5-second SLA in Step 15). No separate queue routing for CPU-bound transcode tasks vs. IO-bound async tasks, no dedicated worker pool sizing, no transcode job timeout or dead-letter handling.
9. HIGH — LTI OIDC state parameter session affinity: The LTI 1.3 OIDC login flow stores state and nonce in the server session between the login initiation request and the launch redirect. With multiple ECS tasks and no explicit session affinity, the callback may land on a different task instance that has no record of the state parameter, causing all LTI launches to fail under load. The plan notes Redis is available but never specifies that LTI session state must be stored in Redis, not in-process.
10. MEDIUM — QTI 2.1 import is massively underscoped: Step 12 allocates one acceptance criterion ('parses a standard QTI package') to QTI 2.1 import. QTI 2.1 is a 500+ page specification covering interaction types, response processing templates, outcome declarations, template variables, stylesheet handling, and asset bundling. A production-grade QTI importer is a multi-month effort. No mention of which QTI interaction types are in scope, which are not, or how out-of-scope types degrade.
11. MEDIUM — xapi_statements table will become a hot-write bottleneck: At 1000 statements/minute sustained (Step 29), this table accumulates 1.44M rows/day. No table partitioning (by date or user), no archival strategy, and the indexes (user_id+course_id) will cause write amplification on insert-heavy workloads. PostgreSQL JSONB with no partitioning at this write rate will degrade within weeks in production.
12. MEDIUM — Missing search infrastructure for course catalog: Step 17 requires search by title, category, and instructor with debounced API calls. No search backend is specified — no pg_trgm extension, no full-text search index, no Elasticsearch/OpenSearch. PostgreSQL ILIKE queries on unindexed text columns will not scale to a large course catalog.
13. MEDIUM — LTI dynamic registration has no approval gate: Step 15 implements dynamic registration (IMS LTI DR spec). Any party who knows the registration endpoint URL can register an LTI platform. Without an admin approval step for new registrations, a malicious actor can register a fake platform and attempt to exploit the OIDC flow. The plan has no mention of registration review, allowlisting, or admin notification.

### Suggestions

1. Replace the fetch-based SCORM JS bridge with a postMessage + SharedArrayBuffer synchronous bridge pattern, OR serve all SCORM content through a same-origin iframe (different subdomain) that has the SCORM API object in its window scope and communicates with the main LMS via postMessage. Research Rustici Engine's open-source reference implementation for prior art.
2. Serve extracted SCORM packages exclusively from a dedicated sandboxed subdomain (e.g., scorm-content.yourdomain.com) with a strict Content-Security-Policy that blocks external network requests and disallows eval. Use postMessage for all SCORM API calls between the iframe and the host page.
3. Replace WeasyPrint-only PDF signing with a two-stage pipeline: WeasyPrint generates the PDF bytes, then PyHanko applies a PAdES-compliant RSA signature. Store the public certificate in the certificates table so the /verify endpoint can validate the embedded signature without holding private key material in the application tier.
4. Replace the parental consent email flow with a proper verifiable consent mechanism: credit card microcharge, electronic signature via DocuSign/HelloSign, or a notarized offline form. Consult an FTC COPPA specialist before launch — the email-only approach is a documented enforcement trigger.
5. Add an HLS token authentication proxy (e.g., nginx with auth_request, or CloudFront signed cookies that validate enrollment server-side on every .ts segment request). Per-segment signed URLs add overhead but are the only reliable way to prevent URL sharing.
6. Add a GDPR compliance step (Step 4.5) covering: lawful basis mapping for all processing activities, DSAR workflow (data subject access + erasure requests within 30 days), DPA templates for all sub-processors, data residency configuration for EU-hosted deployments, and breach notification playbook.
7. Split the Celery worker into at minimum two separate queues: `transcode` (CPU-bound, separate worker process pool, 2-4 workers) and `default` (IO-bound tasks: email, certificates, grade passback, xAPI forwarding). ECS should deploy these as separate task definitions with independent scaling policies.
8. Add PostgreSQL table partitioning for xapi_statements by created_at (monthly range partitions) and define a 90-day archival policy to cold storage (S3 Parquet via pg_partman). Add a separate timeseries-optimized write path (TimescaleDB or a lightweight queue buffer) if the 1000/min sustained rate is a real requirement.
9. Add pg_trgm (trigram) GIN index on courses.title and courses.description for fuzzy full-text search, or provision OpenSearch for more advanced catalog search. Specify this as infrastructure in Step 7/8.
10. Add an admin registration approval screen for LTI Dynamic Registration. New registrations should be created in a 'pending' state, email the admin, and only become active after admin review.

### Missing Elements

1. SCORM package sandboxed serving architecture — where extracted packages live, what origin they're served from, and how the JS SCORM API bridge works synchronously across the iframe boundary
2. GDPR compliance: lawful basis, DSAR workflow, right to erasure, data portability, DPA templates, 72-hour breach notification
3. Celery queue topology: separate queues for CPU-bound (transcode) vs IO-bound tasks, worker sizing, dead-letter queue for failed transcode jobs
4. xapi_statements partitioning and archival strategy for high-volume write scenarios
5. Course catalog search infrastructure (pg_trgm or OpenSearch)
6. Email deliverability setup: SPF, DKIM, DMARC for certificate delivery domain
7. Video CDN token authentication for HLS segment-level access control
8. Multitenancy decision: is this single-tenant SaaS, multi-tenant SaaS, or self-hosted? Affects schema isolation, branding, LTI registration scoping, and FERPA boundaries
9. Rate limiting middleware implementation (mentioned in OpenAPI spec step but never implemented in any backend step)
10. Database backup/DR: RTO/RPO targets, RDS automated backup configuration, cross-region replication for production
11. SCORM 2004 ADL conformance test execution plan (separate from 1.2)
12. QTI 2.1 scope boundary: which interaction types are in-scope for MVP vs. deferred
13. Real-time notifications (instructor grading queue, quiz submission alerts) — polling at 10s is specified but no push infrastructure (WebSocket or SSE) is designed
14. Video transcoding failure and retry handling: what happens to the upload when ffmpeg fails, how the instructor is notified, dead-letter queue
15. WeasyPrint PDF signing gap: no mention of PyHanko or equivalent PDF signing library

### Security Risks

1. SCORM content XSS via same-origin serving: if extracted SCORM packages are served from the LMS application origin, malicious SCORM JavaScript executes in the authenticated LMS context and can make credentialed API requests as the logged-in user, exfiltrate enrollment data, or tamper with grade records. Severity: CRITICAL.
2. LTI JWT replay window: Step 15 acceptance criteria test 'reusing a launch JWT after expiry returns 401' — but the nonce must also be validated and persisted to prevent replay within the JWT validity window (typically 5 minutes). Nonce storage and single-use enforcement are not explicitly designed.
3. SCORM package ZIP bomb and large file extraction: Step 14 validates path traversal but does not mention extraction size limits. A malicious SCORM ZIP could contain a 10 GB decompressed payload from a 10 MB archive, exhausting disk space on the application server. Add extraction size limits and per-instructor storage quotas pre-extraction.
4. Rich text editor XSS (TipTap/ProseMirror): Step 18 uses TipTap for lesson content. TipTap outputs HTML that will be rendered by learner browsers. The backend must sanitize HTML through a strict allowlist (DOMPurify server-side equivalent, e.g., bleach for Python) before storage and before serving. The plan has no explicit HTML sanitization step.
5. Certificate UUID predictability: if certificate verification UUIDs are sequential or time-based (UUID v1/v4), there's no additional access control on the public /certificates/{uuid}/verify endpoint — anyone who can guess a UUID can enumerate all issued certificates and verify learner completion. Use UUID v4 (random) and confirm this is specified in the schema.
6. Video signed URL parameter tampering: a learner could attempt to modify the signed URL parameters (user_id, course_id) after obtaining a valid URL for one course to access video for another. The signing scheme must include all authorization parameters in the HMAC payload — the plan does not specify what is signed.
7. Admin impersonation audit bypass: Step 9 logs impersonation start/end, but does not specify whether all actions taken during an impersonation session are attributed to the impersonator in the audit log. If impersonated actions are logged under the victim's user_id, FERPA audit trails become unreliable and impersonation abuse is undetectable.
8. LTI Dynamic Registration endpoint exposure: as noted, open dynamic registration without admin approval allows any actor to register a platform and probe the OIDC flow for vulnerabilities. Should require at minimum a pre-shared registration token.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.328274
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

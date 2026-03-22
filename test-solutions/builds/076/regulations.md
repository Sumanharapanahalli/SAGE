# Regulatory Compliance — School Erp

**Domain:** edtech
**Solution ID:** 076
**Generated:** 2026-03-22T11:53:39.330191
**HITL Level:** standard

---

## 1. Applicable Standards

- **FERPA**
- **COPPA**
- **PCI DSS**
- **GDPR**

## 2. Domain Detection Results

- edtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 3 | LEGAL | Draft Terms of Service, Privacy Policy, and Data Processing Agreements compliant | Privacy, licensing, contracts |
| Step 5 | SECURITY | Produce a threat model and security design for the School ERP system covering st | Threat modeling, penetration testing |
| Step 6 | COMPLIANCE | Create compliance evidence artifacts for FERPA, COPPA, and WCAG 2.1. Produce a t | Standards mapping, DHF, traceability |
| Step 27 | QA | Produce a comprehensive QA test plan: test strategy, test cases for all six modu | Verification & validation |
| Step 30 | SYSTEM_TEST | Execute end-to-end system integration tests across all six modules using Playwri | End-to-end validation, performance |
| Step 31 | COMPLIANCE | Execute WCAG 2.1 AA accessibility audit across all portal pages using automated  | Standards mapping, DHF, traceability |

**Total tasks:** 33 | **Compliance tasks:** 6 | **Coverage:** 18%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | FERPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | COPPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | PCI DSS compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |
| 4 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |

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
| devops_engineer | 3 | Engineering |
| qa_engineer | 3 | Engineering |
| ux_designer | 2 | Design |
| regulatory_specialist | 2 | Compliance |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| legal_advisor | 1 | Compliance |
| localization_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 62/100 (FAIL) — 1 iteration(s)

**Summary:** This is a structurally ambitious and surprisingly detailed plan for a 6-module School ERP with genuine attention to FERPA/COPPA compliance, RBAC, multi-tenancy, and accessibility — qualities that many ERP plans skip entirely. However, it has a critical dependency graph bug: all six backend implementation steps (13–18) depend only on auth (step 12) and not on the database schema (step 8), meaning the schema can be changed after modules are half-built, guaranteeing destructive rework. Beyond the graph, there are three production-blocking gaps: (1) no academic year rollover workflow, which is a fundamental operational requirement for any school system; (2) no COPPA consent collection implementation despite the legal step identifying it; and (3) no WebSocket infrastructure despite requiring real-time messaging. The fee collection module has a PCI DSS blind spot — Stripe Elements reduces scope but does not eliminate it, and no SAQ A compliance work is planned. The timetable auto-generation feature is aspirationally listed but algorithmically unspecified, making it effectively undeliverable as described. For an MVP that scoped down to enrollment, attendance, and grades (as the PRD step suggests), this plan would score in the mid-70s after fixing the dependency graph. As a full 6-module production plan ready for school districts handling regulated student PII, it needs the identified gaps closed before execution.

### Flaws Identified

1. Steps 13–18 (all backend modules) depend only on step 12 (auth) but NOT on step 8 (database schema). Implementing enrollment, attendance, grades, etc. before the schema is finalized means every module will likely require destructive model changes mid-implementation. This is the single most damaging structural error in the plan.
2. Steps 1 and 2 both have depends_on: [] but PRD (step 2) cannot realistically be produced without completed business analysis (step 1). Running them in parallel means the PRD will be based on incomplete requirements, requiring rework.
3. Step 5 (security/STRIDE threat model) also has depends_on: [] despite requiring module-level understanding from step 1. A threat model written before requirements are documented will miss attack surfaces.
4. Academic year rollover is entirely absent. At year-end, student enrollments must archive, grade history must freeze, new academic year must initialize, and section assignments must roll forward. This is a critical operational workflow for any school ERP and affects the core data model.
5. Step 23 specifies drag-and-drop timetable editor but timetable auto-generation (an NP-hard constraint satisfaction problem) is listed as a feature in step 16 with no algorithmic approach defined. Manual drag-and-drop for 50+ teachers, 30+ rooms, and 200+ sections is operationally unusable.
6. WebSocket infrastructure for real-time messaging (step 24 requirement) has no corresponding setup in step 10 (Docker Compose), step 29 (infra), or step 12 (auth). WebSockets behind Kubernetes/load balancers require sticky sessions or Redis pub/sub — neither is mentioned anywhere.
7. COPPA parental consent collection workflow is missing from the enrollment module (step 13). COPPA requires verifiable parental consent before data collection for children under 13. The legal step (step 3) documents the requirement but no corresponding implementation step exists.
8. FERPA right-of-access (parent/student right to request and receive all records) has no data export feature in scope. Step 3 documents data retention but no export-on-request workflow is planned.
9. Grade finalization/locking after term end is absent. 'Append-only revisions' is not the same as a term-close workflow that locks the gradebook, triggers report card generation, and computes cumulative GPA for the transcript.
10. Step 17 specifies Firebase Cloud Messaging but no mobile app is in scope. FCM for web browsers uses VAPID (Web Push Protocol), which is architecturally different from FCM for native mobile. This distinction is critical for the notification infrastructure design.
11. Age-based record access transition is unaddressed. Under FERPA, when a student turns 18, record access rights transfer from parent to student. No logic exists for this transition, which is a compliance gap for any multi-year student records.

### Suggestions

1. Fix the dependency graph: steps 13–18 must add step 8 to depends_on. Step 2 must depend on step 1. Step 5 must depend on step 1. Draw the full DAG and validate it before execution.
2. Add a step 0 or step 1.5 specifically for academic year data model design — define how year transitions work, what archives, what carries forward, and what initializes. This decision cascades through every module's schema.
3. Split timetable into two sub-steps: (a) manual slot editor with conflict detection (achievable), and (b) auto-generation with a defined algorithm (OR-Tools, backtracking, or simulated annealing). Set explicit scope for MVP vs. Phase 2 on this.
4. Add a Redis pub/sub or dedicated WebSocket service (e.g., Socket.IO server or FastAPI WebSocket handler behind a Redis adapter) to step 10's docker-compose and step 29's infrastructure. Without this, real-time messaging will not scale past one API instance.
5. Add a COPPA consent step to step 13's enrollment workflow: before creating a student record for a child under 13, the system must collect and record verifiable parental consent. Define the consent storage model and UI flow.
6. Add a data export API endpoint (GET /students/{id}/export returning ZIP of all FERPA-covered records) and corresponding UI to the admin portal. This is a legal obligation, not a nice-to-have.
7. Specify PDF generation library in step 15. WeasyPrint, ReportLab, and wkhtmltopdf have radically different capabilities, maintenance status, and Docker image size implications. Lock this choice early — report card layout will be built around it.
8. Add file upload security to step 13: virus/malware scanning (ClamAV or S3 event trigger to a scanning lambda), MIME-type validation server-side (not just extension check), and a maximum file size limit enforced in the API layer.
9. Add Stripe webhook signature verification as an explicit acceptance criterion in step 18. 'Stripe webhook handles payment_intent.succeeded' is incomplete without verifying the Stripe-Signature header — without it, the endpoint is open to spoofed payment confirmations.
10. Add API versioning (/api/v1/) to the OpenAPI spec in step 9. This is a multi-tenant SaaS serving multiple school districts. Without versioning, any breaking API change forces simultaneous upgrades across all tenants.
11. Add a Celery monitoring step (Flower or integration with Grafana via celery-exporter). Background task failures (notification delivery, PDF generation, invoice scheduling) will be invisible without this.
12. Define RTO and RPO in step 29. '7-day backup retention' is not a disaster recovery plan. Specify: how long to restore from backup, how to test restores, and what the acceptable data loss window is.

### Missing Elements

1. Academic year rollover workflow (archive, transition, new-year initialization)
2. PCI DSS compliance documentation — even Stripe Elements SAQ A requirements are unaddressed
3. COPPA verifiable parental consent collection and storage workflow
4. FERPA data export on request (parent/student right of access)
5. WebSocket server/infrastructure design for real-time messaging
6. Timetable auto-generation algorithm specification (OR-Tools, backtracking, etc.)
7. Age-18 record access transfer logic (FERPA §99.5)
8. Grade finalization/term-close workflow
9. File upload malware scanning
10. Email bounce and delivery failure handling (dead-letter queue, retry, fallback)
11. Celery task monitoring and dead-letter handling
12. API versioning strategy
13. RTO/RPO definition and restore testing procedure
14. Stripe webhook signature verification as explicit requirement
15. Rate limiting implementation (mentioned in spec but no implementation step)
16. Data migration/import from legacy systems (existing schools have years of records)
17. Concurrent session management and forced logout for compromised accounts
18. Tenant isolation middleware (application-layer enforcement of school_id scoping, not just FK conventions)

### Security Risks

1. Stripe webhook endpoint with no explicit signature verification requirement is a critical financial fraud vector. A spoofed payment_intent.succeeded event would mark invoices as paid without actual payment.
2. Document upload to S3 with no server-side MIME validation or malware scanning allows upload of malicious files (polyglot PDFs, macro-enabled Office docs). Signed S3 URLs returned to users could serve malware.
3. Row Level Security listed as a database 'feature' but no Postgres RLS policies are specified for implementation. Without enforced RLS, a bug in application-layer filtering leaks all tenants' student PII to any authenticated user.
4. Multi-tenant school_id FK convention relies entirely on application-layer enforcement. A single missing WHERE clause in any query exposes cross-tenant data. No compensating control (RLS, separate schemas, or connection pooling per tenant) is specified.
5. XSS via user-generated content in messaging module. Teacher-to-parent messages with no output encoding or content security policy allow stored XSS. School admin moderation flag does not prevent initial rendering.
6. FERPA audit log tamper protection is unspecified. The audit_log table captures events, but nothing prevents a compromised admin account from deleting or modifying audit records. Append-only enforcement (Postgres trigger or separate write-only log store) is absent.
7. Password reset tokens stored in the database with no mention of hashing. If the token column is plaintext and the DB is breached, all active reset tokens are compromised. Tokens must be stored as bcrypt/argon2 hashes.
8. Rate limiting on auth endpoints (5/min per IP) is in the acceptance criteria but no implementation step exists — not in the API design step, not in the auth implementation step, not in the infra step. This is missing from the execution plan entirely.
9. No Content Security Policy (CSP) headers specified anywhere. An ERP handling student PII with no CSP is vulnerable to data exfiltration via injected scripts.
10. SSRF risk: document upload pre-signed URL generation or any URL-fetching feature could be abused to probe internal AWS metadata endpoints (169.254.169.254). No SSRF mitigation is mentioned.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.330267
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

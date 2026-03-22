# Regulatory Compliance — Procurement System

**Domain:** enterprise
**Solution ID:** 097
**Generated:** 2026-03-22T11:53:39.337262
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **SOX**
- **ISO 27001**
- **GDPR**

## 2. Domain Detection Results

- enterprise (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 3 | LEGAL | Draft legal artifacts for the procurement platform: vendor terms of service, sup | Privacy, licensing, contracts |
| Step 4 | COMPLIANCE | Create ISO 27001 and SOC 2 compliance framework for the procurement system: defi | Standards mapping, DHF, traceability |
| Step 22 | SECURITY | Conduct security review: threat model for procurement data flows, OWASP Top 10 a | Threat modeling, penetration testing |
| Step 24 | QA | Create QA test plan and execute functional test cases for all procurement workfl | Verification & validation |
| Step 26 | SYSTEM_TEST | Execute system-level integration tests: full requisition-to-payment lifecycle ac | End-to-end validation, performance |
| Step 27 | COMPLIANCE | Produce ISO 27001 and SOC 2 evidence artifacts: audit log completeness verificat | Standards mapping, DHF, traceability |

**Total tasks:** 30 | **Compliance tasks:** 6 | **Coverage:** 20%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | SOX compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | ISO 27001 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
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
| developer | 15 | Engineering |
| regulatory_specialist | 3 | Compliance |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 63/100 (FAIL) — 1 iteration(s)

**Summary:** This is one of the more thorough enterprise procurement plans I've reviewed — the scope coverage across 30 steps, the data model depth (16 entities), the compliance framing (ISO 27001 + SOC 2), and the agentic layer are all well-conceived. However, the plan has a hard sequencing deadlock (QA requires staging, staging is built after QA), several missing infrastructure services that would cause silent feature failures at runtime (email, task queue, FX rates), and a complete absence of tax/VAT modeling that will block go-live in any EU or multi-jurisdiction deployment. The sealed bid confidentiality is enforced only at the application layer, creating real legal liability for bid manipulation. The AI agent acceptance criteria cannot be objectively tested without labeled datasets. For an enterprise-grade, production procurement system — where financial controls and vendor integrity are existential concerns — these gaps represent rework, not polish. The architecture direction is correct; the execution plan has approximately 8-10 concrete blockers that would prevent shipping or create compliance failures. Rework the sequencing dependency on staging, add the missing infrastructure services, specify tax field reservations in the schema, and harden the sealed bid and document storage security before treating this as production-ready.

### Flaws Identified

1. Step 24 (QA) requires a staging environment and declares dependencies on Steps 15-20 and 23, but Step 25 (which creates the staging infrastructure via Terraform) is sequenced AFTER Step 24. QA has no environment to run in. This is a hard sequencing deadlock.
2. Email notification service is never configured. Steps 9, 10, 12 all require transactional email (expiry alerts, vendor invitations, award notifications, reminders) but neither Step 7 (Docker Compose) nor Step 25 (Terraform) provisions SES, SendGrid, or any SMTP service. These features will silently not work.
3. Background task queue worker is absent. Step 7 includes Redis as a dependency but never sets up a Celery worker or equivalent. Steps 8 (24h escalation timer), 9 (90/60/30-day expiry alerts), 10 (48h/24h reminder emails), and 13 (15-min materialized view refresh) all require scheduled/async job execution. Docker Compose in Step 7 has no worker service.
4. No FX rate provider integration. Step 11 specifies 'amounts stored in transaction currency + USD equivalent at rate-of-day' but no step integrates an exchange rate API (ECB, Open Exchange Rates, etc.). Without this, multi-currency POs cannot populate the USD equivalent field.
5. Org hierarchy data is assumed to exist but never imported. The approval routing engine in Step 8 resolves approvers from 'org hierarchy' but no step addresses how org structure is ingested — no HR system integration, no org hierarchy CRUD, no import tooling. The engine will have no data to route against.
6. Budget data has no population path. Step 8 validates requisitions against 'department budgets' and the schema in Step 6 has a `budget` entity, but no step implements budget creation UI, budget import from finance systems, or fiscal period setup. Budget validation will always fail or be bypassed.
7. Step 21 AI agent acceptance criteria are unverifiable assertions. '90%+ routing accuracy' and '>95% duplicate detection precision' are stated without a benchmark dataset, labeled test set, or evaluation harness. These pass/fail criteria cannot be objectively tested at handoff.
8. WeasyPrint PDF generation (Step 11) requires system-level dependencies (Cairo, Pango, fonts) that are not addressed in the Docker setup (Step 7). This silently fails in Alpine-based containers, which is the default for FastAPI deployments.
9. ERP/accounting integration is documented in Step 30 but never implemented. The ERD has no ERP foreign keys, no webhook receiver for ERP events, and no field mapping layer. A procurement system that can't post approved POs and matched invoices to the general ledger is a workflow dead end for finance.
10. Sealed bid confidentiality is enforced only at the application layer. Quotes are stored unencrypted in PostgreSQL. Any user with DB read access (DBA, reporting tool, compromised service account) can read competitor bids before the deadline. Column-level encryption or a separate sealed bid vault is not specified.
11. Tax and VAT handling is completely absent. Enterprise procurement in any multi-jurisdiction deployment requires tax calculation, VAT registration validation, withholding tax on vendor payments, and tax-line reporting. The invoice schema has no tax fields. This is a blocker for EU, UK, and many APAC markets.
12. Payment terms are never modeled. Step 12 leads to 'approve-for-payment' but there is no Net 30/60/90 payment terms entity, no due date calculation, and no accounts payable posting step. The invoice aging chart in Step 19 has no due dates to age against.
13. Webhook delivery reliability is unaddressed. Step 14 defines 5 webhook event types but no step implements delivery retry logic, dead letter queues, subscription management (register/unregister), HMAC signature verification, or idempotency keys. Webhooks will drop silently under any transient failure.
14. Vendor deduplication is not addressed. Two vendor reps from the same company can each submit registration, creating duplicates in the vendor directory. No step implements duplicate detection (EIN/VAT number uniqueness, fuzzy name matching) or a merge workflow.
15. Data migration from legacy systems is called out in Step 1 acceptance criteria ('migration plan drafted') but there is no implementation step for migration tooling, data validation, or cutover procedure. Step 1 produces a plan; nothing executes it.

### Suggestions

1. Insert a Step 7b or move Step 25 staging infrastructure before Step 15 to unblock QA. At minimum, Stage 24 must declare a dependency on Step 25, or Step 25 must be split into 'staging' (early) and 'production' (late).
2. Add an explicit infrastructure sub-step to Step 7 that provisions a Docker Compose worker service (Celery + Beat) and an email service container (MailHog for dev, SES/SendGrid config for prod). Add a `celery` service to docker-compose.yml.
3. Add a Step 6b or 7b for 'Reference Data Bootstrap': fiscal calendar configuration, spend category taxonomy import, org hierarchy import (CSV or HR system API), and initial department budget seeding. Without this, Steps 8 and 13 have no reference data.
4. Replace the AI agent acceptance criteria in Step 21 with a concrete evaluation protocol: create a labeled query dataset of 100 test inputs with expected specialist routing, a labeled duplicate invoice dataset with ground-truth labels, and automate the eval as part of Step 23's test suite.
5. Add MFA enforcement for high-value approval actions (POs above configurable threshold). OAuth2 + JWT alone is insufficient for audit-grade approval trails in regulated procurement environments.
6. Specify column-level encryption for sealed bid quote amounts using pgcrypto or application-layer encryption with a key stored in AWS KMS, not in the application config.
7. Add a tax engine decision to the PRD (Step 2) and schema (Step 6): even if full tax calculation is out of scope for MVP, reserve tax_amount, tax_code, and tax_jurisdiction fields on invoice and PO line items to avoid a schema migration at the worst possible time.
8. Add webhook subscription CRUD endpoints to Step 14's API and implement delivery with exponential backoff retry (max 3 attempts), HMAC-SHA256 request signing, and a dead letter log queryable at GET /webhooks/delivery-log.
9. Step 7 Docker Compose should include a WeasyPrint-compatible base image (Debian/Ubuntu, not Alpine) for the API service, or isolate PDF generation to a dedicated sidecar container.
10. Add a FX rate integration step (can be a sub-task of Step 7 config): daily ECB/Open Exchange Rates pull, stored in a `exchange_rate` table, consumed by PO and invoice services. Fallback: reject multi-currency input if today's rate is unavailable.

### Missing Elements

1. Background task queue service (Celery + Beat or equivalent) — required by at least 5 steps
2. Transactional email service configuration (SES/SendGrid) — required by at least 4 steps
3. FX exchange rate provider integration
4. Org hierarchy import/sync mechanism
5. Budget data import and fiscal period management UI
6. Tax/VAT data model and calculation hook (even if deferred to Phase 2, schema must accommodate it)
7. Payment terms data model (Net 30/60/90, due date field on invoices)
8. Webhook subscription management API and reliable delivery infrastructure
9. Vendor deduplication logic and merge workflow
10. Data migration tooling and cutover procedure (Step 1 produces a plan; nothing implements it)
11. API rate limiting middleware implementation (Step 14 documents headers; nothing enforces them)
12. MFA requirement for high-value approval actions
13. Audit log retention policy implementation (GDPR and SOC 2 require defined retention, not just 'logs exist')
14. ERP/accounting system integration implementation (currently docs-only)
15. Vendor email domain verification during registration (prevents impersonation)

### Security Risks

1. Sealed bids stored unencrypted in PostgreSQL. Any DB-level access (reporting, compromised credentials, backup restore to dev) leaks all competitor quotes before deadline. This is a procurement integrity violation and potential legal liability.
2. W-9 forms and bank account details stored in MinIO with application-managed keys. No AWS KMS integration specified in Step 7 or Step 9. If the application config is compromised, all vendor financial data is exposed.
3. Email-ingested invoices (Step 12) are a primary fraud vector — no DKIM/SPF validation of sender domain, no digital signature requirement, no amount-change detection between email parse and human review. Business Email Compromise attacks will succeed undetected.
4. Vendor portal XSS: vendor-submitted content (company name, quote notes, document metadata, dispute thread messages) is rendered in the buyer portal (Steps 16, 17, 19). No step explicitly specifies HTML sanitization of vendor-controlled input fields.
5. IDOR risk on approval bypass: Step 8's approval routing engine resolves chains dynamically. Without server-side enforcement that the calling user_id matches the expected approver_id for the current step, a buyer could POST to the approve endpoint for a step not yet reached.
6. Signed URL pre-generation for documents is stateless. If a signed URL leaks (email forward, browser history, proxy log), the document is accessible for up to 15 minutes with no revocation mechanism. For NDAs and bank details, this window is too long without download tracking and IP logging.
7. No mention of SQL injection protection beyond SQLAlchemy ORM use. Step 13's materialized view refresh and spend aggregation queries likely involve dynamic filter construction (date_range, department, category) — these are injection targets if not using parameterized queries throughout.
8. AI vendor recommender (Step 21) can be poisoned: if the vector store or vendor scoring history is compromised, the recommender systematically steers buyers toward fraudulent vendors. No adversarial input validation or recommendation confidence floor is specified.
9. OAuth2 PKCE is specified for human users but vendor portal uses 'separate JWT' (Step 9). If vendor JWTs are long-lived and not rotatable, a compromised vendor credential provides persistent access to all RFQ quote submission endpoints with no forced re-auth.
10. No mention of Content Security Policy headers, CORS policy enforcement, or Subresource Integrity for the React frontend. The vendor portal and buyer portal sharing a domain (different route prefix only) creates risk of credential sharing via shared localStorage/cookies.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.337297
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

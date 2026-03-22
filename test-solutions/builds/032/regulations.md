# Regulatory Compliance — Crm Platform

**Domain:** saas
**Solution ID:** 032
**Generated:** 2026-03-22T11:53:39.317691
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **GDPR**
- **CCPA**

## 2. Domain Detection Results

- saas (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 5 | LEGAL | Draft Terms of Service, Privacy Policy (GDPR/CCPA compliant), Data Processing Ag | Privacy, licensing, contracts |
| Step 6 | SECURITY | Produce threat model (STRIDE) for CRM platform covering contact data, email cred | Threat modeling, penetration testing |
| Step 8 | COMPLIANCE | Define SOC 2 Type II control framework for crm_platform: map product features to | Standards mapping, DHF, traceability |
| Step 29 | SYSTEM_TEST | Execute end-to-end system tests on staging: load test (k6, 500 concurrent users) | End-to-end validation, performance |

**Total tasks:** 30 | **Compliance tasks:** 4 | **Coverage:** 13%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 3 | CCPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 14 | Engineering |
| devops_engineer | 3 | Engineering |
| regulatory_specialist | 2 | Compliance |
| qa_engineer | 2 | Engineering |
| marketing_strategist | 1 | Operations |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| financial_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| operations_manager | 1 | Operations |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 58/100 (FAIL) — 1 iteration(s)

**Summary:** This is a technically thorough plan with strong coverage of compliance, UX, testing, and operations — the dependency graph is mostly correct and the acceptance criteria are specific. However, it has several production-blocking gaps that must be fixed before implementation begins: Elasticsearch is referenced as a core feature with no infrastructure anywhere in the plan; the LLM-agent-based lead scoring architecture is economically and technically unworkable at the stated scale; there is no authentication implementation step despite auth being foundational to every other backend step; and the 12-week/3-person MVP estimate is not credible for this scope. The missing SPF/DKIM/DMARC setup is a deliverability killer for any email product. Fix the Elasticsearch decision (commit to PostgreSQL FTS or add it to the stack everywhere), replace the scoring architecture with a rules engine, add an auth step before step 12, and reframe the timeline before any implementation begins. As written, this plan would produce a partially functional system with a broken search feature, undeliverable emails, and no scalable scoring engine.

### Flaws Identified

1. Elasticsearch referenced in step 12 acceptance criteria ('elasticsearch_search' feature) but never added to Docker Compose (step 11), Terraform (step 27), or any infra step. The entire search feature has no infrastructure backing it.
2. Step 15 depends on step 14 (email automation) but lead scoring only needs contacts (step 12) and deal activity (step 13). This creates a false sequential bottleneck that blocks scoring until the entire email engine ships.
3. A/B test configuration is built in the frontend (step 20) but the backend email engine (step 14) never implements A/B variant routing, split percentage enforcement, or statistical significance calculation. Feature is half-built.
4. Step 3 acceptance criteria states 'MVP scope is achievable in ≤12 weeks by a 3-person team.' This plan has 6 major feature areas, Salesforce CDC sync, AI lead scoring, and SOC 2 controls. That estimate is not grounded in reality — a realistic 3-person MVP is 9–12 months.
5. LLM-based Multi-Agent Coordinator for lead scoring (step 15) with 5 specialist agents per score event at 100K contacts nightly = 500K LLM calls per night. At any real pricing, this is cost-prohibitive and the 30-minute SLA is unachievable. This should be a rules engine or lightweight ML model, not LLM agents.
6. WebSocket real-time updates in step 19 require pub/sub coordination across multiple API pods. With ECS Fargate running multiple API containers, WebSocket connections are pod-local. Redis pub/sub fanout is never specified anywhere in the plan.
7. No dedicated authentication implementation step. JWT issuance, refresh token rotation, OAuth2 callback handling, and session management are referenced in the API spec (step 10) but no backend step owns their implementation.
8. PDF export with embedded charts (step 16) requires headless Chrome (Playwright/Puppeteer server-side) or a PDF generation library. Neither is in the backend stack (step 11) or infra (step 27). This is a missing service dependency.
9. Salesforce Change Data Capture (step 17) requires Enterprise Edition or higher. Professional and Essentials orgs do not have CDC. The migration tool will silently fail for a significant portion of the target market without a fallback polling strategy.
10. CSV import in step 12 sets the bar at 10K rows without timeout. A Salesforce migration tool targeting 100K+ contacts with a 10K limit is inconsistent — the Salesforce full import target is 250K contacts (step 29). The import bar should match the migration scale.
11. Outbound webhook delivery to customers (in the API spec, step 10) has no backend implementation step. Step 14 handles inbound SendGrid webhooks but there is no step for building the outbound webhook dispatcher, retry queue, or signature signing.
12. Multi-tenancy is mentioned as a row-level security requirement in step 9 but there is no step defining the tenant provisioning model, per-tenant resource limits, or how tenant context propagates through the Celery task queue.

### Suggestions

1. Replace Elasticsearch with PostgreSQL full-text search (tsvector/GIN indexes) for MVP. Defer Elasticsearch to v1 if query performance demands it — this eliminates an unbudgeted infrastructure dependency.
2. Rebuild lead scoring as a configurable rules engine with weighted dimensions (no LLM agents). Reserve LLM calls for score explanation generation only (on-demand, not on every recompute). This makes the 30-minute nightly batch SLA achievable.
3. Move step 15 dependency from [14] to [12, 13]. Email engagement is one scoring dimension — it can be added as an optional signal after the core scoring engine ships.
4. Add a step 11.5: Authentication Service — implement JWT issuance, refresh rotation, password hashing (bcrypt/argon2), MFA (TOTP), and OAuth2 callback handling as a first-class deliverable before any protected endpoint is built.
5. Add Redis pub/sub fanout to the WebSocket architecture. Document in step 19 that the PipelineBoard connects to a single WebSocket gateway that subscribes to a Redis channel broadcast by any API pod on deal mutation.
6. Add headless Chrome (Chromium via Playwright) as a backend sidecar service for PDF generation, or adopt a library like WeasyPrint. Define it in step 11 and the Terraform module in step 27.
7. Add a fallback polling sync mode to step 17 for Salesforce orgs without CDC access. Gate CDC vs. polling on the detected org edition during the OAuth connect step.
8. Salesforce migration rollback via 'snapshot before import' at 250K contacts will take significant time and storage. Use point-in-time recovery on RDS (already configured) plus a sync_log table as the rollback mechanism — faster and cheaper.
9. Step 20 A/B test: add variant routing logic to step 14 backend — store variant assignment per contact in email_sends, enforce percentage splits at send time via Celery, and add a basic significance calculator to the reports API (step 16).
10. SOC 2 Type II language in step 8 is misleading — you cannot complete Type II in a single planning step. Rename to 'SOC 2 Type II Readiness Framework' and add a note that certification requires a 6–12 month observation period post-launch.

### Missing Elements

1. Elasticsearch (or OpenSearch) service in Docker Compose, Terraform, and infra — or an explicit decision to use PostgreSQL FTS instead.
2. SPF, DKIM, and DMARC DNS configuration for email sending domains. Without these, campaigns will land in spam regardless of CAN-SPAM compliance.
3. API rate limiting implementation — both per-tenant REST API throttling and per-campaign email send rate limiting (required by SendGrid and ISPs).
4. Data retention and deletion policy implementation — GDPR right-to-erasure requires contact hard-delete capability with cascade, not just soft-delete. No step covers this.
5. Application-level observability: structured logging (JSON to CloudWatch), distributed tracing (OpenTelemetry), and error tracking (Sentry or equivalent). CloudWatch alarms in step 27 cover infra but not application errors.
6. Tenant provisioning and onboarding flow — how does a new customer get a database schema, subdomain, and initial admin account? No step covers this.
7. Outbound webhook dispatcher service with retry queue, exponential backoff, dead-letter handling, and HMAC signature signing per delivery.
8. Security penetration test or DAST scan step — the STRIDE threat model (step 6) is design-time only. No dynamic testing of the running application is scheduled before production launch.

### Security Risks

1. Salesforce OAuth tokens stored in the database (referenced in step 6 threat model) need encryption at the application layer, not just AES-256 at rest on disk. If the database is compromised, tokens must not be recoverable in plaintext. No token-level encryption implementation is specified.
2. Custom report builder (step 16) accepts 'arbitrary dimension/metric/filter combinations.' The acceptance criteria notes 'without SQL injection risk' but provides no implementation guidance. A naive ORM query builder with user-supplied field names is a classic injection vector — requires an explicit allowlist of valid columns/tables.
3. Email open tracking pixel (step 14) serves a unique image URL per send. Without rate limiting or nonce validation on the pixel endpoint, it can be abused to probe which contact IDs exist in the system (enumeration attack).
4. CSV bulk import (step 12) with no mention of file size limits, MIME type validation, or malicious content scanning. A crafted CSV with formula injection (=CMD|...) targeting Excel users viewing exports is a known attack vector.
5. Rollback button in step 23 is disabled 'after 48h post-import' — but the rollback endpoint itself, if not protected by an additional confirmation token or admin-only RBAC, could be triggered accidentally or maliciously during the 48h window by any authenticated user.
6. WebSocket connections in step 19 carry deal financial data in real-time. No mention of WebSocket authentication — connections must present and validate JWT on upgrade, not just at REST API layer.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.317741
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

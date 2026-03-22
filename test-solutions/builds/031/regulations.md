# Regulatory Compliance — Project Management

**Domain:** saas
**Solution ID:** 031
**Generated:** 2026-03-22T11:53:39.317397
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **GDPR**
- **ISO 27001**

## 2. Domain Detection Results

- saas (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 5 | LEGAL | Draft Terms of Service, Privacy Policy, DPA (Data Processing Agreement), and SLA | Privacy, licensing, contracts |
| Step 7 | COMPLIANCE | Produce SOC 2 Type II readiness artifacts: control mapping, trust service criter | Standards mapping, DHF, traceability |
| Step 28 | SECURITY | Conduct security review: threat model for multi-tenant data isolation, OWASP Top | Threat modeling, penetration testing |
| Step 32 | SYSTEM_TEST | Execute end-to-end system tests: full sprint lifecycle (create → plan → execute  | End-to-end validation, performance |
| Step 33 | QA | Execute QA test plan: exploratory testing of Kanban, Gantt, sprint, and time tra | Verification & validation |
| Step 34 | COMPLIANCE | Collect and organize SOC 2 Type II evidence artifacts: access control logs, chan | Standards mapping, DHF, traceability |

**Total tasks:** 36 | **Compliance tasks:** 6 | **Coverage:** 17%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 3 | ISO 27001 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |

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
| developer | 19 | Engineering |
| regulatory_specialist | 3 | Compliance |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| marketing_strategist | 1 | Operations |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| financial_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| operations_manager | 1 | Operations |
| system_tester | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This is an ambitious, well-structured plan with thoughtful dependency ordering and appropriate technology choices for most components. However, it has three critical-path failures that would prevent a viable SaaS business from operating: (1) there is no billing implementation — the product cannot charge customers; (2) SOC 2 Type II is fundamentally misunderstood as an artifact collection exercise rather than a 6-12 month control observation period, making the compliance target unachievable on this timeline; and (3) the schema-per-tenant PostgreSQL approach will hit a hard scaling ceiling well within the first year of SMB customer growth. Beyond these blockers, the Gantt renderer ambiguity is a months-long wildcard, the test-after-build waterfall structure bakes in architectural debt, and the absence of email notifications, GDPR implementation, data import tooling, and feature flags represent significant gaps for a production SaaS. The security posture is adequate in intent but has concrete implementation gaps — particularly around prompt injection, search_path sanitization, and token storage — that will be introduced by developers following standard framework patterns. Score of 54 reflects a plan that would produce a functional demo but not a shippable, revenue-generating, compliance-ready SaaS product without substantial rework in the billing, compliance, and data architecture layers.

### Flaws Identified

1. Schema-per-tenant PostgreSQL hits pg_class and connection bloat at ~500-1000 tenants. For SMB SaaS targeting hundreds of customers, this ceiling will be reached in year 1. Row-level security (RLS) is the correct pattern for this scale, and there is no migration path defined from schema-per-tenant to RLS.
2. Step 22 defers the Gantt renderer decision to 'DHTMLX or custom Canvas' — this is a 2-4 month wildcard. DHTMLX Gantt commercial license costs $800+/dev and has redistribution restrictions. A custom Canvas Gantt with correct dependency arrow routing, zoom levels, and 60fps for 500 tasks is one of the hardest UI problems in this stack. Treating it as a parenthetical is a critical planning failure.
3. Fractional indexing (step 12) without a rebalancing strategy will cause floating-point precision exhaustion after thousands of inserts between the same two positions. The acceptance criteria don't require a rebalancing procedure, so this technical debt ships to production.
4. Step 31 (write tests) depends on steps 12–18 — tests are authored AFTER all backend modules are complete. This is pure waterfall. No TDD, no integration tests written alongside feature code, no early regression signal. By the time tests are written, architectural mistakes in steps 12–18 are fully baked in.
5. Jira bidirectional sync (step 18) is severely underspecified. Jira Cloud webhooks miss events under load, field mappings between Jira and custom schemas drift silently, and Atlassian's OAuth 2.0 (3LO) token refresh behavior differs by plan. No retry queue, no sync-state reconciliation job, no backfill strategy for missed events. 'Last-write-wins with audit' is not a conflict strategy — it is conflict acknowledgment after the fact.
6. SOC 2 Type II requires a 6–12 month observation period of implemented controls. Step 34 treats evidence collection as a post-build artifact gathering exercise. Controls must be live and auditable from day one of the observation window. The plan has no start-of-observation trigger, meaning the SOC 2 audit readiness target cannot be met on this linear timeline regardless of how well the other steps execute.
7. No billing/subscription implementation step exists anywhere in 36 steps. Pricing tiers are defined (steps 2–4), financial models built (step 4), but there is no Stripe integration, no seat counting, no subscription lifecycle management, no dunning logic, and no usage metering. A SaaS product without a billing system cannot collect revenue.
8. Step 17 specifies Slack notification delivery but does not account for Slack API rate limits: Tier 1 is 1 req/min, Tier 2 is 20 req/min. A workspace with 50 users and active sprint activity will hit these limits immediately. No message queuing, batching, or backpressure strategy is defined.
9. The WebSocket conflict resolution strategy ('last-write-wins with optimistic locking') is inadequate for collaborative board editing. Two users reordering cards simultaneously will silently discard one user's changes. No CRDT or operational transform approach is considered, and the acceptance criteria don't test concurrent edit scenarios.
10. Step 19 hardcodes 'claude-sonnet-4-6' as the LLM provider with no fallback, no per-tenant cost controls, no rate limiting on AI inference calls, and no context window management for workspaces with 1000+ tasks. A single large project's task list can exceed the model's context window, causing silent truncation or errors with no graceful degradation.
11. Timer persistence (step 24) uses 'localStorage + server sync' with no defined conflict resolution. If the server timer and localStorage timer diverge (browser crash, offline usage, multi-tab), the plan provides no tiebreaker. Time tracking errors in a billing-adjacent feature are a support and trust liability.
12. Steps 1–7 are pure research and documentation before a single line of production code is written. In a market with Asana, Linear, Monday.com, and ClickUp all shipping weekly, this waterfall front-load means 3–4 months of zero validated learning. Critical assumptions about positioning and ICP remain untested until the product ships.

### Suggestions

1. Replace schema-per-tenant with row-level security (RLS) on a shared schema. Use a `workspace_id` column on all tables with `CREATE POLICY` statements. This scales to millions of tenants without connection pool exhaustion and is supported natively by Supabase if you want managed RLS.
2. Make a hard architectural decision on the Gantt renderer in step 3 (PRD), not step 22. Evaluate react-gantt-chart, Bryntum Gantt (commercial, production-grade), or DHTMLX with a legal review of redistribution terms. Spike the renderer before committing to Canvas-from-scratch.
3. Add a step between 10 and 11 for fractional indexing implementation and rebalancing strategy. Use the Lexorank algorithm (Jira's own approach) or the `fractional-indexing` npm package, and schedule a background rebalancing job that fires when gap density drops below a threshold.
4. Flip steps 31 and 11–18: write integration test scaffolding in step 10 alongside config setup, and require each backend step (12–18) to ship with its own tests. Gate step 32 on passing tests, not on test authorship.
5. Add a step 10.5: Billing Integration (Stripe). Implement subscription creation, seat-based metering, webhook handlers for payment failures, and a customer portal link. This is critical path for revenue and should precede any marketing spend.
6. Add a step 10.6: Transactional Email System. Integrate SES or SendGrid for task assignment notifications, sprint reminders, timesheet approval requests, and password reset. Slack notifications (step 17) are a secondary channel, not a replacement.
7. Add a GDPR/CCPA implementation step (not just document drafting). Right-to-erasure requires a `DELETE /users/{id}/data` endpoint that cascades deletion across all tenant schemas while preserving anonymized audit log entries. Data portability requires a `GET /export` endpoint. These are legal obligations, not documentation tasks.
8. For the Slack integration, implement a notification queue (Redis-backed with Celery) that batches and rate-limits outbound messages per workspace, with exponential backoff on 429 responses and a dead-letter queue for undeliverable notifications.
9. Add Celery Flower or Grafana + Prometheus worker metrics to step 29. Background job failure visibility is not optional when time tracking, Jira sync, and AI suggestions all run async — silent job failures will surface as user complaints, not alerts.
10. Start the SOC 2 Type II observation period on day one of staging deployment (step 29), not after step 34. Hire a compliance consultant or use Vanta/Drata to instrument controls automatically from the first deployment. Document this explicitly in step 7.
11. Add a feature flag system (step 10.5 or as part of step 10). LaunchDarkly or a simple database-backed flag table. Step 19 (AI features) and step 18 (Jira sync) are high-risk — they need kill switches without a redeploy.
12. Step 9 should document a connection pooling strategy: PgBouncer in transaction mode for the API tier, with a separate long-lived connection pool for Celery workers. Without this, schema-per-tenant search_path switching will cause connection exhaustion under load.

### Missing Elements

1. Billing and subscription management: Stripe integration, seat counting, upgrade/downgrade flows, dunning, invoice generation. Zero coverage in 36 steps.
2. Email notification system: no transactional email provider, no email templates, no delivery tracking. Slack is a secondary channel — email is the primary async notification channel for most business users.
3. GDPR/CCPA implementation (not just documents): right-to-erasure endpoint, data portability export, consent management, data retention policies enforced in code.
4. Data import/migration tooling: no step for importing from Asana, Jira, Monday.com, or CSV. This is a top-3 adoption blocker for SMB customers switching tools.
5. Audit log partitioning and archival strategy: the audit_log table will grow at O(write_operations) indefinitely. No time-based partitioning, no archival job, no retention policy.
6. File upload security controls: no virus scanning (ClamAV or third-party), no MIME type validation beyond extension, no per-workspace storage quota enforcement.
7. PgBouncer or equivalent connection pooling configuration: missing from both step 9 (schema design) and step 10 (infra config).
8. Webhook signature verification implementation: Slack signs payloads with HMAC-SHA256, Jira uses a secret token header. Steps 17 and 18 define the webhook receiver but the acceptance criteria don't require signature verification to be tested.
9. Multi-region or data residency strategy: step 5 flags GDPR data residency as a compliance concern, but no infrastructure step addresses EU vs US data placement for enterprise customers.
10. Soft-delete and data recovery: no mention of soft-delete (`deleted_at` column) for tasks, projects, or workspaces. Accidental deletion with no recovery path is a support and churn risk.
11. AI cost guardrails: no per-workspace monthly AI call budget, no token usage tracking, no circuit breaker when LLM provider is down. Step 19 can run unbounded inference costs against a single LLM provider.

### Security Risks

1. Schema-per-tenant with dynamic `SET search_path = {tenant_name}` is vulnerable to search_path injection if tenant names are not strictly sanitized (alphanumeric + underscore only). A tenant named `public; DROP SCHEMA public` would be catastrophic. No sanitization requirement is stated in step 9.
2. Zustand global state store (step 20): if the store is configured with persistence middleware (common pattern), OAuth access tokens may be written to localStorage, directly contradicting the step 28 requirement that tokens never live in localStorage. This is an implementation gap that will likely be introduced by a developer following standard Zustand patterns.
3. Jira OAuth 2.0 tokens stored in the database need field-level encryption, not just encryption-at-rest on the RDS volume. An application-level SQL injection that dumps the integrations table would expose all Jira tokens in plaintext. No field-level encryption requirement exists in step 9 or 18.
4. S3 file attachments (step 11): presigned URLs with long expiry times (>1 hour) combined with no file type validation create a stored XSS vector if SVG or HTML files are uploaded and served with permissive Content-Type headers. CloudFront distribution must set `Content-Disposition: attachment` for all non-image types.
5. AI assistant (step 19) ingests task titles, descriptions, and comments as LLM context. A malicious user can embed prompt injection payloads in task descriptions that alter the AI's suggestions for other users in the same workspace. No input sanitization or prompt injection defense is specified.
6. Webhook endpoints for Slack and Jira are unauthenticated HTTP receivers. Without HMAC signature verification enforced at the middleware level (not just recommended in docs), these endpoints are open to spoofed event injection — an attacker can fake a Jira issue_deleted event to remove tasks from boards.
7. Redis pub/sub for WebSocket broadcasts (step 12): if channel naming uses workspace/tenant ID without cryptographic validation, a client that guesses another tenant's channel name could subscribe and receive cross-tenant real-time updates. Channel names must be unguessable (UUID-based), not sequential integers.
8. Rate limiting is specified at 1000 req/min per tenant (step 8) but no step implements it. Step 28 only verifies it. If the implementation step is missing, the verification step tests a control that was never built.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.317436
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

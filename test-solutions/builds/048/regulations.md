# Regulatory Compliance — Loyalty Rewards

**Domain:** ecommerce
**Solution ID:** 048
**Generated:** 2026-03-22T11:53:39.322378
**HITL Level:** standard

---

## 1. Applicable Standards

- **PCI DSS**
- **GDPR**
- **CCPA**

## 2. Domain Detection Results

- ecommerce (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 5 | LEGAL | Draft legal artifacts: Terms of Service, Privacy Policy (GDPR/CCPA compliant), M | Privacy, licensing, contracts |
| Step 6 | SECURITY | Threat model the loyalty platform: STRIDE analysis for point fraud vectors, PCI  | Threat modeling, penetration testing |
| Step 7 | COMPLIANCE | Produce PCI DSS compliance artifacts: data flow diagram showing cardholder data  | Standards mapping, DHF, traceability |
| Step 18 | QA | QA test planning and execution: test case design for all loyalty flows, explorat | Verification & validation |
| Step 19 | SECURITY | Execute security review: OWASP Top 10 assessment against deployed staging enviro | Threat modeling, penetration testing |

**Total tasks:** 22 | **Compliance tasks:** 5 | **Coverage:** 23%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | PCI DSS compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |
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
| developer | 8 | Engineering |
| regulatory_specialist | 3 | Compliance |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| marketing_strategist | 1 | Operations |
| business_analyst | 1 | Analysis |
| ux_designer | 1 | Design |
| financial_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| operations_manager | 1 | Operations |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 58/100 (FAIL) — 1 iteration(s)

**Summary:** This is a well-structured, comprehensive plan that covers the right problem surface — most loyalty platform failures come from skipping the compliance, fraud, and financial modeling steps that this plan includes. However, it has a critical architectural gap cluster that will cause a costly mid-build reroute: there is no authentication system, no billing system, and no notification system — three of the most foundational infrastructure components for any SaaS product. The POS integration architecture is optimistic about member identification (assuming PII arrives in webhooks when it typically does not), and the concurrency handling for the points engine declares correctness without specifying the mechanism that achieves it. PostgreSQL RLS under connection pooling is a known production footgun that has caused cross-tenant data leaks in multiple loyalty platform deployments. The sequencing puts DevOps after QA, leaving the testing phase with no staging environment. Fixing the auth/billing/notifications gap requires inserting 3 substantial steps, and the POS architecture may require redesigning step 13 after a discovery spike on each provider's customer data API. This plan is a solid 70-point foundation that needs roughly 20 points of gap-filling before it's production-credible.

### Flaws Identified

1. No authentication implementation step exists. JWT is declared in the OpenAPI spec (step 9) and referenced in frontend (steps 15-16), but no step builds auth: member registration/login, merchant login, password reset, token refresh, or MFA. This is not a minor gap — it blocks every protected endpoint from being testable.
2. Stripe integration is orphaned. STRIPE_KEY appears in .env.example (step 10) but zero steps implement merchant billing, subscription management, plan upgrades, or invoice generation. The financial model exists (step 4) but the system that collects revenue does not.
3. Transactional email and SMS infrastructure is completely absent. No step creates a SendGrid/SES/Postmark integration. Birthday reward notifications, tier upgrade emails, referral completion alerts, and point expiry warnings are core to the product's value proposition and retention loop — none are built.
4. Concurrent redemption race condition is unresolved. Step 11 says 'atomic transaction' but does not specify SELECT FOR UPDATE, optimistic locking, or a distributed lock strategy. On any moderately trafficked deployment, two concurrent redemption requests for the same member balance will both pass the balance check before either commits. This is the most common production failure mode for loyalty platforms.
5. PostgreSQL RLS + SQLAlchemy + connection pooling is a known failure combination. PgBouncer in transaction pooling mode (the standard deployment) strips session-level SET LOCAL statements, which is how RLS tenant context is typically injected. The plan assumes RLS works; in practice it silently fails under pooled connections, leaking cross-tenant data. No mitigation is specified.
6. POS member identification is architecturally naive. The plan assumes POS webhooks deliver email/phone/card number. Square, Clover, and Toast webhooks deliver order events — customer PII is not included in webhook payloads by default and requires separate customer lookup API calls with merchant-level OAuth scope. This changes the integration architecture substantially.
7. Toast requires partner program approval and has a 4-8 week onboarding process before API access is granted. It cannot be treated as a same-sprint deliverable alongside Square.
8. Multi-touch referral attribution is declared in step 2 but never resolved in step 12. The implementation only describes last-event mechanics. Multi-touch requires a resolution model (first-touch, linear, time-decay) and the plan never defines it — this will generate merchant disputes at launch.
9. GDPR Right to Erasure (Art. 17) and Data Portability (Art. 20) have no technical implementation. Step 5 drafts the Privacy Policy but no backend step implements the deletion pipeline. Soft deletes do not satisfy Art. 17 — all downstream data (vector store, analytics aggregates, audit logs, Redis cache) must also purge the member. This is a regulatory liability, not a documentation gap.
10. Birthday reward timezone handling is absent. The daily cron job runs in server timezone (UTC assumed). A member in UTC+9 whose birthday starts at midnight local time will either miss or double-receive rewards depending on when the job fires. No timezone-aware trigger logic is specified.
11. DevOps (step 20) is sequenced after QA (step 18), meaning there is no staging environment during integration testing. Steps 17-18 test against... what? Local Docker Compose cannot replicate RDS failover, ElastiCache behavior, or EKS network policies. The pipeline puts infrastructure last but testing needs it earlier.
12. No load testing step exists. The SLA targets p99 500ms for points transactions and 5s webhook processing but no step validates these under realistic concurrency. Points engine under Black Friday load (thousands of concurrent POS webhook deliveries) is entirely untested.
13. Point expiry legal requirements are unaddressed. Twelve US states have unclaimed property (escheatment) laws that may apply to unredeemed loyalty points above a threshold. Neither the legal step (5) nor the financial model (step 4) addresses escheatment liability or compliance reporting.
14. Analytics cold-start is unmitigated. Redis cache (5-min TTL) is populated on first query. For a merchant with 500K transactions, the first post-cache-miss analytics query will hit PostgreSQL cold with no materialized views or background aggregation jobs. The 500ms SLA will be violated on every cache miss.
15. Celery Beat scheduler configuration is never built. Step 12 defines birthday_cron.py and referral_payout_job.py but no step configures the Celery Beat schedule, task routing, worker concurrency, or task failure alerting. The jobs exist as files but will never execute.

### Suggestions

1. Insert a dedicated AUTH step (between steps 10 and 11) implementing: member JWT issuance with RS256, merchant OAuth2 with PKCE, refresh token rotation, rate-limited login, and a password reset flow. This unblocks every subsequent frontend and backend step.
2. Insert a BILLING step implementing Stripe Billing: merchant subscription creation on signup, plan tier enforcement via feature flags, webhook handler for payment failures (suspend program on non-payment), and invoice PDF generation. Without this the platform has no revenue.
3. Insert a NOTIFICATIONS step implementing transactional email (SES or SendGrid) and optional SMS (Twilio): welcome email on enrollment, tier upgrade/downgrade notifications, point expiry warnings (7-day and 1-day), birthday reward delivery, referral completion confirmation. Wire these as async Celery tasks triggered by domain events.
4. Replace the vague 'atomic transaction' in step 11 with an explicit concurrency contract: SELECT FOR UPDATE on the member balance row for redemptions, plus a distributed Redis lock keyed by member_id with a 5-second TTL for point earn operations that touch balance. Document the lock acquisition timeout and retry behavior.
5. Replace PostgreSQL RLS as the multi-tenancy mechanism with application-layer tenant scoping. Inject merchant_id as a mandatory WHERE clause in all ORM queries via a SQLAlchemy event listener or base query class. This is less elegant but reliable under connection pooling. If RLS is retained, mandate PgBouncer in session pooling mode and document the performance trade-off.
6. Redesign the POS integration architecture: each adapter must make a synchronous customer lookup API call (using POS-specific customer API, not just the webhook payload) to resolve the loyalty member before processing the transaction. Document per-POS API rate limits and the fallback when customer lookup fails.
7. Add explicit GDPR technical implementation tasks to step 8 or as a new step: soft-delete cascade that zeroes PII fields, a member_deletion_requests queue processed by a nightly job, and a data export endpoint returning JSON of all member data. These must be tested before launch.
8. Resequence DevOps (step 20) to run in parallel with step 10 (config) or immediately after. Staging environment must exist before integration tests (step 17) are written. Add a STAGING_DEPLOY gate that steps 17-19 depend on.
9. Add a LOAD_TEST step (between steps 17 and 18): k6 or Locust scenarios for concurrent point earning (500 RPS), concurrent redemption (simulate 50 concurrent redemptions per member), and POS webhook burst (1000 webhooks in 10 seconds). Gate deployment on p99 latency SLA being met under these loads.
10. Resolve multi-touch referral in step 2 acceptance criteria: mandate the BRD explicitly choose a single attribution model (recommend last-touch for simplicity), document it in the referral program terms (step 5), and implement exactly that model in step 12. Remove 'multi-touch' ambiguity or it will ship as last-touch with incorrect documentation.
11. Add birthday timezone logic to step 12: store member timezone (or derive from merchant timezone as fallback), and trigger the birthday reward when the member's local date matches their birth month/day, not UTC date.
12. Add Celery Beat configuration to step 10 or 12: CELERY_BEAT_SCHEDULE dict with cron expressions for birthday_daily_job (02:00 UTC), referral_payout_weekly_job, and point_expiry_nightly_job. Include task failure alerting via Datadog custom metric.

### Missing Elements

1. Authentication system (member auth, merchant auth, token refresh, MFA) — foundational, blocks all protected endpoints
2. Merchant billing and subscription management (Stripe integration) — the platform has no way to collect revenue
3. Transactional email and SMS notification service — removes the core retention mechanics from the product
4. Member data import/migration tooling — merchants migrating from existing programs have no path to bring their member base
5. Merchant self-service signup flow — how does a new merchant create an account, verify their email, select a plan, and connect their first POS?
6. Feature flag / plan enforcement system — the financial model defines feature gating by tier but no code enforces which features a starter vs. enterprise merchant can access
7. Materialized views or background aggregation jobs for analytics — cold-cache query performance will violate the 500ms SLA
8. Escheatment compliance review and reporting — required for US deployment if the platform operates in states with unclaimed property laws
9. POS OAuth flow for customer data access — needed for customer PII lookup in Square/Clover/Toast before point processing can occur
10. Webhook registration UI and API — merchants need a self-service way to retrieve their webhook URL, rotate signing secrets, and view delivery logs
11. GDPR technical controls (erasure pipeline, data export endpoint, consent management for marketing emails)
12. Load and performance testing step
13. Toast partner onboarding process — this has a multi-week external dependency that must be started before step 13 is attempted

### Security Risks

1. Concurrent redemption double-spend: without explicit SELECT FOR UPDATE, two simultaneous redemptions will both pass the balance validation check. The acceptance criteria in step 19 say 'test confirms atomic transaction prevents double-spend' but the implementation in step 11 never specifies the locking mechanism — the test will be written against code that does not actually prevent it.
2. JWT algorithm confusion: step 19 tests for this but the actual enforcement (RS256 hardcoded, alg header ignored in validation) must be implemented in step 11 auth middleware. If the test is written before the fix is in place, it will fail and be treated as a test bug rather than a vulnerability.
3. Birthday date manipulation: members can update their profile birthday to claim rewards repeatedly. No step implements birthday field immutability after first verification, birthday change audit logging, or a cooldown period after birthday modification.
4. Redis idempotency key expiry creates a replay window: 24h TTL means a webhook replayed after 24h1m will be processed as a new transaction. For high-value transactions, this is an exploitable fraud vector. Idempotency should be persisted to PostgreSQL with longer retention, using Redis only as a fast-path cache.
5. RLS tenant isolation silent failure under pooled connections (detailed in flaws above) — the most severe data breach risk in the architecture. Merchant A reading Merchant B's member PII is a GDPR breach, not a bug.
6. Referral device fingerprinting bypass: same-device detection (step 12) is trivially bypassed with incognito mode or a different browser. Stronger signals (email domain analysis, shipping address similarity, behavioral velocity) are not specified.
7. HMAC webhook validation without timestamp: the acceptance criteria in step 13 validate the HMAC signature but do not require a timestamp header (e.g., X-Timestamp within ±5 minutes). Without timestamp validation, a captured valid webhook can be replayed indefinitely — the HMAC alone does not prevent replay.
8. Merchant API key stored and transmitted insecurely: no step specifies API key hashing at rest (keys should be stored as bcrypt/PBKDF2 hashes with only a prefix shown in UI), key rotation mechanism, or scoped permissions per key. A leaked key with full access is a complete merchant account takeover.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.322412
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

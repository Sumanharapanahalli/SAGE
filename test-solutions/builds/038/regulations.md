# Regulatory Compliance — Scheduling App

**Domain:** saas
**Solution ID:** 038
**Generated:** 2026-03-22T11:53:39.319447
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **GDPR**
- **PCI DSS**

## 2. Domain Detection Results

- saas (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | LEGAL | Draft Terms of Service, Privacy Policy (GDPR/CCPA compliant), Data Processing Ag | Privacy, licensing, contracts |
| Step 20 | SECURITY | Conduct security review: threat model for scheduling_app (STRIDE), OWASP Top 10  | Threat modeling, penetration testing |
| Step 21 | COMPLIANCE | Produce SOC 2 Type I readiness artifacts: control matrix mapping to Trust Servic | Standards mapping, DHF, traceability |

**Total tasks:** 28 | **Compliance tasks:** 3 | **Coverage:** 11%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 3 | PCI DSS compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |

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
| developer | 13 | Engineering |
| ux_designer | 2 | Design |
| regulatory_specialist | 2 | Compliance |
| qa_engineer | 2 | Engineering |
| marketing_strategist | 1 | Operations |
| business_analyst | 1 | Analysis |
| financial_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| product_manager | 1 | Design |
| devops_engineer | 1 | Engineering |
| operations_manager | 1 | Operations |
| data_scientist | 1 | Analysis |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 63/100 (FAIL) — 1 iteration(s)

**Summary:** This is an above-average build plan with comprehensive feature coverage, clear acceptance criteria, and good separation of concerns between MVP and v1. However, it has three categories of critical gaps that will cause production failures: (1) concurrency — the booking conflict detection, OAuth token refresh race, and Celery task durability are all specified at the 'we will handle this' level without concrete mechanisms, which historically means they are not handled; (2) third-party integration operational realities — Google Calendar push channel renewal, Google OAuth app verification timelines, and Stripe Connect KYC complexity are each multi-week blockers that are invisible in the current plan; (3) data isolation and security fundamentals — no Row-Level Security, no SSRF protection on outbound webhooks, no key management strategy for OAuth tokens. The AI agents step (27) has acceptance criteria that are impossible to meet at launch. Scoring 63 for an MVP: the feature decomposition and documentation artifacts are solid, but the concurrency and integration gaps are concrete failure modes, not theoretical risks. A developer following this plan faithfully will ship a product that silently stops syncing calendars on day 8, leaks tokens under concurrent load, and blocks launch waiting for Google OAuth verification.

### Flaws Identified

1. Step 11 mandates concurrent conflict detection but specifies no locking strategy. PostgreSQL advisory locks, row-level locks, and optimistic concurrency with version columns all have different failure modes under load. Without specifying which approach, two concurrent bookings of the same slot will race. This is the #1 production failure mode in scheduling systems and the plan hand-waves it.
2. Step 12 omits Google Calendar push notification channel renewal. Channels expire every 7 days and must be renewed before expiry or the sync silently stops. No keepalive job, no channel registry, no expiry tracking. This will cause calendar sync outages starting on day 8 of production.
3. Step 13 introduces Stripe Connect for marketplace payouts with zero acknowledgment of KYC/onboarding complexity. Express and Custom Connect accounts require identity verification flows, payout schedule configuration, and Stripe's own review process. This is a multi-week integration, not a line item.
4. pytz is deprecated since Python 3.9 in favor of zoneinfo (stdlib). Step 11 specifies 'python-dateutil + pytz'. Using pytz for future DST transitions in 2025+ timezone data is a reliability risk; IANA database updates via tzdata package are required and not mentioned.
5. Step 17 (booking page with PaymentStep component) has no dependency on Step 13 (Stripe payments backend). The dependency graph is broken — frontend payment integration cannot be built without the backend payment API.
6. Step 27 no-show predictor requires >70% precision but there is zero historical booking data at launch. Acceptance criteria demand ML model validation against 'historical test data' that does not exist. This step cannot pass its own criteria at launch.
7. Multi-tenant data isolation is absent from the schema design (Step 8). The schema has organizations table but no PostgreSQL Row-Level Security policies or schema-per-tenant strategy. A misconfigured query at the ORM layer can leak one org's bookings to another — no structural guardrail prevents this.
8. OAuth token refresh race condition is unaddressed across Steps 12 and 15. Multiple concurrent API requests with an expired token will all attempt refresh simultaneously, invalidating each other's refresh tokens. No distributed lock around token refresh is specified.
9. Step 14 uses Celery + Redis for reminder scheduling but specifies no Redis HA strategy. If Redis restarts, all scheduled reminder tasks are lost. No mention of Redis persistence (AOF/RDB), Sentinel, or task result backend durability.
10. Feature gating between subscription tiers (defined in Step 6, billed in Step 13) has no implementation step. There is no middleware, permission layer, or entitlement service connecting a user's active Stripe subscription plan to which features they can access.
11. Step 9 documents rate limiting headers in the OpenAPI spec but no implementation step adds rate limiting to the API. Rate limiting on /bookings and /availability endpoints is critical for preventing abuse of the public booking page.
12. Google Calendar OAuth requires app verification by Google for the calendar.events scope before public launch. This is a multi-week review process with a required OAuth consent screen review. It is entirely absent from the plan and will block production launch.

### Suggestions

1. Add an explicit locking strategy to Step 11: define a bookings.slot_lock advisory lock key pattern or a booking_holds table with TTL (e.g., 10 min) to hold a slot during payment. Include a cleanup job for expired holds. Test with at least 50 concurrent booking attempts to the same slot.
2. Add a calendar_channel_registry table in Step 8 and a scheduled job (every 6 days) in Step 12 to renew Google Calendar push notification channels before they expire. Include a dead-channel detector that falls back to polling.
3. Scope Stripe Connect explicitly in Step 13: decide on Standard vs Express vs Custom accounts now. Standard is 80% simpler and covers most use cases. Document this as an ADR. If marketplace payouts are MVP, budget 3-4 weeks for Stripe Connect onboarding flows alone.
4. Replace pytz with zoneinfo + tzdata in Step 11. Change the acceptance criteria to explicitly test a booking made today for a slot 6 months in the future across a DST boundary (e.g., America/New_York in March).
5. Add dependency edge from Step 13 to Step 17. Also add Step 12 (calendar sync) as a dependency of Step 17 since the confirmation page shows 'Add to Google Calendar' links that require the OAuth flow.
6. Defer Step 27 (AI agents) or replace the precision acceptance criterion with 'generates booking brief from available CRM data within 10s' — drop the no-show predictor until 6 months of production data exists. Ship the summarizer first.
7. Add PostgreSQL RLS policies to Step 8 as a first-class deliverable: CREATE POLICY per table scoped to organization_id. Test with a cross-tenant query in integration tests that must return 0 rows.
8. Add a token_refresh_lock Redis key per calendar connection in Step 12. Only one process may hold the lock; others must wait and re-read the refreshed token rather than retrying refresh.
9. Add Redis persistence configuration (AOF enabled, fsync everysec) and a Celery task result backend (PostgreSQL or Redis with persistence) to Step 14. Document RPO for reminder delivery: acceptable to lose reminders scheduled within the last N seconds of a Redis restart.
10. Add a feature entitlement step (or expand Step 10) defining a plan_features table and a middleware decorator (@require_plan('team')) that checks the org's active Stripe subscription. Wire Stripe webhook subscription.updated to update the org's plan in DB.
11. Implement application-level rate limiting in Step 10 bootstrap using slowapi (FastAPI middleware): 60 req/min on public booking endpoints, 10 req/min on /auth/. Add to docker-compose as nginx or rely on Railway's native rate limiting — pick one and document it.
12. Add Google OAuth app verification to the project roadmap between Steps 12 and 24. Submit for review immediately after Step 12 is complete. Do not plan a public launch until verification is approved — plan 4-6 weeks.

### Missing Elements

1. Email deliverability setup: SPF, DKIM, and DMARC records for SendGrid sending domain. Without these, booking confirmations and reminders will hit spam folders at Gmail and Outlook. Zero mention in Steps 14 or 24.
2. Webhook idempotency: Stripe and calendar webhooks can deliver duplicate events. No idempotency key table or processed_event_ids deduplication step is specified. Double-processing a payment.succeeded event could double-confirm a booking.
3. GDPR right to erasure implementation: Step 4 creates a Privacy Policy promising erasure rights, but there is no implementation step for a data deletion workflow (cascade delete user data, anonymize booking history, propagate deletion to CRM integrations).
4. Database connection pooling: FastAPI + PostgreSQL at production load requires PgBouncer or asyncpg connection pooling. Missing from Step 10 bootstrap and Step 24 infra. Will cause connection exhaustion under moderate load.
5. Database backup and recovery: No PITR (Point-in-Time Recovery), no automated snapshot schedule, no RTO/RPO targets. Step 25 has a db_failover runbook but no underlying backup infrastructure to execute against.
6. Booking slug enumeration protection: Public booking pages need non-guessable slugs (UUID or random string) and rate limiting on the public route. Sequential or name-based slugs allow scraping all hosted calendars.
7. iCal feed authentication: Step 12 generates iCal feeds but no mention of whether they are public or token-authenticated. Unauthenticated feeds leak host booking data (invitee names, meeting topics) to anyone with the URL.
8. Celery worker scaling specification: Step 14 specifies Celery + Redis but never defines how workers scale independently from the API tier. At high booking volume, reminder workers queue up. No autoscaling policy or worker count baseline.
9. Content Security Policy for iframe embed: Step 17 requires embed support but CSP headers that block iframe embedding are a common production surprise. frame-ancestors policy needs explicit configuration and testing against common embed targets (Wordpress, Squarespace, Webflow).
10. Materialized view refresh strategy for analytics (Step 26): REFRESH MATERIALIZED VIEW blocks concurrent reads by default unless CONCURRENTLY is used, which requires a unique index. Neither is specified. Hourly refresh on a large bookings table will cause analytics query timeouts.

### Security Risks

1. SSRF via generic webhook outbound (Step 15): The outbound webhook URL is user-configurable. Without an allowlist or URL validation layer, a malicious user can point it at http://169.254.169.254 (AWS IMDS) or internal network services. The plan specifies HMAC signing of outbound payloads but says nothing about validating the destination URL.
2. OAuth token key management: Step 12 specifies tokens 'encrypted at rest (AES-256)' but not where the encryption key lives. If it is in an environment variable alongside the data, it provides no protection against a DB dump. KMS (AWS KMS, GCP Cloud KMS) or a secrets manager is required — not mentioned.
3. Open redirect in OAuth callback: OAuth2 callback handling for Google and Outlook is a well-known vector for open redirect attacks if the state parameter or redirect_uri is not validated server-side. Not mentioned in Step 20's OWASP assessment scope.
4. Stripe webhook timestamp validation missing: Step 13 specifies signature verification but Stripe webhooks should also reject events with timestamps older than 5 minutes (replay window). The plan omits this check, leaving a replay window open.
5. Booking page slug enumeration: If booking page slugs are derived from user names or are sequential integers, an attacker can enumerate all hosts. Combined with calendar availability data (public by design), this leaks host schedules to scrapers. No mention of anti-enumeration measures.
6. JWT secret rotation: Step 9 specifies JWT auth but no mention of secret rotation strategy, token revocation list, or short expiry + refresh token pattern. A leaked JWT with a long TTL cannot be invalidated without a revocation mechanism.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.319478
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

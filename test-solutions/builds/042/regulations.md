# Regulatory Compliance — Headless Storefront

**Domain:** ecommerce
**Solution ID:** 042
**Generated:** 2026-03-22T11:53:39.320614
**HITL Level:** standard

---

## 1. Applicable Standards

- **PCI DSS**
- **GDPR**
- **WCAG 2.1**

## 2. Domain Detection Results

- ecommerce (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | LEGAL | Draft terms of service, privacy policy (GDPR/CCPA), cookie consent policy, and I | Privacy, licensing, contracts |
| Step 5 | SECURITY | Perform threat model for the headless storefront: API key exposure, XSS via prod | Threat modeling, penetration testing |
| Step 18 | COMPLIANCE | Produce PCI DSS SAQ-A compliance artifacts: scoping document confirming cardhold | Standards mapping, DHF, traceability |
| Step 22 | QA | Create QA test plan: functional test cases for all user journeys, cross-browser  | Verification & validation |
| Step 23 | SYSTEM_TEST | Write Playwright E2E test suite: full purchase flow (browse → search → PDP → car | End-to-end validation, performance |

**Total tasks:** 25 | **Compliance tasks:** 5 | **Coverage:** 20%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | PCI DSS compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |
| 2 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 3 | WCAG 2.1 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 11 | Engineering |
| regulatory_specialist | 2 | Compliance |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| marketing_strategist | 1 | Operations |
| financial_analyst | 1 | Analysis |
| ux_designer | 1 | Design |
| legal_advisor | 1 | Compliance |
| product_manager | 1 | Design |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 58/100 (FAIL) — 1 iteration(s)

**Summary:** This is a structurally comprehensive plan that covers the right surface area for a headless ecommerce MVP, but it contains a critical unresolved fork — the Shopify vs Medusa backend decision — that contaminates every downstream step with ambiguity. Approximately 8 of 25 steps produce artifacts that are partially or wholly wrong depending on which backend is ultimately chosen, and no step forces the decision. Beyond this architectural defect, the plan has three production-failure-class gaps: cart split-brain between client and server with no reconciliation strategy, no PSD2/SCA 3DS handling that will cause silent checkout failures for EU users, and no tax computation layer that creates legal compliance exposure from day one. The security work is better than average (STRIDE model, PCI SAQ-A, SBOM) but is scheduled in the wrong order — PCI scope must precede payment implementation, not follow it. The score reflects a plan that would produce a demo-quality build that fails real users in checkout and fails regulators in EU markets without additional rework passes on these specific gaps.

### Flaws Identified

1. Backend decision (Shopify vs Medusa) is never forced — Step 9 says 'if using Shopify only, skip migration setup', meaning the entire database schema, API design, and subscriber architecture could be thrown away mid-build. This is not a design choice, it's deferred technical debt disguised as flexibility.
2. Step 7 outputs both api_schema.graphql and openapi.yaml, but Medusa v2 exposes REST only — there is no GraphQL layer. If Shopify is chosen, the REST OpenAPI spec is irrelevant. The API contract deliverable is contradictory and will produce dead artifacts regardless of which backend is picked.
3. Cart state is split between Zustand/localStorage (client) and Medusa CartService (server). The plan has no strategy for guest-to-authenticated cart merge, concurrent-tab cart conflicts, or Medusa cart expiry (default 7 days) vs localStorage persistence. This is a known ecommerce production bug class.
4. ISR with revalidate: 60 on PDP means a product that sells out stays purchasable for up to 60 seconds post-depletion. No on-demand revalidation (Next.js revalidateTag/revalidatePath) is wired to the Medusa product update subscriber. The plan will ship a known oversell race condition.
5. PSD2/SCA Strong Customer Authentication is completely absent. Any EU customer paying with a European-issued card will trigger 3DS authentication. Stripe Elements handles the UX but the checkout flow (Step 16) must explicitly handle the PaymentIntent status requires_action and redirect the user back. Without this, EU checkout fails for a significant card percentage.
6. Step 4 (Legal) has no dependency on Step 6 (PRD) — legal docs are written before the product scope is defined. The privacy policy will document data collection that doesn't exist yet or miss collection that is later added. Legal depends on at minimum knowing what data flows exist.
7. PCI SAQ-A compliance work (Step 18) is scheduled after the payment implementation (Step 11). The scope definition — specifically whether any cardholder data touches the Next.js server during SSR — must be validated before writing checkout code, not after.
8. No email infrastructure is defined anywhere. Step 11 says 'order confirmation email triggered on payment_intent.succeeded' but there is no SMTP/transactional email provider setup (SendGrid, Postmark, Resend), no email template system, and no delivery failure handling. This is a dangling dependency with no owner step.
9. Tax calculation is entirely absent. Collecting payment without computing applicable sales tax (US nexus rules) or VAT (EU) is a legal compliance failure in most jurisdictions. No TaxJar, Avalara, or Stripe Tax integration is mentioned anywhere in 25 steps.
10. Inventory concurrency is unaddressed. Two simultaneous add-to-cart requests for the last unit will both succeed until checkout. No pessimistic locking, optimistic concurrency check, or reservation pattern is described. Medusa does not handle this automatically.

### Suggestions

1. Force the Shopify vs Medusa decision in Step 1 or as a prerequisite gate before Step 7. Document it as ADR-001 (already planned) and make Steps 9-12 conditional branches, not ambiguous prose. All downstream steps should reference the decided backend only.
2. Replace the dual GraphQL/REST API output in Step 7 with a single contract matching the chosen backend. If Shopify: document the Storefront GraphQL schema. If Medusa: document the REST OpenAPI spec. Delete the unused artifact.
3. Add a cart reconciliation spec to Step 10: define the merge strategy when a guest cart (Medusa cart_id in cookie) is associated with a newly authenticated customer. Medusa supports this via POST /store/customers/me/cart but it must be explicitly called.
4. Wire on-demand revalidation: in the Medusa product.updated subscriber (Step 12), call Next.js revalidateTag('product-[handle]') via a server action or internal API route. This eliminates the oversell window without removing ISR benefits.
5. Add a PSD2/SCA handling section to Step 16: after confirmPayment(), check the PaymentIntent status. If requires_action, call stripe.handleNextAction() or handleCardAction() and handle the return_url flow. Test with Stripe's 3DS test cards (4000002500003155).
6. Reorder Step 4 to depend on Step 6 (PRD). Legal docs need a defined feature scope to accurately describe data collection, retention, and third-party sharing. Running legal in parallel with market research produces legally incomplete documents.
7. Move PCI scope definition (currently Step 18) to before Step 11 implementation. The critical check — does any Next.js Server Component or API route ever receive or log raw card data — must be verified in the architecture phase, not after shipping.
8. Add Step 10.5 or extend Step 8: set up transactional email provider (Resend recommended for Medusa v2 compatibility), define email templates for order confirmation, shipping notification, and password reset, and add SMTP env vars to .env.example.
9. Add tax calculation to Step 10 backend implementation: integrate Stripe Tax (simplest path — one API flag on PaymentIntent) or Medusa's built-in tax module with region-based rates. Document jurisdiction coverage in the PRD.

### Missing Elements

1. Inventory reservation / stock locking strategy during checkout (prevent oversell)
2. Tax computation provider and rate configuration
3. Transactional email infrastructure and template system
4. PSD2/SCA 3DS authentication handling in checkout flow
5. Password reset and account management flows (only register/login is specified)
6. Algolia index aliasing for zero-downtime reindexing (bulk reindex in Step 12 requires alias swap to avoid serving empty index during migration)
7. Image storage backend for Medusa (local disk fails in Docker/Railway — needs S3 or Cloudflare R2 configuration)
8. Error monitoring integration point (Sentry is mentioned in Step 24 ops runbook but never initialized in the application — Step 8 or 13 should install and configure it)
9. Rate limiting on Next.js API routes and Server Actions (Step 10 adds rate limiting to Medusa but the Next.js layer has none)
10. Webhook idempotency handling: Stripe can deliver the same webhook event multiple times; the payment_intent.succeeded handler must be idempotent using the event ID as a deduplication key
11. Medusa v2 plugin compatibility matrix — medusa-payment-stripe package name and API for v2 differs from v1; this needs explicit verification before Step 11
12. Shopify Storefront API access token scoping and rotating strategy (if Shopify path is chosen)
13. Content Security Policy for Stripe Elements: Stripe.js must be loaded from js.stripe.com and the CSP in Step 20 must whitelist exactly the right Stripe domains or payment will fail in production

### Security Risks

1. XSS via product content: Medusa product descriptions are merchant-controlled strings rendered in React. If any component uses dangerouslySetInnerHTML for rich text descriptions (common pattern), a compromised merchant account or admin injection attack yields stored XSS in a PCI-scoped checkout page. The threat model (Step 5) lists XSS but the frontend implementation steps have no explicit sanitization requirement.
2. ALGOLIA_ADMIN_KEY exposure: Step 19 correctly stores this in GitHub Secrets, but if any Next.js Server Component or API route forwards this key to the client response (e.g., in a debug header or error message), it grants full index write access. The search-only key restriction is mentioned but there is no audit requirement to verify the admin key never appears in client-accessible code paths.
3. Stripe webhook endpoint lacks idempotency: a replayed payment_intent.succeeded webhook will create a duplicate order. Without event ID deduplication in the database, this is both a financial and inventory integrity risk.
4. JWT refresh token strategy undefined: Step 10 specifies '1h expiry and refresh token' but the refresh token rotation policy, storage mechanism (httpOnly cookie vs localStorage), and revocation strategy are unspecified. Storing refresh tokens in localStorage makes them accessible to any XSS payload.
5. SSR secret leakage: Next.js App Router Server Components run server-side but developers frequently make the mistake of importing server-only modules into shared components, which Next.js then bundles client-side. Without the server-only package enforced at build time (mentioned nowhere), Medusa API keys or database credentials can leak into the client bundle.
6. CSP misconfiguration for Stripe: Stripe Elements requires specific CSP directives (frame-src https://js.stripe.com, script-src https://js.stripe.com). An overly strict or incorrectly specified CSP (Step 20) will silently break payment in some browsers with no obvious error, which is both a UX failure and a security misconfiguration if the fix is to loosen CSP globally.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.320646
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

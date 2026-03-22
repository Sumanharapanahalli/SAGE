# Regulatory Compliance — Course Marketplace

**Domain:** edtech
**Solution ID:** 080
**Generated:** 2026-03-22T11:53:39.332237
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **GDPR**
- **PCI DSS**
- **Tax Compliance**

## 2. Domain Detection Results

- edtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | COMPLIANCE | Produce compliance artifacts for COPPA (children's data), FERPA (student educati | Standards mapping, DHF, traceability |
| Step 5 | LEGAL | Draft terms of service, privacy policy, instructor agreement, affiliate agreemen | Privacy, licensing, contracts |
| Step 23 | SECURITY | Conduct security review and threat modeling for the platform. Cover payment data | Threat modeling, penetration testing |
| Step 26 | QA | Design and execute QA test plan for the full platform: functional test cases for | Verification & validation |
| Step 27 | SYSTEM_TEST | Execute system-level integration and performance tests: end-to-end purchase-to-p | End-to-end validation, performance |
| Step 30 | COMPLIANCE | Produce final compliance evidence package: WCAG 2.1 AA conformance statement, CO | Standards mapping, DHF, traceability |

**Total tasks:** 30 | **Compliance tasks:** 6 | **Coverage:** 20%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 3 | PCI DSS compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |
| 4 | Tax Compliance compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| regulatory_specialist | 3 | Compliance |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| business_analyst | 1 | Analysis |
| marketing_strategist | 1 | Operations |
| product_manager | 1 | Design |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| financial_analyst | 1 | Analysis |
| localization_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 57/100 (FAIL) — 1 iteration(s)

**Summary:** This is an unusually thorough plan with strong domain coverage — the compliance artifacts, double-entry ledger, affiliate fraud detection, and corporate SSO scope all reflect genuine production thinking. However, it has two critical business-model defects (revenue share math that allows affiliate commissions to consume the entire platform margin, and FERPA applied as a blanket requirement without a legal determination of coverage) and one critical legal exposure (complete GDPR absence despite explicit EUR/GBP and EU locale targeting). The analytics performance targets (500ms instructor dashboard, 300ms search) are aspirational without the infrastructure to support them — PostgreSQL alone will not sustain these SLAs at scale. The test strategy is pure waterfall, concentrating all quality risk at the end of the build rather than distributing it per service. The localization sequencing will cause significant rework cost. None of these are insurmountable, but the revenue share flaw and GDPR gap must be resolved before any further implementation decisions are made — one is a P&L risk, the other is a regulatory enforcement risk on day one of EU launch. Score reflects strong plan structure undermined by foundational business model and compliance gaps.

### Flaws Identified

1. Revenue share math is broken for affiliate-driven sales: 70% instructor + up to 20% elite affiliate commission = 90% of revenue, leaving 10% for the platform to cover payment processing (~3%), infrastructure, support, and margin. The plan never reconciles whether affiliate commissions come from the platform's 30% or reduce instructor earnings. At elite tier on a $100 course: $70 instructor + $20 affiliate + $10 platform — then Stripe takes $3.20, leaving $6.80 platform margin. This is a business model failure waiting to happen.
2. GDPR is entirely absent from a plan that explicitly targets EUR and GBP markets and mentions French and Spanish locales. Affiliate cookie tracking (Step 16), third-party processor inventory (Step 30), and data retention policies all require GDPR compliance. This is a production-blocking legal exposure for any EU-facing launch.
3. FERPA misapplication: FERPA applies to educational institutions receiving federal Title IV funding (K-12, universities). A private commercial course marketplace is not a covered entity under FERPA unless it contracts with Title IV institutions. The plan treats FERPA as a given across all 30 steps without a legal determination of applicability. If the corporate license targets universities, FERPA applies to that vertical only — not the whole platform.
4. Localization is Step 22, after all three frontend surfaces are fully built (Steps 19-21). Retrofitting i18n into a completed React codebase is extremely expensive — string extraction, component refactoring, RTL-capable layout changes, and locale-aware number/date formatting throughout. i18n scaffolding must be Step 10 and enforced from Step 19 onward, not bolted on after.
5. Analytics performance target of 500ms for all instructor metric groups (Step 18) is unrealistic against OLTP PostgreSQL without pre-aggregation. Revenue calculations joining payments, refunds, and ledger entries across time ranges for active instructors will not consistently hit 500ms under production load. No time-series database (TimescaleDB, ClickHouse) or materialized view refresh strategy is specified.
6. Course search returning results within 300ms (Step 19 acceptance criteria) has no specified search technology. PostgreSQL full-text search degrades past ~50k courses. The plan has no Elasticsearch, OpenSearch, or vector search layer — this will fail at scale with no migration path designed.
7. Testing strategy is pure waterfall: Steps 25 (unit/integration), 26 (QA), 27 (system test) all run sequentially after all 8 backend services are complete. This creates a massive late-stage integration risk. Revenue ledger bugs, affiliate attribution edge cases, and payout idempotency failures found at Step 25 require rework of code from Steps 11-18. TDD/BDD should be wired from Step 11.
8. Refund-to-enrollment access revocation timing is undefined. When a refund is processed (Step 13), learner access revocation, review invalidation, and affiliate commission clawback must be transactional. The plan addresses ledger reversal but not: (a) whether a refunded learner keeps their review, (b) how refunds within 30 days but after monthly payout are clawed back from instructor accounts, (c) whether subscription cancellation mid-month triggers partial refund.
9. Stripe Connect compliance is understated. Step 23 correctly identifies SAQ-A scope for card data, but Stripe Connect Express/Custom platforms have additional KYC/AML obligations: collecting instructor identity documentation, monitoring for suspicious payout patterns, and handling Stripe's own compliance reviews. This is not SAQ-A territory for the payout layer.
10. Certificate generation appears in Step 19 frontend acceptance criteria but is listed as Phase 2 in Step 3 PRD. This scope inconsistency will cause requirement disputes at Step 19 implementation. Certificate fraud prevention (verifiable credentials, tamper-proof links) is not addressed at all.
11. SAML 2.0 implementation complexity for corporate SSO (Step 17) is severely underestimated. JIT (Just-In-Time) provisioning, SP-initiated vs. IdP-initiated flows, attribute mapping per corporate tenant, and certificate rotation are each non-trivial. The 15-minute seat provisioning SLA requires real-time SCIM or JIT provisioning — a separate engineering concern not captured.
12. Content moderation for uploaded course material is absent. Instructors can upload videos, PDFs, and assignments. There is no pipeline for CSAM detection, DMCA-infringing content, or malware-embedded downloadable resources. Review moderation (Step 15) handles text reviews but ignores the primary attack surface.
13. India's TDS (Tax Deducted at Source) requirements for INR payouts are missing. India requires platforms paying Indian instructors to deduct TDS at source and file quarterly returns with the Income Tax Department. INR is listed as a supported currency but the regulatory obligation is not captured in Step 7 or Step 14.

### Suggestions

1. Fix the revenue share formula immediately: define explicitly whether affiliate commission is deducted from the platform's 30% (platform absorbs cost), from instructor earnings (instructor absorbs cost), or split. Model the contribution margin at each affiliate tier with Stripe processing fees included. Add a worked example in Step 7 acceptance criteria.
2. Add a GDPR compliance step (or extend Step 4) covering: lawful basis for processing per user type, cookie consent management (OneTrust or equivalent), right-to-erasure implementation with cascade delete across ledger/enrollment/review tables, DPA agreements with all EU-facing processors, and records of processing activities (ROPA).
3. Move i18n scaffolding to Step 10 (Config). Add acceptance criteria to Steps 19, 20, 21 requiring zero hardcoded strings. Reserve Step 22 for translation QA and locale file completion, not infrastructure setup.
4. Add a dedicated search service step (between Steps 9 and 10) to select and provision Elasticsearch/OpenSearch. Define the indexing strategy for courses, instructors, and reviews. Set explicit re-index thresholds and incremental update patterns.
5. Replace the waterfall test sequencing with parallel tracks: mandate test files be written in the same step as the service they cover (Steps 11-18 each require unit tests before acceptance). Steps 25-27 become integration, E2E, and performance gates, not the primary test authoring phase.
6. Add a pre-launch legal determination on FERPA applicability. If the platform will not contract with Title IV institutions, remove FERPA from compliance scope and replace with SOPIPA (for K-12 EdTech) and relevant state student privacy laws (California SOPIPA, NY Ed Law 2-d). If corporate licensing targets universities, scope FERPA compliance only to that vertical.
7. Model the refund-clawback flow explicitly in Step 7 and Step 14. Define: (a) holdback period on instructor payouts equal to refund window, or (b) clawback mechanism from future earnings, or (c) reserve fund. This is a cash flow design decision that affects the entire ledger architecture.
8. Add EU VAT/OSS registration requirements to Step 7 and Step 14. Digital services sold to EU consumers require VAT collection at the customer's country rate. Stripe Tax can handle this but must be configured explicitly per transaction — it is not automatic.
9. Extend Step 23 security review to include Stripe Connect KYC/AML requirements, rate limiting implementation verification (not just design), and affiliate link click injection attacks (where fraudsters inject affiliate codes into checkout URLs at payment time).

### Missing Elements

1. GDPR compliance artifact — entirely absent despite EUR/GBP targeting and EU locales
2. Affiliate commission source definition in the revenue model — undefined whether it comes from platform cut or instructor earnings
3. Cookie consent management system (OneTrust, Cookiebot, or custom) for EU users
4. Search infrastructure decision — Elasticsearch/OpenSearch vs. PostgreSQL FTS with explicit scale threshold
5. EU VAT/OSS (One Stop Shop) registration and per-transaction VAT collection rules
6. India TDS deduction and filing obligations for INR payouts
7. Instructor payout holdback/reserve mechanism to cover post-payout refunds
8. Content moderation pipeline for uploaded videos and downloadable files (CSAM, DMCA, malware)
9. SCIM provisioning spec for corporate SSO (JIT provisioning alone is insufficient for large orgs)
10. Analytics pre-aggregation strategy — materialized views, ClickHouse, or TimescaleDB decision
11. Email deliverability infrastructure — SPF/DKIM/DMARC configuration for SES, suppression list management, unsubscribe compliance (CAN-SPAM, CASL, GDPR)
12. Chargeback handling workflow — Stripe chargebacks trigger automatic refunds and require dispute evidence submission within 7 days; no runbook exists for this
13. Certificate verifiability mechanism — public verification URL or blockchain anchor to prevent credential fraud

### Security Risks

1. Affiliate link parameter injection: an attacker can append ?ref=AFFILIATE_CODE to any checkout URL at payment time, retroactively crediting an affiliate for organic conversions. Server-side validation must verify the affiliate code was present at the original click, not at checkout.
2. IDOR on revenue ledger endpoints: instructor A querying payout history must be strictly scoped to their own ledger entries. Step 23 lists IDOR testing but the ledger endpoints are not explicitly called out as a target — and financial IDOR vulnerabilities have the highest real-world exploit rate.
3. JWT refresh token rotation gap: Step 11 specifies 1-hour access tokens with refresh rotation, but the plan does not address refresh token family invalidation on theft detection (RFC 6819). A stolen refresh token that rotates before the legitimate user triggers silent account takeover.
4. Stripe webhook signature verification is mentioned implicitly via idempotency keys but Step 13/14 acceptance criteria do not explicitly require HMAC-SHA256 signature validation on every webhook. Without this, an attacker can POST fake payment confirmation events to create enrollments without payment.
5. Self-referral detection relies on matching affiliate code to instructor account — but a sophisticated instructor creates a second account as affiliate. IP-based clustering alone is insufficient. Device fingerprinting or payment method correlation is needed.
6. Corporate SAML metadata XML input in the SSO configuration form (Step 21) is a prime XXE (XML External Entity) injection surface. The acceptance criteria says 'validates SAML metadata XML before save' but does not specify XXE-safe XML parsing — a common and serious omission in SAML implementations.
7. Multi-currency exchange rate locking: Step 14 specifies 'time-of-sale exchange rate' but does not define the rate source (provider) or rate-lock granularity. If exchange rates are fetched from a third party, a rate manipulation attack (or provider outage) could cause ledger inconsistencies. The rate used must be stored immutably per transaction.
8. Video content URL authorization: CloudFront signed URLs for HLS streams must be scoped to enrolled users only. The plan does not specify the token expiry for signed URLs or how re-authentication is handled mid-stream for long videos. An unauthenticated CDN URL leak gives permanent free access.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.332275
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

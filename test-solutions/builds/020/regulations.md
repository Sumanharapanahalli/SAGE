# Regulatory Compliance — Payment Gateway

**Domain:** fintech
**Solution ID:** 020
**Generated:** 2026-03-22T11:53:39.313111
**HITL Level:** standard

---

## 1. Applicable Standards

- **PCI DSS Level 1**
- **PSD2**
- **SOC 2**
- **3DS2**

## 2. Domain Detection Results

- fintech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 3 | SECURITY | Produce threat model (STRIDE), PCI DSS Level 1 scope definition, data flow diagr | Threat modeling, penetration testing |
| Step 4 | COMPLIANCE | Build PCI DSS Level 1 compliance artifact set: Risk Assessment, Responsibility A | Standards mapping, DHF, traceability |
| Step 20 | SECURITY | Execute security hardening and penetration testing: DAST scan (OWASP ZAP) agains | Threat modeling, penetration testing |
| Step 21 | COMPLIANCE | Execute PCI DSS Level 1 pre-audit evidence collection: gather network diagrams,  | Standards mapping, DHF, traceability |
| Step 22 | SYSTEM_TEST | Execute system-level integration and performance testing: load test (10,000 TPS  | End-to-end validation, performance |
| Step 23 | LEGAL | Produce legal documentation: Terms of Service for merchants, Privacy Policy (GDP | Privacy, licensing, contracts |

**Total tasks:** 26 | **Compliance tasks:** 6 | **Coverage:** 23%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | PCI DSS Level 1 compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |
| 2 | PSD2 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 4 | 3DS2 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

## 5. Risk Assessment Summary

**Risk Level:** HIGH — Financial data and transactions require strict controls

| Risk Category | Mitigation in Plan |
|--------------|-------------------|
| Financial Loss | SECURITY tasks with fraud detection |
| Data Breach | SECURITY + COMPLIANCE tasks |
| Regulatory Fine | REGULATORY + LEGAL tasks |
| Service Disruption | DEVOPS + SYSTEM_TEST tasks |

## 6. Agent Team Assignment

| Agent Role | Tasks Assigned | Team |
|-----------|---------------|------|
| developer | 10 | Engineering |
| regulatory_specialist | 4 | Compliance |
| devops_engineer | 3 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| qa_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| legal_advisor | 1 | Compliance |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This plan demonstrates broad domain awareness and reasonable sequencing — the compliance-first approach (steps 3-4 before implementation), PSP abstraction layer, idempotency design, and webhook delivery system are all architecturally sound. However, the plan has several critical failures that would prevent it from reaching production as a PCI DSS Level 1 certified gateway. The most severe are: (1) a fundamental misunderstanding of PCI DSS Level 1 — it requires a QSA-conducted RoC, not a self-assessment SAQ, which undermines the entire compliance thread; (2) complete absence of fraud detection and prevention, which is not a feature gap but an existential operational risk — PSPs will terminate accounts with unchecked chargeback rates; (3) no settlement and reconciliation engine, which means there is no mechanism to actually pay merchants; (4) missing KYB/AML controls, which are legal prerequisites to operating a payment gateway in any regulated jurisdiction; (5) a 10,000 TPS performance target against an architecture with no connection pooling, no read replicas, and no caching strategy — the target is unachievable as specified. The Apple Pay certificate management design contains a factual error that will cause Apple Pay to fail in production. The python-jose JWT library selection introduces a known critical authentication bypass vulnerability. Taken together, the plan is a solid skeleton that requires a second-pass architect review before any implementation begins, with particular focus on fraud controls, settlement logic, KYB, database scaling strategy, and compliance tier correctness.

### Flaws Identified

1. PCI DSS Level 1 does not use SAQs. SAQs apply to Level 2-4 merchants. Level 1 requires a full Report on Compliance (RoC) conducted by a QSA. Steps 3 and 20 both list 'PCI DSS SAQ completed' as acceptance criteria — this is a fundamental misunderstanding of the compliance tier being targeted.
2. Apple Pay Merchant Identity Certificate cannot be issued by Vault PKI (step 10). It must be requested through the Apple Developer Portal and is issued by Apple's CA. Vault PKI cannot produce a cert Apple's servers will accept for merchant session validation.
3. PayPal is listed as a PSP target in step 1 but has no corresponding adapter in step 9, which implements only Stripe, Adyen, and Braintree. PayPal silently disappears from the plan with no explanation or deferral.
4. 10,000 TPS with p99 < 500ms (step 22) is untestable against the described infrastructure. FastAPI + a single PostgreSQL 16 instance with no PgBouncer, no read replicas, and no CQRS split will saturate well before 10k TPS. No database connection pooling strategy exists anywhere in the plan.
5. python-jose (step 14) has a known critical vulnerability (CVE-2022-29217, algorithm confusion leading to auth bypass). The plan specifies it by name without pinning a safe version or noting the mitigation. PyJWT with explicit algorithm specification or authlib should be used instead.
6. The 3DS2 implementation (step 15) is vague to the point of being unimplementable. It does not specify who hosts the 3DS Server, how the Authentication Value (CAVV) and ECI flag are threaded back to the PSP, how frictionless vs. challenge flows are differentiated, or how authentication results are linked back to the PaymentIntent state machine. 3DS2 has 20+ message types — 'integrate Cardinal Commerce or Stripe.js 3DS2' is not a design.
7. SAQ A vs SAQ A-EP distinction is misapplied in step 15. If the card form iframe is fully hosted on the payment gateway's domain and the merchant page never touches card data, the merchant qualifies for SAQ A (the simpler profile). SAQ A-EP applies when the merchant's page directly affects card data flow. Misclassifying this increases merchant compliance burden unnecessarily.
8. No fraud detection or prevention layer exists anywhere in 26 steps. No velocity checks, device fingerprinting, fraud scoring, or integration with Sift/Kount/Forter. For a payment gateway, chargeback fraud is the primary P&L risk. Launching without fraud controls guarantees unacceptable chargeback rates and potential PSP account termination.
9. No settlement and reconciliation engine. There is no step covering how funds move from PSPs to merchant bank accounts, settlement batching, reconciliation reports, or financial ledger balancing. This is a core function of a payment gateway, not a post-launch concern.
10. No multi-currency or FX support. No mention of presentment currency vs. settlement currency, FX rate sourcing, or currency conversion fees. Adyen, Stripe, and Braintree all handle multi-currency differently. Omitting this makes the product non-viable for any merchant with international customers.
11. No KYB/KYC/AML merchant onboarding. Step 1 mentions 'merchant onboarding flow' but there is no Know Your Business verification, AML screening, or OFAC/sanctions list checking. Operating a payment gateway without KYB controls violates FinCEN regulations in the US and equivalent regulations in most jurisdictions. This is a legal blocker, not a feature gap.
12. Redis idempotency store (step 9) lacks a specified locking strategy. No mention of SET NX with TTL for atomic reservation, or behavior during Redis failover. If Redis is unavailable, does the idempotency check fail open (allowing duplicate charges) or fail closed (denying all payments)? This is a money-movement correctness issue.
13. Let's Encrypt with cert-manager (step 17) is inappropriate for PCI DSS Level 1 production payment infrastructure. Let's Encrypt has 90-day cert rotation, public CT log exposure, and rate limits. QSAs at major firms routinely flag free CAs for Level 1 CDE endpoints. Commercial CA certs (DigiCert, Sectigo) are the standard.
14. Blue/green deployment (step 18) has no schema migration strategy. PostgreSQL schema changes during a blue/green switch require the expand/contract migration pattern (backward-compatible migrations run before the switch, cleanup migrations after). A breaking schema change mid-deploy will corrupt the active version. This is not mentioned.
15. Webhook delivery target of 5,000 events/second (step 22) is not addressable by a single Redis Streams consumer group. No consumer group sharding strategy, no mention of Celery workers or dedicated webhook service scaling. This target will fail without architectural specificity.

### Suggestions

1. Replace python-jose with PyJWT >= 2.4.0 with explicit algorithm='HS256' or 'RS256' in all decode() calls. Add a CI lint rule that fails on jose imports.
2. Add a step 6.5 or expand step 8 to cover database connection pooling: PgBouncer in transaction pooling mode, max_connections tuning, and read replica routing for reporting queries. Without this, the 10,000 TPS target is fiction.
3. Rewrite step 3 and step 20 acceptance criteria to replace 'SAQ completed' with 'RoC evidence package structured per PCI DSS v4.0 ROC Reporting Template'. Add explicit acceptance criterion: 'QSA firm contracted and scoping call completed'.
4. Add a dedicated Fraud step between steps 11 and 12: velocity rule engine (per card, per device, per merchant), integration with one fraud scoring provider (Sift Science recommended for payment gateways), and chargeback threshold alerting. This is not optional for any PSP that will maintain accounts.
5. Add a Settlement and Reconciliation step between steps 12 and 13: PSP payout webhook handlers, daily settlement batch reconciliation against bank statements, discrepancy alerting, and merchant payout scheduling. Include a ledger table (double-entry bookkeeping) to the database schema in step 6.
6. Fix the Apple Pay certificate management design: remove Vault PKI from step 10 for the Merchant Identity Certificate. The cert must be downloaded from Apple Developer Portal and stored in Vault as a secret (not generated by Vault). Separate the key pair for payment token decryption (which CAN be generated by Vault and stored in HSM) from the merchant identity cert.
7. Add SCA / PSD2 compliance for EU-region payments. If any merchant has European customers, Strong Customer Authentication exemption logic (transaction risk analysis, low-value exemptions, recurring transaction exemptions) must be implemented. This is a legal requirement, not a feature.
8. Add a BIN intelligence step or expand step 15: BIN database lookup (Mastercard/Visa BIN files or a provider like Binlist) for card type detection, issuing country, debit vs. credit classification, and 3DS2 method availability. Needed for routing decisions and compliance.
9. Expand step 17 to explicitly address Redis TLS configuration. Redis in the CDE without in-transit encryption is an automatic PCI DSS finding under Requirement 4.2.1. Specify TLS 1.2+ for all Redis connections.
10. Add webhook signature verification guidance to step 13 acceptance criteria: HMAC-SHA256 comparison MUST use hmac.compare_digest() (constant-time). Specify this explicitly — a naive == comparison is a timing oracle.
11. Add KYB/AML step before or within step 1: merchant identity verification via a KYB provider (Stripe Identity, Persona, or Jumio), OFAC SDN list screening, and ongoing monitoring for high-risk MCC codes. This is a legal prerequisite to going live.
12. Implement a PayPal adapter in step 9 or explicitly descope it with a documented deferral. Silent omission of a named PSP target is a requirements traceability failure.
13. Add data retention and deletion policy design: GDPR right-to-erasure against payment records conflicts with financial record retention requirements (typically 7 years). The plan must specify how tokenized payment methods are deleted from the PSP vault and how audit records are anonymized without being erased.

### Missing Elements

1. Fraud detection and prevention layer (velocity rules, device fingerprinting, fraud scoring provider integration, chargeback threshold monitoring)
2. Settlement and reconciliation engine (PSP payout processing, double-entry ledger, bank statement reconciliation, merchant payout scheduling)
3. Multi-currency and FX support (presentment vs. settlement currency, FX rate sourcing, cross-border fee disclosure)
4. KYB/KYC/AML merchant onboarding verification (identity verification provider, OFAC/sanctions screening, ongoing monitoring)
5. PgBouncer or equivalent database connection pooling (mandatory at the target TPS)
6. PostgreSQL read replicas for analytics and reporting query isolation
7. Monitoring and observability stack (OpenTelemetry instrumentation, APM, payment success rate dashboards, latency anomaly detection)
8. SCA/PSD2 compliance for EU payments (exemption logic, TRA, recurring transaction exemptions)
9. Data retention and deletion policy (GDPR right-to-erasure vs. financial record-keeping requirements)
10. Tax calculation for subscription invoices (Stripe Tax, Avalara, or manual — not mentioned anywhere)
11. BIN database integration for card intelligence
12. Chargeback representment and dispute automation beyond manual evidence upload
13. PayPal adapter implementation (named in requirements, absent from implementation)
14. Disaster recovery runbook for Redis failure (what happens to idempotency and rate limiting when Redis is unavailable)
15. Platform/marketplace PSP licensing assessment (if merchants accept payments from their own end-customers, standard PSP accounts may be prohibited — requires Stripe Connect, Adyen for Platforms, or equivalent)
16. GDPR Data Protection Impact Assessment (DPIA) — required before processing cardholder data at scale under GDPR Art. 35

### Security Risks

1. python-jose CVE-2022-29217: algorithm confusion attack allows forging JWT tokens with 'none' algorithm or HMAC bypass using the RSA public key as HMAC secret. Any deployment using python-jose without explicit algorithm enforcement is vulnerable to authentication bypass.
2. HMAC webhook signature comparison without constant-time comparison: if the implementation uses == instead of hmac.compare_digest(), the signature endpoint is a timing oracle that allows attackers to brute-force valid signatures byte-by-byte.
3. Redis without TLS in CDE: step 8 and 9 both use Redis for idempotency and rate limiting with no TLS specification. Plaintext Redis in or adjacent to the CDE violates PCI DSS Requirement 4.2.1 and is an automatic finding.
4. PostgreSQL Row-Level Security bypass risk: RLS is effective only if every query runs under the correct merchant role/setting (SET app.current_merchant_id). A missing set_config() call in the API middleware silently grants cross-merchant data access. No acceptance criterion validates this negative case.
5. 3DS2 CAVV/ECI handling gap: if the authentication result (CAVV, ECI value) is not correctly forwarded to the PSP with the authorization request, liability shift does not apply. Chargebacks on 3DS-authenticated transactions revert to the gateway — a potentially catastrophic financial exposure.
6. Dependency chain attack surface: 4 PSP SDKs (Stripe, Adyen, Braintree, PayPal) + 3 BNPL SDKs (Affirm, Klarna, Afterpay) + Apple/Google Pay SDKs. Each SDK is a supply chain risk. The SBOM in step 3 is listed as a deliverable but there is no acceptance criterion requiring SBOM verification against a vulnerability database on every CI run.
7. Let's Encrypt certificate transparency log exposure: all Let's Encrypt certificates are logged to public CT logs. This means your internal CDE subdomain hostnames are publicly discoverable, giving attackers a free inventory of your infrastructure topology.
8. Apple Pay payment token decryption key exposure: step 10 uses 'Vault PKI' for certificate management without specifying that the private ECDH key must reside in the HSM (AWS CloudHSM mentioned in step 17). If the decryption key is in Vault software storage rather than CloudHSM, PCI DSS Requirement 3.7 (HSM for cryptographic key operations) is violated.
9. IDOR risk in webhook configuration: step 13 allows merchants to configure arbitrary webhook endpoints. Without SSRF protection (allowlisting, blocking RFC 1918 ranges, blocking cloud metadata endpoints), a malicious merchant can use the webhook delivery system as a server-side request forgery vector against internal services.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.313165
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

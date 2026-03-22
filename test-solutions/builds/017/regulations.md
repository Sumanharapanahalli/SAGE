# Regulatory Compliance — Cross Border Payments

**Domain:** fintech
**Solution ID:** 017
**Generated:** 2026-03-22T11:53:39.311638
**HITL Level:** standard

---

## 1. Applicable Standards

- **PSD2**
- **FATF**
- **PCI DSS**
- **KYC/AML**
- **SWIFT**

## 2. Domain Detection Results

- fintech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 2 | REGULATORY | Map PSD2 (Strong Customer Authentication, open banking APIs, liability framework | Submission preparation, audit readiness |
| Step 3 | LEGAL | Draft Terms of Service, Privacy Policy (GDPR-aligned), data retention policy, an | Privacy, licensing, contracts |
| Step 4 | SECURITY | Produce threat model (STRIDE), penetration test plan, cryptographic controls spe | Threat modeling, penetration testing |
| Step 5 | COMPLIANCE | Build PCI DSS v4.0 compliance framework: cardholder data environment scoping, co | Standards mapping, DHF, traceability |
| Step 23 | SYSTEM_TEST | Execute system-level performance and resilience tests: 1000 TPS payment throughp | End-to-end validation, performance |
| Step 26 | COMPLIANCE | Produce final PCI DSS v4.0 Report on Compliance (RoC) evidence package: network  | Standards mapping, DHF, traceability |

**Total tasks:** 28 | **Compliance tasks:** 6 | **Coverage:** 21%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | PSD2 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | FATF compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | PCI DSS compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |
| 4 | KYC/AML compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 5 | SWIFT compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 13 | Engineering |
| regulatory_specialist | 4 | Compliance |
| devops_engineer | 3 | Engineering |
| qa_engineer | 2 | Engineering |
| business_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 55/100 (FAIL) — 1 iteration(s)

**Summary:** This plan is architecturally coherent and more thorough than most fintech implementation plans — the double-entry ledger, event sourcing for remittance state, idempotency via Redis, and coordinator-pattern HITL agent design are all correct choices. The documentation artifacts (BRD, threat model, ADRs, runbooks) are well-scoped. However, the plan has three existential blockers that will prevent production launch regardless of engineering quality: (1) no regulatory licensing acquisition plan — EMI/PSP licenses are business authorizations that take 12–24 months, not documents to draft; (2) SWIFT direct connectivity is treated as a configuration option when it is actually a multi-year infrastructure and compliance programme — the MVP should use a banking-as-a-service intermediary; and (3) KYC backend implementation is entirely absent despite being the legal prerequisite for allowing any customer to move money. Beyond these blockers, significant implementation gaps exist in AML rules engines, UK payment rails, FATF Travel Rule protocol interoperability, GDPR data subject rights, and fraud detection. The security analysis correctly identifies major threat categories but misses several payment-specific attack vectors including sanctions bypass via Unicode transliteration and FX quote race conditions. Scored 55 for a production regulated payments system: the planning layer is strong, but the gaps are not cosmetic — they are the load-bearing walls.

### Flaws Identified

1. KYC backend implementation is completely absent. The DB schema has a kyc_profiles table, the UX has a KYC onboarding screen, and the legal step mentions KYC obligations — but there is no implementation step for identity document collection, liveness checks, identity verification provider integration (Jumio/Onfido/Persona), risk tiering, or KYC refresh workflows. For a PSD2/FATF-regulated payment platform this is not optional — it is the gating condition for allowing any user to send money.
2. Regulatory licensing is documented but not obtained. Step 3 drafts an EMI/PSP/MSB licensing framework. EU EMI licenses take 12–24 months from application to authorization from a national competent authority (e.g., DNB, BaFin, FCA post-Brexit equivalent). The plan has zero steps for filing, engaging regulators, or operating under a passporting arrangement. You cannot legally move customer funds cross-border without these. This is not a documentation gap — it is a hard legal blocker that invalidates the entire production timeline.
3. SWIFT connectivity is catastrophically underestimated. Step 13 treats SWIFT Alliance Access as a configuration toggle. In practice: SWIFT membership requires an application process (months), a BIC allocation, an HSM (Luna/Thales) for key storage, alliance gateway installation, annual SWIFT CSCF certification, and often a correspondent banking relationship or service bureau contract. Most fintechs take 12–18 months to go live on SWIFT. Treating it as 'SWIFT Alliance Access (configurable)' will blindside any engineering team.
4. FX rate providers chosen are not suitable for regulated money movement. OpenExchangeRates and Fixer.io are information aggregators licensed for display purposes only — their terms of service explicitly prohibit use for financial transactions. For live FX execution on a regulated platform you need Reuters/Refinitiv Elektron, Bloomberg BFWR, or rates sourced directly from a banking partner. Using these providers for actual fund conversion exposes the operator to regulatory censure and contractual liability.
5. PCI DSS compliance is extensively planned but the payment rails are bank transfers (SWIFT/SEPA), not card transactions. PCI DSS applies to cardholder data (PANs, CVVs). If no card acquiring is in scope, steps 4, 5, and 26 are largely irrelevant compliance overhead. If cards ARE in scope there is no card processing implementation step anywhere in the plan. This is a fundamental scope confusion that will waste significant engineering and compliance budget.
6. FATF Travel Rule transmission protocol is unspecified. Step 15 assembles the Travel Rule data package but does not name the interoperability protocol for transmitting it to the beneficiary VASP/PSP (TRISA, OpenVASP, Sygna Bridge, Shyft, or bilateral API). Without a protocol decision, Travel Rule data is assembled but cannot be delivered. The receiving institution also needs to be onboarded to the same network — a business development dependency with multi-month lead time.
7. UK payment rail is missing. The jurisdiction scope includes the UK but the only rails implemented are SWIFT (international) and SEPA (EU only — UK exited SEPA post-Brexit). GBP domestic payments require Faster Payments (via Pay.UK access or an agency bank) and potentially CHAPS for high-value. UK-to-EU remittances cannot use SEPA from a UK-based sender without an EU-licensed entity. This is a product gap, not a minor omission.
8. System tests (step 23) depend on step 22 but are structurally ordered before infrastructure (step 25). Chaos testing PostgreSQL Multi-AZ failover and Redis cluster outage requires actual RDS Multi-AZ and ElastiCache — not Docker Compose. The 1000 TPS benchmark against a local containerized stack is meaningless for production sizing. The dependency chain has this backwards.
9. GDPR data subject rights have no implementation step. Step 3 cites Art17 (right to erasure) and Art20 (data portability) but there is no backend implementation of DSR workflows. Right to erasure conflicts directly with AML 5-year retention obligations and the immutable audit log — this tension must be resolved in code (pseudonymization strategy, legal hold logic), not just in the privacy policy.
10. AML transaction monitoring rules engine is absent. The ComplianceAgent generates STR drafts, but there is no defined rule engine for detecting structuring (smurfing), velocity anomalies, round-dollar patterns, or sudden account activity spikes. The agent cannot draft an STR without upstream detection logic. This is the core of AML compliance and it is missing.
11. Fraud detection is not present. Beyond SCA and sanctions screening there is no real-time fraud scoring, device fingerprinting, behavioral analytics, or velocity controls per account/IP/device. Credential stuffing is listed as a threat in the security step but has no corresponding implementation countermeasure beyond SCA.
12. Sanctions screening false positive target of <2% is operationally naive. Production Levenshtein-at-85% matching against OFAC SDN + EU + UN lists produces false positive rates of 20–60% in real deployments depending on corpus. The plan does not model the compliance officer queue volume this generates (which could overwhelm step 19's portal), nor does it specify list update frequency (OFAC updates multiple times per week).
13. The agentic HITL gate has a deadlock risk in the payment state machine. Step 17's RoutingAgent proposes a route_change which goes to the approval queue. Step 15's state machine has the payment sitting in 'routed' state. If the HITL approval takes hours and the FX quote (30s TTL from step 11) expires, the payment is in an undefined state. There is no compensation transaction or timeout-driven state resolution defined.
14. Tests are written after all implementation (step 21 depends on steps 15–16). No TDD or test-first approach is specified anywhere. For a double-entry ledger and state machine handling real money, discovering invariant violations during a test-writing phase rather than during development is a high-risk approach.
15. No multi-region or data residency strategy. GDPR requires EU personal data to remain in EU jurisdictions. A cross-border platform serving EU, UK, and US users from a single AWS region creates data residency violations. Terraform step 25 mentions only staging and production in presumably one region with no geo-redundancy or data sovereignty controls.

### Suggestions

1. Add a dedicated KYC implementation step (step 10.5) covering: identity document upload API, liveness/selfie verification via provider SDK, KYC status state machine (pending → verified → rejected → expired), risk tier assignment, and periodic re-verification scheduling. Wire the KYC status check as a hard gate before any payment initiation.
2. Add a licensing and regulatory authorization step as step 0 (before everything else) that maps required licenses per jurisdiction, identifies the fastest path (e.g., UK EMI license, EU passporting from an existing authorized partner, or a banking-as-a-service provider like ClearBank/Modulr as a shortcut), and defines the go-live gating condition. Without this, all subsequent steps are pre-legal.
3. Replace SWIFT direct connectivity with a SWIFT Service Bureau or a BaaS provider (ClearBank, Banking Circle, Currencycloud) for MVP. Model direct SWIFT Alliance Access as a phase 2 upgrade after licensing and volume justify it. This de-risks months of infrastructure work.
4. Replace OpenExchangeRates/Fixer.io with a bank-sourced rate feed or a regulated FX data vendor (XE Enterprise, Refinitiv, or rates pulled directly from the BaaS partner). Update step 11's acceptance criteria to include vendor licensing verification.
5. Clarify card scope definitively in step 1 (BRD). If cards are out of scope, strip PCI DSS work from steps 4, 5, and 26. If cards are in scope, add a card processing implementation step using a card-acquiring partner (Stripe, Adyen, or direct scheme membership).
6. In step 15 (Travel Rule), select a specific interoperability protocol (recommend TRISA for VASPs or bilateral API for PSPs) and add a business development sub-task to onboard at least 3 counterparty corridors before go-live.
7. Add UK Faster Payments rail implementation (step 14.5): access via an agency bank or Pay.UK direct participant, Faster Payments message format (ISO 20022 pacs.008), 2-hour settlement cycle, and £1M transaction limit handling.
8. Move system tests (step 23) to depend on step 25 (infra) or create a staging-environment variant that runs against RDS Multi-AZ and ElastiCache rather than Docker Compose. The chaos scenarios are meaningless without the actual infrastructure components.
9. Add a GDPR DSR implementation step covering: pseudonymization strategy for audit logs (replace PII with a pseudonym token after retention period), legal hold logic that prevents erasure when AML retention clock is running, and a DSR request API (GET /v1/users/{id}/export, DELETE /v1/users/{id}).
10. Add an AML rules engine implementation step (step 17.5) defining: velocity rules (>N transactions in 24h, >X amount in 7 days), structuring detection (multiple transactions just below €10k threshold), dormant account activation alerts, and geographic risk scoring. The ComplianceAgent in step 17 should consume this engine's output, not generate it from scratch.
11. Add a sanctions screening capacity model to step 12: given the expected transaction volume and the false positive rate at the chosen threshold, compute the daily compliance officer review queue depth. If the queue exceeds officer capacity, either raise the threshold, add tiered review (automated pre-filter), or hire. This should gate the go/no-go on the 85% Levenshtein threshold.
12. In step 17, define a compensation transaction protocol for the HITL deadlock case: if a payment is awaiting route approval and the FX quote expires, automatically transition the payment to a 'rate_expired' state, refund the reserved balance, and notify the sender to retry. Document this as a named saga with rollback steps.
13. Add data residency annotations to the Terraform step (25): tag each resource with its data classification and map EU-resident user data to eu-west-1/eu-central-1 only. Add S3 bucket policy and RDS subnet group constraints to enforce this. This is required for GDPR and will affect the architecture of multi-tenant routing.

### Missing Elements

1. KYC backend service implementation (identity verification provider integration, document collection API, risk tiering, re-verification scheduling)
2. Regulatory licensing acquisition plan and go-live gating criteria
3. UK domestic payment rail (Faster Payments / CHAPS)
4. FATF Travel Rule interoperability protocol selection and counterparty onboarding plan
5. AML transaction monitoring rules engine (structuring detection, velocity rules, geographic risk scoring)
6. Real-time fraud scoring service (device fingerprinting, behavioral analytics, velocity controls)
7. GDPR data subject rights implementation (erasure workflow, data export API, pseudonymization strategy)
8. HSM specification for SWIFT key management (if direct Alliance Access is pursued)
9. FX P&L ledger and nostro/vostro account reconciliation (the platform needs to account for its own FX book, not just customer conversions)
10. Multi-region deployment and data residency enforcement in Terraform
11. Business continuity plan with formal RPO/RTO targets (runbooks exist but no BCP document)
12. Card payment processing rail (if intended — scope is ambiguous)
13. Account limits and velocity controls per customer tier (daily/monthly send limits enforced at API layer)
14. Correspondent banking relationship documentation (required for SWIFT and often for SEPA corridor access)
15. SWIFT CSCF annual certification plan (mandatory for SWIFT members, includes customer security programme self-attestation)

### Security Risks

1. IBAN enumeration via timing side-channel: IBAN validation that short-circuits on format check before account lookup leaks whether an IBAN is registered. Constant-time comparison required for account lookups.
2. Sanctions screening bypass via Unicode transliteration: Cyrillic/Arabic/CJK characters that visually resemble Latin characters will defeat Levenshtein matching. The plan lists 'alias_expansion' but does not specify Unicode normalization (NFC/NFD) and homoglyph canonicalization before matching.
3. FX quote race condition: two concurrent requests for the same quote_id could both pass the expiry check before either records execution. The acceptance criteria require a 409 on expired quotes but the optimistic locking pattern in step 10 is not applied to quote execution in step 11. Missing SELECT FOR UPDATE on fx_quotes at execution time.
4. Q-learning routing agent adversarial manipulation: a sophisticated actor sending synthetic low-value payments across a specific corridor could poison the RoutingAgent's reward function to prefer that corridor for subsequent high-value payments. No adversarial robustness testing or reward function anomaly detection is defined.
5. Webhook SSRF via attacker-controlled callback URLs: if the platform allows users to register webhook endpoints, an attacker could register an internal metadata URL (169.254.169.254 for AWS IMDSv1) or internal service address. SSRF protection on webhook URL validation is not mentioned.
6. Replay attack on SCA OTP: step 16 mentions SMS OTP fallback but does not specify OTP single-use enforcement across distributed instances. A Redis-based used-OTP set is implied but not specified, and the Redis outage scenario in step 23 creates a window where OTP reuse checking is unavailable.
7. JWT/session token scope escalation: the role-based access model (step 19) restricts compliance officers from initiating payments and senders from seeing the compliance queue, but there is no specification of token claims validation on the backend. A stolen compliance officer token must not be usable against payment initiation endpoints — server-side role enforcement must be explicit per endpoint.
8. SWIFT MT103 field injection: if originator/beneficiary name fields are populated from user-supplied input without sanitization, a SWIFT message could contain malformed field delimiters (colons, hyphens in specific positions) that corrupt downstream parsing. SWIFT field content validation beyond length checks is not specified.
9. Secrets rotation gap: Vault integration is specified for initial secret injection but there is no secret rotation policy defined. Long-lived SWIFT BIC certificates, FX provider API keys, and database credentials that are never rotated are a persistent compromise risk. Vault's dynamic secrets for database credentials should be explicitly specified.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.311677
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

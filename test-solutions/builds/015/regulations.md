# Regulatory Compliance — Expense Management

**Domain:** fintech
**Solution ID:** 015
**Generated:** 2026-03-22T11:53:39.311084
**HITL Level:** standard

---

## 1. Applicable Standards

- **PCI DSS**
- **SOC 2**
- **SOX**

## 2. Domain Detection Results

- fintech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 2 | SECURITY | Perform threat model and security review for expense management system. Produce  | Threat modeling, penetration testing |
| Step 3 | COMPLIANCE | Produce compliance artifacts for PCI DSS, SOC 2, and SOX: risk matrix, traceabil | Standards mapping, DHF, traceability |
| Step 19 | SECURITY | Execute security hardening: implement rate limiting, input sanitization, CSP hea | Threat modeling, penetration testing |
| Step 20 | COMPLIANCE | Produce final compliance package for SOC 2 readiness: control evidence collectio | Standards mapping, DHF, traceability |

**Total tasks:** 21 | **Compliance tasks:** 4 | **Coverage:** 19%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | PCI DSS compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |
| 2 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | SOX compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| devops_engineer | 2 | Engineering |
| business_analyst | 1 | Analysis |
| ux_designer | 1 | Design |
| analyst | 1 | Analysis |
| qa_engineer | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 64/100 (FAIL) — 1 iteration(s)

**Summary:** This is a structurally sound, well-sequenced plan that correctly identifies the major components of a corporate expense management system and includes compliance steps rarely seen in MVP plans. The dependency graph is mostly logical, the database schema is thorough, and the decision to front-load security and compliance (Steps 2-3) before implementation is correct. However, the plan has a fundamental product gap: it approves and exports expenses but never pays employees. ACH reimbursement is not a stretch goal — it is the reason the product exists. Multi-currency is similarly absent despite being extraction-targeted in the OCR step. On the compliance side, PCI DSS SAQ scope is likely mis-classified (SAQ D adds hundreds of controls that may be unnecessary), GDPR/CCPA are unaddressed for a system storing employee personal spending data, and the audit log's tamper-evidence relies entirely on database permissions rather than cryptographic guarantees a SOX auditor will accept. The iOS PWA camera limitation is a known platform constraint that will break the core mobile receipt capture flow on a large portion of the target user base. Accounting OAuth token refresh is a silent production failure waiting to happen on day two. These are not backlog items — they are gaps that prevent the system from functioning correctly in production. Score reflects that the plan's architecture and compliance intent are strong but the execution would stall on payment processing, currency handling, and several security controls before reaching a releasable state.

### Flaws Identified

1. Missing reimbursement payment flow entirely. The plan approves expenses and exports them to accounting, but never pays employees. ACH/wire disbursement is a core feature of any expense management product — employees cannot receive money. This is a fundamental product gap, not a backlog item.
2. Multi-currency is absent despite being an OCR extraction field. The plan extracts 'currency' from receipts but has no FX conversion logic, no exchange rate source, no policy enforcement in foreign currencies, and no accounting export in base currency. Any company with international employees hits this on day one.
3. PCI DSS SAQ D classification is almost certainly wrong. If the application never stores, processes, or transmits PANs (delegating all card data to Marqeta/Stripe), the correct scope is SAQ A or SAQ A-EP. SAQ D requires 329 controls. Mis-scoping upward means months of unnecessary compliance work; mis-scoping downward is an audit failure. This needs a QSA to determine scope before Step 2.
4. Xero OAuth tokens expire in 30 minutes; QuickBooks tokens in 60 minutes. The accounting integration (Step 10) mentions token storage but has no token refresh implementation or acceptance criterion. Production will fail silently after the first token expiry, blocking all accounting exports.
5. Real-time policy evaluation during form entry (Step 8) with no debouncing strategy will hammer the API on every keystroke. At 100 concurrent users editing forms, this is a self-inflicted DDoS. The acceptance criterion of 100ms evaluation time does not account for concurrent load or network latency on mobile.
6. NetSuite OAuth 1.0a (Token-Based Authentication) is significantly more complex than OAuth 2.0 — requires HMAC-SHA256 signing of each request, nonce management, and timestamp synchronization. The plan treats all three accounting integrations as equivalent effort. NetSuite alone could double Step 10's timeline.
7. Bulk approval of 50 expenses in a single action (Step 9) is a SOX control violation risk. SOX requires evidence of actual review, not just an approval click. There is no minimum-review-time control, no anti-rubber-stamp mechanism, and no auditor guidance on what constitutes a valid approval. An auditor will flag this.
8. iOS PWA camera capture is unreliable. iOS Safari restricts camera API access in PWA/homescreen mode on many iOS versions. The 'receipt capture within 3 taps' acceptance criterion will fail on a significant percentage of iPhone users. This requires a native wrapper (Capacitor/React Native) or explicit iOS Safari browser targeting — neither of which is planned.
9. Step 15 anomaly detection uses '3 standard deviations from baseline' but provides no cold-start solution. New employees have no baseline. New expense categories have no baseline. New organizations have no baseline. The false positive rate will be 100% for the first 30-90 days, destroying user trust before the feature can prove value.
10. Approval delegation (Step 9) has no chain delegation guard. If Alice delegates to Bob, and Bob can re-delegate to Carol, approval authority can be arbitrarily transferred across the org with a full audit trail of delegations but no policy check on whether Carol is authorized to approve Alice's expense tier. This is an internal control failure.
11. The audit log table has no tamper-evidence mechanism beyond 'no UPDATE/DELETE permissions.' A compromised app role, a DBA, or a PostgreSQL superuser can still modify records. SOX requires tamper-evident logs. The plan needs cryptographic chaining (hash of previous entry in each row) or an external append-only log service.
12. Step 6 implements SAML 2.0 SSO with acceptance criteria limited to 'tested with a mock IdP.' SAML has well-known implementation vulnerabilities: XML signature wrapping attacks, XXE, comment injection in NameID. A mock IdP test does not catch these. The plan needs a real IdP integration test AND a SAML-specific security review.

### Suggestions

1. Add Step 2.5 or amend Step 2: engage a PCI QSA for formal CDE scoping before any architecture is finalized. The card data flow determines whether this is SAQ A, A-EP, or D — a decision that changes the compliance workload by an order of magnitude.
2. Add an employee reimbursement step between Steps 9 and 10: ACH batch file generation, bank integration (via Dwolla, Modern Treasury, or direct ACH), payment status webhook handling, and reconciliation back to expense records. Without this, the product cannot complete its primary job.
3. Add multi-currency as a first-class concern to Step 5 (database: add base_currency, original_amount, exchange_rate, exchange_rate_date columns to expenses) and Step 8 (policy engine must compare amounts in base currency). Add FX rate provider (ECB, Open Exchange Rates, or Wise) to Step 6.
4. For real-time policy evaluation, implement client-side debouncing (300ms minimum) in Step 12, cache policy rules in Redis with a short TTL in Step 8, and add a dedicated policy evaluation rate limit separate from the general API rate limit.
5. Add cryptographic hash chaining to the audit_log table in Step 5: each row stores sha256(previous_row_hash + current_row_data). Add a nightly audit log integrity verification job. This is the difference between 'append-only by permission' and 'tamper-evident by design.'
6. For NetSuite, consider using a third-party connector library (e.g., netsuite-python) rather than building OAuth 1.0a from scratch. Estimate NetSuite integration at 2-3x the effort of QuickBooks/Xero and reflect this in resource planning.
7. For anomaly detection cold-start (Step 15), implement a peer-group baseline as fallback: if an employee has <10 expenses in a category, use the department median. Document this in the acceptance criteria with a minimum sample size threshold.
8. Add email infrastructure as an explicit step (or sub-step of Step 9): SES/SendGrid setup, transactional email templates, unsubscribe handling (CAN-SPAM/GDPR), and bounce/complaint processing. Email is load-bearing for approval notifications and rejection reasons.
9. For JWT storage, specify httpOnly SameSite=Strict cookies rather than localStorage in Step 6. This eliminates an entire class of XSS token theft. Update the acceptance criteria to include a cookie security audit.
10. Add GDPR/CCPA compliance artifacts to Step 3 or Step 20. Employee expense receipts contain purchase location data, meal companion names, and personal spending patterns. Any EU or California employees trigger these regulations. At minimum: data subject access request flow, right-to-erasure conflict with 7-year SOX retention (these must be reconciled), and a privacy notice.

### Missing Elements

1. Employee reimbursement payment processing: ACH disbursement, payment status tracking, failed payment handling, and bank account management for employees.
2. Multi-currency support: FX rate ingestion, currency conversion at submission time, base-currency normalization for policy enforcement, and accounting export in company base currency.
3. Email infrastructure: transactional email provider setup, templates for approval requests, rejection notices, escalations, and compliance with CAN-SPAM/GDPR unsubscribe requirements.
4. GDPR and CCPA compliance: data subject rights implementation, privacy notice, retention conflict resolution (GDPR erasure vs. SOX 7-year requirement), and data processing agreements with OCR and card providers.
5. Disaster recovery testing: the plan documents RTO/RPO targets in Step 20 but has no step for actually testing failover, backup restoration, or the DR runbook.
6. Card issuing bank partnership: Marqeta and Stripe Issuing both require approval of the business as a program manager. This is a business/legal prerequisite with weeks-to-months lead time that has no planned step.
7. Mobile push notifications: approval requests via push are more reliable than email for time-sensitive approvals. The notification system (Step 9) covers email, Slack, and in-app but not mobile push (APNs/FCM), which is load-bearing for a mobile-first PWA.
8. Expense receipt PAN scrubbing: OCR on receipts will extract visible card numbers (many paper receipts show partial PANs). The OCR pipeline has no step to detect and scrub any card-number-pattern text from extracted data before storage.
9. Accounting token refresh strategy: explicit token refresh logic, encrypted token rotation, and alerting when refresh fails — not implied by 'store tokens encrypted.'
10. Data retention enforcement mechanism: the policy says 7-year receipt retention for SOX, but there is no scheduled job, storage lifecycle policy, or legal hold mechanism to enforce it. Policy documentation is not the same as enforcement.
11. Webhook signature verification: Marqeta and Stripe both provide HMAC signatures on webhook payloads. There is no acceptance criterion requiring verification of these signatures, leaving the card transaction endpoint open to spoofed transactions.

### Security Risks

1. SAML XML signature wrapping: python3-saml and similar libraries have had CVEs for signature wrapping attacks where a valid signed assertion is cloned into an unsigned position. The acceptance criterion 'tested with mock IdP' does not exercise this attack surface. Require a SAML security review against OWASP SAML Security Cheat Sheet before Step 6 ships.
2. Webhook spoofing on card transaction endpoint (Step 11): without HMAC signature verification and timestamp replay protection on Marqeta/Stripe webhooks, any party who discovers the webhook URL can inject fraudulent card transactions that auto-create expense records. This is a direct financial fraud vector.
3. OCR pipeline PAN exposure: receipts frequently display partial or full card numbers. Unguarded OCR extraction stores whatever text is in the image. A malicious employee could submit a receipt image containing a PAN in a format that bypasses pattern detection. The extracted text must be scanned for PAN patterns (Luhn check) and scrubbed before storage.
4. Accounting OAuth token scope over-provisioning: QuickBooks and Xero OAuth scopes, if not minimized, grant read/write access to the entire organization's financial data. A compromised token gives an attacker full accounting access. The plan has no acceptance criterion enforcing minimum-scope OAuth requests.
5. Delegated approval privilege escalation: if delegation is implemented as 'copy approver permissions to delegate,' an employee with no approval authority could be delegated authority over their own manager's expenses if the manager delegates generically. The delegation model needs explicit constraints: a delegate can only approve expenses the delegator could approve, and cannot approve expenses from the delegator.
6. JWT in localStorage (implied default): if the React frontend stores JWT access tokens in localStorage, any XSS vulnerability — including those in third-party dependencies — exfiltrates tokens. The plan adds CSP headers but does not specify token storage mechanism. CSP reduces XSS risk; it does not eliminate it.
7. mTLS certificate lifecycle gap: Step 19 requires mTLS between services but has no acceptance criterion for certificate rotation, revocation, or expiry alerting. An expired internal certificate silently breaks service-to-service communication in production with no user-visible error until a cascading failure.
8. Bulk approval CSRF: the bulk approve endpoint (Step 9) processes up to 50 financial approvals per request. Without SameSite cookie enforcement and CSRF token validation, a cross-site request could trigger mass approvals from an authenticated approver's session. This is a high-value CSRF target.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.311112
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

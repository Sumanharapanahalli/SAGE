# Regulatory Compliance — Robo Advisor

**Domain:** fintech
**Solution ID:** 014
**Generated:** 2026-03-22T11:53:39.310854
**HITL Level:** standard

---

## 1. Applicable Standards

- **SEC RIA**
- **SOC 2**
- **FINRA**
- **Reg BI**

## 2. Domain Detection Results

- fintech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 2 | REGULATORY | Prepare SEC Registered Investment Adviser (RIA) registration package: Form ADV P | Submission preparation, audit readiness |
| Step 3 | LEGAL | Draft client agreements, terms of service, privacy policy (CCPA/GLBA compliant), | Privacy, licensing, contracts |
| Step 4 | SECURITY | Produce threat model, penetration test plan, and Software Bill of Materials (SBO | Threat modeling, penetration testing |
| Step 5 | COMPLIANCE | Build compliance traceability matrix mapping features to regulatory requirements | Standards mapping, DHF, traceability |
| Step 24 | SYSTEM_TEST | Execute end-to-end system tests: full investor lifecycle (onboarding → portfolio | End-to-end validation, performance |
| Step 25 | QA | Execute pre-launch QA: suitability algorithm audit (verify each risk score maps  | Verification & validation |

**Total tasks:** 30 | **Compliance tasks:** 6 | **Coverage:** 20%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SEC RIA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | FINRA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 4 | Reg BI compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 11 | Engineering |
| regulatory_specialist | 3 | Compliance |
| qa_engineer | 3 | Engineering |
| devops_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| product_manager | 1 | Design |
| data_scientist | 1 | Analysis |
| system_tester | 1 | Engineering |
| financial_analyst | 1 | Analysis |
| marketing_strategist | 1 | Operations |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 52/100 (FAIL) — 1 iteration(s)

**Summary:** This is a technically detailed plan that covers the surface area of a robo-advisor competently, but it contains several regulatory errors that are company-ending, not just costly. The misapplication of SOX to a private company is the most visible signal that the compliance framework was assembled by pattern-matching against enterprise compliance checklists rather than fintech-specific regulatory analysis. More critically, the plan omits the SEC Custody Rule, misidentifies Rule 17a-4 (broker-dealer) as the books-and-records standard instead of Rule 204-2 (RIA), and misses the state vs. SEC RIA registration threshold entirely — three errors that SEC examiners would flag on day one. The wash sale cross-account gap will generate incorrect tax documents at scale, creating direct client harm and IRS liability. On the technical side, the absence of a built authentication service, position reconciliation job, notification service, and corporate actions handler means four critical operational systems are planned to exist but never constructed. The plan reads as a sophisticated waterfall spec written for a well-funded team, but its regulatory foundation needs a fintech attorney review before a single line of code is written. Score 52: the technical architecture is sound, but the regulatory layer has enough fundamental errors to require a full rework pass with qualified fintech legal and compliance counsel.

### Flaws Identified

1. SOX (Sarbanes-Oxley) does not apply to private companies. Applying SOX ITGC controls throughout adds enormous compliance overhead with zero legal obligation. The correct framework is SOC 2 Type II. This error propagates through Steps 4, 5, 9, 21, and 25.
2. SEC vs. state RIA registration threshold is missing. The SEC only registers advisers managing $100M+ AUM. A startup robo-advisor almost certainly registers with individual state securities regulators first, not the SEC. Preparing Form ADV for SEC registration before hitting the AUM threshold is premature and potentially misfiled.
3. The Custody Rule (Rule 206(4)-2) is never mentioned. If the RIA deducts advisory fees directly from client accounts (which Step 16 plans), that constitutes custody, triggering annual surprise examinations by an independent public accountant. This is a hard regulatory requirement and a significant operational cost.
4. Wash sale rule enforcement is broken by design. The wash sale rule applies across ALL of a taxpayer's accounts — IRAs, 401ks, spouse accounts — not just accounts held at this platform. Step 15 only tracks within-platform positions. This will generate incorrect Form 8949 data and expose clients and the RIA to IRS penalties.
5. No authentication/authorization service is ever built. Steps 17-20 build frontends and Step 23 tests auth, but no step implements JWT issuance, OAuth 2.0, MFA, session management, or RBAC. Financial services regulators expect MFA. This is a missing vertical slice, not a gap in testing.
6. PCI DSS Level 1 is almost certainly wrong scope. PCI DSS Level 1 applies to merchants processing 6M+ card transactions/year. An RIA charging advisory fees via ACH (Step 16 uses Dwolla/Stripe for ACH) is likely not in card scope at all. Over-scoping PCI DSS Level 1 costs hundreds of thousands in QSA audits and remediation unnecessarily.
7. No notification service is ever built. Steps 14, 16, 24, and 28 all reference 'client notifications' for rebalancing alerts, fee billing failures, and outages, but no step builds email/SMS/push notification infrastructure.
8. Black-Litterman 'market views' have no defined source. The model requires subjective forward-looking views as inputs. Step 11 says they are 'configurable inputs' but never defines who generates them, how they are reviewed, or how they are disclosed in the ADV. If an AI agent generates these views, that is an undisclosed AI-driven investment decision.
9. Order lifecycle management is naive. Step 13 treats brokerage order execution as a single API call. Real execution involves order states (pending, partial fill, rejected, expired), T+2 settlement, and position reconciliation. No reconciliation job is ever built — the platform's internal holdings can silently diverge from actual brokerage positions.
10. Tax-loss harvesting is applied to tax-advantaged accounts. The plan handles both taxable and tax-advantaged accounts but Step 15 scans 'all positions with unrealized losses.' TLH has zero benefit and different wash sale implications inside IRAs/401ks. The engine needs account-type gating.
11. Steps 26 (Financial Model) and 27 (Market Research) are placed after all technical decisions. AUM projections, unit economics, and target customer segment should inform architecture scale, minimum viable AUM for profitability, and which features are P0. Doing this analysis at step 26-27 means all infrastructure and algorithm complexity decisions were made without knowing the business model.
12. ERISA fiduciary standard is absent. Any client using an IRA account triggers ERISA obligations, including the DOL Fiduciary Rule. The compliance framework in Step 5 only covers SEC RIA rules. ERISA adds a separate and stricter fiduciary standard with prohibited transaction rules.
13. Best execution obligation conflicts with Alpaca selection. Step 2 includes a best execution policy, but Step 13 hardcodes Alpaca without a comparative execution quality analysis. An RIA must be able to demonstrate to the SEC that it selected the execution venue in clients' best interest — hardcoding a single broker without documented evaluation fails this test.
14. Rule 17a-4 is cited for books-and-records but it applies to broker-dealers, not RIAs. The applicable rule is Rule 204-2 under the Investment Advisers Act. This is a direct regulatory citation error in Steps 3, 28, and 30.
15. No corporate actions handling. ETF splits, mergers, fund closures, and distributions affect cost basis, tax lots, and holdings. No step addresses corporate actions processing, which means cost basis data will silently corrupt over time.
16. Market data licensing is unaddressed. Real-time and historical market data from NYSE/NASDAQ for MPT optimization requires commercial licenses (e.g., from Refinitiv, Bloomberg, or exchange direct feeds). These cost $10K-$500K+/year and have redistribution restrictions. 'market_data_provider' is listed as an integration with no specification.

### Suggestions

1. Add a Step 1.5 for state RIA registration research: determine which state(s) apply, identify the AUM threshold for SEC registration eligibility, and plan the registration sequence accordingly. Build a trigger to file the SEC switch when AUM crosses $100M.
2. Replace all SOX ITGC references with SOC 2 Type II controls. If any investors are publicly traded companies using this as a corporate treasury tool, note SOX may apply to them — but not to the robo-advisor platform itself.
3. Add a Custody Rule compliance step between Steps 2 and 5. Document whether fee billing from client accounts constitutes custody, engage a qualified custodian, and plan for the annual surprise examination requirement if custody applies.
4. Expand wash sale enforcement to accept external account positions via API or manual input. Document explicitly in the Form ADV that cross-account wash sale accuracy depends on client-provided information when outside accounts are held away.
5. Add an explicit authentication/authorization backend step (JWT service, OAuth 2.0 PKCE for public clients, MFA via TOTP/SMS, role definitions: investor, advisor, admin, auditor). This should precede Step 12.
6. Add a daily reconciliation job step: compare internal holdings/positions/cash against brokerage API positions, flag discrepancies, and route to operations queue. This is non-negotiable for any RIA.
7. Move Steps 26 and 27 to immediately after Step 1 (or run them in parallel with Step 1). Business viability, target AUM, and competitive positioning must inform infrastructure scale decisions before a dollar is spent on cloud architecture.
8. Add account-type gating to the TLH engine. Only run TLH scans on taxable accounts. Add explicit handling for wash sale interactions between taxable and IRA accounts held on-platform.
9. Define the Black-Litterman market views governance process: who inputs them, how often, what the review and sign-off process is, and how they are disclosed in the ADV. Or explicitly choose the 'market-implied returns only' variant to eliminate subjective views entirely.
10. Scope a notification service explicitly: transactional email (SES/SendGrid), SMS (Twilio), and in-app notifications for rebalancing proposals, fee billing, and account alerts. Wire it to rebalancing, fee billing, and operations runbooks.
11. Consult a fintech attorney on whether the tax-loss harvesting feature and Form 8949 generation constitutes tax advice requiring CPA oversight or creates state-specific licensing requirements.
12. Replace PCI DSS Level 1 with Level 4 SAQ-A or SAQ-D based on actual card processing volume, or scope PCI out entirely if payment processing is entirely ACH and no card data is stored or transmitted.

### Missing Elements

1. Authentication and authorization service (JWT, OAuth 2.0, MFA) — never built, only tested
2. Daily position reconciliation between internal records and brokerage — critical operational control
3. Custody Rule (Rule 206(4)-2) compliance analysis and annual surprise examination planning
4. State RIA registration path for sub-$100M AUM launch phase
5. ERISA fiduciary obligations for IRA account holders
6. Corporate actions processing (splits, mergers, fund closures, distributions affecting cost basis)
7. Notification service (email, SMS, in-app) — referenced in 6+ steps but never implemented
8. Market data licensing procurement and cost modeling
9. Cross-account wash sale tracking design (or explicit disclosure of its absence)
10. Account-type gating for tax-loss harvesting (taxable vs. tax-advantaged)
11. Investor suitability re-assessment trigger (life events, large cash flows, annual review)
12. Client portal document delivery (statements, trade confirmations, tax documents) — this is a regulatory requirement under Rule 204-3
13. OFAC sanctions list update mechanism — Step 12 mentions screening but not how the list is kept current
14. Black-Litterman views governance process and ADV disclosure language for AI-influenced inputs
15. Business continuity plan for the RIA itself (not just IT) — regulatory examiners look for this separately from the DR runbook
16. Minimum investment amount design decision and its downstream implications for fractional share requirements

### Security Risks

1. No rate limiting specified on order execution endpoints (/portfolios/:id/construct, /rebalancing/approve, /tax/harvest). A compromised session or SSRF vulnerability could trigger unlimited trade generation.
2. Agent coordinator pattern with external market data inputs creates a prompt injection surface. If market data or news feeds are injected into agent context, adversarial data could influence portfolio construction or TLH decisions.
3. Brokerage API webhook signature verification not mentioned. If Alpaca/IB webhooks are accepted without HMAC verification, an attacker can inject fake fill confirmations, creating phantom positions.
4. No idle session timeout requirement specified for the investor portal. Financial applications are required by most state privacy laws and GLBA to enforce session timeouts. An unattended session exposes all HITL approval actions.
5. Plaid OAuth token storage: the plan stores 'tokenized account references' but does not specify token rotation policy or what happens when Plaid access tokens expire (typically 30 days for some products). Stale tokens cause silent ACH billing failures.
6. The audit log is described as 'append-only with tamper-evident hash chaining' but the threat model for the audit log itself is not scoped — specifically, who has DELETE or DDL access to the audit log database, and whether that access is monitored.
7. SBOM and CVE scanning blocks on CVSS >= 7.0 but PyPortfolioOpt, cvxpy, and scipy dependencies have complex transitive dependency trees in scientific Python. A vulnerable numpy version could pass CVE scans if the CVE is scored below 7.0 but still exploitable in the optimization context.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.310889
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

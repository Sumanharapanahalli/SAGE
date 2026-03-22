# Regulatory Compliance — Accounting Automation

**Domain:** fintech
**Solution ID:** 019
**Generated:** 2026-03-22T11:53:39.312673
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **GAAP**
- **SOX**

## 2. Domain Detection Results

- fintech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 3 | SECURITY | Conduct threat modeling, define security architecture, and produce a threat mode | Threat modeling, penetration testing |
| Step 4 | COMPLIANCE | Produce compliance artifacts for PCI DSS, SOC 2, and SOX. Define risk matrix, tr | Standards mapping, DHF, traceability |
| Step 5 | LEGAL | Draft terms of service, privacy policy, data processing agreements (DPA), and li | Privacy, licensing, contracts |
| Step 21 | SECURITY | Execute security review and penetration testing against the deployed staging env | Threat modeling, penetration testing |
| Step 22 | QA | Develop and execute QA test plan covering functional, regression, performance, a | Verification & validation |
| Step 23 | SYSTEM_TEST | Execute system-level integration and end-to-end tests covering the full lifecycl | End-to-end validation, performance |
| Step 24 | COMPLIANCE | Finalize compliance evidence package for SOC 2 Type II readiness, PCI DSS SAQ-D  | Standards mapping, DHF, traceability |

**Total tasks:** 28 | **Compliance tasks:** 7 | **Coverage:** 25%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | GAAP compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
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
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| data_scientist | 1 | Analysis |
| system_tester | 1 | Engineering |
| marketing_strategist | 1 | Operations |
| financial_analyst | 1 | Analysis |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This plan is thorough in process and compliance documentation but contains a fundamental domain modeling error that invalidates the entire financial reporting and tax preparation stack: there is no double-entry bookkeeping engine. Bank transaction imports are single-entry records; GAAP-compliant financial statements require a general ledger with balanced journal entries. Without this foundation, the P&L, balance sheet, and tax preparation modules cannot produce correct output regardless of how well they are implemented. Additionally, the ML model makes a 95% accuracy promise on synthetic training data without GPU infrastructure to train or serve it — this alone is a blocking gap. The compliance scope is confused: PCI DSS SAQ-D scope needs QSA determination, and SOX is misapplied to a SaaS vendor. These are not polish issues; they require architectural rework before implementation begins. The plan would score in the high 60s if the bookkeeping engine and ML infrastructure gaps were addressed, but in its current state, fundamental rework of Steps 8, 10, 14, 15, and 18 is required before this is production-ready.

### Flaws Identified

1. Double-entry bookkeeping is entirely absent. The database schema has a 'transactions' table but no journal_entries, general_ledger, or debit/credit structure. Without double-entry, GAAP-compliant P&L and balance sheets (Step 14) are mathematically impossible — you cannot derive a correct balance sheet from single-entry imported bank transactions alone.
2. ML model accuracy target of 95% on synthetic training data is unrealistic. Synthetic transactions do not replicate real-world bank description noise (e.g., 'SQ *COFFEE 1234', 'ACH DEBIT 0042891 VENDOR'). Published benchmarks on real bank transaction classification with FinBERT show 80-88% accuracy. The plan promises 95% without a real labeled training corpus.
3. Fine-tuning a transformer (Step 10) requires GPU infrastructure that is never provisioned. The infra step (18) only specifies FastAPI, PostgreSQL, Redis, Celery, and Nginx containers. No mention of GPU nodes, SageMaker, Vertex AI, or any model serving infrastructure. The active learning re-training pipeline has no compute to run on.
4. State tax obligations are completely absent. The vast majority of US small businesses have state income tax, franchise tax, and sales tax obligations. Supporting only Schedule C, 1120-S, 1065, and 1099-NEC covers federal only. This is a major feature gap that affects the credibility of the entire tax module.
5. PCI DSS SAQ-D scope is likely wrong. SAQ-D applies to merchants storing cardholder data (PANs). Plaid access tokens are not PANs. The plan conflates 'bank credentials' with 'cardholder data.' A QSA assessment is needed to determine actual PCI DSS scope — getting this wrong means either over-engineering controls or a compliance violation.
6. SOX Section 404 compliance requires external auditor attestation of internal controls, not just internal documentation. The plan treats SOX as a document production exercise (Step 24). A private company providing accounting software is not itself a SOX-reporting entity — SOX IT General Controls apply to the customer's audit, not the vendor's. The regulatory scope definition is fundamentally confused.
7. Step 16 (auth/RBAC) has no inbound dependency from Steps 11-15. This means five backend services are designed and built without authentication. Auth must be designed before any service API is finalized, or every API contract must be renegotiated post-hoc.
8. Tax liability estimation 'within 1%' (Step 15) is an unrealistic acceptance criterion. Tax liability involves depreciation schedules, carryforwards, AMT, Section 199A QBI deduction, basis tracking, and entity-specific rules that vary by state. A 1% tolerance requires a full tax calculation engine equivalent to TurboTax's core — not a mapper from categorized transactions.
9. Hungarian algorithm for reconciliation (Step 13) is O(n³). For a business with 3,000 monthly transactions, this is 27 billion operations per reconciliation run. No performance budget is defined for the reconciliation step, and the 10-second budget cited is only for the categorization step.
10. Plaid as the sole bank connection method creates a hard dependency with no fallback. ~15% of US financial institutions have limited or no Plaid support. No CSV/OFX/QFX manual import path is specified. A small business with a credit union or community bank is entirely blocked.
11. No Chart of Accounts management feature exists in the plan. Different businesses use different COAs (retail vs. service vs. manufacturing). The ML model maps to IRS Schedule C categories, but actual bookkeeping requires a configurable COA with account codes. The gap between IRS categories and accounting COA is never bridged.
12. The financial model (Step 28) is built last and never feeds back into product scoping. CAC and LTV assumptions should inform which features are in MVP. Building a 28-step pipeline and then discovering the unit economics don't work is a critical sequencing failure.
13. No database backup or restore implementation exists. Step 23 tests disaster recovery (RTO < 4 hours, RPO < 1 hour) but no step in the plan actually implements the backup infrastructure, backup schedules, or restore procedures being tested.
14. Audit log append-only enforcement relies only on database-level INSERT permissions (Step 8). This does not prevent a compromised DB admin or application superuser from deleting rows. For SOC 2 and PCI DSS, immutability requires write-once storage (S3 Object Lock, WORM storage) or cryptographic chaining, not just permission restrictions.
15. GLBA applicability determination is treated as a documentation task (Step 5) rather than a threshold legal question. If the product qualifies as a 'financial institution' under GLBA, it triggers the Safeguards Rule with specific technical controls. If it does not qualify, several compliance requirements are unnecessary. This must be resolved before architecture decisions are finalized.

### Suggestions

1. Add a double-entry bookkeeping engine as a separate step between Step 8 (database) and Step 14 (reports). Define journal_entries and general_ledger tables. All financial report generation must derive from the general ledger, not raw transaction imports.
2. Replace 'synthetic training data' with a real labeled dataset acquisition strategy. Use publicly available labeled datasets (e.g., bank transaction datasets from Kaggle/HuggingFace) supplemented by a human labeling sprint on 5,000 real transactions. Revise accuracy target to 88% for MVP, with 95% as a post-launch improvement target with real user data.
3. Add GPU/model serving infrastructure to Step 18. Specify whether inference runs via a cloud API (AWS SageMaker, Google Vertex), a self-hosted GPU container, or a CPU-optimized ONNX export. Define model artifact storage (S3/GCS) and versioning strategy (MLflow or DVC).
4. Add Step 8b: Chart of Accounts management service — configurable COA with account codes, account types (asset/liability/equity/income/expense), and mapping rules from bank transaction categories to COA entries.
5. Engage a QSA (Qualified Security Assessor) in Step 3 to determine actual PCI DSS scope before designing security controls. This decision changes the entire compliance architecture.
6. Move Step 16 (auth) dependency to be a prerequisite for Steps 11-15. All backend services must have the auth contract defined before API implementation begins.
7. Add a CSV/OFX/QFX manual import fallback in Step 11. Define the file format parsing pipeline alongside the Plaid integration.
8. Add Step 8c: Database backup infrastructure — pg_dump schedules, WAL archiving to S3, PITR configuration, and restore runbooks — before Step 23 tests it.
9. Replace append-only audit log with cryptographic chaining (each event includes hash of previous event) and periodic export to write-once storage. Document this in the audit_trail_spec.
10. Add state tax forms as a Phase 2 explicit scope item in Step 2 (PRD). At minimum, acknowledge the gap in Step 15 acceptance criteria rather than implying federal-only is complete tax filing preparation.
11. Move Step 28 (financial model) to immediately after Step 1, and use its output to constrain Step 2 MVP scope. Unit economics should drive feature prioritization, not follow product completion.
12. For the reconciliation algorithm, replace Hungarian algorithm with a tiered approach: exact match (amount + date ± 1 day) first, fuzzy match second, Hungarian only for the residual unmatched set. Cap the fuzzy match input at 500 items or implement batching.

### Missing Elements

1. Double-entry bookkeeping engine and general ledger — foundational to all accounting, entirely absent
2. Chart of Accounts management — configuration, account codes, account types, COA mapping
3. State tax forms and obligations — all US small businesses have state-level requirements
4. GPU/ML inference infrastructure — FinBERT cannot run on the specified container stack
5. Model versioning, A/B testing, and rollback strategy for the ML model
6. Database backup and PITR infrastructure — tested in Step 23 but never built
7. QSA engagement for PCI DSS scope determination
8. Plaid cost model and API pricing — Plaid charges per connected account; at scale this is a significant COGS line item not in the financial model
9. Split transaction handling in reconciliation
10. Foreign currency transaction support
11. Historical data import / migration from QuickBooks/Xero — critical for adoption
12. Celery task queue design and dead letter queue handling — referenced in infra but never designed
13. Plaid token refresh and re-authentication flows when access tokens expire
14. Multi-year tax carryforward tracking (NOLs, capital loss carryforwards)
15. Tax year update mechanism — IRS form fields and limits change annually
16. Accounts payable and accounts receivable management — referenced in reports but no input mechanism
17. GLBA applicability legal determination
18. Vendor risk assessment for all third-party dependencies, not just Plaid (ML model providers, cloud infrastructure)
19. Customer support and error reporting infrastructure
20. Data residency and state-level privacy law compliance (VCDPA, CPA, etc. beyond CCPA)

### Security Risks

1. Plaid access tokens stored 'encrypted' with no specification of key management. If the application-level AES-256 key is stored in the same database or the same environment, encryption provides no protection against a full system compromise. Key management (HSM, AWS KMS, HashiCorp Vault Transit) must be specified.
2. JWT refresh token rotation (Step 16) with no mention of refresh token storage security. If refresh tokens are stored client-side in localStorage (common React pattern), XSS completely bypasses the 15-minute access token expiry.
3. Tax package PDFs exported as 'password-protected' (Step 15) with no specification of password delivery mechanism. If the password is transmitted in the same channel as the PDF, it provides no security.
4. Multi-tenant RLS relies entirely on application-layer tenant_id injection. A single SQL injection vulnerability or ORM misconfiguration bypasses all tenant isolation. Defense-in-depth requires PostgreSQL RLS policies that enforce tenant_id from the session variable, not just application query parameters.
5. HITL gate bypass via direct database writes is not addressed. The penetration test plan mentions testing this, but the architecture does not describe how the system prevents an attacker with DB access from directly setting approval status, bypassing the API-level gate.
6. Celery workers processing tax and financial data need their own auth context. Workers that run as a privileged application user and accept tasks from Redis (which has no auth in the default Docker Compose config) are a significant lateral movement risk if Redis is exposed.
7. OpenAPI spec exposes all endpoint schemas publicly. For a financial system, the API spec should not be publicly accessible without authentication, as it provides a detailed attack surface map.
8. Dependency vulnerability scan blocks on CRITICAL CVEs (Step 18) but no process defined for CVE remediation timeline or exceptions. A zero-day in a core dependency (e.g., cryptography library) could block all deployments indefinitely without a defined exception process.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.312714
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

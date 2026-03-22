# Regulatory Compliance — Inventory Management

**Domain:** ecommerce
**Solution ID:** 047
**Generated:** 2026-03-22T11:53:39.322096
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **GDPR**

## 2. Domain Detection Results

- ecommerce (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 5 | LEGAL | Draft Terms of Service, Privacy Policy, Data Processing Agreement (GDPR/CCPA), a | Privacy, licensing, contracts |
| Step 6 | SECURITY | Produce threat model (STRIDE) for the inventory platform covering: multi-tenant  | Threat modeling, penetration testing |
| Step 7 | COMPLIANCE | Produce PCI DSS v4.0 compliance artifacts: network segmentation diagram, data fl | Standards mapping, DHF, traceability |
| Step 22 | QA | Produce QA test plan: define test scope, entry/exit criteria, risk-based test pr | Verification & validation |
| Step 24 | SYSTEM_TEST | Execute end-to-end system test suite: full flow from barcode scan → stock receiv | End-to-end validation, performance |

**Total tasks:** 29 | **Compliance tasks:** 5 | **Coverage:** 17%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |

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
| developer | 12 | Engineering |
| devops_engineer | 3 | Engineering |
| regulatory_specialist | 2 | Compliance |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| marketing_strategist | 1 | Operations |
| business_analyst | 1 | Analysis |
| ux_designer | 1 | Design |
| financial_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| data_scientist | 1 | Analysis |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 62/100 (FAIL) — 1 iteration(s)

**Summary:** This is a thorough and professionally structured plan with good coverage of the product surface area, compliance artifacts, and operational concerns. The dependency graph is logical, the tech stack is sound, and the inclusion of STRIDE threat modeling, PCI DSS artifacts, chaos testing, and HITL gates for PO approval reflects genuine production thinking. However, the plan has several critical gaps that would cause failures before the first paying customer reaches steady state: the ML forecasting pipeline has no cold-start strategy and will be useless for 3+ months after onboarding; stock mutation paths have no concurrency control and will produce corrupt inventory counts under normal multi-source load; order import has no idempotency design and will oversell; and the PCI SAQ type ambiguity could invalidate the entire compliance effort if resolved incorrectly after the architecture is built. The marketplace integrations — particularly Amazon SP-API — are underestimated in complexity and rate-limit budget management. The plan reads as designed by someone with strong breadth but insufficient depth on the hardest technical problems: concurrent stock mutation, ML cold-start, and multi-tenant secret isolation at scale. Score 62: solid foundation with a believable scope, but fundamental rework required on concurrency design, idempotency, ML cold-start, and PCI scoping before this is production-safe.

### Flaws Identified

1. ML cold-start problem is completely unaddressed (Step 14): the model requires ≥90 days of movement history per SKU, meaning every new customer gets zero forecasts at onboarding. No fallback strategy (category-level models, velocity input wizard, similar-SKU clustering) exists. This blocks the product's core value proposition for 3 months after signup.
2. Concurrency and row-level locking omitted across Steps 11-13: multiple sources (barcode scan, marketplace order import, manual adjustment, PO receipt) can hit the same SKU stock_level simultaneously. No SELECT FOR UPDATE / optimistic locking / MVCC strategy is defined. This will cause negative stock levels and silent data corruption in production.
3. Order import idempotency not designed (Step 15): Celery workers retrying a failed import, combined with 15-minute polling overlap, will create duplicate stock deductions. No idempotency key pattern is defined for order ingestion. Overselling is the direct consequence.
4. PCI DSS SAQ type is deferred as a decision (Step 7), but it should drive the entire architecture. If the billing integration ever touches raw cardholder data, it's SAQ-D (300+ controls). SAQ-A only applies if payment is fully outsourced with no cardholder data touching your systems. This ambiguity means the compliance scope could double after architecture is locked.
5. Amazon SP-API complexity is severely underestimated (Step 15): inventory quantity on Amazon is not a real-time push — it requires the Feeds API (async, throttled) or FBA inventory reports. SP-API throttles at the selling-partner level, not at the API-key level, so a single tenant's aggressive sync can consume the shared rate limit budget for all tenants. Multi-tenant token management under SP-API requires each seller to individually authorize via LWA — there's no shared app flow.
6. WebSocket scaling for barcode scanning is broken in ECS Fargate (Step 12): WebSocket connections are stateful. Load-balanced ECS Fargate with multiple task instances requires Redis pub/sub or sticky sessions to route scanner messages to the correct backend instance. This isn't designed, meaning the '20 scans/second' benchmark only holds for single-instance deployments.
7. GDPR right to erasure conflicts with immutable audit log (Step 23 acceptance criteria: no UPDATE/DELETE on movements table): stock movements and audit logs likely contain user_id (personal data). GDPR Article 17 requires erasure on request. Pseudonymization strategy is absent — this will require retroactive schema redesign.
8. No connection pooling strategy for multi-tenant async workload: SQLAlchemy 2.0 async with multiple Fargate tasks + Celery workers against a single RDS instance will exhaust connections under load. PgBouncer or asyncpg pool sizing is not mentioned anywhere. RDS max_connections for a db.r6g.large is ~1000 — this ceiling will be hit before the performance targets are.
9. Conflict resolution for concurrent marketplace updates is undefined beyond 'configurable_per_channel': if stock changes simultaneously on Amazon (order deducted), Shopify (manual adjustment), and local (barcode scan), the sync engine has no defined merge strategy. The acceptance criteria say 'audit trail' but not which value wins. This will cause overselling on high-velocity SKUs.
10. Forecast job at scale is unrealistic for the acceptance criteria timeline (Step 14): '1000 SKUs in 10 minutes on 4-core CPU' may hold at MVP, but with a typical SMB catalog of 10,000-50,000 SKUs, this grows to 100-500 minutes. No incremental training, model caching, or SKU batching strategy is designed. The financial model (Step 4) also doesn't account for ML compute costs per tenant at scale.
11. Celery default serializer is pickle — an RCE vector: the plan uses Celery throughout (Steps 12, 13, 14, 15) but never specifies task_serializer='json'. Pickle deserialization of untrusted input is a known arbitrary code execution vulnerability. This is not in the threat model despite STRIDE coverage.
12. Step 21 PKCE is misapplied: PKCE is for public (browser/mobile) OAuth clients where a client secret cannot be kept confidential. The marketplace OAuth flows (Amazon LWA, eBay, Shopify) for a server-side SaaS backend should use confidential client flows with client_secret stored in Secrets Manager. Requiring PKCE for the backend introduces unnecessary complexity and may not be supported by all three marketplace OAuth servers.

### Suggestions

1. Design a cold-start path for new tenants in Step 14: offer manual velocity input (units sold/week per SKU), category-level priors, and a 'not enough data' state with explicit messaging. Gate the ML forecast behind a minimum data threshold and fall back to simple exponential smoothing (statsmodels ETS) which works on 14+ days of data.
2. Add an explicit locking strategy document as a prerequisite to Step 11: define per-SKU advisory locks or SELECT FOR UPDATE SKIP LOCKED for all stock mutation paths. Stock movements must be serialized per SKU, not per-tenant. Consider an event-sourced ledger model where stock_level is a projection, not a mutable field.
3. Add idempotency_key column to orders and sync_job tables before Step 15 implementation: hash (marketplace, order_id) as the key. Enforce UNIQUE constraint. Celery retry + manual rerun should be safe by default.
4. Resolve PCI SAQ type in Step 5 (Legal), not Step 7 (Compliance): the SAQ determination should feed into the architecture of the billing integration. If SAQ-D applies, significant additional controls (pen test scope, log review, vulnerability management) must be added to Steps 6, 7, 25, 26.
5. Add a marketplace API rate-limit budget manager as a first-class component in Step 15: model it as a token bucket per (tenant, marketplace) pair with Redis. Reject sync jobs that would exceed the daily/hourly SP-API quota. Log quota consumption per tenant for billing purposes.
6. Add Redis pub/sub WebSocket routing layer in Step 10 infrastructure setup: configure the FastAPI barcode WebSocket endpoint to publish to a Redis channel and subscribe across all worker instances. This is the standard pattern for stateful connections behind a load balancer.
7. Add pseudonymization design for audit tables before Step 9 schema design: user_id in stock_movements and audit_log should be a pseudonymous reference. Store the mapping in a separate 'identity vault' that can be deleted on GDPR erasure request without corrupting the movement ledger.
8. Split Step 14 ML work into two phases: (a) feature pipeline + data quality validation, then (b) model training and serving. The forecast accuracy acceptance criteria (MAPE ≤20%) cannot be validated until you have real customer data — add a 'model readiness gate' that prevents forecast UI from going live until sufficient history exists.
9. Add PgBouncer sidecar to Step 10 Docker Compose and Step 26 Terraform: define connection pool sizing per service (FastAPI: 20 max, Celery: 10 per worker). Document RDS max_connections ceiling and set alarm when usage exceeds 80%.
10. Add Celery task serializer enforcement to Step 10 config: CELERY_TASK_SERIALIZER='json', CELERY_ACCEPT_CONTENT=['json']. This is a one-line config change that eliminates the pickle RCE class entirely.
11. Add distributed tracing (AWS X-Ray or OpenTelemetry) to Step 25: marketplace sync failures and forecast job failures are async and will be nearly impossible to debug with metrics alone. Trace IDs should propagate from API request through Celery task to DB query.
12. Step 3 requires recruiting 5 participants across 4 personas — plan for 2-3 per persona (8-12 total) or explicitly accept the research as directional only: one-interview-per-persona is not statistically meaningful for design decisions that will affect all warehouse operators.

### Missing Elements

1. Data migration strategy: no onboarding path for customers moving from spreadsheets, Cin7, or Fishbowl. This is the #1 adoption blocker for inventory management tools. A CSV import wizard with field mapping and validation is table stakes.
2. API idempotency specification: no mention of Idempotency-Key header pattern for POST endpoints (create stock movement, create PO, trigger sync). Without this, all client retries and webhook re-deliveries are unsafe.
3. Shopify API version lifecycle management: Shopify deprecates API versions quarterly and requires migration every 12 months. No versioning pinning, upgrade notification, or migration strategy is present.
4. Negative stock handling policy: what happens when a marketplace order arrives for a SKU that is already at zero? Allow negative stock? Block sync? Queue for back-order? This business rule is not defined anywhere and will surface immediately in production.
5. Disaster recovery testing: Step 26 defines Multi-AZ RDS but no backup/restore drill is planned. RTO ≤15 minutes is asserted in Step 27 but never verified. Point-in-time recovery test should be a Step 26 acceptance criterion.
6. Marketplace sandbox limitations documentation: Amazon, eBay, and Shopify sandboxes all have known gaps vs. production (Amazon sandbox doesn't support all SP-API operations; Shopify test orders don't trigger all webhooks). Step 24 E2E tests on sandbox APIs will have false positives that fail silently in production.
7. PO auto-generation rate limiting: Step 13 auto-generates POs when stock falls below reorder_point, but there's no guard against a bad forecast or data anomaly triggering hundreds of POs in minutes. A 'max POs per hour' circuit breaker is missing.
8. Multi-tenant secret isolation strategy: Step 26 stores OAuth tokens in Secrets Manager, but the architecture for per-tenant secret isolation isn't defined. Storing all tokens in one secret vs. one secret per tenant has significant IAM and cost implications at 100+ tenants.
9. Supplier portal or EDI integration: the plan sends supplier emails (Step 13) but has no defined strategy for structured supplier responses (order acknowledgement, delivery confirmation). Manual email parsing will be the bottleneck in the PO lifecycle at any meaningful volume.
10. SLA enforcement mechanism: Step 27 defines SLAs (99.5% uptime, 15-min sync lag) but there's no customer-facing SLA breach notification, credit calculation, or contractual enforcement mechanism — typically required for B2B SaaS with paying customers.
11. RBAC / permissions model: four personas (warehouse operator, purchasing manager, e-commerce seller, finance analyst) have very different permission requirements, but no role-based access control schema, permission matrix, or API authorization middleware is designed in any step.
12. Multi-warehouse stock allocation logic: if a product exists in 3 warehouses and a Shopify order arrives, which warehouse fulfills it? No allocation rules (nearest, FIFO, priority) are defined — this is the core business logic of a WMS.

### Security Risks

1. Celery pickle serialization (RCE): not explicitly disabled anywhere in the plan. Any Celery worker processing tasks from an insufficiently isolated queue can execute arbitrary code via a crafted pickle payload. Must set task_serializer='json' in Step 10.
2. Marketplace OAuth token exposure in logs: async Celery tasks that log request/response details for debugging will capture OAuth Bearer tokens in CloudWatch Logs unless explicit scrubbing middleware is applied. The threat model (Step 6) notes token storage but not token logging surface.
3. Barcode WebSocket endpoint authentication gap: Step 12 defines a WebSocket endpoint for scanner input. WebSocket upgrade requests bypass standard HTTP middleware auth chains in many FastAPI configurations. Explicit JWT validation on the WebSocket upgrade handshake must be called out — it is not.
4. PO auto-generation as a financial control bypass: a malicious tenant with write access to stock_levels or reorder_point values could artificially trigger large POs. The '$500 threshold for human approval' (Step 16) is the only control, but manipulating reorder_point to generate many sub-$500 POs bypasses it. No aggregate daily PO value cap per tenant is defined.
5. Multi-tenant RLS bypass via SQLAlchemy connection pooling: if a connection is reused across requests with different tenant contexts (a common async pool bug), RLS will enforce the wrong tenant's policy. The tenant context must be set at the DB session level on every request — this is a subtle async bug that the plan doesn't guard against explicitly.
6. Bulk operations without row-level authorization: Step 21 allows bulk price override for 500 SKUs. If the authorization check is only at the endpoint level (not per-SKU), a tenant could override pricing for SKUs belonging to a different tenant if any data isolation bug exists. Per-row authorization on bulk operations is not mentioned.
7. Secrets Manager IAM over-privilege risk: Step 26 places all marketplace OAuth tokens in Secrets Manager, but if the ECS task role has GetSecretValue on all secrets (a common misconfiguration), a compromised container can exfiltrate every tenant's OAuth tokens. Least-privilege secret access per service must be defined.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.322139
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

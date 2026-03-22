# Regulatory Compliance — Analytics Dashboard

**Domain:** saas
**Solution ID:** 036
**Generated:** 2026-03-22T11:53:39.318914
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **GDPR**
- **ISO 27001**

## 2. Domain Detection Results

- saas (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 6 | LEGAL | Draft Terms of Service, Privacy Policy, Data Processing Agreement (DPA), and emb | Privacy, licensing, contracts |
| Step 7 | COMPLIANCE | Scope SOC 2 Type I readiness for analytics_dashboard. Produce a trust services c | Standards mapping, DHF, traceability |
| Step 22 | SECURITY | Conduct threat model for analytics_dashboard using STRIDE. Focus on: credential  | Threat modeling, penetration testing |

**Total tasks:** 25 | **Compliance tasks:** 3 | **Coverage:** 12%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 3 | ISO 27001 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |

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
| marketing_strategist | 1 | Operations |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| financial_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| data_scientist | 1 | Analysis |
| qa_engineer | 1 | Engineering |
| operations_manager | 1 | Operations |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 61/100 (FAIL) — 1 iteration(s)

**Summary:** This is a well-structured plan with appropriate sequencing, a reasonable tech stack, and commendable coverage of SOC 2, legal, UX research, and financial modeling. However, it has two fundamental technical errors that will block shipping: (1) WeasyPrint cannot render JavaScript-based ECharts charts — PDF reports will be broken at launch and require an architectural pivot to headless browser rendering; (2) sqlparse is not a security control and ships a SQL injection vulnerability in the raw query editor. Beyond these blockers, the security model has several compounding weaknesses: an invalid X-Frame-Options header, an ephemeral revocation blacklist, and an org-secret HS256 scheme where the customer holds the signing key. The ML chart recommendation model is an unnecessary complexity trap — it's trained on synthetic data derived from heuristics, adding MLOps overhead to deliver what a 20-line rule function achieves. The plan also has a critical dependency omission (Step 15 should depend on Step 17) that will cause integration rework mid-sprint. At 25 steps covering market research through Kubernetes Helm charts and PagerDuty integration, this is realistically a 12-18 month effort, not a 6-month roadmap. Fix the PDF rendering architecture and SQL injection controls before any other development begins — these are not deferrable.

### Flaws Identified

1. CRITICAL: WeasyPrint cannot render ECharts charts. WeasyPrint renders HTML/CSS — it has no JavaScript engine. ECharts is a JS library that renders to canvas/SVG in the browser. PDF reports with charts will either be blank or fail entirely. You need a headless browser (Puppeteer/Playwright) for server-side chart rendering, which is not mentioned anywhere in the plan.
2. CRITICAL: 'X-Frame-Options: ALLOWALL' (Step 13) is not a valid HTTP header value. Valid values are DENY, SAMEORIGIN, and the deprecated ALLOW-FROM. This will be ignored by all major browsers, leaving the embedding security model broken at launch. The correct approach is CSP frame-ancestors, which the plan mentions but then contradicts with this invalid header.
3. HIGH: SQL injection prevention via sqlparse (Step 9) is not a security control. sqlparse is a formatting/parsing library explicitly documented as not safe for security use. It can be bypassed with CTEs, subqueries, string concatenation patterns, and Unicode obfuscation. Blocking DROP/DELETE/UPDATE via regex/sqlparse is fragile and gives false confidence — a determined user can bypass it.
4. HIGH: Redis-backed token revocation blacklist (Step 13) loses its entire state on Redis restart or failover. Revoked tokens become valid again after any Redis outage. The plan has no persistence layer for the revocation list, no fallback, and no mention of this failure mode.
5. HIGH: Fernet key management is unaddressed. Credentials are encrypted with Fernet, but where is the Fernet key stored? If it's an environment variable, key rotation strategy is completely missing. A rotated key invalidates all stored credentials. This is an operational crisis waiting to happen.
6. HIGH: Celery Beat is deployed as a Kubernetes CronJob (Step 20) but Beat is designed as a long-running daemon process, not a job. Running multiple Beat instances (if the CronJob overlaps) causes duplicate scheduled report executions. The Helm chart must enforce singleton Beat — this requires careful pod disruption budget and locking strategy not mentioned anywhere.
7. MEDIUM: Step 15 (chart builder canvas) does not declare Step 17 (query builder) as a dependency, but the chart builder's field binding panel maps data columns to axes — it fundamentally requires the query builder's schema inference and data fetching. Building Step 15 before Step 17 guarantees integration rework.
8. MEDIUM: HS256 embedding tokens signed with 'org secret' (Step 13) means every token ever issued by an org is compromised if that org secret leaks. There is no per-token key isolation. RS256 with a per-org keypair would limit blast radius.
9. MEDIUM: ML chart recommendation model (Step 18) is trained on synthetic data generated by heuristic rules. This is circular — the model learns to approximate the heuristics. The added complexity of GradientBoostingClassifier + MiniLM embeddings delivers no accuracy advantage over the heuristics themselves, adds a 200MB+ model artifact, and creates an MLOps dependency for what should be a simple lookup table.
10. MEDIUM: Query cache key uses 'normalized SQL' (Step 17) but SQL normalization is non-trivial. Semantically identical queries differing in whitespace, comment presence, alias names, or predicate ordering will miss cache. The plan provides no normalization specification, making the '≥60% cache hit rate' acceptance criterion unmeasurable.
11. MEDIUM: No per-tenant connection pool isolation for data connectors (Step 9). One tenant running 50 concurrent long-running BigQuery queries will exhaust the shared connection pool, causing latency spikes for all other tenants. This is a multi-tenant SaaS correctness requirement, not an optimization.
12. MEDIUM: BigQuery and Snowflake query costs are entirely uncontrolled. A user can execute a query scanning terabytes of data. No per-tenant query cost limits, dry-run checks, or byte-scanned caps are specified. This is a financial liability — a single bad query can generate a $500 cloud bill.

### Suggestions

1. Replace WeasyPrint with Puppeteer/Playwright (Node) or a Python-controlled headless Chromium for PDF generation. The backend renders the dashboard URL in headless mode, screenshots it, and converts to PDF. This is the only reliable way to capture JS-rendered charts.
2. Replace sqlparse SQL injection prevention with a proper AST-based SQL parser (sqlglot or pglast). Use a whitelist approach: only SELECT statements are allowed in the query builder. Reject anything that isn't a SELECT at the AST level, not via string matching.
3. Add a persistence layer for the embedding token revocation list. Use a dedicated PostgreSQL table (revoked_tokens) as the source of truth, with Redis as a write-through cache. Redis miss falls back to DB lookup. This survives Redis restarts.
4. Replace the ML chart recommendation model with a deterministic rule engine. A decision tree of 15-20 hand-crafted rules based on column type counts and cardinality covers 90% of cases with zero model artifacts, zero MLOps overhead, and 100% explainability. Add the ML model in v2 when you have real usage data to train on.
5. Add Step 17 as a dependency of Step 15. The chart builder's data binding panel is a consumer of the query builder's schema inference output — they must be built in sequence.
6. Specify Fernet key rotation strategy before Step 9 is built. Options: (1) store in AWS KMS/GCP KMS with envelope encryption, (2) use HashiCorp Vault transit encryption (re-encrypt without decrypting), (3) store key version alongside ciphertext for rotation. Choose one and document it in the credential schema.
7. Deploy Celery Beat as a Kubernetes Deployment with replicas: 1 and a PodDisruptionBudget of maxUnavailable: 0, not as a CronJob. Add a distributed lock (Redlock or DB advisory lock) on Beat startup as a defense-in-depth measure against duplicate execution.
8. Add BigQuery/Snowflake query cost controls to Step 9: BigQuery dry-run API call before execution to estimate bytes scanned, reject if above per-tenant limit; Snowflake query tag + warehouse size cap. These are API-level features that require deliberate implementation.

### Missing Elements

1. Fernet/KMS key rotation runbook and schema versioning for encrypted credentials. Without this, the first key rotation is an operational incident.
2. Per-tenant database connection limits and query concurrency caps. Multi-tenant correctness requires isolation at the connection pool level, not just the org_id filter level.
3. Server-side chart rendering architecture for PDF reports. The current plan has a fundamental technical gap here.
4. BigQuery/Snowflake cost governance controls (byte scan limits, dry-run validation, per-tenant spending caps).
5. Dashboard public sharing model — can dashboards be shared via link without embedding tokens? This is a core BI feature completely absent from all 25 steps.
6. Data freshness indicators — users need to know when cached data was last refreshed. No staleness UI or cache invalidation trigger is specified.
7. Connector credential rotation workflow — when a database password changes, how does the user update it? Is the old credential immediately invalidated? What happens to in-flight queries?
8. Actual JavaScript/TypeScript SDK npm package for the embedding SDK. The plan describes iframe/React/Vue code snippets but no versioned, publishable SDK package with its own repository, changelog, and semver guarantees.
9. PostgreSQL RLS policy testing strategy. RLS misconfiguration is silent and catastrophic for multi-tenant SaaS. The plan enables RLS but has no acceptance criteria for verifying it actually blocks cross-tenant access at the database layer (separate from the application-layer org_id filter).
10. Disaster recovery plan and RTO/RPO targets. SOC 2 CC9 requires risk assessment of availability — the runbooks cover incident response but not full DR scenarios (region failure, data corruption).

### Security Risks

1. CRITICAL: sqlparse-based SQL injection prevention (Step 9) is bypassable. This is documented by sqlparse maintainers. Any plan that ships a raw SQL editor with sqlparse as the security gate has a SQL injection vulnerability in production.
2. HIGH: X-Frame-Options: ALLOWALL is ignored by browsers. The embedding security boundary — the primary security control for the embedding SDK — is broken until this is corrected to CSP frame-ancestors.
3. HIGH: Shared HS256 org secret for embedding tokens means org-level secret compromise = all historical and future tokens for that org are forgeable. No expiry on the signing key itself is mentioned.
4. HIGH: Redis revocation blacklist is ephemeral. A Redis restart between token issuance and expiry silently un-revokes tokens. For an enterprise embedding SDK, this is a security regression.
5. MEDIUM: SSRF via Slack webhook delivery URLs (Step 12) is acknowledged in Step 22 but no mitigation is implemented in Step 12. The delivery channel accepts arbitrary webhook URLs — an attacker can point this at internal AWS metadata endpoints (169.254.169.254) or internal services. Implement an allowlist of HTTPS-only webhook domains with internal RFC 1918 range blocking before Step 12 ships.
6. MEDIUM: The embedding token includes allowed_origins as a claim inside the token. If the token is signed with HS256 using the org secret, and the org can create tokens (they must be able to, to use the SDK), a malicious org can mint tokens with allowed_origins=['*'] if they have access to the signing key. The allowed_origins should be validated server-side against a registry, not trusted from the token claim.
7. LOW: MiniLM embeddings for column names in the ML model (Step 18) means column names from customer databases are processed through a model. If this model is ever externalized (e.g., OpenAI API call instead of local), column names — which may contain PII field names — leave the customer's trust boundary. Ensure the inference endpoint remains local as specified and document this constraint.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.318946
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

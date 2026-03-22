# Regulatory Compliance — Api Gateway

**Domain:** saas
**Solution ID:** 040
**Generated:** 2026-03-22T11:53:39.320064
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **ISO 27001**
- **OAuth 2.0/OIDC**

## 2. Domain Detection Results

- saas (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | LEGAL | Draft all legal artifacts for api_gateway: Terms of Service, Privacy Policy (GDP | Privacy, licensing, contracts |
| Step 9 | COMPLIANCE | Define the SOC 2 Type II evidence collection framework for api_gateway. Map Trus | Standards mapping, DHF, traceability |
| Step 18 | SECURITY | Conduct a full security review: threat model (STRIDE) for gateway proxy and key  | Threat modeling, penetration testing |
| Step 24 | SYSTEM_TEST | Execute full system integration test suite: end-to-end load test (10k req/s sust | End-to-end validation, performance |

**Total tasks:** 24 | **Compliance tasks:** 4 | **Coverage:** 17%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | ISO 27001 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | OAuth 2.0/OIDC compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 8 | Engineering |
| regulatory_specialist | 2 | Compliance |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| marketing_strategist | 1 | Operations |
| business_analyst | 1 | Analysis |
| financial_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| data_scientist | 1 | Analysis |
| operations_manager | 1 | Operations |
| technical_writer | 1 | Operations |
| system_tester | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 58/100 (FAIL) — 1 iteration(s)

**Summary:** This is a well-structured, comprehensive plan that covers the right categories for a production API management platform — the dependency graph is logical, acceptance criteria are mostly measurable, and the technology choices are defensible. However, it has two critical security anti-patterns that must be fixed before any code is written: storing plaintext API keys in Redis (Step 13) and using bcrypt for per-request key lookup (Steps 13/11), which is both a security flaw and a performance impossibility given the stated latency targets. The plan also has a critical business gap — zero billing implementation despite defining four paid pricing tiers across three steps. The performance target (p99 < 5ms, 10k req/s) with an undecided Python/Go language choice is a deferred architectural risk that will force expensive rewrites. The SOC 2 Type II framing is unrealistic as a build deliverable. Fixing the bcrypt/Redis key design, adding billing infrastructure, deciding the gateway language, and adding Redis HA would push this to a 75-80 range. As written, the critical security flaws and missing billing make this unshippable as a commercial product.

### Flaws Identified

1. Step 13 uses bcrypt for API key lookup — bcrypt is intentionally slow (~100-300ms per check). Per-request key authentication cannot go through bcrypt on cache miss. The correct pattern is: store a fast hash (SHA-256/BLAKE2) for lookup indexed by key prefix, and bcrypt only for optional secondary verification. This breaks the < 2ms lookup SLA on every cold cache miss.
2. Step 13 stores plaintext API keys in Redis as a 'lookup cache'. If Redis is compromised (common attack surface), every active key is exposed in cleartext. Redis should store the fast hash, not the plaintext. This is a critical security anti-pattern for a key management service.
3. Step 11 targets p99 added latency < 5ms using 'Python (FastAPI + httpx) or Go'. Python cannot reliably hit 5ms p99 under 1000 req/s once you add Redis round-trip (~0.5ms), async httpx proxying, and route DB hot-reload. The plan defers the language decision to implementation time — this is an architectural decision that must be made before code is written, not during.
4. There is zero billing implementation anywhere in 24 steps. Steps 2–3 define pricing tiers and financial models; steps 15–16 build the portal. But there is no Stripe/payment provider integration, no subscription lifecycle management, no metered billing hooks, no invoice generation, and no dunning flow. Without billing, this is not a SaaS product — it is a free product with unpaid premium tiers.
5. Step 9 claims 'SOC 2 Type II evidence collection framework' as a deliverable. SOC 2 Type II requires a minimum 6-month observation period before an auditor can opine. This plan treats it as a document artifact. The deliverable should be 'SOC 2 Type II readiness' — the certification itself cannot be a build output.
6. Redis is a single point of failure for rate limiting (Step 12), key lookup cache (Step 13), request dedup (Step 8), and the analytics pipeline (Step 14). Step 24 explicitly accepts 'allow-all mode' on Redis failure — meaning any Redis outage fully disables rate limiting, making the gateway unprotected. Redis Sentinel or Redis Cluster is not mentioned anywhere.
7. The gateway (Step 11) implements reverse proxying with configurable upstream URLs from an admin API. This creates an SSRF attack vector: a malicious admin could configure 'http://169.254.169.254/latest/meta-data/' as an upstream. The pentest plan (Step 18) lists SSRF as a test target but no mitigation control is mandated in the gateway implementation step — the threat is identified but not mitigated.
8. Step 20 acceptance criterion: 'All E2E tests deterministic — no flaky assertions; retry count set to 0 in CI.' Playwright tests against a full Docker Compose stack with real database timing, email verification, and cache invalidation windows will have inherent timing nondeterminism. Setting retry to 0 with this criterion will produce a permanently failing CI suite. This criterion is aspirational, not achievable.
9. Steps 11–15 never define where API key authentication happens in the gateway request pipeline. The orchestration of: authenticate key → resolve tenant → check rate limit → proxy upstream → emit analytics event is the most critical hot-path design decision and is split across steps 11, 12, 13 with no integration spec. The middleware chain order (auth before rate limit, or rate limit before auth?) has significant security implications.
10. Step 14 uses Redis Streams for the analytics pipeline at 10k req/s — that's 864M events/day. The plan defines 7-day raw log retention but provides no sizing for Redis Stream memory (at ~200 bytes/event = ~1.7TB/day of Stream data before compaction). No consumer group dead-letter handling or backpressure mechanism is defined.

### Suggestions

1. Replace bcrypt for key lookup with a two-field storage model: store a SHA-256 or BLAKE2b hash of the full key (fast, for lookup) plus an optional bcrypt hash (slow, for secondary audit verification if ever needed). Index the fast hash. Cache the fast hash in Redis, never the plaintext.
2. Decide Go vs Python for the gateway in Step 5 (PRD) or Step 7 (API design), not Step 11. If the 5ms p99 target is a hard SLA, Go is required. If Python is chosen, revise the latency target to p99 < 15ms, which is achievable with proper async httpx + connection pooling.
3. Add a Step 10.5 or amend Step 15: Billing Integration — Stripe (or equivalent) subscription management, metered usage reporting, plan enforcement (block requests when quota exhausted), invoice webhooks, and dunning emails. Without this, Steps 3 and 16 are vaporware.
4. Add SSRF mitigations to Step 11 acceptance criteria: upstream URL allowlist or deny-list (block RFC 1918, link-local, loopback), URL scheme enforcement (https only in prod), and request timeout enforcement to prevent proxy-based port scanning.
5. Change Step 9 scope from 'SOC 2 Type II' to 'SOC 2 Type II Readiness'. Add a note that audit observation period begins at production launch. Actual Type II report is a ~12-month post-launch milestone.
6. Add Redis HA to Step 10 (infrastructure scaffold): Redis Sentinel for failover or Redis Cluster for sharding. Change Step 12 and Step 24 Redis failure behavior from 'allow-all fallback' to 'last-known-rate-limit fallback with TTL' — safer degraded mode than open admission.
7. Add a dedicated Step 11.5 or acceptance criterion to Step 11: define and implement the gateway middleware pipeline spec — the exact order of middleware execution (auth → tenant resolution → rate limit → upstream proxy → response transform → analytics emit) with latency budget allocated per stage.
8. Add email provider setup to Step 10 infrastructure scaffold (.env.example should include SMTP/SendGrid config). Step 15's email verification acceptance criterion is currently undeliverable without an email provider in the dev environment.
9. Step 20 E2E: change retry count from 0 to 2 with documented flake tracking, and add explicit wait conditions (waitForResponse, waitForSelector) instead of fixed sleeps. Determinism comes from proper async handling, not zero retries.
10. Add PgBouncer or explicit connection pool sizing to Step 8 (database design) and Step 10 (infra scaffold). At 10k req/s with multiple services, naive PostgreSQL connection handling will exhaust connection limits before hitting any application bottleneck.

### Missing Elements

1. Billing / payment infrastructure (Stripe integration, subscription lifecycle, metered billing, dunning) — entirely absent across all 24 steps
2. Email provider configuration and transactional email templates (verification, key creation confirmation, rate limit warnings, invoice receipts)
3. Redis HA topology (Sentinel or Cluster) — the plan assumes a single Redis instance for all critical workloads
4. Gateway middleware pipeline integration spec — the auth→rate-limit→proxy execution order and latency budget per stage
5. SSRF mitigation controls in the gateway implementation (upstream URL validation, RFC 1918 blocking)
6. Database connection pooling strategy (PgBouncer configuration, pool sizing per service)
7. Key prefix indexing design — how the gateway maps an incoming `sk_live_...` key to its stored hash without full table scan
8. Webhook retry logic, exponential backoff, dead-letter queue, and at-least-once delivery guarantee (Step 15 mentions webhooks but omits delivery reliability mechanics)
9. Multi-instance rate limit coordination specification — what happens when 10 gateway pods all hit Redis simultaneously for the same tenant's counter
10. Test data isolation strategy — how integration tests clean up between runs without interfering with each other in shared PostgreSQL/Redis instances
11. Tenant isolation validation — confirmation that tenant A cannot access tenant B's keys, routes, or analytics via API parameter manipulation (IDOR testing)

### Security Risks

1. CRITICAL: Plaintext API keys stored in Redis cache (Step 13). Redis is a common lateral-movement target; this design hands an attacker every active key in the system on a single Redis compromise.
2. HIGH: Bcrypt on cache miss means the key authentication path has a 100-300ms window per missed cache entry, enabling timing-based key enumeration attacks and making bcrypt the practical rate limiter rather than the application's own rate limiter.
3. HIGH: SSRF via admin-configurable upstream URLs (Steps 11, 17). No mitigation is implemented — only tested in pentest plan. A compromised admin account gains SSRF against cloud metadata endpoints.
4. HIGH: 'Allow-all' rate limiting fallback on Redis failure (Step 24) — any Redis outage disables the platform's primary abuse prevention mechanism, enabling traffic amplification attacks during incidents.
5. MEDIUM: OpenAPI spec endpoint serving 'merged spec for all routes the developer's plan has access to' (Step 15) may leak internal upstream hostnames, IP addresses, or undocumented parameters if the upstream OpenAPI specs contain internal details.
6. MEDIUM: JWT refresh token rotation without explicit mention of refresh token binding (device fingerprint, IP) or revocation list — a stolen refresh token is valid for 7 days with no revocation mechanism described.
7. MEDIUM: Tenant isolation relies on application-level tenant_id filtering. No database row-level security (RLS) or schema-per-tenant isolation is specified. A query injection or ORM misconfiguration could break tenant boundaries.
8. LOW: Pre-commit secret scanning with gitleaks (Step 10) only catches secrets at commit time. CI pipeline secret scanning (Step 21) should also run on PRs — the plan lists 'security scan' in CI but doesn't specify the tool or scope.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.320098
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

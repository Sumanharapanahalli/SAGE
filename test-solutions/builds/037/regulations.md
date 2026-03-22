# Regulatory Compliance — Form Builder

**Domain:** saas
**Solution ID:** 037
**Generated:** 2026-03-22T11:53:39.319192
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **GDPR**
- **PCI DSS**

## 2. Domain Detection Results

- saas (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 3 | LEGAL | Draft Terms of Service, Privacy Policy, Data Processing Agreement (GDPR/CCPA), a | Privacy, licensing, contracts |
| Step 21 | SECURITY | Perform threat model (STRIDE) for the form builder: identify threats to public s | Threat modeling, penetration testing |
| Step 22 | COMPLIANCE | Produce SOC 2 Type I readiness artifacts: security policy documentation, access  | Standards mapping, DHF, traceability |
| Step 24 | QA | Design and execute manual QA test plan covering: form builder usability (20 fiel | Verification & validation |
| Step 25 | SYSTEM_TEST | Execute end-to-end system test suite and load tests: full flow (create form → ad | End-to-end validation, performance |

**Total tasks:** 28 | **Compliance tasks:** 5 | **Coverage:** 18%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 3 | PCI DSS compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |

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
| developer | 15 | Engineering |
| qa_engineer | 2 | Engineering |
| marketing_strategist | 1 | Operations |
| business_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| financial_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| regulatory_specialist | 1 | Compliance |
| system_tester | 1 | Engineering |
| devops_engineer | 1 | Engineering |
| operations_manager | 1 | Operations |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 63/100 (FAIL) — 1 iteration(s)

**Summary:** This is a well-structured, comprehensive plan that covers the full product lifecycle from market research to operations. The dependency graph is mostly coherent, acceptance criteria are specific, and critical security surfaces (PCI scope, HMAC signatures, RLS) are addressed in principle. However, several concrete failure modes undermine production readiness: the SSRF vulnerability window between Step 13 and Step 21 is a direct security regression; the virus scan async gap creates a malware delivery path through the response payload; the progressive-enhancement criterion directly contradicts Stripe.js and S3 dependencies; and the analytics performance target is unachievable without a firm commitment to TimescaleDB. The undo/redo requirement is dramatically underscoped for a field-reference-aware conditional logic system. For an MVP targeting SMBs without file uploads or payments, the plan scores higher — the core builder, webhook, and submission pipeline are sound. For a production multi-tenant SaaS with payment collection and file uploads as Day 1 features, the missing IaC, SSRF controls in the right step, email service integration, and bot protection are gaps that will be discovered in staging at the worst possible time. Recommend: resolve the SSRF step ordering, commit to TimescaleDB, add an IaC step, and remove the no-JS contradiction before starting implementation.

### Flaws Identified

1. Step 18 acceptance criteria demands progressive enhancement ('form submits with no JavaScript enabled') yet Step 12 mandates Stripe.js and Step 11 mandates pre-signed S3 upload URLs — both require JavaScript. These criteria directly contradict each other and will fail QA.
2. Step 13 (webhook worker) has no SSRF mitigation in its own acceptance criteria. SSRF protection appears only in Step 21 (threat model), which depends on Steps 10-15 being complete. This means the webhook delivery system ships to staging without SSRF controls, exposing internal services to attacker-controlled URLs for the entire build window.
3. File upload async gap in Step 11: the response is stored atomically in a single transaction (acceptance criteria), but virus scanning is triggered asynchronously via S3 event. There is no state machine or deferred-accept pattern defined for the race between 'submission stored' and 'file cleared by AV'. A malware file can be linked to a submitted response before the scan completes.
4. Step 16 treats undo/redo as a trivial acceptance criterion ('last 50 actions, Ctrl+Z/Y'). In a drag-and-drop form builder with conditional logic that references field IDs, undo is a complex CRDT/command-pattern problem. Zustand alone cannot correctly handle undo when a logic rule references a field that was subsequently deleted and then re-added. This will cause silent data corruption in rule references.
5. Step 3 (Legal) has no dependency on Step 4 (Financial). The ToS must include subscription cancellation and refund policies that depend on the pricing tiers defined in Step 4. Drafting ToS before pricing is defined forces a rewrite.
6. Step 25 load test target (1000 concurrent submissions for 5 minutes) is insufficiently aggressive for SaaS launch confidence. 1000 concurrent users is a modest number; a single viral embed on a popular site can spike well past this. The load scenario also doesn't test write amplification: 1 submission triggers DB write + S3 event + webhook fanout + analytics event — the real bottleneck.
7. Step 14 analytics performance target (<200ms on 1M+ events) is stated but the plan hedges 'TimescaleDB hypertable OR Postgres partitioned table' without committing. Standard Postgres partitioned tables without TimescaleDB continuous aggregates will not reliably hit 200ms for funnel queries on 1M rows. The target will fail during Step 25 load tests if TimescaleDB is not chosen.
8. Step 12 Stripe webhook handler does not explicitly require idempotency key handling. Stripe guarantees at-least-once delivery of webhook events. Without deduplication on the `stripe_event_id`, a retried `payment_intent.succeeded` event will double-credit a response as paid.
9. Step 9 (SAGE config for form_builder) is architecturally incoherent with the rest of the plan. Steps 10-28 build a standalone FastAPI product — not a SAGE solution extension. The SAGE YAML config at Step 9 has no consumers in the subsequent backend steps. It creates false organizational clarity without functional integration.
10. Analytics geographic heatmap (Steps 14, 19) has no IP geolocation dependency defined. MaxMind GeoIP2, IPInfo, or equivalent must be licensed and integrated. IP storage also triggers GDPR Article 4(1) personal data obligations not addressed in Step 3's DPA.

### Suggestions

1. Add SSRF mitigation directly to Step 13 acceptance criteria: 'Webhook URLs must be validated against a blocklist of private CIDRs (RFC 1918, loopback, link-local) before dispatch. HTTPS required. DNS rebinding protection via post-resolution IP check.' Do not defer this to Step 21.
2. Replace the 'no-JS progressive enhancement' criterion in Step 18 with a split: non-payment forms use semantic HTML form POST fallback; payment and file upload forms explicitly require JS with a clear degraded-state message.
3. Define an explicit file upload lifecycle state machine before Step 11: PENDING_UPLOAD → UPLOADED → SCANNING → CLEAN/REJECTED. Response submission should store file references in PENDING state and only surface them in the response inbox after CLEAN status. Add a compensation job to tombstone REJECTED files.
4. Add undo/redo architecture as an explicit sub-task of Step 16: define a command registry with typed inverse operations (AddField/RemoveField, UpdateLogicRule/RevertLogicRule). Each command must serialize the field ID references it touches. Test undo after deleting a field that is a logic rule target.
5. Add a Step 10.5 (or amend Step 13) for Stripe event idempotency: create a `stripe_events` table indexed on `stripe_event_id`, check-and-insert before processing, return 200 immediately on duplicate.
6. Add a dedicated step for IaC (Terraform/Pulumi) covering: VPC, RDS (multi-AZ Postgres 15), ElastiCache (Redis), EKS cluster, S3 buckets with lifecycle policies, CloudFront distribution for embed SDK delivery, and IAM roles. Step 26 assumes this infrastructure exists but no step creates it.
7. Add CAPTCHA/bot protection to Step 11 public submission endpoint. Define the mechanism (hCaptcha, Cloudflare Turnstile, or invisible token) and add it to the rate limiting acceptance criteria. Without it, form spam is trivially automated past the 100/min rate limit by distributing across IPs.
8. Add email service integration as an explicit dependency. Step 20 requires 'email delivery confirmation' for team invites, Step 22 lists SendGrid as a vendor, but no step configures transactional email. Add SendGrid (or Postmark) setup, template management, and SPF/DKIM configuration.
9. Commit to TimescaleDB in Step 14 or lower the analytics query SLA target to 500ms with a caveat that >90-day windows require pre-aggregated rollup tables. The hedge between TimescaleDB and Postgres partitioning is a decision that must be made before Step 7 schema design.
10. Add a Stripe Connect architecture decision before Step 12: if agencies collect payments for their clients' forms, raw Stripe charges will credit the platform account, not the end merchant. Decide now: platform model (Stripe Connect) vs. no-marketplace (form owner provides own Stripe keys).

### Missing Elements

1. Infrastructure as Code (Terraform/Pulumi) — no step provisions the actual cloud resources. Step 26 deploys to Kubernetes that is never defined.
2. CDN strategy for public form renderer and embed JS SDK delivery. The embed SDK must be served from a stable CDN URL, not the API origin.
3. Email service setup step (SendGrid/Postmark) — referenced in Step 22 vendor list but never configured or integrated in any step.
4. Form spam/bot protection (CAPTCHA or Cloudflare Turnstile) — public forms with no bot protection are an easy spam vector.
5. Database connection pooling strategy (PgBouncer or asyncpg pool) — FastAPI + SQLAlchemy on PostgreSQL at submission scale will exhaust connection limits without explicit pooling design.
6. Stripe idempotency and event deduplication design — not in any step's acceptance criteria.
7. Form version rollback UI and response compatibility — Steps 7 and 10 store versions but no acceptance criteria covers what happens to responses submitted against a rolled-back form version.
8. In-app response notification system — no step covers notifying form owners of new submissions (email digest, webhook to themselves, in-app push).
9. Multi-tenant data isolation test suite — RLS is defined in Step 7 but no test step explicitly attempts cross-tenant data access to verify isolation holds under RLS bypass patterns.
10. GDPR data subject request flow — the DPA in Step 3 mentions deletion procedures but no step implements the DELETE /responses/export?respondent_email= endpoint or the right-to-erasure workflow in the API or UI.
11. File type validation: Step 11 lists `.csv` and `.xlsx` in allowed_types alongside MIME wildcards, but `.xlsx` is `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` — the plan mixes extension and MIME notation inconsistently. Magic byte validation needs an explicit library choice (python-magic).
12. Celery worker autoscaling rules in production — Step 27 capacity model mentions '1 worker per 500 active forms' but no step configures KEDA or HPA for Celery workers in Kubernetes.

### Security Risks

1. SSRF via outbound webhooks: Step 13 implements webhook dispatch before Step 21 defines SSRF mitigations. An attacker who registers a webhook pointing to http://169.254.169.254/latest/meta-data/ will exfiltrate cloud metadata before the control is implemented. Mitigation must be in Step 13, not Step 21.
2. Embed token leakage: JWT embed tokens in Step 15 contain `allowed_origins` and are delivered to the browser. If the token is stored in localStorage by the JS SDK, XSS on the host page extracts the token, allowing attacker to submit unlimited responses from arbitrary origins using the leaked token outside the origin check.
3. Virus scan race window: a malicious file upload can be stored, linked to a response, and the response webhook fired before ClamAV confirms the file is clean. If the webhook recipient downloads the file URL from the response payload, they receive unscanned content.
4. Webhook HMAC secret storage: Step 13 defines per-webhook HMAC secrets but no step specifies where these secrets are stored server-side. If stored in the `webhooks` table as plaintext (the obvious implementation), a SQL injection or DB dump exposes all customer webhook secrets.
5. Logic engine regex operator (Step 10/17): allowing user-defined regex in conditional logic creates a ReDoS (Regular Expression Denial of Service) vector. A form builder with a malicious regex rule can pin a CPU core on every form submission. The acceptance criteria do not require regex timeout or complexity limits.
6. Public form submission with no authentication creates a response-stuffing vector: an attacker can enumerate active form_ids and flood them with synthetic responses, corrupting analytics and exhausting respondent quotas. The rate limit is per-form but doesn't prevent distributed multi-form attacks.
7. File upload path traversal: pre-signed S3 URLs in Step 11 must enforce a server-controlled S3 key prefix per workspace. If the S3 key is derived from any user-controlled input (filename, respondent field value), path traversal or key collision attacks can overwrite other workspace files.
8. Stripe webhook endpoint must be excluded from CSRF protection middleware and authentication, but the plan does not explicitly flag this endpoint for special routing rules. Applying a JWT auth middleware to the Stripe webhook endpoint will break payment event processing silently in production.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.319227
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

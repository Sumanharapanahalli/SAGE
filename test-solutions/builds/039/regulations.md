# Regulatory Compliance — Email Marketing

**Domain:** saas
**Solution ID:** 039
**Generated:** 2026-03-22T11:53:39.319782
**HITL Level:** standard

---

## 1. Applicable Standards

- **GDPR**
- **CAN-SPAM**
- **CCPA**
- **SOC 2**

## 2. Domain Detection Results

- saas (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | LEGAL | Draft Terms of Service, Privacy Policy, Data Processing Agreement (DPA) for GDPR | Privacy, licensing, contracts |
| Step 10 | COMPLIANCE | Define SOC 2 Type II compliance scope, control mapping, and evidence collection  | Standards mapping, DHF, traceability |
| Step 27 | SECURITY | Conduct security review: threat model (STRIDE), OWASP Top 10 assessment, authent | Threat modeling, penetration testing |
| Step 29 | QA | Author QA test plan covering manual and automated test cases for all six feature | Verification & validation |
| Step 30 | SYSTEM_TEST | Execute end-to-end system tests: full campaign lifecycle (create → segment → bui | End-to-end validation, performance |
| Step 32 | COMPLIANCE | Produce SOC 2 evidence artifacts: access control evidence (RBAC screenshots + au | Standards mapping, DHF, traceability |

**Total tasks:** 35 | **Compliance tasks:** 6 | **Coverage:** 17%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 2 | CAN-SPAM compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | CCPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 4 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |

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
| developer | 19 | Engineering |
| devops_engineer | 2 | Engineering |
| regulatory_specialist | 2 | Compliance |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| marketing_strategist | 1 | Operations |
| business_analyst | 1 | Analysis |
| financial_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 55/100 (FAIL) — 1 iteration(s)

**Summary:** This is a thorough, well-structured plan that covers the right domains in the right order and has genuinely good acceptance criteria for most steps. However, it earns a 55 because it has two reputation-ending gaps for an email platform specifically. First, the SSTI vulnerability is an architectural decision deferred to a security checklist — on a multi-tenant SaaS where templates are user-authored and server-rendered, this is a P0 breach waiting to happen. Second, the deliverability infrastructure is incomplete in ways that will prevent the product from working: missing List-Unsubscribe headers will get emails rejected by Gmail at volume (2024 policy), missing FBL enrollment means complaint spikes go undetected at the ISP level, and IP warming without pipeline enforcement means dedicated IPs are blacklisted before the first real customer sends. The SOC 2 Type II treatment is also a fundamental misconception — executing this plan will not produce a valid Type II report. The automation workflow engine's durability model (Redis state with vague PostgreSQL fallback) will lose in-flight enrollments on any Redis restart. These are not MVP-scope misses — deliverability is the product's core value proposition, and getting IPs blacklisted or being rejected by Gmail kills the product on day one regardless of how polished the UI is. Fix the SSTI architecture, add List-Unsubscribe, add FBL implementation, and harden the automation state persistence before considering this plan production-ready.

### Flaws Identified

1. SSTI risk is architectural, not a checklist item: Step 14 commits to Jinja2-style merge tags AND a `raw_html` block type, but sandboxing is deferred to Step 27's security review. Jinja2's SandboxedEnvironment has known bypasses. On a multi-tenant platform, one tenant exploiting SSTI can read other tenants' data or execute code. The rendering architecture must be decided in Step 14, not audited 13 steps later.
2. SOC 2 Type II is not a documentation exercise: Steps 10 and 32 treat SOC 2 Type II as producing artifacts and writing policies. Type II requires a minimum 6-month observation period of controls operating effectively. You cannot produce Type II evidence from a freshly built system. The plan never acknowledges this — it will either miss the timeline or produce a meaningless report. Target Type I first.
3. Cross-tenant data leakage has no database-level protection: Step 11 specifies 'org-scoped row-level isolation via org_id' enforced entirely at the application layer. Without PostgreSQL Row Level Security (RLS), any single missed `WHERE org_id = ?` filter in any query leaks cross-tenant data. The cross-tenant test in Step 30 is one E2E scenario — not a systematic audit of every query path.
4. No per-organization sending rate limits: One tenant can exhaust the entire AWS SES account quota, triggering account-level reputation damage that affects all other tenants. This is a critical multi-tenancy flaw for an email platform — the entire product value is deliverability.
5. Webhook event idempotency is missing: Step 17 processes bounce/complaint webhooks with no mention of deduplication. SES and SendGrid both send duplicate webhook events under failure/retry conditions. Without idempotency keys, one hard bounce event could suppress a contact twice (no harm) but one complaint event could double-count in complaint rate metrics, triggering false deliverability alerts.
6. Segment estimation at 1M contacts in 2 seconds is unrealistic: Step 13 uses 'on-demand SQL query generation from rule tree' for segment size estimates. Complex nested boolean trees against 1M contacts with event join conditions (event_occurred, event_count) will not complete in 2 seconds without pre-built partial indexes per condition type. This acceptance criterion will fail in production load testing.
7. DSAR export in 200ms is architecturally incompatible with contact data volume: Step 18 requires 'all contact data in structured JSON within 200ms.' A contact with 50k engagement events (normal for an active subscriber over 2 years) cannot be aggregated and serialized in 200ms without pre-aggregation. GDPR gives 30 days — this constraint solves the wrong problem and creates a false engineering requirement.
8. A/B test statistical significance is naive: Step 15 specifies p<0.05 as the winner selection criterion with 'configurable duration.' This is textbook p-value peeking — checking significance repeatedly until it reaches 0.05 inflates the false positive rate to ~30% or higher. No mention of minimum sample size, statistical power, or sequential testing corrections (e.g., Bonferroni, O'Brien-Fleming). Customers will pick losers.
9. Double opt-in creates a suppression deadlock: Step 18 implements double opt-in where a confirmation email is sent before consent is confirmed. Step 17 enforces suppression at queue time. If the contact's email is on the suppression list (e.g., previously unsubscribed and re-signed-up), the confirmation email will be blocked and the contact can never re-consent. The plan does not address this re-subscription flow.
10. Automation engine durability is insufficient: Step 16 uses 'Redis state machine per enrolled contact with PostgreSQL fallback on worker restart.' Redis without AOF/RDB persistence (which docker-compose won't configure) loses all in-flight workflow state on restart. The 'PostgreSQL fallback' is vague — how does a restarted worker know which contacts were mid-wait when Redis was wiped? This needs a proper state persistence design, not a footnote.
11. Celery + Redis as single stack for both queue and cache: Steps 9 and 16 use Redis for both Celery task queue AND workflow state. A single Redis failure simultaneously kills: task queuing, campaign sends, automation state, session cache, and segment count caching. These should be separate Redis instances or the failure blast radius is documented.
12. Financial model output as .xlsx is unimplementable for an AI agent: Step 3 expects an agent to produce a working Excel file with formulas, sensitivity analysis tabs, and P&L projections. No current LLM agent can reliably generate a non-corrupt .xlsx with live cell references. This will produce a file that looks like a spreadsheet but has broken formulas. Output should be Markdown tables or CSV.
13. IP warming has no implementation: Step 17 mentions 'IP warming schedule' in the description but the acceptance criteria contain zero IP warming requirements. Warming is not a runbook — it is a daily volume ramp (typically 50→100→500→2000→... over 6+ weeks) that must be enforced by the sending pipeline. Without this, dedicated IPs will be blacklisted within 48 hours of first production send.
14. Missing List-Unsubscribe headers: CAN-SPAM compliance and Gmail's 2024 bulk sender requirements mandate List-Unsubscribe and List-Unsubscribe-Post headers on all marketing emails. Step 17's acceptance criteria do not mention this. Gmail will reject or send to spam emails from senders missing one-click unsubscribe headers at volume — this is a deliverability-breaking omission.

### Suggestions

1. Decide on merge tag rendering architecture in Step 14: use a purpose-built safe expression evaluator (e.g., restricted AST evaluation) rather than Jinja2, or commit explicitly to Jinja2 SandboxedEnvironment with a documented bypass audit. Eliminate the `raw_html` block type from v1 or process it server-side through an HTML sanitizer (DOMPurify equivalent).
2. Add PostgreSQL Row Level Security policies in Step 8 as a hard requirement, not application-layer convention. Every table with org_id should have an RLS policy enforced at the database level. Application-layer filters become defense-in-depth, not the primary guard.
3. Replace the Celery Redis state machine in Step 16 with a proper durable workflow pattern: either Temporal (already referenced in SAGE), AWS Step Functions, or at minimum persist workflow enrollment state to PostgreSQL on every node transition — not just on worker restart.
4. Reframe Step 10 as SOC 2 Type I readiness, not Type II. Add a note that Type II requires 6 months of control operation evidence post-launch. This is an honest timeline and avoids the audit failure.
5. Add per-organization sending quotas as a first-class database concept in Step 8: an `org_sending_limits` table with daily/hourly caps, enforced at Celery task dispatch time. Start conservative (e.g., 10k/hour) and require org upgrade to raise limits.
6. Add List-Unsubscribe and List-Unsubscribe-Post headers to Step 17's acceptance criteria. Add DKIM signing architecture decision (SES DKIM vs. custom domain) as an explicit requirement.
7. Add FBL enrollment (Gmail Postmaster Tools, Yahoo Complaint Feedback Loop, Microsoft SNDS) as an operational prerequisite in Step 17 or 33, with implementation steps — not just a runbook mention.
8. Add email client rendering compatibility testing to Step 29 QA plan: Litmus or Email on Acid API integration, covering Outlook 2019/365, Gmail web/app, Apple Mail, iOS Mail. Outlook's Word-based renderer breaks standard HTML — this is the #1 support ticket for any email builder.
9. Change A/B winner selection in Step 15 to require minimum sample size calculation (based on expected effect size) and sequential testing methodology (e.g., always-valid p-values or Bayesian updating). Remove pure 'configurable duration' as the sole trigger.
10. Add webhook signature verification to Step 17's acceptance criteria: SES uses SNS topic signatures, SendGrid uses HMAC-SHA256. Without signature verification, the bounce/complaint endpoints are open to spoofing that could suppress arbitrary contacts.
11. Add API rate limiting as a cross-cutting concern in Step 11 — not optional. Minimum: per-API-key rate limits on all write endpoints, stricter limits on computationally expensive endpoints (segment count, DSAR export, template preview).
12. Strengthen the DSAR portal identity verification in Step 26: accepting an email address alone and sending a verification token to that email is trivially abusable to confirm whether any email address is a customer. Add CAPTCHA and consider requiring the data subject to confirm their identity attribute before returning data.

### Missing Elements

1. Email client compatibility testing matrix (Outlook 2019/365, Gmail, Apple Mail) — the #1 deliverability-adjacent failure mode for any email template builder
2. List-Unsubscribe / List-Unsubscribe-Post header implementation in outgoing email pipeline (required by Gmail bulk sender policy 2024, CAN-SPAM)
3. ISP Feedback Loop (FBL) enrollment implementation steps for Gmail Postmaster Tools, Yahoo CFL, Microsoft SNDS
4. DKIM signing architecture decision: who signs outgoing emails and how (SES DKIM vs. Bring Your Own Domain with DNS-side CNAME)
5. PostgreSQL Row Level Security (RLS) policies — application-layer org_id filtering alone is insufficient for a multi-tenant SaaS
6. Per-organization sending quotas enforced at the task queue level — without this, one tenant can consume all sending capacity
7. Webhook event idempotency design (dedup keys, processed_webhook_events table)
8. Re-subscription flow for previously suppressed contacts attempting double opt-in
9. IP warming enforcement mechanism in the sending pipeline (not just an ops runbook reference)
10. SOC 2 Type I vs Type II distinction and realistic timeline — the current plan is unachievable as written
11. API rate limiting specification (per-key, per-endpoint, per-org)
12. Webhook signature verification for SES/SendGrid inbound events
13. Minimum sample size and power analysis for A/B winner selection
14. DSAR portal identity verification beyond email token (trivially abusable for email enumeration)
15. Disaster recovery drill procedure and results — not just a runbook that says it was 'tested in staging'

### Security Risks

1. Server-Side Template Injection (SSTI): Jinja2-style merge tags + `raw_html` block type + server-side preview rendering = critical SSTI surface on a multi-tenant platform. One payload like `{{ ''.__class__.__mro__[1].__subclasses__() }}` can expose the process environment. Architecture must sandbox at Step 14, not audit at Step 27.
2. Cross-tenant data leakage: application-layer org_id filtering with no database RLS means a single missing WHERE clause anywhere in 19 endpoint groups leaks all tenants' data to any authenticated user. Step 30's single cross-tenant test is not a systematic audit.
3. Bounce/complaint webhook spoofing: without SES SNS signature verification and SendGrid HMAC verification on inbound webhook endpoints, any external party can POST fabricated bounce events to suppress arbitrary contacts or inflate complaint metrics.
4. DSAR portal data exfiltration: Step 26 allows any person to submit an email address, receive a verification token to that email, and retrieve all data associated with it. A threat actor who compromises one subscriber's email inbox can extract that contact's full profile, engagement history, and custom fields — including data the org may consider sensitive.
5. Redis exposure in docker-compose: without explicit requirepass and bind configuration, the Redis instance used for both Celery queue and workflow state will bind to 0.0.0.0 by default in Docker bridge networking, potentially accessible beyond the container network depending on host configuration.
6. Merge tag exfiltration via crafted templates: even without SSTI, a malicious org admin could craft merge tags referencing internal system variables if the expression evaluator is not strictly scoped to contact fields. The plan does not define the allowed variable namespace.
7. Mass contact suppression DoS: if the bounce webhook endpoint lacks rate limiting and signature verification, an attacker can POST thousands of fake hard bounces to suppress an entire organization's contact list within seconds.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.319825
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

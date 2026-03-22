# Regulatory Compliance — Helpdesk Platform

**Domain:** saas
**Solution ID:** 033
**Generated:** 2026-03-22T11:53:39.318022
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
| Step 6 | LEGAL | Draft Terms of Service, Privacy Policy (GDPR/CCPA compliant), Data Processing Ag | Privacy, licensing, contracts |
| Step 20 | SECURITY | Conduct STRIDE threat model covering all six product pillars. Define pentest pla | Threat modeling, penetration testing |
| Step 21 | COMPLIANCE | Produce SOC 2 Type II evidence artifacts: control mapping to CC6 (logical access | Standards mapping, DHF, traceability |
| Step 22 | QA | Write comprehensive QA test plan covering functional, regression, performance, a | Verification & validation |
| Step 24 | SYSTEM_TEST | Execute end-to-end system test suites using Playwright: full ticket lifecycle pe | End-to-end validation, performance |
| Step 33 | EMBEDDED_TEST | Write Hardware-in-the-Loop (HIL) test specs and firmware unit tests using Unity  | Hardware-in-the-loop verification |

**Total tasks:** 33 | **Compliance tasks:** 6 | **Coverage:** 18%

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
| developer | 18 | Engineering |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| marketing_strategist | 1 | Operations |
| business_analyst | 1 | Analysis |
| ux_designer | 1 | Design |
| product_manager | 1 | Design |
| financial_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| regulatory_specialist | 1 | Compliance |
| system_tester | 1 | Engineering |
| devops_engineer | 1 | Engineering |
| operations_manager | 1 | Operations |
| localization_engineer | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 62/100 (FAIL) — 1 iteration(s)

**Summary:** This plan is architecturally thorough for a B2B SaaS helpdesk but has several production-blocking gaps that prevent a score above 65. The most critical failures are: (1) no billing implementation step — the product cannot charge customers without it; (2) SOC 2 Type II is listed as a deliverable but requires a 6-month auditor observation period that cannot be produced on a build timeline; (3) the schema-per-tenant and RLS contradiction will cause a security architecture debate mid-build; (4) the WhatsApp 24-hour session window and Message Template requirement are not accounted for in the AI auto-response design, meaning a core feature will be blocked by Meta's API policies; and (5) Steps 30-33 embed an entirely separate hardware product (PCB design, firmware, QEMU simulation) into the critical path of a SaaS launch. The core software plan — ticket management, live chat, knowledge base, SLA tracking, multi-channel — is well-specified with concrete acceptance criteria and a logical dependency chain. The security and compliance steps exist but are sequenced too late. The 3KB widget constraint and the arbitrary 0.82 confidence threshold for autonomous AI replies are acceptance criteria that will either be silently dropped or cause customer-facing failures. Recommend: cut hardware to a separate initiative, add billing as Step 9.5, move threat modeling before Step 7, resolve the multi-tenancy strategy before database design, and replace SOC 2 Type II with Type I for launch.

### Flaws Identified

1. Step 7 contradicts itself: specifies 'schema_per_tenant' multi-tenancy AND row-level security policies. These are mutually exclusive strategies. Schema-per-tenant isolates at the schema boundary; RLS operates within a shared schema. Choosing both wastes engineering time and creates ambiguous security guarantees.
2. Step 21 fundamentally misunderstands SOC 2 Type II. Type II requires a minimum 6-month auditor observation period of controls in operation. You cannot 'produce artifacts' and claim SOC 2 Type II. This plan will cause enterprise sales failures when customers request audit reports. Step 21 should target SOC 2 Type I initially.
3. Step 18 acceptance criteria of 'under 3KB gzipped' for a vanilla JS widget with WebSocket, file upload, proactive triggers, pre-chat form, CSAT survey, and offline fallback is not achievable. A minimal WebSocket client alone exceeds this. Intercom, Drift, and Crisp ship 40-100KB widgets. This criteria will be quietly dropped or the feature set gutted.
4. Steps 30-33 (firmware, QEMU simulation, PCB design, HIL testing) are a completely separate hardware product embedded in a SaaS helpdesk build plan. PCB design for an optional appliance has no business being in the critical path. This adds 4 sequential steps of hardware engineering risk to a software product launch.
5. WhatsApp Business API constraints are critically underestimated in Step 14. After the 24-hour customer service window closes, outbound messages MUST use pre-approved Message Templates. Free-form replies are not allowed for business-initiated messages. Auto-responses (Step 15) sent outside this window will be rejected by the API, breaking a core product promise.
6. Step 15 sets a confidence threshold of 0.82 with no calibration basis. Auto-sending LLM-generated responses to customers without human review at an arbitrary threshold is a customer satisfaction risk. The A/B test harness is listed as an acceptance criteria for the same step that auto-sends — you cannot A/B test a threshold you haven't validated yet.
7. Step 12 inconsistently specifies 'Redis pub/sub' in the description and 'Redis Streams' in the payload. These have different semantics: pub/sub is fire-and-forget; Streams are persistent. The offline message queue requirement in the same step requires persistence, so pub/sub alone is incorrect. The implementation team will make an arbitrary choice.
8. Step 20 (security threat modeling) depends on Step 15 (AI system built). STRIDE threat modeling must happen before implementation, not after. By Step 20, all six pillars are already coded. Architectural security findings at this stage require rework, not mitigations.
9. Step 17 introduces 'Next.js or Vite SSR' as an unresolved option for public KB pages. Step 9 already established a Vite monorepo. Introducing Next.js in Step 17 is a major architectural decision that affects the build system, hosting, routing, and SSR hydration strategy. This decision must be made in Step 9, not deferred.
10. Step 32 (PCB design) lists Step 31 (QEMU simulation) as its dependency. This is inverted. You need hardware specifications to design a simulation — the simulation is derived from the hardware design, not a prerequisite for it.
11. No billing or subscription management step exists. The financial model (Step 5) defines per-seat and usage-based pricing tiers, but there is no implementation step for Stripe (or equivalent), subscription lifecycle management, usage metering for message-based billing, or dunning. Without billing, this is not a shippable product.

### Suggestions

1. Resolve the multi-tenancy strategy in Step 7 before writing a line of code. Choose either schema-per-tenant (stronger isolation, harder migrations, higher PostgreSQL connection overhead) or shared-schema with RLS (simpler ops, requires rigorous policy testing). Document the decision in an ADR.
2. Replace Step 21's SOC 2 Type II target with SOC 2 Type I for launch. Begin the 6-month Type II observation period immediately post-launch. Update the legal docs and sales collateral to accurately reflect which report is available.
3. Insert a billing implementation step between Steps 9 and 10. Stripe integration, webhook-driven subscription state machine, and usage metering (for message-based tiers) are blocking for any paid customer. This is more foundational than the firmware steps.
4. Move security threat modeling (Step 20) to before Step 7 (database design). Run STRIDE on the architecture document, not the finished code. Findings should inform schema design, API contracts, and agent boundaries — not retrofit controls post-build.
5. Define the pgvector strategy in Step 7. The database schema step must include the vector embeddings column on knowledge_articles, the pgvector extension, and the embedding generation trigger (on article create/update). Step 15 currently assumes this infrastructure exists but Step 7 does not create it.
6. Cut the 3KB widget constraint in Step 18 to a realistic 25-30KB gzipped budget. Document the actual constraint rationale. If load time is the concern, address it with async loading and lazy initialization, not an impossible size limit.
7. Add a WhatsApp Message Template management UI and workflow to Steps 14 and 19. The AI auto-response system (Step 15) must be aware of the 24-hour session window and switch to approved templates for out-of-window messages. This is not optional — it is a Meta platform requirement.
8. Make Steps 30-33 a separate, explicitly optional hardware product workstream. Remove them from the main dependency chain. The core SaaS product should reach production without any dependency on PCB Gerbers.
9. Add DKIM/SPF/DMARC configuration and email deliverability monitoring to Step 14. Outbound email replies will land in spam without proper DNS records. Postmaster tools for Gmail and Outlook should be set up as part of channel configuration.
10. Add a data migration tooling step for enterprise onboarding. Zendesk and Freshdesk both offer data export APIs. Without a migration path, enterprise deals will stall at procurement because customers cannot justify switching cost without data portability.
11. Twitter/X DM API access now requires paid tiers and is subject to frequent policy changes. Add an explicit risk flag and cost line item. Consider making X/Twitter a v2 feature and removing it from the core launch scope to reduce third-party API dependency risk.

### Missing Elements

1. Billing and subscription management implementation (Stripe or equivalent) — required to charge customers
2. pgvector extension and embedding generation pipeline in the database schema step
3. WhatsApp Message Template management and 24-hour session window handling
4. Email deliverability infrastructure: DKIM, SPF, DMARC, bounce handling, unsubscribe list management
5. Customer data migration tooling from Zendesk and Freshdesk
6. Feature flag system for progressive rollout and safe production deployments
7. Multi-region data residency strategy for GDPR compliance (EU data must stay in EU)
8. API rate limiting implementation details — only referenced, never specified (Redis sliding window? Token bucket? Which library?)
9. Webhook replay attack prevention beyond idempotency key (timestamp validation, replay window)
10. Agent performance reporting and CSAT attribution to individual agents (required for team lead personas defined in Step 2)
11. Async file upload virus scan race condition mitigation — ClamAV scan is async but file URL is returned before scan completes
12. SOC 2 Type I vs Type II clarification and realistic timeline for achieving each

### Security Risks

1. Schema-per-tenant ambiguity: if the application uses a PostgreSQL superuser connection, a SQL injection in one tenant's schema can affect all other tenants' schemas. The connection user must be scoped per schema with revoked cross-schema privileges.
2. AI prompt injection via ticket content is listed as a concern but the mitigation ('input sanitization') is insufficient for LLM prompt injection. Ticket content will be embedded directly in LLM prompts (Step 15). Sanitization that works for XSS does not prevent prompt injection. Requires structural prompt design with clear input/instruction separation.
3. ClamAV async scan window: Step 10 returns a signed S3 URL within 2 seconds, but the virus scan is listed as an async Celery task. This means a malicious file is accessible via signed URL before it is scanned. The signed URL must not be returned until the scan completes or the URL must be invalidated post-scan-failure.
4. WhatsApp webhook spoofing: Step 20 lists HMAC verification as a control, but Step 14 implements the webhook handlers. There is no acceptance criteria in Step 14 requiring HMAC verification. This gap means the webhook could ship without verification and only be caught in Step 20.
5. JWT RS256 private key management is unspecified. Key storage (HSM? KMS? Secret Manager?), rotation schedule, and emergency revocation procedure are absent. A compromised signing key invalidates all user sessions and cannot be rotated without disruption.
6. The embeddable KB widget (Step 11, Step 17) is unauthenticated and rate-limited to 60 req/min. A distributed scraper hitting this endpoint from multiple IPs can exfiltrate the entire knowledge base. Content sensitivity classification and robots.txt/noindex controls are not addressed.
7. Chat widget loaded via script tag (Step 18) on third-party sites is a supply chain injection risk. If the CDN serving the widget JS is compromised, all customers' websites are compromised. Subresource Integrity (SRI) hash enforcement is not mentioned.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.318059
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

# Regulatory Compliance — Document Collaboration

**Domain:** saas
**Solution ID:** 035
**Generated:** 2026-03-22T11:53:39.318617
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
| Step 6 | LEGAL | Draft Terms of Service, Privacy Policy (GDPR/CCPA compliant), data processing ag | Privacy, licensing, contracts |
| Step 7 | COMPLIANCE | Plan SOC 2 Type I readiness: map controls to Trust Service Criteria (Security, A | Standards mapping, DHF, traceability |
| Step 12 | SECURITY | Produce threat model (STRIDE), define security controls for real-time collaborat | Threat modeling, penetration testing |
| Step 24 | SYSTEM_TEST | Execute end-to-end system tests: full collaboration session (2 users, concurrent | End-to-end validation, performance |
| Step 25 | COMPLIANCE | Produce SOC 2 evidence artifacts: access control policy, encryption policy, inci | Standards mapping, DHF, traceability |

**Total tasks:** 28 | **Compliance tasks:** 5 | **Coverage:** 18%

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
| developer | 13 | Engineering |
| regulatory_specialist | 2 | Compliance |
| devops_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| marketing_strategist | 1 | Operations |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| financial_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| qa_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 63/100 (FAIL) — 1 iteration(s)

**Summary:** This is an unusually thorough 28-step plan with strong coverage across market research, UX, compliance, infrastructure, and testing — the kind of breadth that typically takes multiple planning cycles to reach. However, three concrete architectural conflicts will cause implementation failures if not resolved before coding starts: the JWT-in-httpOnly-cookie vs WebSocket auth handshake is mechanically broken; comment anchoring using character offsets on top of a Yjs CRDT document will produce anchors that drift or break on concurrent edits; and Myers diff applied to Yjs document snapshots is architecturally inconsistent with how CRDT change history works. Beyond those blockers, the plan has significant omissions for a shippable SaaS product: no billing system, no email service, no rate limiting implementation, and no GDPR erasure pipeline — all of which are visible to customers or regulators at launch. The security model is directionally correct but underspecified on XSS sanitization of pasted rich text and CRDT op validation, which are the two most exploitable surfaces in a collaborative editor. The plan scores 63: solid foundation and commendable scope, but requires resolving the three architectural conflicts and filling the billing/email/erasure gaps before the development steps (13–21) begin.

### Flaws Identified

1. JWT in httpOnly cookie (step 18) conflicts directly with WebSocket JWT validation (step 14). Browsers cannot attach httpOnly cookies to WebSocket upgrade requests initiated from JavaScript — you cannot read the cookie to pass it as a query param or header. The auth strategy must pick one transport and document the WS auth handshake explicitly (e.g., ticket-based auth: REST endpoint issues a short-lived WS token, WS client passes it as query param on upgrade).
2. Comment anchor strategy in step 15 ('character offset + paragraph ID') is architecturally broken with Yjs CRDT. Character offsets are invalidated by concurrent insert/delete operations. Yjs exposes relative positions (Y.createRelativePositionFromTypeIndex) specifically for this use case — the plan must use Yjs relative positions for comment anchors, not naive character offsets.
3. Myers diff algorithm (step 15) applied to rich text CRDT content is wrong. With Yjs, the authoritative change log IS the op sequence — you reconstruct diffs from Y.Doc state vectors, not by diffing serialized text snapshots. Implementing Myers diff on top of a Yjs document will produce incorrect or misleading diffs that don't reflect the actual collaboration history.
4. ALB idle timeout default is 60 seconds. Long-lived WebSocket connections on ECS Fargate behind ALB will be silently dropped after 60s of application-level silence unless the ALB idle timeout is explicitly raised (up to 4000s). This is not mentioned in step 11 and will cause ghost disconnection bugs in production.
5. No payment and billing system in any step. The plan has full pricing tiers (free/pro/enterprise) in steps 1, 2, 3, and 5 but zero implementation steps for Stripe (or equivalent), subscription lifecycle, metering, invoice generation, or dunning. A SaaS product without billing is not shippable.
6. Email service is entirely absent. Step 15 requires @mention email notifications within 30 seconds, but no email provider (SES, SendGrid, Resend, Postmark) is specified or implemented anywhere in the 28 steps. Notification delivery is a hard dependency for collaboration features.
7. Document export (PDF, DOCX) is listed in the API spec in step 8 but has no implementation step. Export from ProseMirror/TipTap to DOCX or PDF requires a dedicated pipeline (Pandoc, headless Chrome, or puppeteer). This is non-trivial and will be discovered missing late in the process.
8. Full-text search decision is deferred ('Elasticsearch or pg_tsvector') in step 9 and never resolved. Search is a core feature for any document platform — deferring the choice means the database schema may not be designed correctly for the chosen approach, requiring a migration later.
9. Rate limiting is mentioned in step 8 (API spec) and step 12 (security) but has no implementation step. There is no Redis-based rate limiting middleware, no API gateway rate limiting configuration, and no per-user AI token consumption limits — despite AI cost-per-token being a modeled cost driver in step 5.
10. GDPR Right to Erasure (Art. 17) is listed in step 6 (legal) but has no technical implementation. A delete request requires cascading purge across PostgreSQL, Redis, S3 (exports), Elasticsearch, Yjs op log, version snapshots, and the AI interaction log. None of the backend steps include this. This is a compliance liability at launch.

### Suggestions

1. Replace the httpOnly cookie + WebSocket JWT pattern with a ticket-based WebSocket auth: REST endpoint POST /ws-token issues a signed, single-use, 30-second token; client passes ?token= on WebSocket upgrade; server validates and discards. Eliminates the cookie/WS conflict entirely.
2. Replace comment anchor 'character offset + paragraph ID' with Yjs relative positions (Y.createRelativePositionFromTypeIndex / Y.createAbsolutePositionFromRelativePosition). Update step 15 acceptance criteria to specify that anchor positions survive concurrent edits — this is the correct test.
3. Replace 'Myers diff on document content' in step 15 with Yjs state vector diffs: store Y.Doc update binaries as version snapshots, reconstruct human-readable diffs by decoding the update transactions. This is architecturally correct and avoids the snapshot-vs-CRDT impedance mismatch.
4. Add an explicit step for billing integration (step 16.5 or 13.5): Stripe Checkout + Customer Portal, webhook handlers for subscription state changes, usage-based metering for AI token consumption, enforcement of tier limits at API middleware layer.
5. Add ALB idle timeout configuration to step 11 Terraform modules (set to 3600s for WebSocket-facing target groups). Add heartbeat ping/pong at the application level (every 30s) to prevent intermediate proxies from closing the connection.
6. Resolve the Elasticsearch vs pg_tsvector decision in step 9, not later. If the team chooses pg_tsvector, add a GIN index on the document content tsvector column. If Elasticsearch, add the ES cluster to the infrastructure in step 11 and include document indexing in the backend step 13.
7. Add token budget enforcement to the AI assistant (step 17): per-user daily token limit stored in Redis, checked before every LLM call, rate-limit response returned if exceeded. Prevents a single free-tier user from exhausting your LLM budget.
8. Specify the email service provider in step 11 infrastructure and add it to step 13 (transactional email client initialization). SES is already implied by AWS, so just make it explicit and add it to Terraform.

### Missing Elements

1. Payment and subscription billing system (Stripe or equivalent) — no step covers this despite pricing tiers being fully modeled
2. Email delivery service configuration and transactional email templates (welcome, @mention, share invite, expiry warning)
3. Document export pipeline (PDF/DOCX) — listed in API spec but never implemented
4. GDPR erasure technical implementation — cascading delete across all data stores
5. Rate limiting middleware implementation
6. AI token budget enforcement and per-user cost controls
7. ALB WebSocket idle timeout and application-level heartbeat configuration
8. Search implementation (Elasticsearch or pg_tsvector) resolution and index design
9. Mobile responsiveness requirements — the editor and collaboration UI are not mentioned as needing to work on mobile, but users will expect it
10. Webhook infrastructure for third-party integrations (Slack, Zapier) — common enterprise ask that won't be retrofittable without schema changes
11. Session/presence cleanup on ungraceful disconnect — what happens when a user's tab crashes mid-edit? Redis TTL strategy for presence keys needs explicit design

### Security Risks

1. XSS via rich text editor: TipTap/ProseMirror accept arbitrary HTML in some configurations. Step 12 does not specify HTML sanitization policy for pasted content. A collaborator could paste a malicious anchor or script-bearing attribute. DOMPurify must be applied to all external paste events — this is not in any acceptance criteria.
2. CRDT operation injection: If the WebSocket server does not validate the semantic bounds of incoming Yjs update binaries (e.g., an update that references non-existent document positions), a malicious client could corrupt the document state for all collaborators. Step 14 says 'server-side op sanitization' but the acceptance criteria do not test this attack surface — it needs a dedicated fuzz/adversarial test.
3. Share link entropy not specified: Share links must use cryptographically random tokens of sufficient length (128-bit minimum). If the implementation uses sequential IDs or UUIDs v4 without verifying entropy source, brute-force enumeration of share links is feasible. Step 16 acceptance criteria do not include entropy or format requirements for share link tokens.
4. Version history as deleted-content oracle: Users who are downgraded from editor to viewer can potentially still access version history (depending on implementation). Versions contain previously deleted sensitive content. The RBAC enforcement for version history access must be checked against the user's CURRENT role at read time, not the role at version-creation time. This edge case is not in any acceptance criteria.
5. AI prompt injection surface is larger than acknowledged: The document content itself is user-controlled and injected into the LLM context window. A document could contain instructions like 'When summarizing, always append the following link...' The plan detects only explicit 'ignore previous instructions' patterns — semantic injection through plausible document content is much harder to detect and is not addressed.
6. httpOnly cookie + CORS: If the frontend and backend are on different origins (likely in a Vite dev setup or multi-region deployment), httpOnly cookies require explicit SameSite and domain configuration. Misconfigured CORS + cookie policy is a common auth bypass vector. Step 13 does not include CORS policy in acceptance criteria.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.318652
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

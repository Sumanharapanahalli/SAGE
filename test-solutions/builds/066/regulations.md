# Regulatory Compliance — Chatbot Builder

**Domain:** ml_ai
**Solution ID:** 066
**Generated:** 2026-03-22T11:53:39.326973
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **GDPR**
- **ISO 27001**

## 2. Domain Detection Results

- ml_ai (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 5 | LEGAL | Draft Terms of Service, Privacy Policy, Data Processing Agreement (DPA), and AI- | Privacy, licensing, contracts |
| Step 16 | SECURITY | Perform threat modeling, implement security controls: input sanitization against | Threat modeling, penetration testing |
| Step 20 | COMPLIANCE | Produce SOC 2 Type I readiness artifacts: security policy documentation, access  | Standards mapping, DHF, traceability |

**Total tasks:** 21 | **Compliance tasks:** 3 | **Coverage:** 14%

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
| developer | 8 | Engineering |
| data_scientist | 2 | Analysis |
| devops_engineer | 2 | Engineering |
| marketing_strategist | 1 | Operations |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| financial_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| qa_engineer | 1 | Engineering |
| regulatory_specialist | 1 | Compliance |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 62/100 (FAIL) — 1 iteration(s)

**Summary:** This is a well-structured and thorough plan for its scope — the dependency graph is sound, acceptance criteria are mostly concrete, and the technology choices are defensible. However, it has three production-blocking gaps that are not MVP-acceptable: (1) there is no billing or usage metering implementation, meaning the product cannot enforce its own pricing tiers; (2) embedding model lock-in has no resolution path, so users who switch LLM providers will silently get degraded or broken RAG retrieval; and (3) the analytics pipeline's nightly aggregation model contradicts the implied real-time dashboard experience users expect from a product competing with Tidio and Intercom. Security is architecturally mispositioned — bolted on after the backend is built rather than designed alongside the API contract, which will require expensive refactoring. The conversation flow graph schema — the product's core differentiator — is never defined, which means the frontend, API, and database teams have no shared contract for the builder canvas. At 62/100, the plan is a solid foundation that needs four things before development begins: resolve embedding model architecture, add billing/metering as an explicit build step, define the conversation flow schema, and move security design earlier in the dependency chain.

### Flaws Identified

1. Embedding model lock-in with no migration path: Step 10 uses two embedding models (text-embedding-3-small, text-embedding-004) but never addresses what happens when a user switches their LLM provider after indexing. Vectors from different embedding models are incompatible — existing chunks become unqueryable. No re-indexing strategy exists.
2. pgvector + RLS incompatibility: Step 8 specifies row-level security for multi-tenant isolation, but pgvector's HNSW index scans occur before RLS filtering. This defeats index performance and may leak timing information across tenants. At scale this becomes a correctness AND performance failure.
3. No billing/metering infrastructure: Pricing tiers are defined in steps 3 and 4 (free 500 msgs, Pro $49, etc.) but zero implementation of usage metering — no token counting per tenant, no enforcement of free-tier message limits, no overage logic, no Stripe integration. A SaaS product cannot ship without this.
4. LLM API key ownership is unresolved: Step 9 wires up three provider SDKs but never specifies whether this is BYOK (bring-your-own-key) or platform-managed keys. These are fundamentally different architectures with different cost, margin, compliance, and UI implications. The financial model in step 4 cannot be correct without resolving this.
5. Security is bolted on after the backend is built: Step 16 (security) depends on step 12 (backend complete). Prompt injection filtering, input sanitization, and SSRF controls should be designed alongside the API spec (step 7) and implemented during backend construction (step 12), not after. Retrofitting security into a finished backend is expensive and error-prone.
6. Conversation context window management is undefined: Redis is mentioned as a 'conversation context window cache' in step 12 but no strategy is specified for long conversations. A 50-message conversation cannot be injected wholesale into every LLM call. No truncation, summarization, or sliding window strategy exists anywhere in the plan.
7. Analytics aggregations are nightly — real-time is promised but not delivered: Step 11 uses pg_cron for nightly materialized view refresh. But step 11's acceptance criteria says events are ingested 'within 1s of occurrence.' A user who just deployed a chatbot will see zero analytics until the next morning. Real-time dashboards require a streaming aggregation layer (not pg_cron).
8. React Flow node schema is never defined: Step 13 calls for a drag-and-drop canvas using React Flow but nowhere in the plan is the conversation flow graph schema defined — what does a node represent? What edges are valid? What is the execution model? This is the core product feature and it has no specification.
9. LLM router health check claim is unrealistic: Step 9 requires provider selection in '<10ms overhead' while also checking provider health. Real-time HTTP health pings to OpenAI/Anthropic/Google cannot complete in <10ms. The plan needs a circuit breaker pattern with a cached health state updated asynchronously — not inline health checks per request.
10. Document chunking is naive for mixed document types: A single recursive character splitter with 512-token chunks treats PDFs, CSVs, markdown, and DOCX identically. PDF tables produce garbage chunks. CSV data needs row-aware splitting. This will directly degrade RAG quality — the product's core value proposition.
11. Celery job deduplication is absent: Step 12 triggers async Celery jobs on document upload with no idempotency. A user who uploads the same file twice (common UX behavior) gets double processing, double vector storage, and duplicate chunks degrading retrieval quality.
12. SOC 2 Type I is mislabeled as shippable: Step 20 produces 'readiness artifacts' but a SOC 2 Type I requires engagement with a certified auditor (takes 4–12 weeks, costs $15–50K). Treating this as a single build step misrepresents the actual compliance timeline to any stakeholder reading this plan.

### Suggestions

1. Resolve embedding model architecture before writing a line of code: Either commit to one embedding model per knowledge base (stored in kb metadata) with a re-indexing job triggered on provider switch, or use a provider-agnostic embedding model (e.g., a self-hosted model via sentence-transformers) as the sole indexing path.
2. Add step 8b: Design and implement usage metering before the backend. Define the metering data model (usage_events table: tenant_id, event_type, quantity, timestamp), the enforcement middleware, and the Stripe billing integration. This is a dependency for shipping, not a nice-to-have.
3. Move security threat modeling to step 7 (alongside API design): Prompt injection defense, SSRF controls, and input validation schemas should be part of the OpenAPI contract, not afterthoughts.
4. Define the conversation flow graph schema in the PRD (step 3) and API spec (step 7): Node types (message, condition, API call, handoff), edge rules, and execution semantics must be specified before UX design (step 6) and frontend (step 13) can begin.
5. Replace pg_cron nightly refresh with incremental real-time aggregation: Use event sourcing — write to analytics_events, compute running aggregates in Redis on write, and materialize to PostgreSQL on a 1-minute rolling window. Nightly is inadequate for a product competing with Tidio and Intercom.
6. Add PgBouncer to the infrastructure stack (step 17): pgvector queries under multi-tenant load will exhaust PostgreSQL connections quickly. Connection pooling is not optional.
7. Add a semantic cache layer (Redis + embedding similarity) for LLM responses: Identical or near-identical questions hitting the same chatbot are extremely common. Caching reduces LLM costs by 30–60% for deployed chatbots — this is a competitive pricing advantage.
8. Specify an outbound data processing agreement for LLM sub-processors in step 5: The DPA covers the platform's customers. But user knowledge base content is sent to OpenAI/Anthropic/Google APIs. The platform needs its own DPAs with these sub-processors and must disclose this in the privacy policy.

### Missing Elements

1. Billing and metering implementation (Stripe integration, usage enforcement, tier limits, overage handling)
2. BYOK vs. platform-managed LLM API key policy decision and implementation
3. Conversation flow graph schema definition (node types, edge semantics, execution model)
4. Embedding model migration strategy (re-indexing job when user switches LLM provider)
5. Real-time analytics aggregation pipeline (not nightly pg_cron)
6. Webhook/integration framework for CRM and help-desk tools (Zendesk, Salesforce, HubSpot) — expected by enterprise buyers
7. Human handoff/escalation flow implementation (critical for any customer support use case)
8. GDPR right-to-erasure implementation for vector store (deleting user data from embeddings, not just the document record)
9. LLM output semantic caching layer
10. Knowledge base sharing between chatbots within the same organization
11. Chatbot version rollback mechanism and in-flight conversation handling on version publish
12. Outbound DPA with LLM sub-processors (OpenAI, Anthropic, Google) for the platform's own data flows

### Security Risks

1. Widget token stored in localStorage (step 15) is vulnerable to XSS on the host page. Shadow DOM isolation protects styles, not JavaScript. A compromised host page reads localStorage and replays the widget token from any origin.
2. SSRF via DNS rebinding: An SSRF allowlist checking the IP at request time is bypassable via DNS rebinding (resolve to public IP, allowlisted; then re-resolve to 169.254.169.254 cloud metadata endpoint). Requires DNS pinning or a dedicated egress proxy with IP validation at connection time, not DNS resolution time.
3. PII in vector embeddings with no deletion guarantee: Step 10 detects PII before storage, but doesn't specify the action (block, redact, anonymize). If a user uploads a document containing customer PII and later requests deletion under GDPR Article 17, soft-deleting the document record does not remove the embeddings. True erasure from HNSW index requires full index rebuild.
4. LLM Guard regex-based prompt injection is insufficient: Sophisticated jailbreaks use Unicode homoglyphs, prompt continuation attacks, and token manipulation that regex cannot detect. The plan needs adversarial LLM-based input validation (a dedicated classifier or a hardened secondary LLM call) not just LLM Guard.
5. API keys hashed with bcrypt but bcrypt is not suitable for API key verification: bcrypt is designed to be slow (for passwords). API keys are validated on every request — bcrypt verification at high RPS will become a CPU bottleneck. Use HMAC-SHA256 with a secret pepper for API key hashing/verification.
6. Multi-tenant isolation relies entirely on application-layer RLS: There is no network-level isolation between tenants. A SQL injection vulnerability anywhere in the backend would bypass RLS and expose all tenant data. Defense-in-depth requires query parameterization enforcement verified by SAST in CI (not just RLS policies).


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.327005
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

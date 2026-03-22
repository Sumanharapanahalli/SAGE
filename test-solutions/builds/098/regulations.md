# Regulatory Compliance — Knowledge Management

**Domain:** enterprise
**Solution ID:** 098
**Generated:** 2026-03-22T11:53:39.337552
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **ISO 27001**
- **GDPR**

## 2. Domain Detection Results

- enterprise (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 3 | LEGAL | Draft terms of service, privacy policy, and data processing agreements. Review I | Privacy, licensing, contracts |
| Step 4 | COMPLIANCE | Produce ISO 27001 and SOC 2 readiness artifacts. Define the information security | Standards mapping, DHF, traceability |
| Step 8 | SECURITY | Produce a threat model (STRIDE) for the knowledge management system. Identify at | Threat modeling, penetration testing |
| Step 27 | QA | Produce the QA test plan, test case library, and traceability matrix mapping req | Verification & validation |
| Step 28 | SYSTEM_TEST | Execute end-to-end system integration tests across the full stack: complete know | End-to-end validation, performance |
| Step 29 | COMPLIANCE | Collect and organize ISO 27001 and SOC 2 evidence artifacts: access control logs | Standards mapping, DHF, traceability |

**Total tasks:** 31 | **Compliance tasks:** 6 | **Coverage:** 19%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | ISO 27001 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |

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
| regulatory_specialist | 3 | Compliance |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| data_scientist | 1 | Analysis |
| data_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 62/100 (FAIL) — 1 iteration(s)

**Summary:** This is an ambitious, well-structured plan that covers the right phases in the right order with generally sensible acceptance criteria. The compliance, security threat modeling, and HITL pattern are notably well-considered. However, several concrete failure modes make this plan risky to execute as written. The most critical: collaborative editing is catastrophically underscoped — no WebSocket infrastructure exists anywhere in the plan, yet it appears as a checklist item in a single backend step; this will either silently die or consume 2–3x the estimated effort. The MRR acceptance criterion in Step 15 is unverifiable without a baseline. Elasticsearch's SSPL licensing is an unacknowledged legal and cost risk. JWT in localStorage is a likely implementation path given no explicit guidance, creating a P0 auth vulnerability. SSO/SAML absence will fail enterprise procurement. The dependency graph also has a gap: frontend modules (Steps 19–21) are not wired as prerequisites to system testing (Step 28), allowing tests to pass CI gates before the UI is actually built. Fix the collaborative editing scope (defer or split), mandate httpOnly cookies, add SSO, resolve the Elasticsearch licensing question, and define the WebSocket infrastructure before committing to this plan.

### Flaws Identified

1. Step 11 lists 'collaborative editing support via operational transforms or CRDT-based conflict resolution' as one bullet among many wiki features. Real-time collaborative editing (à la Google Docs) is a multi-month engineering effort requiring a WebSocket server, presence protocol, and conflict resolution engine. No WebSocket infrastructure is mentioned anywhere in the plan. This will either be silently dropped or block the entire wiki module.
2. Step 15 acceptance criterion: 'Re-ranker improves top-10 retrieval MRR by ≥15% on test query set.' There is no golden query set established in any earlier step, and no baseline MRR measured. This criterion is unverifiable as written — you cannot guarantee a relative improvement without a measured baseline.
3. Step 18 acceptance criterion mentions JWT storage across page reloads. The plan never specifies where JWT tokens are stored. If implemented in localStorage (the default for most React JWT tutorials), this is a P0 XSS vulnerability — any injected script exfiltrates the token. HttpOnly cookies are required for enterprise auth.
4. Step 23 requires Postgres logical replication (CDC) but wal_level=logical must be set at Postgres initialization time. This is a database configuration concern that belongs in Step 6 (database schema) or Step 24 (infrastructure), not Step 23. If the DB is deployed without it, enabling CDC requires a Postgres restart — production downtime.
5. Elasticsearch 8.x uses SSPL licensing for production self-hosted deployments in many configurations. Enterprise production use typically requires a commercial Elastic license. The plan has no licensing cost analysis or mitigation (e.g., OpenSearch as a drop-in alternative). This is a legal and budget risk that could force a mid-project replatform.
6. Step 16 lists 'semantic_drift' as a freshness scoring signal with no specification of how it is computed. Detecting semantic drift requires periodically re-embedding content and comparing cosine distance to a baseline — this is a non-trivial ML pipeline not described anywhere. It will either be silently omitted or require significant unplanned work.
7. Step 14 (LDAP/SCIM sync) has no conflict resolution strategy defined. In large enterprises, SCIM delta syncs frequently produce duplicate identity records when external IDs change (e.g., contractor rehire, email change). No de-duplication logic or sync idempotency guarantee is specified.
8. Step 28 lists 'Failover scenario tested' as an acceptance criterion with zero specification of what failover means (DB primary failure? LLM provider outage? Elasticsearch node loss?), what the expected behavior is, or what the RTO target is. This criterion cannot be evaluated.
9. Steps 19–21 build the frontend but Step 28 (system tests) only depends on Step 22 (admin panel). If any of steps 19–21 are delayed or broken, the E2E tests in Step 28 still pass its dependency check — the dependency graph does not enforce that all frontend modules are complete before system testing.

### Suggestions

1. Split Step 11 into two steps: (a) wiki CRUD + versioning + states, and (b) collaborative editing as a separate, explicitly-scoped step with WebSocket infrastructure (socket.io or native WebSocket), a defined CRDTlibrary (e.g., Yjs or Automerge), and its own acceptance criteria. If timeline is constrained, make collaborative editing a v2 feature with a clear deferral decision in the PRD.
2. Step 6 must specify wal_level=logical in the Postgres initialization config and reserve a replication slot for the CDC pipeline. Document this in the schema migration README so any fresh DB provisioning includes it.
3. Replace the relative MRR acceptance criterion in Step 15 with an absolute target or define a mandatory baseline measurement task before Step 15 begins. For example: 'BM25-only baseline MRR on 50-query golden set measured and recorded in eval/baseline.json before re-ranker integration.'
4. Step 18 must explicitly mandate httpOnly, Secure, SameSite=Strict cookies for JWT storage. Add this as a P0 acceptance criterion. Remove any guidance that implies localStorage for tokens.
5. Add SSO/SAML 2.0 (or OIDC) as an explicit module. Enterprise knowledge management without SSO will fail procurement reviews. This belongs in Step 7 (API design) and Step 10 (auth implementation) at minimum.
6. Replace Elasticsearch with OpenSearch (Apache 2.0 license) or include an Elastic commercial license line item in the project budget and legal review (Step 3). The current plan has an unacknowledged licensing risk.
7. Add a data export / portability endpoint (wiki articles as ZIP/Markdown, FAQ as CSV, decision trees as JSON) to the API design in Step 7. Enterprise buyers require this for vendor lock-in compliance — its absence is a common deal-breaker.
8. Step 15 cross-encoder re-ranking at P95 ≤ 2s under 50 concurrent users requires either a GPU-backed inference service or aggressive result caching. Add an explicit architecture decision: either deploy the cross-encoder behind a dedicated inference endpoint (TorchServe/Triton) or cache re-ranked results by query hash with a short TTL.
9. Add Steps 19–21 as explicit dependencies of Step 28 to enforce that all frontend modules are complete before system testing runs.

### Missing Elements

1. SSO/SAML 2.0 or OIDC integration — not mentioned anywhere. Mandatory for enterprise customer procurement.
2. WebSocket server design — required by Step 11 (collaborative editing) and Step 21 (streaming search responses). No WebSocket infrastructure, protocol, or connection management is defined.
3. Content sanitization for the rich text wiki editor — ProseMirror/TipTap output can contain arbitrary HTML if misconfigured. No mention of DOMPurify or server-side HTML sanitization before storage.
4. LLM API cost model — the plan uses text-embedding-3-small for ingestion, similarity clustering, freshness drift, expert recommendation, and search. At enterprise scale (thousands of documents, frequent re-indexing), this is a significant recurring cost with no budget estimate or cost cap.
5. Multi-tenancy model — 'enterprise' typically means multiple departments or customer organizations. The plan defines RBAC roles but never defines whether this is a single-tenant or multi-tenant SaaS deployment. If multi-tenant, every data model and query must be scoped by tenant_id from day one.
6. Email/notification infrastructure — Step 16 sends freshness alerts to content owners; Step 17 routes HITL proposals. No email provider (SES, SendGrid), template system, or notification preferences model is defined.
7. File storage service — Step 11 references storing media attachments in 'object storage' but no S3/GCS bucket configuration, CDN setup, signed URL generation, or storage lifecycle policy is specified anywhere.
8. Malware scanning for file uploads — Step 11 validates type and size but does not scan uploaded files for malware. This is a P0 security control for any enterprise platform accepting user uploads.
9. pgvector backup and recovery strategy — if the embedding store is corrupted or the PVC is lost, re-embedding all content from scratch can take hours and cost hundreds of dollars. No backup schedule or point-in-time recovery for pgvector is defined.
10. Data migration tooling — Step 1 mentions a 'migration plan drafted' as a deliverable but no migration step exists in the build plan. Enterprises adopting this platform will have existing knowledge bases (Confluence, SharePoint, Notion) that need import tooling.
11. API versioning strategy — the OpenAPI spec in Step 7 has no versioning scheme (/v1/, header-based, etc.). Breaking changes in a future version will break all integrations.

### Security Risks

1. JWT token storage location unspecified — if defaulted to localStorage, all active sessions are exfiltrable via any XSS vector in the rich text wiki editor or search results. Severity: Critical.
2. ProseMirror/TipTap rich text output stored and re-rendered without explicit server-side sanitization — a malicious contributor can inject stored XSS payloads that execute for all viewers of a wiki article. Severity: Critical.
3. Prompt injection in AI search — Step 8 identifies this risk and Step 9 says 'Prompt injection guard rules defined in coordinator system prompt.' System prompt instructions are not a reliable defense; they are bypassable. No input-layer sanitization, output validation, or sandboxed LLM execution model is specified. Severity: High.
4. File upload endpoint (Step 11) validates type and size but has no malware scanning. A contributor can upload a crafted PDF or SVG containing embedded JavaScript or exploit code. In an enterprise platform, this file is then served to potentially thousands of users. Severity: High.
5. LDAP/SCIM integration (Step 14) — no mention of LDAP injection prevention. If user-supplied input is used to construct LDAP queries without escaping (e.g., skill search queries that get forwarded to LDAP), this is exploitable. Severity: High.
6. Webhook receiver (Steps 7, 8) — webhook endpoints that accept external payloads require HMAC signature validation. This is called out in Step 8's attack surface list but no concrete implementation requirement is specified in Step 7's API design. Severity: Medium.
7. SBOM generated once (Step 8) but no continuous dependency monitoring defined. New CVEs in transitive dependencies will go undetected after the initial scan. Severity: Medium.
8. Search history persisted in localStorage with a 50-entry limit (Step 21) — if queries contain sensitive keywords (e.g., searching for confidential project names), this data is accessible to any script running in the browser context. Severity: Low-Medium depending on data sensitivity.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.337586
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

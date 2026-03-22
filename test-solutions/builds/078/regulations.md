# Regulatory Compliance — Virtual Lab

**Domain:** edtech
**Solution ID:** 078
**Generated:** 2026-03-22T11:53:39.331487
**HITL Level:** standard

---

## 1. Applicable Standards

- **FERPA**
- **WCAG 2.1**
- **NGSS Alignment**

## 2. Domain Detection Results

- edtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 5 | COMPLIANCE | Produce COPPA and FERPA compliance evidence artifacts: data inventory, parental  | Standards mapping, DHF, traceability |
| Step 6 | LEGAL | Draft Terms of Service, Privacy Policy (COPPA/FERPA compliant), educator license | Privacy, licensing, contracts |
| Step 9 | SECURITY | Perform threat model (STRIDE) for the virtual lab platform, covering student dat | Threat modeling, penetration testing |
| Step 24 | QA | Produce the QA test plan covering all experiment domains, collaboration workflow | Verification & validation |
| Step 27 | SYSTEM_TEST | Execute system-level integration and performance tests: simulation rendering und | End-to-end validation, performance |
| Step 28 | COMPLIANCE | Produce WCAG 2.1 AA compliance evidence: automated accessibility audit report (a | Standards mapping, DHF, traceability |

**Total tasks:** 30 | **Compliance tasks:** 6 | **Coverage:** 20%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | FERPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | WCAG 2.1 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | NGSS Alignment compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 14 | Engineering |
| regulatory_specialist | 3 | Compliance |
| qa_engineer | 3 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| marketing_strategist | 1 | Operations |
| ux_designer | 1 | Design |
| product_manager | 1 | Design |
| legal_advisor | 1 | Compliance |
| localization_engineer | 1 | Engineering |
| devops_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 47/100 (FAIL) — 1 iteration(s)

**Summary:** This plan is thorough in its compliance, legal, and testing coverage — the COPPA/FERPA artifacts, STRIDE threat model, WCAG accessibility audit, and multi-level test strategy are well-specified. However, it fails on two fundamental dimensions that prevent it from shipping as written. First, the 3D simulation scope (26+ experiments across Steps 16-18) is treated as a software engineering problem when it is primarily a 3D content production problem: the plan has no asset sourcing strategy, no 3D artist budget, and no fallback for the low-end school hardware that represents the majority of the K-12 addressable market. Second, the COPPA 'verifiable parental consent' implementation does not meet the FTC's legal standard, which exposes the company to regulatory action at launch. Beyond these blockers, three missing infrastructure elements (email service, vector database, Redis HA) would cause production failures within the first week of operation. The plan should be revised with a dedicated pre-build step for 3D asset strategy, a corrected COPPA consent mechanism, and explicit infrastructure additions before any implementation work begins.

### Flaws Identified

1. Steps 16-18 assume 26+ production-quality 3D simulations can be built as frontend tasks with no asset creation strategy. A single high-fidelity virtual frog dissection with 8 anatomically correct organ layers requires either months of 3D modeling work or expensive licensed GLTF assets. This is not a frontend coding task — it is a 3D content production problem, and the plan has no budget, vendor, or timeline for it.
2. COPPA 'verifiable parental consent' is a legal standard with specific FTC requirements (direct notice, explicit consent mechanisms). The plan's 'age gate → parent email → consent token' flow does not meet the 'verifiable' standard unless the verification method is one of: credit card verification, toll-free phone number, digital certificate, or video conference. A parent email alone does not satisfy this. Step 11 will fail a legal review.
3. Step 21 HITL model is operationally unworkable: low-confidence AI responses are 'routed to teacher review before delivery' during live experiment sessions. This means a teacher must be monitoring a review queue in real time while simultaneously teaching a class. In practice, responses will be blocked indefinitely, destroying the student experience. This design has never been used successfully in any real-time classroom AI product.
4. Step 13 uses 'keyword + embedding similarity match' for curriculum alignment but Step 7 (database) specifies only PostgreSQL with no vector database or pgvector extension. Embedding similarity requires a vector store. This is a missing infrastructure dependency between two steps.
5. Step 17 lists PubChem REST API as a runtime dependency for loading molecular structures during active student sessions. PubChem has rate limits, occasional downtime, and no SLA. A chemistry class of 30 students simultaneously loading molecules will hit rate limits. No caching layer, CDN, or local molecular data fallback is specified.
6. Steps 16-18 have a '≥60fps on a mid-range laptop' acceptance criterion with no definition of 'mid-range' and no WebGL fallback strategy. School-issued Chromebooks with ARM chips, older iPads, and Windows devices with Intel HD 4000 graphics routinely fail complex Three.js scenes. No mention of LOD switching, quality tiers, or a 2D fallback for low-end hardware.
7. Rapier.js WASM physics engine (Step 16) adds significant bundle weight and has a cold-start WASM compilation delay. On first load, 3D physics experiments will have a noticeable freeze. No preloading, service worker caching, or streaming compilation strategy is mentioned.
8. Step 14 describes Yjs CRDT collaboration with 'server-side Y.js via websocket relay' but does not specify CRDT state persistence. If a student disconnects and reconnects, where does the current Y.Doc state come from? Redis holds transient pub/sub but not CRDT document state. This is a data loss failure mode that will occur daily.
9. The AI domain classifier (Step 21) requires '≥95% accuracy on a test set of 50 questions' — 50 questions is statistically insufficient to validate 95% accuracy. Cross-domain questions (e.g., biophysics, biochemistry, molecular biology) are common in high school and will fail silently with no routing fallback.
10. Step 22 requires '100% translation key coverage for en/es/fr/zh-CN' with no mention of how translations are produced. Scientific terminology in Mandarin and French (e.g., 'Henderson-Hasselbalch equation,' 'Punnett square genetics') translated by machine will be inaccurate or nonsensical. No professional translator budget or review process is specified.
11. Step 26 requires 'COPPA under-13 E2E test verifies parent email is sent' but no email service (SES, SendGrid, Postmark) is provisioned anywhere in the infrastructure plan (Step 23). The COPPA consent flow, onboarding, teacher assignment notifications, and breach notification (72h legal requirement) all depend on email, but no email provider appears in environment variables, docker-compose, or devops setup.
12. Step 9 threat model covers IDOR on lab reports as a key threat but maps the mitigation to 'RBAC on all endpoints.' RBAC is role-level, not object-level authorization. A student could access another student's lab report if they know the report ID. Object-level authorization (verify report.owner_id == current_user.id) is a separate control not explicitly specified in Step 11.
13. Steps 16, 17, and 18 run in parallel (all depend on 15 and 12) and together represent 26+ distinct 3D simulations across three scientific domains. Running these in parallel requires at minimum 3 separate teams with 3D expertise. A single developer or agent cannot build the physics, chemistry, and biology simulation sets concurrently. No resource allocation or parallelization staffing model is acknowledged.

### Suggestions

1. Add a Step 0 or sub-task to Steps 16-18 specifically for 3D asset sourcing: evaluate Sketchfab licensing, BioDigital Human API for biology, commercial GLTF asset packs for molecular models, and contract a 3D artist for custom biology meshes. This must be resolved before any frontend 3D coding begins.
2. Replace the parent email consent flow with COPPA-compliant options: (1) credit card microcharge ($0.50 refunded) as verifiable method, (2) integration with a COPPA safe harbor certified service like Veritas or PRIVO. Document the chosen method explicitly in the compliance artifacts.
3. Redesign the AI assistant HITL model: instead of blocking delivery pending teacher review, use async review — deliver the response with a 'pending teacher verification' watermark, log it, and allow teacher correction post-delivery. This matches how Google Classroom and Khan Academy handle this problem.
4. Add pgvector to the PostgreSQL schema in Step 7, or add ChromaDB as a service in Step 23's docker-compose. Without this, the curriculum alignment engine in Step 13 has no vector similarity backend.
5. Add a PubChem data import pipeline that pre-loads the top 1,000 common curriculum molecules into your own storage at deploy time. Runtime PubChem calls should be a cache miss path only, not the primary load path.
6. Define three hardware tiers (high/mid/low) with explicit GPU specs. For low-end, implement 2D canvas fallbacks for all simulations — this is essential for equitable access in under-resourced schools, which are your primary K-12 market.
7. Add Yjs document state persistence: store the serialized Y.Doc binary in PostgreSQL (BYTEA column) on each collaboration session, updated every 10 seconds and on room close. Restore from this on reconnect. Without this, disconnection = data loss.
8. Add email service (SES or SendGrid) to Step 23 infrastructure as a required service. Add EMAIL_FROM and SMTP_URL to environment variables. This unblocks COPPA consent, teacher notifications, and breach notification legal obligations.
9. Expand the AI classifier test set to at minimum 200 questions covering cross-domain edge cases. Define the ground truth labeling methodology before writing the acceptance criterion. 50 questions cannot statistically demonstrate 95% accuracy.
10. Add a Parental Portal page (not just a consent email) — parents under COPPA have the right to review their child's data, request deletion, and withdraw consent at any time. This requires a dedicated authenticated portal, not just email links.

### Missing Elements

1. 3D asset sourcing and licensing strategy — the plan assumes 3D models exist but provides no source for biology anatomy meshes, molecular structures (beyond runtime PubChem), or physics simulation visual assets
2. Email service infrastructure — required for COPPA consent, teacher notifications, breach notification, and password reset, but absent from all devops and infrastructure steps
3. Parental portal / parent account type — COPPA grants parents ongoing access rights (review, delete, withdraw consent); no parent-facing UI is designed or built
4. Content moderation for student-generated content — lab reports and collaboration chat among minors require profanity/harmful content filtering, especially for the under-13 user segment
5. CDN strategy for 3D assets, WASM binaries, and textures — these assets will be 10-100MB per simulation domain; no asset delivery or lazy-loading strategy is defined
6. pgvector extension or vector database — required by Step 13's curriculum alignment engine but absent from Step 7 database schema and Step 23 infrastructure
7. Disaster recovery and backup — no database backup schedule, point-in-time recovery, or RTO/RPO targets defined for a product holding student educational records
8. LTI 1.3 certification process for LMS integrations — Canvas, Schoology, and Google Classroom each require separate OAuth app approval and LTI certification; these are multi-month vendor processes, not engineering tasks
9. Redis HA configuration — Redis is used for session state and collaboration pub/sub but is specified as a single instance with no sentinel, cluster, or persistence config; a Redis restart loses all active sessions
10. Hardware tier definitions and 2D fallback strategy for low-end school hardware
11. Breach incident response runbook — Step 6 includes '72h breach notification' in legal docs but no operational IR procedure exists to actually detect, contain, and notify within 72 hours
12. API rate limiting configuration per user tier — student accounts hitting AI assistant endpoints during a class could exhaust LLM API budget; no per-user or per-class rate limiting is specified

### Security Risks

1. IDOR on lab reports: RBAC controls role-level access but does not prevent student A from reading student B's report by guessing the report UUID. Object-level ownership checks must be explicitly implemented and tested in Step 11 — the threat model names this but the mitigation is incomplete.
2. WebSocket JWT exposure: WebSocket upgrade requests commonly pass tokens as URL query parameters (wss://host/room/123?token=...), which are logged by load balancers, proxy servers, and browser history. Step 14 specifies 'JWT token in handshake' without requiring header-based authentication, leaving this open.
3. Redis session state contains student PII without an explicit encryption-at-rest requirement. Step 7 requires AES-256 for PostgreSQL PII fields but places no equivalent requirement on Redis, which holds active session state including user identity.
4. TipTap rich text editor (Step 19) processes student-submitted HTML/JSON that will be stored and rendered for other users (teacher grading view). Without explicit server-side sanitization of TipTap JSON before storage, stored XSS is possible through malformed extension payloads.
5. ANTHROPIC_API_KEY is listed as an environment variable in Step 23 with no mention of secrets rotation, vault integration (HashiCorp Vault, AWS Secrets Manager), or access auditing. A compromised deployment environment exposes this key.
6. Age verification bypass: the age gate relies on self-reported date of birth. A minor can enter a false birthdate to bypass COPPA controls. No behavioral or verification signal supplements the self-report. This is a known, documented attack vector against COPPA implementations.
7. Multi-tenant Redis key collisions: collaboration rooms and session state stored in Redis must be namespaced by tenant (school district). Without explicit key prefixing strategy (e.g., {tenant_id}:{room_id}), a key collision between two districts would expose cross-tenant session state.
8. PubChem API response injection: molecular data loaded from PubChem at runtime and rendered via 3Dmol.js or Three.js is not mentioned as being sanitized. A compromised or spoofed PubChem response could inject malicious data into the 3D renderer.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.331538
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

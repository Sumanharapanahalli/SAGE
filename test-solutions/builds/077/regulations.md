# Regulatory Compliance — Flashcard App

**Domain:** edtech
**Solution ID:** 077
**Generated:** 2026-03-22T11:53:39.330691
**HITL Level:** standard

---

## 1. Applicable Standards

- **GDPR**
- **COPPA**
- **WCAG 2.1**

## 2. Domain Detection Results

- edtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 5 | COMPLIANCE | Produce compliance artifacts for COPPA, FERPA, and WCAG 2.1. Define parental con | Standards mapping, DHF, traceability |
| Step 6 | LEGAL | Draft Terms of Service, Privacy Policy (COPPA-compliant for under-13), and data  | Privacy, licensing, contracts |
| Step 16 | SECURITY | Perform security review: threat model for user-generated media uploads, authenti | Threat modeling, penetration testing |
| Step 18 | QA | Design and execute the QA test plan: functional test cases for all user flows, e | Verification & validation |
| Step 19 | SYSTEM_TEST | Execute end-to-end system tests: multi-user collaboration scenario, cross-platfo | End-to-end validation, performance |

**Total tasks:** 22 | **Compliance tasks:** 5 | **Coverage:** 23%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 2 | COPPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | WCAG 2.1 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 7 | Engineering |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| marketing_strategist | 1 | Operations |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| regulatory_specialist | 1 | Compliance |
| legal_advisor | 1 | Compliance |
| data_scientist | 1 | Analysis |
| localization_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 63/100 (FAIL) — 1 iteration(s)

**Summary:** This is a thorough and well-structured plan for a collaborative flashcard MVP — the compliance coverage (COPPA, FERPA, WCAG), SM-2 algorithm specificity, agentic card generation design, and testing depth are genuinely strong. However, it has several production-blocking gaps that would surface late and be expensive to fix: WebSocket sync assumes single-server deployment with no horizontal scaling path; the conflict resolution strategy silently destroys SR data in collaborative offline scenarios; security review happens after the entire stack is built rather than informing its design; i18n is a retrofit rather than built-in from step one; and COPPA verifiable parental consent is documented as a requirement but the actual technical mechanism (not just an email form) is unspecified, which is a legal blocker. The plan also has infrastructure gaps — no CDN for media, no email service for sharing invitations, no IaC for production, and an antivirus stub that provides no actual protection. At MVP scope for a non-regulated product this would be a 63: the core learning loop is well-designed, but at least five of the identified flaws would require architectural rework rather than incremental fixes if left until late in development.

### Flaws Identified

1. WebSocket sync has no horizontal scaling strategy. Broadcasting to 'all connected collaborators' works on a single server but breaks the moment you add a second backend instance. No Redis pub/sub or sticky session strategy is mentioned anywhere in the plan.
2. Conflict resolution is 'last-write-wins by server timestamp' for mobile sync. This silently destroys SR state: two users study the same shared card offline, one's review data is erased on sync. For a spaced repetition app, lost review history is the worst possible data loss.
3. Security review at step 16 is after the entire backend (step 9) and frontend (step 11) are built. IDOR on deck access, stored XSS in card content, and FERPA data leakage are architectural concerns, not late-stage checks. Finding these post-build means rework, not fixes.
4. Localization is step 15, after frontend (step 11) and mobile (step 12) are complete. Retrofitting i18n into an existing React/RN codebase requires touching every component. This is a known high-friction rework that teams consistently underestimate.
5. Step 8 (monorepo and toolchain setup) depends on step 7 (DB schema). This is wrong — repo structure, ESLint, Docker Compose, and environment config are prerequisites for development, not outputs of schema design. This bottleneck delays all parallel dev work unnecessarily.
6. RLS (Row-Level Security) for deck_collaborators is described as a 'sketch'. PostgreSQL RLS is the enforcement mechanism for multi-user data isolation — a sketch that doesn't ship is a FERPA violation waiting to happen.
7. Step 13 (agentic card generation) requires semantic similarity embeddings for duplicate detection but the database design (step 7) has no embeddings table or vector index. pgvector extension, collection schema, and embedding model choice are completely absent.
8. The forgetting curve parameter estimation in step 14 ('initial stability, decay estimated per user per deck') requires meaningful per-user study history to produce valid estimates. New users with <10 reviews per deck will get garbage parameters. No cold-start fallback defined.
9. Step 12 (mobile) passes an Expo build as the acceptance criterion, but there is no App Store/Google Play submission path, no signing certificate management, no review timeline buffer, and no TestFlight/internal track setup. Expo build ≠ shippable app.
10. Step 9 defines rate limits in the OpenAPI spec step (step 10) but the backend implementation step has no rate limiting in its acceptance criteria. Rate limits exist on paper only — no Redis-backed limiter is wired in.

### Suggestions

1. Move security threat modeling to step 3-4 (alongside PRD), not step 16. Define the IDOR and XSS mitigations before writing the backend, not after.
2. Replace last-write-wins conflict resolution with a merge strategy that combines SR state: take the more-conservative next_review_date (earlier date wins) and max repetitions. Lost reviews in SR apps produce overconfidence; this heuristic prevents it without requiring CRDTs.
3. Add Redis pub/sub to the WebSocket sync architecture explicitly. The coordinator pattern in step 8 already includes Redis — wire it for WS fanout. Document the connection limit per pod and horizontal scaling strategy before step 9 ships.
4. Move i18n infrastructure setup to step 8 (CONFIG). Scaffold react-i18next and all locale JSON files before any UI strings are written. Enforce the no-hardcoded-strings rule via ESLint (eslint-plugin-i18next) from day one.
5. Decide TimescaleDB vs PostgreSQL partitioning in step 7, not step 14. The schema and migration strategy differ significantly — this is an architectural decision, not a data pipeline detail.
6. Add pgvector to the step 7 database design for the duplicate-detection embeddings (step 13). Include a card_embeddings table with (card_id, embedding vector(1536)) and an ivfflat index.
7. Add an email service (SES or SendGrid) to the step 8 Docker Compose and step 9 backend implementation. Deck sharing by email invite (step 11 acceptance criteria) has no delivery mechanism in the current plan.
8. Define push notification backend infrastructure in step 9: APNS/FCM credential management, a notifications table for queuing, and a Celery task for delivery. expo-notifications handles the client SDK; the server side is unaddressed.
9. Add infrastructure-as-code (Terraform or Pulumi) as a deliverable in step 20. Without IaC, the production environment is undocumented and non-reproducible.
10. Define a per-user storage quota for media uploads in step 7 schema and step 9 backend. Open-ended image/audio upload with only a per-file size limit will generate runaway S3 costs at scale.

### Missing Elements

1. CDN for media delivery. Images and audio served directly from S3 will have unacceptable latency for non-US users. No CloudFront, Cloudflare, or equivalent is mentioned anywhere.
2. Full-text search for decks and cards. A user with 500 decks and 10,000 cards needs search. No PostgreSQL full-text search, Meilisearch, or equivalent is in the plan.
3. Age gate implementation on the registration endpoint. COPPA requires blocking under-13 registration without verifiable parental consent. The backend step 9 endpoint list has no age verification flow — the COPPA flag appears on the user record but the gate that prevents creation is absent.
4. Database backup and point-in-time recovery strategy. With FERPA student data, data loss is a compliance event, not just an operational inconvenience.
5. Media content moderation. User-uploaded images and audio can contain CSAM or FERPA-protected content. The plan mentions HITL checkpoints for content moderation in the PRD but no implementation exists — not even a stub.
6. Verifiable parental consent mechanism (COPPA §312.5). 'Email + consent form' is not verifiable consent under COPPA. Credit card transaction, knowledge-based authentication, or digital signature service is required. This is a legal blocker for under-13 users, not a design preference.
7. Webhook or background job for SR reminder emails (web users). Push notifications cover mobile but web users get no review reminders — a significant retention gap given D7/D30 retention is a success metric.
8. Audio transcoding and image optimization pipeline. Raw WAV uploads (≤10MB) should be converted to compressed formats server-side. No FFmpeg worker, Cloudinary integration, or equivalent is specified.
9. Session management and refresh token rotation. JWT is mentioned but refresh token strategy, expiry, revocation on logout, and concurrent session limits are unspecified — critical for a FERPA-compliant system where account sharing is a violation.
10. Staging environment definition with production parity. Step 20 mentions staging deploy but no staging infrastructure spec — same DB engine version, same Redis config, same media storage setup. Without parity, staging test results are unreliable.

### Security Risks

1. Stored XSS in card content: Cards support rich text with image embeds. Without a strict server-side HTML sanitizer (DOMPurify server-side equivalent, not client-side), a malicious card shared to a classroom deck becomes a stored XSS vector affecting all students who study it. Step 16 mentions this but the backend step 9 has no sanitization in its acceptance criteria.
2. IDOR on media URLs: S3 pre-signed URLs or direct blob URLs for card media are accessible to anyone with the URL. A private deck's audio file URL, once obtained, can be shared externally. No per-request authorization check on media access is specified.
3. Antivirus scan is a stub, not an implementation. Step 16 acceptance criterion says 'antivirus scan stub in place' — a stub that doesn't scan is no protection against malware-embedded files. This needs a real integration (ClamAV, VirusTotal API) before production.
4. JWT secret rotation is unaddressed. A compromised JWT secret invalidates all sessions — no rotation strategy, no short expiry + refresh pattern, no key versioning is defined.
5. FERPA audit trail for educator access: Step 5 mentions audit trail requirements but no implementation is in the backend step. Educator access to student study records without a logged audit trail is a FERPA violation.
6. Semantic similarity embeddings (step 13) require sending card content to an external LLM API. If cards contain FERPA-protected student-generated content (e.g., a student's personal notes), this is a third-party data sharing event that requires disclosure in the Privacy Policy and potentially a DPA with the LLM provider.
7. WebSocket authentication: The WS /sync endpoint is listed in step 9 but WebSocket upgrade requests cannot carry Authorization headers in browser clients. Token-in-query-param is a common workaround but logs tokens in server access logs. No WebSocket auth strategy is specified.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.330759
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

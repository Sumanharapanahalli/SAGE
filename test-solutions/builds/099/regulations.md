# Regulatory Compliance — Visitor Management

**Domain:** enterprise
**Solution ID:** 099
**Generated:** 2026-03-22T11:53:39.337835
**HITL Level:** standard

---

## 1. Applicable Standards

- **GDPR**
- **SOC 2**
- **Physical Security Standards**

## 2. Domain Detection Results

- enterprise (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 3 | LEGAL | Draft NDA template (mutual and one-way variants), visitor privacy notice (GDPR A | Privacy, licensing, contracts |
| Step 4 | SECURITY | Produce threat model for visitor management system: PII data at rest and in tran | Threat modeling, penetration testing |
| Step 8 | COMPLIANCE | Produce initial ISO 27001 and SOC 2 evidence artifacts: information security pol | Standards mapping, DHF, traceability |
| Step 22 | QA | Design and execute quality assurance test plan: test cases for all six core flow | Verification & validation |
| Step 23 | SYSTEM_TEST | Execute end-to-end system test suite: full visitor lifecycle from invitation ema | End-to-end validation, performance |
| Step 26 | COMPLIANCE | Compile final ISO 27001 and SOC 2 evidence package: statement of applicability ( | Standards mapping, DHF, traceability |

**Total tasks:** 26 | **Compliance tasks:** 6 | **Coverage:** 23%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 2 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | Physical Security Standards compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| regulatory_specialist | 3 | Compliance |
| devops_engineer | 2 | Engineering |
| product_manager | 1 | Design |
| business_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| qa_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 61/100 (FAIL) — 1 iteration(s)

**Summary:** This is a structurally sound, unusually comprehensive plan for enterprise visitor management — the dependency graph is logical, acceptance criteria are specific, and compliance concerns are addressed earlier than most plans attempt. However, it has several production-blocking flaws that require rework before implementation begins. The most critical: (1) the NDA signing mechanism (canvas PNG) is legally unenforceable and would expose every signed NDA to challenge; (2) the async watchlist check creates a race condition where a flagged visitor receives a physical badge before security is alerted — a fundamental security failure; (3) the unauthenticated evacuation endpoint is a PII exposure risk dressed up as an operational convenience. Beyond these three blockers, the plan has significant gaps in key management, GDPR consent mechanics, kiosk OS hardening, and physical badge enforcement that would cause either compliance failure or operational embarrassment post-launch. Score of 61 reflects a plan with the right instincts and wrong execution on several high-stakes items. Fix the NDA signing approach, make the watchlist check synchronous with a blocking gate, and secure the evacuation endpoint before any backend sprint begins.

### Flaws Identified

1. NDA signing (Step 14) uses canvas PNG blob embedded in a reportlab PDF. This is NOT a legally enforceable e-signature under ESIGN Act (US), eIDAS (EU), or ECA (UK). A PNG image in a PDF has zero cryptographic provenance. Without a proper e-signature provider (DocuSign, Adobe Sign, or at minimum a hash-sealed audit trail from a recognised TSP), every NDA signed through this system is contestable in court. This is not a legal edge case — it is a fundamental design failure for a compliance-claiming product.
2. Watchlist check (Step 12) is specified as an 'async background check'. This creates a race condition where a flagged visitor can complete check-in, trigger badge printing, and have a physical badge in hand before the watchlist result returns. For a security-sensitive system, this is not a latency optimisation — it is a security bypass. The check must be synchronous and block badge printing.
3. Evacuation endpoint (Step 16) is 'no auth token required for emergency access (IP whitelist only)'. IP whitelisting on a local network is not access control — it is a comfort blanket. Any device on the site LAN (visitor laptop on guest WiFi, compromised IoT device, attacker who tailgated in) can enumerate the full visitor roster. The 'emergency access' argument is false: pre-issued emergency bearer tokens stored offline on security tablets take 0 seconds longer to use than an unprotected endpoint.
4. PII encryption is inconsistent between Step 6 (pgcrypto AES-256 at database column level) and Step 10 (Fernet AES-128-CBC at application layer). These are different algorithms, different key lengths, and different key management surfaces. Double-encrypting adds complexity without a defined key rotation strategy. The plan never specifies where encryption keys live, how they are rotated, or who manages them — omitting this from an ISO 27001 candidate system is a gap the auditor will immediately flag.
5. Step 17 requires the routing_agent to classify badge type correctly in >95% of test cases with no discussion of training data source, confidence thresholds, or fallback behaviour in the 5% failure case. A misclassified badge type (e.g., 'standard' instead of 'contractor') is a security incident in regulated facilities. Stating a 95% accuracy SLA for an LLM classifier without a deterministic fallback is not an acceptance criterion — it is wishful thinking.
6. LDAP host lookup (Step 10) requires a 500ms SLA with no mention of connection pooling, local cache, or replica failover. Active Directory outages are common. Without a cached fallback, an AD timeout blocks every check-in across every site simultaneously. This is a single point of failure in the critical path.
7. Kiosk OS hardening is absent. 'Chrome kiosk flags + CSS full-screen lock' (Step 20) is not kiosk security. ESC, F11, Ctrl+W, Win+L, or a Bluetooth keyboard attachment all break it on a standard Windows or Linux install. A production kiosk requires OS-level lockdown: ChromeOS managed enrollment, Windows IoT with shell replacement, or equivalent. This is not optional for a device handling PII in a public-facing context.
8. Badge expiry enforcement (Step 13) is stated as 'expired badges rejected on re-scan' but the plan contains no specification of badge readers at entry/exit points, no access control system integration, and no defined scanner hardware. Who scans the badge, with what device, at what point? The enforcement mechanism is undefined, making the acceptance criterion untestable.
9. Step 15 (SMS via Twilio) specifies delivery within 30s but ignores Twilio throughput limits. Short-code throughput is 100 msg/s; long-code is 1 msg/s in the US and heavily filtered in the EU. A 100-concurrent-kiosk load scenario (Step 23) would queue 100 SMS messages simultaneously. With a 1 msg/s long-code limit, the last notification arrives after 100 seconds — 3x over SLA. No carrier-specific rate limit strategy or number provisioning plan is included.
10. GDPR consent capture is never implemented technically. Step 3 produces a privacy notice HTML file. Steps 11 and 20 collect PII (emergency contact, vehicle registration, photo). Nowhere is there a GDPR-compliant consent checkbox with granular purpose selection, consent withdrawal mechanism, or right-to-erasure implementation for captured visitor photos. The legal artifact exists; the technical enforcement does not.

### Suggestions

1. Replace canvas-signature PDF with a PKCS#7 / PAdES-compliant e-signature flow. Minimum viable: integrate a provider like DocuSign Embedded Signing or use a hash-sealed audit record (visitor_id, timestamp, IP, device_id, document_hash signed with server private key) that satisfies ESIGN's 'intent to sign' and 'record retention' requirements. Get this reviewed by legal before Step 14 begins.
2. Make the watchlist check synchronous in the critical path. If the check cannot complete within a defined timeout (e.g., 3s), default to 'hold for manual review' — do not default to 'allow'. Add a 'pending clearance' visit state that shows on the kiosk with a 'please wait' screen and notifies the receptionist.
3. Replace IP-whitelist-only evacuation access with offline-capable emergency tokens: pre-generate short-lived tokens (24h TTL) monthly, print and laminate them with the site's evacuation quick-reference card. Security staff enter the token on first use; subsequent requests in the same session reuse the session cookie. Zero extra steps in a real emergency; auditable access.
4. Pick one encryption layer and document the key management strategy. Recommendation: application-layer encryption (AES-256-GCM via cryptography library) with keys stored in HashiCorp Vault or AWS KMS, not pgcrypto, so key rotation does not require DB-layer changes. Remove pgcrypto from Step 6 or explicitly document why both layers exist.
5. For the routing/badge classifier in Step 17: define a confidence threshold (e.g., >0.85) below which the agent outputs 'unknown' and the system falls back to a deterministic rule table keyed on visit_purpose enum values. LLM classifiers in security workflows must have deterministic fallbacks, not just accuracy targets.
6. Add an LDAP cache layer (Redis, 5-minute TTL) with a read-through pattern. On AD unavailability, serve cached host records and log a degraded-mode audit event. Acceptance criteria should include: 'LDAP cache serves host lookup within 50ms when AD is unreachable; degraded mode persists for up to 30 minutes before requiring admin intervention.'
7. Separate kiosk OS specification into its own CONFIG/INFRA step. Specify the target OS (ChromeOS Managed, Windows IoT Enterprise, or Ubuntu with openbox + xdotool lockdown), the management enrollment process, and BIOS password + secure boot requirements. This should be a prerequisite for Step 20, not an afterthought in the payload.
8. Add an explicit GDPR consent step to both the pre-registration form (Step 11/19) and the kiosk walk-in flow (Step 12/20). Consent must be: per-purpose (photo capture, email notifications, emergency contact storage), revocable, and stored with timestamp + version in a separate consent_records table. Right-to-erasure must cascade to MinIO photos and all PII columns within 30 days.
9. For multi-site enterprise deployments, clarify whether this is single-tenant (one DB, RLS by site_id) or multi-tenant SaaS (separate schema or DB per enterprise customer). Several enterprise buyers will have data sovereignty requirements (EU data must not leave EU) that RLS alone cannot satisfy. Document the architecture decision and its compliance implications in Step 2.
10. Add Celery dead letter queue (DLQ) configuration and alerting for all async tasks. A silently-dropped 'send_confirmation_email' or 'send_arrival_notification' task is invisible without DLQ monitoring. Define retry policies (3 retries, exponential backoff) and alert on DLQ depth > 0 for security-critical tasks like watchlist_sync.

### Missing Elements

1. Key management specification: where encryption keys live, rotation policy, and break-glass procedure. Without this, the entire PII encryption design is incomplete regardless of algorithm choice.
2. Physical kiosk hardening specification: OS image, management enrollment, BIOS lockdown, USB port disablement, tamper detection. None of these appear in any step.
3. Badge reader / access control system integration: the plan assumes badges are enforced but never specifies the enforcement hardware, API, or integration. Step 13's expiry enforcement criterion is untestable without this.
4. Right-to-erasure (GDPR Article 17) technical implementation: how visitor data is fully purged from PostgreSQL, MinIO (photos, NDAs), Redis (evacuation roster), and all backups within the 30-day obligation window.
5. Consent management technical implementation: consent_records table, per-purpose granularity, revocation endpoint, and audit trail for consent changes.
6. Network segmentation specification: kiosk network zone, badge printer network zone, admin portal zone, and firewall rules between them. The threat model (Step 4) identifies these surfaces but the config step (Step 9) has no network architecture.
7. Backup and point-in-time recovery specification for PostgreSQL: backup frequency, retention, encryption, and tested restore time. The DR test in Step 23 assumes this exists but it is never designed.
8. Twilio number provisioning plan: short-code vs long-code vs alpha-sender per target country, and throughput capacity matched to expected peak load.
9. Offline kiosk operation design: Step 12 mentions Redis offline queue but the frontend (Step 20) only shows an error screen. There is no design for fully offline check-in (paper log, manual badge) or the reconciliation process when connectivity is restored.
10. Multi-jurisdiction NDA enforceability review: Step 3 produces templates for US/EU/UK but does not address whether a touchscreen finger signature (even with a proper e-sig provider) satisfies the specific requirements of each jurisdiction for the NDA type (trade secret protection, IP assignment).
11. Penetration test execution: Step 4 produces a pentest scope document and Step 26 references a pentest report, but no step in the plan actually executes the penetration test. This is a missing step between Steps 21 and 26.
12. Multi-language / internationalisation support: enterprise visitor management at global sites requires at minimum the kiosk UI and NDA to be presented in the visitor's language. No i18n step exists.

### Security Risks

1. Async watchlist check race condition (Step 12): flagged visitor receives physical badge before security alert fires. This is the highest-severity risk in the plan — a determined bad actor who appears on the watchlist can complete check-in and be inside the building before security is notified.
2. Unauthenticated evacuation endpoint (Step 16): exposes full on-site visitor roster (names, companies, check-in times) to any device on the local network. In a social engineering or insider threat scenario, this is a pre-attack reconnaissance goldmine.
3. ZPL over raw TCP 9100 (Step 13): badge printers accepting unauthenticated raw TCP connections on the corporate LAN allow any device on the network to print arbitrary visitor badges. An attacker could print a badge claiming to be any person with any badge type. The threat model identifies this surface but no mitigation is specified in the implementation.
4. Canvas PNG NDA signature (Step 14): beyond legal unenforceability, the PNG blob provides no cryptographic binding between the signature image and the document content. An attacker with database write access could swap the NDA document hash while leaving the signature intact, or vice versa, with no detection mechanism.
5. Kiosk session residue (Step 20): a 60-second idle timeout with no specification of what 'session clear' means technically (memory wipe, cookie deletion, IndexedDB clear, React state reset) could leave PII from visitor A accessible to visitor B if the timeout logic is incomplete. Browser storage APIs retain data across soft reloads.
6. QR code JWT secret management (Step 11): pre-registration QR codes contain signed JWTs. The signing key is not specified. If this key is shared across all sites and rotated infrequently, a compromise at one site invalidates or forges pre-registrations across all sites.
7. Photo storage without access expiry (Steps 12/14): visitor photos are stored in MinIO and referenced in badge generation and host notifications via URLs. If these URLs are not pre-signed with short expiry times, any person with the URL (forwarded email, browser history, log file) can access visitor photos indefinitely.
8. LDAP credentials in config (Step 10): the python-ldap3 integration requires a service account DN and password. These credentials are not mentioned in the secrets management section. Hardcoded or .env-stored LDAP service account credentials with broad read access to the AD tree are a high-value target.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.337881
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

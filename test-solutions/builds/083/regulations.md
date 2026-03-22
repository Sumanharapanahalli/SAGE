# Regulatory Compliance — Dating App

**Domain:** consumer_app
**Solution ID:** 083
**Generated:** 2026-03-22T11:53:39.333090
**HITL Level:** standard

---

## 1. Applicable Standards

- **GDPR**
- **CCPA**
- **Age Verification Laws**
- **SOC 2**

## 2. Domain Detection Results

- consumer_app (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | SECURITY | Produce threat model and security architecture for dating_app: identity verifica | Threat modeling, penetration testing |
| Step 5 | LEGAL | Draft Terms of Service, Privacy Policy, and community guidelines for dating_app. | Privacy, licensing, contracts |
| Step 26 | QA | Create the quality assurance test plan: test case catalog for all features, edge | Verification & validation |
| Step 30 | SYSTEM_TEST | Execute full system integration testing: end-to-end user journey from registrati | End-to-end validation, performance |

**Total tasks:** 30 | **Compliance tasks:** 4 | **Coverage:** 13%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 2 | CCPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | Age Verification Laws compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
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
| developer | 16 | Engineering |
| devops_engineer | 3 | Engineering |
| qa_engineer | 3 | Engineering |
| marketing_strategist | 1 | Operations |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| regulatory_specialist | 1 | Compliance |
| legal_advisor | 1 | Compliance |
| localization_engineer | 1 | Engineering |
| technical_writer | 1 | Operations |
| system_tester | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 58/100 (FAIL) — 1 iteration(s)

**Summary:** This is an ambitious, well-structured plan that covers the right surface area for a dating app MVP — the technology choices are reasonable, the compliance awareness is above average, and the dependency graph is mostly coherent. However, it has several critical production failures that would surface within weeks of launch: push notifications are entirely absent (every core engagement loop breaks without them), the E2E encryption design directly contradicts the server-side history API, the matching algorithm has no scalability architecture and will collapse under real load, and age verification is legal self-attestation that will not satisfy COPPA or the UK Online Safety Act. The soft-delete-as-erasure pattern is a GDPR compliance fiction. The subscription entitlement model breaks the moment a user pays via Stripe and opens the iOS app. For a prototype with 100-1000 users and legal tolerance for gaps, this plan gets you to a demo. For a production dating app targeting real regulatory jurisdictions and real scale, at least 6 of the flaws identified above represent launch-blocking issues that require fundamental rework, not incremental fixes.

### Flaws Identified

1. E2E encryption (Signal Protocol, Step 12) is fundamentally incompatible with the server-side chat history endpoint GET /chat/{match_id}/history. If messages are E2E encrypted, the server stores ciphertext only — it cannot return a decrypted history. The plan never resolves this contradiction. You either have E2E encryption or server-readable history, not both.
2. Push notifications are completely absent from the entire 30-step plan. No APNs/FCM setup, no notification service, no token registration endpoints. New match, new message, super-like, call incoming — every core engagement loop depends on push. This is a P0 missing feature, not an oversight.
3. Age verification is self-attestation via birthdate (Step 9). Step 5 lists COPPA compliance and the UK Online Safety Act requires age assurance — DOB entry does not satisfy either. No age verification provider (Yoti, Veriff, Onfido) is specified. A regulator will reject this as insufficient.
4. The matching algorithm performance target (200ms for 20 candidates with 10k+ users in radius) has no precomputation strategy. Running live multi-stage geo+preference+compatibility scoring on PostgreSQL per request will not hit 200ms at any meaningful scale. No mention of offline candidate pool generation, Redis cache, or vector similarity indexing for interests.
5. Soft-delete is not GDPR erasure (Steps 6, 8). GDPR Article 17 requires actual deletion of PII. Soft-deleting a row keeps all personal data in the database. The plan needs a separate scheduled erasure job that nulls/removes PII fields and confirms deletion within the 30-day window. Soft-delete for foreign key integrity is fine, but it is not the erasure mechanism.
6. AWS Rekognition is not available in eu-west-1 with the same feature set (liveness detection may require us-east-1). Sending EU user photos to a US AWS service for processing is a GDPR cross-border transfer issue. No Standard Contractual Clauses or data transfer mechanism is mentioned.
7. The subscription cross-platform consistency model is broken. A user who subscribes via Stripe (web) then opens the iOS app will appear as free-tier because Apple StoreKit won't know about the Stripe subscription. The 30-second sync target (Step 15) only works within a single payment rail. No unified entitlement layer is specified.
8. WebSocket offline delivery is unaddressed. Step 12's server-side design uses Redis pub/sub, which is fire-and-forget. If the recipient is offline, the message is lost from the pub/sub channel. Step 19 mentions 'reconnect logic' on the client, but the server has no message queue for offline delivery. Messages sent while a user is offline will be silently dropped.
9. The automated shadow-ban threshold (3 reports in 24 hours, Step 14) is trivially gameable by coordinated harassment groups spacing reports across multiple days, and simultaneously abusable for mass-false-reporting innocent users. No mention of reporter credibility weighting, report velocity analysis, or appeal process.
10. Step 13's 'call recording opt-in for safety' has no implementation path. Two-party consent laws vary by jurisdiction, storage costs are unaccounted for, retention policy is undefined, and there is no moderation workflow for reviewing recorded calls. This feature will be cut in production or create legal liability.
11. The matching algorithm has no fairness or bias evaluation. Collaborative filtering signals (activity_recency, premium_boost, mutual_like_bonus) create rich-get-richer loops that systematically disadvantage new users and non-subscribers. No A/B testing framework, no bias metrics, no equity guards are in the plan.
12. Step 23 (localization) is planned after all frontend screens are built. Retrofitting i18n into completed components is 3-5x the work of building with i18n from the start. React Native text rendered natively (e.g., inside react-native-reanimated animations, WebRTC overlays) often cannot be extracted by standard i18n tooling.

### Suggestions

1. Add a Step 7.5 for push notification infrastructure: APNs HTTP/2 + FCM v1 setup, device token registration endpoint (POST /devices/token), and a notification dispatch service. This unblocks match alerts, message notifications, and call incoming — all critical for retention.
2. Resolve the E2E encryption contradiction by choosing a clear model: (a) Server-managed encryption (server holds keys, can serve history, can moderate) — simpler, better for safety/moderation; or (b) True E2E (client holds keys, server stores ciphertext, no server-side history, no content moderation on messages). For a dating app with safety requirements, option (a) is more defensible.
3. Add a precomputed candidate pool service to Step 11: a background job (Celery beat or AWS EventBridge) that pre-generates and caches ranked candidate lists per user in Redis, refreshed every 15-30 minutes. The live /discover endpoint reads from cache, not from live DB queries. This is the only credible path to 200ms at scale.
4. Replace birthdate self-attestation with an integration to a real age verification vendor (Veriff, Onfido, or Yoti) for the 18+ gate. At minimum, add a flag for 'age_verified: false' with a grace period before blocking access, so the system can be upgraded without a breaking change.
5. Add a unified entitlement service (Step 15.5): a single source of truth for subscription status that ingests webhooks from Stripe, Apple App Store Server API, and Google Play Developer API, and exposes a single GET /entitlements/me endpoint. Every feature gate hits this service, not the raw payment provider state.
6. Add Step 11.5 for Redis Streams or a proper message queue (SQS FIFO) for chat message persistence before the WebSocket delivery layer. Store messages durably on receipt, then fan out to connected clients via pub/sub. This provides offline delivery, at-least-once guarantees, and decouples persistence from transport.
7. Add observability to Step 7: Sentry for error tracking, Datadog or Grafana Cloud for APM, and structured logging (JSON) from day one. Dating apps have complex failure modes (match detection race conditions, WebSocket reconnect storms) that are impossible to debug without traces.
8. Add an appeal workflow to Step 14's ban management: users need a path to contest shadow-bans and permanent bans, both for legal defensibility and to handle false-positive reports from coordinated harassment.
9. Specify a data residency enforcement mechanism beyond Route 53 geolocation in Step 24. Route 53 geolocation routes HTTP traffic, not data — you need application-level tenant routing that writes EU user records only to the eu-west-1 RDS instance and enforces this at the ORM layer.
10. Add a rate-limiting layer at the application level (Step 8/11): Redis-backed rate limits on /swipes (e.g., 100/hour for free users), /discover, and /photos/upload. WAF rules alone are insufficient — WAF operates at IP level and won't catch authenticated API abuse.

### Missing Elements

1. Push notification service (APNs + FCM) — completely absent from all 30 steps
2. Unified entitlement/subscription state service across Stripe, Apple, and Google payment rails
3. Offline message delivery mechanism (Redis Streams, SQS, or equivalent)
4. Real age verification vendor integration (currently only self-attested DOB)
5. Analytics pipeline — no Mixpanel/Amplitude/Firebase Analytics. Success metrics in Step 2 are defined but never instrumented anywhere in the plan
6. Error tracking and APM (Sentry, Datadog) — zero observability tooling in the plan
7. Database backup and disaster recovery strategy for RDS (point-in-time recovery config, cross-region snapshot replication)
8. GDPR erasure job — a scheduled process that actually purges PII fields from soft-deleted records within the 30-day window
9. Appeal and ban review workflow for moderation actions
10. Certificate pinning for the React Native app to prevent MITM on internal API endpoints
11. Pre-computation / caching strategy for the matching algorithm at scale
12. Admin dashboard frontend — Step 14 defines admin API endpoints but no UI for moderators is planned
13. Content moderation for chat text (only photo moderation is covered — text harassment is unaddressed)
14. Referral / invite system — omitted but standard for dating app growth loops; not a blocker but notable for V1 roadmap
15. App store review strategy — dating apps face heightened scrutiny from Apple; no review preparation checklist, content rating classification, or privacy nutrition label specification

### Security Risks

1. Refresh token revocation gap: 30-day refresh tokens with no revocation endpoint or device session management. A stolen refresh token gives full account access for up to 30 days. No mention of refresh token families (rotation + invalidation on reuse detection).
2. Location triangulation: PostGIS POINT is stored with full precision. 'Never exposed as raw coordinates' is an implementation promise, not an enforced constraint. Fuzzy location rounding must be applied at the query layer, not just the serialization layer. If any join or aggregate leaks a precise distance, adversaries can triangulate exact location with 3+ queries.
3. Apple IAP receipt validation is deprecated: the legacy /verifyReceipt endpoint was deprecated in 2023. Step 15 must use the App Store Server API with server-to-server JWT authentication. Using the deprecated endpoint creates validation bypass risks and will eventually stop working.
4. Government ID data handling: Step 4 lists 'government ID for verification' as sensitive data but no verification vendor (Veriff, Onfido) is specified, no ID data retention/deletion policy is defined, and no mention of how ID data is isolated from the main user database. Storing government IDs on the same server as dating profiles is a catastrophic breach scenario.
5. Signed S3 URL leakage: 1-hour signed URLs (Step 10) can be shared outside the app. No Referer header validation, no CloudFront signed cookie alternative for restricting photo access to authenticated sessions. A user can screenshot a URL and share it for an hour.
6. WebRTC TURN credential scope: Step 13 says TURN credentials expire after 1 hour, but if credentials are issued at call initiation (POST /calls/initiate), a user could harvest TURN credentials without completing calls and use Twilio TURN bandwidth at the app's expense. Credentials should be bound to a specific call session ID.
7. Shadow-ban information leakage: if a shadow-banned user can detect they are shadow-banned (e.g., by noticing zero matches despite high activity), this reveals the moderation action and allows ban evasion. The UX needs to simulate normal operation for shadow-banned accounts.
8. OTP brute force: Step 8 requires OTP codes expire in 10 minutes and are single-use, but no mention of attempt rate limiting (e.g., max 5 attempts per OTP before requiring re-issue). A 6-digit OTP has 1M combinations — without rate limiting, it is brute-forceable within the expiry window.
9. Stripe webhook replay: Step 15 correctly requires signature verification, but no mention of idempotency key storage to prevent replay attacks. A replayed 'invoice.payment_succeeded' event could incorrectly extend a subscription.
10. No mention of dependency scanning or SBOM for the supply chain. React Native + Expo + 15+ third-party SDKs (WebRTC, IAP, Giphy, Stripe) is a large attack surface with no automated CVE monitoring specified.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.333128
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

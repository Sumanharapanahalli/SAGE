# Regulatory Compliance — Habit Tracker

**Domain:** consumer_app
**Solution ID:** 089
**Generated:** 2026-03-22T11:53:39.334883
**HITL Level:** standard

---

## 1. Applicable Standards

- **GDPR**
- **CCPA**
- **Apple/Google Health Policies**

## 2. Domain Detection Results

- consumer_app (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 6 | SECURITY | STRIDE threat model on auth, social group access control, and health data handli | Threat modeling, penetration testing |
| Step 7 | LEGAL | Draft Terms of Service, Privacy Policy, and Data Processing Agreement covering h | Privacy, licensing, contracts |
| Step 8 | COMPLIANCE | Build compliance traceability matrix mapping PRD requirements to implementation  | Standards mapping, DHF, traceability |
| Step 18 | EMBEDDED_TEST | Firmware unit tests (Unity + CMock) and HIL test specification for wearable: BLE | Hardware-in-the-loop verification |
| Step 19 | QA | QA test plan for habit_tracker mobile app: smoke (20 cases), regression (150 cas | Verification & validation |
| Step 20 | SYSTEM_TEST | End-to-end system tests: full user journeys via Detox (React Native E2E on iOS S | End-to-end validation, performance |

**Total tasks:** 23 | **Compliance tasks:** 6 | **Coverage:** 26%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 2 | CCPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | Apple/Google Health Policies compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| qa_engineer | 3 | Engineering |
| regulatory_specialist | 2 | Compliance |
| devops_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| marketing_strategist | 1 | Operations |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| legal_advisor | 1 | Compliance |
| system_tester | 1 | Engineering |
| localization_engineer | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 52/100 (FAIL) — 1 iteration(s)

**Summary:** This plan is architecturally ambitious but contains one concrete technical error that will cause production rework (HealthKit OAuth2 PKCE does not exist), one hardware design contradiction that blocks firmware delivery (dual-MCU with single firmware target), and two major feature gaps that affect core product viability (offline mode for a habit app, no monetization implementation). The software-only portions of the plan (steps 1-11, 15-23) are well-structured with real database integration tests, proper security tooling, and a defensible tech stack. However, the wearable hardware workstream (steps 12-14) is underspecified, lacks certification timelines, and introduces firmware complexity that is disproportionate to an unvalidated consumer product. The plan also conflates MVP with full-product delivery — steps 12-23 represent 6+ months of additional work beyond a functional app. Scoring 52: the software foundation is sound but the HealthKit misconception is a concrete bug in the design, offline mode is a product-defining omission for a habit tracker, and the hardware workstream has blocking technical contradictions requiring rework before any fabrication.

### Flaws Identified

1. HealthKit does NOT use OAuth2 PKCE. HealthKit uses HKHealthStore.requestAuthorization() — a native iOS permission dialog with no callback URL or authorization code. The plan documents 'Health sync OAuth2 PKCE callback flow for HealthKit' (steps 5, 6, 11) which is architecturally wrong and will require rework across API design, backend, and security model.
2. Steps 12-13 introduce a dual-MCU design (STM32L476RG + nRF52840) but treat it as a single firmware target. These are two physically separate chips requiring separate firmware images, an inter-chip communication protocol (SPI or UART), and synchronized state machines. Step 12 only targets STM32L4 with Nordic SoftDevice — SoftDevice runs on nRF, not STM32. This is a fundamental hardware architecture contradiction.
3. Offline mode appears only in QA regression scope ('150 cases — all features, error states, offline mode') with zero implementation steps. A habit tracking app must work offline — users complete habits in planes, gyms, and subways. No local SQLite, no sync conflict resolution, no optimistic UI, no queue-and-sync pattern is specified anywhere in the build steps.
4. No monetization implementation exists. Step 1 analyzes pricing models; the PRD (step 2) mentions freemium vs subscription; but there is no implementation step for StoreKit 2 (iOS in-app purchases), Google Play Billing, subscription state management, paywall UI, entitlement checking, or receipt validation. A consumer app without a monetization implementation path cannot generate revenue.
5. Step 11 depends on Step 10 (SAGE agent config), meaning the core FastAPI backend cannot be built until AI agent YAML files are authored. This dependency is inverted — SAGE agents call the backend API, not the reverse. This blocks the critical path unnecessarily.
6. GDPR right to erasure is inconsistent: the legal step (7) states 'account deletion within 30 days' (async background job) but the E2E test (step 20) validates 'account deletion → verify data purged' immediately. The architecture needs a defined deletion model: soft-delete immediately, hard-delete by scheduled purge job within 30 days, with user-visible status.
7. No product analytics implementation. The north star metric is '30-day streak retention rate' but there is no Mixpanel, Amplitude, Firebase Analytics, or PostHog integration step. You cannot measure DAU, D7, D30, or streak retention without an event tracking pipeline. This makes the success metrics in the PRD unmeasurable.
8. FCC Part 15 + CE RED certification for BLE hardware is listed as 'planned' in the PCB step but has no corresponding implementation step, budget estimate, or timeline allocation. FCC certification alone takes 4-12 weeks and $15,000-$30,000 minimum. This is not a checkbox — it is a regulatory gate that blocks hardware shipping.
9. Step 20 system test load target (10,000 concurrent users, 1,000 RPS) has no corresponding EKS cluster sizing, RDS instance class specification, or Redis cache sizing. Running k6 at 1,000 RPS against an undersized cluster will produce meaningless results and false failures at test time.
10. The 'writing habit completions as mindful sessions' to HealthKit (step 15 acceptance criteria) is an architectural assumption that Apple may reject during App Store review. Apple scrutinizes HealthKit data type usage — writing habit completions as mindful sessions is a misuse of that category. This needs explicit validation against HealthKit developer guidelines before implementation.

### Suggestions

1. Replace 'Health sync OAuth2 PKCE flow for HealthKit' with 'HKHealthStore.requestAuthorization() permission flow' across steps 5, 6, 11, and 15. Health Connect (Android) does use OAuth2; keep that. Audit every acceptance criterion that mentions HealthKit OAuth.
2. Split the wearable into a separate product workstream or explicitly gate it behind a post-MVP milestone. Steps 12-14 add 4-6 months of specialized embedded work, certification overhead, and supply chain risk with zero validated demand. Ship the app first.
3. Add a dedicated OFFLINE step between steps 11 and 15: define the local-first data model (WatermelonDB or expo-sqlite), optimistic completion writes, background sync with conflict resolution (last-write-wins or server-authoritative), and connectivity state indicators in UI.
4. Add a MONETIZATION step after step 2: StoreKit 2 integration (iOS), Google Play Billing 5 (Android), RevenueCat as the abstraction layer, subscription entitlement checking middleware in the FastAPI backend, and paywall screen in the frontend.
5. Move Step 10 (SAGE config) out of the critical path for Step 11. SAGE agents should be configured against a running backend, not as a prerequisite for building it. Step 10 can depend on step 11.
6. Add a PUSH_INFRASTRUCTURE step between steps 9 and 11: Firebase project setup, APNs certificate provisioning, device token registration endpoint, token refresh strategy, notification category definitions for iOS (actionable notifications), and opted-out user handling.
7. Define the timezone strategy for streak calculation in the PRD (step 2) not just as a QA edge case (step 19). Decision: does 'today' mean user local midnight or UTC midnight? What happens on DST transitions? What happens when a user changes their device timezone mid-streak? This is a data model decision, not a test case.
8. Add a CONTENT_MODERATION step for social features: abuse reporting endpoint, automated toxicity screening (Perspective API or equivalent), moderator review queue, and ban/mute mechanics. Social UGC without moderation creates platform liability.
9. Replace EKS with ECS Fargate for the initial deployment. EKS adds Kubernetes operational overhead (node groups, cluster autoscaler, control plane management) that is disproportionate for an unproven consumer app. Migrate to EKS when sustained load justifies it.
10. Add an APP_STORE_READINESS step before DevOps (step 16): App Store Connect setup, privacy nutrition labels, HealthKit usage justification strings, App Review information, TestFlight external test group creation, and Play Console setup with Health Connect permissions declaration.

### Missing Elements

1. Offline-first architecture and sync conflict resolution — not mentioned in any implementation step
2. In-app purchase / subscription implementation (StoreKit 2, Google Play Billing, RevenueCat)
3. Product analytics event tracking pipeline (required to measure the north star metric)
4. Push notification infrastructure setup (Firebase, APNs certificates, token lifecycle)
5. nRF52840 firmware specification — the BLE SoC has no firmware plan despite being on the PCB schematic
6. Inter-chip communication protocol between STM32L4 and nRF52840 (SPI/UART framing, command set)
7. FCC/CE certification workstream with timeline and cost estimate
8. App Store Connect and Google Play Console setup and submission workflow
9. Streak timezone strategy — a business logic decision missing from the PRD
10. Social content moderation system (reporting, review queue, enforcement)
11. Data export feature (GDPR Article 20 portability — mentioned legally but not implemented)
12. Database zero-downtime migration strategy for live production schema changes
13. Rate limiting implementation location (API gateway vs. application layer vs. Redis)
14. Background fetch / background app refresh entitlements for iOS reminder reliability

### Security Risks

1. HealthKit data written to push notification payloads or analytics events would violate HealthKit guidelines and potentially GDPR. Step 8 mentions 'health data never stored in cleartext logs or analytics events' as a compliance criterion but no enforcement mechanism (log scrubbing, PII filtering middleware) is specified in the implementation steps.
2. Group invitation codes: the plan specifies secrets.token_urlsafe (correct) but does not specify code expiry, single-use enforcement, or rate limiting on the join endpoint. A non-expiring group code is a permanent membership escalation vector.
3. JWT RS256 private key storage: Secrets Manager rotation is mentioned for DB credentials and JWT signing keys (step 9) but key rotation for RS256 requires coordinated key rollover — existing valid tokens must remain verifiable during rotation. No key versioning or rotation strategy is specified, risking authentication outages on key rotation.
4. Health OAuth tokens (Health Connect) stored encrypted at column level — but the encryption key management is unspecified beyond 'AES-256'. Who holds the key? Is it in Secrets Manager? Is it per-user or global? A global encryption key means a single key compromise decrypts all health tokens.
5. Social group posts (UGC) with no input length limits or content-type restrictions in the API spec create a stored XSS and database bloat risk. The OpenAPI spec step (5) does not mention max payload sizes for group_posts.
6. APNs device tokens stored in the database — if the users table is exfiltrated, attackers can send arbitrary push notifications to all users (push phishing). Device tokens should be stored in a separate table with restricted access, not inline in user records.
7. Refresh token rotation without concurrent session invalidation: if the plan allows multiple active refresh tokens (common for multi-device use), a stolen refresh token remains valid until it is used. The acceptance criteria mention 'concurrent session limit' in tests but the implementation step does not define the session model.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.334925
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

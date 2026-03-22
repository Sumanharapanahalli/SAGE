# Regulatory Compliance — Social Fitness

**Domain:** consumer_app
**Solution ID:** 081
**Generated:** 2026-03-22T11:53:39.332505
**HITL Level:** standard

---

## 1. Applicable Standards

- **GDPR**
- **CCPA**
- **Apple/Google Health Data Policies**

## 2. Domain Detection Results

- consumer_app (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 16 | EMBEDDED_TEST | Write HIL (Hardware-in-the-Loop) test specs for the BLE health bridge firmware a | Hardware-in-the-loop verification |
| Step 17 | SECURITY | Perform a security review covering: threat model (STRIDE), OWASP Mobile Top 10 a | Threat modeling, penetration testing |
| Step 19 | QA | Design the QA test plan: test case library covering workout logging, challenge m | Verification & validation |
| Step 22 | SYSTEM_TEST | Execute full end-to-end system tests across the integrated stack: user onboardin | End-to-end validation, performance |
| Step 23 | LEGAL | Draft Terms of Service, Privacy Policy (GDPR + CCPA compliant), trainer marketpl | Privacy, licensing, contracts |

**Total tasks:** 25 | **Compliance tasks:** 5 | **Coverage:** 20%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 2 | CCPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | Apple/Google Health Data Policies compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| marketing_strategist | 1 | Operations |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| firmware_engineer | 1 | Engineering |
| localization_engineer | 1 | Engineering |
| devops_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| legal_advisor | 1 | Compliance |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 58/100 (FAIL) — 1 iteration(s)

**Summary:** This plan is impressively broad — 25 steps covering market research through docs, with serious acceptance criteria and a realistic dependency graph. The core backend architecture (FastAPI, PostgreSQL, Redis sorted sets for leaderboards, Stripe Connect, Celery) is sound. However, there are three critical technical conflicts that will cause costly rework: (1) Expo managed workflow cannot host the custom Swift/Kotlin BLE native modules the plan requires — this forces an architectural pivot on the mobile side before a single screen is built; (2) HealthKit background delivery fundamentally does not work with a server-side Celery poller — the entire health sync architecture for iOS is wrong; and (3) the badge device plan has a missing firmware implementation step between PCB design and HIL testing. Beyond these blockers, the plan omits push notifications entirely (a core UX requirement for a social app), never builds the admin panel it references, and has no content moderation for a UGC platform — both of which will cause App Store rejection. The trainer marketplace has underestimated legal and tax compliance surface area. Score: 58. Fix the Expo/BLE conflict and the missing firmware step first — these are load-bearing; everything else is recoverable.

### Flaws Identified

1. CRITICAL — Expo managed workflow (Step 14) is fundamentally incompatible with custom native BLE modules (Step 8). Expo managed workflow sandboxes native code and does not allow Swift/Kotlin native modules without ejecting to bare workflow or using a custom dev client via EAS Build. This conflict will force a painful mid-build eject that invalidates the Expo managed workflow assumption across all 12 screens.
2. Google Fit REST API is being sunset by Google in favor of Health Connect exclusively. Step 13 lists both 'Google Fit REST API + Health Connect SDK' as if they are parallel options, but Google Fit REST API access for fitness data from Android devices is deprecated. Building against it now means rework before launch.
3. No badge firmware implementation step exists. Step 15 designs the PCB; Step 16 tests the firmware. The actual Zephyr/nRF SDK firmware for the nRF52840 — BLE advertising, GATT server, step counting interrupt handler, power management — is never written. The dependency chain 15→16 skips the most critical artifact.
4. Auth0 + custom JWT refresh (Step 9) is an anti-pattern. Auth0 already provides PKCE + refresh token rotation. Layering a custom JWT refresh on top creates two divergent token lifecycles, complicates revocation, and is a security surface. Choose one or the other.
5. HealthKit background delivery does not work with a Celery beat poller (Step 13). iOS enforces strict background execution rules. HKObserverQuery background delivery is push-based from HealthKit to the app; the app cannot poll Apple Health from a backend scheduler. The '15 min Celery beat' approach will silently fail on iOS and Apple will reject the app if HealthKit entitlements are misconfigured.
6. The social feed fan-out problem (Step 9) is trivialized to one line: 'chronological + engagement-weighted for followed users.' At even modest scale (10k users, 1000 follows each), fan-out on write generates millions of feed insertions per workout post. No fan-out strategy, no cutoff threshold for high-follower users, no mention of feed rebuild jobs. This is a known distributed systems scaling cliff.
7. SSE long-lived connections (Steps 10, 14) will be silently killed by AWS ALB's default 60-second idle timeout. ECS Fargate behind ALB will drop SSE connections every 60 seconds unless the ALB idle timeout is explicitly raised and heartbeat frames are sent. This is not mentioned anywhere, and the acceptance criterion 'SSE stream reconnects automatically on client disconnect' treats the symptom rather than the cause.
8. Step 3 requires 5 user interviews and a usability test with 3 participants. In an agent-driven autonomous build pipeline, there are no real participants. This step cannot be completed autonomously and creates a blocking dependency for all subsequent UX-dependent work (Step 14 depends on Step 3).
9. Trainer independent contractor classification (Step 23) is treated as a document-drafting exercise. In California (AB5), New York, and UK employment law, a platform that sets pricing, controls bookings, and takes commission may be reclassifying trainers as employees regardless of what the contract says. This is a business model risk, not just a legal drafting task — and it is not flagged.

### Suggestions

1. Replace Expo managed workflow with Expo bare workflow or React Native CLI from the start. Document the EAS Build custom dev client setup in Step 6. This is not a minor configuration change — it affects the entire mobile build pipeline.
2. Remove Google Fit REST API references entirely. Target Health Connect (Android 9+) and document the minimum SDK version (API 26 minimum, Health Connect requires Android 9). Add a graceful degradation path for devices below API 28.
3. Add a Step 15.5: EMBEDDED_FIRMWARE — implement the nRF52840 firmware in Zephyr RTOS: BLE advertising (iBeacon/Eddystone), GATT HR server stub, ADXL362 SPI driver, step counter ISR, power management (System OFF between advertising intervals). This is ~2 weeks of work that is simply missing.
4. Consolidate auth to Auth0 fully (PKCE on mobile, machine-to-machine for service tokens). Remove the 'custom JWT refresh' from Step 9. Auth0's refresh token rotation already handles this. If cost is a concern, switch to Supabase Auth or Keycloak.
5. Replace the Celery beat HealthKit poller with proper HealthKit background delivery: HKObserverQuery registered in the mobile app, which calls setBackgroundDeliveryEnabled, which wakes the app to trigger a backend sync. The backend records the push; it does not poll Apple.
6. Add Step 9.5: Push Notifications Infrastructure — FCM (Android) + APNs (iOS) via Expo Notifications (if bare workflow) or a service like OneSignal. Challenge invites, booking confirmations, workout reactions, and leaderboard overtakes all require push. This is a complete omission.
7. Add Step 11.5 or extend Step 21 to build the web-admin panel. The monorepo includes web-admin/ but no step builds it. Trainer verification queue, dispute resolution, payout override, and content moderation all need an admin UI. Right now there is just an undocumented 'admin review endpoint.'
8. Add content moderation to Step 9 or as a standalone step. Workout media uploads (photos, video clips) require at minimum CSAM hash-matching (PhotoDNA or AWS Rekognition) before S3 storage. Missing this will cause App Store rejection and potential legal liability.
9. Add 1099-K / tax reporting to Step 23. US trainers earning >$600 annually trigger IRS reporting requirements via Stripe's 1099-K. Stripe Connect handles generation but the platform must collect W-9 during onboarding and store TINs. This is a compliance obligation, not optional.
10. Move load testing earlier — add a performance checkpoint at Step 13 (after all backend services exist but before mobile is built). Discovering that the feed or leaderboard cannot handle 500 users at Step 22 means rearchitecting already-deployed services.

### Missing Elements

1. Push notification service (FCM + APNs) — completely absent from the plan. Required for challenge invites, booking confirmations, leaderboard overtakes, and trainer messages.
2. Admin panel build step — web-admin/ is in the monorepo but never implemented. Trainer verification, content moderation review, payout dispute resolution, and user bans all require this.
3. Badge firmware implementation step — the embedded C/Zephyr code for the nRF52840 is never written. PCB is designed (Step 15), tests written (Step 16), but the firmware itself is missing.
4. Content moderation pipeline — no CSAM detection, no inappropriate image filtering, no report/flag mechanism for workout posts. This is a legal and App Store requirement for UGC platforms.
5. Anti-cheat / data validation layer — users can submit arbitrary workout data or manipulate health sync payloads. No server-side plausibility checks (e.g., 500 km run in 1 hour), no rate limiting on workout submissions.
6. Real-time messaging or notification inbox — trainer ↔ user communication before/after sessions is implied by the booking flow but never designed or built.
7. Tax / 1099-K compliance for trainer payouts — W-9 collection during Stripe Connect onboarding, IRS threshold monitoring, annual 1099-K generation.
8. App Store review strategy — Apple's health data review is strict and slow (2-4 week review times common for HealthKit apps). No contingency for rejection, no TestFlight beta plan, no review preparation checklist.
9. Exercise library data source — Step 9 validates 'exercise library references' but no step populates the exercise library. Where do the 500+ exercises come from? CRUD admin tool? Seed migration? Third-party API?
10. Rate limiting implementation — Step 5 documents rate limit headers but no step actually implements rate limiting middleware (e.g., slowapi, Redis token bucket). Documentation without enforcement is not a control.

### Security Risks

1. Health data is PHI-adjacent. AES-256 at rest is mentioned (Step 17) but the key management strategy is absent. Who holds the KMS keys? Are they rotated? Is there envelope encryption per-user or per-table? A single compromised key should not expose all users' biometric data.
2. Stripe webhook signature validation is listed as an acceptance criterion (Step 17) but the implementation is in Step 11's backend with no explicit code review gate. If a developer bypasses signature validation 'temporarily' during development, it stays in. This should be a test that fails CI if the Stripe-Signature header is not validated.
3. Trainer payout fraud: velocity limits are mentioned (Step 17) but there is no fraud scoring model, no manual review trigger for unusual payout patterns, and no mention of Stripe Radar rules. A compromised trainer account can drain funds up to the velocity limit before detection.
4. BLE GATT parsing (Step 8) with no input validation on raw byte payloads. Malformed GATT packets from a rogue BLE peripheral could trigger buffer misreads in the native module. The acceptance criteria test only Heart Rate Service encoding variants — not adversarial payloads.
5. S3 pre-signed URL validation (Step 9): 'backend validates on completion' is vague. Without a server-side content type check and file size limit enforced on the S3 bucket policy (not just API-side), users can upload arbitrary files to S3 under workout media keys.
6. OAuth2 refresh token storage on mobile: if stored in AsyncStorage (React Native default), it is readable by any code running in the app context. Should use iOS Keychain / Android Keystore via Expo SecureStore. Not specified anywhere in Steps 8 or 14.
7. USDA FoodData Central API key (if using the authenticated endpoint for higher rate limits) and Open Food Facts are external dependencies. No credential rotation plan, no circuit breaker if these APIs are unavailable, no mention of whether the API key is in Secrets Manager or hardcoded.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.332543
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

# Regulatory Compliance — Language Learning

**Domain:** edtech
**Solution ID:** 074
**Generated:** 2026-03-22T11:53:39.329285
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
| Step 5 | COMPLIANCE | Produce compliance evidence artifacts for COPPA, FERPA, and WCAG 2.1. Document p | Standards mapping, DHF, traceability |
| Step 6 | LEGAL | Draft Terms of Service, Privacy Policy (COPPA-compliant with parental consent se | Privacy, licensing, contracts |
| Step 23 | SECURITY | Conduct security review: threat model for speech data and user PII, penetration  | Threat modeling, penetration testing |
| Step 25 | QA | Create QA test plan covering manual test cases for COPPA/FERPA compliance flows, | Verification & validation |
| Step 26 | SYSTEM_TEST | Execute end-to-end system test suite covering: full user journey (register → pla | End-to-end validation, performance |

**Total tasks:** 29 | **Compliance tasks:** 5 | **Coverage:** 17%

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
| developer | 15 | Engineering |
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
| devops_engineer | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This is an ambitious and structurally well-organized plan that demonstrates genuine product depth — the FSRS algorithm choice, coordinator agentic pattern, vector clock sync, and compliance awareness all reflect serious thinking. However, it has two critical failures that require rework before any implementation begins: (1) the COPPA parental consent mechanism is legally invalid — email verification will not satisfy FTC requirements, exposing the company to significant penalties; and (2) there is no content creation pipeline, meaning the entire technical stack will have nothing to teach when it launches. Beyond these blockers, several technical assumptions are incorrect (MFA for real-time pronunciation, Whisper base WER targets for Arabic/Mandarin, per-language Whisper model sizing, Expo managed workflow + on-device ML compatibility), and major product components are entirely absent (payments, push notifications, CMS, app store child-directed registration). The plan scores 54: the architecture is sound enough to build from, but the compliance flaw is a launch-blocking legal risk, the missing content pipeline is a fundamental product gap, and roughly 6-8 steps need to be added before this plan reflects what it would actually take to ship.

### Flaws Identified

1. CRITICAL: Email verification does NOT constitute 'verifiable parental consent' under COPPA. The FTC explicitly requires methods such as a signed consent form, credit card micro-charge, knowledge-based authentication, or government ID. An email flow will fail FTC review and expose the company to civil penalties up to $51,744 per violation. This invalidates Step 10's core auth implementation.
2. CRITICAL: Zero content creation pipeline. The plan builds a sophisticated engine with no mechanism to produce the actual learning content — vocabulary decks, professionally-recorded native speaker audio, lesson sequences, cultural context data. This is typically 40-60% of the cost and timeline for a language learning product. No CMS, no content ingestion pipeline, no editorial workflow.
3. Montreal Forced Aligner is a batch research tool, not a real-time scoring engine. MFA requires dictionary lookups and G2P models per language, processes audio in sequential steps (not pipelined), and has limited phoneme dictionaries for Arabic and Japanese. The '< 3 seconds server-side' target is not achievable with MFA for all 6 languages, particularly for Arabic.
4. Whisper base is a single multilingual model (~140MB), not a per-language model. Stating '~150MB per language' is a fundamental misunderstanding of the architecture. The storage estimate for offline is incorrect, and the download manager UI (Step 21) will show wrong sizes. More critically, Whisper base's WER on Arabic is ~15-25% — the '< 5% WER for all 6 target languages' acceptance criterion is unachievable with the base model.
5. On-device Whisper in a React Native/Expo managed workflow requires native modules (llama.cpp bindings or similar). This creates a hard conflict with Expo managed workflow — bare workflow is required, which significantly increases CI/CD complexity (EAS Build custom native modules, platform-specific builds). Step 7 picks React Native + Expo without resolving this tension.
6. FSRS without per-user parameter optimization is significantly less effective than advertised. The real value of FSRS-4.5 over SM-2 is per-user weight optimization from review history. The plan uses global default parameters, which degrades to near SM-2 quality for new users and never personalizes. No mention of the FSRS optimizer running on user review history.
7. Coordinator pattern with 4 sequential specialist agent calls will routinely exceed the 4-second response target. Each LLM call is 1-3 seconds at production load. GrammarCoach + VocabularyCoach + synthesis alone hits the ceiling, before adding PronunciationCoach context lookup and CulturalContextAgent retrieval.
8. Offline pronunciation scoring is deferred to sync (Step 18) but Step 26 requires 'pronunciation drill score and retry' as a passing E2E journey. These are contradictory: the user gets no phoneme feedback offline, breaking the core offline value proposition for pronunciation.
9. Vector clock conflict resolution for FSRS state (Step 15) is architecturally unsound. FSRS state is path-dependent — the stability value after rating 'Hard' on a card with stability=5 differs from replaying the same rating on server-updated state=7. 'Server-wins with local queue replay' will produce different scheduling than what the user experienced, causing phantom reviews and broken stability estimates.
10. No subscription/payment backend. The ROI model (Step 1) includes freemium and subscription scenarios, but no step implements in-app purchases (StoreKit for iOS, Google Play Billing), subscription state management, or paywall enforcement. In-app purchase integration with Apple/Google is a significant workload with compliance requirements of its own.
11. No push notification infrastructure. Daily reminder notifications are the single highest-impact retention mechanism for language learning apps (Duolingo's entire retention strategy depends on this). Absent from every step.
12. App Store child-directed designation is unaddressed. Apps targeting under-13 users must register under Apple's 'Made for Kids' category and Google Play's 'Designed for Families' program. These programs restrict third-party SDKs (no Facebook, many analytics), enforce COPPA-compliant data handling at the platform level, and require separate review. The CI/CD plan (Step 27) ignores this entirely.
13. No LLM cost model for conversational AI at scale. 4 specialist agents × average 500 tokens × cost per token × DAU × sessions/day = potentially $50K-$200K/month at modest scale. No discussion of cost controls, token budget per session, caching, or which LLM provider is used.

### Suggestions

1. Replace email-only parental consent with a compliant COPPA verification service (Veriff, PRIVO, or SuperAwesome) — these are purpose-built SDKs that handle the FTC's acceptable verification methods and stay current with regulatory changes. Budget 2-4 weeks for integration.
2. Add a Step 2.5 or Step 3.5 for content architecture: define the content data model, identify native speaker recording vendors (Voices.com, Speechify Studio, in-house studio), build a content ingestion pipeline, and plan the initial deck sizes per language. Without this, Steps 11, 17, and 18 have no data to work with.
3. Replace Montreal Forced Aligner with a purpose-built pronunciation assessment API for production (SpeechAce, Azure Pronunciation Assessment, or Google Speech-to-Text with word confidence scores). Use MFA only for offline/research evaluation. Revisit phoneme-level scoring architecture around these APIs' actual output formats.
4. Switch to Expo bare workflow immediately in Step 7 or accept the limitation that on-device Whisper will not be available in the MVP. Document this trade-off explicitly in an ADR. If bare workflow, plan for separate iOS/Android CI lanes with native dependency caching.
5. Add FSRS optimizer as a background job in Step 11: collect minimum 50 reviews per user, run parameter optimization weekly, store personalized weights per user. This is the core differentiator over SM-2 and should be in v1.0 not v2.0.
6. Cap the conversational AI response at 2 specialist agent calls per turn maximum (route to the most relevant specialist only, not all 4). Add a response streaming SSE endpoint so perceived latency is lower even if total generation time is 5-6 seconds.
7. Add Step 10.5: Payment/subscription service — StoreKit 2 (iOS) + Google Play Billing Library 5+ (Android), server-side receipt validation, subscription state webhook handlers, entitlement management. This blocks the freemium model entirely if absent.
8. Add Step 7.5: Push notification infrastructure — FCM + APNs integration, notification permission flow (critical for under-13: must be parent-consented), streak reminder scheduling, and unsubscribe management for GDPR compliance.
9. In the COPPA compliance step (Step 5), add explicit Apple MfK / Google DFF registration requirements and the SDK allow-list review — many analytics SDKs (Firebase Analytics, Mixpanel) are prohibited in child-directed contexts without special data processing agreements.
10. Add a content management system step between Steps 3 and 7: admin panel for deck management, content approval workflow, audio upload + normalization pipeline, and localization of lesson content (separate from app UI i18n in Step 22).

### Missing Elements

1. Content creation pipeline: vocabulary deck production, native speaker audio recording, lesson sequencing, and cultural content for 6 languages. This is the product's core asset and has no step.
2. In-app purchase and subscription management (StoreKit 2, Google Play Billing, server-side receipt validation, entitlement service).
3. Push notification infrastructure (FCM, APNs, permission flow, streak reminders, GDPR opt-out).
4. CMS / admin panel for content managers and educators to manage decks, lessons, and student accounts.
5. Analytics product instrumentation (event schema, Amplitude/Mixpanel integration, funnel analysis setup) — CloudWatch alone is insufficient for product decisions.
6. LLM provider selection and cost model for conversational AI: which model, what token limits per session, cost per conversation turn, monthly budget ceiling.
7. App Store submission requirements for child-directed apps: Apple Made for Kids category, Google Designed for Families program, SDK restrictions imposed by each.
8. GDPR data portability export format — what file format, which fields, delivery mechanism (email, in-app download), and SLA.
9. Whisper model language-specific performance benchmarks BEFORE committing to the < 5% WER target. Arabic and Mandarin with the base model will fail this criterion.
10. Customer support tooling and COPPA data deletion request intake — the runbook in Step 29 mentions a 45-day SLA but there's no support ticket system or intake form planned.
11. FSRS per-user parameter optimization job — a core differentiator entirely absent from the algorithm implementation.
12. Pronunciation reference audio recording plan — who records native speaker audio for thousands of vocabulary items across 6 languages, at what quality (studio vs. crowdsourced), at what cost.

### Security Risks

1. Children's speech recordings stored in S3 without explicit field-level access controls. S3 bucket policy + presigned URL expiry is insufficient if object keys are guessable (e.g., user_id/recording_id). COPPA violation risk: unauthorized access to minor's voice recordings. Require envelope encryption per recording with per-user KMS keys.
2. JWT storage in React Native: AsyncStorage is unencrypted and accessible to any JS code in the app. Refresh tokens in AsyncStorage are exfiltrable by XSS equivalents in WebView components or compromised native modules. Use iOS Keychain / Android Keystore via react-native-keychain for all token storage.
3. Offline XP manipulation window: XP events accumulated offline are replayed on sync with only 'server-side validation' as protection. An attacker can manipulate the local SQLite database (especially without SQLCipher, which is only mentioned for review, not guaranteed in implementation) to inject arbitrary XP events. Server must independently recompute achievable XP from session metadata, not trust client-reported values.
4. Parental consent endpoint (POST /auth/parental-consent) has no brute-force protection mentioned beyond general rate limiting. An attacker enumerating pending consent tokens (UUID-based or timestamp-predictable) could activate under-13 accounts without genuine parental action. Add HMAC-signed tokens with expiry and one-time use enforcement.
5. IDOR on speech recordings: POST /speech/evaluate and related endpoints must enforce that the requesting user_id matches the recording owner. The threat model lists this but the API spec (Step 9) has no explicit ownership enforcement requirement on the speech endpoints — it must be in the auth middleware, not assumed.
6. SBOM scan in CI without a remediation SLA. Generating a CycloneDX SBOM is listed as an acceptance criterion but there is no policy for what happens when a critical CVE is found — does the build block? Who is notified? For a children's app with COPPA exposure, a critical CVE in a data-handling library must block deployment.
7. No mention of SQL injection protection at the ORM layer. 'Parameterized queries' is listed in Step 23 but not enforced in Step 10's implementation acceptance criteria. FastAPI + SQLAlchemy with raw text() queries is a common injection vector — must be explicitly prohibited in coding standards.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.329332
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

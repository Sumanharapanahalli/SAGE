# Regulatory Compliance — Travel Planner

**Domain:** consumer_app
**Solution ID:** 084
**Generated:** 2026-03-22T11:53:39.333345
**HITL Level:** standard

---

## 1. Applicable Standards

- **PCI DSS**
- **GDPR**
- **Package Travel Directive**
- **SOC 2**

## 2. Domain Detection Results

- consumer_app (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 15 | SECURITY | Perform security review of travel_planner: threat model for booking data (PII, p | Threat modeling, penetration testing |
| Step 16 | LEGAL | Draft Terms of Service, Privacy Policy, and cookie consent banner for travel_pla | Privacy, licensing, contracts |
| Step 19 | QA | Develop QA test plan and execute manual test cases for travel_planner: explorato | Verification & validation |
| Step 20 | SYSTEM_TEST | Execute end-to-end system tests for travel_planner's critical user journeys usin | End-to-end validation, performance |

**Total tasks:** 22 | **Compliance tasks:** 4 | **Coverage:** 18%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | PCI DSS compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |
| 2 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 3 | Package Travel Directive compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
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
| developer | 11 | Engineering |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| marketing_strategist | 1 | Operations |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| localization_engineer | 1 | Engineering |
| legal_advisor | 1 | Compliance |
| devops_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This is a thorough and well-structured plan that covers the full product lifecycle from market research to documentation, with credible dependency ordering and specific acceptance criteria. However, it has one fundamental hole that makes the core value proposition non-functional: there is no payment processing anywhere in 22 steps. Itinerary generation + booking search is a free feature; actual booking requires charging money, and this is completely absent. Compounding this, the two named booking providers (Amadeus, Booking.com) require commercial agreements that are non-trivial to obtain — the plan treats them as technical integrations when they are business partnerships. The mobile vs. web ambiguity (app store mockups, offline maps, but React web stack) will cause rework when stakeholders realize the PWA cannot match native offline map UX. The offline tile storage architecture (local filesystem, S3 optional) will fail at multi-worker scale without a mandatory shared object store. Group concurrency is untested at the database level — eight simultaneous editors on unversioned rows will corrupt data silently. These are not polish issues; they require architectural decisions before backend implementation begins. Score 54: the plan's structure and research/design steps are solid, but the backend implementation steps (7–11) are building on unresolved foundations. Resolve payment processing, booking API access strategy, and mobile/web platform decision before proceeding to Step 5.

### Flaws Identified

1. Payment processing is completely absent. Steps 8 describes 'booking confirmation' but there is no Stripe/Braintree integration, no payment flow, no PCI DSS scope. You cannot book a flight or hotel without charging a card. This is not a minor gap — the entire booking feature is non-functional without it.
2. Booking.com's Connectivity API is restricted to licensed travel agencies with commercial agreements. It is not a self-service API. Amadeus Self-Service has limited inventory and sandbox-only access without a commercial agreement. The plan treats both as simple REST adapters; obtaining production access to either could take months of business negotiation and is a potential project-killer.
3. The product description implies a mobile app ('offline maps', 'app store screenshot mockups' in Step 3). The entire implementation is React web + React Router — not React Native or Flutter. A PWA can approximate offline maps but cannot match native map tile caching on iOS/Android. This is a fundamental product/implementation mismatch that is never resolved.
4. Celery tile workers write to 'local filesystem + optional S3' (Step 11). In a multi-worker production environment, a tile downloaded by worker A is not accessible to worker B serving the tile endpoint. S3 must be mandatory, not optional. The 2GB LRU per-user cap on local filesystem does not scale beyond a single machine.
5. Real-time group notifications via WebSocket (Step 10) are never wired into infrastructure. Step 17 (DevOps) defines services as FastAPI + Postgres + Redis + Celery — no WebSocket connection manager, no sticky sessions, no pub/sub fan-out. This breaks group editing UX entirely in multi-worker deployments.
6. The 15-second SLA for 7-day itinerary generation (Step 7) is unrealistic. Three parallel LLM calls (each 5–15s p50 on current models) plus coordinator overhead, SSE handshake, and DB persistence will routinely exceed 15s. There is no fallback or revised UX contract when this SLA is breached.
7. Group concurrency is untested at the schema level. Step 10 acceptance criteria require 'no data conflict' with 8 simultaneous editors, but the database schema (Step 5) has no optimistic locking fields (version/etag), no row-level locking strategy, and no CRDT approach. This will produce silent last-write-wins overwrites.
8. GDPR 'right to erasure' is mentioned in the Privacy Policy (Step 16) but the database schema has no soft-delete columns, no cascade delete strategy, no account deletion endpoint, and no data purge job. The legal document will promise a right the backend cannot honor.
9. The iterative refinement quality scorer (Step 14, threshold 0.85) uses LLM-as-judge with no calibration baseline. LLM quality scores are non-deterministic; the same itinerary can score 0.78 one run and 0.91 the next. There is no validation that the scorer is accurate, no human-labeled ground truth, and no metric to detect scorer drift.
10. Budget alerts (Step 9) are mentioned as acceptance criteria but there is no notification delivery system anywhere in the plan — no email service, no push notification infrastructure, no SMS. The alert fires into a void.
11. Mapbox bulk tile download for offline use likely violates Mapbox Terms of Service Section 3 (restrictions on bulk tile extraction). The plan acknowledges 'OSM fallback' but OSM tile servers also prohibit bulk downloads. Legal clearance for offline tile caching is not addressed in the Legal step (Step 16).
12. Single-use invite tokens (Step 15) conflict with the 48h expiry window (Step 10). If a user clicks the link, the request fails mid-flight (network drop), and they retry, the token is consumed and they are locked out. No retry-safe token invalidation strategy is defined.

### Suggestions

1. Add a dedicated payment step using Stripe with a defined PCI scope. Use Stripe's hosted payment page to stay out of PCI DSS SAQ D. Wire payment_intent_id to the flight_bookings and hotel_bookings tables. Define refund/cancellation flows explicitly.
2. Replace direct Booking.com/Amadeus integration in MVP with an aggregator that has accessible APIs — Duffel (flights, accessible self-service API with real inventory), HotelBeds, or Agoda Partner API. Document the partnership acquisition path as a project dependency, not a technical task.
3. Decide on web PWA vs native mobile and commit. If PWA: document its offline map limitations explicitly and use Workbox for service worker tile caching. If native: add React Native + Expo to the stack and replace Mapbox GL JS with react-native-maps or Mapbox React Native SDK.
4. Make S3 (or equivalent object store) mandatory for tile storage in Step 11. Add a shared Redis key namespace for tile metadata so any worker can serve any tile. Define the storage cost model per user at the expected scale.
5. Add a WebSocket connection manager (e.g., Redis pub/sub + FastAPI WebSocket) as an explicit infrastructure component in Step 17. Define which service owns connection state and how fan-out works across multiple FastAPI instances.
6. Replace the 15s itinerary SLA with a streaming progress contract: emit a 'planning started' SSE event immediately, stream partial results as each specialist agent completes, set a 60s hard timeout with a graceful truncation. Remove the wall-clock SLA from acceptance criteria.
7. Add version integer columns to itinerary_days, itinerary_items, and budget_items. Implement optimistic locking at the API layer: accept If-Match header, reject with 409 on version mismatch. This is the minimal viable concurrency control for group editing.
8. Add a /users/{id}/delete endpoint in Step 9 or a new GDPR Compliance step that cascades deletion across all tables, revokes tokens, and queues a deletion audit event. This must exist before any GDPR-scoped Privacy Policy is published.
9. Calibrate the quality scorer in Step 14 with at least 20 human-labeled itinerary examples before setting a hard threshold. Use a confidence interval, not a point estimate. Log raw dimension scores to audit_log.db so scorer drift is detectable.
10. Add a notification service step (or subsystem within Step 9/10): choose SendGrid for email, Firebase Cloud Messaging for push. Define the notification contract (event types, payload schema, user preferences) before wiring alert triggers.
11. Add a Legal review of Mapbox and OSM offline tile terms to Step 16. If offline caching is prohibited, the entire Step 11 must pivot to a licensed offline map provider (e.g., Maps.me data, HERE Maps offline SDK) or be descoped to Phase 2.

### Missing Elements

1. Payment processing and PCI DSS scope definition — the most critical missing element
2. Booking API commercial access acquisition plan — this is a business dependency, not a code task
3. Account deletion and GDPR erasure implementation (endpoint + cascade delete + purge job)
4. Notification delivery infrastructure (email + push) for budget alerts and group events
5. Optimistic locking / concurrency control strategy for collaborative group editing
6. Offline map tile licensing review and storage architecture decision (S3 mandatory, not optional)
7. WebSocket infrastructure design for real-time group collaboration
8. Mobile vs. web platform decision and corresponding build pipeline
9. Error compensation / saga pattern for partial booking failures (flight booked, hotel fails)
10. Quality scorer calibration and validation methodology for Step 14
11. Currency conversion failure handling and stale-rate fallback policy
12. Token retry-safety for invite link acceptance flow

### Security Risks

1. Passport numbers stored in the database (referenced in Step 16) require encryption at rest. The schema design (Step 5) specifies no column-level encryption or KMS integration. Storing plaintext passport numbers is a regulatory liability in GDPR/CCPA jurisdictions.
2. Payment tokens referenced as 'sensitive_data' in Step 15 but with no tokenization architecture. If Stripe is used, the raw card number should never reach the backend. If a custom payment flow is built (which this plan implies), it is PCI DSS in-scope and requires formal audit.
3. Group invite tokens with 48h expiry and no rate limiting on the accept endpoint enable enumeration attacks. Tokens should be 128-bit random, single-use with atomic compare-and-swap invalidation, and the accept endpoint should have its own rate limit separate from the general API limits.
4. Offline tile endpoints require auth (Step 15 correctly identifies this), but tile URLs at /maps/tiles/{z}/{x}/{y}.png follow a predictable pattern. Without signed URLs or short-lived session tokens on the tile endpoint, authenticated users can share tile URLs that remain accessible.
5. The WebSocket endpoint for group notifications (Step 10) is not in the security threat model (Step 15). WebSocket connections bypass standard HTTP middleware for auth; JWT validation must be explicit on the upgrade handshake, not assumed from the HTTP session.
6. Exchange Rate API (Step 9) is an external dependency with no mention of authentication or SSRF protection. If the API URL is configurable, this is an SSRF vector. If hardcoded, a compromised CDN/DNS cache can manipulate exchange rates.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.333379
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

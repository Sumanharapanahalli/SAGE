# Regulatory Compliance — Recipe App

**Domain:** consumer_app
**Solution ID:** 086
**Generated:** 2026-03-22T11:53:39.333893
**HITL Level:** standard

---

## 1. Applicable Standards

- **GDPR**
- **FDA Nutritional Label Guidelines**

## 2. Domain Detection Results

- consumer_app (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 16 | EMBEDDED_TEST | Write HIL test harness and firmware unit tests: BLE pairing sequence tests with  | Hardware-in-the-loop verification |
| Step 18 | QA | Develop QA test plan: define test scope, risk-based test prioritization for nutr | Verification & validation |
| Step 20 | SECURITY | Perform security review: STRIDE threat model for auth, ingredient data ingestion | Threat modeling, penetration testing |
| Step 21 | LEGAL | Draft Terms of Service, Privacy Policy, data retention policy, and cookie policy | Privacy, licensing, contracts |

**Total tasks:** 23 | **Compliance tasks:** 4 | **Coverage:** 17%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 2 | FDA Nutritional Label Guidelines compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| marketing_strategist | 1 | Operations |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| firmware_engineer | 1 | Engineering |
| localization_engineer | 1 | Engineering |
| legal_advisor | 1 | Compliance |
| technical_writer | 1 | Operations |
| devops_engineer | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 47/100 (FAIL) — 1 iteration(s)

**Summary:** This plan is structurally coherent for a web-based recipe app but contains two categories of problems that push the score well below acceptable for a production launch. First, a critical missing piece: there is no authentication implementation step anywhere in 23 steps — JWT appears in the API design as a contract annotation and in the security review as a checklist item, but the actual auth system (registration, login, session management, token lifecycle) has no owner, no step, and no acceptance criteria. Shipping without this is not an MVP gap, it is a non-starter. Second, the plan buries a fully separate hardware product (e-ink display, BLE firmware, SystemC simulation, PCB fabrication) inside a recipe app roadmap. This is not scope creep — it is a different project entirely, with a 6–12 month hardware lifecycle that has no relationship to the web app's delivery timeline. Remove steps 13–16 entirely or isolate them as a post-v1 hardware initiative. The remaining flaws — dead Firebase dependency, background timer impossibility in mobile web, inverted API/DB dependency, missing ingredient ontology, missing content moderation, and UGC copyright exposure — are individually fixable, but collectively they represent a plan that has not been walked through from a shipping perspective. Fundamental rework on auth, hardware scoping, and the Firebase replacement is required before this plan should be executed.

### Flaws Identified

1. Firebase Dynamic Links (step 8) was deprecated August 2023 and shut down August 2025. Any deep-link implementation using it will fail at runtime. No replacement (Branch.io, App Links, Universal Links) is named.
2. No dedicated authentication implementation step exists anywhere in the 23-step plan. JWT is mentioned in the API design step as a contract detail, but registration, login, OAuth social sign-in, password reset, and session invalidation have no implementation owner or acceptance criteria.
3. Steps 13–16 (firmware, SystemC power simulation, PCB design, HIL test harness) are a completely separate hardware product embedded inside a recipe app MVP. This quadruples scope and introduces a 6–12 month hardware procurement and fab cycle that has no dependency on any user-facing software milestone.
4. API design (step 5) depends on database schema (step 4), but the correct dependency is the reverse — the API contract should drive schema decisions. Reversing this order means you will discover schema incompatibilities only after the DB migration tooling is already in place, forcing costly rework.
5. Web Speech API (step 11) is not available on iOS Safari in any reliable form and requires network access in Chrome. Cooking mode voice navigation will silently not work for a significant portion of mobile users. No fallback (button-only mode, native speech SDK for a native app) is specified.
6. Background timer reliability in a web app (step 11 acceptance criteria: 'works with screen backgrounded') is not achievable without a Service Worker + Push Notification or a native app wrapper. Browser tabs are throttled or suspended by every major mobile OS. This acceptance criterion cannot pass in a pure web context.
7. PCB design (step 15) is assigned to the 'developer' agent role. PCB layout, antenna keep-out zone tuning, and DRC rule compliance require EE-specific skills that a software developer agent cannot supply. This is a role mismatch that will produce unmanufacturable boards.
8. The hardware dependency chain is inverted: step 14 (SystemC simulation) and step 15 (PCB design) both depend on step 13 (firmware). In practice, PCB design must precede firmware bring-up, not follow it — you cannot write BLE drivers before you have a board with a BLE radio on it.
9. 500 recipes with 'full nutritional data' in the seed script (step 4) — no source is named. LLM-generated nutritional data would be legally and medically dangerous (incorrect calorie/macro values). USDA-sourced seed data requires bulk download and transformation tooling that is never planned.
10. Ingredient unit normalization (step 7, 2% accuracy target) ignores the long tail of non-SI cooking units: 'a pinch', 'to taste', 'one bunch', 'a handful', 'a can'. No handling strategy is defined, and real recipes use these constantly. The deduplication logic will silently drop or miscount these items.

### Suggestions

1. Replace Firebase Dynamic Links with Android App Links (Digital Asset Links JSON) + Apple Universal Links. Both are free, standards-based, and not deprecated. Wire them in step 8 with a /.well-known/ static file served from the FastAPI app.
2. Add a dedicated AUTH step between steps 5 and 6: implement JWT issuance, httpOnly refresh token cookie (not localStorage — XSS safe), /auth/register, /auth/login, /auth/logout, /auth/refresh, and optional OAuth2 (Google) for social login. This is the most critical missing step.
3. Scope-gate the hardware work (steps 13–16) as a v3 milestone, not a dependency of cooking mode. The mobile cooking mode (step 11) and e-ink companion device are independent products. The app ships without the device. Build the BLE integration as an optional progressive enhancement post-launch.
4. Reverse the step 4/5 dependency: design the OpenAPI contract first (step 4), then derive the PostgreSQL schema (step 5). Use the contract as the source of truth and generate Pydantic models from it. This catches impedance mismatches before migrations are written.
5. Replace Web Speech API with a graceful-degradation strategy: use the API where available (Chrome desktop, Chrome Android) and fall back to visible tap targets. Document this explicitly in the cooking mode acceptance criteria. For a production app, evaluate Capacitor or React Native for reliable native speech access.
6. Add a USDA bulk nutritional data import step. Download the USDA FoodData Central SR Legacy JSON dump (public domain, ~350MB), write an ETL into the nutritional_facts table, and use the live API only for lookup of items not in the local cache. This eliminates rate limit exposure and makes nutritional data available offline.
7. Add an ingredient ontology or synonym table to the database schema. 'Scallion', 'green onion', and 'spring onion' are the same ingredient. pg_trgm trigram search will not unify these without explicit synonym expansion. Model this in the schema and wire it into the search layer in step 6.
8. Add image content moderation to the photo upload pipeline (step 8). S3 presigned URL uploads bypass your server entirely — add an S3 event trigger to invoke AWS Rekognition (or equivalent) for NSFW/CSAM detection before the image is made publicly visible. This is a legal requirement for any UGC platform.
9. Define the mobile delivery target explicitly before step 10: PWA, React Native, Capacitor, or separate iOS/Android codebases. This decision affects steps 10, 11, 12, 17, and 22. A PWA cannot reliably receive background push notifications on iOS, cannot run background timers, and cannot access native share sheets without polyfills.

### Missing Elements

1. Authentication and session management implementation — JWT issuance, refresh rotation, logout/revocation, and social OAuth are completely absent as a buildable step.
2. USDA FoodData Central API rate limit strategy — the free tier is 3,600 requests/hour. At 500 RPS load test volume, the live API will be exhausted in seconds. No bulk import, quota management, or fallback nutrition database (Open Food Facts) is planned.
3. Content moderation pipeline for UGC — recipe posts, user-submitted photos, and community recipe submissions have no moderation layer (automated or human). Launching without this exposes the platform to CSAM, spam, and brand risk.
4. Mobile app delivery decision — the plan builds a React web app but references iOS/Android deep links, app store screenshots, and backgrounded session resume. The gap between 'web app' and 'app store app' is never resolved.
5. Token storage security decision — JWT tokens stored in localStorage are XSS-vulnerable. httpOnly cookie strategy vs localStorage is a security-critical choice that must be made before step 6, not discovered during the security review in step 20.
6. Right-to-erasure cascade — step 21 maps GDPR erasure to DELETE /users/{id} but does not address cascading deletion of social posts, likes, follows, saved recipes, pantry entries, and grocery list history. Partial erasure is an Article 17 GDPR violation.
7. Offline support strategy for cooking mode — a user mid-recipe in a kitchen with poor Wi-Fi cannot have cooking mode fail. Service Worker caching for the active recipe is never mentioned.
8. Ingredient taxonomy / synonym normalization data model — 'tomato', 'roma tomato', 'cherry tomato', 'tinned tomatoes' are distinct ingredients in some recipes and interchangeable in others. No ontology or synonym resolution layer is planned.
9. Recipe content attribution and copyright — the 500 seed recipes need a clear license (user-submitted, CC-licensed, USDA, public domain). Seeding with scraped or LLM-generated recipes creates copyright and accuracy liability.
10. Social feed scalability model — no fan-out strategy (write-time fan-out vs read-time fan-out) is specified. For users with 10,000 followers, write-time fan-out will cause post creation to block. This needs a design decision before step 8 is implemented.

### Security Risks

1. Photo uploads via S3 presigned URLs (step 8/12) bypass all server-side validation. A malicious actor can upload arbitrary file types by forging the Content-Type header. MIME type sniffing must happen server-side on S3 via Lambda trigger or post-upload validation — not just in the browser client.
2. JWT tokens stored implicitly (localStorage assumed) are exfiltrable via XSS. The social content injection surface (recipe posts, step 20 mitigates with bleach) means a successful stored XSS attack would harvest all auth tokens. Require httpOnly cookies for refresh tokens and short-lived memory-only access tokens.
3. IDOR on grocery lists — step 20 lists this as a known risk but the mitigation is not specified beyond 'OWASP Top 10 checklist'. Grocery list endpoints must enforce that the authenticated user owns the list on every read/write/delete operation. This must be a first-class implementation requirement in step 6, not an afterthought in step 20.
4. Ingredient search input is a PostgreSQL FTS query path. Even with SQLAlchemy ORM, complex tsvector/tsquery construction with user input requires explicit sanitization. FTS injection (crafting tsquery syntax to cause query plan denial of service) is not covered by standard parameterized query protection.
5. LLM-generated ingredient substitution suggestions (step 7) could recommend allergen substitutions that are medically dangerous (e.g., suggesting almond flour as a 'gluten-free' substitute for someone with tree nut allergy). No disclaimer, no allergen cross-check, and no liability boundary is defined.
6. OTA firmware update endpoint (step 13) has no authentication model defined. An unauthenticated or weakly authenticated /ota/firmware endpoint on a public backend is a remote code execution surface for the companion device. Firmware signing (Ed25519 or similar) must be in the acceptance criteria, not just hash verification of an unsigned payload.
7. Social sharing deep links contain recipe content. An attacker who crafts a malicious deep link URL could exploit open redirect vulnerabilities in the link resolution layer if URL parsing is not strict. Firebase Dynamic Links (now dead) had this mitigated — the replacement must explicitly address open redirect.
8. The SBOM (step 20, syft) is generated but there is no vulnerability scanning step (Trivy, Grype, or Dependabot). Generating a SBOM without acting on it provides compliance theater, not actual supply chain security. Add a CI gate that fails on critical CVEs in the SBOM.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.333925
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

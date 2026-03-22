# Regulatory Compliance — Mental Health Chatbot

**Domain:** medtech
**Solution ID:** 010
**Generated:** 2026-03-22T11:53:39.309609
**HITL Level:** strict

---

## 1. Applicable Standards

- **HIPAA**
- **SOC 2**
- **WCAG 2.1**

## 2. Domain Detection Results

- medtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 3 | LEGAL | Draft terms of service, privacy policy, disclaimer language, and data processing | Privacy, licensing, contracts |
| Step 4 | REGULATORY | Map product to FTC wellness app guidance, SAMHSA safe messaging rules, Apple/Goo | Submission preparation, audit readiness |
| Step 5 | SAFETY | Perform hazard analysis and risk assessment for crisis detection failures, false | Risk management, FMEA, hazard analysis |
| Step 6 | COMPLIANCE | Produce HIPAA/HITECH compliance artifacts: risk analysis, workforce training pla | Standards mapping, DHF, traceability |
| Step 7 | SECURITY | Produce threat model (STRIDE), penetration test plan, SBOM, encryption-at-rest/i | Threat modeling, penetration testing |
| Step 18 | QA | Develop QA test plan covering functional, regression, accessibility, safe messag | Verification & validation |
| Step 19 | SYSTEM_TEST | Execute end-to-end system integration tests covering the full user journey from  | End-to-end validation, performance |
| Step 23 | SECURITY | Execute security review: penetration test against staging environment focusing o | Threat modeling, penetration testing |

**Total tasks:** 23 | **Compliance tasks:** 8 | **Coverage:** 35%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | HIPAA compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 2 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | WCAG 2.1 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

## 5. Risk Assessment Summary

**Risk Level:** HIGH — Safety-critical domain requiring strict HITL gates

| Risk Category | Mitigation in Plan |
|--------------|-------------------|
| Patient/User Safety | SAFETY tasks with FMEA and hazard analysis |
| Data Integrity | DATABASE tasks with audit trail requirements |
| Cybersecurity | SECURITY tasks with threat modeling |
| Regulatory Non-compliance | REGULATORY + COMPLIANCE tasks |
| Software Defects | QA + SYSTEM_TEST + EMBEDDED_TEST tasks |

## 6. Agent Team Assignment

| Agent Role | Tasks Assigned | Team |
|-----------|---------------|------|
| developer | 5 | Engineering |
| regulatory_specialist | 4 | Compliance |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| marketing_strategist | 1 | Operations |
| legal_advisor | 1 | Compliance |
| safety_engineer | 1 | Compliance |
| ux_designer | 1 | Design |
| product_manager | 1 | Design |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 63/100 (FAIL) — 1 iteration(s)

**Summary:** This is a well-structured, thorough plan that correctly identifies the major risk domains — crisis detection, HIPAA, safe messaging, multi-agent safety guardrails, and penetration testing — and sequences them with reasonable dependencies. The regulatory and safety steps (1–7) are notably better than most AI product plans. However, the plan has three categories of critical gaps that prevent a confident production recommendation: (1) architectural blockers that are treated as compliance artifacts — particularly LLM provider BAA feasibility, which could invalidate the cloud LLM architecture entirely; (2) absent population-specific requirements — minors/COPPA and EU AI Act high-risk classification are complete omissions, not oversights, given the stated EU jurisdiction scope; and (3) quantitative thresholds that are insufficiently stringent for the domain — a 95% crisis recall target means thousands of missed crises at scale, and the 100-user load test does not validate the 99.99% crisis SLO. The plan scores 63 for a wellness MVP context: the bones are sound and the safety thinking is serious, but the LLM BAA question and the minors handling gap are blocking issues that must be resolved before significant engineering investment proceeds.

### Flaws Identified

1. Crisis detection '95% recall' acceptance criterion is dangerously low. 1 in 20 missed crisis messages in a mental health context is a life-safety failure, not a product metric. The plan never addresses the downstream consequence of a false negative — no fallback, no ambiguous-case escalation, no 'when in doubt, route to hotline' default.
2. False positive rate for crisis detection is never specified. High recall without precision constraints will flood non-crisis users with hotline cards, causing alert fatigue and app abandonment. The FMEA (step 5) doesn't close this gap in the downstream acceptance criteria.
3. HIPAA applicability is determined at step 4 but steps 6, 7, 11, and 15 are already architected around HIPAA being applicable. If the assessment concludes HIPAA doesn't apply (it's a wellness app with no covered-entity relationship), the compliance scaffolding is waste. Conversely, if it does apply and the LLM provider won't sign a BAA, the core architecture is broken. This must be resolved before design, not after.
4. LLM provider BAA feasibility is an unaddressed architectural blocker. Mood logs and chat history containing mental health disclosures almost certainly constitute PHI if HIPAA applies. Major LLM providers have inconsistent or restricted BAA policies. If your LLM provider won't sign a BAA, you cannot send session data to them — which invalidates the entire cloud LLM integration. This is a go/no-go question, not a compliance checkbox.
5. Age verification and minors handling are completely absent. Mental health apps disproportionately attract minors. COPPA compliance, parental consent, different escalation protocols for under-18 users (Teen Line, Crisis Text Line's youth protocols), and age-gating are not mentioned anywhere in 23 steps.
6. EU AI Act compliance is missing. For EU deployment, AI systems used in mental health contexts are classified as high-risk under Annex III of the EU AI Act. This requires a conformity assessment, transparency disclosures, human oversight documentation, and registration in the EU database. GDPR alone is insufficient — the plan mentions GDPR but has no EU AI Act analysis.
7. The CBT exercise catalog is never reviewed by a licensed clinician. Implementing evidence-based CBT with incorrect sequencing, missing contraindications, or wrong therapeutic targets is harmful. Step 1 lists 'clinician_reviewer' as a persona but there is no formal clinical review gate anywhere in the 23 steps.
8. Step 23 assigns penetration testing to 'regulatory_specialist' — the wrong role. Penetration testing requires a security engineer or external firm with offensive security expertise. Regulatory specialists assess compliance frameworks; they do not run Burp Suite or write custom jailbreak suites.
9. Hotline routing by 'user locale' is brittle in crisis conditions. Users travel, use VPNs, or may have a device locale mismatched to their physical location. During an acute crisis, routing to the wrong country's hotline is a critical failure. The plan has no fallback for locale ambiguity.
10. 99.99% crisis routing SLO is unrealistic for a single-team MVP launch. That is fewer than 53 minutes of downtime per year. The infra plan has no multi-region active-active deployment, no graceful degradation path (e.g., 'if routing service is down, always show 988'), and no SLO violation consequence definition.
11. Mood log retention of 90 days may conflict with state mental health records laws. California (CMIA), New York, and several other states mandate 7-year retention for mental health records regardless of wellness vs. medical classification. The plan addresses HIPAA and CCPA but misses state-level mental health data privacy statutes entirely.
12. Mobile app local storage encryption is unaddressed. React Native/Expo will cache chat history and mood logs locally. The plan has no specification for iOS Secure Enclave use, Android Keystore, or what happens to PHI cached on a lost or stolen device.
13. The 100-concurrent-user system test is not production-scale and does not validate the 99.99% crisis routing SLO or capacity planning claims. Any meaningful public launch will exceed 100 concurrent users within weeks.

### Suggestions

1. Resolve LLM provider BAA feasibility before finalizing the architecture. Evaluate providers specifically for BAA availability (AWS Bedrock, Azure OpenAI, or self-hosted models are safer paths if HIPAA applies). Make this a step 0 or 1 decision, not a step 6 checkbox.
2. Replace the '95% recall' crisis detection threshold with a tiered ambiguity policy: any message scoring above a lower confidence threshold should default to hotline surfacing, not suppression. Document explicit false negative consequence scenarios in the FMEA.
3. Add a clinical advisory step between step 1 and step 10. All CBT exercise content, crisis escalation tiers, and safe messaging language should be reviewed and signed off by at least one licensed mental health clinician before any code is written.
4. Add an EU AI Act conformity assessment as a parallel track to the HIPAA/FTC regulatory work. If EU launch is in scope, this is not optional.
5. Add a minors handling specification covering: age-gate at onboarding, COPPA notice, youth-specific hotline routing, different consent requirements for under-13 vs 13-17 users.
6. Replace the locale-based hotline router with IP geolocation + locale as a fallback, plus a manual 'I'm in [country]' override in the crisis card UI. Default to 988/International Association for Suicide Prevention directory when geolocation is ambiguous.
7. Change step 23's agent role from 'regulatory_specialist' to 'security_engineer' or explicitly require an external third-party penetration testing firm. Internal teams should not self-certify security for a mental health app.
8. Add mobile app local storage encryption to step 14 acceptance criteria. Specify SQLCipher or equivalent for any locally persisted chat or mood data.
9. Reduce the crisis routing SLO to a defensible target (99.9% = ~8.7 hours/year) and add a graceful degradation design: when crisis routing service is unavailable, the app displays a static crisis card with hardcoded 988 and Crisis Text Line numbers.
10. Resolve data retention conflict between step 11 (90-day mood logs) and applicable state mental health records laws before implementing the deletion jobs.

### Missing Elements

1. LLM provider BAA feasibility assessment — this is a go/no-go architectural decision, not a compliance artifact
2. EU AI Act high-risk AI conformity assessment for EU market
3. Age verification, COPPA compliance, and minors-specific crisis protocols
4. Licensed clinician review gate for CBT content and crisis thresholds
5. State-level mental health data privacy law analysis (CA CMIA, NY, TX, etc.)
6. Mobile app local data encryption specification (iOS Keychain, Android Keystore, SQLCipher)
7. AI disclosure requirement — several jurisdictions require explicit disclosure that the user is interacting with an AI, not a human clinician. Not present in the consent flow.
8. Adverse event reporting and post-market surveillance process. Even wellness apps need a process for capturing and responding to user-reported harms.
9. App store review timeline planning — Apple's mental health app review is stringent and slow. No launch timeline buffer or pre-submission review process is defined.
10. Multi-region or static fallback for crisis routing to achieve crisis routing SLO
11. Clinical contraindications for CBT exercises (e.g., breathing exercises contraindicated for certain anxiety presentations)
12. User opt-out from AI conversation (right to speak to a human or use app without LLM)

### Security Risks

1. LLM provider receiving PHI without BAA: if HIPAA applies and the LLM provider doesn't have a signed BAA, every API call with session context is a HIPAA violation. The plan lists this as a future compliance artifact rather than a blocking architectural constraint.
2. Prompt injection via mood journal entries: users can embed adversarial instructions in free-text journal entries that are subsequently fed to the LLM in context. The threat model names prompt injection but the specific attack surface of user-controlled freetext in the RAG context is not mitigated.
3. Crisis bypass via multi-turn context manipulation: a sophisticated adversarial user can gradually shift the conversation context to neutralize crisis detection without triggering any single keyword classifier. The jailbreak detector tests single-turn attempts; multi-turn context poisoning is not addressed.
4. PHI in mobile app cache without encryption: chat history and mood logs cached locally are accessible to any app with root access or via iOS backup unless explicitly encrypted. Not addressed in the frontend acceptance criteria.
5. Session token exposure in React Native deep links: OAuth/JWT tokens passed via deep links in React Native apps are a known attack vector. The auth design doesn't specify secure deep link handling or PKCE enforcement for mobile auth flows.
6. The 100-sample adversarial guardrail test suite is insufficient for production. LLMs can generate harmful content in ways that evade keyword and small-sample classifier testing. Without red-teaming at scale (thousands of samples, including indirect harm like enabling isolation or excessive reassurance that delays real help-seeking), the safety guardrail provides false confidence.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.309648
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

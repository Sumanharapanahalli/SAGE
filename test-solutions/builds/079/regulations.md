# Regulatory Compliance — Skill Assessment

**Domain:** edtech
**Solution ID:** 079
**Generated:** 2026-03-22T11:53:39.331844
**HITL Level:** standard

---

## 1. Applicable Standards

- **EEOC Guidelines**
- **GDPR**
- **SOC 2**
- **Adverse Impact Analysis**

## 2. Domain Detection Results

- edtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 5 | LEGAL | Draft Terms of Service, Privacy Policy, Data Processing Agreements, and candidat | Privacy, licensing, contracts |
| Step 6 | COMPLIANCE | Produce compliance evidence artifacts for COPPA, FERPA, and WCAG 2.1. Build a re | Standards mapping, DHF, traceability |
| Step 7 | SECURITY | Threat model the platform covering proctoring data, video streams, coding sandbo | Threat modeling, penetration testing |
| Step 23 | QA | Develop QA test plan covering manual test cases for adaptive testing accuracy, v | Verification & validation |
| Step 24 | SYSTEM_TEST | End-to-end system test suite: full candidate journey (invite → adaptive test → c | End-to-end validation, performance |

**Total tasks:** 26 | **Compliance tasks:** 5 | **Coverage:** 19%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | EEOC Guidelines compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 3 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 4 | Adverse Impact Analysis compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 10 | Engineering |
| regulatory_specialist | 2 | Compliance |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| marketing_strategist | 1 | Operations |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| legal_advisor | 1 | Compliance |
| data_scientist | 1 | Analysis |
| localization_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 55/100 (FAIL) — 1 iteration(s)

**Summary:** This is a thorough, well-structured plan that correctly identifies the major components of a hiring assessment platform and sequences them logically. The technical choices are generally sound — 3PL IRT, gVisor sandboxing, MediaPipe proctoring, and demographic parity metrics are all industry-appropriate. However, the plan has several fundamental production blockers that are not cosmetic gaps but architectural contradictions: the adaptive engine cannot function without pre-calibrated IRT parameters, which require a separate multi-month data collection study that is absent from the plan entirely; the composite ranking score includes a video rubric component that is never defined anywhere; the bias detection pipeline requires protected demographic data that the plan never specifies how to collect, under what legal basis, or how to reconcile with GDPR data minimization; and the system test requires session resumption that no step actually designs. Beyond these core gaps, the compliance coverage misses the most directly applicable US AI hiring regulations (NYC LL144, Illinois AI Video Interview Act), WebRTC will fail silently for enterprise candidates without TURN infrastructure, and client-side ML proctoring at 15 FPS CPU-only will cause device performance failures that falsely escalate cheating flags. The plan scores 55 — above 50 because the domain coverage is comprehensive and the technical direction is correct, but below 65 because the IRT bootstrapping gap alone makes the adaptive testing feature non-functional on launch day, and two other core features (video rubric, bias detection) have undefined or legally contradictory inputs.

### Flaws Identified

1. IRT 3PL cold-start problem is fatal and unaddressed: calibrated item parameters (a, b, c) require hundreds of real candidate responses per question. The plan seeds 50 questions across 5 categories with no calibration strategy. On day one, the adaptive engine has zero valid IRT parameters and cannot function as specified.
2. Video rubric score is a phantom component: step 15 aggregates 'irt_theta + coding_score + video_rubric_score' but no step anywhere defines how video_rubric_score is produced. Is it human-scored? LLM-analyzed? Sentiment analysis? This is a core input to the final ranking with no implementation plan.
3. Bias detection requires protected attribute data that is never collected: steps 14 and 6 assume gender, race_ethnicity, and age_bracket exist per candidate. No step defines how this data is gathered, from whom, when, or under what consent. EEOC best practices actually recommend NOT collecting this data during assessment — creating an architectural contradiction.
4. Demographic data for bias analysis is architecturally irreconcilable with GDPR data minimization: you cannot simultaneously minimize PII collection (GDPR Art. 5) and collect sensitive protected-class data for bias auditing without a specific legal basis. The plan never resolves this tension.
5. WebRTC without TURN/STUN infrastructure will fail for enterprise candidates: corporate firewalls and symmetric NAT — the default in most enterprise environments — block direct WebRTC peer connections. Neither step 12 (video service) nor step 19 (infra) mentions TURN server deployment (coturn or commercial). Connection failure rates in enterprise environments without TURN can exceed 20-30%.
6. MediaPipe FaceMesh at 15 FPS CPU-only in a browser is unrealistic: on mid-range laptops running a full-screen coding assessment with Monaco editor and WebRTC simultaneously, sustained 15 FPS CPU-side inference will peg one core, cause thermal throttling, and may crash the tab — disqualifying candidates due to hardware limitations, not cheating.
7. Item exposure control is completely absent: selecting questions by maximum Fisher information causes popular items to be seen by nearly every candidate in a cohort. Without a control algorithm (Sympson-Hetter, randomesque, or maximum priority index), the question bank is compromised within weeks by candidate sharing. This is a known CAT failure mode.
8. SE < 0.3 stopping criterion assumes well-calibrated, high-discrimination items that don't exist at launch: with a 50-question seed bank lacking calibrated parameters, many sessions will hit max_items=40 without converging, producing ability estimates with confidence intervals so wide they are meaningless for ranking.
9. EEOC AI hiring regulations and state laws are entirely absent: NYC Local Law 144 (mandatory annual bias audit before deployment, candidate notification), Illinois AI Video Interview Act (requires candidate consent for AI video analysis, provides deletion rights), and Maryland's similar law create immediate legal exposure. Step 5 and 6 cover FERPA/COPPA/GDPR/CCPA but omit the most directly applicable US AI hiring regulations.
10. Session resumption architecture is undefined but required by step 24 acceptance criteria: 'candidate session resumable after pod crash' requires explicit CAT state persistence (current theta, standard error, items administered, responses). No schema field, no API contract, and no design for this exists anywhere in the 26 steps.
11. 50-question seed bank is insufficient for operational CAT: avoiding item overexposure requires 5-10x the number of target test items per ability range. A 40-item max test needs 200-400 calibrated items per skill domain for acceptable exposure rates. With 50 total questions across 5 categories (10/domain), every candidate will see nearly identical tests — making the 'adaptive' claim false.
12. SHAP explainability applied to IRT psychometric scores is technically inappropriate: SHAP explains feature contributions in ML models. The IRT composite score is a psychometric likelihood-based estimate, not a feature-weight model. Applying SHAP here produces outputs that look like explanations but have no valid psychometric interpretation.

### Suggestions

1. Add a calibration study phase before launch: recruit 300-500 participants to take a static pretest with all seed questions. Use response data to estimate IRT parameters. Gate CAT launch on having >= 100 questions with calibrated parameters per domain. This likely takes 6-8 weeks and must be planned as a separate workstream.
2. Define video rubric scoring explicitly in a new step between step 12 and step 15: decide between (a) structured human rubric scored by interviewer, (b) LLM-based transcript scoring against rubric dimensions, or (c) no video score in v1 — only transcript keyword matching. Each choice has different accuracy, cost, and bias implications.
3. Resolve the demographic data contradiction before step 14 is built: three viable paths are (1) collect voluntary self-reported demographics post-hire with separate consent for audit-only purposes, (2) use proxy inference (which has its own legal risk), or (3) implement 'potential bias' monitoring using cohort score distributions without protected attributes. Document the legal basis for whichever path is chosen.
4. Add TURN server provisioning to step 12 or 19: deploy coturn or purchase Twilio TURN credits. Set ICE server configuration in the LiveKit/mediasoup client. Define TURN traffic cost estimates (TURN relay adds ~1 Mbps per session routed). Without this, enterprise customer POCs will fail at the demo stage.
5. Add Sympson-Hetter exposure control to the CAT engine in step 10: each item gets a target exposure rate (typically 0.20-0.33). The selection algorithm draws from top-N maximum-information items rather than always selecting the single best item. This is a 50-line addition to the selection logic but prevents question bank compromise.
6. Add NYC Local Law 144 and Illinois AI Video Interview Act compliance to step 5 and step 6: specifically, annual bias audit by independent third party, candidate notification that AI is used in evaluation, and right-to-request-deletion for video AI data. These are not optional for US hiring deployments.
7. Add a minimum cohort size gate to the bias detection pipeline: refuse to compute adverse impact ratios for cohorts < 30 per protected group (the standard statistical threshold from EEOC's Uniform Guidelines). Below this threshold, emit a 'INSUFFICIENT_DATA' status rather than a potentially misleading ratio.
8. Define session state persistence schema in step 8 and step 10: add a cat_sessions table with columns for current_theta, current_se, items_administered (array), responses (array), status (active/suspended/completed). This schema is the precondition for step 24's resumption requirement.
9. Reduce MediaPipe to server-side processing or use WASM SIMD with a capability check: run FaceMesh inference server-side on captured frame snapshots (1 frame/sec is sufficient for proctoring) rather than demanding real-time client-side inference. This eliminates the performance cliff on low-end devices.
10. Add at least one ATS integration (Greenhouse or Lever webhooks) to the MVP scope: without this, enterprise buyers cannot create a trial without manual CSV workflows. A webhook-based integration (not full OAuth) can be built in 2-3 days and removes a common deal-blocker.

### Missing Elements

1. TURN/STUN server infrastructure and ICE server configuration for WebRTC
2. IRT parameter calibration study — a prerequisite workstream, not a day-one deliverable
3. Video rubric scoring definition and implementation plan
4. Demographic data collection mechanism with legal basis justification
5. Minimum cohort size thresholds for valid bias analysis
6. Item exposure control algorithm in the CAT engine
7. NYC Local Law 144, Illinois AI Video Interview Act, and EEOC AI guidance compliance
8. GDPR Article 22 candidate notification rights (automated decision-making disclosure)
9. CAT session state persistence schema for resumption
10. Video storage cost model and retention/deletion schedule with cost projections
11. Question bank size requirements per domain for functional adaptive testing
12. Key rotation and JWT expiry/revocation policy
13. Candidate device requirements check (browser compatibility, camera/mic, bandwidth) before test start
14. Age verification mechanism implementation for COPPA (not just 'specified in consent flow')
15. Disaster recovery plan and RTO/RPO targets

### Security Risks

1. gVisor has documented CVEs and syscall compatibility gaps that can cause Java runtime crashes inside the sandbox — an attacker who knows the runtime version may trigger a controlled crash to escape the time limit without a TLE verdict. No CVE monitoring or syscall allowlist is specified.
2. Anti-cheat screenshots stored with candidate PII create a high-value exfiltration target: a breach exposes biometric-adjacent data (face images) linked to identity and assessment scores. The plan specifies encryption at rest but no access control policy, key rotation, or breach notification procedure specific to biometric data (BIPA in Illinois applies to face images).
3. WebRTC media encrypted in transit (DTLS/SRTP) but the recording pipeline breaks this: server-side recording decrypts the stream, re-encrypts for storage. The decryption point is an attack surface that is not addressed in the threat model.
4. JWT tokens with org-scoped API keys: no mention of token expiry enforcement, refresh token rotation, or revocation on recruiter offboarding. A leaked API key with no rotation policy provides indefinite access to all candidate data in that org.
5. Bias flag data in the audit trail identifies protected-class group membership indirectly: if a flag records 'demographic_parity_violation for group: gender=female', the audit log becomes a de facto record of gender per candidate ID, creating a sensitive data category that may not be covered by the existing privacy controls.
6. AST fingerprinting for plagiarism detection stores normalized ASTs per submission pair: if the comparison corpus is accessible via API, it enables reconstruction of proprietary coding challenge solutions through differential queries — a form of test content leakage.
7. No rate limiting or anti-automation controls specified on POST /sessions/{id}/responses: an automated script could submit thousands of MCQ responses per second, polluting score distributions and calibration data.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.331915
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

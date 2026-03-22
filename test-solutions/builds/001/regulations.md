# Regulatory Compliance — Elder Fall Detection

**Domain:** medtech
**Solution ID:** 001
**Generated:** 2026-03-22T11:53:39.305383
**HITL Level:** strict

---

## 1. Applicable Standards

- **FDA Class II**
- **IEC 62304**
- **ISO 14971**
- **ISO 13485**

## 2. Domain Detection Results

- medtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 1 | SAFETY | Conduct ISO 14971 risk management: identify hazards (missed fall, false alarm, G | Risk management, FMEA, hazard analysis |
| Step 2 | COMPLIANCE | Establish the Design History File (DHF) skeleton per FDA 21 CFR Part 820.30 and  | Standards mapping, DHF, traceability |
| Step 4 | SECURITY | Produce threat model (STRIDE) for device-to-cloud and cloud-to-caregiver communi | Threat modeling, penetration testing |
| Step 15 | EMBEDDED_TEST | Develop hardware-in-the-loop (HIL) test suite for fall detection firmware: autom | Hardware-in-the-loop verification |
| Step 16 | EMBEDDED_TEST | Develop system-level HIL tests: full device power cycle, LTE-M network registrat | Hardware-in-the-loop verification |
| Step 17 | QA | Develop and execute QA test plan for cloud backend and mobile app: functional te | Verification & validation |
| Step 18 | COMPLIANCE | Populate complete DHF per FDA 21 CFR Part 820.30: compile all design verificatio | Standards mapping, DHF, traceability |
| Step 19 | REGULATORY | Prepare 510(k) premarket notification submission package: cover letter, device d | Submission preparation, audit readiness |
| Step 21 | SECURITY | Execute penetration test plan against all system surfaces: firmware binary analy | Threat modeling, penetration testing |
| Step 22 | SYSTEM_TEST | Execute design validation in representative use environment: clinical simulation | End-to-end validation, performance |

**Total tasks:** 24 | **Compliance tasks:** 10 | **Coverage:** 42%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | FDA Class II compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | IEC 62304 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | ISO 14971 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 4 | ISO 13485 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 9 | Engineering |
| safety_engineer | 3 | Compliance |
| regulatory_specialist | 3 | Compliance |
| qa_engineer | 2 | Engineering |
| system_tester | 2 | Engineering |
| technical_writer | 2 | Operations |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| devops_engineer | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This plan is unusually comprehensive for a medtech IoT system — the technology choices are sensible (nRF9161, LSM6DSO32X ML Core, Zephyr RTOS, TimescaleDB, RapidSOS), the regulatory structure is well-intentioned, and the testing depth is above average for an early-stage plan. However, it cannot score above 54 for an FDA Class II submission target because it contains multiple blocking issues that will cause either FDA rejection or post-market regulatory action: the IEC 62304 software safety class is almost certainly wrong and must be resolved before any V&V work begins; the 510(k) predicate strategy is unvalidated and deferred 17 steps too late; no IRB approval step exists for human subject studies; indoor GPS is the primary use case failure mode with no mitigation; 400mAh supporting 72h with active LTE-M and GPS is a credible but unproven claim that must be budgeted before PCB fabrication; automatic 911 dispatch has zero legal review; and post-market surveillance and MDR complaint handling procedures — both non-negotiable FDA requirements — are entirely absent. The security architecture is solid in concept but has critical gaps in key management and revocation infrastructure. To reach production readiness for a regulated submission, the plan needs a regulatory strategy gate (Step 0: predicate + pathway + Q-Sub), a reclassification decision on IEC 62304 safety class, IRB process, indoor positioning fallback, FCC certification track, post-market procedures, and legal review of the 911 dispatch feature — before committing to the current hardware BOM and firmware architecture.

### Flaws Identified

1. IEC 62304 Software Safety Class misclassification: Class B ('injury possible') is almost certainly wrong. An undetected fall causing an elderly person to lie unresponsive for hours can be fatal — that is Class C ('death possible'). Class B requires only software unit testing; Class C requires full integration and system testing with traceability to every software item. If FDA reviewers disagree with your Class B justification, the entire IEC 62304 software documentation package must be redone. This is submission-killing if wrong.
2. 510(k) predicate assumption is unvalidated and deferred too late. The predicate device search is listed as an acceptance criterion in Step 18 — after 17 steps of design work. If no adequate predicate exists under MVO, or if FDA classifies automatic emergency dispatch as a novel feature requiring De Novo, the entire regulatory strategy collapses. Predicate identification must happen in Step 2, not Step 18.
3. No IRB/Ethics Board approval step. Step 22 involves controlled fall simulations with elderly participants on padded mats and a 30-day field trial. This requires IRB approval (45 CFR Part 46 / 21 CFR Part 50) before any human subject study begins. Proceeding without IRB approval invalidates the clinical data for FDA submission and exposes the organization to serious legal liability.
4. Indoor GPS is the primary failure mode and it's unaddressed. Falls predominantly happen indoors — bathroom, bedroom, kitchen. u-blox M10 GPS will not achieve ≤10m accuracy indoors; it often cannot acquire a fix at all. There is no fallback positioning strategy (WiFi positioning, BLE beacon triangulation, cell tower triangulation, last-known-outdoors position). The '≤10 meters' GPS spec will fail the majority of real-world use cases.
5. 400mAh battery vs. 72h runtime with LTE-M + GPS is not credible without a detailed power budget. LTE-M active transmit current on nRF9161 is 220-490mA peak; GPS acquisition is 15-20mA; Zephyr RTOS active MCU is 5-15mA. Even with aggressive duty cycling (eDRX, PSM), 400mAh / 72h = 5.5mA average budget is extremely tight. Step 6 acceptance criteria require a power budget analysis, but the 400mAh figure is already specified as a fixed constraint in the BOM — if the power budget fails, the hardware must be redesigned. This should be validated before committing to the form factor.
6. 30-second escalation timer for automatic 911 dispatch has no legal framework. Automatic emergency dispatch is regulated differently in each US state. False-positive 911 calls can result in liability under FCC rules and state statutes. No legal review step exists in this plan. RapidSOS NG911 API access requires a signed agreement with RapidSOS, carrier integration agreements, and may not have PSAP coverage in all geographies. The plan treats this as a pure engineering problem.
7. Clinical validation sample size is inadequate for FDA evidence. 30 participants (10 for field trial) is far below what FDA expects for a Class II device with a primary safety endpoint. Predicate devices in the fall detection space have used 100-300 participants for pivotal validation. The 'controlled fall simulation on padded mats' does not replicate real fall biomechanics. FDA will likely require clinical data from spontaneous or minimally-assisted falls. This validation plan will not support a 510(k) submission.
8. Fall detection algorithm training data provenance and demographic coverage are unspecified. The ML Core decision tree is 'pre-loaded' but there is no specification of what dataset it was trained on, whether it covers the target demographic (elderly, 65+, varying BMIs, mobility aids like walkers/canes), or whether the training data is independent from the validation data. This is a SOUP qualification gap under IEC 62304 and a performance validation gap for FDA.
9. No Post-Market Surveillance (PMS) Plan. FDA 21 CFR Part 822 requires a post-market surveillance plan for Class II devices. ISO 13485 requires post-market monitoring. MDR (Medical Device Reporting) procedures under 21 CFR Part 803 for adverse event reporting are completely absent. These are not optional and must exist before commercialization.
10. No FCC / RF Certification step. The nRF9161 LTE-M radio and BLE 5.3 require FCC Part 15/22 certification. Even using a pre-certified module, the end-product integration requires FCC approval or a Declaration of Conformity. This process takes 6-16 weeks, can require test lab time, and may require hardware modifications. It's entirely absent from the plan.
11. Caregiver push notification delivery (FCM/APNs) is treated as reliable for a life-safety alert path. FCM/APNs are best-effort, not guaranteed-delivery. The caregiver's phone may have notifications disabled, the app backgrounded/killed by iOS memory pressure, or the phone on DND/airplane mode. There is no SMS fallback SLA, no PSTN voice call fallback, and no multi-caregiver escalation chain specified. A single-point FCM failure means no alert.
12. OTA signing key management is unspecified. The ECDSA P-256 private key for firmware signing is critical — if compromised, an attacker can push arbitrary firmware to all deployed devices. There is no HSM requirement, no key ceremony procedure, no key rotation policy, and no revocation mechanism specified. This is both a security gap and a regulatory gap (cybersecurity documentation for FDA 510(k)).
13. Step 1 (risk management) and Step 3 (system architecture) have no dependency on each other and run in parallel. The hazard analysis outputs (risk controls, mitigations) must inform the architecture requirements. If Step 3 produces an architecture before Step 1 identifies a hazard that requires an architectural control (e.g., redundant alert paths for alert delivery failure), the architecture must be revised — causing cascading rework.
14. False positive rate specification (2%) applies only to 'normal ADL' bench simulation. No specification exists for sleep positions, bed egress, wheelchair use, exercise, or activities by users with mobility aids. The ADL dataset of 500 events is small and likely does not cover clinically relevant edge cases for an elderly population.

### Suggestions

1. Resolve software safety class (Class B vs C) as the first decision, before any other work begins. Document the hazard severity analysis that justifies the class. If any software function failure could contribute to a death, it is Class C. Get this decision signed off by your regulatory lead and an external notified body if targeting EU MDR simultaneously.
2. Run predicate device search in parallel with Step 1/2, not deferred to Step 18. Use FDA 510(k) database, product code MVO, and engage FDA pre-submission (Q-Sub) meeting early to confirm the regulatory pathway. Budget 3-6 months for FDA feedback cycles.
3. Add an IRB protocol submission step immediately before Step 22. Allow 8-12 weeks for IRB approval. Write the clinical protocol (including fall simulation methodology, inclusion/exclusion criteria, stopping rules, adverse event reporting) in Step 2 alongside the DHF structure.
4. Add a hybrid positioning fallback architecture: GPS (outdoor), WiFi positioning (indoor via Google/Apple location APIs), BLE beacon proximity (home environment option), with cell tower triangulation as last resort. Specify indoor vs outdoor accuracy requirements separately in the design inputs.
5. Commission a detailed power budget analysis as a blocking gate before PCB layout is finalized. Use nRF9161 Power Profiler Kit 2 measurements. If 400mAh cannot support 72h with representative duty cycle, increase to 600-800mAh or shrink the GPS duty cycle further — this decision must be made before Gerbers are fabricated.
6. Engage legal counsel specializing in telehealth/emergency services regulation before Step 11 (alert engine) is built. Obtain a RapidSOS partner agreement and confirm PSAP coverage in your target markets. Define false-alarm liability policy. Add a legal review gate before the 911 dispatch feature is enabled in production.
7. Increase clinical validation to minimum 100 participants for the pivotal study and engage a clinical research organization (CRO) with fall detection experience. Consider a wear-and-detect protocol with instrumented falls rather than supervised padded-mat falls to get more realistic biomechanical data.
8. Specify ML Core decision tree training dataset: source, size, demographic breakdown, independent validation holdout, and IRB approval for any human-derived data. Treat the decision tree as SOUP requiring qualification evidence per IEC 62304 §8.
9. Add Step 0: FCC pre-certification assessment and RF test planning. Determine whether to use a pre-certified nRF9161 module or do board-level FCC approval. Add FCC testing to the critical path — it must complete before commercial launch.
10. Add a Post-Market Surveillance plan and MDR/complaint handling SOP as deliverables in Step 18 or a new Step 18.5. These are required before commercial distribution.
11. Implement a multi-tier alert delivery chain: FCM push (primary, 0-5s) → SMS via Twilio (secondary, 5-15s) → PSTN voice call to caregiver (tertiary, 15-25s) → RapidSOS dispatch (30s). Each tier should fire if the previous tier is unacknowledged, not just the final escalation.
12. Specify ECDSA signing key management: HSM (AWS CloudHSM or similar) for key storage, documented key ceremony, dual-control key access, key rotation every 2 years, device revocation list mechanism. This is required for FDA cybersecurity documentation.
13. Make Step 3 depend on Step 1 (risk management outputs), or explicitly document that Step 3 is a preliminary architecture subject to revision after risk analysis completes. Track all architecture-impacting risk controls in the traceability matrix from Step 1 outputs.

### Missing Elements

1. Post-Market Surveillance Plan (required by 21 CFR Part 822 and ISO 13485 §8.2.1)
2. Medical Device Reporting (MDR) and Complaint Handling SOP (21 CFR Part 803 / 820.198)
3. IRB protocol submission and approval process (21 CFR Part 50, 45 CFR Part 46)
4. FCC Part 15/22 RF certification step and timeline
5. Indoor positioning fallback strategy — GPS alone is insufficient for the intended use environment
6. OTA signing key management procedure (HSM, key ceremony, rotation, revocation)
7. Legal review of automatic 911 dispatch liability, FCC false-alarm rules, and state-by-state emergency dispatch laws
8. Multi-tier alert delivery with guaranteed fallback (SMS → voice call → 911) beyond single FCM push
9. De Novo pathway analysis as alternative to 510(k) if no adequate predicate is found
10. FDA Pre-Submission (Q-Sub) meeting step to confirm regulatory pathway before significant investment
11. COOP / multi-region AWS deployment strategy for the life-safety alert engine (single-region outage = no alerts)
12. Supplier qualification records and component obsolescence risk assessment for critical components (nRF9161, LSM6DSO32X, ATECC608B)
13. Cleaning and biocompatibility assessment per ISO 10993 — skin-contact wearable requires cytotoxicity and sensitization testing
14. Quality Management System (QMS) selection and setup (required for ISO 13485 certification and FDA 820.5)
15. ANVISA (Brazil), Health Canada, TGA (Australia) registration strategy if non-US markets are targeted
16. EU MDR 2017/745 Technical Documentation and Notified Body engagement if CE marking is required
17. Software anomaly resolution procedure (IEC 62304 §6.2.5) — defects found during V&V must go through a documented resolution process

### Security Risks

1. OTA signing key stored without HSM: if the ECDSA private key is compromised (developer laptop, CI/CD secret leak), an attacker can push malicious firmware to the entire deployed device fleet — silently disabling fall detection or enabling remote surveillance. No revocation mechanism is specified.
2. RapidSOS API endpoint is a high-value target: an attacker who can forge a fall event (exploiting a confidence score bypass or MQTT topic ACL gap) can trigger automatic 911 dispatch to any address, causing emergency resource exhaustion. Rate limiting on the fall-event endpoint is specified but its enforcement under a spoofed device identity is not verified.
3. mTLS device certificates provisioned at manufacturing (ATECC608B) have no revocation mechanism specified. If a device is stolen or its certificate extracted, it can permanently impersonate a legitimate device. No OCSP/CRL infrastructure is defined.
4. The offline flash buffer (8KB, Step 10) stores unprocessed fall events. If the buffer contents are not encrypted at rest on the nRF9161 flash, an attacker with physical access (JTAG/SWD) can read buffered GPS positions and health events — PHI exposure without decryption.
5. The 30-second no-response escalation window is a denial-of-service vector: an attacker who can flood the alert engine with high-confidence false fall events (by compromising one device's credentials) can saturate Celery workers, delay legitimate escalations, and potentially deplete the RapidSOS API quota causing real emergencies to go undispatched.
6. The caregiver app uses OAuth 2.0 + PKCE via Auth0, but biometric unlock on subsequent opens does not re-authenticate to the server — it only unlocks the local token store. A stolen unlocked phone gives permanent caregiver access with no session expiry on the device. Server-side session binding to device fingerprint is not specified.
7. IEC 62443 is cited as a security standard (Step 4) but it governs industrial control systems, not medical device cybersecurity. The correct references are FDA 2023 Cybersecurity Guidance, IEC 81001-5-1:2021, and NIST SP 800-213 (already cited). Relying on IEC 62443 framing may produce a security architecture that passes an industrial audit but fails FDA cybersecurity review.
8. GPS position data transmitted at 1Hz during emergencies over MQTT QoS 1 means precise real-time location of a vulnerable elderly person is continuously accessible to anyone who can read the MQTT broker stream. MQTT topic ACLs are mentioned but the broker-level authorization model (per-device topic isolation) and the cloud-side storage encryption for live location data are not fully specified.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.305491
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

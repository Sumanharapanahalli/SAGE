# Regulatory Compliance — Elder Fall Detection

**Domain:** medtech
**Solution ID:** 001
**Generated:** 2026-03-22T18:55:19.969329
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
| Step 2 | SAFETY | Perform preliminary hazard analysis (PHA) and initial risk assessment per ISO 14 | Risk management, FMEA, hazard analysis |
| Step 3 | COMPLIANCE | Establish Design History File (DHF) skeleton and Quality Management System (QMS) | Standards mapping, DHF, traceability |
| Step 4 | SECURITY | Produce threat model (STRIDE) and cybersecurity risk assessment per IEC 62443 fo | Threat modeling, penetration testing |
| Step 17 | EMBEDDED_TEST | Write firmware unit tests (Unity framework) and HIL test specifications for elde | Hardware-in-the-loop verification |
| Step 19 | SYSTEM_TEST | Execute end-to-end system test suite covering full elder_fall_detection workflow | End-to-end validation, performance |
| Step 20 | COMPLIANCE | Complete DHF with all design verification and validation evidence. Populate trac | Standards mapping, DHF, traceability |
| Step 21 | REGULATORY | Prepare FDA 510(k) premarket notification package for elder_fall_detection devic | Submission preparation, audit readiness |
| Step 22 | SAFETY | Complete final FMEA and fault tree analysis (FTA) for elder_fall_detection syste | Risk management, FMEA, hazard analysis |
| Step 23 | SECURITY | Execute security review and finalize SBOM for elder_fall_detection. Run automate | Threat modeling, penetration testing |

**Total tasks:** 24 | **Compliance tasks:** 9 | **Coverage:** 38%

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
| developer | 6 | Engineering |
| regulatory_specialist | 5 | Compliance |
| devops_engineer | 3 | Engineering |
| safety_engineer | 2 | Compliance |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| firmware_engineer | 1 | Engineering |
| data_scientist | 1 | Analysis |
| quality_engineer | 1 | Engineering |
| qa_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This is a structurally comprehensive plan that covers the right domains — hardware, firmware, ML, backend, mobile, compliance, and regulatory — but contains multiple fundamental flaws that would block both FDA clearance and safe production deployment. The most critical are: (1) IEC 62366-1 usability engineering is entirely absent, which is a 510(k) submission blocker; (2) the BLE-only connectivity architecture makes the device unsafe when the caregiver's phone is out of range — for a medical safety device this is a design defect, not a limitation; (3) ML validation on lab-collected young-adult simulation data does not support the ≥95% sensitivity claim for the real elderly target population; (4) the 35x25mm PCB with five major ICs and RF modules is likely infeasible without a feasibility analysis; and (5) the 72h GPS battery claim has no supporting power budget. The compliance documentation framework (DHF, ISO 14971, IEC 62304) is well-structured, but is missing the clinical performance data that will be demanded during 510(k) review. The plan reads like a senior engineer's first pass at a regulated medical device — it knows what boxes to check but underestimates the depth required in hardware feasibility, clinical evidence, and usability engineering. Significant rework on the hardware architecture, connectivity design, ML validation methodology, and missing regulatory artifacts is required before this plan could be executed with confidence.

### Flaws Identified

1. ML model (step 10) incorrectly depends on firmware (step 9). Model training requires labeled IMU datasets, not working firmware. This serializes 6+ weeks of parallel work unnecessarily and is a fundamental scheduling error.
2. BLE-only connectivity architecture is a critical safety gap. If the caregiver's phone is out of BLE range (~10m), the device cannot alert anyone. For a medical safety device, this is a design defect — cellular (LTE-M/NB-IoT) fallback is not optional.
3. PCB form factor constraint (35mm x 25mm) is likely infeasible. u-blox MAX-M10S alone is 9.6mm x 9.6mm. Fitting STM32L476 + nRF52840 + u-blox MAX-M10S + LSM6DSO + BQ25180 + passives on a 35x25mm PCB while meeting RF keepout zones is implausible without a 6-layer board and 0201 passives. No feasibility analysis justifies this constraint.
4. Dual-chip architecture (STM32L4 + nRF52840 as co-processor) adds unnecessary BOM cost, PCB area, and inter-chip UART latency. The nRF52840 has its own Cortex-M4 that can run FreeRTOS and handle fall detection. This architectural choice is never justified.
5. 72h battery life with active GPS is physically implausible without duty cycling. u-blox MAX-M10S draws ~10-15mA at acquisition, ~1mA tracking. At 5mA average GPS draw alone on a typical 180mAh wristband battery, GPS exhausts battery in 36h before accounting for MCU, BLE, or cellular. No power budget analysis exists anywhere in the plan.
6. ML model validation uses MobiAct and SisFall datasets — both collected from younger, healthy adults performing simulated falls in controlled lab conditions. Validation on these datasets does not transfer to real elderly users with atypical gait, slower falls, partial falls, or falls from seated positions. This invalidates the ≥95% sensitivity claim for the target population.
7. IEC 62366-1 usability engineering is completely absent. FDA requires a Usability Engineering File (UEF) for 510(k) submissions. Missing use error risk analysis, formative studies, and summative validation with elderly users is a submission blocker — not a gap that can be patched post-submission.
8. No post-market surveillance (PMS) plan. FDA 21 CFR Part 803 (MDR) and 21 CFR Part 806 requires PMS from day one of commercialization. A Class II fall detection device with missed-fall risk will face MDR reporting obligations. This is entirely absent.
9. RapidSOS/NG911 integration assumes a contractual API relationship that takes months to establish, has geographic coverage gaps in rural US, and requires specific data formatting per NENA i3 standards. Treating it as a simple API call in step 12 acceptance criteria is unrealistic.
10. Software Safety Class assignment says 'Class B minimum' without justification. For a device where software failure (missed fall) could lead to serious patient harm (death from undetected fall), IEC 62304 Class C is the defensible classification. Class B underclassification risks FDA refusal-to-accept.
11. MQTT message buffering during connectivity loss is tested in step 19 but never designed. Step 9 firmware spec says nothing about flash-backed event queue, queue depth, TTL, or replay ordering. The system test will fail because the feature was never specified.
12. No manufacturing process validation. A Class II medical device requires IQ/OQ/PQ for manufacturing processes (pick-and-place, reflow, IP67 seal testing, functional test fixture). This is entirely absent from the plan — the DHF cannot be complete without it.
13. JWT authentication for IoT devices (step 4, step 12) conflicts with mutual TLS mentioned in the same plan. AWS IoT Core uses X.509 certificates, not JWTs, for device authentication. The authentication architecture is internally inconsistent.
14. No device provisioning security model at manufacturing time. How are X.509 certificates injected at the factory? No HSM, no certificate authority, no secure element (ATECC608 or equivalent). Firmware signing is listed as an acceptance criterion but the key management infrastructure is never designed.

### Suggestions

1. Move step 10 (ML model) to run in parallel with steps 6-9, with only the deployment-to-firmware step blocked on step 9. This recovers 3-4 weeks of critical path time.
2. Add LTE-M or NB-IoT as the primary alert channel, with BLE as the configuration/pairing interface only. Nordic nRF9161 or Sequans Monarch handles LTE-M and integrates more cleanly than the dual-chip STM32+nRF52840 design.
3. Commission a 6-layer PCB stack-up analysis before committing to the 35x25mm constraint. If the constraint is from product design requirements, add a feasibility step before PCB layout. If it is aspirational, state it as a target and validate in step 7 (mechanical).
4. Add an explicit power budget analysis step before PCB design (step 6). Define GPS duty cycle (e.g., 1 fix per 30s when stationary, continuous when motion detected), CPU active/sleep ratios, and BLE advertising intervals. This gates the 72h claim.
5. Add step 0.5: IEC 62366-1 Usability Engineering Plan, with formative usability studies at step 5 (UX Design) using actual elderly participants, and summative validation scheduled before step 20 (DHF completion).
6. Add a clinical performance validation step between step 17 (embedded test) and step 20 (DHF). The 510(k) substantial equivalence argument for a fall detection device will be strengthened significantly by even a 30-subject pilot study with elderly users in a care home setting.
7. Add step 8.5: device identity and certificate provisioning design. Specify secure element (ATECC608B or equivalent), certificate authority architecture, factory provisioning fixture, and certificate revocation mechanism.
8. Replace IEC 62443 as the primary cybersecurity standard with FDA's 2023 Cybersecurity Guidance (Refuse to Accept policy) and NIST IR 8259. IEC 62443 is industrial control systems — reference it as supplementary only.
9. Define HIPAA Business Associate Agreements (BAAs) with AWS, Twilio, SendGrid, and RapidSOS explicitly. AWS BAA is available but must be executed. Twilio and SendGrid have their own BAA processes. Missing BAA voids HIPAA safe harbor.
10. Specify a post-market surveillance plan as a deliverable in step 21 (regulatory). Include MDR decision tree, complaint handling procedure (21 CFR Part 820.198), and field corrective action trigger criteria.

### Missing Elements

1. IEC 62366-1 Usability Engineering File — formative studies, use error analysis, summative validation with elderly target users. FDA will not accept a 510(k) without this.
2. Post-market surveillance plan (21 CFR Part 803, 21 CFR Part 806, EU MDR Article 83 if international scope intended).
3. Cellular (LTE-M/NB-IoT) connectivity design. BLE range limitation makes the device unsafe as a sole-communication-path medical device.
4. Power budget analysis and GPS duty cycling strategy supporting the 72h battery life claim.
5. Manufacturing process validation (IQ/OQ/PQ) for PCB assembly, IP67 seal testing, and final functional test.
6. Secure element and certificate provisioning architecture for device identity at manufacturing time.
7. Clinical performance data with elderly subjects — lab datasets alone are insufficient for the 510(k) substantial equivalence performance testing section.
8. HIPAA BAA execution plan for all third-party data processors (AWS, Twilio, SendGrid, RapidSOS).
9. Data retention and right-to-deletion policy (HIPAA minimum 6-year retention, GDPR if EU market).
10. PCB feasibility analysis before committing to 35x25mm constraint.
11. Alert deduplication logic — what prevents duplicate NG911 dispatch if caregiver and auto-dispatch both trigger within seconds?
12. Firmware OTA update design (mentioned in step 9 acceptance criteria but never designed as a task — rollback, signature verification, atomic swap, and fail-safe boot are all unspecified).
13. International regulatory pathway — CE marking under EU MDR 2017/745 is not mentioned despite the device's clear EU market applicability.

### Security Risks

1. BLE bonding without a secure element means pairing keys are stored in MCU flash. A physical device compromise yields all pairing credentials and enables location tracking of the patient. No mention of anti-tamper or key erasure on tamper detection.
2. JWT tokens for caregiver mobile app without refresh token rotation policy. A stolen JWT provides persistent patient location access. Token lifetime and rotation strategy are unspecified.
3. GPS coordinates stored as PII in PostgreSQL with pgcrypto — but pgcrypto column-level encryption means the application holds the decryption keys in memory. A backend compromise exposes all patient location history. No mention of key management service (AWS KMS) for column keys.
4. MQTT/AWS IoT Core device certificates: if a device is stolen, there is no defined certificate revocation workflow. Attacker can impersonate the device, inject false fall events triggering unnecessary emergency dispatch, or suppress real fall events.
5. OTA firmware update mechanism exists in acceptance criteria but signing/verification design is absent. An unsigned OTA channel on a medical device is a direct patient safety risk — malicious firmware could suppress fall detection entirely.
6. MobSF scan for mobile app is planned but no runtime application self-protection (RASP) or jailbreak/root detection is specified. On a jailbroken device, screenshot prevention and auto-lock controls are trivially bypassed, exposing patient location and health data.
7. RapidSOS API credentials stored where? If in Secrets Manager, how are they rotated? If rotation fails and credentials expire, emergency dispatch silently fails — a safety-critical failure mode with no detection mechanism in the plan.
8. No network segmentation between MQTT ingestion path and caregiver REST API path. A compromised IoT device should not be able to reach the user management or emergency dispatch endpoints. The VPC/WAF design in step 15 does not specify this isolation.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T18:55:19.969443
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

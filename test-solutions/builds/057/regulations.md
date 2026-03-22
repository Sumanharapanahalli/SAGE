# Regulatory Compliance — Wearable Fitness

**Domain:** iot
**Solution ID:** 057
**Generated:** 2026-03-22T11:53:39.324766
**HITL Level:** standard

---

## 1. Applicable Standards

- **FCC Part 15**
- **CE Mark**
- **GDPR**
- **HIPAA**

## 2. Domain Detection Results

- iot (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 11 | SECURITY | Conduct threat model (STRIDE) for wearable_fitness: BLE channel security, health | Threat modeling, penetration testing |
| Step 12 | COMPLIANCE | Produce IEC 62443 compliance artifacts: security requirements specification (SRS | Standards mapping, DHF, traceability |
| Step 13 | EMBEDDED_TEST | Write firmware unit tests (Zephyr Twister + Unity) for: MAX30102 driver mock, Sp | Hardware-in-the-loop verification |
| Step 15 | QA | Design and execute system QA test plan: end-to-end scenarios covering device pai | Verification & validation |
| Step 16 | SYSTEM_TEST | Execute system-level integration tests: BLE stack interoperability on 5 device m | End-to-end validation, performance |

**Total tasks:** 20 | **Compliance tasks:** 5 | **Coverage:** 25%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | FCC Part 15 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | CE Mark compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 4 | HIPAA compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |

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
| developer | 5 | Engineering |
| qa_engineer | 3 | Engineering |
| firmware_engineer | 2 | Engineering |
| regulatory_specialist | 2 | Compliance |
| marketing_strategist | 1 | Operations |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| data_scientist | 1 | Analysis |
| system_tester | 1 | Engineering |
| devops_engineer | 1 | Engineering |
| localization_engineer | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 48/100 (FAIL) — 1 iteration(s)

**Summary:** This plan is well-structured at the software architecture level and shows genuine domain knowledge in firmware, ML, and mobile development. However, it contains a fundamental regulatory misclassification that could block market entry entirely: IEC 62443 is the wrong standard for a consumer wearable, and SpO2 measurement almost certainly requires FDA 510(k) clearance rather than a wellness disclaimer — a decision that must be made before Step 2 is finalized, not retrofitted at Step 12. The entire hardware development pipeline is absent: there is no PCB design, first article build, FCC/CE/Bluetooth SIG certification, or battery safety certification track, yet firmware development in Steps 5-6 implicitly assumes validated hardware exists. The deployment spec has a concrete error (TimescaleDB on AWS RDS is not supported). The firmware and PRD accuracy targets contradict each other and will cause late-stage integration failures. The ML training data (MESA dataset) is demographically mismatched to the target users. For a product that outputs health numbers and SpO2 readings to consumers, the 5-subject sleep staging validation and the missing risk management file (ISO 14971) are not just gaps — they are the difference between a defensible product and a liability. Score: 48. Fundamental rework is needed on the regulatory classification decision, hardware development track, and security key management before this plan can credibly reach production.

### Flaws Identified

1. IEC 62443 is an industrial automation/control systems cybersecurity standard — it does not apply to a consumer fitness wearable. The correct standards are IEC 62304 (medical device software lifecycle), ISO 14971 (risk management for medical devices), and IEC 60601-1-2 for EMC if SpO2 claims are made. Mapping to the wrong standard produces compliance artifacts that are worthless and potentially misleading to regulators.
2. SpO2 measurement is NOT a wellness feature. FDA classifies pulse oximeters under 21 CFR 880.2890 (Class II, 510(k) required) or requires De Novo petition. The plan's 'FDA wellness device guidance' flag is a category error. Shipping a device that measures SpO2 without 510(k) clearance exposes the company to enforcement action. The 'not for diagnostic use' disclaimer does not substitute for premarket authorization when the device outputs a specific SpO2 percentage.
3. Firmware acceptance criteria in Step 5 allow ±5 bpm / ±3% SpO2, but the PRD (Step 2) requires ±2 bpm / ±2% SpO2. The firmware team is building to tolerances that will fail product-level acceptance. This contradiction will surface late in integration testing.
4. No hardware development pipeline exists. There is no step for schematic design, PCB layout, component sourcing, first article build, or hardware bring-up. Firmware development (Steps 5-6) assumes validated hardware exists. For a new wearable product, hardware bring-up typically takes 3-6 months and is on the critical path before any firmware can run on target silicon.
5. Bluetooth SIG qualification (QDID/DID listing) is mandatory for any product using Bluetooth. Not mentioned anywhere in the plan. Without qualification, the product cannot legally carry the Bluetooth name/logo and risks BLE stack interop failures that are undebuggable without knowing the qualification status.
6. FCC Part 15 (US) and CE RED Directive (EU) certifications for RF devices are not mentioned. Pre-certification typically requires 6-12 weeks with an accredited test house. Missing this blocks market entry regardless of software readiness.
7. TimescaleDB is not natively available as an AWS RDS extension. Step 17 specifies 'AWS RDS PostgreSQL + TimescaleDB extension' — this requires either Timescale Cloud, a self-managed EC2 deployment, or Aurora PostgreSQL with unofficial extension loading. The infra spec will fail at provisioning time.
8. MESA dataset (Step 9) is a cardiovascular outcomes study in adults aged 45-84. Using it as primary training data for a fitness wearable targeting athletes and health-conscious consumers introduces severe demographic bias. Sleep quality models trained on MESA will systematically mis-score younger, fitter users.
9. OTA update mechanism is listed as an acceptance criterion in BOTH Step 5 and Step 6 — duplicated across two separate firmware implementation steps with no distinction. This is unowned work that will be deferred by both implementers.
10. Live workout HR WebSocket architecture (Step 8) routes BLE data from device → mobile app → backend → WebSocket → mobile app. The mobile app already has the BLE data directly; this round-trip adds 200-500ms latency and backend load for data that's already on-device. The <500ms latency acceptance criterion may fail due to this architectural choice.
11. Android BLE reliability at 99.5% sync success rate (Step 2) is not achievable across the device matrix in Step 16 (Xiaomi 14, OnePlus 12) without per-device workarounds. AOSP BLE stack divergence on Chinese OEM devices routinely causes connection drops and MTU negotiation failures. The PRD target will be a permanent miss metric.
12. Sleep staging validation on 5 subjects (Step 6) provides near-zero statistical power for a product accuracy claim. 5-subject PSG pilots produce confidence intervals of ±15-20% on epoch-by-epoch accuracy. The ≥80% target has no meaningful confidence bound and cannot be used to support a product claim.
13. Step 3 (UX) requires an accessibility audit for WCAG 2.1 AA but Step 10 (mobile app) lists accessibility as an acceptance criterion via VoiceOver/TalkBack only. There is no explicit WCAG audit step for the mobile app — WCAG 2.1 AA applies to mobile apps under ADA/EAA, not just web. The gap between 'wireframe audit' and 'shipped app audit' is unowned.
14. BLE background sync on iOS is severely restricted by CoreBluetooth. Background execution time is capped, central scanning is not permitted in background, and BLE sync requires the peripheral to re-advertise after a connection drop. None of the Flutter/iOS BLE steps address background mode entitlements, state restoration, or the 'use-bluetooth-peripheral' background mode configuration. The 7-day offline sync scenario (E2E-003) will fail on iOS unless the user keeps the app foregrounded.
15. HIPAA is not addressed. If the backend stores SpO2 and HR data for US users and the business model involves healthcare context (even indirect), HIPAA Business Associate Agreement obligations may apply. The plan's GDPR-only compliance posture creates legal exposure for US market launch.

### Suggestions

1. Replace IEC 62443 throughout with the correct stack: IEC 62304 for software lifecycle, ISO 14971 for risk management, and IEC 60601-1-2 for electromagnetic compatibility. Engage a regulatory consultant before Step 2 is finalized.
2. Add a regulatory classification step (Step 0) before PRD: determine FDA device classification for SpO2 feature, decide between 510(k) pathway or 'wellness only' with SpO2 feature removed, and document the decision with legal review. Do not commit to SpO2 as a shipped feature without this decision.
3. Add a Hardware Development track as Steps 4a-4c: schematic design, PCB layout/review, component procurement and first article build. These are pre-conditions for Steps 5-6. The firmware steps cannot start without target hardware.
4. Add FCC/CE/Bluetooth SIG certification to the dependency graph. These should block the system test step (Step 16) and launch. Engage a test house at Step 4 to reserve slots 6 months out.
5. Fix TimescaleDB deployment: choose Timescale Cloud (managed, fully supported) or document the self-managed EC2 approach with HA configuration. Remove 'AWS RDS + TimescaleDB extension' as it will not work.
6. Replace MESA as primary training data with SHHS (Sleep Heart Health Study) or NSRR datasets which include younger adults and athletes. Augment with PhysioNet waveform data for PPG-specific features. Document dataset demographic distribution explicitly in the model card.
7. Reconcile firmware vs PRD accuracy targets in Step 2 review: either tighten firmware acceptance criteria to match PRD (±2 bpm, ±2% SpO2) or update PRD to reflect what the hardware can realistically achieve with MAX30102.
8. Refactor Step 8 WebSocket to a direct BLE→app display path for live workout HR. The backend WebSocket should receive forwarded data from the mobile app for cloud recording, not serve as the display path. This reduces latency and eliminates a single point of failure during live workouts.
9. Add iOS BLE background mode configuration to Step 10 acceptance criteria: 'use-bluetooth-peripheral' entitlement configured, Core Bluetooth state restoration implemented, reconnection logic handles CBManagerState.poweredOff transitions.
10. Increase sleep staging validation cohort to ≥20 subjects for a publishable accuracy claim. Consider partnering with a sleep clinic for PSG validation data early (Step 6 dependency).

### Missing Elements

1. Hardware development pipeline: schematic, PCB layout, BOM, first article build, hardware bring-up. This entire track is absent.
2. FCC Part 15 / IC RSS-210 (CA) / CE RED Directive (EU) radio certification plan with test house engagement and timeline.
3. Bluetooth SIG qualification process (QDID listing) — required before product launch.
4. Regulatory classification decision document: FDA device class for SpO2, 510(k) vs De Novo vs wellness-only scope decision.
5. ISO 14971 risk management file: hazard identification, risk estimation, risk control measures for SpO2 mis-reading, HR alarm failure, battery thermal runaway.
6. Battery safety certification (UN 38.3 for LiPo transport, IEC 62133 for portable batteries) — blocks shipping product internationally.
7. Manufacturing readiness review (MRR) and Design for Manufacturing (DFM) checklist — no mention of how firmware + hardware transition to volume production.
8. Privacy impact assessment (DPIA under GDPR Art. 35) — SpO2 and health data are special category data under GDPR Art. 9, requiring DPIA before processing begins, not just GDPR-compliant schema design.
9. Data residency and sovereignty plan — where health data is stored matters for EU (GDPR), China (PIPL), and other regulated markets. Not addressed in infra step.
10. Device identity provisioning infrastructure — how are device certificates/keys burned at manufacturing time? Referenced as an acceptance criterion in Step 11 but the provisioning system and key management HSM are not designed anywhere.
11. Secure boot chain for firmware — Step 11 mentions 'firmware signing enabled' but there is no step designing the root of trust, key ceremony, or secure bootloader for nRF5340.
12. Post-market surveillance plan — for any device making health claims, a PMS process is required by both FDA and EU MDR. Not mentioned.
13. App store health entitlements review — Apple HealthKit and Google Health Connect have specific review requirements and privacy nutrition label disclosures for health data apps. No step addresses this.
14. Infrastructure cost model — Step 17 provisions Multi-AZ RDS + EKS + GPU nodes with zero cost estimate. At 10K users this architecture runs $8K-15K/month minimum. Needs validation against business model before provisioning.

### Security Risks

1. Device identity and firmware signing are referenced only in Step 11 acceptance criteria ('Device identity provisioned', 'Firmware signing enabled') but no step actually designs or implements the PKI, HSM, or secure element key provisioning. If these are checked as 'done' at Step 11 without implementation artifacts, the OTA mechanism in Step 17 is unsigned and vulnerable to firmware injection attacks.
2. BLE LE Secure Connections with passkey entry (Step 11) requires the device to have a display or input mechanism. If the wearable has no display (common for slim form factors), LESC with passkey is not possible — the fallback is Just Works pairing which provides no MITM protection. The hardware UX must be defined before the BLE security model is finalized.
3. Certificate pinning (Step 11) on mobile apps requires a rotation strategy. The plan has no certificate rotation or pinning bypass mechanism for emergency revocation. Pinned certs that expire in production cause app-wide outages for all users simultaneously.
4. JWT RS256 with refresh token rotation (Step 8) — the plan doesn't specify where private keys are stored on the mobile client. If stored in SharedPreferences (Android) or UserDefaults (iOS) without Keystore/Keychain backing, private key extraction via rooted device is trivial on health data.
5. ML model inversion risk (Step 9) is listed as in scope for the threat model but the isolation forest anomaly detector running on user SpO2 data is a membership inference attack surface. No mitigations are described beyond flagging it as a risk area.
6. The health insights coordinator agent (Step 20) POSTs SpO2 anomaly proposals to the SAGE approval queue. If the approval queue is compromised or an attacker can inject proposals, they could suppress health alerts (delayed notification of real SpO2 dips) — a patient safety risk if the product is used for any health monitoring purpose.
7. ONNX model files served via the ML microservice have no integrity verification step described. A supply chain compromise of the ONNX model file would silently corrupt all health scores without triggering any monitoring alert.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.324799
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

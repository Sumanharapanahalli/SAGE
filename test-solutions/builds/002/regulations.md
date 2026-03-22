# Regulatory Compliance — Insulin Pump Controller

**Domain:** medtech
**Solution ID:** 002
**Generated:** 2026-03-22T11:53:39.306366
**HITL Level:** strict

---

## 1. Applicable Standards

- **FDA Class III**
- **ISO 13485**
- **IEC 62304**
- **ISO 14971**

## 2. Domain Detection Results

- medtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 2 | REGULATORY | Develop regulatory strategy and submission pathway for FDA Class III PMA | Submission preparation, audit readiness |
| Step 3 | LEGAL | Establish IP landscape review, patent clearance, and regulatory compliance legal | Privacy, licensing, contracts |
| Step 5 | SAFETY | Perform preliminary hazard analysis and establish risk management plan per ISO 1 | Risk management, FMEA, hazard analysis |
| Step 6 | COMPLIANCE | Establish Design History File structure and IEC 62304 software development lifec | Standards mapping, DHF, traceability |
| Step 23 | SECURITY | Conduct comprehensive threat model and cybersecurity risk assessment per FDA cyb | Threat modeling, penetration testing |
| Step 24 | EMBEDDED_TEST | Develop HIL test specification, firmware unit test suite, and software integrati | Hardware-in-the-loop verification |
| Step 25 | QA | Execute firmware unit tests, integration tests, and HIL test campaigns against b | Verification & validation |
| Step 26 | EMBEDDED_TEST | Execute automated firmware regression suite and performance benchmarks on target | Hardware-in-the-loop verification |
| Step 27 | SYSTEM_TEST | Execute end-to-end system integration test campaign across firmware, backend, an | End-to-end validation, performance |
| Step 28 | COMPLIANCE | Compile Design History File with complete design controls evidence and IEC 62304 | Standards mapping, DHF, traceability |
| Step 29 | COMPLIANCE | Build requirements traceability matrix linking user needs through design to veri | Standards mapping, DHF, traceability |
| Step 30 | SAFETY | Complete ISO 14971 risk management activities: risk evaluation, risk controls ve | Risk management, FMEA, hazard analysis |
| Step 32 | REGULATORY | Prepare and compile FDA PMA submission package with all required modules | Submission preparation, audit readiness |

**Total tasks:** 35 | **Compliance tasks:** 13 | **Coverage:** 37%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | FDA Class III compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | ISO 13485 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | IEC 62304 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 4 | ISO 14971 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 19 | Engineering |
| analyst | 14 | Analysis |
| planner | 2 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 52/100 (FAIL) — 1 iteration(s)

**Summary:** This plan is architecturally coherent and demonstrates genuine expertise in medical device development — the coverage of IEC 62304 lifecycle, ISO 14971 risk management structure, DHF organization, and regulatory documentation is above average for an AI-generated build plan. However, it cannot ship as a PMA-approved FDA Class III device because it is missing the single most important element: a clinical trial. No pivotal clinical data means no Class III PMA approval, regardless of how complete the technical documentation is. This is not a minor gap — it is a multi-year, multi-million-dollar program element that requires IDE approval before it can begin, and that entire pathway is absent from all 35 steps. Secondary critical gaps include missing hardware prototype testing cycles (the plan goes from schematic to system test through simulation only), absent biocompatibility and accredited EMC testing, no manufacturing process validation, an ML integration step that is developed but never reintegrated into the validated firmware, and a security threat modeling step positioned at the end of the build rather than at the architecture stage. Scoring at 52: the regulatory and software lifecycle scaffolding is solid enough to build from, but the clinical evidence pathway gap alone makes this plan unbuildable to FDA approval without fundamental restructuring.

### Flaws Identified

1. FATAL: No clinical trial / IDE pathway. FDA Class III PMA for a novel automated insulin delivery (AID) system requires Investigational Device Exemption (IDE) application, IRB approval, and actual pivotal clinical trial execution with enrolled human subjects. The plan has 'clinical studies protocol' as a PMA module deliverable (step 32) but zero steps for IDE submission, trial execution, patient enrollment, data collection, or clinical study report authoring. FDA will not approve a Class III AID device without this evidence — full stop.
2. No hardware prototype build/bring-up cycle. The plan jumps from PCB schematic (step 9) directly to firmware development (step 12) and then to system test (step 27) with no explicit EVT/DVT/PVT (Engineering Verification Test / Design Verification Test / Production Verification Test) stages. Real hardware has bring-up issues, power sequencing failures, silicon errata, and component incompatibilities. Simulation-only validation of firmware is insufficient for FDA Class III V&V evidence.
3. ML model integration back into firmware is a missing step. Step 16 (ML model development) depends on step 15 (firmware) and produces a quantized model for STM32H7. But there is no subsequent step to integrate that model into the firmware build, re-test the integrated system, or validate the inference engine in-situ. The model is developed and then orphaned from the firmware pipeline.
4. Biocompatibility testing (ISO 10993) is mentioned in the PMA module (step 32) but has no execution step. For a Class III device with a transcutaneous infusion catheter and reservoir in contact with body tissue and fluids, a full ISO 10993 biocompatibility evaluation (cytotoxicity, sensitization, genotoxicity, implantation as applicable) is required. This is a multi-month testing program requiring external lab engagement.
5. Actual IEC 60601-1-2 EMC testing is absent. Step 9 has an 'EMC pre-compliance plan' and step 33 has 'EMC pre-compliance test.' Pre-compliance testing at an in-house bench is not acceptable for FDA submission. Accredited third-party lab testing per IEC 60601-1-2 (radiated/conducted emissions, immunity) is mandatory. No step allocates for this.
6. Threat modeling (step 23) comes after the system is fully built (depends on steps 15, 17, 20). Security-by-design requires STRIDE analysis during architecture definition (step 7), not post-implementation. Finding BLE spoofing or replay attack vulnerabilities after the protocol stack is finalized and firmware is written means expensive redesign. This ordering error is a textbook mistake in medical device security programs.
7. STM32H7 and Nordic nRF5340 are specified as separate chips with no inter-chip security specification. CGM glucose data arriving over BLE on the nRF5340 must transit to the STM32H7 via SPI or UART. This internal bus is never described, secured, or included in the threat model. An attacker with physical access who spoofs CGM readings on this internal bus can cause fatal insulin over-delivery — the most critical attack vector in the system.
8. Manufacturing process validation (IQ/OQ/PQ) is entirely absent. 21 CFR Part 820.75 requires process validation for processes whose results cannot be fully verified by subsequent inspection. Pump assembly, sterilization of infusion components, and calibration of insulin delivery are all such processes. Step 34 covers operator training but not process validation protocols or execution.
9. Acceptance criteria in step 5 list 'ISO 14971 risk management file complete' and 'Residual risk acceptable' as exit criteria for the PRELIMINARY hazard analysis step. These are final risk management outcomes that belong in step 30, not step 5. This creates false closure — a QA reviewer could sign off on step 5 believing the risk file is complete when it is not.
10. Steps 28 and 29 both repeat 'DHF structure created' and 'V&V protocol drafted' as acceptance criteria. These artifacts are supposed to be created in step 6. Repeating them in steps 28-29 (post-system test) either means they were never actually created in step 6 or these criteria are copy-paste errors that will confuse DHF auditors and obscure traceability.
11. No design freeze gate defined. There is no explicit step that triggers design freeze and initiates formal change control before V&V begins. Changes made during steps 24-27 (testing) without a documented design freeze create 21 CFR Part 820.30 compliance risk: what version was validated?
12. Summative usability evaluation (step 33, 15 participants) has no prerequisite step for participant recruitment, IRB/ethics approval for human subjects testing, or scheduling. IRB approval alone can take 4-12 weeks. This step will block the validation timeline with no allocated time.
13. React Native's ability to wake device from lock screen for critical alarms is not guaranteed. iOS limits background execution and Do Not Disturb overrides non-system apps. Android OEM battery optimizations kill background processes. Step 20's acceptance criterion 'critical alarm screen wakes device from lock screen' is stated as if it is trivially achievable — it is one of the hardest UX requirements in medical mobile app development and requires platform-specific native code, often requiring Apple's Critical Alerts entitlement and equivalent Android workarounds. None of this complexity is reflected in the step.
14. STM32H7 LSTM inference at 100ms with full 24-hour CGM history as input features is not validated for feasibility. STM32H7 has ~1MB RAM and 2MB Flash in common variants. An LSTM with attention operating on 288 timesteps (24hr at 5-min intervals) x multiple features will require careful quantization. Step 16's acceptance criterion of 'quantized model fits within STM32H7 RAM and flash constraints' is listed as a check, not a design constraint — there is no analysis confirming it is achievable before 5 preceding firmware steps are built assuming it works.
15. No CGM manufacturer interoperability agreement pathway. Integrating with a commercially available CGM (Dexcom, Abbott) for a PMA submission requires either the CGM being listed as an accessory/component with appropriate predicate, or demonstrated interoperability under FDA's iCGM special controls (21 CFR 862.3570). The plan treats this as a technical protocol implementation when it is also a regulatory and commercial licensing challenge.

### Suggestions

1. Insert an IDE Application step between steps 2 and 5. Draft IDE sections (risk analysis, clinical protocol, device description, informed consent templates) in parallel with regulatory strategy. Clinical enrollment cannot begin until FDA grants IDE — model this as a critical path gate.
2. Add an explicit Hardware Prototype Bring-Up step after step 9 and before step 12. Scope it: board assembly, power rail verification, JTAG debug bring-up, peripheral loopback tests, thermal characterization. This is where 30-40% of hardware issues surface.
3. Add a step for ML model firmware integration and regression test after step 16. This step takes the quantized model artifact, integrates it into the IEC 62304-compliant firmware build, and re-executes the full test suite from steps 24-25 against the integrated system.
4. Move threat modeling (step 23) to depend on step 7 (architecture), not steps 15/17/20. Security controls must inform design, not audit it. The architectural security review should produce threat mitigations that are baked into steps 12-17.
5. Add a step for ISO 10993 biocompatibility testing program. Scope: identify all patient-contacting materials, classify tests required, contract with accredited biocompatibility lab, execute testing. This runs in parallel with firmware development and typically takes 3-6 months.
6. Add a step for IEC 60601-1-2 EMC testing at an accredited laboratory. Schedule this after prototype hardware is stable (post-DVT). Budget 6-10 weeks for lab scheduling, testing, and report generation.
7. Add a Manufacturing Process Validation step. Define IQ/OQ/PQ protocols for pump assembly, calibration, and any sterilization processes. This is a 21 CFR Part 820.75 requirement and a common PMA deficiency.
8. Add a Design Freeze milestone step between steps 27 and 28. Explicitly lock the configuration baseline, enumerate all open defects with disposition, and require formal approval before DHF compilation begins.
9. Define the STM32H7↔nRF5340 internal protocol in step 7 (Interface Control Document) and add it to the threat model. Consider authenticated message authentication codes (HMAC) on all internal insulin delivery commands.
10. For the mobile app alarm wakeup requirement, add a spike investigation task before step 20. Verify iOS Critical Alerts entitlement availability, Android foreground service behavior across target OEM skins (Samsung OneUI, Xiaomi MIUI), and document the implementation approach and its limitations in the use specification.
11. Add an EU MDR pathway track if international commercialization is in scope. EU Class III equivalent (Annex IX) requires Notified Body engagement and a Clinical Evaluation per MEDDEV 2.7/1 Rev 4 — not the same as FDA PMA and cannot be retrofitted easily.
12. Validate STM32H7 ML feasibility before committing to the architecture. Run a benchmark of the quantized LSTM on the actual target MCU variant selected (specific part number matters) as a step 7 output. If it fails, the architecture choice needs to change before 8 firmware steps are built around it.

### Missing Elements

1. IDE (Investigational Device Exemption) application and FDA approval step — prerequisite for any human clinical testing
2. Clinical trial execution step (enrollment, data collection, monitoring, statistical analysis, clinical study report)
3. ISO 10993 biocompatibility testing program with accredited lab
4. IEC 60601-1-2 EMC/electrical safety testing at accredited third-party lab
5. IEC 60601-1-8 alarm testing (auditory alarm loudness, alarm signal characteristics) — not just hierarchy definition
6. Hardware prototype bring-up and hardware verification test (EVT/DVT cycle)
7. Manufacturing process validation (IQ/OQ/PQ per 21 CFR 820.75)
8. ML model → firmware integration step post-step 16
9. Design freeze gate with formal configuration baseline
10. IRB/ethics approval for summative usability study (human subjects research requirement)
11. CGM manufacturer interoperability agreement or iCGM predicate analysis
12. EU MDR pathway (Notified Body engagement, EU Clinical Evaluation) if non-US markets targeted
13. Software of Unknown Provenance (SOUP) validation plan — step 12 lists 'SOUP components listed' as criteria but no step plans the SOUP validation activities required by IEC 62304 Section 8
14. Post-production surveillance data collection system setup (not just the plan — the actual technical implementation of adverse event data collection)

### Security Risks

1. CRITICAL: STM32H7↔nRF5340 internal SPI/UART bus carries glucose readings that directly drive insulin delivery. If unprotected, physical access allows glucose value injection causing potentially fatal overdose. No HMAC or message authentication is specified for this bus.
2. CRITICAL: BLE insulin delivery command injection. Step 20 allows the mobile app to send bolus commands to the pump over BLE. If the BLE pairing/bonding security is misconfigured or the command channel lacks replay protection, an attacker in BLE range could trigger unauthorized bolus delivery. The threat model (step 23) occurs too late to prevent this being designed-in wrong.
3. HIGH: ML model update pathway not cryptographically bound. Step 16 produces a model for embedded deployment, and step 35 mentions OTA firmware updates with signature verification. But there is no specification of how ML model updates (distinct from firmware updates under PCCP) are authenticated and verified before deployment to the device.
4. HIGH: CGM data integrity — no specification of whether CGM readings received over BLE are authenticated. A spoofed CGM broadcasting falsely low glucose values would cause the closed-loop controller to suspend insulin delivery, potentially triggering hyperglycemic crisis. Conversely, falsely high readings cause overdose. The CGMS GATT profile does not natively include authentication.
5. HIGH: React Native JavaScript bundle is not a trusted execution environment for security-critical operations. The bolus confirmation logic running in JavaScript is susceptible to prototype pollution, dependency confusion attacks in the npm supply chain, and dynamic patching. For a device delivering life-critical doses, the confirmation logic should run in native code with attestation.
6. MEDIUM: No specification of secure element or HSM on the device for private key storage. Step 22 uses an HSM for firmware signing in CI, but the device itself needs a secure element (e.g., ATECC608) to store the public key used to verify firmware signatures and to authenticate BLE connections. Without this, key material is stored in STM32H7 flash and extractable via JTAG.
7. MEDIUM: No firmware downgrade attack prevention specified. The bootloader verifies signature (step 12) but does not specify anti-rollback counters. An attacker who extracts an older signed firmware can downgrade the device to a version with known vulnerabilities.
8. MEDIUM: Kafka and TimescaleDB in the data pipeline (step 18) are complex OSS components with their own vulnerability surface. No step specifies patching SLA or vulnerability scanning for the data infrastructure layer, only for the application layer (SBOM in step 23 covers application software, not infrastructure).


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.306436
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

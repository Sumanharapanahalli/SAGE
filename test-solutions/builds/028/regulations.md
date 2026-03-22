# Regulatory Compliance — Autonomous Parking

**Domain:** automotive
**Solution ID:** 028
**Generated:** 2026-03-22T11:53:39.316441
**HITL Level:** strict

---

## 1. Applicable Standards

- **ISO 26262 ASIL B**
- **SAE J3016**
- **UNECE R79**

## 2. Domain Detection Results

- automotive (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 1 | SAFETY | Conduct hazard analysis and risk assessment (HARA) for automated valet parking p | Risk management, FMEA, hazard analysis |
| Step 3 | COMPLIANCE | Establish the ISO 26262 Safety Case framework: create the Design History File (D | Standards mapping, DHF, traceability |
| Step 4 | SECURITY | Perform threat analysis and risk assessment (TARA) per UNECE R155/R156 and ISO/S | Threat modeling, penetration testing |
| Step 17 | EMBEDDED_TEST | Write firmware unit tests for HAL and occupancy grid modules: sensor timing accu | Hardware-in-the-loop verification |
| Step 20 | SYSTEM_TEST | Design and execute system-level integration test suite: mobile app → backend → M | End-to-end validation, performance |
| Step 21 | QA | Execute ISO 26262 software verification plan: static analysis (MISRA C:2012 comp | Verification & validation |
| Step 22 | COMPLIANCE | Produce ISO 26262 V&V evidence package: populate traceability matrix with test r | Standards mapping, DHF, traceability |
| Step 23 | COMPLIANCE | Produce UNECE R155/R156 cybersecurity compliance artifacts: cybersecurity manage | Standards mapping, DHF, traceability |

**Total tasks:** 26 | **Compliance tasks:** 8 | **Coverage:** 31%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | ISO 26262 ASIL B compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |
| 2 | SAE J3016 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | UNECE R79 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 11 | Engineering |
| regulatory_specialist | 3 | Compliance |
| qa_engineer | 3 | Engineering |
| safety_engineer | 2 | Compliance |
| system_tester | 2 | Engineering |
| devops_engineer | 2 | Engineering |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 42/100 (FAIL) — 1 iteration(s)

**Summary:** This plan demonstrates solid systems-level thinking — the dependency graph is logical, the coverage is broad, and including HARA, TARA, HIL, and compliance artifacts shows genuine ISO 26262 literacy. However, it fails the 85+ threshold required for a regulated automotive system on several fundamental grounds that cannot be patched: (1) the hardware stack (HC-SR04, STM32F4, FreeRTOS, ESP32, Raspberry Pi) is entirely composed of non-automotive-qualified components with no ASIL rating or safety manual, making the certification path non-existent without component replacement; (2) three mandatory ISO 26262 work products are missing — software architectural design, FMEDA/hardware safety analysis, and tool qualification; (3) the Independent Safety Assessment, which is mandatory for ASIL B and non-negotiable with certification bodies, is entirely absent; and (4) the HIL platform choice (QEMU/Renode) cannot validate real-time safety function timing, rendering the V&V evidence for EStop and occupancy grid latency inadmissible. The plan is viable as a research prototype or concept demonstrator, but as written it cannot produce an ISO 26262 ASIL B type-approved system. Fundamental rework of the hardware stack selection, addition of missing ISO 26262 work products, and ISA engagement are required before development begins.

### Flaws Identified

1. HC-SR04 is a hobby-grade sensor with no automotive qualification, no FMEDA report, and no ASIL rating. Using it as the primary sensing modality in an ASIL B system is a certification blocker. ISO 26262 Part 8 requires that COTS hardware be evaluated — HC-SR04 has no safety manual, no FIT rate data, and no diagnostic coverage metrics. An OEM certifying body will reject this immediately.
2. STM32F4 is not a safety-certified MCU for ASIL B motion control. The plan needs AURIX TC3xx (Infineon), TMS570 (TI), or RH850 (Renesas) — MCUs that ship with safety manuals, FMEDA reports, and certified peripheral libraries. STM32F4 has no safety manual and no ISO 26262 support package from ST.
3. Standard FreeRTOS is not ASIL B certified. SAFERTOS (from WITTENSTEIN) is the qualified variant with a safety manual and certified kernel. Using vanilla FreeRTOS in ASIL B motion control is a mandatory violation of ISO 26262 Part 6 (software tool/OS qualification). This alone fails the certification audit.
4. ESP32 and Raspberry Pi 4 are explicitly not suitable for safety-critical roles. The plan uses 'STM32H7_or_Raspberry_Pi4' for path planning and ESP32/SIM7600 for comms — both 'or' choices and neither is ASIL-qualified. Linux-based SBCs cannot host ASIL B functions without extensive qualification effort not addressed anywhere in the plan.
5. No formal software architectural design step. ISO 26262 Part 6 clause 7 mandates a software architectural design work product covering component interfaces, data flows, concurrency, and freedom from interference. The plan jumps from PRD (step 2) directly to simulation (step 6) and firmware (step 8) with no architectural design phase.
6. No FMEDA (Failure Mode Effects and Diagnostic Analysis) for the hardware system. ASIL B requires a hardware architecture that meets PMHF < 10^-7 per hour. The plan has FMEA in step 1 but no system-level FMEDA with FIT rates and diagnostic coverage metrics to demonstrate the hardware safety architecture is compliant.
7. No tool qualification plan. ISO 26262 Part 8 requires that software tools (ARM-GCC, PC-lint/Cppcheck, VectorCAST/LDRA for MC/DC coverage) be qualified at TQL-1 through TQL-3. Mentioning tools by name without a Tool Qualification Plan (TQP) means the coverage and static analysis results are inadmissible as ISO 26262 evidence.
8. No Independent Safety Assessment (ISA). ISO 26262 Part 2 clause 6 requires an independent functional safety assessment for ASIL B systems. This is a mandatory external review by an assessor independent from the development team. Completely absent from the plan.
9. BLE 5.0 is non-deterministic and unsuitable as the transport layer for safety-critical vehicle motion commands. BLE has undefined latency variance, susceptibility to interference, and no QoS guarantees. The 1500ms heartbeat timeout is dangerously long — a vehicle traveling at 10 km/h covers 42cm in that window with no stop command.
10. AUTOSAR compliance is listed as an acceptance criterion in steps 8-12 but there is no AUTOSAR architecture design step anywhere. AUTOSAR Classic Platform requires SWC definition, RTE configuration, BSW stack selection, and ARXML tooling. This is a months-long effort that cannot be a checkbox at the end of firmware implementation.
11. The HIL platform choice (QEMU/Renode) is insufficient for timing validation of safety functions. These are instruction-set simulators, not cycle-accurate hardware emulators with real-time guarantees. Validating 50ms EStop latency or 10Hz occupancy grid update rates on QEMU produces results that do not transfer to real hardware. Production automotive HIL uses dSPACE SCALEXIO or NI PXI-based systems.
12. No physical hardware validation phase. The plan goes directly from HIL simulation to compliance documentation with no EMC testing, environmental testing (temperature -40°C to +85°C for automotive), vibration/shock testing, or IP rating validation. ISO 26262 Part 4 requires hardware integration testing and validation on real hardware.
13. ASIL decomposition strategy is undefined. ASIL B can be achieved through ASIL B single-channel or ASIL A + ASIL A dual-channel decomposition. This architectural choice determines the entire hardware and software redundancy design. Deferring this to step 3 compliance setup, after sensors and MCU are already chosen, means the architecture may be incompatible with the decomposition strategy chosen.
14. Step 20 targets EStop-from-mobile within 500ms. The budget is not allocated per layer: mobile BLE stack + network stack + MQTT broker processing + vehicle MQTT client + CAN + brake actuator response. Without per-layer allocation and worst-case analysis, this target is unverifiable and likely unachievable over public internet paths.
15. Single sensor modality (ultrasonic only) for ASIL B in a valet parking environment. Ultrasonic sensors are affected by temperature gradients, high humidity, soft materials (clothing, foam), and cross-talk from other vehicles' sensors. 'camera_optional' is insufficient — ASIL B pedestrian protection requires redundant sensing. No sensor fusion architecture is defined.

### Suggestions

1. Replace HC-SR04 with automotive-grade ultrasonic sensors that include FMEDA reports and FIT rate data — Bosch UPA, Continental USS, or Valeo Ultrasound sensors. Add a formal COTS component evaluation step per ISO 26262 Part 8.
2. Replace STM32F4 with a qualified safety MCU: Infineon AURIX TC375 (ASIL D capable, includes safety manual + FMEDA) or TI TMS570LC4357. Add an MCU selection and qualification step early in the plan, before firmware implementation.
3. Replace FreeRTOS with SAFERTOS (FreeRTOS kernel with ASIL D safety certification package from WITTENSTEIN). This is a drop-in replacement — the API is identical. Budget for the SAFERTOS license.
4. Add a dedicated Software Architectural Design step between PRD (step 2) and firmware implementation (step 8). This step must produce: component diagram, interface definitions, data flow diagrams, freedom-from-interference analysis, and OS/BSW selection rationale.
5. Add a Hardware Safety Analysis step to produce FMEDA with FIT rates from supplier data sheets, calculate PMHF/SPFM/LFM metrics, and confirm ASIL B hardware architectural metrics compliance (PMHF < 10^-7/h).
6. Add a Tool Qualification Plan (TQP) step that classifies each tool (ARM-GCC, PC-lint, coverage tool) by tool confidence level (TCL) and tool impact (TI), and produces qualification evidence per ISO 26262 Part 8 clause 11.
7. Add an Independent Safety Assessment milestone at step 22, with external assessor engagement planned from step 1. The ISA needs access to all work products from HARA through V&V evidence — they must be contracted early.
8. Replace QEMU/Renode HIL with a proper real-time HIL platform (dSPACE SCALEXIO, Speedgoat, or NI VeriStand) that provides deterministic timing. If budget is a constraint, at minimum run firmware on actual target hardware with physical sensor simulation injected via CAN.
9. Define the ASIL decomposition strategy in step 1 or as a new step 1.5. Document whether the system uses single-channel ASIL B or dual-channel ASIL A+A decomposition. This decision must precede hardware selection.
10. For the comms gateway, move EStop to an independent hardware path (dedicated CAN message or discrete digital signal) that does not depend on the BLE/MQTT chain. Safety-critical stop commands must be independent of the same channel used for normal operation.
11. Add camera (or short-range radar) as a mandatory secondary sensor for pedestrian detection, and define a sensor fusion architecture. Treat ultrasonic as primary for proximity, camera as cross-check for pedestrian classification — assign separate ASIL levels per function.
12. Replace the SAGE HITL gate for motion commands with a proper AUTOSAR-compliant supervision mechanism on the firmware side. A cloud-based HITL approval gate (step 16) for individual motion commands will make the system unusable — this is appropriate for firmware deployment, not per-maneuver motion control.

### Missing Elements

1. MCU and hardware component selection and qualification step (ISO 26262 Part 8 COTS evaluation)
2. Software architectural design work product (ISO 26262 Part 6 clause 7 — mandatory)
3. ASIL decomposition decision and rationale document
4. FMEDA with FIT rates and hardware architectural metrics (PMHF, SPFM, LFM)
5. Tool Qualification Plan (TQP) for ARM-GCC, static analysis, and coverage tools
6. Independent Safety Assessment (ISA) engagement and milestone
7. Physical hardware integration and validation testing (EMC, environmental, vibration)
8. OTA update safety case: what happens to the safety certification when firmware is updated post-deployment? ISO 26262 requires a documented change impact analysis for every OTA
9. Parking lot infrastructure requirements: fixed sensor nodes, wireless AP placement, lot-side controller, marking/signage — the vehicle system alone cannot work without defined infrastructure
10. Safe state definition: what is the system's safe state for each hazard? 'Apply brakes' is not sufficient — needs formal safe state specification per safety goal
11. Degraded mode operation specification: single sensor failure behavior must be formally specified and validated, not just described as 'graceful speed reduction'
12. Random hardware failure analysis confirming ASIL B hardware targets are met
13. Secure element or HSM specification for HMAC key storage on the vehicle gateway — storing cryptographic keys in ESP32 flash is not acceptable for ASIL B cybersecurity

### Security Risks

1. BLE proximity check (50m) is trivially bypassable with a directional antenna. Proximity authentication via BLE RSSI is not a reliable security control — spoofed RSSI or relay attacks enable unauthorized remote operation of a moving vehicle.
2. 30-minute HMAC session token lifetime is excessive for a vehicle motion command session. A stolen or intercepted token provides a 30-minute window for unauthorized commands. Recommend per-command nonces or maximum 5-minute session tokens tied to active BLE proximity.
3. MQTT without client certificate authentication. The plan specifies TLS 1.3 for mobile-to-cloud but the cloud-to-vehicle MQTT path only mentions 'TLS_1.3_MQTT' without specifying mutual TLS (mTLS). A malicious MQTT client on the same broker can subscribe to vehicle command topics.
4. No certificate pinning specified for the mobile app. Without pinning, a compromised CA or network MITM can intercept JWT tokens and inject commands.
5. Ultrasonic sensor spoofing (listed in TARA attack surfaces) has no firmware-side mitigation in the firmware steps 8-12. The acceptance criteria for spoofing resistance are only in the TARA document — no runtime detection, plausibility checking, or cross-sensor validation is implemented.
6. CAN bus access control 'requirements defined' (step 4) but no SecOC (Secure Onboard Communication) implementation step exists. Without MAC authentication on CAN frames, a physical access attack (OBD port, aftermarket device) can inject motion commands directly.
7. SBOM in step 23 is generated post-development. CVE exposure from open-source components (FreeRTOS/SAFERTOS, MQTT client libraries, React Native dependencies) should be tracked from step 1 with a dependency pinning and audit policy from the start.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.316477
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

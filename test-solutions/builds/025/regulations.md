# Regulatory Compliance — V2X Communication

**Domain:** automotive
**Solution ID:** 025
**Generated:** 2026-03-22T11:53:39.315383
**HITL Level:** strict

---

## 1. Applicable Standards

- **SAE J2735**
- **SAE J3161**
- **IEEE 802.11p**
- **ETSI ITS**

## 2. Domain Detection Results

- automotive (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 2 | SAFETY | Conduct HARA (Hazard Analysis and Risk Assessment) per ISO 26262 Part 3 for all  | Risk management, FMEA, hazard analysis |
| Step 3 | COMPLIANCE | Produce Design History File skeleton and regulatory compliance matrix for UNECE  | Standards mapping, DHF, traceability |
| Step 4 | SECURITY | Threat model the V2X stack using STRIDE. Cover BSM spoofing/replay, SPAT signal  | Threat modeling, penetration testing |
| Step 21 | EMBEDDED_TEST | Design and implement HIL (Hardware-in-the-Loop) test harness for OBU firmware: c | Hardware-in-the-loop verification |
| Step 22 | EMBEDDED_TEST | Write firmware unit tests for all RTOS tasks and HAL modules using Unity + CMock | Hardware-in-the-loop verification |
| Step 24 | SYSTEM_TEST | Execute end-to-end system validation scenarios in the ns-3 + SUMO simulation env | End-to-end validation, performance |
| Step 27 | REGULATORY | Prepare AUTOSAR Classic SWC (Software Component) architecture description in ARX | Submission preparation, audit readiness |
| Step 28 | COMPLIANCE | Produce ISO 26262 Part 6 (software) evidence artifacts: software architecture de | Standards mapping, DHF, traceability |
| Step 31 | QA | Develop V&V test plan and execute functional qualification testing (OQ) for the  | Verification & validation |

**Total tasks:** 32 | **Compliance tasks:** 9 | **Coverage:** 28%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SAE J2735 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | SAE J3161 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | IEEE 802.11p compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 4 | ETSI ITS compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 14 | Engineering |
| qa_engineer | 5 | Engineering |
| regulatory_specialist | 4 | Compliance |
| devops_engineer | 3 | Engineering |
| system_tester | 2 | Engineering |
| business_analyst | 1 | Analysis |
| safety_engineer | 1 | Compliance |
| ux_designer | 1 | Design |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 52/100 (FAIL) — 1 iteration(s)

**Summary:** This is a technically sophisticated and architecturally comprehensive V2X plan that demonstrates genuine domain expertise across firmware, safety, security, and systems engineering. The dependency graph is correct, latency budgets are specific, and the acceptance criteria are measurable. However, it fails the 85+ threshold required for regulated automotive production on several fundamental grounds: ASIL assignments precede the HARA that should generate them (a process violation that would fail an ISO 26262 audit); AUTOSAR Classic and Adaptive are conflated without architectural resolution; the C-V2X PC5 implementation complexity is severely underestimated relative to the single step allocated; the WAVE stack dependency on OpenV2X is a production risk; and OTA firmware update — a hard UNECE R156 requirement — has no implementation step. Beyond these structural issues, SCMS certificate lifecycle, pseudonym privacy, GNSS spoofing defense, and type approval planning are missing. The plan would produce a capable research prototype or proof-of-concept at its current state, but requires fundamental rework in the safety process, AUTOSAR architecture, and compliance implementation before it could pass an automotive homologation audit.

### Flaws Identified

1. ASIL assignments are predefined as inputs to HARA (Step 2 payload lists 'ASIL-B for ICW', 'ASIL-C for EVP' before the hazard analysis runs). ASIL is an OUTPUT of HARA, not a starting assumption. This inverts the ISO 26262 Part 3 process and invalidates the safety case.
2. AUTOSAR Classic R22-11 is used in Step 27 (SWC architecture, AUTOSAR OS tasks, RTE) but AUTOSAR Adaptive R23-11 is set up in Step 5. These are architecturally incompatible. Classic uses AUTOSAR OS/COM/RTE; Adaptive uses POSIX/ara::com/service-oriented communication. The plan never resolves which one the OBU actually uses or defines their boundary.
3. Platooning gap control at 80 km/h with 5 m target gap assigned ASIL-B. At those parameters, a spurious gap-close command or missed emergency dissolve is a rear-end collision at highway speed. ISO 26262 HARA would almost certainly yield ASIL-C or ASIL-D for the gap-control actuator path. ASIL-B is likely underclassified without documented rationale.
4. Step 7 implements C-V2X PC5 sidelink (3GPP TS 36.213/38.885) as a single firmware step with 7 acceptance criteria. PC5 mode 2 autonomous resource selection requires access to modem lower MAC/PHY via proprietary vendor API (Qualcomm QCA9150 SDK, Autotalks CRATON2). These SDKs are under NDA, have their own bugs, and typically take 3-6 months to integrate. The step treats it as equivalent complexity to the DSRC HAL.
5. Step 5 lists 'OpenV2X_reference' as the WAVE stack. OpenV2X is an early-stage open-source project that does not have production-grade IEEE 1609.3 WSMP, complete 1609.2 security, or validated ITS-G5 GeoNetworking. Step 8 then builds protocol layers *above* this stack. If OpenV2X is incomplete or non-conformant, Steps 8-12 are built on a broken foundation.
6. Steps 6 and 7 require physical hardware measurements (SPI ACK, oscilloscope GPIO toggle, SLSS lock timing) against specific boards (NXP S32G eval, Cohda MK6 modem). No step procures or provisions this hardware. The HIL test bench in Step 21 also assumes USRP B210 and SEGGER JLink are available. Hardware lead times in automotive can be 8-20 weeks.
7. SCMS integration is treated as a configuration item across Steps 4 and 8. There is no dedicated step for: enrollment certificate bootstrapping, butterfly key expansion for pseudonym provisioning, linkage authority interaction, or pseudonym certificate pre-loading onto the OBU. The CAMP SCMS REST API is referenced but its certificate lifecycle complexity (enrollment cert → pseudonym request → batch download → rotation) is not designed.
8. Step 24 treats the Linux POSIX x86 firmware port as a trivial variant: 'firmware application logic compiled for Linux.' Porting FreeRTOS-dependent code (RTOS task timing, queue semantics, ISR-safe APIs) to POSIX with correct timing behavior is a non-trivial effort. FreeRTOS POSIX port has known timing jitter that would invalidate latency acceptance criteria (100 ms E2E ICW) if not accounted for.
9. OTA firmware update (UNECE R156 SOTA requirement) is documented in Step 3 as a compliance artifact but never implemented. There is no step that builds the secure boot chain, firmware signing, delta update packaging, rollback mechanism, or update campaign management. This is a significant implementation gap for a production system.
10. Step 14 assumes the WINNER+ B1 channel model and ETSI TS 102 687 DCC algorithm are available in ns-3 3.40 out of the box. Neither is. B1 requires the COST 2100 or similar external module; DCC requires custom implementation. The simulation environment would need to be built first, but this is not captured as a sub-task.

### Suggestions

1. Split Step 2 into two phases: (a) hazard identification and S/E/C rating — producing a draft ASIL table — followed by (b) ASIL assignment and decomposition. Remove the predefined ASIL candidates from the payload and let HARA produce them.
2. Add an explicit architectural decision step (before Step 5) that resolves AUTOSAR Classic vs. Adaptive partitioning: which ECU runs which profile, what is the communication boundary, and which steps apply to which AUTOSAR variant. Without this, Steps 5, 6, 7, 27, and 28 are building on an undefined foundation.
3. Add a dedicated SCMS Integration step after Step 4 covering: enrollment certificate issuance flow, pseudonym certificate download batch size, certificate change triggers (location-based, time-based), and CRL/LCRL pull vs. push strategy. This is 2-3 weeks of work minimum and is load-bearing for all security acceptance criteria.
4. Add a Hardware Procurement and Lab Setup step (prerequisite to Steps 6, 7, 15, 21) listing all required hardware (OBU eval boards, Cohda/Autotalks modems, USRP, RF emulator, JTAG probes) with lead times and fallback simulation paths for each.
5. Add a FreeRTOS POSIX Simulation Layer step between Step 5 and Step 24 to explicitly design the FreeRTOS-to-POSIX abstraction, timing shim, and mock HAL layer used in co-simulation. Define which acceptance criteria are waived in simulation vs. required on target.
6. Elevate UNECE R156 OTA implementation to its own step: secure boot chain design, firmware image signing (Ed25519 or RSA-PSS), delta update packaging, bootloader handoff, rollback-on-failure, and integration with the SCMS for update campaign authorization.
7. Add a spectrum coordination sub-task to Step 5 or Step 6 addressing: the FCC 2020 5.9 GHz reallocation (DSRC now at 5.895–5.925 GHz), CEPT ECC Decision (19)01 for ITS-G5, and coexistence with Wi-Fi in the lower sub-band. Wrong channel configuration will fail FCC Part 90 conformance.
8. Step 12 CACC PID acceptance criterion (RMS gap error ≤0.3 m at 80 km/h) requires vehicle dynamics parameters that don't exist yet in this plan. Add a vehicle dynamics model identification step or scope the HIL test to a specific known vehicle model with documented transfer function.
9. Add explicit penetration testing execution to Step 4 or as a separate step. UNECE R155 Annex 5 requires demonstrated attack resistance, not just a threat model. A signed pentest report from a qualified tester is required for type approval — the threat model alone does not satisfy this.
10. Step 17 misbehavior detection threshold (position jump >50 m/s) only catches trivial spoofing. Add a Sybil attack detection algorithm specification (e.g., ETSI TS 103 759 Section 6 local MBD) and define how it handles low-and-slow spoofing, cooperative false data injection, and position falsification within plausible kinematic bounds.

### Missing Elements

1. FCC Part 90 Subpart M and ETSI EN 302 663 type approval planning: engagement with accredited test lab, estimated timeline (6-18 months), and pre-compliance test strategy. Referenced as a checklist in Step 31 but not planned as an activity.
2. Pseudonym certificate change strategy: when/how the OBU rotates pseudonyms (per SAE J2945/1 Annex B), implications for platoon session continuity (platoon ID tied to certificate?), and privacy analysis showing unlinkability.
3. GNSS timing accuracy specification for C-V2X SLSS: PC5 mode 2 requires <1 μs synchronization accuracy. The plan mentions GNSS_primary but does not specify which GNSS timing signal (PPS output from u-blox F9T vs F9P position output) or the UTC timing chain to modem timing reference.
4. Vehicle dynamics model for CACC tuning: the PID gains in Step 12 cannot be specified without longitudinal vehicle model parameters (mass, drivetrain lag, brake actuator response time). Either a specific vehicle model must be selected or adaptive gain scheduling must be designed.
5. RF spectrum coexistence plan for DSRC + C-V2X hybrid OBU: concurrent operation on the same 5.9 GHz band requires time or frequency domain sharing arbitration not addressed in the radio abstraction layer design.
6. Certificate revocation propagation latency budget: CRL/delta-CRL propagation to OBUs in the field can take seconds to minutes. The security model must define the maximum acceptable revocation latency and how the system behaves during the window between revocation and CRL receipt.
7. Step 15 RF channel emulator hardware budget: R&S CMW500 costs $80,000-$150,000; Spirent Vertex is comparable. If this hardware is not available, Step 15's acceptance criteria (PER vs SNR curves, Doppler tolerance) have no path to completion.
8. NTCIP 1202 TSC simulator: Steps 11 and 23 both require a simulated Traffic Signal Controller responding to SNMP SET. No step creates or procures this simulator. Open-source TSC simulators (e.g., NTCIP-sim) are not production-grade.
9. Fail-operational behavior specification: what happens when the V2X radio fails mid-platoon? The emergency_dissolve state exists but the fail-safe behavior (fall back to radar-only CACC, controlled deceleration, driver takeover alert) is not specified as a requirement.

### Security Risks

1. wolfSSL 5.x ECDSA P-256 implementation: must be verified for constant-time execution on the target SoC to prevent timing side-channel attacks on private key operations. wolfSSL has had CVEs in this area (e.g., CVE-2022-25640). Step 8 specifies the library but no side-channel analysis is planned.
2. BSM pseudonym linkability: if pseudonym certificates are not changed frequently enough or change events are predictable (e.g., always at the same intersection), an attacker can correlate BSMs across certificates and track a vehicle. No privacy analysis or pseudonym change audit is in scope.
3. MQTT broker client certificate rotation: Step 17 specifies mTLS client certificates for RSU-to-cloud MQTT but does not address certificate lifecycle management for the broker's CA. A compromised RSU with a valid client cert can inject arbitrary BSMs into the cloud backend.
4. CRL injection attack: the cloud backend pushes CRLs to SCMS (Step 17). If an attacker can trigger a misbehavior report for a legitimate emergency vehicle, its pseudonym cert could be revoked, blocking EVP. The misbehavior detection threshold and reporting authorization are not hardened against adversarial inputs.
5. OBU firmware update signing key management: when UNECE R156 OTA is eventually implemented, the firmware signing key is the highest-value target in the entire system. HSM-backed key storage and key ceremony procedures are not mentioned anywhere.
6. GPS spoofing against the EKF: Step 13 implements GPS/IMU fusion but the EKF does not include GNSS spoofing detection. A spoofed GNSS signal that moves slowly within EKF innovation bounds will pass through to the BSM position field, enabling false ICW triggers or platoon disruption. GNSS spoofing detection (signal strength monitoring, clock drift analysis) is not in scope.
7. SCMS REST API authentication for CRL push (Step 17): if the cloud backend's SCMS integration uses API keys rather than mTLS + certificate-bound tokens, a compromised cloud backend credential enables unauthorized CRL submissions — effectively a denial-of-service against any vehicle's pseudonym cert.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.315431
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

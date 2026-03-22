# Regulatory Compliance — Adas Perception

**Domain:** automotive
**Solution ID:** 021
**Generated:** 2026-03-22T11:53:39.313523
**HITL Level:** strict

---

## 1. Applicable Standards

- **ISO 26262 ASIL D**
- **AUTOSAR**
- **UNECE R79**

## 2. Domain Detection Results

- automotive (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 1 | SAFETY | Conduct Hazard Analysis and Risk Assessment (HARA) per ISO 26262 Part 3. Identif | Risk management, FMEA, hazard analysis |
| Step 5 | SAFETY | Perform Failure Mode and Effects Analysis (FMEA) and Fault Tree Analysis (FTA) f | Risk management, FMEA, hazard analysis |
| Step 16 | EMBEDDED_TEST | Write firmware unit tests for all HAL drivers and RTOS tasks using Unity + CMock | Hardware-in-the-loop verification |
| Step 17 | EMBEDDED_TEST | Execute HIL integration test suite on test bench (Step 15). Run all defined scen | Hardware-in-the-loop verification |
| Step 18 | SECURITY | Perform threat analysis and risk assessment (TARA) per ISO/SAE 21434 and UNECE R | Threat modeling, penetration testing |
| Step 21 | COMPLIANCE | Produce the Design History File (DHF) traceability matrix linking: SRS requireme | Standards mapping, DHF, traceability |
| Step 22 | COMPLIANCE | Produce ISO 26262 Safety Case and Functional Safety Assessment (FSA) package. In | Standards mapping, DHF, traceability |
| Step 23 | COMPLIANCE | Produce UNECE R155/R156 cybersecurity and software update management compliance  | Standards mapping, DHF, traceability |
| Step 24 | SYSTEM_TEST | Execute full system-level validation: deploy adas_perception firmware + backend  | End-to-end validation, performance |
| Step 26 | QA | Produce Software Verification Plan (SVP) and Software Verification Report (SVR)  | Verification & validation |

**Total tasks:** 27 | **Compliance tasks:** 10 | **Coverage:** 37%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | ISO 26262 ASIL D compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |
| 2 | AUTOSAR compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
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
| developer | 9 | Engineering |
| safety_engineer | 4 | Compliance |
| regulatory_specialist | 4 | Compliance |
| qa_engineer | 3 | Engineering |
| data_scientist | 2 | Analysis |
| system_tester | 2 | Engineering |
| product_manager | 1 | Design |
| devops_engineer | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This plan demonstrates solid high-level coverage of ISO 26262 process steps and shows genuine domain knowledge — the HARA→SRS→FMEA→firmware→HIL→compliance V-model structure is correct in outline. However, it fails on several architectural decisions that will require fundamental rework before TÜV submission is viable. The most critical failure is the undefined dual-compute-domain architecture: the plan treats an ARM Cortex-R52 safety MCU and an NVIDIA Orin inference SoC as a single undifferentiated platform, which makes the ASIL decomposition strategy for the ML pipeline impossible to evaluate. The complete absence of SOTIF (ISO 21448) is a certification blocker — no assessor reviewing a camera+LiDAR+radar perception system in 2024 will accept ISO 26262 alone. The AUTOSAR Classic/Adaptive contradiction in Step 4 will produce an invalid configuration from day one. Security PKI and key management are named but have no implementation content. On the positive side, the acceptance criteria are specific and measurable, the HIL test scenarios cover meaningful edge cases, and the compliance artifact chain (HARA→FMEA→DHF→Safety Case→SVR) is structurally correct. With the architectural issues resolved, an ODD definition added, SOTIF integrated as a parallel track, and toolchain qualification addressed, this plan could reach a certifiable state — but that represents 20-30% additional scoping work before a line of production code should be written.

### Flaws Identified

1. AUTOSAR Classic/Adaptive architecture is fatally ambiguous: Step 4 specifies 'AUTOSAR Adaptive R22-11' in the payload but lists an OIL file (os_config.oil) as an artifact — OIL files are AUTOSAR Classic/OSEK only. Adaptive AUTOSAR uses POSIX, ara::com, and Manifest XML, not OIL. This is a fundamental platform decision that must be resolved before any firmware work begins.
2. ML inference (YOLOv8, PointPillars) is assigned to the ASIL D functional chain with no ASIL decomposition strategy. Deep learning models cannot be certified to ASIL D under current ISO 26262 Part 6 methodology. The standard requires deterministic, analyzable software. The plan must define explicit ASIL decomposition (e.g., ML outputs tagged QM/ASIL B, wrapped by ASIL D safety monitors) and document Freedom from Interference (FFI) per ISO 26262-9.
3. Compute platform heterogeneity is undefined. ADAS perception systems require two distinct compute domains: a real-time safety MCU (ARM Cortex-R52, running AUTOSAR RTOS, ASIL D) for control tasks and a high-compute SoC/GPU (NVIDIA Orin or equivalent) for neural network inference. The plan conflates these — Steps 6-14 run RTOS tasks on Cortex-R52 while Step 9 targets Orin for TensorRT. Running PointPillars (Step 10) on a Cortex-R52 is computationally impossible. This dual-domain boundary is never defined as a design decision.
4. FTA listed as acceptance criterion in Step 1 (HARA) — FTA cannot be completed before system architecture and software design are available. FTA at HARA stage produces only top-level hazard trees; complete FTA with cut sets requires knowledge of design elements defined in Steps 3-14. This is a sequencing error that will cause the Step 1 artifact to be either incomplete or require expensive rework.
5. Secure boot architecture (Step 18) is designed after firmware implementation (Steps 6-14). Secure boot affects flash layout, memory map, startup vector, and bootloader — all of which must be established in Step 4 (AUTOSAR/toolchain config). Retrofitting secure boot onto an existing firmware image is a known project failure mode.
6. TensorRT INT8 quantization validation is absent. INT8 quantization changes model numerical behavior vs FP32/FP16 training. Step 9 has no post-quantization accuracy regression test, no INT8 vs FP32 delta analysis, and no qualification evidence for the TensorRT runtime library itself (which must be qualified per ISO 26262-8 Clause 11 as a software tool).
7. HIL smoke test as a per-PR gate in < 20 minutes (Step 25) is operationally unrealistic. dSPACE SCALEXIO racks are expensive shared physical infrastructure. Queue wait time alone on a shared HIL rack will routinely exceed 20 minutes. This gate will either stall all development or be disabled within weeks of going live.
8. Ghost target rejection acceptance criterion in Step 8 references an undefined 'recorded highway dataset.' Without a controlled, versioned, ground-truth-labeled dataset with known provenance, this criterion cannot be evaluated objectively or reproduced for audit.
9. No AUTOSAR Watchdog Manager (WdgM) SWC is defined. Step 14 mentions watchdog timers as safety mechanisms, but WdgM is the AUTOSAR component that provides supervised entity management, alive supervision, deadline supervision, and logical supervision for ASIL D. Its absence from the AUTOSAR SWC list in Step 4 means the supervision architecture has no AUTOSAR-compliant implementation path.
10. Step 5 FMEA/FTA depends on Steps 1 and 3 (sensor simulators) but not on Steps 4 (AUTOSAR SWC architecture). FMEA for the fusion pipeline requires knowledge of the software architecture and inter-component interfaces to enumerate failure modes correctly. Without Step 4 as a dependency, the FMEA will miss SWC boundary failure modes.
11. Driver override detection (Step 12) uses only steering torque threshold. This is insufficient for ASIL D: a single-threshold detection on a single signal is a single-point failure. ISO 26262 requires redundant detection paths or ASIL decomposition for driver override — e.g., torque + rate-of-change + driver monitoring camera input.

### Suggestions

1. Add Step 0: Define the system architecture — explicitly state dual-domain compute (safety MCU vs inference SoC), choose Classic OR Adaptive AUTOSAR (not both), define the inter-domain communication channel (Ethernet AVB, PCIe, or shared memory), and specify hardware qualification status. Everything else in the plan depends on this.
2. Add SOTIF (ISO 21448) analysis as a parallel track to ISO 26262. SOTIF covers performance insufficiencies (sensor limitations, edge cases, ODD boundary failures) that ISO 26262 explicitly excludes. For a perception system, a TÜV assessor will demand SOTIF coverage — its absence will block certification.
3. Add Operational Design Domain (ODD) specification as a prerequisite to Step 1 HARA. Severity and exposure ratings in HARA are undefined without ODD boundaries (speed range, weather conditions, road type, lighting conditions). HARA signed off without ODD is not valid.
4. Add toolchain qualification artifacts (ISO 26262-8 Clause 11) for LDRA, PC-lint+, the LLVM/GCC cross-compiler, and TensorRT. All tools used to produce or verify ASIL D software must be qualified. This is a mandatory work product for TÜV submission.
5. Insert SIL (Software-in-the-Loop) and PIL (Processor-in-the-Loop) test stages between unit tests (Step 16) and HIL (Step 17). SIL catches algorithmic bugs on a workstation before consuming expensive HIL rack time. PIL catches timing and target-specific issues on actual ARM hardware in a non-real environment. This is standard automotive V-model practice.
6. Add Automotive SPICE (A-SPICE) process capability artifacts as a parallel compliance track. For any Tier-1 supplier or OEM-facing delivery, A-SPICE CL2 is contractually required. No A-SPICE process work products means this plan cannot be delivered to a major OEM regardless of ISO 26262 status.
7. Add key management infrastructure to Step 18: HSM (Hardware Security Module) provisioning, key hierarchy definition (root CA, intermediate, device keys), key injection process for manufacturing, and key rotation procedure. AUTOSAR SecOC CMAC is meaningless without a defined key management system.
8. Reference ISO 11270 (Lane-Keeping Assistance) in Step 12 and ISO 15622 (Adaptive Cruise Control) in Step 13. These domain-specific ADAS standards define performance requirements, test procedures, and HMI requirements that supplement ISO 26262. Their absence means the plan may produce an ASIL D certified system that fails domain-standard homologation.
9. Add a Change Impact Analysis procedure (ISO 26262-8 Clause 8). Any post-release software change requires a documented CIA to determine if ASIL re-analysis is required. Without this procedure, the first OTA update will create a compliance gap.
10. Split Step 4 into two steps: 4a (architecture decision record — Classic vs Adaptive, dual-domain definition, secure boot memory map) and 4b (AUTOSAR configuration). Step 4a should depend on Step 1 HARA and precede all firmware steps. The current single step is doing too much and has the wrong dependencies.

### Missing Elements

1. SOTIF (ISO 21448) analysis — mandatory for perception-based ADAS, explicitly out of scope for ISO 26262
2. Operational Design Domain (ODD) specification document
3. Dual-domain compute architecture definition (safety MCU vs inference SoC with inter-domain communication spec)
4. Toolchain qualification plan and qualification reports (ISO 26262-8 Clause 11) for all ASIL D tools
5. A-SPICE process capability work products (SWE.1–SWE.6, SYS.2–SYS.5 at minimum)
6. HSM configuration and key management infrastructure (manufacturing key injection, rotation, revocation)
7. AUTOSAR WdgM (Watchdog Manager) SWC configuration and supervised entity definitions
8. Hardware qualification evidence for ARM Cortex-R52 MCU (IEC 61508 SIL 3 certified silicon or equivalent)
9. SIL (Software-in-the-Loop) and PIL (Processor-in-the-Loop) test phases
10. Freedom from Interference (FFI) analysis for ML QM components co-located with ASIL D partitions
11. Change Impact Analysis (CIA) procedure for post-release modifications
12. ML model ASIL decomposition strategy document (QM inference wrapped by ASIL D monitors)
13. INT8 quantization validation test suite comparing TensorRT INT8 vs FP32 accuracy delta
14. Domain-standard references: ISO 11270 (LKA), ISO 15622 (ACC), ISO 17361 (LDWS)
15. Bootloader design and secure boot memory map (must precede firmware implementation)
16. Vehicle-level integration / proving ground validation plan (HIL alone is insufficient for system-level sign-off)
17. OBD-II UDS Security Access service configuration (authentication for diagnostic sessions)

### Security Risks

1. No PKI infrastructure defined for OTA TLS 1.3 certificates. Who issues device certificates? What is the certificate lifetime? How are revoked certificates handled across a deployed fleet? Without a PKI plan, the OTA secure channel is a design intent with no implementation path.
2. AUTOSAR SecOC CMAC requires symmetric key pre-provisioning. The plan has no manufacturing key injection process and no HSM integration. If keys are hardcoded or provisioned insecurely at the factory, the entire SecOC architecture is compromised regardless of cryptographic correctness.
3. Diagnostic backend (Step 19) exposes fleet DEM fault data and perception metrics via unauthenticated REST API. The acceptance criteria have no mention of authentication, authorization, or TLS for the backend endpoints. Fleet fault data is operationally sensitive and can be used for targeted attacks.
4. Radar spoofing mitigation ('sensor_liveness_checks') is undefined. FMCW radar spoofing via signal replay or waveform injection is a demonstrated attack. The plan names the mitigation but never specifies the mechanism — there is no implementable design here.
5. Camera blinding countermeasure is listed as an attack surface in Step 18 but no mitigation is specified in the payload. Laser dazzling and IR flooding are known physical attacks on camera-based ADAS. The plan acknowledges the risk but proposes no defense.
6. No mention of UDS Security Access service (ISO 14229-1) configuration for OBD-II. Without SecurityAccess (service 0x27) properly gated, the diagnostic port allows unrestricted ECU reprogramming and memory read/write by any connected tool on the OBD-II port.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.313574
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

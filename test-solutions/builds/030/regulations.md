# Regulatory Compliance — Hmi Design System

**Domain:** automotive
**Solution ID:** 030
**Generated:** 2026-03-22T11:53:39.317092
**HITL Level:** strict

---

## 1. Applicable Standards

- **ISO 15005**
- **ISO 15008**
- **NHTSA Distraction Guidelines**

## 2. Domain Detection Results

- automotive (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 2 | SAFETY | Perform system-level hazard analysis and risk assessment (HARA) per ISO 26262 fo | Risk management, FMEA, hazard analysis |
| Step 3 | SAFETY | Conduct FMEA and fault tree analysis (FTA) for HMI rendering pipeline, input pro | Risk management, FMEA, hazard analysis |
| Step 5 | COMPLIANCE | Establish Design History File (DHF) skeleton, traceability matrix (requirements  | Standards mapping, DHF, traceability |
| Step 15 | SECURITY | Threat model and UNECE R155 cybersecurity analysis for HMI system: OBD-II/CAN at | Threat modeling, penetration testing |
| Step 17 | EMBEDDED_TEST | Write HIL test specifications and harness for instrument cluster renderer, HUD o | Hardware-in-the-loop verification |
| Step 19 | SYSTEM_TEST | Execute end-to-end system test suite: full vehicle signal playback through clust | End-to-end validation, performance |
| Step 20 | QA | ISO 15005 usability evaluation: observer-rated distraction test protocol, second | Verification & validation |
| Step 21 | COMPLIANCE | Populate DHF and finalize traceability matrix: link HARA safety goals → design d | Standards mapping, DHF, traceability |

**Total tasks:** 23 | **Compliance tasks:** 8 | **Coverage:** 35%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | ISO 15005 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | ISO 15008 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | NHTSA Distraction Guidelines compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 7 | Engineering |
| safety_engineer | 3 | Compliance |
| ux_designer | 2 | Design |
| regulatory_specialist | 2 | Compliance |
| devops_engineer | 2 | Engineering |
| firmware_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| product_manager | 1 | Design |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 52/100 (FAIL) — 1 iteration(s)

**Summary:** This plan demonstrates strong breadth and correct high-level sequencing: HARA before design, FMEA before implementation, DHF populated from real evidence. For a regulated automotive domain, however, several errors are disqualifying rather than merely advisory. The MISRA-C vs MISRA C++ confusion is a standards audit failure. FreeRTOS without ASIL certification invalidates all ASIL claims on safety-critical tasks. The absence of a Software Architecture Document before implementation begins means the DHF will be assembled retroactively from code rather than traced forward from design — which is the opposite of what ISO 26262 Part 6 requires. The CNN gesture recognizer has no viable certification path as specified. SystemC simulation labeled as HIL will not satisfy a Tier 1 safety assessment. These are not polish issues — they are fundamental rework items that would cause rejection at a first-party OEM safety audit. Recommend halting implementation (steps 7–13) until the SAD, ASIL decomposition, tool qualification plan, and RTOS selection are resolved, then re-scoring.

### Flaws Identified

1. Steps 9, 10, 11 mandate 'MISRA C violations zero' but are written in C++17. MISRA-C:2012 applies to C only. The applicable standard is MISRA C++:2008 or AUTOSAR C++14. This is a fundamental standards mis-citation that will fail any ISO 26262 software audit.
2. FreeRTOS is used for safety-critical task scheduling but is not ASIL-certified out of the box. For any ASIL C or ASIL D safety goals derived from the HARA, SafeRTOS (certified) or an AUTOSAR OS on a qualified platform is required. Using vanilla FreeRTOS and asserting ASIL compliance is a certification blocker.
3. Step 11 uses a CNN for gesture recognition and sets 90% accuracy as the acceptance criterion. CNNs are non-deterministic, not formally verifiable, and currently cannot be certified under ISO 26262 without a qualified safety cage and a documented argumentation strategy (e.g., ISO/PAS 8800 if available). 90% accuracy is also insufficient for any safety-relevant input — no ASIL level is defined for the gesture subsystem.
4. Step 17 labels SystemC simulation as the 'HIL platform'. Simulation is not HIL testing. For ISO 26262 evidence, HIL must use representative hardware (actual SoC, actual interfaces) or a formally validated surrogate. A SystemC model at unknown fidelity does not satisfy Part 4 integration test requirements.
5. MC/DC coverage is required for ASIL C/D modules under ISO 26262-6 Table 10. The plan specifies 90% line coverage throughout (steps 18, 22). Line coverage is only sufficient for ASIL A/B. If HARA produces any ASIL C/D safety goals (likely for warning indicator pipeline), this coverage metric is non-compliant.
6. No software architecture document is produced before implementation begins. Steps 8–13 implement code against a HARA and toolchain, but no software architectural design document (SAD) — a required ISO 26262 Part 6 work product — is ever authored. It appears at step 21 as 'software_architecture_description' listed as input to the DHF, but it was never created.
7. Step 13 implements a SOME/IP bridge in Python/FastAPI. SOME/IP is a service-oriented middleware protocol native to AUTOSAR Adaptive/Classic ECU layers. A Python bridge introduces non-deterministic latency, GIL contention, and is architecturally disconnected from the AUTOSAR stack specified elsewhere. This will not meet the 50ms WebSocket relay budget under load.
8. The HUD geometric correction acceptance criterion of '< 1 arcminute' is implausible. Production-grade automotive HUD systems (Visteon, Continental, Yazaki) achieve 2–5 arcminutes with dedicated optical calibration rigs. Sub-1-arcminute correction requires hardware-level optical alignment, not a software matrix. This criterion will never pass and blocks step 19.
9. Step 14 uses an AI agentic coordinator as a build gate for ISO 15005 compliance. If the LLM provider is unavailable, rate-limited, or returns a hallucinated pass, the gate is meaningless. Regulatory gates cannot be dependent on non-deterministic AI inference without a certified fallback and a documented human override audit trail.
10. No software tool qualification plan exists. ISO 26262 Part 8 clause 11 requires tool qualification (TCL1–3) for every development tool used — CMake, CppUTest, arm-none-eabi-gcc, OpenGL ES driver. The plan never addresses this. Unqualified tools mean all test evidence produced by those tools is inadmissible for functional safety claims.
11. ASIL decomposition strategy is absent. The HARA (step 2) will produce mixed-ASIL safety goals. The plan never specifies how ASIL decomposition is applied across redundant channels, which functions are ASIL D vs QM, or how freedom from interference between ASIL and non-ASIL software partitions is guaranteed. Without this, the ASIL assignments are decorative.

### Suggestions

1. Add a dedicated 'SOFTWARE_ARCHITECTURE' step between steps 5 and 6 to produce the SAD before any implementation. This is a required ISO 26262-6 work product and enables all downstream implementation steps to reference it.
2. Replace vanilla FreeRTOS with SafeRTOS or AUTOSAR OS on a qualified BSP, OR explicitly scope all safety-critical tasks to a separate ASIL partition with a qualified RTOS and relegate FreeRTOS to QM tasks only with a documented freedom-from-interference argument.
3. Replace MISRA-C:2012 citations in C++ steps with MISRA C++:2008 or AUTOSAR C++14 (preferred for new projects). Add a dedicated static analysis tool step (Polyspace, Helix QAC, or Coverity with AUTOSAR ruleset) as a separate CI gate.
4. Add a tool qualification plan as a deliverable in step 5 or 6, listing all development tools, their TCL ratings, and qualification method (validation, use of established tools, or diverse verification).
5. Replace the 90% line coverage gate with tiered coverage: MC/DC for ASIL C/D modules, branch coverage for ASIL B, line coverage for ASIL A/QM. Map coverage requirements directly to ASIL assignments from step 2.
6. Replace the SystemC-as-HIL fiction with an explicit HIL strategy: either specify a real hardware target (e.g., NXP i.MX8, Renesas R-Car) for HIL, or formally document the simulation fidelity argument and its acceptance by the safety authority.
7. The CNN gesture recognizer needs either: (a) a safety cage — a certified rule-based watchdog that monitors CNN outputs and vetoes physically impossible or unsafe gestures — plus a formal argument that the combination is ASIL-compliant, or (b) replacement with a classical ML model that can be formally verified. Document this in the HARA.
8. The SOME/IP bridge should be implemented using vsomeip (C++ library) or AUTOSAR Adaptive ServiceD, not a Python FastAPI wrapper. Keep the FastAPI layer as a REST façade that calls into a proper SOME/IP middleware.
9. Add ISO/SAE 21434 TARA alignment: step 15 covers UNECE R155 but cybersecurity and functional safety interaction points (e.g., a cyber-attack causing a safety violation) must be explicitly mapped between the TARA and HARA. This gap is a common OEM audit finding.
10. Split step 22 CI time estimate: MISRA lint + cross-compile is feasible in 20 min, but SystemC HIL simulation of a full drive scenario is not. Separate fast (pre-merge) and slow (nightly) CI tiers with explicit gate definitions for each.

### Missing Elements

1. Software Architecture Document (SAD) as an explicit work product — never created, only referenced as input to DHF at step 21
2. ASIL decomposition strategy and freedom-from-interference analysis between software partitions
3. Software tool qualification plan (ISO 26262-8:11) covering CMake, CppUTest, static analysis tools, and OpenGL ES driver
4. SIL (Software Integration Level) testing step between unit tests (step 18) and system tests (step 19)
5. Automotive-grade OS specification — the plan specifies FreeRTOS but never addresses whether the display SoC runs QNX, Green Hills INTEGRITY, or Linux, each of which has radically different ASIL argumentation paths
6. Formal definition of the React design system's role versus the embedded OpenGL ES renderer — are these two separate executables on different hardware? The plan conflates them.
7. ASIL-rated watchdog / safety monitor implementation for rendering pipeline — if the OpenGL ES renderer hangs, what detects it and what is the safe state?
8. Hardware specification for the target SoC — Renesas R-Car H3, NXP i.MX8, TI Jacinto, or other — which determines ASIL BSP availability, GPU driver safety certification, and HIL platform choice
9. Offline map / ADAS data pipeline for HUD AR waypoints — step 10 references AR waypoints but no data source, update mechanism, or staleness policy is defined
10. Driver monitoring integration — ISO 15005 distraction assessment in real deployment requires driver state awareness; the plan has no sensor or signal path for this

### Security Risks

1. CAN-FD bus has no authentication by design. Step 13's SOME/IP bridge ingesting CAN signals into a JWT-protected REST API creates a confused deputy: the bridge process is authenticated to the API but any node on the CAN bus can inject arbitrary vehicle signals. The TARA in step 15 identifies this surface but the firmware implementation in step 8 has no input validation or message authentication.
2. Voice command pipeline (step 11) with offline DSP and wake-word detection is vulnerable to acoustic injection (ultrasonic or adversarial audio). The plan does not specify rejection of commands above a confidence threshold or liveness detection. A spoofed 'navigate home' command while driving is a safety-relevant attack.
3. OTA update integrity is documented as a requirement in step 15 but no implementation step exists for the secure bootloader, key management infrastructure, or rollback protection. Requirements without implementation are not mitigations.
4. USB debug port is listed as an attack surface in step 15 but no step disables or gates it in production firmware. Debug interfaces left enabled in production are a consistent automotive vulnerability (see Jeep Cherokee CAN injection, BMW ConnectedDrive).
5. JWT secret management for the FastAPI backend (step 13) is unspecified — no mention of rotation policy, storage (HSM vs env var), or token expiry. In a vehicle context, a compromised JWT allows arbitrary HMI config modification.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.317127
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

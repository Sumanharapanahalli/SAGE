# Regulatory Compliance — Infotainment System

**Domain:** automotive
**Solution ID:** 023
**Generated:** 2026-03-22T11:53:39.314412
**HITL Level:** strict

---

## 1. Applicable Standards

- **ISO 26262 QM**
- **ISO 15005**
- **UNECE R155/R156**

## 2. Domain Detection Results

- automotive (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | SAFETY | Perform ISO 26262 QM Hazard Analysis and Risk Assessment (HARA) and system-level | Risk management, FMEA, hazard analysis |
| Step 5 | COMPLIANCE | Establish compliance framework for AUTOSAR, ISO 26262 QM, and UNECE R155/R156. C | Standards mapping, DHF, traceability |
| Step 15 | SECURITY | Perform threat modeling (STRIDE/TARA per ISO/SAE 21434) for the IVI system. Iden | Threat modeling, penetration testing |
| Step 19 | EMBEDDED_TEST | Produce Hardware-in-the-Loop (HIL) test specifications for IVI system: test harn | Hardware-in-the-loop verification |
| Step 20 | QA | Produce QA Test Plan covering all IVI features: test strategy, entry/exit criter | Verification & validation |
| Step 21 | SYSTEM_TEST | Execute system-level integration test suite: end-to-end voice command → navigati | End-to-end validation, performance |
| Step 22 | COMPLIANCE | Compile final ISO 26262 QM compliance package: completed DHF with all work produ | Standards mapping, DHF, traceability |

**Total tasks:** 24 | **Compliance tasks:** 7 | **Coverage:** 29%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | ISO 26262 QM compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |
| 2 | ISO 15005 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | UNECE R155/R156 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 10 | Engineering |
| regulatory_specialist | 3 | Compliance |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| marketing_strategist | 1 | Operations |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| safety_engineer | 1 | Compliance |
| localization_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 58/100 (FAIL) — 1 iteration(s)

**Summary:** This plan is architecturally ambitious and structurally sound — 24 well-sequenced steps covering the full IVI stack from HARA through type approval. The dependency graph is mostly correct, the compliance artifacts are the right ones, and the HITL gating in step 24 is appropriately calibrated. However, it fails on several production-critical dimensions that would cause it to collapse before reaching the regulated-domain threshold of 85. The three most serious flaws are: (1) TARA placed after OTA server implementation, violating security-by-design and UNECE R155 process requirements; (2) AOSP build time acceptance criteria that are physically impossible, meaning CI will be declared broken from day one; and (3) the complete absence of a secure boot chain and PKI lifecycle — without these, UNECE R156 software integrity claims cannot be substantiated. Additionally, the HARA pre-determining QM before running the analysis is a methodological error that will surface in a third-party functional safety audit. The plan needs a security-architecture step inserted before Step 7, TARA moved to before Step 9, realistic build time targets, secure boot scoped in, and GMS licensing confirmed as a go/no-go gate before navigation implementation begins. In current form, this ships a technically impressive demo that fails regulatory submission.

### Flaws Identified

1. Step 18 acceptance criteria states 'PR pipeline completes in <20 minutes (build + test + lint)' — AOSP full builds take 4–8 hours; incremental builds take 30–60 minutes minimum. This criterion is off by 10–20x and will be failed on day one.
2. Step 6 acceptance criteria states 'AAOS emulator boots in <90 seconds' — cold boot of the Android Automotive AVD routinely takes 3–8 minutes on standard CI hardware. This will never pass.
3. Step 4 pre-determines ASIL as QM before the HARA is performed. The HARA is the process that determines ASIL — you cannot set a target ASIL and then run the HARA to confirm it. Navigation misdirection and HMI freeze at highway speed may yield ASIL A under rigorous Severity × Exposure × Controllability analysis. This is methodologically backwards and will fail a third-party functional safety audit.
4. Step 15 (TARA/threat modeling) depends on steps 5 and 10, meaning the OTA server is fully implemented before the attack surface is analyzed. Security must inform design, not audit it post-hoc. UNECE R155 requires CSMS to be integrated into the development process, not appended to it.
5. Step 11 lists Snowboy as a wake-word detection option. Snowboy was archived in 2020 and is no longer maintained. Using deprecated security-adjacent software in a production vehicle system is a compliance and supply-chain risk.
6. Step 7 acceptance criteria demands 'MISRA C violations zero.' Zero MISRA violations is unachievable for any non-trivial embedded codebase. The correct standard is documented and justified deviations — claiming zero is either a lie or means the checker is not configured correctly.
7. Step 14 includes 'battery level gate: reject if SOC < 20%' — SOC applies to EVs and hybrids only. ICE vehicles use 12V lead-acid without meaningful SOC tracking. No equivalent 12V voltage gate is specified, leaving ICE platforms unprotected against low-voltage brick during OTA.
8. Step 10 requires HSM-backed OTA package signing, but Step 18 implements signing in GitHub Actions CI. There is no described mechanism for GitHub Actions to reach an HSM. This gap means signing will be done with software keys in practice, violating the stated security requirement.
9. Step 8 proposes using QEMU for AAOS firmware bring-up, but AAOS is not a standard QEMU target. AOSP car builds use the Android Automotive Emulator (AVD), not bare QEMU. Raw QEMU for NXP i.MX8 or SA8155P requires board-specific machine definitions that do not exist in upstream QEMU — this step will stall without custom QEMU porting work that is not scoped.
10. Step 12 specifies 'Jetpack Compose for Automotive (Car UI Library 2.0)' — as of 2025, Compose for Android Automotive remains experimental with known compatibility gaps against the AAOS Car UI Library. Production commitment to this stack requires explicit compatibility validation against the target AAOS version, which is absent.
11. Step 21 specifies an 8-hour soak test. Automotive reliability standards (e.g., AEC-Q100, OEM PPAP requirements) typically require 100–500 hours for thermal cycling and memory leak detection. An 8-hour soak will not catch slow leaks (e.g., a 5MB/hour leak looks fine at 8h, catastrophic at 200h).
12. The AUTOSAR Classic/Adaptive stack (step 5, step 7) and Android Automotive OS operate on physically separate compute domains (MCU vs application processor). The plan never defines the architectural boundary between them, inter-domain communication protocol (e.g., SOME/IP, virtio), or which stack owns which feature. Without this, steps 7 and 12 will produce incompatible artifacts.

### Suggestions

1. Move Step 15 (TARA) to immediately after Step 2 (PRD), before any architecture or implementation decisions. Security requirements must gate the API contracts in Step 9, not follow OTA server implementation.
2. Replace the AOSP build time acceptance criterion with a realistic split: 'incremental build <45 minutes; full clean build <6 hours on 32-core runner.' Use ccache and Google's build cache to optimize.
3. Add an explicit architectural document step (between Steps 6 and 7) that defines the MCU/AUTOSAR ↔ Android Automotive OS boundary, inter-domain IPC mechanism, and which compute domain owns each feature. This is the single most important missing artifact.
4. Replace Snowboy with a supported alternative: Picovoice Porcupine (actively maintained, has automotive licensing), SNIPS (acquired by Sonos but open-source artifacts exist), or custom wake-word model via TensorFlow Lite.
5. Replace 'MISRA C violations zero' with 'MISRA C:2012 compliance report generated; all Rule violations are documented deviations with rationale approved by safety_engineer.'
6. Add a secure boot chain step after Step 6: define hardware root of trust (ROM bootloader → U-Boot with verified boot → AAOS verified boot), key provisioning in manufacturing, and revocation strategy. Without this, UNECE R156 software integrity cannot be demonstrated.
7. Add certificate lifecycle management: PKI architecture, certificate expiry strategy for 10-year vehicle lifetime, OEM-specific root CA, and key rotation runbook. The current plan treats TLS/Ed25519 as implementation details with no operational lifecycle.
8. Add Android GMS licensing as a dependency blocker before Step 13. Google Maps for Android Automotive requires an OEM GMS contract and passing Android Automotive CDD compatibility testing. This is a 6–18 month business process, not a technical task.
9. Move HIL platform procurement decision to Step 6 (environment setup), not Step 19. dSPACE SCALEXIO lead times are 4–9 months. A decision deferred to Step 19 makes Steps 19–21 impossible to execute on schedule.
10. Add a Data Protection Impact Assessment (DPIA) step, required under GDPR Article 35 for voice recording pipelines and continuous location tracking — both present in this system. The current GDPR mention (step 16) is insufficient.

### Missing Elements

1. Secure boot chain design and key provisioning in manufacturing — no mention anywhere in 24 steps. UNECE R156 Article 7 requires cryptographic integrity of installed software, which requires verified boot.
2. Vehicle network security gateway architecture — the CAN boundary is mentioned in security but no gateway design (e.g., Adaptive AUTOSAR ara::com, SOME/IP firewall, SecOC) is specified. This is the most critical safety boundary in the system.
3. Android GMS/GAPPS licensing process — required before any Google Maps for Automotive integration can proceed. Absent from the plan entirely.
4. PKI infrastructure and certificate lifecycle management across a 10+ year vehicle lifetime.
5. Multi-SoC porting strategy — NXP i.MX8 and Qualcomm SA8155P have fundamentally different BSPs, power management, and GPU stacks. The HAL layer must be specified as SoC-agnostic or the target must be locked to one SoC.
6. AUTOSAR ↔ AAOS inter-domain communication specification (SOME/IP, ARA::COM, or virtio-based).
7. Manufacturing key provisioning and hardware root of trust specification for production units.
8. Driver Monitoring System (DMS) integration point — EU GSR 2022 mandates DMS; IVI must receive DMS alerts and potentially suppress UI interactions.
9. DPIA (Data Protection Impact Assessment) for voice pipeline and location history — legally required under GDPR Article 35.
10. GPS/GNSS privacy — continuous location tracking requires user consent mechanism and data retention policy beyond the 30-day voice log policy already stated.
11. OSS license scanning in CI/CD — the SBOM GPL-3 check is a one-time compliance artifact (step 22) with no automated enforcement in the pipeline. GPL-3 components can be introduced silently via transitive dependencies.
12. Regulatory engagement plan with Technical Service (TS) and Type Approval Authority (TAA) for UNECE R155/R156 — type approval is not a document submission, it is an 8–24 month engagement process.

### Security Risks

1. TARA post-implementation: threat modeling after OTA server is built means discovered high-rated threats (e.g., unauthenticated manifest endpoint, weak VIN-based targeting) require expensive rework rather than cheap design changes.
2. HSM-CI gap: if GitHub Actions cannot reach the HSM, signing falls back to software keys on the runner. A compromised runner then signs malicious OTA packages that will be accepted by all enrolled vehicles. This is a fleet-wide remote code execution risk.
3. No secure boot: without verified boot, a physical attacker with USB access can reflash the application processor with arbitrary firmware. Combined with CAN gateway access, this is a potential vehicle safety issue even within the IVI QM scope.
4. Voice adversarial command surface: 'report_hazard' intent combined with automated responses could be triggered by audio played from a passing vehicle or roadside speaker. The plan's false-positive criterion (1/hour) only covers wake-word, not downstream intent misclassification.
5. CAN write access ambiguity: step 15 states 'IVI→CAN write access confirmed restricted to non-safety bus segments only' but no step in the plan implements or tests this restriction at the gateway level. It is a stated goal with no verification path.
6. OTA rollback integrity: the watchdog-guarded rollback in step 14 does not specify whether the rollback itself is authenticated. An attacker who can corrupt the active partition could force rollback to a known-vulnerable previous version.
7. mTLS vehicle identity: step 10 requires mTLS for vehicle-to-server communication but no step provisions vehicle certificates at manufacturing time or defines certificate rotation for the vehicle lifetime. Expired vehicle certs will brick OTA capability.
8. Debug interface: step 15 mentions APK injection via USB debug interface as an attack surface, and step 23 covers technician UDS access. Neither step specifies how ADB and diagnostic interfaces are disabled in production builds vs enabled for service.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.314470
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

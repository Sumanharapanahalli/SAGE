# Regulatory Compliance — Surgical Robot Ui

**Domain:** medtech
**Solution ID:** 004
**Generated:** 2026-03-22T11:53:39.307275
**HITL Level:** strict

---

## 1. Applicable Standards

- **ISO 13485**
- **IEC 62304**
- **IEC 61508 SIL 3**
- **ISO 14971**

## 2. Domain Detection Results

- medtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 1 | SAFETY | Conduct preliminary hazard analysis (PHA) and system-level FMEA for the surgical | Risk management, FMEA, hazard analysis |
| Step 2 | COMPLIANCE | Establish the Design History File (DHF) skeleton and traceability matrix framewo | Standards mapping, DHF, traceability |
| Step 12 | EMBEDDED_TEST | Write Hardware-in-the-Loop (HIL) test harness for the haptic firmware and tracki | Hardware-in-the-loop verification |
| Step 14 | SYSTEM_TEST | Execute end-to-end system test suite covering full surgical procedure simulation | End-to-end validation, performance |
| Step 15 | SAFETY | Complete detailed FMEA and fault tree analysis (FTA) for the integrated system b | Risk management, FMEA, hazard analysis |
| Step 16 | COMPLIANCE | Populate and close the Design History File (DHF). Assemble all evidence artifact | Standards mapping, DHF, traceability |
| Step 17 | SECURITY | Perform threat model and security review for the surgical console. Scope: operat | Threat modeling, penetration testing |

**Total tasks:** 19 | **Compliance tasks:** 7 | **Coverage:** 37%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | ISO 13485 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | IEC 62304 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | IEC 61508 SIL 3 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
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
| developer | 7 | Engineering |
| safety_engineer | 3 | Compliance |
| regulatory_specialist | 2 | Compliance |
| qa_engineer | 2 | Engineering |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| system_tester | 1 | Engineering |
| devops_engineer | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This plan demonstrates genuine regulatory literacy — the three-YAML structure of DHF/FMEA/FTA, MC/DC targets, HIL simulation, mTLS auth, and audit logging all reflect real medical device engineering experience. However, it contains two architectural failures that would block regulatory clearance and one that is a patient safety risk: (1) The SIL-3 claim cannot be substantiated — IEC 61508 system-level activities (SFF analysis, HFT architecture, SC3 systematic capability) are absent, and FreeRTOS is not SIL-3 certified SOUP; (2) The emergency stop display path routes through the WebSocket bridge and React render cycle, meaning a software fault in the bridge or browser can prevent the safety alert from rendering — this is an unacceptable Class C design for a safety function; (3) The decision to render the surgical 3D viewport in Three.js/WebGL2/React 18 introduces non-deterministic GC and scheduler latency that cannot guarantee the ≤16ms display latency acceptance criterion. For a surgical robot requiring ISO 13485 + IEC 62304 Class C, the missing IEC 60601-1, missing clinical validation, missing FreeRTOS SOUP assessment, and absent regulatory submission pathway mean this plan cannot reach design freeze without substantial rework. Estimated rework scope: add 6–8 steps, restructure the e-stop architecture, replace or certify the RTOS, and engage a notified body for SIL-3 scope clarification before implementation begins.

### Flaws Identified

1. SIL-3 (IEC 61508) and IEC 62304 Class C are conflated throughout the plan. IEC 62304 defines Software Safety Classes A/B/C — it does not use SIL levels. SIL-3 per IEC 61508 requires additional functional safety activities (safe failure fraction analysis, hardware fault tolerance levels, systematic capability SC3 evaluation, common cause failure analysis) that are entirely absent from this plan. Claiming SIL-3 compliance without these activities will fail a notified body audit.
2. FreeRTOS 10.6 is not SIL-3 certified. Using uncertified RTOS as SOUP at SIL-3 requires exhaustive validation evidence (test coverage, formal SOUP assessment per IEC 62304 clause 8.1, known-anomaly list). The plan lists 'SOUP components listed' as a checkbox but provides no SOUP validation strategy. Safety-certified alternatives (SAFERTOS, PikeOS, LynxOS-178, Integrity RTOS) would need evaluation. This alone can block regulatory clearance.
3. Emergency stop notification travels through the software stack: firmware → CAN → Rust WS bridge → WebSocket → React → UI render. Step 9's acceptance criterion 'Emergency stop overlay activates within 100ms via WebSocket' means the safety alert path is software-dependent and can be blocked by browser GC, WebSocket reconnect (step 10 says 500ms reconnect), or axum back-pressure. For a SIL-3 or even Class C device, the e-stop display path must be independent of the normal data path or hardwired. This is an architectural safety failure.
4. Three.js / WebGL2 / React 18 for safety-critical surgical display is architecturally unacceptable for SIL-3. JavaScript's non-deterministic GC, React 18 concurrent scheduler preemption, and browser engine update behavior introduce non-deterministic frame timing. The ≤16ms display latency acceptance criterion cannot be guaranteed on this stack — it can only be measured statistically. For Class C software, this requires documented justification or a native renderer (Vulkan C++ binding was listed as an alternative — use it).
5. Step 17 (security threat model) depends on steps 10 and 6 — meaning it runs after full implementation. STRIDE on a built system is purely reactive. Threat modeling must occur at architecture phase (step 5) to influence design decisions. Running it post-implementation means any structural finding (e.g., 'the WebSocket bridge needs a separate security boundary') requires expensive rework.
6. No IEC 60601-1 (general safety and essential performance for medical electrical equipment) anywhere in the plan. A surgeon console with haptic actuators and electrical connections is a medical electrical system. IEC 60601-1 is mandatory for market access in US (via FDA recognition) and EU (MDR harmonized standard). Missing it is a regulatory show-stopper.
7. No IEC 60601-1-2 (EMC for medical electrical equipment) testing or design requirements. EMI interference is correctly listed as a hazard in step 1 but no EMC test plan exists. Surgical ORs are EMI-dense environments (electrosurgical units, cauterizers). Without EMC qualification, the device cannot be demonstrated safe for its intended environment.
8. Clinical validation is absent. ISO 13485 clause 7.3.6 requires design validation 'under defined operating conditions' using 'representative units.' For a surgical robot console, this means simulated surgical procedures with representative end-users (surgeons), not just HIL simulation tests. No formative or summative usability validation study plan is defined beyond the UX wireframe review in step 4.
9. No FDA regulatory submission pathway defined. A minimally invasive surgical robot is a Class III device in the US requiring PMA or De Novo submission — not merely 21 CFR Part 820 quality system compliance. The plan treats FDA 21 CFR Part 820 as a checkbox but ignores the submission strategy, predicate device analysis, and clinical study requirements.
10. Step 13 firmware unit testing uses CppUTest but step 6 implements in C (MISRA-C). The MC/DC 100% target (correctly required for SIL-3) is listed in step 12 (HIL) but the unit test framework for firmware (CppUTest) does not automatically generate MC/DC evidence. A dedicated coverage tool (LDRA, Polyspace, VectorCAST) integrated with the MISRA checker is required and absent from the toolchain.
11. The haptic latency budget is internally inconsistent. Step 3 states 'haptic_loop_ms: 10' but step 6 implements a 1kHz control loop (1ms period). A 10ms haptic control loop is only 100Hz — unacceptable for transparent force feedback. The requirement likely means end-to-end latency budget is 10ms, but this conflicts with a 1kHz loop period of 1ms. Ambiguity in a safety requirement is a compliance defect.
12. No SOUP analysis for the Rust/axum/React/Three.js/Zustand/Node.js stack. IEC 62304 clause 8.1 requires SOUP items to be identified with version, known anomalies, and regression test strategy. The plan mentions SOUP only for firmware (step 6). The entire service layer and UI are unaddressed SOUP.
13. Safety-critical parameter change control is missing. Force saturation limits (step 6), confidence thresholds (step 7, 'configurable, default 0.85'), and latency limits are safety-critical parameters. Changing them post-release requires a design change process under ISO 13485 clause 7.3.9. No parameter configuration management or change control process is defined.
14. No formal Design Review gates (PDR/CDR) as plan steps. Step 2 creates DHF skeleton with 'design_reviews' as a section but no plan steps schedule a preliminary design review before implementation or critical design review before testing. Without review gates, the DHF will be missing signed design review records — a common ISO 13485 audit finding.
15. No Design Transfer step per ISO 13485 clause 7.3.8. The plan ends at documentation (step 19) with no step covering manufacturing transfer, production qualification, or ensuring design outputs can be consistently reproduced. For a medical device, Design Transfer is a mandatory DHF section.

### Suggestions

1. Separate the IEC 61508 SIL-3 activities from IEC 62304 Class C activities into distinct work streams with a clear scope boundary: IEC 62304 governs the software lifecycle; IEC 61508 governs the system-level functional safety. Hire or contract a TÜV-recognized functional safety assessor to scope this correctly before writing another line of FMEA.
2. Replace FreeRTOS with SAFERTOS (FreeRTOS kernel with pre-existing SIL-3 safety case) or a certified RTOS. Alternatively, document FreeRTOS SOUP validation per IEC 62304 clause 8.1 with a full known-anomaly assessment and dedicated regression suite — but this path adds months.
3. Architect the emergency stop path as a hardware-independent safety channel: dedicated SIL-rated safety controller (e.g., Pilz PNOZ, Sick flexi soft) that hardwires e-stop to force-zero at the actuator driver level. The UI overlay is informational only — it must not be on the critical path for force cessation.
4. Move STRIDE threat modeling to immediately after step 5 (architecture), not after step 10. Run it as a gated architecture review. Any HIGH finding that requires structural change is far cheaper to fix before implementation.
5. Replace Three.js/WebGL2 with the native Vulkan C++ renderer (already listed as an option in step 8). Implement it as a dedicated process with real-time scheduling priority. The React UI dashboard can remain for non-safety panels, but the 3D viewport and alarm overlay should be native with bounded frame timing.
6. Add IEC 60601-1 and IEC 60601-1-2 as explicit plan steps. These need to inform hardware design, PCB layout, power supply isolation class, and applied part classification — decisions that must be made before manufacturing, not after.
7. Add a clinical validation step after system testing: define a simulated use study with ≥5 surgeons executing defined surgical task scenarios, measuring critical use errors, task completion time, and alarm response accuracy. This is required for both FDA Human Factors (FDA HFE guidance 2016) and IEC 62366-1 summative evaluation.
8. Define the MC/DC evidence toolchain explicitly: VectorCAST or LDRA for C firmware, cargo-llvm-cov with custom MC/DC extraction for Rust, and document how MC/DC reports map to DHF evidence artifacts. 'MC/DC 100%' as an acceptance criterion without naming the measurement tool is unverifiable.
9. Add a step for SBOM vulnerability monitoring process (not just SBOM generation). IMDRF N60 and FDA 2023 cybersecurity guidance require a post-market vulnerability monitoring plan — who watches CVE feeds, what is the patch SLA, and how is a patch released through the IEC 62304 change control process.
10. Specify IPC schema validation at runtime for all cross-component boundaries. CBOR-framed messages between Rust services should be validated against a schema on every deserialization. A malformed tracking state message should be rejected and trigger a fault, not crash the consumer.

### Missing Elements

1. IEC 61508 Part 2/3 system-level functional safety activities (SFF analysis, architectural constraints for SIL-3 hardware, systematic capability SC3 evidence)
2. IEC 60601-1 general safety and essential performance analysis and test plan
3. IEC 60601-1-2 EMC test plan and design requirements for OR environment
4. Summative usability evaluation (IEC 62366-1 clause 5.9) with representative users — step 4 only covers formative evaluation
5. FDA regulatory submission strategy (PMA/De Novo, predicate device, clinical study plan)
6. EU MDR clinical evaluation plan (MEDDEV 2.7/1 Rev 4 or MDCG 2020-13)
7. FreeRTOS SOUP validation assessment or replacement with SIL-certified RTOS
8. Formal design review steps (PDR before step 5, CDR before step 12) with sign-off requirements
9. Design Transfer step (ISO 13485 clause 7.3.8) — manufacturing qualification, production BOM, assembly process validation
10. Hardware safety analysis (system-level FMEA including hardware components of the console)
11. Post-market surveillance plan (ISO 13485 clause 8.2, MDR Article 83)
12. Penetration test execution (step 17 creates a plan but no step executes it)
13. Named MC/DC coverage toolchain for each language (not just 'cargo test + proptest')
14. Runtime IPC schema validation between all four architecture layers
15. Safety-critical parameter change control process (force limits, thresholds, latency budgets)
16. Actual execution of the penetration test plan produced in step 17

### Security Risks

1. Emergency stop display path through WebSocket bridge means a compromised or crashed WS bridge (axum service) prevents the surgeon from seeing the e-stop confirmation alert. If a malicious actor can crash the WS bridge (e.g., via WebSocket flood), the console goes dark during a procedure. The e-stop actuation must be independent of this path.
2. Browser-hosted visualization surface: if the console UI runs in a general-purpose browser, it inherits the full browser attack surface. A compromised browser extension or cached malicious content could manipulate the 3D visualization (instrument position rendering) without triggering any firmware-level fault. Mitigate by using a locked-down browser kiosk (Electron with CSP, or purpose-built renderer).
3. Firmware OTA update path is mentioned as a security scope item in step 17 but never implemented in any prior step. This is a functional gap: the plan has no step that implements signed firmware update. If firmware update is done over a production interface (USB, Ethernet), an unsigned update path is an unmitigated HIGH-severity finding.
4. mTLS smart card authentication in an OR is operationally risky: surgeons wear sterile gloves, cannot touch unsterile card readers, and time-critical moments require immediate access. If the mTLS session expires during a procedure and requires reauthentication, the surgeon cannot comply without breaking sterility. No session management policy or graceful expiry handling is defined — operator lockout during surgery is a patient safety hazard.
5. Audit log append-only protection is stated as an acceptance criterion (step 17) but no cryptographic implementation is specified. An append-only file on a general-purpose Linux system can be trivially overwritten by root. Tamper-evident logging requires WORM storage, cryptographic hash chaining (each entry hashes the previous), or an external write-once sink.
6. SBOM covers direct and transitive dependencies but no CVE monitoring or vulnerability SLA is defined. A known-vulnerable version of axum, ring (Rust crypto), or Three.js post-release with no patch process is a regulatory and patient safety risk under FDA 2023 cybersecurity guidance.
7. Unix domain socket IPC between Rust services has no authentication. A compromised process on the same host can inject malformed instrument state (fake 6-DOF poses) into the rendering layer, causing the surgeon to see incorrect instrument positions without any alarm. Message signing or SELinux mandatory access control between service processes is absent.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.307332
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

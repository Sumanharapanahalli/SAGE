# Regulatory Compliance — Patient Monitoring Dashboard

**Domain:** medtech
**Solution ID:** 005
**Generated:** 2026-03-22T11:53:39.307658
**HITL Level:** strict

---

## 1. Applicable Standards

- **IEC 62304**
- **ISO 13485**
- **HL7 FHIR**
- **ISO 14971**

## 2. Domain Detection Results

- medtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 2 | SAFETY | Conduct preliminary hazard analysis and FMEA for the ICU patient monitoring syst | Risk management, FMEA, hazard analysis |
| Step 3 | REGULATORY | Map product to applicable regulatory frameworks: FDA 21 CFR Part 820 (QMS), IEC  | Submission preparation, audit readiness |
| Step 4 | LEGAL | Draft legal artifacts for the ICU monitoring platform: HIPAA Business Associate  | Privacy, licensing, contracts |
| Step 8 | SECURITY | Produce threat model (STRIDE) for the ICU monitoring system covering device comm | Threat modeling, penetration testing |
| Step 9 | COMPLIANCE | Initialize Design History File (DHF) per FDA 21 CFR Part 820 and ISO 13485. Crea | Standards mapping, DHF, traceability |
| Step 16 | EMBEDDED_TEST | Design and implement hardware-in-the-loop (HIL) test specs for device adapter fi | Hardware-in-the-loop verification |
| Step 17 | QA | Produce comprehensive QA test plan covering functional, regression, usability, a | Verification & validation |
| Step 18 | SECURITY | Execute security review and penetration test plan for the ICU monitoring platfor | Threat modeling, penetration testing |
| Step 19 | SYSTEM_TEST | Execute end-to-end system test suite: full patient admit→monitor→alert→acknowled | End-to-end validation, performance |
| Step 20 | COMPLIANCE | Complete DHF with all executed V&V evidence: link each test execution record to  | Standards mapping, DHF, traceability |
| Step 21 | REGULATORY | Prepare FDA 510(k) premarket notification package: predicate device comparison,  | Submission preparation, audit readiness |

**Total tasks:** 24 | **Compliance tasks:** 11 | **Coverage:** 46%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | IEC 62304 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | ISO 13485 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | HL7 FHIR compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
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
| developer | 9 | Engineering |
| regulatory_specialist | 4 | Compliance |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| safety_engineer | 1 | Compliance |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| devops_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 61/100 (FAIL) — 1 iteration(s)

**Summary:** This plan demonstrates genuine regulatory sophistication — the DHF structure, ISO 14971 FMEA, HIPAA controls, and FHIR R4 alignment are handled with appropriate depth, and the 24-step sequencing correctly front-loads compliance artifacts before implementation. However, it has one disqualifying omission (IEC 60601-1-8 for alarm management) and three critical gaps that would cause production failures or regulatory rejection: the IEC 62304 safety class is unresolved at the point where it governs firmware coverage requirements, the FHIR server architecture is left as an open fork through implementation, and real device interoperability testing is absent in favor of a simulator that will not surface vendor-specific HL7 deviations. The MQTT single-broker design, legacy device mTLS gap, and missing Design Validation execution (protocol only, no evidence) are additional showstoppers for a 510(k) submission. For a regulated ICU monitoring SaMD, this plan is solid preliminary work that needs a targeted rework pass on alarm standards compliance, safety class gating, infrastructure HA, and real-device testing before implementation begins. Current state: suitable for design review and stakeholder alignment, not ready to gate implementation start.

### Flaws Identified

1. IEC 60601-1-8 (Alarm Systems for Medical Electrical Equipment) is completely absent from the entire plan. This is the primary standard governing medical alarm management — precisely what this product is. Its omission is not a minor gap; it is a foundational regulatory miss that invalidates the alarm engine design and could block FDA clearance.
2. IEC 62304 software safety class is left as 'Class B or C' (step 3) but this determination gates every subsequent design decision: documentation depth, testing coverage requirements, architecture decomposition, and SOUP management. Deferring this to step 3 while firmware (step 10) assumes ≥80% line coverage is backward. Class C (almost certain for an ICU alerting system) mandates 100% branch coverage of safety-critical units — this plan's 80% line coverage target is flatly non-compliant.
3. Step 11 has an unresolved architectural fork: 'HAPI FHIR (Java) or fhir-kit-client (Node.js)'. These are not interchangeable options — HAPI FHIR is a full server with its own persistence and validation engine; fhir-kit-client is a REST client library requiring a separate FHIR server. Leaving this unresolved at implementation time means the database schema (step 6), API design (step 7), and DevOps (step 15) could all need rework. This is an ADR that must close before step 6.
4. No real physical device interoperability testing exists in the plan. Step 16 builds a Python simulator, but Philips IntelliVue, Dräger Evita, Masimo Radical, and GE Carescape all implement HL7 v2 with vendor-specific extensions, non-standard segment ordering, and proprietary OBX identifiers. A simulator will not expose these divergences. Without testing against actual devices or captured production HL7 traffic, the firmware will fail in the first hospital.
5. The Mosquitto MQTT broker (step 11) is a critical single point of failure for all device data ingestion. In an ICU, broker downtime means loss of all real-time patient monitoring. No clustering, HA configuration, or broker-level persistence is specified. A single Mosquitto instance does not meet the 99.9% SLA defined in step 22.
6. Step 10 firmware target is 'ARM Cortex-A or Cortex-M' — a hardware architecture decision left open during implementation. Bare-metal FreeRTOS and Yocto Linux are fundamentally different development environments with different toolchains, SOUP lists, and IEC 62304 documentation requirements. This must be resolved before any firmware is written.
7. The HL7 v2 → FHIR R4 transformation (step 11) is treated as a 'mapping engine' — a single-step implementation task. In reality this is a 6-12 week effort involving LOINC code mapping tables, handling missing/malformed segments, managing vendor-specific PV1/OBX variants, and building a test corpus from real device traffic. The plan has no dedicated step for this and no acceptance criterion for mapping coverage across device types.
8. Step 14 introduces SAGE AI agent roles ('alert_reviewer', 'clinical_analyst') that could influence clinical alert decisions. If these agents surface clinical recommendations that affect care, they are themselves SaMD requiring separate FDA clearance. The plan neither flags this regulatory risk nor constrains agent outputs to administrative/operational scope only.
9. Design Validation (actual clinical environment testing with clinical staff on patient-representative scenarios) is referenced in step 20 as a 'protocol to be produced' but never executed as a plan step. FDA 21 CFR 820.30(g) requires Design Validation evidence, not just a protocol. The plan ends with a protocol draft, not executed validation evidence.
10. mTLS for device communications (step 8) is specified as a control, but legacy ICU devices — the majority of installed base — do not support TLS at all. RS-232 serial devices and older TCP/IP stacks cannot participate in mTLS. The plan has no fallback architecture (e.g., TLS-terminating gateway proxy at the device interface layer) and no acceptance criterion for how non-TLS devices are handled.
11. Step 22 defines an RTO of 15 minutes but no DR test is in the plan. Runbook documentation does not prove RTO achievability. The load test (step 19) is scoped to 50 patients under normal conditions, not failover scenarios. A 15-minute RTO for an ICU system requires tested, measured failover — not documented intent.
12. Missing: physiological plausibility validation on ingested data. A SpO2 reading of 150%, heart rate of 500 bpm, or arterial BP of 300/200 mmHg from a malfunctioning or mis-configured device will pass through the ingestion pipeline, be stored, and trigger alerts. No range-gate, calibration-drift detection, or implausibility flagging exists in the design.

### Suggestions

1. Add a dedicated step 2.5 (before firmware design) to resolve the IEC 62304 software safety class and produce the Software Development Plan. Gate all subsequent development steps on this determination. Expect Class C — design for it from the start.
2. Add IEC 60601-1-8 to the regulatory mapping in step 3 and create a dedicated alarm management design step between steps 12 and 13 covering: alarm prioritization taxonomy (high/medium/low/advisory), alarm signal characteristics, alarm condition persistence logic, and nurse override/silence policies. This is not optional for a product in this category.
3. Replace the Mosquitto single broker with a clustered MQTT setup (EMQX cluster or HiveMQ with HA) or use a Kafka-backed ingestion pipeline for device data, with MQTT as the edge protocol only. Document the HA architecture explicitly before step 11.
4. Capture real HL7 traffic from at least one target device type (even in a lab environment) before implementing the transformation engine. Create a dedicated 'Device Interoperability Spike' step between steps 10 and 11 with the deliverable of a validated HL7 corpus for each device type.
5. Add a step for hospital IT infrastructure dependency resolution: VLAN provisioning approval, network access to device ports, firewall rule changes, and integration engine assessment (Mirth Connect/Rhapsody/Corepoint). In most hospitals this takes 4-12 weeks and cannot run in parallel with firmware development.
6. Constrain SAGE agent roles (step 14) to administrative and operational tasks only (alert routing, shift handover summaries, compliance check status). Add explicit documentation that agent outputs are not clinical decision support and are not used in direct patient care decisions. Alternatively, scope out AI agent functionality until post-clearance.
7. Add a time synchronization design section to step 6/7: NTP/PTP sync requirements for device adapters, handling of late-arriving or out-of-order messages, and timestamp normalization policy. Without this, trend charts and alert timing will be unreliable when device clocks drift.
8. Add firmware SOUP (Software of Unknown Provenance) management per IEC 62304 Section 8 as an explicit deliverable in step 10. Each third-party library used in firmware must have a documented version, known anomalies list, and regression test evidence. This is an audit finding target.
9. Add FDA 2023 Cybersecurity post-market requirements to step 21: ongoing SBOM monitoring process, coordinated vulnerability disclosure policy, and software update mechanism documentation. The 2023 guidance makes these mandatory for submissions.

### Missing Elements

1. IEC 60601-1-8 alarm management standard — entirely absent, directly applicable
2. Dedicated IEC 62304 Software Safety Classification step with gating logic before design begins
3. Real device interoperability testing step (not simulator-only) with vendor-specific HL7 corpus
4. Hospital IT/infrastructure dependency resolution step (VLAN, firewall, integration engine assessment)
5. HL7 Clinical Integration Engine (Mirth/Rhapsody) assessment — most hospitals route all HL7 through a CIE, bypassing the plan's assumed direct device connectivity
6. ADT feed from EHR (Epic/Cerner) for patient admission/discharge/transfer synchronization — without this, patient-device linkage depends on manual entry
7. Time synchronization design: NTP/PTP policy for device adapters, clock skew handling in data pipeline
8. Physiological plausibility validation layer on ingested observations
9. Joint Commission NPSG 06.01.01 alarm management requirements (US hospital accreditation standard)
10. FDA post-market cybersecurity surveillance program (required by 2023 guidance for 510(k) submissions)
11. Executed Design Validation (clinical environment) — plan produces protocol but never executes it
12. SOUP list and anomaly tracking per IEC 62304 Section 8 for all firmware and backend components
13. DR failover test demonstrating 15-minute RTO is achievable
14. Coordinated Vulnerability Disclosure (CVD) program documentation
15. Architectural Decision Record closing the HAPI FHIR vs. alternative FHIR server selection before step 6

### Security Risks

1. SSE stream reconnection (step 12/13): if the EventSource reconnects without re-authenticating the OAuth token, an expired or revoked token could maintain an active PHI stream. The plan does not specify token re-validation on SSE reconnect.
2. WebSocket device ingestion endpoint (step 7/11): device-to-server WebSocket authentication relies on mTLS, which legacy devices cannot perform. If the fallback for non-mTLS devices uses API key or IP allowlisting, those controls are not specified and are typically weak.
3. HL7 v2 injection: the fuzzing test in step 18 is correct to include, but the HL7 parser in step 10/11 must also be validated for buffer overflow and memory safety — particularly if the C-based HL7 v2 parser processes untrusted device input over TCP. This is a remote code execution surface on a medical device gateway.
4. Nurse station webhook endpoint: step 12 lists 'REST webhook' as a nurse station protocol. Incoming webhooks without HMAC signature validation are trivially spoofable and could inject false alert acknowledgments, creating a patient safety risk (alert marked acknowledged when it was not).
5. PHI in Prometheus/Grafana metrics: step 15 uses Prometheus for monitoring. If any metric labels include patient identifiers (e.g., per-patient alert counts), PHI will be present in the metrics endpoint. This is a common HIPAA violation in observability stacks.
6. ELK stack PHI masking (step 15): 'PHI field masking' is listed as a requirement but the implementation is undefined. Log shipping pipelines frequently have timing gaps where unmasked PHI appears in intermediate buffers (Logstash pipeline, Elasticsearch indexing queue) before masking is applied.
7. Keycloak SMART on FHIR plugin maturity: the Keycloak SMART on FHIR community plugin has known gaps in the EHR launch context flow and is not officially supported by Keycloak. Production ICU use should evaluate a purpose-built SMART authorization server (e.g., Inferno-compatible) instead.
8. Admin console threat surface (step 8): the RBAC matrix covers nurse/intensivist/admin/biomedical roles but does not specify what the 'admin' role can access. Unrestricted admin access to PHI query endpoints, FHIR history, and audit logs is a HIPAA minimum-necessary violation risk.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.307700
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

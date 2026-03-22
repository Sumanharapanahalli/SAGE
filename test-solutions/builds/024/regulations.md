# Regulatory Compliance — Fleet Telematics

**Domain:** automotive
**Solution ID:** 024
**Generated:** 2026-03-22T11:53:39.314900
**HITL Level:** strict

---

## 1. Applicable Standards

- **ELD Mandate**
- **FMCSA**
- **GDPR**
- **SOC 2**

## 2. Domain Detection Results

- automotive (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | REGULATORY | Map all applicable regulatory requirements: FMCSA ELD mandate (49 CFR Part 395), | Submission preparation, audit readiness |
| Step 5 | SAFETY | Perform system-level FMEA and hazard analysis for the telematics ECU and connect | Risk management, FMEA, hazard analysis |
| Step 6 | SECURITY | Perform threat modeling (STRIDE) for the telematics platform per UNECE R155/R156 | Threat modeling, penetration testing |
| Step 23 | EMBEDDED_TEST | Build hardware-in-the-loop (HIL) test harness for the telematics ECU: inject sim | Hardware-in-the-loop verification |
| Step 24 | COMPLIANCE | Produce FMCSA ELD self-certification package: technical documentation, test resu | Standards mapping, DHF, traceability |
| Step 25 | LEGAL | Draft terms of service, driver data privacy policy (CCPA/GDPR), data processing  | Privacy, licensing, contracts |
| Step 27 | QA | Design and execute QA test plan: driver app ELD workflow, fleet dashboard GPS ac | Verification & validation |
| Step 28 | SYSTEM_TEST | Execute end-to-end system test: physical or simulated ECU → MQTT → backend → das | End-to-end validation, performance |

**Total tasks:** 32 | **Compliance tasks:** 8 | **Coverage:** 25%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | ELD Mandate compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | FMCSA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 4 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |

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
| regulatory_specialist | 3 | Compliance |
| firmware_engineer | 3 | Engineering |
| devops_engineer | 3 | Engineering |
| data_scientist | 3 | Analysis |
| safety_engineer | 2 | Compliance |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| product_manager | 1 | Design |
| business_analyst | 1 | Analysis |
| marketing_strategist | 1 | Operations |
| ux_designer | 1 | Design |
| legal_advisor | 1 | Compliance |
| system_tester | 1 | Engineering |
| financial_analyst | 1 | Analysis |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This plan is broad, structured, and clearly authored by people who understand fleet telematics at a systems level. The dependency graph is coherent, the acceptance criteria are specific, and the regulatory awareness (FMCSA, UNECE R155) is above average for this type of plan. However, it has three fatal gaps that prevent a production score above 60 for a regulated hardware product. First, the hardware device — the physical ECU — has no design step, no PCB, no BOM, no FCC/CE certification plan, and no carrier approval process; firmware and HIL tests cannot proceed on undefined hardware, and the device cannot be legally sold without RF certification. Second, the ISO 26262 application is incorrect — assigning ASIL levels to passive data logging functions will fail any functional safety audit and may create liability exposure by implying safety claims the product cannot substantiate. Third, the ML models have a training data bootstrapping problem with no solution: the product needs real fleet data to produce useful predictions, but real fleet data only exists after the product is deployed and trusted. The plan assumes this problem doesn't exist. The MISRA C zero-violations criterion, AUTOSAR Classic without tooling budget, and Expo for an ELD-certified mobile app are individually fixable but collectively indicate the plan was written without scoping the embedded/regulatory implementation cost. Estimate these gaps add 4-8 months and $500k+ to the delivery timeline before the plan becomes executable as written.

### Flaws Identified

1. MISRA C 'zero violations' in Steps 9 and 10 is unachievable in practice. FreeRTOS itself ships with documented MISRA deviations. The correct acceptance criterion is 'zero unjustified deviations' with a deviation log — not zero violations. Any CI gate enforcing zero will block the build permanently on the first third-party include.
2. ISO 26262 scope is misapplied. ISO 26262 governs E/E systems that can cause physical harm to vehicle occupants or road users. A read-only telematics ECU that does not actuate any vehicle system does not meet the 'controllability' threshold for ASIL assignment. Assigning ASIL A to 'HOS alerts' (an informational notification) and ASIL B to 'brake event detection' (which is passive logging, not brake control) misuses the standard and will fail a functional safety audit. The actual applicable standard for a data-logging device is ISO/SAE 21434 for cybersecurity, not ISO 26262.
3. AUTOSAR Classic BSW mapping in Steps 9 and 10 requires commercial AUTOSAR toolchains (EB tresos Studio, Vector DaVinci Configurator). These are $50k+ annual licenses. Acceptance criterion 'AUTOSAR compliance checked' is not a functional test — AUTOSAR conformance testing requires accredited test labs. Treating this as a firmware checkbox will fail any OEM integration audit.
4. ML training data bootstrapping problem is unresolved. Steps 14, 15, and 16 depend on 'labeled fleet data' and 'fleet data from Step 13,' but Step 13 is the ingestion infrastructure — not a data collection program. The product has no data before launch. The AUC >0.82 target on synthetic SHRP2 data does not validate real-world fleet performance. No warm-start strategy, no minimum fleet size for statistical validity, no model confidence floor before serving predictions to real operators.
5. SHRP2 naturalistic driving data access is non-trivial. It requires a formal data-sharing agreement with Virginia Tech Transportation Institute (VTTI) and IRB-equivalent review. Treating it as a passive dependency ('publicly available') is incorrect — it is licensed data with use restrictions.
6. Hardware design is entirely absent. The plan includes firmware (Step 9), hardware simulation (Step 8), and HIL testing (Step 23) but zero steps for PCB schematic, component selection, thermal design, EMC/EMI testing, or hardware design review. You cannot build firmware for undefined hardware.
7. FCC/IC/CE certification for the telematics ECU device is missing. Any device sold in the US that emits RF (LTE modem + GPS) requires FCC Part 15/Part 90 certification. This is a multi-month process with an accredited test lab. Without it, the device cannot be legally sold or installed. This is a hard stop before Step 28.
8. Cellular carrier certification is absent. Devices connecting to AT&T, Verizon, or T-Mobile LTE networks require carrier device certification (PTCRB/GCF) in addition to FCC approval. Fleet operators will demand certified devices. This can take 3-6 months and is not mentioned anywhere.
9. React Native Expo (Step 19) is incompatible with ELD compliance requirements. FMCSA mandates three data transfer methods including USB. Expo managed workflow does not support USB host/accessory mode, custom BLE service UUIDs required for ELD profile, or background location with the reliability required for continuous HOS tracking. This requires a bare React Native workflow with native modules — a significant architecture change.
10. ELD cryptographic signature private key storage on mobile (Step 19) has no security specification. 'ELD log sign-off generates cryptographic signature' without specifying Secure Enclave (iOS) / StrongBox (Android) usage means keys will likely land in AsyncStorage or app storage — readable by any process with device access. An FMCSA auditor or court discovery will invalidate signatures stored this way.
11. PostGIS is missing from the database design (Step 11). TimescaleDB does not natively support geospatial queries. The acceptance criterion 'geospatial queries return in <200ms on 1M rows' requires PostGIS with GIST spatial indexes. Without it, bounding-box queries will full-scan the telemetry table and fail the latency target at any meaningful scale.
12. MQTT topic structure enables cross-tenant enumeration. `fleet/{vehicle_id}/telemetry` with predictable vehicle IDs allows a subscriber with a valid broker connection to subscribe to `fleet/+/telemetry` and receive data across all fleets. Broker-level ACLs per tenant are not specified anywhere in the plan.
13. GDPR right to erasure vs. FMCSA 6-month retention is flagged as a documentation task (Step 25) but requires a concrete technical implementation decision. You cannot delete ELD records on GDPR request while simultaneously satisfying FMCSA retention. The legal position (FMCSA as a superseding federal obligation) must be codified in the privacy policy AND technically enforced (selective field suppression vs. full deletion). This is not just a lawyer task.
14. Vehicle provisioning flow has no dedicated design step. Step 31 references a 'vehicle onboarding runbook' and Step 21 mentions AWS IoT Core certificates, but no step designs the device provisioning API: IMEI registration, X.509 certificate issuance and push to device, fleet assignment, and first-telemetry validation. This is a critical operational gap — field technicians have no defined workflow.
15. UNECE R155 type approval process is misunderstood. R155 type approval is conducted by national type approval authorities (TÜV SÜD, DEKRA, etc.) on behalf of vehicle OEMs, not aftermarket telematics vendors. A telematics device supplier provides a CSMS and evidence package to the OEM, who applies for type approval. Step 6 and Step 24 treat this as the vendor's own certification — which is incorrect and will produce documentation that no OEM can use.
16. LTE PPP stack choice (Step 9) is outdated and fragile. Modern SIM7600/EC25 modems support ECM or RNDIS Ethernet emulation mode, which gives a standard network interface to the RTOS TCP/IP stack without implementing PPP. PPP adds dial-up-era complexity, higher CPU overhead, and fragile reconnection behavior that will cause store-and-forward data loss in poor signal conditions.
17. The plan has no V2X, fleet integrations (TMW, PeopleNet, Omnitracs), or ERP/dispatch system integration story. Competing against Samsara and Geotab without an open API and integration marketplace is a market positioning failure, not just a technical gap.
18. Load test in Step 28 targets '10,000 vehicles at 1Hz telemetry for 10 minutes' using k6. k6 is an HTTP load testing tool — it does not natively support MQTT protocol simulation at scale. 10,000 concurrent MQTT connections requires a purpose-built MQTT load generator (mqttx-cli, JMeter MQTT plugin, or custom tooling). Using k6 for this will produce misleading results.

### Suggestions

1. Replace 'MISRA C zero violations' with 'all MISRA C:2012 deviations documented with rationale, approved by safety engineer, total deviations < 50.' Use PC-lint Plus or LDRA for enforcement — not a CI regex.
2. Remove ISO 26262 from the telematics ECU scope unless the ECU will actuate vehicle systems. Replace with ISO/SAE 21434 (automotive cybersecurity), which is the correct standard for a connected telematics device. Retain the FMEA for failure mode analysis — just don't assign ASIL levels to passive logging functions.
3. Add a dedicated HARDWARE step between Steps 8 and 9: PCB schematic, component BOM with lead times, thermal design review, and EMC pre-scan. This unblocks firmware, HIL, and FCC certification in parallel. Without it, Steps 9, 23, and 28 have no validated hardware target.
4. Add FCC/IC/CE certification as an explicit step with a dependency on hardware design. Assign it between Steps 8 and 23. It is a critical path blocker for GA and must start as early as EVT hardware is stable.
5. For ML cold-start: define a 'shadow mode' launch where models run but do not surface predictions to users until a minimum 30-day dataset from 200+ vehicles is available per fleet. Specify synthetic pre-training accuracy thresholds separately from production accuracy thresholds.
6. Replace Expo with bare React Native from the start. Define required native modules: react-native-ble-plx (BLE ELD transfer), react-native-usb (USB transfer), react-native-keychain (Secure Enclave key storage), react-native-background-geolocation (continuous HOS tracking). Specify iOS minimum iOS 15 for CryptoKit Secure Enclave access.
7. Add PostGIS to Step 11's database design. Add GIST index on `telemetry(location)` where location is a PostGIS geography type. Restate geospatial query acceptance criterion explicitly as 'ST_Within bounding box query on PostGIS geography column with GIST index.'
8. Add an MQTT ACL design document as a deliverable in Step 12. Define per-tenant topic namespacing (e.g., `t/{tenant_id}/fleet/{vehicle_id}/telemetry`) and require broker-enforced ACL that rejects cross-tenant subscriptions. Test with a negative case: fleet A's credentials attempt to subscribe to fleet B's topic.
9. Split Step 24 into two steps: (a) FMCSA self-certification package (executable by the vendor), and (b) CSMS evidence package preparation for OEM partners pursuing UNECE R155 type approval. Clarify that your organization produces (b) as a vendor deliverable — OEMs carry the type approval burden.
10. Add an explicit MQTT load testing tool to Step 28. Use mqttx-cli (`mqttx bench pub -c 10000 -t 'fleet/{id}/telemetry' -im 1000`) or a custom Go MQTT publisher. Document the load test tool in the acceptance criteria so reviewers can reproduce the results.
11. Add a Step 33: FCC/IC/CE Certification and Carrier Approval. Dependencies: Step 8 (hardware sim), hardware design step. Deliverables: FCC grant of authorization, PTCRB certification report, carrier device approval letters. This is the hard gate before commercial deployment.

### Missing Elements

1. Hardware PCB design step — schematics, BOM, component selection, thermal analysis, signal integrity review
2. FCC Part 15 / PTCRB / CE certification plan and timeline for the ECU device
3. Device provisioning API design — X.509 certificate lifecycle, IMEI registration, first-boot enrollment flow
4. PostGIS spatial extension in database design
5. MISRA C deviation management process (deviation log format, approval workflow, deviation budget)
6. ML warm-start and cold-start strategy — minimum data requirements before model serves live predictions
7. MQTT per-tenant ACL specification
8. OTA key ceremony procedure — HSM setup, key generation, key custody policy, rotation schedule, revocation procedure
9. V2X and third-party fleet management system integration API (TMW, McLeod, PeopleNet) — required for enterprise fleet operator adoption
10. Vehicle compatibility matrix — not all commercial vehicles expose J1939 PGNs; older vehicles may require OBD-II only fallback; some vehicles have non-standard CAN implementations
11. SIM card / cellular provider agreements and APN configuration management for deployed devices
12. GPS cold-start, TTFF (time to first fix) specification, and HDOP threshold policy (when to reject GPS readings as inaccurate)
13. FMCSA ELD Technical Standard version reference (current is v4.0) — acceptance criteria should cite specific document version
14. Carrier certification step (AT&T FirstNet for public safety, Verizon Network Access Requirements)
15. Step for GDPR data subject rights technical implementation — how deletion requests are processed when FMCSA retention creates a hold

### Security Risks

1. MQTT topic enumeration: `fleet/{vehicle_id}/telemetry` with sequential or guessable vehicle IDs allows a compromised or rogue device to subscribe to `fleet/+/telemetry` and harvest all fleet data. No broker ACL design is specified.
2. ELD cryptographic key on mobile device: Step 19 requires cryptographic signature of ELD logs but does not specify Secure Enclave (iOS) / Android StrongBox usage. Keys in app-accessible storage can be extracted from a rooted device, invalidating the tamper-evidence guarantee that regulators require.
3. WebSocket token refresh not addressed: Live map WebSocket connections are long-lived (hours). JWT expiry during an active session will either silently continue serving stale auth or abruptly disconnect fleet managers. Neither is specified, and the silent-continue case is a broken access control.
4. OTA rollback attack: Step 9 specifies ECDSA-256 signature verification for OTA updates but does not specify anti-rollback counters. A signed but older (vulnerable) firmware version is a valid ECDSA signature. Without a monotonic version counter in OTP memory, a downgrade attack restores known vulnerabilities.
5. CAN bus injection no authentication: Step 9 reads J1939 PGNs from CAN bus with no input validation or anomaly detection on the bus. A compromised OBD-II dongle or tampered CAN node could inject falsified fuel consumption, RPM, or mileage values that corrupt driver scoring and predictive maintenance models — directly undermining the product's core value proposition.
6. Driver GPS location continuous exposure: Step 25 lists GPS location as a collected data category, but the data model in Step 11 stores lat/lon at 10Hz. This is surveillance-grade location granularity. No data minimization strategy (e.g., location fuzzing at rest stops, geofenced location suppression near driver's home) is specified, creating CCPA/GDPR class action exposure.
7. SBOM not enforced in CI: Step 6 requires an SBOM for ECU firmware dependencies, but Step 22's firmware CI pipeline (`arm-none-eabi-gcc → unity tests → binary sign → S3`) has no SBOM generation or dependency vulnerability scanning step. The SBOM becomes a snapshot artifact, not a living supply chain control.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.314964
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)

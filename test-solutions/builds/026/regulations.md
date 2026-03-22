# Regulatory Compliance — Obd Diagnostics App

**Domain:** automotive
**Solution ID:** 026
**Generated:** 2026-03-22T11:53:39.315787
**HITL Level:** strict

---

## 1. Applicable Standards

- **OBD-II Standard**
- **SAE J1979**
- **ISO 15031**

## 2. Domain Detection Results

- automotive (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 5 | LEGAL | Draft Terms of Service, Privacy Policy (GDPR/CCPA compliant), mechanic marketpla | Privacy, licensing, contracts |
| Step 6 | SAFETY | Perform safety analysis per ISO 26262 and ISO 14971 (if health monitoring featur | Risk management, FMEA, hazard analysis |
| Step 7 | COMPLIANCE | Produce compliance artifacts for UNECE R155/R156 (cybersecurity/OTA), SOC 2 Type | Standards mapping, DHF, traceability |
| Step 19 | SECURITY | Security review and implementation: OBD session authentication (prevent unauthor | Threat modeling, penetration testing |
| Step 20 | EMBEDDED_TEST | Write HIL test specs and firmware unit tests for OBD-II adapter: BLE GATT charac | Hardware-in-the-loop verification |
| Step 23 | SYSTEM_TEST | Execute system-level integration test suite: full DTC scan flow (mobile → BLE si | End-to-end validation, performance |
| Step 28 | QA | Execute QA test plan: exploratory testing of all user flows on physical Android  | Verification & validation |

**Total tasks:** 30 | **Compliance tasks:** 7 | **Coverage:** 23%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | OBD-II Standard compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | SAE J1979 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | ISO 15031 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| qa_engineer | 4 | Engineering |
| devops_engineer | 3 | Engineering |
| safety_engineer | 2 | Compliance |
| technical_writer | 2 | Operations |
| marketing_strategist | 1 | Operations |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| financial_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| regulatory_specialist | 1 | Compliance |
| ux_designer | 1 | Design |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This is an ambitious, well-structured plan that covers the full product lifecycle and demonstrates genuine domain knowledge in OBD-II protocols, marketplace mechanics, and mobile development. However, it has two categories of fatal flaw that require rework before execution. First, the compliance scope is systematically wrong: ISO 26262, ISO 14971, UNECE R155/R156, and AUTOSAR CP are OEM automotive standards that do not apply to an aftermarket consumer app. Applying them will consume 20-30% of the budget generating artifacts that provide no legal protection and mislead the team about their actual obligations. Replace with proportionate product liability analysis, OWASP MASVS, and GDPR/CCPA scope review. Second, the core architecture has a structural flaw: the backend cannot hold BLE connections, making the 'OBDSessionManager BLE proxy' in Step 14 unimplementable as written. This must be redesigned as a mobile-side session manager before any backend work begins. Beyond these, three high-severity gaps — TimescaleDB on RDS incompatibility, the missing BLE simulation layer for E2E tests, and DTC code IP licensing — will cause expensive late-stage failures. The security section is directionally correct but leaves critical gaps in token storage, webhook signature verification, and OBD write command enforcement. Score 54: the plan has a solid foundation and the right instincts, but the compliance misdirection and architectural flaw require targeted rework on Steps 6, 7, 11, 13, and 14 before greenlit execution.

### Flaws Identified

1. ISO 26262 does not apply to aftermarket diagnostic apps. It governs OEM road vehicle E/E system development. Applying ASIL classification to a third-party OBD app will waste months on inapplicable compliance work and produce artifacts that provide false assurance. Same problem with AUTOSAR CP — that is an OEM ECU framework, not an aftermarket BLE adapter standard.
2. ISO 14971 is a medical device standard. It has zero applicability here unless the app is making clinical health claims. Listing it in the safety step signals a fundamental misreading of the standard.
3. UNECE R155/R156 bind vehicle manufacturers (OEMs) seeking type approval, not third-party software vendors. An OBD diagnostics app does not require a CSMS under R155. Building a full CSMS policy document for a startup app is a resource sink based on a compliance scope error.
4. The backend 'OBDSessionManager (ELM327 BLE proxy, connection pool)' is architecturally incorrect. BLE is a direct radio connection between the mobile device and the adapter — the cloud backend cannot hold BLE connections. This must be a mobile-side session manager that relays OBD data to the backend via REST or WebSocket. If this flaw propagates to implementation, the core scan flow will not work.
5. TimescaleDB on AWS RDS is not straightforward. RDS does not grant superuser access required for TimescaleDB installation via the standard extension mechanism. The plan needs Timescale Cloud, a self-managed PostgreSQL on EC2, or an explicit workaround. Discovering this during Step 24 infra setup will block Step 9 schema work retroactively.
6. The SimPy BLE simulator (Step 10) emulates ELM327 over a TCP socket, not over BLE. The React Native app uses react-native-ble-plx which requires a real BLE radio or a BLE hardware simulator. Maestro E2E tests in Step 22 that depend on 'BLE sim' will fail at this gap — there is no BLE-level simulation layer in the plan.
7. Manufacturer-specific DTC codes (P1xxx–P3xxx, B-codes, C-codes, U-codes) are proprietary to each OEM. Distributing 20,000+ DTC descriptions in a SQLite DB without OEM licensing agreements exposes the product to IP infringement. Standard SAE P0xxx codes are public; everything else is not.
8. iOS background BLE mode is severely restricted by Apple. Sustained live sensor polling at 1Hz in the background is not permitted under standard BLE background modes. This fundamentally breaks the live dashboard use case when the app is backgrounded. The plan has no mitigation.
9. NHTSA vPIC has no SLA, is periodically unavailable, and has gaps for pre-1980 vehicles, imports not sold in the US, and grey-market VINs. Using it as the sole VIN decoder with a <500ms acceptance criterion will fail during NHTSA outages. No fallback decoder is specified.
10. Stripe Connect for a mechanic marketplace triggers money transmitter licensing considerations in multiple US states. The plan identifies commission structure and payouts but omits the legal analysis of whether the platform is acting as a payment facilitator requiring state-level licensing or exemption filings. This is not covered in the legal step.
11. No hardware design step exists. Step 11 implements firmware for an ESP32-S3 adapter, but there is no step for PCB schematic, BOM, FCC Part 15 / CE BLE certification, OBD-II 16-pin connector compliance, or manufacturing. If this product ships a physical adapter, the plan is missing its entire hardware layer. If it relies on third-party adapters, the firmware step is misscoped.
12. The database schema (Step 9) has no fleet/organization tables, yet fleet management is a named user segment and a v2 roadmap item. Fleet operators need vehicle_groups, organizations, driver assignments, and fleet_users. Retrofitting this onto a live schema is expensive.
13. Step 15 adds a disputed booking state with a '72h escalation to ops team' but no ops team is staffed or budgeted in the plan. Marketplace disputes require human judgment and will arrive from day one of launch. There is no fraud detection implementation step — only a fraud runbook.

### Suggestions

1. Replace ISO 26262 with a targeted product liability and consumer safety analysis: identify hazards (wrong repair advice → unsafe repair → injury), document risk mitigations (disclaimers, severity classification, 'consult a professional' gates), and reference ISO/IEC 25010 software quality model instead.
2. Replace the UNECE R155 CSMS requirement with a proportionate cybersecurity controls document aligned to OWASP MASVS and NIST CSF. This achieves the actual security goal without inapplicable regulatory overhead.
3. Redesign the OBD session architecture: mobile app owns the BLE connection and runs an on-device ELM327 session manager. Data is relayed to the backend via WebSocket or chunked REST. The backend SSE endpoint rebroadcasts to the frontend. This is the correct topology for BLE-mediated vehicle data.
4. Replace RDS + manual TimescaleDB with Timescale Cloud (managed) or rewrite Step 9 to use RDS with vanilla PostgreSQL partitioning + BRIN indexes on timestamp columns as a TimescaleDB-free alternative that works reliably on RDS.
5. Add a BLE hardware-in-the-loop simulation layer: nRF52840-DK running a GATT server emulator, or use Android BLE emulation via a dedicated test device running a BLE peripheral app. Document this as a test fixture in Step 10 so Steps 20 and 22 can actually execute.
6. Add a DTC licensing step before Step 9: audit which codes are SAE public domain vs. OEM proprietary, source a licensed DTC database (Mitchell 1, Snap-on, ALLDATA have licensed datasets), or restrict the app to SAE standard codes only for MVP.
7. Add iOS BLE background entitlement research to Step 8/16: determine if use-peripheral mode + local notifications can satisfy the live dashboard use case, or require the app to be foregrounded during scanning (most production OBD apps do this).
8. Add a hardware design workstream as a parallel track to firmware (Step 11): PCB design, component selection, FCC/CE pre-certification test plan, and contract manufacturer evaluation. This is a prerequisite for any physical product.
9. Add a legal step specifically for Stripe Connect compliance: money transmitter license analysis per state, 1099-K reporting requirements for mechanic payouts, and consumer protection obligations for payment disputes.
10. Add a mechanic background check integration (Checkr or similar) to Step 15 verification flow. A marketplace that dispatches strangers to customers' vehicles without background checks creates significant liability and will face App Store scrutiny.
11. Add SAE J1979-2 (UDS-based OBD for 2023+ vehicles) to the firmware and backend scope, or explicitly scope it out with a documented decision. Torque Pro and BlueDriver already support this — ignoring it cedes the newest vehicle segment.

### Missing Elements

1. Hardware design and manufacturing workstream (PCB, BOM, FCC/CE certification, OBD connector compliance) — absent entirely if this is a hardware+software product
2. Applicable compliance framework for the actual regulatory exposure: CCPA/GDPR data residency for EU users, COPPA if minors can use the app, and PCI DSS scope assessment for payment card handling via Stripe
3. DTC database licensing strategy and IP clearance for manufacturer-specific codes
4. iOS App Store hardware accessory compliance (MFi program review, BLE accessory guidelines, payment processing rules for apps with physical hardware)
5. Fleet data model: organization, fleet_vehicles, driver_assignment tables missing from Step 9 schema despite fleet being a defined user segment
6. Fraud detection implementation (not just a runbook): automated flagging of fake reviews, payout fraud, and mechanic account takeover — must be built, not just responded to
7. SAE J1979-2 / ISO 15031-5 UDS compatibility for 2023+ vehicles
8. Data residency and cross-border data transfer mechanism for GDPR (SCCs, adequacy decision) if EU users are in scope
9. Mechanic background check integration (Checkr, Veriff, or equivalent)
10. App Store / Google Play policy review step before development start — both stores have specific policies for apps connecting to hardware and processing payments that can cause rejection
11. On-call staffing plan and ops team definition — referenced in Step 26 but never provisioned
12. OBD adapter partnership strategy: are they manufacturing the adapter, white-labeling an existing one (Veepeak, OBDLink), or supporting third-party adapters? This decision changes scope of Steps 11 and 20 entirely

### Security Risks

1. BLE session key exchange (ECDH) described in Step 19 is correct in principle, but the plan does not address key pinning on the mobile side or GATT service UUID obfuscation. An attacker with a BLE sniffer can enumerate GATT services, identify the OBD characteristic, and inject AT commands if the session key exchange is not enforced before any command is accepted.
2. OBD Mode 04 (clear DTCs) is a write command. Mode 27 (security access) and manufacturer-specific modes can actuate actuators or unlock ECU programming. The 'read-only by default' allowlist in Step 19 must explicitly enumerate every blocked command — a 'deny unknown' policy is required, not just blocking known writes. The current plan is insufficiently specific.
3. VIN stored encrypted via pgcrypto: pgcrypto column-level encryption does not prevent application-layer leaks. If the FastAPI service is compromised, it decrypts VINs in memory on every query. Application-level encryption is not a substitute for proper data classification and need-to-know access controls. The plan conflates encryption with access control.
4. NHTSA vPIC VIN decode in Step 14 passes raw user-supplied VINs to an external API. No input sanitization or VIN format validation is specified before the external call. A malformed VIN or SSRF-crafted input could be forwarded to NHTSA's endpoint.
5. JWT rotation is mentioned in Step 19 but the refresh token revocation mechanism is not detailed. Without a token revocation list or short-lived access tokens backed by a revocation store, a stolen refresh token grants indefinite access. This is especially critical given the vehicle data and payment scope.
6. Stripe webhook processing in Step 15 specifies idempotency but does not mention Stripe webhook signature verification (stripe-signature header). Without signature verification, any actor can POST fake payment confirmation events to trigger mechanic payouts.
7. Firmware OTA via 'HTTPS + RSA-2048 signature' in Step 11: the plan does not specify how the signing key is protected in the CI/CD pipeline. Step 25 mentions 'AWS KMS for firmware codesign' which is correct, but the acceptance criteria in Step 11 do not cross-reference this requirement, leaving a gap where a non-KMS signing approach could pass Step 11 review.
8. The React Native app stores JWT tokens — the plan does not specify secure storage (iOS Keychain / Android Keystore via react-native-keychain). AsyncStorage is insecure for auth tokens and is the default in many RN setups. This is an OWASP Mobile M1 violation.
9. PostGIS geospatial mechanic search exposes approximate user location on every search query. No location fuzzing or radius obfuscation is specified. A malicious mechanic who creates multiple accounts can triangulate a user's home address through repeated search queries from different positions.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.315857
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
